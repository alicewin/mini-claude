#!/usr/bin/env python3
"""
Mini-Worker #1: Web Scraping + API Integration Specialist
Autonomous news collection from multiple sources with rate limiting and quality control
"""

import os
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import json
import hashlib
from urllib.parse import urljoin, urlparse
import re
import time

import requests
from bs4 import BeautifulSoup
import feedparser
from newspaper import Article
import tweepy
import linkedin_api

from core.mini_worker import MiniWorker, WorkerType
from core.rate_limiter import RateLimiter
from core.content_validator import ContentValidator

@dataclass
class NewsArticle:
    title: str
    content: str
    url: str
    source: str
    published_at: datetime
    author: Optional[str] = None
    category: Optional[str] = None
    sentiment_score: Optional[float] = None
    credibility_score: Optional[float] = None
    hash_id: str = None
    
    def __post_init__(self):
        if not self.hash_id:
            content_hash = hashlib.md5(f"{self.title}{self.url}".encode()).hexdigest()
            self.hash_id = content_hash[:12]

@dataclass
class SocialPost:
    content: str
    platform: str
    author: str
    url: str
    engagement_score: int
    posted_at: datetime
    hashtags: List[str]
    mentions: List[str]

class ScraperWorker(MiniWorker):
    """
    Specialized Mini-Worker for web scraping and API integration
    Handles news sites, RSS feeds, Twitter, LinkedIn, and tech blogs
    """
    
    def __init__(self, worker_id: str = "Scraper-01"):
        super().__init__(worker_id, WorkerType.SCRAPER)
        
        self.rate_limiter = RateLimiter()
        self.content_validator = ContentValidator()
        self.session = None
        
        # API clients
        self.twitter_client = None
        self.linkedin_client = None
        
        # Source configurations
        self.news_sources = {
            "techcrunch": {
                "base_url": "https://techcrunch.com",
                "rss_feed": "https://techcrunch.com/feed/",
                "selectors": {
                    "title": "h1.article__title",
                    "content": "div.article-content",
                    "author": "span.article__byline-link",
                    "date": "time"
                }
            },
            "arstechnica": {
                "base_url": "https://arstechnica.com",
                "rss_feed": "https://feeds.arstechnica.com/arstechnica/index",
                "selectors": {
                    "title": "h1.heading",
                    "content": "div.article-content",
                    "author": "span.author",
                    "date": "time.date"
                }
            },
            "theverge": {
                "base_url": "https://www.theverge.com",
                "rss_feed": "https://www.theverge.com/rss/index.xml",
                "selectors": {
                    "title": "h1.c-page-title",
                    "content": "div.c-entry-content",
                    "author": "span.c-byline__author-name",
                    "date": "time"
                }
            },
            "hackernews": {
                "base_url": "https://news.ycombinator.com",
                "api_url": "https://hacker-news.firebaseio.com/v0/",
                "type": "api"
            }
        }
        
        self._setup_api_clients()
    
    def _setup_api_clients(self):
        """Initialize API clients for social media"""
        try:
            # Twitter API v2 setup
            twitter_bearer = os.getenv("TWITTER_BEARER_TOKEN")
            if twitter_bearer:
                self.twitter_client = tweepy.Client(bearer_token=twitter_bearer)
                self.logger.info("Twitter API client initialized")
            
            # LinkedIn API setup (using unofficial library)
            linkedin_email = os.getenv("LINKEDIN_EMAIL")
            linkedin_password = os.getenv("LINKEDIN_PASSWORD")
            if linkedin_email and linkedin_password:
                self.linkedin_client = linkedin_api.Linkedin(linkedin_email, linkedin_password)
                self.logger.info("LinkedIn API client initialized")
                
        except Exception as e:
            self.logger.warning(f"API client setup failed: {e}")
    
    async def execute_task(self, task_id: str):
        """Execute scraping task"""
        task = await self.task_queue.get_task(task_id)
        if not task:
            return
        
        self.logger.info(f"Executing scraping task: {task.description}")
        
        try:
            if task.task_type == "scrape_source":
                result = await self._scrape_news_source(
                    task.parameters.get("source_url"),
                    task.parameters.get("niche"),
                    task.parameters.get("max_age_hours", 24)
                )
            
            elif task.task_type == "scrape_social":
                result = await self._scrape_social_media(
                    task.parameters.get("platform"),
                    task.parameters.get("query"),
                    task.parameters.get("max_posts", 50)
                )
            
            elif task.task_type == "scrape_rss":
                result = await self._scrape_rss_feeds(
                    task.parameters.get("feed_urls"),
                    task.parameters.get("max_age_hours", 24)
                )
            
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            # Save results
            await self._save_scraped_content(task_id, result)
            
            # Update task status
            await self.task_queue.update_task_status(task_id, {
                "status": "completed",
                "result": f"Scraped {len(result)} articles",
                "completed_at": datetime.now().isoformat()
            })
            
            self.logger.info(f"Task {task_id} completed: {len(result)} articles scraped")
            
        except Exception as e:
            self.logger.error(f"Task {task_id} failed: {e}")
            await self.task_queue.update_task_status(task_id, {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            })
    
    async def _scrape_news_source(self, source_url: str, niche: str, max_age_hours: int) -> List[NewsArticle]:
        """Scrape articles from a news source"""
        articles = []
        
        # Identify source type
        domain = urlparse(source_url).netloc.lower()
        source_name = self._identify_source(domain)
        
        if source_name in self.news_sources:
            config = self.news_sources[source_name]
            
            if config.get("type") == "api":
                articles = await self._scrape_api_source(source_name, config, max_age_hours)
            else:
                articles = await self._scrape_web_source(source_name, config, max_age_hours)
        
        else:
            # Generic scraping
            articles = await self._scrape_generic_source(source_url, max_age_hours)
        
        # Filter by niche and age
        filtered_articles = self._filter_articles(articles, niche, max_age_hours)
        
        self.logger.info(f"Scraped {len(articles)} articles, filtered to {len(filtered_articles)}")
        return filtered_articles
    
    async def _scrape_web_source(self, source_name: str, config: Dict, max_age_hours: int) -> List[NewsArticle]:
        """Scrape web-based news source"""
        articles = []
        
        # Rate limiting
        await self.rate_limiter.wait_if_needed(source_name)
        
        try:
            # First try RSS feed
            if "rss_feed" in config:
                rss_articles = await self._parse_rss_feed(config["rss_feed"], max_age_hours)
                articles.extend(rss_articles)
            
            # Then scrape main page for additional articles
            async with aiohttp.ClientSession() as session:
                async with session.get(config["base_url"]) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Find article links
                        article_links = self._extract_article_links(soup, config["base_url"])
                        
                        # Scrape individual articles
                        for link in article_links[:10]:  # Limit to 10 articles per source
                            article = await self._scrape_individual_article(link, config["selectors"])
                            if article:
                                articles.append(article)
                            
                            # Small delay between requests
                            await asyncio.sleep(1)
        
        except Exception as e:
            self.logger.error(f"Error scraping {source_name}: {e}")
        
        return articles
    
    async def _scrape_api_source(self, source_name: str, config: Dict, max_age_hours: int) -> List[NewsArticle]:
        """Scrape API-based news source (e.g., Hacker News)"""
        articles = []
        
        if source_name == "hackernews":
            articles = await self._scrape_hackernews(config, max_age_hours)
        
        return articles
    
    async def _scrape_hackernews(self, config: Dict, max_age_hours: int) -> List[NewsArticle]:
        """Scrape Hacker News using their API"""
        articles = []
        
        try:
            # Get top stories
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{config['api_url']}topstories.json") as response:
                    story_ids = await response.json()
                
                # Get details for top 30 stories
                for story_id in story_ids[:30]:
                    async with session.get(f"{config['api_url']}item/{story_id}.json") as response:
                        story = await response.json()
                        
                        if story and story.get("type") == "story":
                            # Check age
                            story_time = datetime.fromtimestamp(story.get("time", 0))
                            if datetime.now() - story_time <= timedelta(hours=max_age_hours):
                                
                                article = NewsArticle(
                                    title=story.get("title", ""),
                                    content=story.get("text", ""),
                                    url=story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                                    source="Hacker News",
                                    published_at=story_time,
                                    author=story.get("by", ""),
                                    credibility_score=min(story.get("score", 0) / 100, 1.0)
                                )
                                
                                articles.append(article)
                    
                    await asyncio.sleep(0.1)  # Rate limiting
        
        except Exception as e:
            self.logger.error(f"Error scraping Hacker News: {e}")
        
        return articles
    
    async def _scrape_generic_source(self, url: str, max_age_hours: int) -> List[NewsArticle]:
        """Generic scraping for unknown sources"""
        articles = []
        
        try:
            # Use newspaper library for automatic extraction
            article = Article(url)
            article.download()
            article.parse()
            
            if article.title and article.text:
                news_article = NewsArticle(
                    title=article.title,
                    content=article.text,
                    url=url,
                    source=urlparse(url).netloc,
                    published_at=article.publish_date or datetime.now(),
                    author=", ".join(article.authors) if article.authors else None
                )
                
                articles.append(news_article)
        
        except Exception as e:
            self.logger.error(f"Error scraping generic source {url}: {e}")
        
        return articles
    
    async def _parse_rss_feed(self, feed_url: str, max_age_hours: int) -> List[NewsArticle]:
        """Parse RSS feed for articles"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                # Check age
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6])
                else:
                    published = datetime.now()
                
                if datetime.now() - published <= timedelta(hours=max_age_hours):
                    article = NewsArticle(
                        title=entry.title,
                        content=self._clean_html(entry.get('summary', '')),
                        url=entry.link,
                        source=feed.feed.get('title', 'Unknown'),
                        published_at=published,
                        author=entry.get('author', None)
                    )
                    
                    articles.append(article)
        
        except Exception as e:
            self.logger.error(f"Error parsing RSS feed {feed_url}: {e}")
        
        return articles
    
    async def _scrape_individual_article(self, url: str, selectors: Dict) -> Optional[NewsArticle]:
        """Scrape individual article using CSS selectors"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Extract content using selectors
                        title_elem = soup.select_one(selectors.get("title", "h1"))
                        content_elem = soup.select_one(selectors.get("content", "article"))
                        author_elem = soup.select_one(selectors.get("author", ""))
                        date_elem = soup.select_one(selectors.get("date", ""))
                        
                        if title_elem and content_elem:
                            title = title_elem.get_text().strip()
                            content = self._clean_html(content_elem.get_text())
                            author = author_elem.get_text().strip() if author_elem else None
                            
                            # Parse date
                            published_at = datetime.now()
                            if date_elem:
                                date_text = date_elem.get('datetime') or date_elem.get_text()
                                published_at = self._parse_date(date_text)
                            
                            return NewsArticle(
                                title=title,
                                content=content,
                                url=url,
                                source=urlparse(url).netloc,
                                published_at=published_at,
                                author=author
                            )
        
        except Exception as e:
            self.logger.error(f"Error scraping article {url}: {e}")
        
        return None
    
    async def _scrape_social_media(self, platform: str, query: str, max_posts: int) -> List[SocialPost]:
        """Scrape social media posts"""
        posts = []
        
        if platform == "twitter" and self.twitter_client:
            posts = await self._scrape_twitter(query, max_posts)
        elif platform == "linkedin" and self.linkedin_client:
            posts = await self._scrape_linkedin(query, max_posts)
        
        return posts
    
    async def _scrape_twitter(self, query: str, max_posts: int) -> List[SocialPost]:
        """Scrape Twitter posts using API"""
        posts = []
        
        try:
            tweets = tweepy.Paginator(
                self.twitter_client.search_recent_tweets,
                query=query,
                max_results=min(max_posts, 100),
                tweet_fields=['created_at', 'author_id', 'public_metrics', 'entities']
            ).flatten(limit=max_posts)
            
            for tweet in tweets:
                # Calculate engagement score
                metrics = tweet.public_metrics
                engagement = metrics['like_count'] + metrics['retweet_count'] + metrics['reply_count']
                
                # Extract hashtags and mentions
                hashtags = []
                mentions = []
                if tweet.entities:
                    hashtags = [tag['tag'] for tag in tweet.entities.get('hashtags', [])]
                    mentions = [mention['username'] for mention in tweet.entities.get('mentions', [])]
                
                post = SocialPost(
                    content=tweet.text,
                    platform="twitter",
                    author=str(tweet.author_id),  # Would need user lookup for username
                    url=f"https://twitter.com/i/status/{tweet.id}",
                    engagement_score=engagement,
                    posted_at=tweet.created_at,
                    hashtags=hashtags,
                    mentions=mentions
                )
                
                posts.append(post)
        
        except Exception as e:
            self.logger.error(f"Error scraping Twitter: {e}")
        
        return posts
    
    async def _scrape_linkedin(self, query: str, max_posts: int) -> List[SocialPost]:
        """Scrape LinkedIn posts (simplified)"""
        posts = []
        
        try:
            # LinkedIn API is limited - this is a placeholder
            # In practice, would need proper LinkedIn API access
            self.logger.info(f"LinkedIn scraping requested for: {query}")
            # posts = self.linkedin_client.search_posts(query, limit=max_posts)
        
        except Exception as e:
            self.logger.error(f"Error scraping LinkedIn: {e}")
        
        return posts
    
    def _filter_articles(self, articles: List[NewsArticle], niche: str, max_age_hours: int) -> List[NewsArticle]:
        """Filter articles by niche relevance and age"""
        filtered = []
        
        niche_keywords = {
            "tech": ["technology", "software", "ai", "artificial intelligence", "startup", "tech", "digital"],
            "startup": ["startup", "entrepreneur", "funding", "venture", "investment", "founder"],
            "finance": ["finance", "bank", "investment", "market", "economy", "financial"],
            "healthcare": ["health", "medical", "pharma", "healthcare", "medicine", "biotech"]
        }
        
        keywords = niche_keywords.get(niche.lower(), [])
        
        for article in articles:
            # Age filter
            age = datetime.now() - article.published_at
            if age > timedelta(hours=max_age_hours):
                continue
            
            # Content validation
            if not self.content_validator.is_valid_article(article):
                continue
            
            # Niche relevance (basic keyword matching)
            if keywords:
                text = f"{article.title} {article.content}".lower()
                if any(keyword in text for keyword in keywords):
                    filtered.append(article)
            else:
                filtered.append(article)
        
        # Remove duplicates
        seen_urls = set()
        unique_articles = []
        for article in filtered:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)
        
        return unique_articles
    
    def _identify_source(self, domain: str) -> str:
        """Identify news source from domain"""
        domain_mappings = {
            "techcrunch.com": "techcrunch",
            "arstechnica.com": "arstechnica",
            "theverge.com": "theverge",
            "news.ycombinator.com": "hackernews"
        }
        
        for known_domain, source_name in domain_mappings.items():
            if known_domain in domain:
                return source_name
        
        return "generic"
    
    def _extract_article_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract article links from main page"""
        links = []
        
        # Common selectors for article links
        selectors = [
            "a[href*='/article/']",
            "a[href*='/story/']",
            "a[href*='/news/']",
            "h2 a",
            "h3 a",
            ".article-title a"
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                href = elem.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    if self._is_article_url(full_url):
                        links.append(full_url)
        
        return list(set(links))  # Remove duplicates
    
    def _is_article_url(self, url: str) -> bool:
        """Check if URL looks like an article"""
        # Simple heuristics
        article_patterns = [
            r'/\d{4}/',  # Contains year
            r'/article/',
            r'/story/',
            r'/news/',
            r'/blog/',
            r'/post/'
        ]
        
        return any(re.search(pattern, url) for pattern in article_patterns)
    
    def _clean_html(self, text: str) -> str:
        """Clean HTML tags and normalize text"""
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', text)
        # Normalize whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean
    
    def _parse_date(self, date_text: str) -> datetime:
        """Parse date from various formats"""
        try:
            # Try ISO format first
            return datetime.fromisoformat(date_text.replace('Z', '+00:00'))
        except:
            try:
                # Try common formats
                from dateutil.parser import parse
                return parse(date_text)
            except:
                return datetime.now()
    
    async def _save_scraped_content(self, task_id: str, articles: List[NewsArticle]):
        """Save scraped content to storage"""
        output_file = f"data/scraped_{task_id}.json"
        os.makedirs("data", exist_ok=True)
        
        data = {
            "task_id": task_id,
            "scraped_at": datetime.now().isoformat(),
            "article_count": len(articles),
            "articles": [asdict(article) for article in articles]
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        self.logger.info(f"Saved {len(articles)} articles to {output_file}")

# Standalone execution
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Scraper Worker")
    parser.add_argument("--url", help="URL to scrape")
    parser.add_argument("--niche", default="tech", help="Content niche")
    parser.add_argument("--hours", type=int, default=24, help="Max age in hours")
    
    args = parser.parse_args()
    
    worker = ScraperWorker()
    
    if args.url:
        articles = await worker._scrape_news_source(args.url, args.niche, args.hours)
        print(f"Scraped {len(articles)} articles")
        for article in articles[:5]:
            print(f"- {article.title[:100]}...")

if __name__ == "__main__":
    asyncio.run(main())