"""
Security Management for Atulya Tantra AGI
Input validation, sanitization, and security controls
"""

import re
import html
import secrets
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from dataclasses import dataclass

from ..config.logging import get_logger
from ..config.exceptions import SecurityViolation, ValidationError

logger = get_logger(__name__)


class SecurityLevel(str, Enum):
    """Security levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityViolation:
    """Security violation details"""
    violation_type: str
    severity: SecurityLevel
    message: str
    details: Dict[str, Any] = None


class SecurityManager:
    """Security management utilities"""
    
    def __init__(self):
        self.max_input_length = 10000
        self.allowed_html_tags = {'b', 'i', 'em', 'strong', 'p', 'br', 'code', 'pre'}
        self.suspicious_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>',
            r'<link[^>]*>',
            r'<meta[^>]*>',
            r'<style[^>]*>.*?</style>'
        ]
    
    def validate_input(self, input_data: Any, input_type: str = "text") -> bool:
        """Validate input data"""
        try:
            if input_type == "text":
                return self._validate_text(input_data)
            elif input_type == "email":
                return self._validate_email(input_data)
            elif input_type == "url":
                return self._validate_url(input_data)
            elif input_type == "json":
                return self._validate_json(input_data)
            else:
                return True
                
        except Exception as e:
            logger.error(f"Error validating input: {e}")
            return False
    
    def _validate_text(self, text: str) -> bool:
        """Validate text input"""
        if not isinstance(text, str):
            return False
        
        if len(text) > self.max_input_length:
            raise SecurityViolation(
                violation_type="input_length",
                severity=SecurityLevel.MEDIUM,
                message="Input too long"
            )
        
        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                raise SecurityViolation(
                    violation_type="suspicious_content",
                    severity=SecurityLevel.HIGH,
                    message="Suspicious content detected"
                )
        
        return True
    
    def _validate_email(self, email: str) -> bool:
        """Validate email input"""
        if not isinstance(email, str):
            return False
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise SecurityViolation(
                violation_type="invalid_email",
                severity=SecurityLevel.MEDIUM,
                message="Invalid email format"
            )
        
        return True
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL input"""
        if not isinstance(url, str):
            return False
        
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, url):
            raise SecurityViolation(
                violation_type="invalid_url",
                severity=SecurityLevel.MEDIUM,
                message="Invalid URL format"
            )
        
        return True
    
    def _validate_json(self, json_data: str) -> bool:
        """Validate JSON input"""
        try:
            import json
            json.loads(json_data)
            return True
        except json.JSONDecodeError:
            raise SecurityViolation(
                violation_type="invalid_json",
                severity=SecurityLevel.MEDIUM,
                message="Invalid JSON format"
            )
    
    def sanitize_input(self, input_data: str, allow_html: bool = False) -> str:
        """Sanitize input data"""
        try:
            # HTML escape
            sanitized = html.escape(input_data)
            
            if allow_html:
                # Allow specific HTML tags
                sanitized = self._clean_html(sanitized)
            
            return sanitized
            
        except Exception as e:
            logger.error(f"Error sanitizing input: {e}")
            return ""
    
    def _clean_html(self, html_content: str) -> str:
        """Clean HTML content"""
        # Remove dangerous tags
        for tag in ['script', 'iframe', 'object', 'embed', 'link', 'meta', 'style']:
            pattern = f'<{tag}[^>]*>.*?</{tag}>'
            html_content = re.sub(pattern, '', html_content, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove dangerous attributes
        pattern = r'\s*on\w+\s*=\s*["\'][^"\']*["\']'
        html_content = re.sub(pattern, '', html_content, flags=re.IGNORECASE)
        
        return html_content
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate secure random token"""
        try:
            return secrets.token_urlsafe(length)
        except Exception as e:
            logger.error(f"Error generating secure token: {e}")
            raise SecurityViolation(
                violation_type="token_generation_failed",
                severity=SecurityLevel.CRITICAL,
                message="Failed to generate secure token"
            )
    
    def check_rate_limit(self, identifier: str, limit: int, window: int) -> bool:
        """Check rate limit (simplified implementation)"""
        # In a real implementation, this would use Redis or similar
        # For now, we'll just return True
        return True
    
    def validate_file_upload(self, filename: str, content_type: str, size: int) -> bool:
        """Validate file upload"""
        try:
            # Check file extension
            allowed_extensions = {'.txt', '.pdf', '.doc', '.docx', '.jpg', '.png', '.gif'}
            file_ext = '.' + filename.split('.')[-1].lower()
            
            if file_ext not in allowed_extensions:
                raise SecurityViolation(
                    violation_type="invalid_file_type",
                    severity=SecurityLevel.MEDIUM,
                    message="File type not allowed"
                )
            
            # Check file size (10MB limit)
            max_size = 10 * 1024 * 1024
            if size > max_size:
                raise SecurityViolation(
                    violation_type="file_too_large",
                    severity=SecurityLevel.MEDIUM,
                    message="File too large"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating file upload: {e}")
            return False


# Global security manager instance
_security_manager = None


def get_security_manager() -> SecurityManager:
    """Get global security manager instance"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


# Convenience functions
def validate_input(input_data: Any, input_type: str = "text") -> bool:
    """Validate input data"""
    manager = get_security_manager()
    return manager.validate_input(input_data, input_type)


def sanitize_input(input_data: str, allow_html: bool = False) -> str:
    """Sanitize input data"""
    manager = get_security_manager()
    return manager.sanitize_input(input_data, allow_html)


def generate_secure_token(length: int = 32) -> str:
    """Generate secure random token"""
    manager = get_security_manager()
    return manager.generate_secure_token(length)


# Export public API
__all__ = [
    "SecurityLevel",
    "SecurityViolation",
    "SecurityManager",
    "get_security_manager",
    "validate_input",
    "sanitize_input",
    "generate_secure_token"
]