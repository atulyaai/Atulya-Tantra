"""
Password Management for Atulya Tantra AGI
Password hashing, verification, and strength validation
"""

import re
import bcrypt
from typing import Dict, Any, List
from enum import Enum
from dataclasses import dataclass

from ..config.logging import get_logger
from ..config.exceptions import ValidationError

logger = get_logger(__name__)


class PasswordStrength(str, Enum):
    """Password strength levels"""
    VERY_WEAK = "very_weak"
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


@dataclass
class PasswordValidationResult:
    """Password validation result"""
    is_valid: bool
    strength: PasswordStrength
    score: int
    issues: List[str]
    suggestions: List[str]


class PasswordManager:
    """Password management utilities"""
    
    def __init__(self):
        self.min_length = 8
        self.max_length = 128
        self.require_uppercase = True
        self.require_lowercase = True
        self.require_digits = True
        self.require_special_chars = True
        self.forbidden_patterns = [
            r'password',
            r'123456',
            r'qwerty',
            r'admin',
            r'user',
            r'login'
        ]
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        try:
            # Generate salt
            salt = bcrypt.gensalt()
            
            # Hash password
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            
            logger.debug("Password hashed successfully")
            return hashed.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error hashing password: {e}")
            raise ValidationError("Failed to hash password")
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            is_valid = bcrypt.checkpw(
                password.encode('utf-8'),
                hashed.encode('utf-8')
            )
            
            logger.debug(f"Password verification: {'success' if is_valid else 'failed'}")
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False
    
    def validate_password_strength(self, password: str) -> PasswordValidationResult:
        """Validate password strength"""
        issues = []
        suggestions = []
        score = 0
        
        # Length check
        if len(password) < self.min_length:
            issues.append(f"Password must be at least {self.min_length} characters long")
            suggestions.append("Use a longer password")
        else:
            score += 1
            
        if len(password) > self.max_length:
            issues.append(f"Password must be no more than {self.max_length} characters long")
            suggestions.append("Use a shorter password")
        
        # Character type checks
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            issues.append("Password must contain at least one uppercase letter")
            suggestions.append("Add uppercase letters")
        else:
            score += 1
            
        if self.require_lowercase and not re.search(r'[a-z]', password):
            issues.append("Password must contain at least one lowercase letter")
            suggestions.append("Add lowercase letters")
        else:
            score += 1
            
        if self.require_digits and not re.search(r'\d', password):
            issues.append("Password must contain at least one digit")
            suggestions.append("Add numbers")
        else:
            score += 1
            
        if self.require_special_chars and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            issues.append("Password must contain at least one special character")
            suggestions.append("Add special characters like !@#$%^&*")
        else:
            score += 1
        
        # Pattern checks
        for pattern in self.forbidden_patterns:
            if re.search(pattern, password, re.IGNORECASE):
                issues.append(f"Password contains forbidden pattern: {pattern}")
                suggestions.append("Avoid common patterns")
                score -= 1
        
        # Additional strength checks
        if len(password) >= 12:
            score += 1
        if len(set(password)) >= len(password) * 0.7:  # 70% unique characters
            score += 1
        if not re.search(r'(.)\1{2,}', password):  # No repeated characters
            score += 1
        
        # Determine strength
        if score <= 1:
            strength = PasswordStrength.VERY_WEAK
        elif score <= 2:
            strength = PasswordStrength.WEAK
        elif score <= 4:
            strength = PasswordStrength.MEDIUM
        elif score <= 6:
            strength = PasswordStrength.STRONG
        else:
            strength = PasswordStrength.VERY_STRONG
        
        is_valid = len(issues) == 0 and strength in [PasswordStrength.MEDIUM, PasswordStrength.STRONG, PasswordStrength.VERY_STRONG]
        
        return PasswordValidationResult(
            is_valid=is_valid,
            strength=strength,
            score=score,
            issues=issues,
            suggestions=suggestions
        )
    
    def generate_secure_password(self, length: int = 16) -> str:
        """Generate a secure random password"""
        import secrets
        import string
        
        try:
            # Character sets
            lowercase = string.ascii_lowercase
            uppercase = string.ascii_uppercase
            digits = string.digits
            special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            
            # Ensure at least one character from each required set
            password = [
                secrets.choice(lowercase),
                secrets.choice(uppercase),
                secrets.choice(digits),
                secrets.choice(special)
            ]
            
            # Fill remaining length
            all_chars = lowercase + uppercase + digits + special
            for _ in range(length - 4):
                password.append(secrets.choice(all_chars))
            
            # Shuffle the password
            secrets.SystemRandom().shuffle(password)
            
            generated_password = ''.join(password)
            
            logger.debug("Secure password generated")
            return generated_password
            
        except Exception as e:
            logger.error(f"Error generating secure password: {e}")
            raise ValidationError("Failed to generate secure password")
    
    def check_password_breach(self, password: str) -> bool:
        """Check if password has been breached (simplified implementation)"""
        # In a real implementation, this would check against known breach databases
        # For now, we'll just check against common weak passwords
        common_passwords = [
            "password", "123456", "123456789", "qwerty", "abc123",
            "password123", "admin", "letmein", "welcome", "monkey"
        ]
        
        return password.lower() in common_passwords


# Global password manager instance
_password_manager = None


def get_password_manager() -> PasswordManager:
    """Get global password manager instance"""
    global _password_manager
    if _password_manager is None:
        _password_manager = PasswordManager()
    return _password_manager


# Convenience functions
def hash_password(password: str) -> str:
    """Hash password"""
    manager = get_password_manager()
    return manager.hash_password(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify password"""
    manager = get_password_manager()
    return manager.verify_password(password, hashed)


def validate_password_strength(password: str) -> PasswordValidationResult:
    """Validate password strength"""
    manager = get_password_manager()
    return manager.validate_password_strength(password)


def generate_secure_password(length: int = 16) -> str:
    """Generate secure password"""
    manager = get_password_manager()
    return manager.generate_secure_password(length)


# Export public API
__all__ = [
    "PasswordStrength",
    "PasswordValidationResult",
    "PasswordManager",
    "get_password_manager",
    "hash_password",
    "verify_password",
    "validate_password_strength",
    "generate_secure_password"
]