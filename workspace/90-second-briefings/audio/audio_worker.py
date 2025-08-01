#!/usr/bin/env python3
"""
Mini-Worker #3: Audio Narration Pipeline (TTS)
Converts briefings to high-quality audio for premium subscribers
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import json
import hashlib
import tempfile
import subprocess
from pathlib import Path

import openai
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
import boto3
from botocore.exceptions import ClientError

from core.mini_worker import MiniWorker, WorkerType
from core.summarizer_worker import CompleteBriefing, BriefingSection

@dataclass
class AudioSegment:
    section_title: str
    content: str
    duration_seconds: float
    file_path: str
    voice_settings: Dict[str, Any]

@dataclass
class PodcastEpisode:
    id: str
    title: str
    description: str
    briefing_id: str
    duration_seconds: float
    file_path: str
    file_size_bytes: int
    created_at: datetime
    segments: List[AudioSegment]
    download_url: Optional[str] = None
    rss_url: Optional[str] = None

@dataclass
class VoiceProfile:
    name: str
    openai_voice: str  # alloy, echo, fable, onyx, nova, shimmer
    speed: float
    stability: float
    description: str

class AudioWorker(MiniWorker):
    """
    Specialized Mini-Worker for audio generation and podcast creation
    Handles TTS, audio processing, hosting, and RSS feed generation
    """
    
    def __init__(self, worker_id: str = "Audio-01"):
        super().__init__(worker_id, WorkerType.AUDIO)
        
        # Initialize TTS client
        self.openai_client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Initialize cloud storage
        self.s3_client = None
        self._setup_s3_client()
        
        # Voice profiles for different content types
        self.voice_profiles = {
            "professional": VoiceProfile(
                name="Professional News",
                openai_voice="nova",
                speed=1.0,
                stability=0.8,
                description="Clear, authoritative voice for business news"
            ),
            "conversational": VoiceProfile(
                name="Conversational",
                openai_voice="alloy",
                speed=1.1,
                stability=0.7,
                description="Friendly, engaging voice for casual content"
            ),
            "tech_focused": VoiceProfile(
                name="Tech Expert",
                openai_voice="echo",
                speed=0.95,
                stability=0.9,
                description="Tech-savvy voice for technical content"
            )
        }
        
        # Audio settings
        self.audio_config = {
            "sample_rate": 24000,
            "format": "mp3",
            "bitrate": "128k",
            "normalize": True,
            "add_intro": True,
            "add_outro": True
        }
        
        # S3 bucket for hosting
        self.s3_bucket = os.getenv("S3_BUCKET_NAME", "90-second-briefings-audio")
        
    def _setup_s3_client(self):
        """Setup AWS S3 client for audio hosting"""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )
            self.logger.info("S3 client initialized for audio hosting")
        except Exception as e:
            self.logger.warning(f"S3 client setup failed: {e}")
    
    async def execute_task(self, task_id: str):
        """Execute audio generation task"""
        task = await self.task_queue.get_task(task_id)
        if not task:
            return
        
        self.logger.info(f"Executing audio task: {task.description}")
        
        try:
            if task.task_type == "generate_audio":
                result = await self._generate_audio_briefing(
                    task.parameters.get("project_id"),
                    task.parameters.get("briefing_task")
                )
            
            elif task.task_type == "create_podcast_episode":
                result = await self._create_podcast_episode(
                    task.parameters.get("briefing_data"),
                    task.parameters.get("voice_profile", "professional")
                )
            
            elif task.task_type == "generate_rss_feed":
                result = await self._generate_podcast_rss(
                    task.parameters.get("episodes"),
                    task.parameters.get("feed_config")
                )
            
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            # Save results
            await self._save_audio_results(task_id, result)
            
            # Update task status
            await self.task_queue.update_task_status(task_id, {
                "status": "completed",
                "result": "Audio generated successfully",
                "completed_at": datetime.now().isoformat()
            })
            
            self.logger.info(f"Audio task {task_id} completed successfully")
            
        except Exception as e:
            self.logger.error(f"Audio task {task_id} failed: {e}")
            await self.task_queue.update_task_status(task_id, {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            })
    
    async def _generate_audio_briefing(self, project_id: str, briefing_task_id: str) -> PodcastEpisode:
        """Generate audio version of a briefing"""
        
        # Load briefing data
        briefing = await self._load_briefing_data(briefing_task_id)
        if not briefing:
            raise ValueError(f"No briefing data found for task {briefing_task_id}")
        
        self.logger.info(f"Generating audio for briefing: {briefing.title}")
        
        # Select voice profile based on niche
        voice_profile = self._select_voice_profile(briefing.niche)
        
        # Generate audio segments
        segments = await self._generate_audio_segments(briefing, voice_profile)
        
        # Combine segments with intro/outro
        final_audio_path = await self._combine_audio_segments(segments, briefing)
        
        # Calculate total duration
        audio = AudioSegment.from_file(final_audio_path)
        total_duration = len(audio) / 1000.0  # Convert to seconds
        
        # Upload to cloud storage
        download_url = await self._upload_to_s3(final_audio_path, briefing.id)
        
        # Create podcast episode
        episode = PodcastEpisode(
            id=f"ep-{briefing.id}",
            title=briefing.title,
            description=self._generate_episode_description(briefing),
            briefing_id=briefing.id,
            duration_seconds=total_duration,
            file_path=final_audio_path,
            file_size_bytes=os.path.getsize(final_audio_path),
            created_at=datetime.now(),
            segments=segments,
            download_url=download_url
        )
        
        return episode
    
    async def _load_briefing_data(self, briefing_task_id: str) -> Optional[CompleteBriefing]:
        """Load briefing data from summarizer task"""
        try:
            data_file = f"data/briefing_{briefing_task_id}.json"
            if os.path.exists(data_file):
                with open(data_file, 'r') as f:
                    data = json.load(f)
                
                # Convert back to CompleteBriefing object (simplified)
                briefing = CompleteBriefing(
                    id=data['id'],
                    title=data['title'],
                    niche=data['niche'],
                    frequency=data['frequency'],
                    generated_at=datetime.fromisoformat(data['generated_at']),
                    sections=[],  # Would need to reconstruct sections
                    total_articles=data['total_articles'],
                    overall_sentiment=None,  # Simplified
                    estimated_read_time=data['estimated_read_time'],
                    credibility_score=data['credibility_score'],
                    bias_score=data['bias_score'],
                    summary=data['summary'],
                    key_takeaways=data['key_takeaways']
                )
                
                return briefing
        
        except Exception as e:
            self.logger.error(f"Failed to load briefing data: {e}")
        
        return None
    
    def _select_voice_profile(self, niche: str) -> VoiceProfile:
        """Select appropriate voice profile for content niche"""
        niche_mappings = {
            "tech": "tech_focused",
            "startup": "conversational",
            "finance": "professional",
            "healthcare": "professional"
        }
        
        profile_key = niche_mappings.get(niche.lower(), "professional")
        return self.voice_profiles[profile_key]
    
    async def _generate_audio_segments(self, briefing: CompleteBriefing, voice_profile: VoiceProfile) -> List[AudioSegment]:
        """Generate TTS audio for each briefing section"""
        segments = []
        
        # Intro segment
        intro_text = self._generate_intro_text(briefing)
        intro_segment = await self._generate_tts_segment("intro", intro_text, voice_profile)
        segments.append(intro_segment)
        
        # Summary segment
        summary_text = f"Here's your executive summary: {briefing.summary}"
        summary_segment = await self._generate_tts_segment("summary", summary_text, voice_profile)
        segments.append(summary_segment)
        
        # Key takeaways
        if briefing.key_takeaways:
            takeaways_text = "Key takeaways: " + ". ".join(briefing.key_takeaways)
            takeaways_segment = await self._generate_tts_segment("takeaways", takeaways_text, voice_profile)
            segments.append(takeaways_segment)
        
        # Sections (if available)
        for i, section in enumerate(briefing.sections[:3], 1):  # Limit to 3 sections
            section_text = f"{section.title}. {section.content}"
            section_segment = await self._generate_tts_segment(
                f"section_{i}", 
                section_text, 
                voice_profile
            )
            segments.append(section_segment)
        
        # Outro segment
        outro_text = self._generate_outro_text(briefing)
        outro_segment = await self._generate_tts_segment("outro", outro_text, voice_profile)
        segments.append(outro_segment)
        
        return segments
    
    async def _generate_tts_segment(self, segment_id: str, text: str, voice_profile: VoiceProfile) -> AudioSegment:
        """Generate TTS audio for a text segment"""
        
        # Clean text for TTS
        clean_text = self._prepare_text_for_tts(text)
        
        try:
            # Generate audio using OpenAI TTS
            response = self.openai_client.audio.speech.create(
                model="tts-1-hd",  # High quality model
                voice=voice_profile.openai_voice,
                input=clean_text,
                speed=voice_profile.speed
            )
            
            # Save to temporary file
            temp_dir = tempfile.mkdtemp()
            audio_file = os.path.join(temp_dir, f"{segment_id}.mp3")
            
            with open(audio_file, "wb") as f:
                f.write(response.content)
            
            # Get duration
            audio = AudioSegment.from_file(audio_file)
            duration = len(audio) / 1000.0
            
            # Track costs
            await self.cost_tracker.track_api_call("openai-tts", len(clean_text))
            
            return AudioSegment(
                section_title=segment_id,
                content=text,
                duration_seconds=duration,
                file_path=audio_file,
                voice_settings=asdict(voice_profile)
            )
            
        except Exception as e:
            self.logger.error(f"TTS generation failed for segment {segment_id}: {e}")
            raise
    
    def _prepare_text_for_tts(self, text: str) -> str:
        """Prepare text for optimal TTS pronunciation"""
        
        # Remove markdown formatting
        clean_text = text
        clean_text = clean_text.replace("**", "")
        clean_text = clean_text.replace("*", "")
        clean_text = clean_text.replace("#", "")
        
        # Replace common abbreviations with full words
        replacements = {
            "AI": "artificial intelligence",
            "ML": "machine learning",
            "API": "A P I",
            "CEO": "C E O",
            "CTO": "C T O",
            "IPO": "I P O",
            "VC": "venture capital",
            "B2B": "business to business",
            "B2C": "business to consumer",
            "SaaS": "Software as a Service",
            "IoT": "Internet of Things",
            "VR": "virtual reality",
            "AR": "augmented reality"
        }
        
        for abbr, expansion in replacements.items():
            clean_text = clean_text.replace(abbr, expansion)
        
        # Add pauses for better flow
        clean_text = clean_text.replace(". ", ". ... ")
        clean_text = clean_text.replace("! ", "! ... ")
        clean_text = clean_text.replace("? ", "? ... ")
        
        # Limit length (OpenAI TTS has character limits)
        if len(clean_text) > 4000:
            clean_text = clean_text[:4000] + "..."
        
        return clean_text
    
    def _generate_intro_text(self, briefing: CompleteBriefing) -> str:
        """Generate intro text for audio briefing"""
        date_str = briefing.generated_at.strftime("%B %d, %Y")
        
        intro_templates = {
            "daily": f"Welcome to your daily {briefing.niche} briefing for {date_str}. Here's what you need to know in just 90 seconds.",
            "weekly": f"This is your weekly {briefing.niche} roundup for the week of {date_str}. Let's dive into the key developments."
        }
        
        return intro_templates.get(briefing.frequency, intro_templates["daily"])
    
    def _generate_outro_text(self, briefing: CompleteBriefing) -> str:
        """Generate outro text for audio briefing"""
        outros = [
            "That's your briefing for today. Stay informed, stay ahead.",
            "Thanks for listening. We'll be back with more updates soon.",
            "Until next time, keep innovating.",
            "That wraps up today's briefing. Have a productive day ahead."
        ]
        
        # Select based on briefing ID for consistency
        outro_index = int(briefing.id[-1], 16) % len(outros) if briefing.id else 0
        return outros[outro_index]
    
    async def _combine_audio_segments(self, segments: List[AudioSegment], briefing: CompleteBriefing) -> str:
        """Combine audio segments into final podcast episode"""
        
        combined_audio = AudioSegment.empty()
        
        for segment in segments:
            # Load segment audio
            segment_audio = AudioSegment.from_file(segment.file_path)
            
            # Apply audio processing
            if self.audio_config["normalize"]:
                segment_audio = normalize(segment_audio)
            
            # Add to combined audio with small pause
            combined_audio += segment_audio + AudioSegment.silent(duration=500)  # 0.5s pause
        
        # Apply final processing
        if self.audio_config["normalize"]:
            combined_audio = normalize(combined_audio)
            combined_audio = compress_dynamic_range(combined_audio)
        
        # Export final audio
        output_dir = Path("audio_output")
        output_dir.mkdir(exist_ok=True)
        
        final_path = output_dir / f"{briefing.id}.mp3"
        combined_audio.export(
            str(final_path),
            format="mp3",
            bitrate=self.audio_config["bitrate"],
            tags={
                "title": briefing.title,
                "artist": "90-Second Briefings",
                "album": f"{briefing.niche.title()} Briefings",
                "date": briefing.generated_at.strftime("%Y-%m-%d")
            }
        )
        
        self.logger.info(f"Combined audio saved to {final_path}")
        return str(final_path)
    
    async def _upload_to_s3(self, file_path: str, briefing_id: str) -> Optional[str]:
        """Upload audio file to S3 for hosting"""
        if not self.s3_client:
            return None
        
        try:
            s3_key = f"episodes/{briefing_id}.mp3"
            
            # Upload file
            self.s3_client.upload_file(
                file_path,
                self.s3_bucket,
                s3_key,
                ExtraArgs={
                    'ContentType': 'audio/mpeg',
                    'ACL': 'public-read'
                }
            )
            
            # Generate public URL
            download_url = f"https://{self.s3_bucket}.s3.amazonaws.com/{s3_key}"
            
            self.logger.info(f"Audio uploaded to: {download_url}")
            return download_url
            
        except ClientError as e:
            self.logger.error(f"S3 upload failed: {e}")
            return None
    
    def _generate_episode_description(self, briefing: CompleteBriefing) -> str:
        """Generate podcast episode description"""
        description = f"""
{briefing.summary}

