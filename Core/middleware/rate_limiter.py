"""
Rate Limiting Middleware for Atulya Tantra AGI
Request rate limiting and throttling
"""

import time
from typing import Dict, Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from ..config.logging import get_logger
from ..config.exceptions import RateLimitExceeded

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter implementation"""
    
    def __init__(self):
        self.requests: Dict[str, list] = {}
        self.default_limit = 100  # requests per minute
        self.default_window = 60  # seconds
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    def is_allowed(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window: Optional[int] = None
    ) -> bool:
        """Check if request is allowed"""
        try:
            current_time = time.time()
            limit = limit or self.default_limit
            window = window or self.default_window
            
            # Cleanup old entries periodically
            if current_time - self.last_cleanup > self.cleanup_interval:
                self._cleanup_old_entries(current_time, window)
                self.last_cleanup = current_time
            
            # Get request history for identifier
            if identifier not in self.requests:
                self.requests[identifier] = []
            
            request_times = self.requests[identifier]
            
            # Remove old requests outside window
            cutoff_time = current_time - window
            request_times[:] = [t for t in request_times if t > cutoff_time]
            
            # Check if under limit
            if len(request_times) < limit:
                request_times.append(current_time)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True  # Allow on error
    
    def get_remaining_requests(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window: Optional[int] = None
    ) -> int:
        """Get remaining requests for identifier"""
        try:
            current_time = time.time()
            limit = limit or self.default_limit
            window = window or self.default_window
            
            if identifier not in self.requests:
                return limit
            
            request_times = self.requests[identifier]
            cutoff_time = current_time - window
            recent_requests = [t for t in request_times if t > cutoff_time]
            
            return max(0, limit - len(recent_requests))
            
        except Exception as e:
            logger.error(f"Error getting remaining requests: {e}")
            return limit
    
    def get_reset_time(
        self,
        identifier: str,
        window: Optional[int] = None
    ) -> float:
        """Get time when rate limit resets"""
        try:
            window = window or self.default_window
            
            if identifier not in self.requests:
                return time.time() + window
            
            request_times = self.requests[identifier]
            if not request_times:
                return time.time() + window
            
            oldest_request = min(request_times)
            return oldest_request + window
            
        except Exception as e:
            logger.error(f"Error getting reset time: {e}")
            return time.time() + window
    
    def _cleanup_old_entries(self, current_time: float, window: int):
        """Clean up old request entries"""
        try:
            cutoff_time = current_time - window
            
            for identifier in list(self.requests.keys()):
                request_times = self.requests[identifier]
                request_times[:] = [t for t in request_times if t > cutoff_time]
                
                # Remove empty entries
                if not request_times:
                    del self.requests[identifier]
                    
        except Exception as e:
            logger.error(f"Error cleaning up old entries: {e}")


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


class RateLimitMiddleware:
    """Rate limiting middleware for FastAPI"""
    
    def __init__(
        self,
        limit: int = 100,
        window: int = 60,
        identifier_func: Optional[callable] = None
    ):
        self.limit = limit
        self.window = window
        self.identifier_func = identifier_func or self._default_identifier
        self.rate_limiter = get_rate_limiter()
    
    def _default_identifier(self, request: Request) -> str:
        """Default identifier function using client IP"""
        # Get client IP
        client_ip = request.client.host
        
        # Check for forwarded IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        return client_ip
    
    async def __call__(self, request: Request, call_next):
        """Middleware function"""
        try:
            # Get identifier
            identifier = self.identifier_func(request)
            
            # Check rate limit
            if not self.rate_limiter.is_allowed(identifier, self.limit, self.window):
                remaining = self.rate_limiter.get_remaining_requests(identifier, self.limit, self.window)
                reset_time = self.rate_limiter.get_reset_time(identifier, self.window)
                
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "message": "Too many requests",
                        "retry_after": int(reset_time - time.time()),
                        "remaining": remaining
                    }
                )
                
                # Add rate limit headers
                response.headers["X-RateLimit-Limit"] = str(self.limit)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(int(reset_time))
                response.headers["Retry-After"] = str(int(reset_time - time.time()))
                
                return response
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to response
            remaining = self.rate_limiter.get_remaining_requests(identifier, self.limit, self.window)
            reset_time = self.rate_limiter.get_reset_time(identifier, self.window)
            
            response.headers["X-RateLimit-Limit"] = str(self.limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(reset_time))
            
            return response
            
        except Exception as e:
            logger.error(f"Error in rate limit middleware: {e}")
            # Allow request on error
            return await call_next(request)


def create_rate_limit_middleware(
    limit: int = 100,
    window: int = 60,
    identifier_func: Optional[callable] = None
) -> RateLimitMiddleware:
    """Create rate limit middleware"""
    return RateLimitMiddleware(limit, window, identifier_func)


# Export public API
__all__ = [
    "RateLimiter",
    "RateLimitMiddleware",
    "get_rate_limiter",
    "create_rate_limit_middleware"
]