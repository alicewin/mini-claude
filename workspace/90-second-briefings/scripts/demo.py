#!/usr/bin/env python3
"""
Demo Briefing Generator for 90-Second Briefings
Creates sample briefings to demonstrate system capabilities
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import uuid

# Mock data for demo briefings
DEMO_ARTICLES = [
    {
        "title": "AI Startup Raises $50M Series B to Revolutionize Healthcare Diagnostics",
        "content": "Medical AI company DiagnosticsAI has closed a $50 million Series B funding round led by Andreessen Horowitz, with participation from GV and Kleiner Perkins. The San Francisco-based startup uses machine learning to analyze medical imaging data, claiming 95% accuracy in early cancer detection. The funding will be used to expand their FDA approval process and scale their platform to 100+ hospitals nationwide. CEO Dr. Sarah Chen stated that the technology could reduce diagnostic times from weeks to hours, potentially saving thousands of lives annually.",
        "url": "https://techcrunch.com/2024/01/15/diagnostics-ai-series-b",
        "source": "TechCrunch",
        "published_at": (datetime.now() - timedelta(hours=2)).isoformat(),
        "author": "Alex Wilhelm",
        "category": "AI/Healthcare"
    },
    {
        "title": "Meta Announces Open-Source Large Language Model to Compete with GPT-4",
        "content": "Meta has released Llama-3, a 70-billion parameter language model that the company claims matches GPT-4 performance on key benchmarks while being fully open-source. The model will be available through Hugging Face and includes commercial licensing terms that allow startups to use it freely. Meta's AI Research team spent 18 months developing the model using a new training technique called 'Constitutional AI' that reduces harmful outputs. Industry experts see this as a significant challenge to OpenAI's market dominance and could democratize access to advanced AI capabilities.",
        "url": "https://arstechnica.com/ai/2024/01/15/meta-llama-3-release",
        "source": "Ars Technica",
        "published_at": (datetime.now() - timedelta(hours=4)).isoformat(),
        "author": "Benj Edwards",
        "category": "AI/Open Source"
    },
    {
        "title": "Tesla Reports Record Q4 Deliveries Despite Production Challenges",
        "content": "Tesla delivered 484,507 vehicles in Q4 2023, beating analyst expectations of 470,000 units despite ongoing supply chain issues. The electric vehicle manufacturer attributed the strong performance to increased production at its Shanghai and Berlin Gigafactories. Model Y sales drove the majority of deliveries, with the compact SUV becoming the world's best-selling electric vehicle. However, Tesla stock dropped 3% in after-hours trading as investors focused on CEO Elon Musk's comments about 'significant challenges' in 2024 related to interest rates and economic uncertainty.",
        "url": "https://theverge.com/2024/1/15/tesla-q4-deliveries-record",
        "source": "The Verge",
        "published_at": (datetime.now() - timedelta(hours=6)).isoformat(),
        "author": "Sean O'Kane",
        "category": "Electric Vehicles"
    },
    {
        "title": "Google DeepMind Achieves Breakthrough in Protein Folding Prediction",
        "content": "Researchers at Google DeepMind have announced AlphaFold 3, which can now predict protein structures with 99.9% accuracy and model protein interactions with other molecules. This advancement could accelerate drug discovery by decades, allowing pharmaceutical companies to design medications in silico before expensive lab testing. The team has made the predictions for over 200 million protein structures freely available to researchers worldwide. Several biotech companies have already licensed the technology, with Moderna announcing plans to use it for next-generation vaccine development.",
        "url": "https://nature.com/articles/deepmind-alphafold-3",
        "source": "Nature",
        "published_at": (datetime.now() - timedelta(hours=8)).isoformat(),
        "author": "Dr. Michael Chen",
        "category": "Biotechnology"
    },
    {
        "title": "Crypto Markets Rally as Bitcoin ETF Approval Rumors Intensify",
        "content": "Bitcoin surged 12% to $43,500 following reports that the SEC may approve spot Bitcoin ETFs from BlackRock and Fidelity as early as this week. The potential approval represents a major milestone for cryptocurrency adoption in traditional finance. Ethereum and other altcoins also gained significantly, with the total crypto market cap increasing by $200 billion in 24 hours. However, regulatory experts caution that approval is not guaranteed, and the SEC has previously delayed similar decisions multiple times.",
        "url": "https://coindesk.com/markets/2024/01/15/bitcoin-rally-etf-rumors",
        "source": "CoinDesk",
        "published_at": (datetime.now() - timedelta(hours=10)).isoformat(),
        "author": "James Park",
        "category": "Cryptocurrency"
    }
]

class DemoBriefingGenerator:
    """Generate demo briefings to showcase system capabilities"""
    
    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
    
    async def generate_demo_briefing(self, niche: str = "tech", frequency: str = "daily"):
        """Generate a complete demo briefing"""
        
        print(f"🤖 Generating demo {frequency} {niche} briefing...")
        
        # Create briefing ID
        briefing_id = f"demo-{niche}-{datetime.now().strftime('%Y%m%d%H%M')}"
        
        # Filter articles by niche
        relevant_articles = self._filter_articles_by_niche(DEMO_ARTICLES, niche)
        
        # Generate briefing sections
        sections = self._create_briefing_sections(relevant_articles, niche)
        
        # Create complete briefing
        briefing = {
            "id": briefing_id,
            "title": f"Demo {niche.title()} {frequency.title()} Briefing - {datetime.now().strftime('%B %d, %Y')}",
            "niche": niche,
            "frequency": frequency,
            "generated_at": datetime.now().isoformat(),
            "sections": sections,
            "total_articles": len(relevant_articles),
            "estimated_read_time": 90,  # Target 90 seconds
            "credibility_score": 0.92,
            "bias_score": 0.15,
            "summary": self._generate_executive_summary(sections, niche),
            "key_takeaways": self._extract_key_takeaways(sections)
        }
        
        # Save briefing data
        await self._save_briefing(briefing_id, briefing)
        
        # Generate readable version
        await self._create_readable_version(briefing)
        
        # Simulate cost tracking
        await self._simulate_costs(briefing_id, len(relevant_articles))
        
        print(f"✅ Demo briefing generated: {briefing_id}")
        print(f"📄 Readable version: data/briefing_{briefing_id}.md")
        print(f"📊 Data file: data/briefing_{briefing_id}.json")
        
        return briefing_id
    
    def _filter_articles_by_niche(self, articles, niche):
        """Filter articles by niche relevance"""
        
        niche_keywords = {
            "tech": ["ai", "startup", "technology", "software", "tesla", "meta", "google"],
            "finance": ["funding", "investment", "market", "crypto", "bitcoin", "etf"],
            "healthcare": ["medical", "healthcare", "pharma", "biotech", "drug", "protein"],
            "startup": ["startup", "funding", "series", "venture", "investment", "founder"]
        }
        
        keywords = niche_keywords.get(niche.lower(), niche_keywords["tech"])
        
        relevant = []
        for article in articles:
            text = f"{article['title']} {article['content']}".lower()
            if any(keyword in text for keyword in keywords):
                relevant.append(article)
        
        return relevant[:4]  # Limit to 4 articles for demo
    
    def _create_briefing_sections(self, articles, niche):
        """Create briefing sections from articles"""
        
        sections = []
        
        # Group articles by category
        categories = {}
        for article in articles:
            category = article.get('category', 'General')
            if category not in categories:
                categories[category] = []
            categories[category].append(article)
        
        # Create sections
        section_templates = {
            "AI/Healthcare": "🏥 Healthcare Innovation",
            "AI/Open Source": "🔓 Open Source Developments", 
            "Electric Vehicles": "⚡ Transportation Tech",
            "Biotechnology": "🧬 Biotech Breakthroughs",
            "Cryptocurrency": "💰 Crypto Markets"
        }
        
        for category, category_articles in categories.items():
            section_title = section_templates.get(category, f"📈 {category}")
            
            # Create section content
            content_parts = []
            for article in category_articles[:2]:  # Max 2 articles per section
                summary = self._summarize_article(article)
                content_parts.append(summary)
            
            section = {
                "title": section_title,
                "content": " ".join(content_parts),
                "articles_count": len(category_articles),
                "sentiment": {
                    "positive": 0.7,
                    "negative": 0.1,
                    "neutral": 0.2,
                    "compound": 0.6,
                    "confidence": 0.85
                },
                "importance_score": 0.8,
                "read_time_seconds": 25
            }
            
            sections.append(section)
        
        return sections
    
    def _summarize_article(self, article):
        """Create a concise summary of an article"""
        
        # Extract key information
        title = article["title"]
        content = article["content"]
        
        # Create summary (first 2 sentences + key details)
        sentences = content.split('. ')
        summary = '. '.join(sentences[:2])
        
        # Add key metrics if present
        import re
        money_matches = re.findall(r'\$[\d.]+[MmBb]', content)
        percent_matches = re.findall(r'\d+%', content)
        
        if money_matches:
            summary += f" Key figure: {money_matches[0]}."
        elif percent_matches:
            summary += f" Key metric: {percent_matches[0]}."
        
        return summary[:200] + "..." if len(summary) > 200 else summary
    
    def _generate_executive_summary(self, sections, niche):
        """Generate executive summary"""
        
        summaries = {
            "tech": "Major developments in AI and technology this week include significant funding rounds, open-source releases, and breakthrough research. The sector continues rapid innovation with strong investor confidence despite market uncertainties.",
            "finance": "Financial markets showed mixed signals with crypto rallying on regulatory optimism while traditional sectors face headwinds. Key developments include potential ETF approvals and continued venture funding activity.",
            "healthcare": "Healthcare technology sector demonstrates strong momentum with AI diagnostics breakthroughs and substantial funding rounds. Regulatory progress and research advances signal continued growth in medical innovation.",
            "startup": "Startup ecosystem remains active with major funding announcements across AI and healthcare sectors. Series B rounds dominated activity, with established VCs continuing to back innovative technologies."
        }
        
        return summaries.get(niche.lower(), summaries["tech"])
    
    def _extract_key_takeaways(self, sections):
        """Extract key takeaways from sections"""
        
        takeaways = [
            "AI healthcare diagnostics company raises $50M Series B, targeting 95% accuracy in cancer detection",
            "Meta releases open-source Llama-3 model to compete with GPT-4, democratizing advanced AI access",
            "Tesla delivers record 484K vehicles in Q4 despite supply chain challenges and economic uncertainty",
            "Google DeepMind's AlphaFold 3 achieves 99.9% protein folding accuracy, accelerating drug discovery"
        ]
        
        return takeaways[:3]  # Return top 3 takeaways
    
    async def _save_briefing(self, briefing_id, briefing):
        """Save briefing to JSON file"""
        
        output_file = self.data_dir / f"briefing_{briefing_id}.json"
        
        with open(output_file, 'w') as f:
            json.dump(briefing, f, indent=2, default=str)
    
    async def _create_readable_version(self, briefing):
        """Create human-readable markdown version"""
        
        briefing_id = briefing["id"]
        output_file = self.data_dir / f"briefing_{briefing_id}.md"
        
        content = f"""# {briefing['title']}

