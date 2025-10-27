"""
Password management and security
Handles password hashing, verification, and strength validation
"""

import re
import secrets
import string
from typing import List, Tuple
from passlib.context import CryptContext
from passlib.hash import bcrypt

from ..config.logging import get_logger

logger = get_logger(__name__)

class PasswordManager:
    """Manages password operations and security"""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.min_length = 8
        self.require_uppercase = True
        self.require_lowercase = True
        self.require_digits = True
        self.require_special = True
        self.max_length = 128
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def validate_password_strength(self, password: str) -> Tuple[bool, List[str]]:
        """Validate password strength and return (is_valid, errors)"""
        errors = []
        
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long")
        
        if len(password) > self.max_length:
            errors.append(f"Password must be no more than {self.max_length} characters long")
        
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self.require_lowercase and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.require_digits and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        # Check for common patterns
        if self._is_common_password(password):
            errors.append("Password is too common or predictable")
        
        if self._has_repeating_patterns(password):
            errors.append("Password contains repeating patterns")
        
        return len(errors) == 0, errors
    
    def _is_common_password(self, password: str) -> bool:
        """Check if password is in common passwords list"""
        common_passwords = {
            "password", "123456", "123456789", "qwerty", "abc123",
            "password123", "admin", "letmein", "welcome", "monkey",
            "1234567890", "password1", "qwerty123", "dragon", "master"
        }
        return password.lower() in common_passwords
    
    def _has_repeating_patterns(self, password: str) -> bool:
        """Check for repeating character patterns"""
        # Check for 3+ consecutive identical characters
        if re.search(r'(.)\1{2,}', password):
            return True
        
        # Check for sequential patterns (123, abc, etc.)
        if re.search(r'(?:012|123|234|345|456|567|678|789|890)', password):
            return True
        
        if re.search(r'(?:abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)', password.lower()):
            return True
        
        return False
    
    def generate_secure_password(self, length: int = 16) -> str:
        """Generate a secure random password"""
        if length < self.min_length:
            length = self.min_length
        
        # Character sets
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special = "!@#$%^&*(),.?\":{}|<>"
        
        # Ensure at least one character from each required set
        password = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(digits),
            secrets.choice(special)
        ]
        
        # Fill the rest with random characters
        all_chars = lowercase + uppercase + digits + special
        for _ in range(length - 4):
            password.append(secrets.choice(all_chars))
        
        # Shuffle the password
        secrets.SystemRandom().shuffle(password)
        
        return ''.join(password)
    
    def check_password_breach(self, password: str) -> bool:
        """Check if password has been in a data breach (placeholder)"""
        # In a real implementation, this would check against known breach databases
        # For now, we'll just check against a small local list
        breached_passwords = {
            "password", "123456", "password123", "admin", "qwerty"
        }
        return password.lower() in breached_passwords
    
    def get_password_strength_score(self, password: str) -> int:
        """Get password strength score (0-100)"""
        score = 0
        
        # Length scoring
        if len(password) >= 8:
            score += 20
        if len(password) >= 12:
            score += 10
        if len(password) >= 16:
            score += 10
        
        # Character variety scoring
        if re.search(r'[a-z]', password):
            score += 10
        if re.search(r'[A-Z]', password):
            score += 10
        if re.search(r'\d', password):
            score += 10
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 10
        
        # Bonus for length
        if len(password) > 20:
            score += 10
        
        # Penalty for common patterns
        if self._is_common_password(password):
            score -= 30
        if self._has_repeating_patterns(password):
            score -= 20
        
        return max(0, min(100, score))

# Global password manager instance
password_manager = PasswordManager()

# Convenience functions
def get_password_hash(password: str) -> str:
    """Hash a password"""
    return password_manager.hash_password(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return password_manager.verify_password(plain_password, hashed_password)

def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """Validate password strength"""
    return password_manager.validate_password_strength(password)

def generate_secure_password(length: int = 16) -> str:
    """Generate a secure random password"""
    return password_manager.generate_secure_password(length)

def get_password_strength_score(password: str) -> int:
    """Get password strength score"""
    return password_manager.get_password_strength_score(password)