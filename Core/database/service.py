"""
Database Service for Atulya Tantra AGI
High-level database operations
"""

from typing import Dict, List, Any, Optional
from .database import Database

class DatabaseService:
    """High-level database operations"""
    
    def __init__(self, db_path: str = "tantra.db"):
        self.db = Database(db_path)
        self.db.connect()
        self.db.create_tables()
    
    def save_conversation(self, user_id: str, message: str, response: str = None):
        """Save conversation to database"""
        query = """
        INSERT INTO conversations (user_id, message, response)
        VALUES (?, ?, ?)
        """
        self.db.execute_query(query, (user_id, message, response))
    
    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation history for user"""
        query = """
        SELECT * FROM conversations 
        WHERE user_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
        """
        return self.db.execute_query(query, (user_id, limit))
    
    def save_memory(self, user_id: str, key: str, value: str):
        """Save memory to database"""
        query = """
        INSERT INTO memory (user_id, key, value)
        VALUES (?, ?, ?)
        """
        self.db.execute_query(query, (user_id, key, value))
    
    def get_memory(self, user_id: str, key: str) -> Optional[str]:
        """Get memory from database"""
        query = """
        SELECT value FROM memory 
        WHERE user_id = ? AND key = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """
        result = self.db.execute_query(query, (user_id, key))
        return result[0]['value'] if result else None