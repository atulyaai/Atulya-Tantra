"""
Atulya Tantra - Database Module
Version: 2.5.0
Production-ready database configuration and initialization
"""

from sqlalchemy import create_engine, MetaData, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool, QueuePool
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DisconnectionError
import os
import logging
from contextlib import contextmanager
from typing import Generator
import time

logger = logging.getLogger(__name__)

# Database URL from environment with fallback
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/database/atulya.db")

# Production database configuration
DB_CONFIG = {
    "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
    "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
    "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
    "pool_pre_ping": os.getenv("DB_POOL_PRE_PING", "true").lower() == "true",
    "echo": os.getenv("DB_ECHO", "false").lower() == "true"
}

def create_database_engine():
    """Create database engine with production-ready configuration"""
    
    if DATABASE_URL.startswith("sqlite"):
        # SQLite configuration for development
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=DB_CONFIG["echo"]
        )
    else:
        # PostgreSQL/MySQL configuration for production
        engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=DB_CONFIG["pool_size"],
            max_overflow=DB_CONFIG["max_overflow"],
            pool_timeout=DB_CONFIG["pool_timeout"],
            pool_recycle=DB_CONFIG["pool_recycle"],
            pool_pre_ping=DB_CONFIG["pool_pre_ping"],
            echo=DB_CONFIG["echo"]
        )
    
    # Add connection event listeners for monitoring
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Set SQLite pragmas for better performance"""
        if DATABASE_URL.startswith("sqlite"):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()
    
    @event.listens_for(engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        """Monitor connection checkout"""
        logger.debug("Connection checked out from pool")
    
    @event.listens_for(engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        """Monitor connection checkin"""
        logger.debug("Connection checked in to pool")
    
    return engine

# Create engine with production configuration
engine = create_database_engine()

# Create session factory with retry logic
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine,
    expire_on_commit=False
)

# Create base class for models
Base = declarative_base()

# Metadata for Alembic
metadata = MetaData()

def get_db() -> Generator:
    """Get database session with retry logic"""
    db = SessionLocal()
    try:
        yield db
    except DisconnectionError:
        logger.warning("Database connection lost, retrying...")
        db.rollback()
        db = SessionLocal()
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def get_db_session():
    """Context manager for database sessions with automatic cleanup"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def health_check() -> dict:
    """Check database health and connectivity"""
    try:
        start_time = time.time()
        with engine.connect() as conn:
            # Simple query to test connectivity
            if DATABASE_URL.startswith("sqlite"):
                conn.execute("SELECT 1")
            else:
                conn.execute("SELECT 1")
        
        response_time = time.time() - start_time
        
        return {
            "database": "healthy",
            "connection": "active",
            "response_time_ms": round(response_time * 1000, 2),
            "url": DATABASE_URL.split("://")[0] + "://***",  # Hide credentials
            "pool_size": DB_CONFIG["pool_size"],
            "pool_overflow": DB_CONFIG["max_overflow"]
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "database": "unhealthy",
            "connection": "failed",
            "error": str(e)
        }

def create_tables():
    """Create all database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise

def drop_tables():
    """Drop all database tables (use with caution)"""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("Database tables dropped")
    except Exception as e:
        logger.error(f"Failed to drop database tables: {e}")
        raise

def init_database():
    """Initialize database with tables and default data"""
    try:
        create_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
