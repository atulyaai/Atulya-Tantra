"""
Database models and ORM definitions for Atulya Tantra Level 5 AGI System
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
import os

from .schema import Base

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/database/atulya.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    poolclass=StaticPool if "sqlite" in DATABASE_URL else None,
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Initialize database with tables and default data"""
    # Create tables
    create_tables()
    
    # Create default agents
    db = SessionLocal()
    try:
        from .schema import Agent
        
        # Check if agents already exist
        if db.query(Agent).count() == 0:
            default_agents = [
                Agent(
                    name="JARVIS",
                    type="jarvis",
                    status="active",
                    config={
                        "personality": "helpful",
                        "voice_enabled": True,
                        "proactive_suggestions": True
                    },
                    performance_metrics={
                        "response_time": 0.0,
                        "success_rate": 0.0,
                        "user_satisfaction": 0.0
                    }
                ),
                Agent(
                    name="Skynet",
                    type="skynet",
                    status="active",
                    config={
                        "autonomous_mode": True,
                        "self_healing": True,
                        "monitoring_enabled": True
                    },
                    performance_metrics={
                        "tasks_completed": 0,
                        "uptime": 0.0,
                        "error_rate": 0.0
                    }
                ),
                Agent(
                    name="Code Agent",
                    type="specialized",
                    status="active",
                    config={
                        "specialization": "coding",
                        "languages": ["python", "javascript", "typescript", "go", "rust"],
                        "tools": ["git", "docker", "kubernetes"]
                    },
                    performance_metrics={
                        "code_generated": 0,
                        "bugs_fixed": 0,
                        "tests_written": 0
                    }
                ),
                Agent(
                    name="Research Agent",
                    type="specialized",
                    status="active",
                    config={
                        "specialization": "research",
                        "sources": ["web", "academic", "news"],
                        "fact_checking": True
                    },
                    performance_metrics={
                        "papers_analyzed": 0,
                        "facts_verified": 0,
                        "sources_cited": 0
                    }
                ),
                Agent(
                    name="Creative Agent",
                    type="specialized",
                    status="active",
                    config={
                        "specialization": "creative",
                        "domains": ["writing", "design", "music", "art"],
                        "style_adaptation": True
                    },
                    performance_metrics={
                        "content_created": 0,
                        "styles_adapted": 0,
                        "creativity_score": 0.0
                    }
                )
            ]
            
            for agent in default_agents:
                db.add(agent)
            
            db.commit()
            print("Default agents created successfully")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()

# Database utility functions
class DatabaseManager:
    """Database management utilities"""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    def create_tables(self):
        """Create all tables"""
        create_tables()
    
    def drop_tables(self):
        """Drop all tables (use with caution!)"""
        Base.metadata.drop_all(bind=self.engine)
    
    def reset_database(self):
        """Reset database by dropping and recreating all tables"""
        self.drop_tables()
        self.create_tables()
        init_database()
    
    def backup_database(self, backup_path: str):
        """Backup database to file"""
        import shutil
        if "sqlite" in DATABASE_URL:
            db_path = DATABASE_URL.replace("sqlite:///", "")
            shutil.copy2(db_path, backup_path)
            print(f"Database backed up to {backup_path}")
        else:
            print("Backup not implemented for non-SQLite databases")
    
    def get_stats(self) -> dict:
        """Get database statistics"""
        db = self.get_session()
        try:
            from .schema import User, Conversation, Message, Project, Agent, Task
            
            stats = {
                "users": db.query(User).count(),
                "conversations": db.query(Conversation).count(),
                "messages": db.query(Message).count(),
                "projects": db.query(Project).count(),
                "agents": db.query(Agent).count(),
                "tasks": db.query(Task).count(),
                "active_users": db.query(User).filter(User.is_active == True).count(),
                "archived_conversations": db.query(Conversation).filter(Conversation.is_archived == True).count()
            }
            return stats
        finally:
            db.close()

# Global database manager instance
db_manager = DatabaseManager()
