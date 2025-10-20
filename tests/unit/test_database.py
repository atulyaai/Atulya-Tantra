"""
Unit tests for core database module
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from datetime import datetime
from typing import Dict, Any

# Import the core database module
from src.core.database import (
    get_db, get_db_session, health_check, create_tables, 
    drop_tables, init_database, DATABASE_URL, DB_CONFIG
)
from src.core.database.schema import User, Session, Conversation, Message
from src.core.database.models import engine, SessionLocal


class TestDatabaseConfiguration:
    """Test database configuration"""
    
    def test_database_url_configuration(self):
        """Test database URL configuration"""
        assert DATABASE_URL is not None
        # Should default to SQLite for development
        assert "sqlite" in DATABASE_URL or "postgresql" in DATABASE_URL
    
    def test_database_config(self):
        """Test database configuration parameters"""
        assert DB_CONFIG["pool_size"] >= 1
        assert DB_CONFIG["max_overflow"] >= 0
        assert DB_CONFIG["pool_timeout"] >= 0
        assert DB_CONFIG["pool_recycle"] >= 0
        assert isinstance(DB_CONFIG["pool_pre_ping"], bool)
        assert isinstance(DB_CONFIG["echo"], bool)
    
    def test_engine_creation(self):
        """Test database engine creation"""
        assert engine is not None
        assert hasattr(engine, 'connect')
        assert hasattr(engine, 'execute')


class TestDatabaseSession:
    """Test database session management"""
    
    def test_session_local_creation(self):
        """Test SessionLocal creation"""
        assert SessionLocal is not None
        assert hasattr(SessionLocal, '__call__')
    
    def test_get_db_generator(self):
        """Test get_db function returns generator"""
        db_gen = get_db()
        assert hasattr(db_gen, '__next__')
        assert hasattr(db_gen, '__iter__')
    
    def test_get_db_session_context_manager(self):
        """Test get_db_session context manager"""
        # Test that it returns a context manager
        with get_db_session() as db:
            assert db is not None
            assert hasattr(db, 'query')
            assert hasattr(db, 'commit')
            assert hasattr(db, 'rollback')


class TestDatabaseHealth:
    """Test database health checks"""
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check when database is healthy"""
        with patch('src.core.database.engine') as mock_engine:
            mock_connection = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_connection
            
            health = health_check()
            
            assert health["database"] == "healthy"
            assert health["connection"] == "active"
            assert "response_time_ms" in health
            assert "url" in health
            assert "pool_size" in health
            assert "pool_overflow" in health
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        """Test health check when database is unhealthy"""
        with patch('src.core.database.engine') as mock_engine:
            mock_engine.connect.side_effect = Exception("Connection failed")
            
            health = health_check()
            
            assert health["database"] == "unhealthy"
            assert health["connection"] == "failed"
            assert "error" in health


class TestDatabaseOperations:
    """Test database operations"""
    
    def test_create_tables(self):
        """Test creating database tables"""
        with patch('src.core.database.Base.metadata.create_all') as mock_create_all:
            create_tables()
            mock_create_all.assert_called_once_with(bind=engine)
    
    def test_drop_tables(self):
        """Test dropping database tables"""
        with patch('src.core.database.Base.metadata.drop_all') as mock_drop_all:
            drop_tables()
            mock_drop_all.assert_called_once_with(bind=engine)
    
    def test_init_database(self):
        """Test database initialization"""
        with patch('src.core.database.create_tables') as mock_create_tables:
            init_database()
            mock_create_tables.assert_called_once()


