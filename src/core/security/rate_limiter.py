"""
Atulya Tantra - Rate Limiter
Version: 2.5.0
Implements rate limiting for API endpoints to prevent abuse
"""

import time
import asyncio
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter implementation
    """
    
    def __init__(self, max_requests: int = 100, time_window: int = 60):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum number of requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.lock = asyncio.Lock()
    
    async def is_allowed(self, identifier: str) -> Tuple[bool, Dict[str, int]]:
        """
        Check if request is allowed for given identifier
        
        Args:
            identifier: Unique identifier (e.g., user_id, ip_address)
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        async with self.lock:
            now = time.time()
            user_requests = self.requests[identifier]
            
            # Remove old requests outside time window
            while user_requests and user_requests[0] <= now - self.time_window:
                user_requests.popleft()
            
            # Check if under limit
            if len(user_requests) < self.max_requests:
                user_requests.append(now)
                remaining = self.max_requests - len(user_requests)
                reset_time = int(now + self.time_window)
                
                return True, {
                    "limit": self.max_requests,
                    "remaining": remaining,
                    "reset": reset_time
                }
            else:
                # Rate limit exceeded
                oldest_request = user_requests[0]
                reset_time = int(oldest_request + self.time_window)
                
                return False, {
                    "limit": self.max_requests,
                    "remaining": 0,
                    "reset": reset_time
                }
    
    async def get_status(self, identifier: str) -> Dict[str, int]:
        """
        Get current rate limit status for identifier
        
        Args:
            identifier: Unique identifier
            
        Returns:
            Rate limit status information
        """
        async with self.lock:
            now = time.time()
            user_requests = self.requests[identifier]
            
            # Remove old requests
            while user_requests and user_requests[0] <= now - self.time_window:
                user_requests.popleft()
            
            remaining = max(0, self.max_requests - len(user_requests))
            reset_time = int(now + self.time_window) if user_requests else int(now)
            
            return {
                "limit": self.max_requests,
                "remaining": remaining,
                "reset": reset_time
            }


class AdaptiveRateLimiter(RateLimiter):
    """
    Adaptive rate limiter that adjusts limits based on system load
    """
    
    def __init__(self, base_max_requests: int = 100, time_window: int = 60):
        super().__init__(base_max_requests, time_window)
        self.base_max_requests = base_max_requests
        self.current_max_requests = base_max_requests
        self.load_threshold = 0.8  # 80% load threshold
        self.min_requests = 10  # Minimum requests per window
    
    async def update_load(self, cpu_usage: float, memory_usage: float):
        """
        Update rate limits based on system load
        
        Args:
            cpu_usage: CPU usage percentage (0-1)
            memory_usage: Memory usage percentage (0-1)
        """
        # Calculate combined load
        combined_load = (cpu_usage + memory_usage) / 2
        
        if combined_load > self.load_threshold:
            # Reduce rate limit under high load
            self.current_max_requests = max(
                self.min_requests,
                int(self.base_max_requests * (1 - combined_load))
            )
        else:
            # Restore normal rate limit
            self.current_max_requests = self.base_max_requests
        
        # Update the parent class limit
        self.max_requests = self.current_max_requests
        
        logger.info(f"Rate limit adjusted to {self.current_max_requests} requests per {self.time_window}s (load: {combined_load:.2f})")


class DistributedRateLimiter:
    """
    Distributed rate limiter using Redis for multi-instance deployments
    """
    
    def __init__(self, redis_client, max_requests: int = 100, time_window: int = 60):
        """
        Initialize distributed rate limiter
        
        Args:
            redis_client: Redis client instance
            max_requests: Maximum requests per time window
            time_window: Time window in seconds
        """
        self.redis = redis_client
        self.max_requests = max_requests
        self.time_window = time_window
    
    async def is_allowed(self, identifier: str) -> Tuple[bool, Dict[str, int]]:
        """
        Check if request is allowed using Redis
        
        Args:
            identifier: Unique identifier
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        key = f"rate_limit:{identifier}"
        now = int(time.time())
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, now - self.time_window)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Set expiration
        pipe.expire(key, self.time_window)
        
        results = await pipe.execute()
        current_requests = results[1]
        
        if current_requests < self.max_requests:
            remaining = self.max_requests - current_requests - 1
            reset_time = now + self.time_window
            
            return True, {
                "limit": self.max_requests,
                "remaining": remaining,
                "reset": reset_time
            }
        else:
            # Get oldest request time
            oldest_requests = await self.redis.zrange(key, 0, 0, withscores=True)
            if oldest_requests:
                oldest_time = int(oldest_requests[0][1])
                reset_time = oldest_time + self.time_window
            else:
                reset_time = now + self.time_window
            
            return False, {
                "limit": self.max_requests,
                "remaining": 0,
                "reset": reset_time
            }
    
    async def get_status(self, identifier: str) -> Dict[str, int]:
        """
        Get current rate limit status
        
        Args:
            identifier: Unique identifier
            
        Returns:
            Rate limit status information
        """
        key = f"rate_limit:{identifier}"
        now = int(time.time())
        
        # Remove old entries and count current
        await self.redis.zremrangebyscore(key, 0, now - self.time_window)
        current_requests = await self.redis.zcard(key)
        
        remaining = max(0, self.max_requests - current_requests)
        reset_time = now + self.time_window
        
        return {
            "limit": self.max_requests,
            "remaining": remaining,
            "reset": reset_time
        }


# Global rate limiter instances
rate_limiters: Dict[str, RateLimiter] = {
    "default": RateLimiter(max_requests=100, time_window=60),
    "strict": RateLimiter(max_requests=10, time_window=60),
    "lenient": RateLimiter(max_requests=1000, time_window=60),
}


def get_rate_limiter(limiter_type: str = "default") -> RateLimiter:
    """
    Get rate limiter instance by type
    
    Args:
        limiter_type: Type of rate limiter to get
        
    Returns:
        Rate limiter instance
    """
    return rate_limiters.get(limiter_type, rate_limiters["default"])


async def check_rate_limit(identifier: str, limiter_type: str = "default") -> Tuple[bool, Dict[str, int]]:
    """
    Check rate limit for identifier
    
    Args:
        identifier: Unique identifier
        limiter_type: Type of rate limiter to use
        
    Returns:
        Tuple of (is_allowed, rate_limit_info)
    """
    limiter = get_rate_limiter(limiter_type)
    return await limiter.is_allowed(identifier)
