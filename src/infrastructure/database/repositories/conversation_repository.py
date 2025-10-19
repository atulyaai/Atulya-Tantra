"""
Conversation repository and service for Atulya Tantra Level 5 AGI System
"""

from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import json

from ..schema import Conversation, Message, User, Project
from ..models import get_db

logger = logging.getLogger(__name__)

class ConversationRepository:
    """Repository for conversation data operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_conversation(
        self,
        user_id: int,
        title: str,
        project_id: Optional[int] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """Create a new conversation"""
        conversation = Conversation(
            user_id=user_id,
            project_id=project_id,
            title=title,
            settings=settings or {}
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        logger.info(f"Created conversation: {conversation.id} for user: {user_id}")
        return conversation
    
    def get_conversation(self, conversation_id: int, user_id: int) -> Optional[Conversation]:
        """Get a conversation by ID"""
        return self.db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
    
    def get_user_conversations(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False
    ) -> List[Conversation]:
        """Get user's conversations"""
        query = self.db.query(Conversation).filter(Conversation.user_id == user_id)
        
        if not include_archived:
            query = query.filter(Conversation.is_archived == False)
        
        return query.order_by(desc(Conversation.updated_at)).offset(offset).limit(limit).all()
    
    def update_conversation(
        self,
        conversation_id: int,
        user_id: int,
        title: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> Optional[Conversation]:
        """Update conversation"""
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            return None
        
        if title:
            conversation.title = title
        if settings:
            conversation.settings.update(settings)
        
        conversation.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(conversation)
        
        return conversation
    
    def archive_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Archive a conversation"""
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            return False
        
        conversation.is_archived = True
        conversation.updated_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Archived conversation: {conversation_id}")
        return True
    
    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Delete a conversation and all its messages"""
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            return False
        
        # Delete all messages first
        self.db.query(Message).filter(Message.conversation_id == conversation_id).delete()
        
        # Delete conversation
        self.db.delete(conversation)
        self.db.commit()
        
        logger.info(f"Deleted conversation: {conversation_id}")
        return True
    
    def search_conversations(
        self,
        user_id: int,
        query: str,
        limit: int = 20
    ) -> List[Conversation]:
        """Search conversations by title and content"""
        # Simple text search - in production, use full-text search
        conversations = self.db.query(Conversation).filter(
            Conversation.user_id == user_id,
            or_(
                Conversation.title.ilike(f"%{query}%"),
                Conversation.id.in_(
                    self.db.query(Message.conversation_id).filter(
                        Message.content.ilike(f"%{query}%")
                    ).distinct()
                )
            )
        ).order_by(desc(Conversation.updated_at)).limit(limit).all()
        
        return conversations
    
    def get_conversation_stats(self, user_id: int) -> Dict[str, int]:
        """Get conversation statistics for user"""
        stats = {
            "total_conversations": self.db.query(Conversation).filter(
                Conversation.user_id == user_id
            ).count(),
            "active_conversations": self.db.query(Conversation).filter(
                Conversation.user_id == user_id,
                Conversation.is_archived == False
            ).count(),
            "archived_conversations": self.db.query(Conversation).filter(
                Conversation.user_id == user_id,
                Conversation.is_archived == True
            ).count(),
            "total_messages": self.db.query(Message).join(Conversation).filter(
                Conversation.user_id == user_id
            ).count()
        }
        
        return stats

class MessageRepository:
    """Repository for message data operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[str] = None
    ) -> Message:
        """Add a message to a conversation"""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            message_metadata=metadata or {},
            embedding=embedding
        )
        
        self.db.add(message)
        
        # Update conversation timestamp
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        if conversation:
            conversation.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def get_conversation_messages(
        self,
        conversation_id: int,
        user_id: int,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Message]:
        """Get messages for a conversation"""
        # Verify user has access to conversation
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            return []
        
        query = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.timestamp)
        
        if limit:
            query = query.offset(offset).limit(limit)
        
        return query.all()
    
    def get_recent_messages(
        self,
        user_id: int,
        limit: int = 100
    ) -> List[Message]:
        """Get recent messages across all user conversations"""
        return self.db.query(Message).join(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(desc(Message.timestamp)).limit(limit).all()
    
    def search_messages(
        self,
        user_id: int,
        query: str,
        limit: int = 50
    ) -> List[Message]:
        """Search messages by content"""
        return self.db.query(Message).join(Conversation).filter(
            Conversation.user_id == user_id,
            Message.content.ilike(f"%{query}%")
        ).order_by(desc(Message.timestamp)).limit(limit).all()
    
    def update_message(
        self,
        message_id: int,
        user_id: int,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Message]:
        """Update a message"""
        message = self.db.query(Message).join(Conversation).filter(
            Message.id == message_id,
            Conversation.user_id == user_id
        ).first()
        
        if not message:
            return None
        
        if content:
            message.content = content
        if metadata:
            message.message_metadata.update(metadata)
        
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def delete_message(self, message_id: int, user_id: int) -> bool:
        """Delete a message"""
        message = self.db.query(Message).join(Conversation).filter(
            Message.id == message_id,
            Conversation.user_id == user_id
        ).first()
        
        if not message:
            return False
        
        self.db.delete(message)
        self.db.commit()
        
        logger.info(f"Deleted message: {message_id}")
        return True

class ConversationService:
    """Service layer for conversation operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.conversation_repo = ConversationRepository(db)
        self.message_repo = MessageRepository(db)
    
    def create_conversation(
        self,
        user_id: int,
        title: str,
        project_id: Optional[int] = None,
        initial_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new conversation with optional initial message"""
        conversation = self.conversation_repo.create_conversation(
            user_id=user_id,
            title=title,
            project_id=project_id
        )
        
        # Add initial message if provided
        if initial_message:
            self.message_repo.add_message(
                conversation_id=conversation.id,
                role="user",
                content=initial_message
            )
        
        return {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "project_id": conversation.project_id,
            "settings": conversation.settings
        }
    
    def get_conversation_history(
        self,
        conversation_id: int,
        user_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation history"""
        messages = self.message_repo.get_conversation_messages(
            conversation_id=conversation_id,
            user_id=user_id,
            limit=limit
        )
        
        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "metadata": msg.message_metadata
            }
            for msg in messages
        ]
    
    def add_message_to_conversation(
        self,
        conversation_id: int,
        user_id: int,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a message to a conversation"""
        # Verify conversation exists and user has access
        conversation = self.conversation_repo.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError("Conversation not found or access denied")
        
        message = self.message_repo.add_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata
        )
        
        return {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp.isoformat(),
            "metadata": message.metadata
        }
    
    def get_user_conversations(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False
    ) -> List[Dict[str, Any]]:
        """Get user's conversations"""
        conversations = self.conversation_repo.get_user_conversations(
            user_id=user_id,
            limit=limit,
            offset=offset,
            include_archived=include_archived
        )
        
        return [
            {
                "id": conv.id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "project_id": conv.project_id,
                "is_archived": conv.is_archived,
                "message_count": len(conv.messages)
            }
            for conv in conversations
        ]
    
    def search_conversations(
        self,
        user_id: int,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search conversations"""
        conversations = self.conversation_repo.search_conversations(
            user_id=user_id,
            query=query,
            limit=limit
        )
        
        return [
            {
                "id": conv.id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "project_id": conv.project_id,
                "is_archived": conv.is_archived
            }
            for conv in conversations
        ]
    
    def archive_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Archive a conversation"""
        return self.conversation_repo.archive_conversation(conversation_id, user_id)
    
    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Delete a conversation"""
        return self.conversation_repo.delete_conversation(conversation_id, user_id)
    
    def get_conversation_stats(self, user_id: int) -> Dict[str, int]:
        """Get conversation statistics"""
        return self.conversation_repo.get_conversation_stats(user_id)
    
    def export_conversation(
        self,
        conversation_id: int,
        user_id: int,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export conversation in specified format"""
        conversation = self.conversation_repo.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError("Conversation not found or access denied")
        
        messages = self.message_repo.get_conversation_messages(conversation_id, user_id)
        
        if format == "json":
            return {
                "conversation": {
                    "id": conversation.id,
                    "title": conversation.title,
                    "created_at": conversation.created_at.isoformat(),
                    "updated_at": conversation.updated_at.isoformat(),
                    "project_id": conversation.project_id,
                    "settings": conversation.settings
                },
                "messages": [
                    {
                        "id": msg.id,
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "metadata": msg.message_metadata
                    }
                    for msg in messages
                ]
            }
        elif format == "markdown":
            markdown = f"# {conversation.title}\n\n"
            markdown += f"**Created:** {conversation.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            for msg in messages:
                role_emoji = "👤" if msg.role == "user" else "🤖"
                markdown += f"{role_emoji} **{msg.role.title()}** ({msg.timestamp.strftime('%H:%M:%S')})\n\n"
                markdown += f"{msg.content}\n\n---\n\n"
            
            return {"content": markdown, "format": "markdown"}
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
