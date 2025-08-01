#!/usr/bin/env python3
"""
Mini-Worker #2: AI Summarization + Sentiment Analysis Specialist
Transforms raw news data into concise, high-signal briefings using Claude Haiku
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import json
import statistics
from collections import Counter
import re

import anthropic
from textstat import flesch_reading_ease
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

from core.mini_worker import MiniWorker, WorkerType
from scraper.scraper_worker import NewsArticle

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
    nltk.data.find('vader_lexicon')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('vader_lexicon')

@dataclass
class SentimentScore:
    positive: float
    negative: float
    neutral: float
    compound: float
    confidence: float

@dataclass
class TopicCluster:
    topic: str
    articles: List[str]  # article hash_ids
    importance_score: float
    sentiment: SentimentScore
    key_phrases: List[str]

@dataclass
class BriefingSection:
    title: str
    content: str
    articles_count: int
    sentiment: SentimentScore
    importance_score: float
    read_time_seconds: int

@dataclass
class CompleteBriefing:
    id: str
    title: str
    niche: str
    frequency: str
    generated_at: datetime
    sections: List[BriefingSection]
    total_articles: int
    overall_sentiment: SentimentScore
    estimated_read_time: int
    credibility_score: float
    bias_score: float
    summary: str
    key_takeaways: List[str]

class SummarizationWorker(MiniWorker):
    """
    Specialized Mini-Worker for AI-powered summarization and analysis
    Uses Claude Haiku for cost-effective, high-quality content generation
    """
    
    def __init__(self, worker_id: str = "Summarizer-01"):
        super().__init__(worker_id, WorkerType.SUMMARIZER)
        
        # Initialize AI client
        self.claude_client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        
        # Initialize sentiment analyzer
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.stop_words = set(stopwords.words('english'))
        
        # Summarization templates
        self.templates = self._load_prompt_templates()
        
        # Quality thresholds
        self.min_credibility_score = 0.7
        self.max_bias_score = 0.3
        self.target_reading_time = 90  # seconds
        
    def _load_prompt_templates(self) -> Dict[str, str]:
        """Load Claude prompt templates for different briefing types"""
        return {
            "daily_tech": """
You are an expert tech journalist creating a concise daily briefing for busy executives.

ARTICLES TO SUMMARIZE:
{articles}

INSTRUCTIONS:
- Create a 90-second briefing (approximately 200-250 words)
- Focus on the most impactful stories that decision-makers need to know
- Group related stories into logical sections
- Use clear, professional language
- Include specific numbers, companies, and outcomes when relevant
- Maintain neutral tone while highlighting significance

BRIEFING STRUCTURE:
🚀 **Key Developments** (most important story)
📈 **Market Movements** (funding, acquisitions, stock moves)
🔧 **Product Launches** (new tech, features, releases)
⚠️ **Industry Challenges** (regulations, controversies, setbacks)

Each section should be 2-3 sentences maximum. End with one key takeaway.
""",
            
            "weekly_startup": """
You are a startup ecosystem expert creating a weekly roundup for founders and investors.

ARTICLES TO SUMMARIZE:
{articles}

INSTRUCTIONS:
- Create a comprehensive weekly briefing (approximately 400-500 words)
- Focus on funding rounds, new startups, market trends, and ecosystem changes
- Include specific funding amounts, valuations, and investor names
- Highlight patterns and trends across multiple stories
- Use data-driven insights and forward-looking analysis

BRIEFING STRUCTURE:
💰 **Funding Highlights** (major rounds, new funds)
🌟 **Startup Spotlights** (interesting new companies)
📊 **Market Trends** (sector analysis, patterns)
🎯 **Founder Insights** (lessons, strategies, advice)
📅 **Week Ahead** (upcoming events, deadlines)

Include 3-5 key takeaways at the end.
""",
            
            "sentiment_analysis": """
Analyze the sentiment and bias in the following news articles:

ARTICLES:
{articles}

Provide:
1. Overall sentiment (positive/neutral/negative) with confidence score
2. Bias detection (political lean, corporate bias, sensationalism)
3. Credibility assessment based on:
   - Source reputation
   - Fact vs opinion ratio
   - Use of specific data/citations
   - Balanced perspectives