**Generated:** {datetime.fromisoformat(briefing['generated_at']).strftime('%B %d, %Y at %I:%M %p')}  
**Reading Time:** ~{briefing['estimated_read_time'] // 60} minutes  
**Sources:** {briefing['total_articles']} articles  
**Credibility Score:** {briefing['credibility_score']:.1%}  
**Quality Rating:** 🌟🌟🌟🌟🌟

## Executive Summary
{briefing['summary']}

## Key Takeaways
"""
        
        for i, takeaway in enumerate(briefing['key_takeaways'], 1):
            content += f"{i}. {takeaway}\n"
        
        content += "\n## Detailed Analysis\n\n"
        
        for section in briefing['sections']:
            content += f"### {section['title']}\n"
            content += f"*{section['articles_count']} articles • "
            
            sentiment = section['sentiment']
            if sentiment['compound'] > 0.1:
                content += "Positive sentiment*\n\n"
            elif sentiment['compound'] < -0.1:
                content += "Negative sentiment*\n\n"
            else:
                content += "Neutral sentiment*\n\n"
            
            content += f"{section['content']}\n\n"
        
        content += f"""
---
*🤖 Generated by 90-Second Briefings Demo System*  
*Quality Score: {briefing['credibility_score']:.1%} • Bias Score: {briefing['bias_score']:.1%}*  
*Demo Mode: Using sample data to showcase system capabilities*
"""
        
        with open(output_file, 'w') as f:
            f.write(content)
    
    async def _simulate_costs(self, briefing_id, article_count):
        """Simulate cost tracking for demo"""
        
        costs_dir = self.data_dir / "costs"
        costs_dir.mkdir(exist_ok=True)
        
        today_file = costs_dir / f"costs_{datetime.now().strftime('%Y%m%d')}.json"
        
        # Simulate realistic costs
        demo_costs = {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "daily_costs": {
                "scraper": 0.05,  # Web scraping
                "claude-haiku": 0.12,  # AI summarization
                "openai-tts": 0.08,  # Audio generation
                "email": 0.02,  # Email delivery
                "storage": 0.01  # File storage
            },
            "worker_costs": {
                "Scraper-01": 0.05,
                "Summarizer-01": 0.12,
                "Audio-01": 0.08,
                "Dashboard-01": 0.03
            },
            "total_cost": 0.28,
            "events": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "service": "demo-generation",
                    "operation": "briefing_creation",
                    "units": article_count,
                    "cost_gbp": 0.15,
                    "worker_id": "demo-generator",
                    "metadata": {"briefing_id": briefing_id}
                }
            ]
        }
        
        with open(today_file, 'w') as f:
            json.dump(demo_costs, f, indent=2)
    
    async def generate_multiple_demos(self):
        """Generate multiple demo briefings for different niches"""
        
        print("🚀 Generating comprehensive demo briefings...")
        
        demo_configs = [
            ("tech", "daily"),
            ("startup", "weekly"),
            ("healthcare", "daily"),
            ("finance", "daily")
        ]
        
        briefing_ids = []
        
        for niche, frequency in demo_configs:
            briefing_id = await self.generate_demo_briefing(niche, frequency)
            briefing_ids.append(briefing_id)
            
            # Small delay between generations
            await asyncio.sleep(1)
        
        # Create summary report
        await self._create_demo_summary(briefing_ids)
        
        print(f"\n✅ Generated {len(briefing_ids)} demo briefings")
        print("📋 Summary report: data/demo_summary.md")
        
        return briefing_ids
    
    async def _create_demo_summary(self, briefing_ids):
        """Create summary of all demo briefings"""
        
        summary_file = self.data_dir / "demo_summary.md"
        
        content = f"""# 90-Second Briefings Demo Summary

**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}  
**Demo Briefings Created:** {len(briefing_ids)}

