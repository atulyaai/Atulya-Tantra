"""
Database schema definitions for Atulya Tantra Level 5 AGI System
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from . import Base

class User(Base):
    """User accounts and authentication"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    settings = Column(JSON, default=dict)
    
    # Relationships
    sessions = relationship("Session", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")
    projects = relationship("Project", back_populates="user")
    tasks = relationship("Task", back_populates="user")
    files = relationship("File", back_populates="user")

class Session(Base):
    """User sessions and JWT tokens"""
    __tablename__ = 'sessions'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    token = Column(String(500), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")

class Conversation(Base):
    """Chat conversations"""
    __tablename__ = 'conversations'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    title = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = Column(Boolean, default=False)
    settings = Column(JSON, default=dict)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    project = relationship("Project", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")

class Message(Base):
    """Individual chat messages"""
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    message_metadata = Column(JSON, default=dict)  # Renamed from metadata
    timestamp = Column(DateTime, default=datetime.utcnow)
    embedding = Column(Text, nullable=True)  # Vector embedding for semantic search
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

class Project(Base):
    """User projects for organizing conversations"""
    __tablename__ = 'projects'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="projects")
    conversations = relationship("Conversation", back_populates="project")

class Agent(Base):
    """AI agents and their configurations"""
    __tablename__ = 'agents'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)  # 'jarvis', 'skynet', 'specialized'
    status = Column(String(20), default='active')  # 'active', 'inactive', 'training'
    config = Column(JSON, default=dict)
    performance_metrics = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tasks = relationship("Task", back_populates="agent")

class Task(Base):
    """Tasks assigned to agents"""
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    agent_id = Column(Integer, ForeignKey('agents.id'), nullable=True)
    description = Column(Text, nullable=False)
    status = Column(String(20), default='pending')  # 'pending', 'in_progress', 'completed', 'failed'
    result = Column(Text, nullable=True)
    task_metadata = Column(JSON, default=dict)  # Renamed from metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="tasks")
    agent = relationship("Agent", back_populates="tasks")

class File(Base):
    """File uploads and attachments"""
    __tablename__ = 'files'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    path = Column(String(500), nullable=False)
    size = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    file_metadata = Column(JSON, default=dict)  # Renamed from metadata
    
    # Relationships
    user = relationship("User", back_populates="files")

class SystemMetrics(Base):
    """System performance and monitoring metrics"""
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metrics_metadata = Column(JSON, default=dict)  # Renamed from metadata

class KnowledgeGraph(Base):
    """Knowledge graph nodes and relationships"""
    __tablename__ = 'knowledge_graph'
    
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String(100), unique=True, index=True, nullable=False)
    node_type = Column(String(50), nullable=False)  # 'concept', 'entity', 'relation'
    properties = Column(JSON, default=dict)
    embedding = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class KnowledgeRelation(Base):
    """Relationships between knowledge graph nodes"""
    __tablename__ = 'knowledge_relations'
    
    id = Column(Integer, primary_key=True, index=True)
    source_node_id = Column(String(100), ForeignKey('knowledge_graph.node_id'), nullable=False)
    target_node_id = Column(String(100), ForeignKey('knowledge_graph.node_id'), nullable=False)
    relation_type = Column(String(50), nullable=False)
    weight = Column(Float, default=1.0)
    relation_properties = Column(JSON, default=dict)  # Renamed from properties
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    source_node = relationship("KnowledgeGraph", foreign_keys=[source_node_id])
    target_node = relationship("KnowledgeGraph", foreign_keys=[target_node_id])
