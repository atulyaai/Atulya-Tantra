"""
Database abstraction layer for Atulya Tantra AGI
Supports SQLite, PostgreSQL, and JSON file backends
"""

from .database import (
    DatabaseInterface,
    SQLiteDatabase,
    PostgreSQLDatabase,
    JSONDatabase,
    DatabaseFactory,
    get_database,
    close_database
)
from .service import DatabaseService, get_db_service
from .migrations import setup_alembic, create_initial_migration, run_migrations

__all__ = [
    "DatabaseInterface",
    "SQLiteDatabase",
    "PostgreSQLDatabase", 
    "JSONDatabase",
    "DatabaseFactory",
    "get_database",
    "close_database",
    "DatabaseService",
    "get_db_service",
    "setup_alembic",
    "create_initial_migration",
    "run_migrations"
]