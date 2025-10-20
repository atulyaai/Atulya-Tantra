"""
Atulya Tantra - Encryption Utilities
Version: 2.5.0
Provides encryption and decryption utilities for sensitive data
"""

import os
import base64
import hashlib
from typing import Union, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class EncryptionManager:
    """
    Manages encryption and decryption of sensitive data
    """
    
    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize encryption manager
        
        Args:
            key: Encryption key (if None, will generate from environment)
        """
        if key is None:
            key = self._get_key_from_env()
        
        self.key = key
        self.cipher = Fernet(key)
    
    def _get_key_from_env(self) -> bytes:
        """
        Get encryption key from environment variable
        
        Returns:
            Encryption key as bytes
        """
        key_str = os.getenv("ENCRYPTION_KEY")
        if not key_str:
            # Use a default key for development/testing (NOT for production)
            logger.warning("ENCRYPTION_KEY not set, using default key (NOT for production)")
            key_str = "default-dev-key-change-in-production-32-chars"
        
        # If key is base64 encoded, decode it
        try:
            return base64.b64decode(key_str)
        except Exception:
            # If not base64, derive key from string
            return self._derive_key(key_str)
    
    def _derive_key(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """
        Derive encryption key from password using PBKDF2
        
        Args:
            password: Password string
            salt: Salt bytes (if None, will generate)
            
        Returns:
            Derived key as bytes
        """
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, data: Union[str, bytes]) -> str:
        """
        Encrypt data
        
        Args:
            data: Data to encrypt (string or bytes)
            
        Returns:
            Encrypted data as base64 string
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        encrypted_data = self.cipher.encrypt(data)
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data
        
        Args:
            encrypted_data: Encrypted data as base64 string
            
        Returns:
            Decrypted data as string
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted_data = self.cipher.decrypt(encrypted_bytes)
            return decrypted_data.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data")
    
    def encrypt_file(self, file_path: str, output_path: Optional[str] = None) -> str:
        """
        Encrypt file contents
        
        Args:
            file_path: Path to file to encrypt
            output_path: Output path (if None, will overwrite original)
            
        Returns:
            Path to encrypted file
        """
        if output_path is None:
            output_path = file_path + ".encrypted"
        
        with open(file_path, 'rb') as f:
            data = f.read()
        
        encrypted_data = self.cipher.encrypt(data)
        
        with open(output_path, 'wb') as f:
            f.write(encrypted_data)
        
        return output_path
    
    def decrypt_file(self, encrypted_file_path: str, output_path: Optional[str] = None) -> str:
        """
        Decrypt file contents
        
        Args:
            encrypted_file_path: Path to encrypted file
            output_path: Output path (if None, will remove .encrypted extension)
            
        Returns:
            Path to decrypted file
        """
        if output_path is None:
            output_path = encrypted_file_path.replace(".encrypted", "")
        
        with open(encrypted_file_path, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = self.cipher.decrypt(encrypted_data)
        
        with open(output_path, 'wb') as f:
            f.write(decrypted_data)
        
        return output_path


class HashManager:
    """
    Manages hashing operations for passwords and data integrity
    """
    
    @staticmethod
    def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
        """
        Hash password using PBKDF2
        
        Args:
            password: Password to hash
            salt: Salt bytes (if None, will generate)
            
        Returns:
            Tuple of (hash, salt)
        """
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        password_hash = kdf.derive(password.encode())
        return password_hash, salt
    
    @staticmethod
    def verify_password(password: str, password_hash: bytes, salt: bytes) -> bool:
        """
        Verify password against hash
        
        Args:
            password: Password to verify
            password_hash: Stored password hash
            salt: Salt used for hashing
            
        Returns:
            True if password is correct, False otherwise
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        computed_hash = kdf.derive(password.encode())
        return computed_hash == password_hash
    
    @staticmethod
    def hash_data(data: Union[str, bytes], algorithm: str = "sha256") -> str:
        """
        Hash data using specified algorithm
        
        Args:
            data: Data to hash
            algorithm: Hash algorithm (sha256, sha512, md5)
            
        Returns:
            Hash as hexadecimal string
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        if algorithm == "sha256":
            hash_obj = hashlib.sha256(data)
        elif algorithm == "sha512":
            hash_obj = hashlib.sha512(data)
        elif algorithm == "md5":
            hash_obj = hashlib.md5(data)
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        
        return hash_obj.hexdigest()
    
    @staticmethod
    def verify_data_integrity(data: Union[str, bytes], expected_hash: str, algorithm: str = "sha256") -> bool:
        """
        Verify data integrity using hash
        
        Args:
            data: Data to verify
            expected_hash: Expected hash value
            algorithm: Hash algorithm used
            
        Returns:
            True if data integrity is verified, False otherwise
        """
        computed_hash = HashManager.hash_data(data, algorithm)
        return computed_hash == expected_hash


class SecureRandom:
    """
    Provides secure random number generation
    """
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """
        Generate secure random token
        
        Args:
            length: Token length in bytes
            
        Returns:
            Random token as hexadecimal string
        """
        random_bytes = os.urandom(length)
        return random_bytes.hex()
    
    @staticmethod
    def generate_salt(length: int = 16) -> bytes:
        """
        Generate secure random salt
        
        Args:
            length: Salt length in bytes
            
        Returns:
            Random salt as bytes
        """
        return os.urandom(length)
    
    @staticmethod
    def generate_key(length: int = 32) -> bytes:
        """
        Generate secure random key
        
        Args:
            length: Key length in bytes
            
        Returns:
            Random key as bytes
        """
        return os.urandom(length)


# Global encryption manager instance
encryption_manager = EncryptionManager()


def encrypt_data(data: Union[str, bytes]) -> str:
    """
    Encrypt data using global encryption manager
    
    Args:
        data: Data to encrypt
        
    Returns:
        Encrypted data as base64 string
    """
    return encryption_manager.encrypt(data)


def decrypt_data(encrypted_data: str) -> str:
    """
    Decrypt data using global encryption manager
    
    Args:
        encrypted_data: Encrypted data as base64 string
        
    Returns:
        Decrypted data as string
    """
    return encryption_manager.decrypt(encrypted_data)


def hash_password(password: str) -> tuple[bytes, bytes]:
    """
    Hash password using global hash manager
    
    Args:
        password: Password to hash
        
    Returns:
        Tuple of (hash, salt)
    """
    return HashManager.hash_password(password)


def verify_password(password: str, password_hash: bytes, salt: bytes) -> bool:
    """
    Verify password using global hash manager
    
    Args:
        password: Password to verify
        password_hash: Stored password hash
        salt: Salt used for hashing
        
    Returns:
        True if password is correct, False otherwise
    """
    return HashManager.verify_password(password, password_hash, salt)
