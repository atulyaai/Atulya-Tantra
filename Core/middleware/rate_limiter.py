"""
Rate limiting middleware
Implements sliding window rate limiting for API endpoints
"""

import time
from typing import Dict, List, Optional, Callable
from collections import defaultdict, deque
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

from ..config.settings import settings
from ..config.logging import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """Implements sliding window rate limiting"""
    
    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    def is_allowed(
        self, 
        identifier: str, 
        limit: int = None, 
        window: int = None
    ) -> bool:
        """Check if request is allowed based on rate limit"""
        limit = limit or settings.rate_limit_requests
        window = window or settings.rate_limit_window
        
        now = time.time()
        identifier_requests = self.requests[identifier]
        
        # Remove expired requests
        while identifier_requests and identifier_requests[0] <= now - window:
            identifier_requests.popleft()
        
        # Check if limit exceeded
        if len(identifier_requests) >= limit:
            return False
        
        # Add current request
        identifier_requests.append(now)
        
        # Cleanup old entries periodically
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup_expired_entries(now, window)
            self.last_cleanup = now
        
        return True
    
    def get_remaining_requests(self, identifier: str, limit: int = None) -> int:
        """Get remaining requests for identifier"""
        limit = limit or settings.rate_limit_requests
        identifier_requests = self.requests[identifier]
        return max(0, limit - len(identifier_requests))
    
    def get_reset_time(self, identifier: str, window: int = None) -> float:
        """Get time when rate limit resets"""
        window = window or settings.rate_limit_window
        identifier_requests = self.requests[identifier]
        
        if not identifier_requests:
            return time.time()
        
        return identifier_requests[0] + window
    
    def _cleanup_expired_entries(self, now: float, window: int) -> None:
        """Clean up expired entries from memory"""
        expired_identifiers = []
        
        for identifier, requests in self.requests.items():
            # Remove expired requests
            while requests and requests[0] <= now - window:
                requests.popleft()
            
            # Remove empty entries
            if not requests:
                expired_identifiers.append(identifier)
        
        for identifier in expired_identifiers:
            del self.requests[identifier]

# Global rate limiter instance
rate_limiter = RateLimiter()

def get_client_identifier(request: Request) -> str:
    """Get unique identifier for rate limiting"""
    # Try to get user ID from JWT token first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from ..auth.jwt import verify_token
            token = auth_header.split(" ")[1]
            payload = verify_token(token)
            return f"user:{payload.get('sub', 'unknown')}"
        except Exception:
            pass
    
    # Fall back to IP address
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    
    return f"ip:{ip}"

async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    # Skip rate limiting for health checks and docs
    if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)
    
    # Get client identifier
    identifier = get_client_identifier(request)
    
    # Check rate limit
    if not rate_limiter.is_allowed(identifier):
        reset_time = rate_limiter.get_reset_time(identifier)
        retry_after = int(reset_time - time.time())
        
        logger.warning(f"Rate limit exceeded for {identifier}")
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "retry_after": retry_after,
                "limit": settings.rate_limit_requests,
                "window": settings.rate_limit_window
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(settings.rate_limit_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset_time))
            }
        )
    
    # Add rate limit headers to response
    response = await call_next(request)
    
    remaining = rate_limiter.get_remaining_requests(identifier)
    reset_time = rate_limiter.get_reset_time(identifier)
    
    response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(int(reset_time))
    
    return response

def create_rate_limit_decorator(limit: int, window: int = 60):
    """Create a rate limit decorator for specific endpoints"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # Extract request from kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                return await func(*args, **kwargs)
            
            identifier = get_client_identifier(request)
            
            if not rate_limiter.is_allowed(identifier, limit, window):
                reset_time = rate_limiter.get_reset_time(identifier, window)
                retry_after = int(reset_time - time.time())
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds",
                    headers={"Retry-After": str(retry_after)}
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator