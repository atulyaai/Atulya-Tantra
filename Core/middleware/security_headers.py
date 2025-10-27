"""
Security Headers Middleware for Atulya Tantra AGI
Security headers and protection mechanisms
"""

from typing import Dict, List, Optional
from fastapi import Request, Response

from ..config.logging import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class SecurityHeaders:
    """Security headers configuration"""
    
    def __init__(self):
        self.headers = {
            # Content Security Policy
            "Content-Security-Policy": self._get_csp(),
            
            # X-Frame-Options
            "X-Frame-Options": "DENY",
            
            # X-Content-Type-Options
            "X-Content-Type-Options": "nosniff",
            
            # X-XSS-Protection
            "X-XSS-Protection": "1; mode=block",
            
            # Referrer Policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Permissions Policy
            "Permissions-Policy": self._get_permissions_policy(),
            
            # Strict Transport Security
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            
            # Cross-Origin Embedder Policy
            "Cross-Origin-Embedder-Policy": "require-corp",
            
            # Cross-Origin Opener Policy
            "Cross-Origin-Opener-Policy": "same-origin",
            
            # Cross-Origin Resource Policy
            "Cross-Origin-Resource-Policy": "same-origin",
            
            # Cache Control
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    
    def _get_csp(self) -> str:
        """Get Content Security Policy"""
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self'",
            "connect-src 'self'",
            "media-src 'self'",
            "object-src 'none'",
            "child-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'",
            "manifest-src 'self'"
        ]
        
        return "; ".join(csp_directives)
    
    def _get_permissions_policy(self) -> str:
        """Get Permissions Policy"""
        permissions = [
            "accelerometer=()",
            "ambient-light-sensor=()",
            "autoplay=()",
            "battery=()",
            "camera=()",
            "display-capture=()",
            "document-domain=()",
            "encrypted-media=()",
            "fullscreen=()",
            "geolocation=()",
            "gyroscope=()",
            "magnetometer=()",
            "microphone=()",
            "midi=()",
            "payment=()",
            "picture-in-picture=()",
            "publickey-credentials-get=()",
            "usb=()",
            "web-share=()",
            "xr-spatial-tracking=()"
        ]
        
        return ", ".join(permissions)
    
    def get_headers(self) -> Dict[str, str]:
        """Get security headers"""
        return self.headers.copy()
    
    def add_header(self, name: str, value: str):
        """Add custom header"""
        self.headers[name] = value
    
    def remove_header(self, name: str):
        """Remove header"""
        self.headers.pop(name, None)


class SecurityHeadersMiddleware:
    """Security headers middleware for FastAPI"""
    
    def __init__(self, security_headers: Optional[SecurityHeaders] = None):
        self.security_headers = security_headers or SecurityHeaders()
    
    async def __call__(self, request: Request, call_next):
        """Middleware function"""
        # Process request
        response = await call_next(request)
        
        # Add security headers
        headers = self.security_headers.get_headers()
        for name, value in headers.items():
            response.headers[name] = value
        
        return response


class CORSHeaders:
    """CORS headers configuration"""
    
    def __init__(self):
        self.allowed_origins = settings.ALLOWED_ORIGINS
        self.allowed_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        self.allowed_headers = [
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "Accept",
            "Origin"
        ]
        self.allow_credentials = True
        self.max_age = 3600
    
    def get_headers(self) -> Dict[str, str]:
        """Get CORS headers"""
        return {
            "Access-Control-Allow-Origin": ", ".join(self.allowed_origins),
            "Access-Control-Allow-Methods": ", ".join(self.allowed_methods),
            "Access-Control-Allow-Headers": ", ".join(self.allowed_headers),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": str(self.max_age)
        }


class CORSHeadersMiddleware:
    """CORS headers middleware for FastAPI"""
    
    def __init__(self, cors_headers: Optional[CORSHeaders] = None):
        self.cors_headers = cors_headers or CORSHeaders()
    
    async def __call__(self, request: Request, call_next):
        """Middleware function"""
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response()
            headers = self.cors_headers.get_headers()
            for name, value in headers.items():
                response.headers[name] = value
            return response
        
        # Process request
        response = await call_next(request)
        
        # Add CORS headers
        headers = self.cors_headers.get_headers()
        for name, value in headers.items():
            response.headers[name] = value
        
        return response


class TrustedHostMiddleware:
    """Trusted host middleware for FastAPI"""
    
    def __init__(self, allowed_hosts: Optional[List[str]] = None):
        self.allowed_hosts = allowed_hosts or ["*"]
    
    async def __call__(self, request: Request, call_next):
        """Middleware function"""
        # Check if host is allowed
        host = request.headers.get("host", "")
        
        if "*" not in self.allowed_hosts and host not in self.allowed_hosts:
            return Response(
                content="Host not allowed",
                status_code=400
            )
        
        # Process request
        response = await call_next(request)
        return response


def create_security_headers_middleware(
    security_headers: Optional[SecurityHeaders] = None
) -> SecurityHeadersMiddleware:
    """Create security headers middleware"""
    return SecurityHeadersMiddleware(security_headers)


def create_cors_headers_middleware(
    cors_headers: Optional[CORSHeaders] = None
) -> CORSHeadersMiddleware:
    """Create CORS headers middleware"""
    return CORSHeadersMiddleware(cors_headers)


def create_trusted_host_middleware(
    allowed_hosts: Optional[List[str]] = None
) -> TrustedHostMiddleware:
    """Create trusted host middleware"""
    return TrustedHostMiddleware(allowed_hosts)


# Export public API
__all__ = [
    "SecurityHeaders",
    "SecurityHeadersMiddleware",
    "CORSHeaders",
    "CORSHeadersMiddleware",
    "TrustedHostMiddleware",
    "create_security_headers_middleware",
    "create_cors_headers_middleware",
    "create_trusted_host_middleware"
]