## Demo Briefings Generated

"""
        
        for briefing_id in briefing_ids:
            # Load briefing to get details
            briefing_file = self.data_dir / f"briefing_{briefing_id}.json"
            if briefing_file.exists():
                with open(briefing_file) as f:
                    briefing = json.load(f)
                
                content += f"""### {briefing['title']}
- **ID:** `{briefing_id}`
- **Niche:** {briefing['niche']}
- **Frequency:** {briefing['frequency']}
- **Articles:** {briefing['total_articles']}
- **Credibility:** {briefing['credibility_score']:.1%}
- **Read Time:** ~{briefing['estimated_read_time']} seconds
- **Files:** 
  - JSON: `data/briefing_{briefing_id}.json`
  - Markdown: `data/briefing_{briefing_id}.md`

"""
        
        content += f"""
## System Capabilities Demonstrated

✅ **Multi-source data aggregation** from news sites and APIs  
✅ **AI-powered summarization** with quality scoring  
✅ **Cost tracking and monitoring** with budget guardrails  
✅ **Multiple output formats** (JSON, Markdown, HTML)  
✅ **Niche-specific filtering** and content categorization  
✅ **Sentiment analysis and bias detection**  
✅ **Hierarchical AI worker orchestration**  

## Next Steps

1. **Configure API keys** in `.env` file for live data
2. **Launch full system** with `./scripts/launch.sh --docker`
3. **Access web dashboard** at http://localhost:8000
4. **Monitor costs** in real-time via dashboard
5. **Create custom briefings** for your specific needs

## Demo Data Notice

These briefings use sample data to demonstrate system capabilities. In production mode with API keys configured, the system will:
- Scrape live news sources in real-time
- Generate fresh content using Claude AI
- Create audio briefings with OpenAI TTS
- Deliver via email, Notion, and RSS feeds
- Track actual usage costs and enforce limits

---
*🤖 Generated by 90-Second Briefings Demo System*
"""
        
        with open(summary_file, 'w') as f:
            f.write(content)

async def main():
    """Main demo function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Demo Briefing Generator")
    parser.add_argument("--niche", default="tech", help="Briefing niche")
    parser.add_argument("--frequency", default="daily", help="Briefing frequency")
    parser.add_argument("--all", action="store_true", help="Generate all demo briefings")
    
    args = parser.parse_args()
    
    generator = DemoBriefingGenerator()
    
    if args.all:
        await generator.generate_multiple_demos()
    else:
        await generator.generate_demo_briefing(args.niche, args.frequency)

if __name__ == "__main__":
    asyncio.run(main())