📊 This episode covers {briefing.total_articles} sources
🎯 Key topics: {', '.join(briefing.key_takeaways[:3])}
⏱️ Estimated listen time: {briefing.estimated_read_time // 60} minutes
📈 Content quality score: {briefing.credibility_score:.0%}

Generated by 90-Second Briefings AI on {briefing.generated_at.strftime('%B %d, %Y')}
        """.strip()
        
        return description
    
    async def _generate_podcast_rss(self, episodes: List[PodcastEpisode], feed_config: Dict[str, Any]) -> str:
        """Generate RSS feed for podcast episodes"""
        
        feed_title = feed_config.get("title", "90-Second Briefings")
        feed_description = feed_config.get("description", "AI-curated news briefings for busy professionals")
        feed_url = feed_config.get("url", "https://90secondbriefings.com")
        
        # RSS XML template
        rss_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel>
    <title>{feed_title}</title>
    <description>{feed_description}</description>
    <link>{feed_url}</link>
    <language>en-us</language>
    <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}</lastBuildDate>
    <itunes:author>90-Second Briefings AI</itunes:author>
    <itunes:category text="News"/>
    <itunes:category text="Business"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:image href="{feed_url}/podcast-cover.jpg"/>
    
"""
        
        # Add episodes
        for episode in episodes[-20:]:  # Latest 20 episodes
            pub_date = episode.created_at.strftime('%a, %d %b %Y %H:%M:%S %z')
            
            rss_template += f"""
    <item>
        <title>{episode.title}</title>
        <description><![CDATA[{episode.description}]]></description>
        <pubDate>{pub_date}</pubDate>
        <guid>{episode.id}</guid>
        <enclosure url="{episode.download_url}" length="{episode.file_size_bytes}" type="audio/mpeg"/>
        <itunes:duration>{int(episode.duration_seconds)}</itunes:duration>
    </item>
"""
        
        rss_template += """
</channel>
</rss>
"""
        
        # Save RSS feed
        rss_file = "audio_output/podcast_feed.xml"
        with open(rss_file, 'w', encoding='utf-8') as f:
            f.write(rss_template)
        
        self.logger.info(f"RSS feed generated: {rss_file}")
        return rss_file
    
    async def _save_audio_results(self, task_id: str, episode: PodcastEpisode):
        """Save audio generation results"""
        output_file = f"data/audio_{task_id}.json"
        os.makedirs("data", exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(asdict(episode), f, indent=2, default=str)
        
        self.logger.info(f"Audio results saved to {output_file}")

# Standalone execution
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Audio Worker")
    parser.add_argument("--demo", action="store_true", help="Generate demo audio")
    parser.add_argument("--voice", default="professional", help="Voice profile")
    
    args = parser.parse_args()
    
    worker = AudioWorker()
    
    if args.demo:
        print(f"Demo audio generation with {args.voice} voice...")
        # This would normally process a real briefing
        print("Demo mode - would generate audio from briefing data")

if __name__ == "__main__":
    asyncio.run(main())