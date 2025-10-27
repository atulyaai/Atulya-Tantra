"""
Creative Agent for Atulya Tantra AGI
Specialized agent for creative content generation
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_agent import BaseAgent, AgentTask, AgentStatus, AgentCapability, AgentPriority
from ..config.logging import get_logger
from ..config.exceptions import AgentError, ValidationError

logger = get_logger(__name__)


class CreativeAgent(BaseAgent):
    """Creative content generation agent"""
    
    def __init__(self):
        super().__init__(
            agent_id="creative_agent",
            name="Creative Agent",
            capabilities=[
                AgentCapability.CONTENT_GENERATION,
                AgentCapability.CREATIVE_WRITING,
                AgentCapability.IMAGE_GENERATION,
                AgentCapability.MUSIC_GENERATION,
                AgentCapability.STORYTELLING
            ],
            priority=AgentPriority.MEDIUM
        )
        self.creative_templates = self._load_creative_templates()
    
    def _load_creative_templates(self) -> Dict[str, str]:
        """Load creative templates"""
        return {
            "story": "Once upon a time, {setting}, there was {character} who {conflict}...",
            "poem": "{title}\n\n{line1}\n{line2}\n{line3}\n{line4}",
            "song": "{title}\n\n[Verse 1]\n{verse1}\n\n[Chorus]\n{chorus}\n\n[Verse 2]\n{verse2}",
            "script": "SCENE: {setting}\n\n{character1}: {dialogue1}\n{character2}: {dialogue2}"
        }
    
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute creative task"""
        try:
            task_type = task.parameters.get("task_type", "generate")
            
            if task_type == "generate":
                return await self._generate_content(task)
            elif task_type == "edit":
                return await self._edit_content(task)
            elif task_type == "brainstorm":
                return await self._brainstorm_ideas(task)
            elif task_type == "style_transfer":
                return await self._transfer_style(task)
            else:
                raise ValidationError(f"Unknown task type: {task_type}")
                
        except Exception as e:
            logger.error(f"Error executing creative task: {e}")
            raise AgentError(f"Failed to execute creative task: {e}")
    
    async def _generate_content(self, task: AgentTask) -> Dict[str, Any]:
        """Generate creative content"""
        try:
            content_type = task.parameters.get("content_type", "story")
            prompt = task.parameters.get("prompt", "")
            style = task.parameters.get("style", "creative")
            length = task.parameters.get("length", "medium")
            
            # Generate content using AI
            content = await self._generate_with_ai(content_type, prompt, style, length)
            
            return {
                "content": content,
                "content_type": content_type,
                "style": style,
                "length": length,
                "metadata": await self._analyze_content(content)
            }
            
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            raise AgentError(f"Failed to generate content: {e}")
    
    async def _edit_content(self, task: AgentTask) -> Dict[str, Any]:
        """Edit creative content"""
        try:
            content = task.parameters.get("content", "")
            edit_type = task.parameters.get("edit_type", "improve")
            style = task.parameters.get("style", "creative")
            
            # Edit content using AI
            edited_content = await self._edit_with_ai(content, edit_type, style)
            
            return {
                "original_content": content,
                "edited_content": edited_content,
                "edit_type": edit_type,
                "changes": await self._identify_changes(content, edited_content)
            }
            
        except Exception as e:
            logger.error(f"Error editing content: {e}")
            raise AgentError(f"Failed to edit content: {e}")
    
    async def _brainstorm_ideas(self, task: AgentTask) -> Dict[str, Any]:
        """Brainstorm creative ideas"""
        try:
            topic = task.parameters.get("topic", "")
            num_ideas = task.parameters.get("num_ideas", 5)
            category = task.parameters.get("category", "general")
            
            # Generate ideas using AI
            ideas = await self._generate_ideas_with_ai(topic, num_ideas, category)
            
            return {
                "topic": topic,
                "ideas": ideas,
                "category": category,
                "inspiration": await self._get_inspiration(topic, category)
            }
            
        except Exception as e:
            logger.error(f"Error brainstorming ideas: {e}")
            raise AgentError(f"Failed to brainstorm ideas: {e}")
    
    async def _transfer_style(self, task: AgentTask) -> Dict[str, Any]:
        """Transfer style between content"""
        try:
            content = task.parameters.get("content", "")
            target_style = task.parameters.get("target_style", "formal")
            source_style = task.parameters.get("source_style", "casual")
            
            # Transfer style using AI
            styled_content = await self._transfer_style_with_ai(content, source_style, target_style)
            
            return {
                "original_content": content,
                "styled_content": styled_content,
                "source_style": source_style,
                "target_style": target_style,
                "style_analysis": await self._analyze_style(content, styled_content)
            }
            
        except Exception as e:
            logger.error(f"Error transferring style: {e}")
            raise AgentError(f"Failed to transfer style: {e}")
    
    async def _generate_with_ai(self, content_type: str, prompt: str, style: str, length: str) -> str:
        """Generate content using AI"""
        # This would integrate with the LLM provider
        template = self.creative_templates.get(content_type, "")
        
        if template:
            return template.format(
                setting="in a magical forest",
                character="a brave knight",
                conflict="faced a dragon",
                title="The Adventure",
                line1="In the forest deep and dark",
                line2="Where shadows dance and play",
                line3="A knight with courage in his heart",
                line4="Set out to save the day"
            )
        
        return f"Generated {content_type} content: {prompt}"
    
    async def _edit_with_ai(self, content: str, edit_type: str, style: str) -> str:
        """Edit content using AI"""
        # This would integrate with the LLM provider
        if edit_type == "improve":
            return content.replace("good", "excellent").replace("bad", "terrible")
        elif edit_type == "shorten":
            return content[:len(content)//2] + "..."
        elif edit_type == "expand":
            return content + " " + content
        
        return content
    
    async def _generate_ideas_with_ai(self, topic: str, num_ideas: int, category: str) -> List[str]:
        """Generate ideas using AI"""
        # This would integrate with the LLM provider
        ideas = []
        for i in range(num_ideas):
            ideas.append(f"Idea {i+1} about {topic} in {category} category")
        
        return ideas
    
    async def _transfer_style_with_ai(self, content: str, source_style: str, target_style: str) -> str:
        """Transfer style using AI"""
        # This would integrate with the LLM provider
        if target_style == "formal":
            return content.replace("don't", "do not").replace("can't", "cannot")
        elif target_style == "casual":
            return content.replace("do not", "don't").replace("cannot", "can't")
        
        return content
    
    async def _analyze_content(self, content: str) -> Dict[str, Any]:
        """Analyze content characteristics"""
        return {
            "word_count": len(content.split()),
            "sentence_count": content.count('.') + content.count('!') + content.count('?'),
            "readability": "medium",
            "tone": "creative",
            "emotion": "positive"
        }
    
    async def _identify_changes(self, original: str, edited: str) -> List[str]:
        """Identify changes between original and edited content"""
        changes = []
        
        if len(edited) > len(original):
            changes.append("Content expanded")
        elif len(edited) < len(original):
            changes.append("Content shortened")
        
        if edited != original:
            changes.append("Content modified")
        
        return changes
    
    async def _get_inspiration(self, topic: str, category: str) -> List[str]:
        """Get inspiration for creative work"""
        return [
            f"Research {topic} in {category}",
            f"Look at examples of {category} work",
            f"Consider different perspectives on {topic}",
            f"Explore related topics to {topic}"
        ]
    
    async def _analyze_style(self, original: str, styled: str) -> Dict[str, Any]:
        """Analyze style differences"""
        return {
            "formality_change": "increased" if "do not" in styled else "decreased",
            "tone_change": "more formal" if "do not" in styled else "more casual",
            "word_count_change": len(styled.split()) - len(original.split())
        }