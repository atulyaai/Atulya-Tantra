"""
Request logging middleware
Logs HTTP requests and responses for monitoring and debugging
"""

import time
import uuid
from typing import Dict, Any
from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..config.logging import get_logger

logger = get_logger(__name__)

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Logs HTTP requests and responses"""
    
    def __init__(self, app, **kwargs):
        super().__init__(app)
        self.sensitive_headers = {
            "authorization", "cookie", "x-api-key", "x-auth-token"
        }
        self.sensitive_paths = {
            "/api/auth/login", "/api/auth/register", "/api/auth/refresh"
        }
    
    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request
        await self._log_request(request, request_id)
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error
            await self._log_error(request, request_id, e, time.time() - start_time)
            raise
        
        # Log response
        await self._log_response(request, response, request_id, time.time() - start_time)
        
        return response
    
    async def _log_request(self, request: Request, request_id: str):
        """Log incoming request"""
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Get user info if available
        user_info = self._get_user_info(request)
        
        # Prepare request data
        request_data = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": client_ip,
            "user_agent": request.headers.get("user-agent", ""),
            "content_type": request.headers.get("content-type", ""),
            "content_length": request.headers.get("content-length", "0"),
            "user_info": user_info,
            "timestamp": time.time()
        }
        
        # Add headers (excluding sensitive ones)
        headers = {}
        for name, value in request.headers.items():
            if name.lower() not in self.sensitive_headers:
                headers[name] = value
        request_data["headers"] = headers
        
        # Add body for non-sensitive requests
        if request.method in ["POST", "PUT", "PATCH"] and request.url.path not in self.sensitive_paths:
            try:
                body = await request.body()
                if body and len(body) < 1000:  # Only log small bodies
                    request_data["body"] = body.decode("utf-8", errors="ignore")
            except Exception:
                pass
        
        logger.info("HTTP Request", extra=request_data)
    
    async def _log_response(self, request: Request, response: Response, request_id: str, duration: float):
        """Log outgoing response"""
        response_data = {
            "request_id": request_id,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "content_type": response.headers.get("content-type", ""),
            "content_length": response.headers.get("content-length", "0"),
            "timestamp": time.time()
        }
        
        # Add response headers (excluding sensitive ones)
        headers = {}
        for name, value in response.headers.items():
            if name.lower() not in self.sensitive_headers:
                headers[name] = value
        response_data["headers"] = headers
        
        # Log level based on status code
        if response.status_code >= 500:
            logger.error("HTTP Response", extra=response_data)
        elif response.status_code >= 400:
            logger.warning("HTTP Response", extra=response_data)
        else:
            logger.info("HTTP Response", extra=response_data)
    
    async def _log_error(self, request: Request, request_id: str, error: Exception, duration: float):
        """Log request error"""
        error_data = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "duration_ms": round(duration * 1000, 2),
            "timestamp": time.time()
        }
        
        logger.error("HTTP Request Error", extra=error_data)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client host
        return request.client.host if request.client else "unknown"
    
    def _get_user_info(self, request: Request) -> Dict[str, Any]:
        """Get user information from request"""
        user_info = {}
        
        # Try to get user ID from JWT token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from ..auth.jwt import verify_token
                token = auth_header.split(" ")[1]
                payload = verify_token(token)
                user_info["user_id"] = payload.get("sub")
                user_info["username"] = payload.get("username")
            except Exception:
                pass
        
        return user_info