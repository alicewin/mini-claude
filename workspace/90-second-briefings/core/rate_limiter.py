#!/usr/bin/env python3
"""
Rate Limiter for API calls and web scraping
Prevents hitting service limits and ensures respectful usage
"""

import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass
from collections import defaultdict, deque
import logging

@dataclass
class RateLimit:
    requests_per_minute: int
    requests_per_hour: int
    burst_limit: int
    cooldown_seconds: float = 1.0

class RateLimiter:
    """
    Rate limiter with per-service configurations
    Supports burst limits and adaptive backoff
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Rate limit configurations
        self.limits = {
            "anthropic": RateLimit(
                requests_per_minute=60,
                requests_per_hour=1000,
                burst_limit=10,
                cooldown_seconds=1.0
            ),
            "openai": RateLimit(
                requests_per_minute=60,
                requests_per_hour=500,
                burst_limit=8,
                cooldown_seconds=1.2
            ),
            "techcrunch": RateLimit(
                requests_per_minute=30,
                requests_per_hour=200,
                burst_limit=5,
                cooldown_seconds=2.0
            ),
            "arstechnica": RateLimit(
                requests_per_minute=20,
                requests_per_hour=150,
                burst_limit=3,
                cooldown_seconds=3.0
            ),
            "theverge": RateLimit(
                requests_per_minute=25,
                requests_per_hour=180,
                burst_limit=4,
                cooldown_seconds=2.5
            ),
            "hackernews": RateLimit(
                requests_per_minute=60,
                requests_per_hour=1000,
                burst_limit=10,
                cooldown_seconds=0.5
            ),
            "twitter": RateLimit(
                requests_per_minute=300,
                requests_per_hour=1500,
                burst_limit=15,
                cooldown_seconds=0.2
            ),
            "generic": RateLimit(
                requests_per_minute=10,
                requests_per_hour=100,
                burst_limit=2,
                cooldown_seconds=6.0
            )
        }
        
        # Tracking structures
        self.request_times: Dict[str, deque] = defaultdict(deque)
        self.last_request: Dict[str, float] = {}
        self.burst_count: Dict[str, int] = defaultdict(int)
        self.backoff_until: Dict[str, float] = {}
    
    async def wait_if_needed(self, service: str) -> float:
        """
        Wait if rate limit requires it, return actual delay
        """
        
        service_key = self._normalize_service_name(service)
        limit = self.limits.get(service_key, self.limits["generic"])
        
        now = time.time()
        
        # Check if we're in backoff period
        if service_key in self.backoff_until and now < self.backoff_until[service_key]:
            delay = self.backoff_until[service_key] - now
            self.logger.warning(f"Rate limiter: backing off {service_key} for {delay:.1f}s")
            await asyncio.sleep(delay)
            return delay
        
        # Clean old request times
        self._cleanup_old_requests(service_key, limit)
        
        # Check rate limits
        delay = await self._calculate_required_delay(service_key, limit)
        
        if delay > 0:
            self.logger.info(f"Rate limiter: delaying {service_key} for {delay:.1f}s")
            await asyncio.sleep(delay)
        
        # Record the request
        self.request_times[service_key].append(now + delay)
        self.last_request[service_key] = now + delay
        
        return delay
    
    def _normalize_service_name(self, service: str) -> str:
        """Normalize service name for rate limiting"""
        
        service = service.lower()
        
        # Map variations to standard names
        if "claude" in service or "anthropic" in service:
            return "anthropic"
        elif "openai" in service or "gpt" in service or "tts" in service:
            return "openai"
        elif "techcrunch" in service:
            return "techcrunch"
        elif "arstechnica" in service:
            return "arstechnica"
        elif "theverge" in service:
            return "theverge"
        elif "hackernews" in service or "ycombinator" in service:
            return "hackernews"
        elif "twitter" in service or "tweet" in service:
            return "twitter"
        else:
            return "generic"
    
    def _cleanup_old_requests(self, service_key: str, limit: RateLimit):
        """Remove old request timestamps"""
        
        now = time.time()
        requests = self.request_times[service_key]
        
        # Remove requests older than 1 hour
        while requests and now - requests[0] > 3600:
            requests.popleft()
    
    async def _calculate_required_delay(self, service_key: str, limit: RateLimit) -> float:
        """Calculate required delay based on rate limits"""
        
        now = time.time()
        requests = self.request_times[service_key]
        
        # Check minimum cooldown from last request
        last_req = self.last_request.get(service_key, 0)
        cooldown_delay = max(0, limit.cooldown_seconds - (now - last_req))
        
        # Check per-minute limit
        minute_ago = now - 60
        recent_requests = sum(1 for req_time in requests if req_time > minute_ago)
        
        if recent_requests >= limit.requests_per_minute:
            # Find when we can make the next request
            oldest_in_window = None
            for req_time in requests:
                if req_time > minute_ago:
                    oldest_in_window = req_time
                    break
            
            if oldest_in_window:
                minute_delay = oldest_in_window + 60 - now
                return max(cooldown_delay, minute_delay)
        
        # Check per-hour limit
        hour_ago = now - 3600
        hourly_requests = sum(1 for req_time in requests if req_time > hour_ago)
        
        if hourly_requests >= limit.requests_per_hour:
            # Find when we can make the next request
            oldest_in_hour = None
            for req_time in requests:
                if req_time > hour_ago:
                    oldest_in_hour = req_time
                    break
            
            if oldest_in_hour:
                hour_delay = oldest_in_hour + 3600 - now
                return max(cooldown_delay, hour_delay)
        
        # Check burst limit
        burst_window = 10  # seconds
        burst_start = now - burst_window
        burst_requests = sum(1 for req_time in requests if req_time > burst_start)
        
        if burst_requests >= limit.burst_limit:
            # Apply exponential backoff
            backoff_time = min(burst_requests * 2, 30)  # Max 30 seconds
            self.backoff_until[service_key] = now + backoff_time
            return backoff_time
        
        return cooldown_delay
    
    def get_service_stats(self, service: str) -> Dict[str, any]:
        """Get current rate limiting stats for a service"""
        
        service_key = self._normalize_service_name(service)
        limit = self.limits.get(service_key, self.limits["generic"])
        requests = self.request_times[service_key]
        
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        recent_requests = sum(1 for req_time in requests if req_time > minute_ago)
        hourly_requests = sum(1 for req_time in requests if req_time > hour_ago)
        
        return {
            "service": service_key,
            "requests_last_minute": recent_requests,
            "requests_last_hour": hourly_requests,
            "minute_limit": limit.requests_per_minute,
            "hour_limit": limit.requests_per_hour,
            "minute_utilization": recent_requests / limit.requests_per_minute,
            "hour_utilization": hourly_requests / limit.requests_per_hour,
            "is_backing_off": service_key in self.backoff_until and now < self.backoff_until[service_key],
            "last_request_ago": now - self.last_request.get(service_key, 0)
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, any]]:
        """Get stats for all services"""
        
        stats = {}
        for service_key in self.request_times.keys():
            stats[service_key] = self.get_service_stats(service_key)
        
        return stats

# Global rate limiter instance
_rate_limiter = None

def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

# Test function
async def test_rate_limiter():
    """Test rate limiter functionality"""
    
    limiter = RateLimiter()
    
    print("Testing rate limiter...")
    
    # Test rapid requests
    for i in range(5):
        start = time.time()
        delay = await limiter.wait_if_needed("anthropic")
        elapsed = time.time() - start
        print(f"Request {i+1}: waited {elapsed:.2f}s (delay: {delay:.2f}s)")
    
    # Check stats
    stats = limiter.get_service_stats("anthropic")
    print(f"\nAnthropics stats: {stats}")

if __name__ == "__main__":
    asyncio.run(test_rate_limiter())