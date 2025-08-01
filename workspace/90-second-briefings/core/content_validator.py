#!/usr/bin/env python3
"""
Content Validator for news articles and social posts
Quality control and filtering for scraped content
"""

import re
from typing import List, Optional
from urllib.parse import urlparse
import logging

class ContentValidator:
    """
    Validates scraped content for quality and relevance
    Filters out spam, duplicate, and low-quality content
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Quality thresholds
        self.min_title_length = 10
        self.max_title_length = 200
        self.min_content_length = 100
        self.max_content_length = 50000
        
        # Spam indicators
        self.spam_phrases = [
            "click here", "buy now", "limited time", "act fast",
            "make money", "work from home", "guaranteed",
            "free trial", "no obligation", "special offer"
        ]
        
        # Low-quality content indicators
        self.low_quality_indicators = [
            "lorem ipsum", "placeholder", "test content",
            "coming soon", "under construction", "404",
            "page not found", "access denied"
        ]
        
        # Trusted domains (higher quality score)
        self.trusted_domains = {
            'techcrunch.com', 'arstechnica.com', 'theverge.com',
            'reuters.com', 'bbc.com', 'cnn.com', 'wsj.com',
            'nytimes.com', 'washingtonpost.com', 'bloomberg.com',
            'wired.com', 'engadget.com', 'zdnet.com'
        }
        
        # Content patterns to validate
        self.valid_content_patterns = [
            r'\b\d{4}\b',  # Years
            r'\$\d+',      # Money amounts
            r'\d+%',       # Percentages
            r'\b(CEO|CTO|CFO)\b',  # Business titles
        ]
    
    def is_valid_article(self, article) -> bool:
        """
        Main validation function for news articles
        Returns True if article passes quality checks
        """
        
        try:
            # Basic structure validation
            if not self._has_required_fields(article):
                return False
            
            # Title validation
            if not self._is_valid_title(article.title):
                return False
            
            # Content validation
            if not self._is_valid_content(article.content):
                return False
            
            # URL validation
            if not self._is_valid_url(article.url):
                return False
            
            # Spam detection
            if self._is_spam_content(article.title, article.content):
                return False
            
            # Language detection (basic)
            if not self._is_english_content(article.content):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating article: {e}")
            return False
    
    def _has_required_fields(self, article) -> bool:
        """Check if article has required fields"""
        
        required_fields = ['title', 'content', 'url', 'source']
        
        for field in required_fields:
            if not hasattr(article, field) or not getattr(article, field):
                self.logger.debug(f"Article missing required field: {field}")
                return False
        
        return True
    
    def _is_valid_title(self, title: str) -> bool:
        """Validate article title"""
        
        if not title or not isinstance(title, str):
            return False
        
        title = title.strip()
        
        # Length checks
        if len(title) < self.min_title_length or len(title) > self.max_title_length:
            return False
        
        # Basic content checks
        if title.lower() in ['untitled', 'no title', 'title', '']:
            return False
        
        # Check for excessive capitalization
        if title.isupper() and len(title) > 20:
            return False
        
        # Check for excessive punctuation
        punct_ratio = sum(1 for c in title if not c.isalnum() and c != ' ') / len(title)
        if punct_ratio > 0.3:
            return False
        
        return True
    
    def _is_valid_content(self, content: str) -> bool:
        """Validate article content"""
        
        if not content or not isinstance(content, str):
            return False
        
        content = content.strip()
        
        # Length checks
        if len(content) < self.min_content_length or len(content) > self.max_content_length:
            return False
        
        # Check for placeholder content
        content_lower = content.lower()
        for indicator in self.low_quality_indicators:
            if indicator in content_lower:
                return False
        
        # Check for reasonable word count
        words = content.split()
        if len(words) < 20:  # Too few words
            return False
        
        # Check for reasonable sentence structure
        sentences = re.split(r'[.!?]+', content)
        valid_sentences = [s for s in sentences if len(s.strip()) > 10]
        if len(valid_sentences) < 3:  # Too few sentences
            return False
        
        # Check for content patterns that indicate real articles
        pattern_matches = 0
        for pattern in self.valid_content_patterns:
            if re.search(pattern, content):
                pattern_matches += 1
        
        # Should have some business/news patterns
        if pattern_matches < 1 and len(content) > 1000:
            return False
        
        return True
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate article URL"""
        
        if not url or not isinstance(url, str):
            return False
        
        try:
            parsed = urlparse(url)
            
            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Must be http/https
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Check for suspicious patterns
            suspicious_patterns = [
                r'bit\.ly', r'tinyurl', r'short\.link',  # URL shorteners
                r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}',  # IP addresses
                r'localhost', r'127\.0\.0\.1'  # Local addresses
            ]
            
            for pattern in suspicious_patterns:
                if re.search(pattern, url):
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _is_spam_content(self, title: str, content: str) -> bool:
        """Detect spam content"""
        
        text = f"{title} {content}".lower()
        
        # Check for spam phrases
        spam_count = 0
        for phrase in self.spam_phrases:
            if phrase in text:
                spam_count += 1
        
        # More than 2 spam phrases is suspicious
        if spam_count > 2:
            return True
        
        # Check for excessive exclamation marks
        exclamation_ratio = text.count('!') / len(text)
        if exclamation_ratio > 0.02:  # More than 2% exclamation marks
            return True
        
        # Check for excessive capitalization
        if title:
            caps_ratio = sum(1 for c in title if c.isupper()) / len(title)
            if caps_ratio > 0.5:  # More than 50% caps
                return True
        
        return False
    
    def _is_english_content(self, content: str) -> bool:
        """Basic English language detection"""
        
        if not content:
            return False
        
        # Check for common English words
        common_english_words = [
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through',
            'during', 'before', 'after', 'above', 'below', 'between'
        ]
        
        words = content.lower().split()
        english_word_count = sum(1 for word in words if word in common_english_words)
        
        # At least 5% should be common English words
        if len(words) > 20 and english_word_count / len(words) < 0.05:
            return False
        
        # Check character set (basic)
        non_ascii_ratio = sum(1 for c in content if ord(c) > 127) / len(content)
        if non_ascii_ratio > 0.1:  # More than 10% non-ASCII characters
            return False
        
        return True
    
    def calculate_quality_score(self, article) -> float:
        """
        Calculate a quality score from 0.0 to 1.0 for an article
        Higher scores indicate higher quality
        """
        
        score = 0.5  # Base score
        
        try:
            # Source reputation
            if hasattr(article, 'source') and article.source:
                domain = urlparse(article.url).netloc.lower()
                if any(trusted in domain for trusted in self.trusted_domains):
                    score += 0.2
            
            # Content length (optimal range)
            if hasattr(article, 'content') and article.content:
                content_len = len(article.content)
                if 500 <= content_len <= 5000:  # Optimal range
                    score += 0.1
                elif content_len > 5000:  # Long-form content
                    score += 0.05
            
            # Author information
            if hasattr(article, 'author') and article.author:
                score += 0.1
            
            # Recent publication
            if hasattr(article, 'published_at') and article.published_at:
                from datetime import datetime, timedelta
                age = datetime.now() - article.published_at
                if age < timedelta(hours=6):  # Very recent
                    score += 0.1
                elif age < timedelta(hours=24):  # Recent
                    score += 0.05
            
            # Content patterns
            if hasattr(article, 'content') and article.content:
                pattern_score = 0
                for pattern in self.valid_content_patterns:
                    if re.search(pattern, article.content):
                        pattern_score += 0.02
                score += min(pattern_score, 0.1)
            
            # Title quality
            if hasattr(article, 'title') and article.title:
                title = article.title
                # Reasonable length
                if 30 <= len(title) <= 100:
                    score += 0.05
                # Not all caps
                if not title.isupper():
                    score += 0.02
                # Has numbers (often indicates data/specificity)
                if re.search(r'\d+', title):
                    score += 0.03
            
            return min(score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error calculating quality score: {e}")
            return 0.5
    
    def is_duplicate_content(self, article1, article2, threshold: float = 0.8) -> bool:
        """
        Check if two articles are duplicates based on content similarity
        """
        
        try:
            # Title similarity
            title1 = article1.title.lower() if article1.title else ""
            title2 = article2.title.lower() if article2.title else ""
            
            # Simple similarity check
            if title1 and title2:
                title_similarity = self._calculate_similarity(title1, title2)
                if title_similarity > threshold:
                    return True
            
            # URL similarity (same domain + similar path)
            if hasattr(article1, 'url') and hasattr(article2, 'url'):
                if article1.url == article2.url:
                    return True
            
            # Content similarity (first 500 chars)
            content1 = article1.content[:500].lower() if article1.content else ""
            content2 = article2.content[:500].lower() if article2.content else ""
            
            if content1 and content2:
                content_similarity = self._calculate_similarity(content1, content2)
                if content_similarity > threshold:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking duplicate content: {e}")
            return False
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts using simple word overlap
        """
        
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0

# Test function
def test_content_validator():
    """Test content validator functionality"""
    
    validator = ContentValidator()
    
    # Mock article class
    class MockArticle:
        def __init__(self, title, content, url, source, author=None):
            self.title = title
            self.content = content
            self.url = url
            self.source = source
            self.author = author
    
    # Test cases
    good_article = MockArticle(
        title="Tech Company Raises $10M in Series A Funding",
        content="A promising startup in the artificial intelligence space has successfully raised $10 million in Series A funding. The company, founded in 2023, focuses on developing machine learning solutions for healthcare applications. The funding will be used to expand their engineering team and accelerate product development.",
        url="https://techcrunch.com/2024/01/15/startup-funding",
        source="techcrunch.com",
        author="Jane Reporter"
    )
    
    spam_article = MockArticle(
        title="MAKE MONEY FAST - CLICK HERE NOW!!!",
        content="Buy now! Limited time offer! Make money from home guaranteed! Click here to start earning immediately! No obligation free trial!",
        url="https://spam-site.com/offer",
        source="spam-site.com"
    )
    
    short_article = MockArticle(
        title="Short",
        content="Too short.",
        url="https://example.com/short",
        source="example.com"
    )
    
    # Test validation
    print("Testing content validator...")
    print(f"Good article valid: {validator.is_valid_article(good_article)}")
    print(f"Spam article valid: {validator.is_valid_article(spam_article)}")
    print(f"Short article valid: {validator.is_valid_article(short_article)}")
    
    # Test quality scores
    print(f"Good article quality: {validator.calculate_quality_score(good_article):.3f}")
    print(f"Spam article quality: {validator.calculate_quality_score(spam_article):.3f}")
    print(f"Short article quality: {validator.calculate_quality_score(short_article):.3f}")

if __name__ == "__main__":
    test_content_validator()