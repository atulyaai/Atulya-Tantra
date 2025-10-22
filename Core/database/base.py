"""
Base database interface and factory for Atulya Tantra AGI
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

__all__ = [
    "DatabaseInterface",
    "SQLiteDatabase",
    "PostgreSQLDatabase", 
    "JSONDatabase",
    "DatabaseFactory",
    "get_database",
    "close_database"
]
