"""
Database implementations for Atulya Tantra AGI
SQLite, PostgreSQL, and JSON file backends
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json
import sqlite3
from pathlib import Path

from ..config.settings import settings, DatabaseType
from ..config.exceptions import DatabaseError, RecordNotFoundError, DuplicateRecordError


class DatabaseInterface(ABC):
    """Abstract base class for database implementations"""
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish database connection"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close database connection"""
        pass
    
    @abstractmethod
    async def create_tables(self) -> None:
        """Create database tables"""
        pass
    
    @abstractmethod
    async def insert(self, table: str, data: Dict[str, Any]) -> str:
        """Insert a record and return ID"""
        pass
    
    @abstractmethod
    async def get_by_id(self, table: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Get record by ID"""
        pass
    
    @abstractmethod
    async def get_by_field(self, table: str, field: str, value: Any) -> Optional[Dict[str, Any]]:
        """Get record by field value"""
        pass
    
    @abstractmethod
    async def update(self, table: str, record_id: str, data: Dict[str, Any]) -> bool:
        """Update record by ID"""
        pass
    
    @abstractmethod
    async def delete(self, table: str, record_id: str) -> bool:
        """Delete record by ID"""
        pass
    
    @abstractmethod
    async def list(self, table: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List records with pagination"""
        pass
    
    @abstractmethod
    async def search(self, table: str, query: str, fields: List[str]) -> List[Dict[str, Any]]:
        """Search records"""
        pass
    
    @abstractmethod
    async def count(self, table: str) -> int:
        """Count records in table"""
        pass
    
    @abstractmethod
    async def execute_raw(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute raw SQL query"""
        pass


class SQLiteDatabase(DatabaseInterface):
    """SQLite database implementation"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.sqlite_path
        self.connection: Optional[sqlite3.Connection] = None
    
    async def connect(self) -> None:
        """Establish SQLite connection"""
        try:
            # Ensure directory exists
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
            self.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self.connection.row_factory = sqlite3.Row
            await self.create_tables()
        except Exception as e:
            raise DatabaseError(f"Failed to connect to SQLite: {e}")
    
    async def disconnect(self) -> None:
        """Close SQLite connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    async def create_tables(self) -> None:
        """Create database tables"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        tables = {
            'users': '''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    hashed_password TEXT,
                    roles TEXT DEFAULT 'user',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'conversations': '''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''',
            'messages': '''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tokens_used INTEGER DEFAULT 0,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            ''',
            'sessions': '''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    refresh_token TEXT UNIQUE,
                    expires_at TIMESTAMP NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''',
            'agent_logs': '''
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id TEXT PRIMARY KEY,
                    agent_type TEXT NOT NULL,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms INTEGER,
                    result TEXT,
                    error TEXT,
                    user_id TEXT,
                    conversation_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            ''',
            'memories': '''
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding_vector TEXT,
                    metadata TEXT,
                    importance_score INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''',
            'knowledge_nodes': '''
                CREATE TABLE IF NOT EXISTS knowledge_nodes (
                    id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'knowledge_edges': '''
                CREATE TABLE IF NOT EXISTS knowledge_edges (
                    id TEXT PRIMARY KEY,
                    source_node_id TEXT NOT NULL,
                    target_node_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    weight INTEGER DEFAULT 1,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_node_id) REFERENCES knowledge_nodes (id),
                    FOREIGN KEY (target_node_id) REFERENCES knowledge_nodes (id)
                )
            ''',
            'system_metrics': '''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id TEXT PRIMARY KEY,
                    metric_name TEXT NOT NULL,
                    metric_value INTEGER NOT NULL,
                    metric_unit TEXT,
                    tags TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'api_logs': '''
                CREATE TABLE IF NOT EXISTS api_logs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    duration_ms INTEGER,
                    request_size INTEGER,
                    response_size INTEGER,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            '''
        }
        
        cursor = self.connection.cursor()
        for table_name, sql in tables.items():
            cursor.execute(sql)
        self.connection.commit()
    
    async def insert(self, table: str, data: Dict[str, Any]) -> str:
        """Insert a record and return ID"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        # Generate ID if not provided
        record_id = data.get('id', f"{table}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}")
        data['id'] = record_id
        
        # Add timestamps
        if 'created_at' not in data:
            data['created_at'] = datetime.now().isoformat()
        data['updated_at'] = datetime.now().isoformat()
        
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, list(data.values()))
            self.connection.commit()
            return record_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise DuplicateRecordError(table, "unique constraint", data)
            raise DatabaseError(f"Insert failed: {e}")
    
    async def get_by_id(self, table: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Get record by ID"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        cursor = self.connection.cursor()
        cursor.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    async def get_by_field(self, table: str, field: str, value: Any) -> Optional[Dict[str, Any]]:
        """Get record by field value"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        cursor = self.connection.cursor()
        cursor.execute(f"SELECT * FROM {table} WHERE {field} = ?", (value,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    async def update(self, table: str, record_id: str, data: Dict[str, Any]) -> bool:
        """Update record by ID"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        # Add updated timestamp
        data['updated_at'] = datetime.now().isoformat()
        
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE id = ?"
        
        cursor = self.connection.cursor()
        cursor.execute(sql, list(data.values()) + [record_id])
        self.connection.commit()
        
        return cursor.rowcount > 0
    
    async def delete(self, table: str, record_id: str) -> bool:
        """Delete record by ID"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        cursor = self.connection.cursor()
        cursor.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
        self.connection.commit()
        
        return cursor.rowcount > 0
    
    async def list(self, table: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List records with pagination"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        cursor = self.connection.cursor()
        cursor.execute(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    async def search(self, table: str, query: str, fields: List[str]) -> List[Dict[str, Any]]:
        """Search records"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        # Simple LIKE search across specified fields
        where_clause = " OR ".join([f"{field} LIKE ?" for field in fields])
        sql = f"SELECT * FROM {table} WHERE {where_clause}"
        
        search_term = f"%{query}%"
        params = [search_term] * len(fields)
        
        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    async def count(self, table: str) -> int:
        """Count records in table"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        cursor = self.connection.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]
    
    async def execute_raw(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute raw SQL query"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        cursor = self.connection.cursor()
        if params:
            cursor.execute(query, list(params.values()))
        else:
            cursor.execute(query)
        
        self.connection.commit()
        
        if query.strip().upper().startswith('SELECT'):
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        else:
            return cursor.rowcount


class PostgreSQLDatabase(DatabaseInterface):
    """PostgreSQL database implementation"""
    
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string or settings.database_url
        self.connection = None
    
    async def connect(self) -> None:
        """Establish PostgreSQL connection"""
        try:
            import asyncpg
            self.connection = await asyncpg.connect(self.connection_string)
            await self.create_tables()
        except ImportError:
            raise DatabaseError("asyncpg not installed. Install with: pip install asyncpg")
        except Exception as e:
            raise DatabaseError(f"Failed to connect to PostgreSQL: {e}")
    
    async def disconnect(self) -> None:
        """Close PostgreSQL connection"""
        if self.connection:
            await self.connection.close()
            self.connection = None
    
    async def create_tables(self) -> None:
        """Create database tables"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        tables = {
            'users': '''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    hashed_password TEXT,
                    roles TEXT DEFAULT 'user',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'conversations': '''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''',
            'messages': '''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tokens_used INTEGER DEFAULT 0,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            ''',
            'sessions': '''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    refresh_token TEXT UNIQUE,
                    expires_at TIMESTAMP NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''',
            'agent_logs': '''
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id TEXT PRIMARY KEY,
                    agent_type TEXT NOT NULL,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms INTEGER,
                    result TEXT,
                    error TEXT,
                    user_id TEXT,
                    conversation_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            ''',
            'memories': '''
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding_vector TEXT,
                    metadata TEXT,
                    importance_score INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''',
            'knowledge_nodes': '''
                CREATE TABLE IF NOT EXISTS knowledge_nodes (
                    id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'knowledge_edges': '''
                CREATE TABLE IF NOT EXISTS knowledge_edges (
                    id TEXT PRIMARY KEY,
                    source_node_id TEXT NOT NULL,
                    target_node_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    weight INTEGER DEFAULT 1,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_node_id) REFERENCES knowledge_nodes (id),
                    FOREIGN KEY (target_node_id) REFERENCES knowledge_nodes (id)
                )
            ''',
            'system_metrics': '''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id TEXT PRIMARY KEY,
                    metric_name TEXT NOT NULL,
                    metric_value INTEGER NOT NULL,
                    metric_unit TEXT,
                    tags TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'api_logs': '''
                CREATE TABLE IF NOT EXISTS api_logs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    duration_ms INTEGER,
                    request_size INTEGER,
                    response_size INTEGER,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            '''
        }
        
        for table_name, sql in tables.items():
            await self.connection.execute(sql)
    
    async def insert(self, table: str, data: Dict[str, Any]) -> str:
        """Insert a record and return ID"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        # Generate ID if not provided
        record_id = data.get('id', f"{table}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}")
        data['id'] = record_id
        
        # Add timestamps
        if 'created_at' not in data:
            data['created_at'] = datetime.now().isoformat()
        data['updated_at'] = datetime.now().isoformat()
        
        columns = ', '.join(data.keys())
        placeholders = ', '.join([f"${i+1}" for i in range(len(data))])
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"
        
        try:
            result = await self.connection.fetchval(sql, *data.values())
            return result
        except Exception as e:
            if "duplicate key" in str(e).lower():
                raise DuplicateRecordError(table, "unique constraint", data)
            raise DatabaseError(f"Insert failed: {e}")
    
    async def get_by_id(self, table: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Get record by ID"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        sql = f"SELECT * FROM {table} WHERE id = $1"
        row = await self.connection.fetchrow(sql, record_id)
        
        if row:
            return dict(row)
        return None
    
    async def get_by_field(self, table: str, field: str, value: Any) -> Optional[Dict[str, Any]]:
        """Get record by field value"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        sql = f"SELECT * FROM {table} WHERE {field} = $1"
        row = await self.connection.fetchrow(sql, value)
        
        if row:
            return dict(row)
        return None
    
    async def update(self, table: str, record_id: str, data: Dict[str, Any]) -> bool:
        """Update record by ID"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        # Add updated timestamp
        data['updated_at'] = datetime.now().isoformat()
        
        set_clause = ', '.join([f"{k} = ${i+2}" for i, k in enumerate(data.keys())])
        sql = f"UPDATE {table} SET {set_clause} WHERE id = $1"
        
        result = await self.connection.execute(sql, record_id, *data.values())
        return result.split()[-1] == '1'
    
    async def delete(self, table: str, record_id: str) -> bool:
        """Delete record by ID"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        result = await self.connection.execute(f"DELETE FROM {table} WHERE id = $1", record_id)
        return result.split()[-1] == '1'
    
    async def list(self, table: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List records with pagination"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        sql = f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT $1 OFFSET $2"
        rows = await self.connection.fetch(sql, limit, offset)
        
        return [dict(row) for row in rows]
    
    async def search(self, table: str, query: str, fields: List[str]) -> List[Dict[str, Any]]:
        """Search records"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        # Simple ILIKE search across specified fields
        where_clause = " OR ".join([f"{field} ILIKE $1" for field in fields])
        sql = f"SELECT * FROM {table} WHERE {where_clause}"
        
        search_term = f"%{query}%"
        
        rows = await self.connection.fetch(sql, search_term)
        return [dict(row) for row in rows]
    
    async def count(self, table: str) -> int:
        """Count records in table"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        result = await self.connection.fetchval(f"SELECT COUNT(*) FROM {table}")
        return result
    
    async def execute_raw(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute raw SQL query"""
        if not self.connection:
            raise DatabaseError("Not connected to database")
        
        if params:
            result = await self.connection.fetch(query, *params.values())
            return [dict(row) for row in result]
        else:
            result = await self.connection.fetch(query)
            return [dict(row) for row in result]


class JSONDatabase(DatabaseInterface):
    """JSON file-based database implementation"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.tables: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self) -> None:
        """Load existing JSON files"""
        try:
            for json_file in self.data_dir.glob("*.json"):
                table_name = json_file.stem
                if json_file.exists():
                    with open(json_file, 'r', encoding='utf-8') as f:
                        self.tables[table_name] = json.load(f)
                else:
                    self.tables[table_name] = {}
        except Exception as e:
            raise DatabaseError(f"Failed to load JSON database: {e}")
    
    async def disconnect(self) -> None:
        """Save all tables to JSON files"""
        try:
            for table_name, data in self.tables.items():
                json_file = self.data_dir / f"{table_name}.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise DatabaseError(f"Failed to save JSON database: {e}")
    
    async def create_tables(self) -> None:
        """Initialize empty tables"""
        tables = ['users', 'conversations', 'messages', 'sessions', 'agent_logs', 
                 'memories', 'knowledge_nodes', 'knowledge_edges', 'system_metrics', 'api_logs']
        for table in tables:
            if table not in self.tables:
                self.tables[table] = {}
    
    async def insert(self, table: str, data: Dict[str, Any]) -> str:
        """Insert a record and return ID"""
        if table not in self.tables:
            self.tables[table] = {}
        
        # Generate ID if not provided
        record_id = data.get('id', f"{table}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}")
        data['id'] = record_id
        
        # Add timestamps
        if 'created_at' not in data:
            data['created_at'] = datetime.now().isoformat()
        data['updated_at'] = datetime.now().isoformat()
        
        # Check for duplicates
        if record_id in self.tables[table]:
            raise DuplicateRecordError(table, "id", record_id)
        
        self.tables[table][record_id] = data
        return record_id
    
    async def get_by_id(self, table: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Get record by ID"""
        if table not in self.tables:
            return None
        
        return self.tables[table].get(record_id)
    
    async def get_by_field(self, table: str, field: str, value: Any) -> Optional[Dict[str, Any]]:
        """Get record by field value"""
        if table not in self.tables:
            return None
        
        for record in self.tables[table].values():
            if record.get(field) == value:
                return record
        
        return None
    
    async def update(self, table: str, record_id: str, data: Dict[str, Any]) -> bool:
        """Update record by ID"""
        if table not in self.tables or record_id not in self.tables[table]:
            return False
        
        # Add updated timestamp
        data['updated_at'] = datetime.now().isoformat()
        
        # Preserve existing data and update
        existing = self.tables[table][record_id]
        existing.update(data)
        
        return True
    
    async def delete(self, table: str, record_id: str) -> bool:
        """Delete record by ID"""
        if table not in self.tables or record_id not in self.tables[table]:
            return False
        
        del self.tables[table][record_id]
        return True
    
    async def list(self, table: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List records with pagination"""
        if table not in self.tables:
            return []
        
        records = list(self.tables[table].values())
        # Sort by created_at descending
        records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return records[offset:offset + limit]
    
    async def search(self, table: str, query: str, fields: List[str]) -> List[Dict[str, Any]]:
        """Search records"""
        if table not in self.tables:
            return []
        
        results = []
        query_lower = query.lower()
        
        for record in self.tables[table].values():
            for field in fields:
                field_value = str(record.get(field, '')).lower()
                if query_lower in field_value:
                    results.append(record)
                    break
        
        return results
    
    async def count(self, table: str) -> int:
        """Count records in table"""
        if table not in self.tables:
            return 0
        
        return len(self.tables[table])
    
    async def execute_raw(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute raw query (not supported in JSON database)"""
        raise DatabaseError("Raw queries not supported in JSON database")


class DatabaseFactory:
    """Factory for creating database instances"""
    
    @staticmethod
    def create_database(db_type: DatabaseType = None) -> DatabaseInterface:
        """Create database instance based on configuration"""
        db_type = db_type or settings.database_type
        
        if db_type == DatabaseType.SQLITE:
            return SQLiteDatabase()
        elif db_type == DatabaseType.POSTGRESQL:
            return PostgreSQLDatabase()
        elif db_type == DatabaseType.JSON:
            return JSONDatabase()
        else:
            raise DatabaseError(f"Unsupported database type: {db_type}")


# Global database instance
_db_instance: Optional[DatabaseInterface] = None


async def get_database() -> DatabaseInterface:
    """Get global database instance"""
    global _db_instance
    
    if _db_instance is None:
        _db_instance = DatabaseFactory.create_database()
        await _db_instance.connect()
    
    return _db_instance


async def close_database() -> None:
    """Close global database connection"""
    global _db_instance
    
    if _db_instance:
        await _db_instance.disconnect()
        _db_instance = None


# Export public API
__all__ = [
    "DatabaseInterface",
    "SQLiteDatabase", 
    "PostgreSQLDatabase",
    "JSONDatabase",
    "DatabaseFactory",
    "get_database",
    "close_database"
]
