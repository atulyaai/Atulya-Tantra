"""
Security utilities and input validation
Handles input sanitization, validation, and security checks
"""

import re
import html
import bleach
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
import ipaddress

from ..config.logging import get_logger

logger = get_logger(__name__)

class SecurityManager:
    """Manages security operations and input validation"""
    
    def __init__(self):
        # Allowed HTML tags for rich text
        self.allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 'b', 'i', 'ul', 'ol', 'li',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre'
        ]
        
        # Allowed HTML attributes
        self.allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            'code': ['class'],
            'pre': ['class']
        }
        
        # SQL injection patterns
        self.sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\b(OR|AND)\s+['\"].*['\"]\s*=\s*['\"].*['\"])",
            r"(\bUNION\s+SELECT\b)",
            r"(\bDROP\s+TABLE\b)",
            r"(\bINSERT\s+INTO\b)",
            r"(\bDELETE\s+FROM\b)",
            r"(\bUPDATE\s+.*\s+SET\b)",
            r"(\bEXEC\s*\()",
            r"(\bSCRIPT\b)",
            r"(--|\#|\/\*|\*\/)",
            r"(\bxp_\w+\b)",
            r"(\bsp_\w+\b)"
        ]
        
        # XSS patterns
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"onmouseover\s*=",
            r"onfocus\s*=",
            r"onblur\s*=",
            r"onchange\s*=",
            r"onsubmit\s*=",
            r"onreset\s*=",
            r"onselect\s*=",
            r"onkeydown\s*=",
            r"onkeyup\s*=",
            r"onkeypress\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<form[^>]*>",
            r"<input[^>]*>",
            r"<textarea[^>]*>",
            r"<select[^>]*>",
            r"<option[^>]*>",
            r"<button[^>]*>"
        ]
    
    def sanitize_input(self, input_data: Any) -> Any:
        """Sanitize input data to prevent XSS and injection attacks"""
        if isinstance(input_data, str):
            return self._sanitize_string(input_data)
        elif isinstance(input_data, dict):
            return {key: self.sanitize_input(value) for key, value in input_data.items()}
        elif isinstance(input_data, list):
            return [self.sanitize_input(item) for item in input_data]
        else:
            return input_data
    
    def _sanitize_string(self, text: str) -> str:
        """Sanitize a string input"""
        if not text:
            return text
        
        # HTML escape
        text = html.escape(text, quote=True)
        
        # Remove potential XSS
        for pattern in self.xss_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove potential SQL injection
        for pattern in self.sql_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Remove control characters except newlines and tabs
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        return text.strip()
    
    def sanitize_html(self, html_content: str) -> str:
        """Sanitize HTML content while preserving allowed tags"""
        if not html_content:
            return html_content
        
        # Use bleach to sanitize HTML
        cleaned = bleach.clean(
            html_content,
            tags=self.allowed_tags,
            attributes=self.allowed_attributes,
            strip=True
        )
        
        return cleaned
    
    def validate_email(self, email: str) -> bool:
        """Validate email format"""
        if not email:
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def validate_username(self, username: str) -> bool:
        """Validate username format"""
        if not username:
            return False
        
        # Username should be 3-50 characters, alphanumeric and underscores only
        pattern = r'^[a-zA-Z0-9_]{3,50}$'
        return bool(re.match(pattern, username))
    
    def validate_url(self, url: str) -> bool:
        """Validate URL format"""
        if not url:
            return False
        
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def validate_ip_address(self, ip: str) -> bool:
        """Validate IP address format"""
        if not ip:
            return False
        
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def detect_sql_injection(self, text: str) -> bool:
        """Detect potential SQL injection in text"""
        if not text:
            return False
        
        text_lower = text.lower()
        for pattern in self.sql_patterns:
            if re.search(pattern, text_lower):
                logger.warning(f"Potential SQL injection detected: {text[:100]}...")
                return True
        
        return False
    
    def detect_xss(self, text: str) -> bool:
        """Detect potential XSS in text"""
        if not text:
            return False
        
        for pattern in self.xss_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Potential XSS detected: {text[:100]}...")
                return True
        
        return False
    
    def validate_file_upload(self, filename: str, content_type: str, max_size: int) -> Dict[str, Any]:
        """Validate file upload"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check filename
        if not filename:
            result["valid"] = False
            result["errors"].append("Filename is required")
            return result
        
        # Check for path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            result["valid"] = False
            result["errors"].append("Invalid filename")
            return result
        
        # Check file extension
        allowed_extensions = {'.txt', '.md', '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp'}
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        if f'.{file_ext}' not in allowed_extensions:
            result["valid"] = False
            result["errors"].append(f"File type .{file_ext} not allowed")
        
        # Check content type
        allowed_types = {
            'text/plain', 'text/markdown', 'application/pdf',
            'image/jpeg', 'image/png', 'image/gif', 'image/webp'
        }
        if content_type not in allowed_types:
            result["valid"] = False
            result["errors"].append(f"Content type {content_type} not allowed")
        
        # Check file size
        if max_size > 10 * 1024 * 1024:  # 10MB
            result["warnings"].append("File size exceeds recommended limit")
        
        return result
    
    def generate_csrf_token(self) -> str:
        """Generate CSRF token"""
        import secrets
        return secrets.token_urlsafe(32)
    
    def validate_csrf_token(self, token: str, session_token: str) -> bool:
        """Validate CSRF token"""
        return token == session_token and len(token) > 0
    
    def check_rate_limit(self, identifier: str, requests: List[float], limit: int, window: int) -> bool:
        """Check if rate limit is exceeded"""
        now = time.time()
        # Remove requests outside the window
        valid_requests = [req for req in requests if now - req < window]
        
        return len(valid_requests) < limit
    
    def validate_json_input(self, data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
        """Validate JSON input with required fields"""
        result = {
            "valid": True,
            "errors": [],
            "data": data
        }
        
        # Check required fields
        for field in required_fields:
            if field not in data:
                result["valid"] = False
                result["errors"].append(f"Required field '{field}' is missing")
        
        # Sanitize data
        result["data"] = self.sanitize_input(data)
        
        return result

# Global security manager instance
security_manager = SecurityManager()

# Convenience functions
def validate_input(input_data: Any) -> Any:
    """Validate and sanitize input data"""
    return security_manager.sanitize_input(input_data)

def sanitize_input(input_data: Any) -> Any:
    """Sanitize input data"""
    return security_manager.sanitize_input(input_data)

def validate_email(email: str) -> bool:
    """Validate email format"""
    return security_manager.validate_email(email)

def validate_username(username: str) -> bool:
    """Validate username format"""
    return security_manager.validate_username(username)

def detect_sql_injection(text: str) -> bool:
    """Detect potential SQL injection"""
    return security_manager.detect_sql_injection(text)

def detect_xss(text: str) -> bool:
    """Detect potential XSS"""
    return security_manager.detect_xss(text)