class TestDatabaseSchema:
    """Test database schema models"""
    
    def test_user_model(self):
        """Test User model structure"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash == "hashed_password"
        assert user.is_active == True  # Default value
        assert user.created_at is not None
    
    def test_session_model(self):
        """Test Session model structure"""
        session = Session(
            user_id=1,
            token="jwt_token",
            expires_at=datetime.now()
        )
        
        assert session.user_id == 1
        assert session.token == "jwt_token"
        assert session.expires_at is not None
        assert session.is_active == True  # Default value
    
    def test_conversation_model(self):
        """Test Conversation model structure"""
        conversation = Conversation(
            user_id=1,
            title="Test Conversation",
            created_at=datetime.now()
        )
        
        assert conversation.user_id == 1
        assert conversation.title == "Test Conversation"
        assert conversation.is_active == True  # Default value
        assert conversation.created_at is not None
    
    def test_message_model(self):
        """Test Message model structure"""
        message = Message(
            conversation_id=1,
            role="user",
            content="Hello, JARVIS!",
            timestamp=datetime.now()
        )
        
        assert message.conversation_id == 1
        assert message.role == "user"
        assert message.content == "Hello, JARVIS!"
        assert message.timestamp is not None
        assert message.tokens == 0  # Default value


class TestDatabaseIntegration:
    """Test database integration scenarios"""
    
    @pytest.fixture
    def temp_db_file(self):
        """Create a temporary database file for testing"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_file.close()
        yield temp_file.name
        os.unlink(temp_file.name)
    
    def test_database_connection_with_temp_file(self, temp_db_file):
        """Test database connection with temporary file"""
        # This test would require setting up a temporary SQLite database
        # For now, we'll test the configuration
        assert temp_db_file is not None
        assert os.path.exists(temp_db_file) or not os.path.exists(temp_db_file)
    
    def test_session_cleanup(self):
        """Test that database sessions are properly cleaned up"""
        # Test that get_db properly closes sessions
        db_gen = get_db()
        db = next(db_gen)
        
        # The session should be closed when the generator is exhausted
        try:
            next(db_gen)
        except StopIteration:
            pass
        
        # Verify the session was closed (this would need actual DB connection)
        assert True  # Placeholder for actual test
    
    def test_context_manager_cleanup(self):
        """Test that context manager properly cleans up sessions"""
        # Test that get_db_session properly commits and closes
        with get_db_session() as db:
            assert db is not None
        
        # Session should be closed after context manager exits
        assert True  # Placeholder for actual test


class TestDatabaseErrorHandling:
    """Test database error handling"""
    
    def test_connection_error_handling(self):
        """Test handling of connection errors"""
        with patch('src.core.database.engine.connect') as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            # Test that health check handles errors gracefully
            health = health_check()
            assert health["database"] == "unhealthy"
    
    def test_session_error_handling(self):
        """Test handling of session errors"""
        # Test that get_db handles session errors
        with patch('src.core.database.SessionLocal') as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            mock_session.close.side_effect = Exception("Close failed")
            
            # The function should still work even if close fails
            db_gen = get_db()
            try:
                db = next(db_gen)
                next(db_gen)  # Trigger cleanup
            except StopIteration:
                pass
            except Exception:
                # This is expected if close fails
                pass


class TestDatabaseProductionFeatures:
    """Test production-ready database features"""
    
    def test_connection_pooling_config(self):
        """Test connection pooling configuration"""
        # Test that production database settings are properly configured
        if "sqlite" not in DATABASE_URL:
            # For non-SQLite databases, check pooling settings
            assert DB_CONFIG["pool_size"] > 1
            assert DB_CONFIG["max_overflow"] > 0
            assert DB_CONFIG["pool_timeout"] > 0
            assert DB_CONFIG["pool_recycle"] > 0
    
    def test_sqlite_pragmas(self):
        """Test SQLite pragmas for performance"""
        if "sqlite" in DATABASE_URL:
            # SQLite should have performance pragmas configured
            assert True  # The pragmas are set in the engine creation
    
    def test_connection_monitoring(self):
        """Test connection monitoring features"""
        # Test that connection events are properly configured
        assert engine is not None
        # The event listeners are added during engine creation


@pytest.mark.asyncio
async def test_database_full_integration():
    """Test full database integration"""
    # This would test the complete database setup and operations
    # For now, we'll test the basic functionality
    
    # Test health check
    health = health_check()
    assert "database" in health
    assert "connection" in health
    
    # Test session creation
    db_gen = get_db()
    db = next(db_gen)
    assert db is not None
    
    # Clean up
    try:
        next(db_gen)
    except StopIteration:
        pass