Return structured analysis with scores 0-1.
"""
        }
    
    async def execute_task(self, task_id: str):
        """Execute summarization task"""
        task = await self.task_queue.get_task(task_id)
        if not task:
            return
        
        self.logger.info(f"Executing summarization task: {task.description}")
        
        try:
            if task.task_type == "generate_briefing":
                result = await self._generate_briefing(
                    task.parameters.get("project_id"),
                    task.parameters.get("niche"),
                    task.parameters.get("frequency"),
                    task.parameters.get("source_tasks", [])
                )
            
            elif task.task_type == "analyze_sentiment":
                result = await self._analyze_content_sentiment(
                    task.parameters.get("content"),
                    task.parameters.get("source_url")
                )
            
            elif task.task_type == "extract_topics":
                result = await self._extract_topic_clusters(
                    task.parameters.get("articles")
                )
            
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            # Save results
            await self._save_briefing_results(task_id, result)
            
            # Update task status
            await self.task_queue.update_task_status(task_id, {
                "status": "completed",
                "result": "Briefing generated successfully",
                "completed_at": datetime.now().isoformat()
            })
            
            self.logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            self.logger.error(f"Task {task_id} failed: {e}")
            await self.task_queue.update_task_status(task_id, {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            })
    
    async def _generate_briefing(self, project_id: str, niche: str, frequency: str, source_tasks: List[str]) -> CompleteBriefing:
        """Generate complete briefing from scraped articles"""
        
        # Load articles from scraper tasks
        articles = await self._load_articles_from_tasks(source_tasks)
        
        if not articles:
            raise ValueError("No articles found from source tasks")
        
        self.logger.info(f"Generating {frequency} {niche} briefing from {len(articles)} articles")
        
        # Step 1: Content analysis and filtering
        analyzed_articles = await self._analyze_articles(articles)
        high_quality_articles = self._filter_by_quality(analyzed_articles)
        
        # Step 2: Topic clustering
        topic_clusters = await self._extract_topic_clusters(high_quality_articles)
        
        # Step 3: Generate briefing sections
        sections = await self._generate_briefing_sections(topic_clusters, niche, frequency)
        
        # Step 4: Overall analysis
        overall_sentiment = self._calculate_overall_sentiment(analyzed_articles)
        credibility_score = self._calculate_credibility_score(analyzed_articles)
        bias_score = await self._detect_bias(analyzed_articles)
        
        # Step 5: Generate summary and takeaways
        summary = await self._generate_executive_summary(sections, niche)
        key_takeaways = await self._extract_key_takeaways(sections, topic_clusters)
        
        # Calculate reading time
        total_words = sum(len(section.content.split()) for section in sections)
        estimated_read_time = max(int(total_words / 250 * 60), 60)  # Assume 250 WPM, min 60s
        
        briefing = CompleteBriefing(
            id=f"brief-{project_id}-{datetime.now().strftime('%Y%m%d%H%M')}",
            title=f"{niche.title()} {frequency.title()} Briefing - {datetime.now().strftime('%B %d, %Y')}",
            niche=niche,
            frequency=frequency,
            generated_at=datetime.now(),
            sections=sections,
            total_articles=len(articles),
            overall_sentiment=overall_sentiment,
            estimated_read_time=estimated_read_time,
            credibility_score=credibility_score,
            bias_score=bias_score,
            summary=summary,
            key_takeaways=key_takeaways
        )
        
        return briefing
    
    async def _load_articles_from_tasks(self, source_tasks: List[str]) -> List[NewsArticle]:
        """Load articles from completed scraper tasks"""
        articles = []
        
        for task_id in source_tasks:
            try:
                # Load scraped data
                data_file = f"data/scraped_{task_id}.json"
                if os.path.exists(data_file):
                    with open(data_file, 'r') as f:
                        data = json.load(f)
                    
                    # Convert to NewsArticle objects
                    for article_data in data.get('articles', []):
                        article = NewsArticle(
                            title=article_data['title'],
                            content=article_data['content'],
                            url=article_data['url'],
                            source=article_data['source'],
                            published_at=datetime.fromisoformat(article_data['published_at']),
                            author=article_data.get('author'),
                            category=article_data.get('category'),
                            hash_id=article_data.get('hash_id')
                        )
                        articles.append(article)
            
            except Exception as e:
                self.logger.warning(f"Failed to load articles from task {task_id}: {e}")
        
        return articles
    
    async def _analyze_articles(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Analyze articles for sentiment and credibility"""
        analyzed_articles = []
        
        for article in articles:
            # Sentiment analysis
            sentiment_scores = self.sentiment_analyzer.polarity_scores(
                f"{article.title} {article.content}"
            )
            article.sentiment_score = sentiment_scores['compound']
            
            # Credibility scoring (basic heuristics)
            credibility = self._calculate_article_credibility(article)
            article.credibility_score = credibility
            
            analyzed_articles.append(article)
        
        return analyzed_articles
    
    def _calculate_article_credibility(self, article: NewsArticle) -> float:
        """Calculate credibility score for an article"""
        score = 0.5  # Base score
        
        # Source reputation (simplified)
        trusted_sources = {
            'techcrunch.com': 0.9,
            'arstechnica.com': 0.95,
            'theverge.com': 0.85,
            'news.ycombinator.com': 0.8,
            'reuters.com': 0.95,
            'bbc.com': 0.9
        }
        
        for domain, trust_score in trusted_sources.items():
            if domain in article.source.lower():
                score = trust_score
                break
        
        # Content quality indicators
        if article.author:
            score += 0.1
        
        if article.content and len(article.content) > 500:
            score += 0.1
        
        # Check for specific data/numbers
        if re.search(r'\d+%|\$\d+|\d+\s*(million|billion)', article.content):
            score += 0.05
        
        return min(score, 1.0)
    
    def _filter_by_quality(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Filter articles by quality thresholds"""
        return [
            article for article in articles
            if (article.credibility_score or 0) >= self.min_credibility_score
            and len(article.content) > 200  # Minimum content length
        ]
    
    async def _extract_topic_clusters(self, articles: List[NewsArticle]) -> List[TopicCluster]:
        """Extract and cluster topics from articles"""
        if not articles:
            return []
        
        # Simple keyword-based clustering (can be enhanced with ML)
        topic_keywords = {
            'Funding & Investment': ['funding', 'investment', 'venture', 'series', 'raised', 'valuation'],
            'Product Launches': ['launch', 'release', 'announce', 'unveil', 'debut', 'new product'],
            'Acquisitions & Mergers': ['acquire', 'merger', 'acquisition', 'bought', 'purchase', 'deal'],
            'AI & Machine Learning': ['ai', 'artificial intelligence', 'machine learning', 'neural', 'algorithm'],
            'Regulation & Policy': ['regulation', 'policy', 'law', 'government', 'compliance', 'legal'],
            'Market Trends': ['trend', 'market', 'growth', 'decline', 'analysis', 'forecast']
        }
        
        clusters = []
        
        for topic, keywords in topic_keywords.items():
            matching_articles = []
            
            for article in articles:
                text = f"{article.title} {article.content}".lower()
                if any(keyword in text for keyword in keywords):
                    matching_articles.append(article.hash_id)
            
            if matching_articles:
                # Calculate importance and sentiment
                topic_articles = [a for a in articles if a.hash_id in matching_articles]
                importance = len(matching_articles) / len(articles)
                
                sentiments = [a.sentiment_score for a in topic_articles if a.sentiment_score]
                avg_sentiment = statistics.mean(sentiments) if sentiments else 0
                
                sentiment_score = SentimentScore(
                    positive=max(0, avg_sentiment),
                    negative=abs(min(0, avg_sentiment)),
                    neutral=1 - abs(avg_sentiment),
                    compound=avg_sentiment,
                    confidence=0.8
                )
                
                # Extract key phrases
                key_phrases = self._extract_key_phrases(topic_articles)
                
                cluster = TopicCluster(
                    topic=topic,
                    articles=matching_articles,
                    importance_score=importance,
                    sentiment=sentiment_score,
                    key_phrases=key_phrases
                )
                
                clusters.append(cluster)
        
        # Sort by importance
        return sorted(clusters, key=lambda x: x.importance_score, reverse=True)
    
    def _extract_key_phrases(self, articles: List[NewsArticle]) -> List[str]:
        """Extract key phrases from article cluster"""
        # Combine all text
        all_text = " ".join([f"{a.title} {a.content}" for a in articles])
        
        # Tokenize and filter
        words = word_tokenize(all_text.lower())
        words = [w for w in words if w.isalnum() and w not in self.stop_words and len(w) > 3]
        
        # Count frequencies
        word_freq = Counter(words)
        
        # Return top phrases
        return [word for word, count in word_freq.most_common(10)]
    
    async def _generate_briefing_sections(self, clusters: List[TopicCluster], niche: str, frequency: str) -> List[BriefingSection]:
        """Generate briefing sections using Claude"""
        sections = []
        
        # Select template
        template_key = f"{frequency}_{niche}"
        if template_key not in self.templates:
            template_key = "daily_tech"  # Fallback
        
        template = self.templates[template_key]
        
        # Take top clusters (limit based on frequency)
        max_clusters = 4 if frequency == "daily" else 6
        top_clusters = clusters[:max_clusters]
        
        for cluster in top_clusters:
            try:
                # Prepare article summaries for this cluster
                cluster_articles = await self._get_cluster_articles(cluster)
                articles_text = self._format_articles_for_claude(cluster_articles)
                
                # Generate section using Claude
                prompt = template.format(articles=articles_text)
                
                response = self.claude_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                content = response.content[0].text.strip()
                
                # Calculate reading time
                word_count = len(content.split())
                read_time = int(word_count / 250 * 60)  # 250 WPM in seconds
                
                section = BriefingSection(
                    title=cluster.topic,
                    content=content,
                    articles_count=len(cluster.articles),
                    sentiment=cluster.sentiment,
                    importance_score=cluster.importance_score,
                    read_time_seconds=read_time
                )
                
                sections.append(section)
                
                # Track costs
                await self.cost_tracker.track_api_call("claude-haiku", len(prompt.split()))
                
            except Exception as e:
                self.logger.error(f"Failed to generate section for {cluster.topic}: {e}")
        
        return sections
    
    async def _get_cluster_articles(self, cluster: TopicCluster) -> List[NewsArticle]:
        """Get articles for a specific cluster"""
        # This would normally query the database
        # For now, return empty list as placeholder
        return []
    
    def _format_articles_for_claude(self, articles: List[NewsArticle]) -> str:
        """Format articles for Claude input"""
        formatted = []
        
        for i, article in enumerate(articles[:5], 1):  # Limit to 5 articles
            formatted.append(f"""
Article {i}:
Title: {article.title}
Source: {article.source}
Published: {article.published_at.strftime('%Y-%m-%d %H:%M')}
Content: {article.content[:500]}...
""")
        
        return "\n".join(formatted)
    
    async def _generate_executive_summary(self, sections: List[BriefingSection], niche: str) -> str:
        """Generate executive summary of the briefing"""
        if not sections:
            return f"No significant {niche} developments today."
        
        # Combine section titles and key points
        summary_input = "\n".join([
            f"{section.title}: {section.content[:200]}..." 
            for section in sections[:3]
        ])
        
        prompt = f"""
Create a 2-sentence executive summary for this {niche} briefing:

{summary_input}

Summary should highlight the most critical information for busy executives.
"""
        
        try:
            response = self.claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            self.logger.error(f"Failed to generate summary: {e}")
            return f"Key developments in {niche} including {sections[0].title.lower()} and related industry updates."
    
    async def _extract_key_takeaways(self, sections: List[BriefingSection], clusters: List[TopicCluster]) -> List[str]:
        """Extract key takeaways from the briefing"""
        takeaways = []
        
        # Take the most important points from top sections
        for section in sections[:3]:
            # Simple extraction - in practice would use NLP
            sentences = sent_tokenize(section.content)
            if sentences:
                # Take first sentence as key takeaway
                takeaways.append(sentences[0])
        
        return takeaways[:5]  # Limit to 5 takeaways
    
    def _calculate_overall_sentiment(self, articles: List[NewsArticle]) -> SentimentScore:
        """Calculate overall sentiment across all articles"""
        sentiments = [a.sentiment_score for a in articles if a.sentiment_score is not None]
        
        if not sentiments:
            return SentimentScore(0.33, 0.33, 0.33, 0, 0.5)
        
        avg_sentiment = statistics.mean(sentiments)
        
        return SentimentScore(
            positive=max(0, avg_sentiment),
            negative=abs(min(0, avg_sentiment)),
            neutral=1 - abs(avg_sentiment),
            compound=avg_sentiment,
            confidence=0.85
        )
    
    def _calculate_credibility_score(self, articles: List[NewsArticle]) -> float:
        """Calculate overall credibility score"""
        scores = [a.credibility_score for a in articles if a.credibility_score is not None]
        return statistics.mean(scores) if scores else 0.5
    
    async def _detect_bias(self, articles: List[NewsArticle]) -> float:
        """Detect potential bias in article collection"""
        # Simple bias detection based on sentiment distribution
        sentiments = [a.sentiment_score for a in articles if a.sentiment_score is not None]
        
        if not sentiments:
            return 0.5
        
        # Check for extreme sentiment skew
        positive_count = sum(1 for s in sentiments if s > 0.3)
        negative_count = sum(1 for s in sentiments if s < -0.3)
        total_count = len(sentiments)
        
        # Calculate bias as deviation from balanced sentiment
        if total_count > 0:
            positive_ratio = positive_count / total_count
            negative_ratio = negative_count / total_count
            
            # Bias score increases with sentiment imbalance
            bias = abs(positive_ratio - negative_ratio)
            return min(bias, 1.0)
        
        return 0.5
    
    async def _save_briefing_results(self, task_id: str, briefing: CompleteBriefing):
        """Save generated briefing to storage"""
        output_file = f"data/briefing_{task_id}.json"
        os.makedirs("data", exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(asdict(briefing), f, indent=2, default=str)
        
        # Also save human-readable version
        readable_file = f"data/briefing_{task_id}.md"
        await self._save_readable_briefing(briefing, readable_file)
        
        self.logger.info(f"Saved briefing to {output_file}")
    
    async def _save_readable_briefing(self, briefing: CompleteBriefing, filename: str):
        """Save human-readable markdown version"""
        content = f"""# {briefing.title}

**Generated:** {briefing.generated_at.strftime('%B %d, %Y at %I:%M %p')}  
**Reading Time:** ~{briefing.estimated_read_time // 60} minutes  
**Sources:** {briefing.total_articles} articles  
**Credibility Score:** {briefing.credibility_score:.1%}  

## Executive Summary
{briefing.summary}

## Key Takeaways
"""
        
        for i, takeaway in enumerate(briefing.key_takeaways, 1):
            content += f"{i}. {takeaway}\n"
        
        content += "\n## Detailed Analysis\n\n"
        
        for section in briefing.sections:
            content += f"### {section.title}\n"
            content += f"*{section.articles_count} articles • "
            content += f"Sentiment: {'Positive' if section.sentiment.compound > 0.1 else 'Negative' if section.sentiment.compound < -0.1 else 'Neutral'}*\n\n"
            content += f"{section.content}\n\n"
        
        content += f"""
---
*Generated by Mini-Claude Summarization Worker*  
*Quality Score: {briefing.credibility_score:.1%} • Bias Score: {briefing.bias_score:.1%}*
"""
        
        with open(filename, 'w') as f:
            f.write(content)

# Standalone execution
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Summarization Worker")
    parser.add_argument("--demo", action="store_true", help="Run demo briefing")
    parser.add_argument("--niche", default="tech", help="Briefing niche")
    parser.add_argument("--frequency", default="daily", help="Briefing frequency")
    
    args = parser.parse_args()
    
    worker = SummarizationWorker()
    
    if args.demo:
        print(f"Generating demo {args.frequency} {args.niche} briefing...")
        # This would normally be called with real scraped data
        print("Demo mode - would generate briefing from scraped articles")

if __name__ == "__main__":
    asyncio.run(main())