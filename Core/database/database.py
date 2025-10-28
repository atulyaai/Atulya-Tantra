"""
Database for Atulya Tantra AGI
Database connection and operations
"""

import sqlite3
from typing import Dict, List, Any, Optional

class Database:
    """Database connection and operations"""
    
    def __init__(self, db_path: str = "tantra.db"):
        self.db_path = db_path
        self.connection = None
    
    def connect(self):
        """Connect to database"""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
    
    def disconnect(self):
        """Disconnect from database"""
        if self.connection:
            self.connection.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute query and return results"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        
        if query.strip().upper().startswith('SELECT'):
            return [dict(row) for row in cursor.fetchall()]
        else:
            self.connection.commit()
            return []
    
    def create_tables(self):
        """Create necessary tables"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                message TEXT NOT NULL,
                response TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        for table in tables:
            self.execute_query(table)