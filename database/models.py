"""
Database models for Atulya Tantra
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import json
import hashlib

DB_PATH = Path("data/atulya.db")

def get_db():
    """Get database connection"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT,
            model TEXT DEFAULT 'gemma2:2b',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    ''')
    
    # Sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

class User:
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def create(username: str, email: str, password: str) -> Optional[int]:
        """Create new user"""
        conn = get_db()
        cursor = conn.cursor()
        try:
            password_hash = User.hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash)
            )
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            return user_id
        except sqlite3.IntegrityError:
            conn.close()
            return None
    
    @staticmethod
    def authenticate(username: str, password: str) -> Optional[Dict]:
        """Authenticate user"""
        conn = get_db()
        cursor = conn.cursor()
        password_hash = User.hash_password(password)
        
        cursor.execute(
            "SELECT id, username, email FROM users WHERE username = ? AND password_hash = ?",
            (username, password_hash)
        )
        user = cursor.fetchone()
        
        if user:
            # Update last login
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user['id'],)
            )
            conn.commit()
        
        conn.close()
        return dict(user) if user else None
    
    @staticmethod
    def get_by_id(user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, email, created_at, last_login FROM users WHERE id = ?",
            (user_id,)
        )
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None

class Conversation:
    @staticmethod
    def create(user_id: int, title: str = "New Conversation", model: str = "gemma2:2b") -> int:
        """Create new conversation"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (user_id, title, model) VALUES (?, ?, ?)",
            (user_id, title, model)
        )
        conn.commit()
        conv_id = cursor.lastrowid
        conn.close()
        return conv_id
    
    @staticmethod
    def get_by_user(user_id: int, limit: int = 50) -> List[Dict]:
        """Get conversations for user"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit)
        )
        conversations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return conversations
    
    @staticmethod
    def update_title(conv_id: int, title: str):
        """Update conversation title"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, conv_id)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def delete(conv_id: int):
        """Delete conversation"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        conn.commit()
        conn.close()

class Message:
    @staticmethod
    def create(conversation_id: int, role: str, content: str, metadata: Optional[Dict] = None) -> int:
        """Create new message"""
        conn = get_db()
        cursor = conn.cursor()
        metadata_json = json.dumps(metadata) if metadata else None
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, metadata) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, metadata_json)
        )
        
        # Update conversation timestamp
        cursor.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,)
        )
        
        conn.commit()
        msg_id = cursor.lastrowid
        conn.close()
        return msg_id
    
    @staticmethod
    def get_by_conversation(conversation_id: int) -> List[Dict]:
        """Get messages for conversation"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,)
        )
        messages = []
        for row in cursor.fetchall():
            msg = dict(row)
            if msg['metadata']:
                msg['metadata'] = json.loads(msg['metadata'])
            messages.append(msg)
        conn.close()
        return messages

class Session:
    @staticmethod
    def create(user_id: int, session_id: str, expires_at: str) -> str:
        """Create session"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)",
            (session_id, user_id, expires_at)
        )
        conn.commit()
        conn.close()
        return session_id
    
    @staticmethod
    def get(session_id: str) -> Optional[Dict]:
        """Get session"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sessions WHERE id = ? AND expires_at > CURRENT_TIMESTAMP",
            (session_id,)
        )
        session = cursor.fetchone()
        conn.close()
        return dict(session) if session else None
    
    @staticmethod
    def delete(session_id: str):
        """Delete session"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()

