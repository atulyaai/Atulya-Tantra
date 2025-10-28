"""
Database Migrations for Atulya Tantra AGI
Database schema migrations
"""

from typing import List, Dict, Any

class MigrationManager:
    """Manage database migrations"""
    
    def __init__(self, db):
        self.db = db
        self.migrations = []
    
    def add_migration(self, version: int, description: str, sql: str):
        """Add a migration"""
        self.migrations.append({
            'version': version,
            'description': description,
            'sql': sql
        })
    
    def run_migrations(self):
        """Run all pending migrations"""
        # Create migrations table if it doesn't exist
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS migrations (
                version INTEGER PRIMARY KEY,
                description TEXT,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Get applied migrations
        applied = self.db.execute_query("SELECT version FROM migrations")
        applied_versions = {row['version'] for row in applied}
        
        # Run pending migrations
        for migration in sorted(self.migrations, key=lambda x: x['version']):
            if migration['version'] not in applied_versions:
                self.db.execute_query(migration['sql'])
                self.db.execute_query(
                    "INSERT INTO migrations (version, description) VALUES (?, ?)",
                    (migration['version'], migration['description'])
                )