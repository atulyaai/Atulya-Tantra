"""
Data models for Atulya Tantra AGI
SQLAlchemy models for database operations
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=True)
    roles = Column(String(50), default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id='{self.id}', username='{self.username}', email='{self.email}')>"


class Conversation(Base):
    """Conversation model"""
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Conversation(id='{self.id}', user_id='{self.user_id}', title='{self.title}')>"


class Message(Base):
    """Message model"""
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    metadata = Column(Text, nullable=True)  # JSON string for additional data
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    def __repr__(self):
        return f"<Message(id='{self.id}', conversation_id='{self.conversation_id}', role='{self.role}')>"


class Session(Base):
    """User session model"""
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, nullable=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<Session(id='{self.id}', user_id='{self.user_id}', expires_at='{self.expires_at}')>"


class AgentLog(Base):
    """Agent execution log model"""
    __tablename__ = "agent_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_type = Column(String(50), nullable=False, index=True)
    task = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed'
    duration_ms = Column(Integer, nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User")
    conversation = relationship("Conversation")
    
    def __repr__(self):
        return f"<AgentLog(id='{self.id}', agent_type='{self.agent_type}', status='{self.status}')>"


class Memory(Base):
    """Memory storage model"""
    __tablename__ = "memories"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    memory_type = Column(String(50), nullable=False, index=True)  # 'conversation', 'fact', 'preference', 'semantic'
    content = Column(Text, nullable=False)
    embedding_vector = Column(Text, nullable=True)  # JSON string of vector
    metadata = Column(Text, nullable=True)  # JSON string for additional data
    importance_score = Column(Integer, default=0, nullable=False)  # 0-100
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f"<Memory(id='{self.id}', memory_type='{self.memory_type}', importance_score='{self.importance_score}')>"


class KnowledgeNode(Base):
    """Knowledge graph node model"""
    __tablename__ = "knowledge_nodes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_type = Column(String(50), nullable=False, index=True)  # 'entity', 'concept', 'event', 'person'
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    properties = Column(Text, nullable=True)  # JSON string for additional properties
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<KnowledgeNode(id='{self.id}', node_type='{self.node_type}', name='{self.name}')>"


class KnowledgeEdge(Base):
    """Knowledge graph edge model"""
    __tablename__ = "knowledge_edges"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_node_id = Column(String, ForeignKey("knowledge_nodes.id"), nullable=False, index=True)
    target_node_id = Column(String, ForeignKey("knowledge_nodes.id"), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False, index=True)  # 'related_to', 'part_of', 'causes', etc.
    weight = Column(Integer, default=1, nullable=False)  # Relationship strength
    properties = Column(Text, nullable=True)  # JSON string for additional properties
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    source_node = relationship("KnowledgeNode", foreign_keys=[source_node_id])
    target_node = relationship("KnowledgeNode", foreign_keys=[target_node_id])
    
    def __repr__(self):
        return f"<KnowledgeEdge(id='{self.id}', source='{self.source_node_id}', target='{self.target_node_id}', type='{self.relationship_type}')>"


class SystemMetric(Base):
    """System performance metrics model"""
    __tablename__ = "system_metrics"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Integer, nullable=False)
    metric_unit = Column(String(20), nullable=True)  # 'ms', 'bytes', 'count', etc.
    tags = Column(Text, nullable=True)  # JSON string for tags/labels
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<SystemMetric(id='{self.id}', name='{self.metric_name}', value='{self.metric_value}')>"


class APILog(Base):
    """API request/response log model"""
    __tablename__ = "api_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    endpoint = Column(String(200), nullable=False, index=True)
    method = Column(String(10), nullable=False, index=True)
    status_code = Column(Integer, nullable=False, index=True)
    duration_ms = Column(Integer, nullable=True)
    request_size = Column(Integer, nullable=True)
    response_size = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f"<APILog(id='{self.id}', endpoint='{self.endpoint}', status='{self.status_code}')>"


# Export all models
__all__ = [
    "Base",
    "User",
    "Conversation", 
    "Message",
    "Session",
    "AgentLog",
    "Memory",
    "KnowledgeNode",
    "KnowledgeEdge",
    "SystemMetric",
    "APILog"
]
