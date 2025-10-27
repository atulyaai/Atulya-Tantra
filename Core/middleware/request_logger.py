"""
Request Logging Middleware for Atulya Tantra AGI
Request/response logging and monitoring
"""

import time
import json
from typing import Dict, Any, Optional
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

from ..config.logging import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class RequestLogger:
    """Request logging utility"""
    
    def __init__(self):
        self.log_requests = settings.LOG_REQUESTS
        self.log_responses = settings.LOG_RESPONSES
        self.log_body = settings.LOG_REQUEST_BODY
        self.max_body_size = settings.MAX_LOG_BODY_SIZE
    
    def log_request(self, request: Request, start_time: float):
        """Log incoming request"""
        try:
            if not self.log_requests:
                return
            
            # Get request details
            method = request.method
            url = str(request.url)
            headers = dict(request.headers)
            client_ip = self._get_client_ip(request)
            user_agent = headers.get("user-agent", "")
            
            # Get request body if enabled
            body = None
            if self.log_body and method in ["POST", "PUT", "PATCH"]:
                body = self._get_request_body(request)
            
            # Create log entry
            log_entry = {
                "type": "request",
                "method": method,
                "url": url,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "headers": self._sanitize_headers(headers),
                "body": body,
                "timestamp": start_time
            }
            
            logger.info(f"Request: {method} {url}", extra=log_entry)
            
        except Exception as e:
            logger.error(f"Error logging request: {e}")
    
    def log_response(
        self,
        request: Request,
        response: Response,
        start_time: float,
        end_time: float
    ):
        """Log outgoing response"""
        try:
            if not self.log_responses:
                return
            
            # Calculate processing time
            processing_time = end_time - start_time
            
            # Get response details
            status_code = response.status_code
            headers = dict(response.headers)
            
            # Get response body if enabled
            body = None
            if self.log_body and hasattr(response, 'body'):
                body = self._get_response_body(response)
            
            # Create log entry
            log_entry = {
                "type": "response",
                "method": request.method,
                "url": str(request.url),
                "status_code": status_code,
                "processing_time": processing_time,
                "headers": self._sanitize_headers(headers),
                "body": body,
                "timestamp": end_time
            }
            
            logger.info(
                f"Response: {request.method} {request.url} - {status_code} ({processing_time:.3f}s)",
                extra=log_entry
            )
            
        except Exception as e:
            logger.error(f"Error logging response: {e}")
    
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
        
        # Use client host
        return request.client.host if request.client else "unknown"
    
    def _get_request_body(self, request: Request) -> Optional[str]:
        """Get request body"""
        try:
            # Check content type
            content_type = request.headers.get("content-type", "")
            
            # Skip binary content
            if "application/octet-stream" in content_type:
                return "[Binary content]"
            
            # Get body
            body = request.body()
            if not body:
                return None
            
            # Limit body size
            if len(body) > self.max_body_size:
                return f"[Body too large: {len(body)} bytes]"
            
            # Decode body
            try:
                return body.decode("utf-8")
            except UnicodeDecodeError:
                return "[Binary content]"
                
        except Exception as e:
            logger.error(f"Error getting request body: {e}")
            return None
    
    def _get_response_body(self, response: Response) -> Optional[str]:
        """Get response body"""
        try:
            # Skip streaming responses
            if isinstance(response, StreamingResponse):
                return "[Streaming response]"
            
            # Get body
            if hasattr(response, 'body') and response.body:
                body = response.body
                
                # Limit body size
                if len(body) > self.max_body_size:
                    return f"[Body too large: {len(body)} bytes]"
                
                # Decode body
                try:
                    return body.decode("utf-8")
                except UnicodeDecodeError:
                    return "[Binary content]"
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting response body: {e}")
            return None
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize headers for logging"""
        sensitive_headers = {
            "authorization",
            "cookie",
            "x-api-key",
            "x-auth-token",
            "x-access-token"
        }
        
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        
        return sanitized


class RequestLoggingMiddleware:
    """Request logging middleware for FastAPI"""
    
    def __init__(self, request_logger: Optional[RequestLogger] = None):
        self.request_logger = request_logger or RequestLogger()
    
    async def __call__(self, request: Request, call_next):
        """Middleware function"""
        start_time = time.time()
        
        # Log request
        self.request_logger.log_request(request, start_time)
        
        # Process request
        response = await call_next(request)
        
        # Log response
        end_time = time.time()
        self.request_logger.log_response(request, response, start_time, end_time)
        
        return response


def create_request_logging_middleware(
    request_logger: Optional[RequestLogger] = None
) -> RequestLoggingMiddleware:
    """Create request logging middleware"""
    return RequestLoggingMiddleware(request_logger)


# Export public API
__all__ = [
    "RequestLogger",
    "RequestLoggingMiddleware",
    "create_request_logging_middleware"
]