"""
Creative Agent for Atulya Tantra AGI
Specialized agent for creative writing, content generation, and artistic tasks
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import random

from .base_agent import BaseAgent, AgentTask, AgentCapability, AgentStatus
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..brain import generate_response, get_llm_router

logger = get_logger(__name__)


class CreativeAgent(BaseAgent):
    """Agent specialized in creative writing, content generation, and artistic tasks"""
    
    def __init__(self):
        super().__init__(
            name="CreativeAgent",
            description="Specialized agent for creative writing, content generation, storytelling, and artistic tasks",
            capabilities=[
                AgentCapability.CREATIVE_WRITING,
                AgentCapability.TEXT_GENERATION,
                AgentCapability.FILE_PROCESSING
            ],
            max_concurrent_tasks=3,
            timeout_seconds=180
        )
        
        self.creative_styles = [
            "professional", "casual", "formal", "humorous", "poetic", "dramatic",
            "conversational", "academic", "marketing", "technical", "storytelling"
        ]
        
        self.content_types = [
            "article", "blog_post", "story", "poem", "script", "dialogue",
            "description", "summary", "outline", "proposal", "email", "letter"
        ]
        
        self.tone_options = [
            "friendly", "professional", "casual", "formal", "enthusiastic",
            "serious", "humorous", "inspiring", "persuasive", "informative"
        ]
    
    async def can_handle_task(self, task: AgentTask) -> bool:
        """Check if this agent can handle the given task"""
        task_type = task.task_type or ""
        description = (task.description or "").lower()
        
        # Check for creative-related keywords
        creative_keywords = [
            "write", "create", "generate", "story", "article", "blog", "poem",
            "script", "dialogue", "content", "creative", "artistic", "narrative",
            "fiction", "non-fiction", "copy", "marketing", "advertising",
            "description", "outline", "proposal", "email", "letter", "summary",
            "character", "plot", "setting", "theme", "style", "tone"
        ]
        
        return (
            task_type in ["creative_writing", "content_generation", "storytelling", "copywriting"] or
            any(keyword in description for keyword in creative_keywords)
        )
    
    async def get_task_estimate(self, task: AgentTask) -> Dict[str, Any]:
        """Estimate task execution time and resource requirements"""
        task_type = task.task_type or ""
        description = task.description or ""
        
        # Base estimates
        if task_type == "creative_writing":
            estimated_time = 45  # seconds
            complexity = "medium"
        elif task_type == "content_generation":
            estimated_time = 30
            complexity = "low"
        elif task_type == "storytelling":
            estimated_time = 90
            complexity = "high"
        else:
            estimated_time = 60
            complexity = "medium"
        
        # Adjust based on content length requirements
        if "long" in description or "detailed" in description:
            estimated_time *= 1.5
            complexity = "high"
        elif "short" in description or "brief" in description:
            estimated_time *= 0.7
            complexity = "low"
        
        return {
            "estimated_time_seconds": estimated_time,
            "complexity": complexity,
            "resource_requirements": {
                "memory_mb": 30,
                "cpu_usage": "low",
                "creativity_level": "high"
            }
        }
    
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute a creative task"""
        try:
            task_type = task.task_type or "creative_writing"
            input_data = task.input_data or {}
            
            if task_type == "creative_writing":
                return await self._creative_writing(task, input_data)
            elif task_type == "content_generation":
                return await self._generate_content(task, input_data)
            elif task_type == "storytelling":
                return await self._create_story(task, input_data)
            elif task_type == "copywriting":
                return await self._copywriting(task, input_data)
            elif task_type == "poetry":
                return await self._create_poetry(task, input_data)
            else:
                return await self._general_creative_task(task, input_data)
                
        except Exception as e:
            logger.error(f"CreativeAgent execution error: {e}")
            raise AgentError(f"Creative task failed: {e}")
    
    async def _creative_writing(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate creative written content"""
        topic = input_data.get("topic", task.description)
        content_type = input_data.get("content_type", "article")
        style = input_data.get("style", "professional")
        tone = input_data.get("tone", "friendly")
        length = input_data.get("length", "medium")
        audience = input_data.get("audience", "general")
        
        if not topic:
            raise AgentError("No topic provided for creative writing")
        
        # Create detailed prompt
        prompt = f"""
You are a creative writer. Create {content_type} content with the following specifications:

Topic: {topic}
Content Type: {content_type}
Style: {style}
Tone: {tone}
Length: {length}
Target Audience: {audience}

Please create engaging, well-structured content that:
1. Captures the reader's attention
2. Maintains consistent style and tone
3. Provides value to the target audience
4. Uses appropriate language and vocabulary
5. Includes relevant examples or anecdotes if suitable

Make the content original, creative, and compelling.
"""
        
        content = await generate_response(
            prompt=prompt,
            max_tokens=2000,
            temperature=0.7,  # Higher temperature for creativity
            preferred_provider="openai"
        )
        
        # Generate additional creative elements
        title = await self._generate_title(topic, content_type, style)
        outline = await self._generate_outline(content)
        
        return {
            "content": content,
            "title": title,
            "outline": outline,
            "metadata": {
                "topic": topic,
                "content_type": content_type,
                "style": style,
                "tone": tone,
                "length": length,
                "audience": audience,
                "word_count": len(content.split()),
                "created_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _generate_content(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate specific types of content"""
        content_type = input_data.get("content_type", "article")
        topic = input_data.get("topic", task.description)
        requirements = input_data.get("requirements", [])
        
        if not topic:
            raise AgentError("No topic provided for content generation")
        
        prompt = f"""
Generate {content_type} content about: {topic}

Additional Requirements:
{json.dumps(requirements, indent=2) if requirements else "None"}

Please create high-quality {content_type} that is:
1. Informative and engaging
2. Well-structured and organized
3. Appropriate for the target audience
4. Original and creative
5. Meets all specified requirements

Make it professional and polished.
"""
        
        content = await generate_response(
            prompt=prompt,
            max_tokens=1500,
            temperature=0.6,
            preferred_provider="openai"
        )
        
        return {
            "content": content,
            "content_type": content_type,
            "topic": topic,
            "requirements_met": requirements,
            "metadata": {
                "task_type": "content_generation",
                "generated_at": datetime.utcnow().isoformat(),
                "word_count": len(content.split())
            }
        }
    
    async def _create_story(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a story with characters, plot, and setting"""
        genre = input_data.get("genre", "general")
        theme = input_data.get("theme", task.description)
        characters = input_data.get("characters", [])
        setting = input_data.get("setting", "")
        length = input_data.get("length", "short")
        
        if not theme:
            raise AgentError("No theme provided for story creation")
        
        # Generate story elements if not provided
        if not characters:
            characters = await self._generate_characters(theme, genre)
        
        if not setting:
            setting = await self._generate_setting(theme, genre)
        
        plot = await self._generate_plot(theme, characters, setting, genre)
        
        # Create the story
        prompt = f"""
Write a {length} {genre} story with the following elements:

Theme: {theme}
Setting: {setting}
Characters: {json.dumps(characters, indent=2)}
Plot Outline: {plot}

Please create an engaging story that:
1. Develops the characters effectively
2. Maintains consistent tone and style
3. Follows the plot outline
4. Includes dialogue and description
5. Has a satisfying conclusion

Make it compelling and well-written.
"""
        
        story = await generate_response(
            prompt=prompt,
            max_tokens=2500,
            temperature=0.8,  # High temperature for creative storytelling
            preferred_provider="openai"
        )
        
        return {
            "story": story,
            "story_elements": {
                "genre": genre,
                "theme": theme,
                "characters": characters,
                "setting": setting,
                "plot": plot
            },
            "metadata": {
                "task_type": "storytelling",
                "created_at": datetime.utcnow().isoformat(),
                "word_count": len(story.split()),
                "story_length": length
            }
        }
    
    async def _copywriting(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create marketing copy and advertising content"""
        product = input_data.get("product", task.description)
        target_audience = input_data.get("target_audience", "general")
        copy_type = input_data.get("copy_type", "advertisement")
        tone = input_data.get("tone", "persuasive")
        call_to_action = input_data.get("call_to_action", "")
        
        if not product:
            raise AgentError("No product provided for copywriting")
        
        prompt = f"""
Create compelling {copy_type} copy for: {product}

Target Audience: {target_audience}
Copy Type: {copy_type}
Tone: {tone}
Call to Action: {call_to_action}

Please create copy that:
1. Captures attention immediately
2. Highlights key benefits and features
3. Appeals to the target audience
4. Uses persuasive language
5. Includes a clear call to action
6. Is memorable and engaging

Make it professional and effective for marketing purposes.
"""
        
        copy_content = await generate_response(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.6,
            preferred_provider="openai"
        )
        
        # Generate additional copy variations
        headline = await self._generate_headline(product, target_audience)
        tagline = await self._generate_tagline(product, tone)
        
        return {
            "copy": copy_content,
            "headline": headline,
            "tagline": tagline,
            "call_to_action": call_to_action,
            "metadata": {
                "product": product,
                "target_audience": target_audience,
                "copy_type": copy_type,
                "tone": tone,
                "created_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _create_poetry(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create poetry and verse"""
        theme = input_data.get("theme", task.description)
        style = input_data.get("style", "free verse")
        mood = input_data.get("mood", "contemplative")
        length = input_data.get("length", "medium")
        
        if not theme:
            raise AgentError("No theme provided for poetry creation")
        
        prompt = f"""
Write a {style} poem about: {theme}

Style: {style}
Mood: {mood}
Length: {length}

Please create poetry that:
1. Captures the essence of the theme
2. Uses appropriate poetic devices (metaphor, imagery, rhythm)
3. Evokes the desired mood
4. Is emotionally resonant
5. Follows the specified style conventions

Make it beautiful and meaningful.
"""
        
        poem = await generate_response(
            prompt=prompt,
            max_tokens=800,
            temperature=0.9,  # Very high temperature for poetic creativity
            preferred_provider="openai"
        )
        
        return {
            "poem": poem,
            "poetry_elements": {
                "theme": theme,
                "style": style,
                "mood": mood,
                "length": length
            },
            "metadata": {
                "task_type": "poetry",
                "created_at": datetime.utcnow().isoformat(),
                "line_count": len(poem.split('\n')),
                "word_count": len(poem.split())
            }
        }
    
    async def _general_creative_task(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general creative tasks"""
        description = task.description or ""
        
        prompt = f"""
You are a creative professional. Help with the following creative task:

Task: {description}

Please provide:
1. Creative approach and ideas
2. Key elements to consider
3. Style and tone recommendations
4. Creative techniques to use
5. Examples or inspiration

Be imaginative and helpful in your creative guidance.
"""
        
        response = await generate_response(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.7,
            preferred_provider="openai"
        )
        
        return {
            "creative_guidance": response,
            "task_description": description,
            "metadata": {
                "task_type": "general_creative",
                "completed_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _generate_title(self, topic: str, content_type: str, style: str) -> str:
        """Generate an engaging title"""
        prompt = f"""
Generate an engaging title for {content_type} about: {topic}

Style: {style}

Create a title that is:
1. Attention-grabbing
2. Relevant to the content
3. Appropriate for the style
4. Memorable and compelling

Return only the title.
"""
        
        title = await generate_response(
            prompt=prompt,
            max_tokens=50,
            temperature=0.8,
            preferred_provider="openai"
        )
        
        return title.strip()
    
    async def _generate_outline(self, content: str) -> List[str]:
        """Generate an outline from content"""
        prompt = f"""
Create a structured outline for the following content:

{content[:1000]}...

Please provide:
1. Main sections/headings
2. Key points under each section
3. Logical flow and organization

Return as a clear, hierarchical outline.
"""
        
        outline_text = await generate_response(
            prompt=prompt,
            max_tokens=500,
            temperature=0.3,
            preferred_provider="openai"
        )
        
        # Parse outline into list
        outline_lines = [line.strip() for line in outline_text.split('\n') if line.strip()]
        return outline_lines
    
    async def _generate_characters(self, theme: str, genre: str) -> List[Dict[str, str]]:
        """Generate characters for a story"""
        prompt = f"""
Create 2-3 interesting characters for a {genre} story about: {theme}

For each character, provide:
1. Name
2. Age
3. Background/occupation
4. Key personality traits
5. Motivation/goal
6. Role in the story

Make the characters diverse and compelling.
"""
        
        characters_text = await generate_response(
            prompt=prompt,
            max_tokens=400,
            temperature=0.7,
            preferred_provider="openai"
        )
        
        # Parse characters (simplified parsing)
        characters = []
        lines = characters_text.split('\n')
        current_character = {}
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith(' '):
                if current_character:
                    characters.append(current_character)
                current_character = {"description": line}
            elif line:
                current_character["description"] += f" {line}"
        
        if current_character:
            characters.append(current_character)
        
        return characters[:3]  # Limit to 3 characters
    
    async def _generate_setting(self, theme: str, genre: str) -> str:
        """Generate a setting for a story"""
        prompt = f"""
Create an interesting setting for a {genre} story about: {theme}

Provide:
1. Time period
2. Location
3. Atmosphere/mood
4. Key environmental details

Make it vivid and appropriate for the theme and genre.
"""
        
        setting = await generate_response(
            prompt=prompt,
            max_tokens=200,
            temperature=0.7,
            preferred_provider="openai"
        )
        
        return setting.strip()
    
    async def _generate_plot(self, theme: str, characters: List[Dict], setting: str, genre: str) -> str:
        """Generate a plot outline"""
        prompt = f"""
Create a plot outline for a {genre} story about: {theme}

Setting: {setting}
Characters: {json.dumps(characters, indent=2)}

Provide:
1. Beginning/Setup
2. Rising Action/Conflict
3. Climax
4. Resolution/Ending

Make it engaging and appropriate for the genre.
"""
        
        plot = await generate_response(
            prompt=prompt,
            max_tokens=300,
            temperature=0.6,
            preferred_provider="openai"
        )
        
        return plot.strip()
    
    async def _generate_headline(self, product: str, audience: str) -> str:
        """Generate a marketing headline"""
        prompt = f"""
Create a compelling headline for: {product}

Target Audience: {audience}

Make it:
1. Attention-grabbing
2. Benefit-focused
3. Appropriate for the audience
4. Memorable

Return only the headline.
"""
        
        headline = await generate_response(
            prompt=prompt,
            max_tokens=30,
            temperature=0.8,
            preferred_provider="openai"
        )
        
        return headline.strip()
    
    async def _generate_tagline(self, product: str, tone: str) -> str:
        """Generate a marketing tagline"""
        prompt = f"""
Create a memorable tagline for: {product}

Tone: {tone}

Make it:
1. Short and punchy
2. Memorable
3. Brand-appropriate
4. Tone-consistent

Return only the tagline.
"""
        
        tagline = await generate_response(
            prompt=prompt,
            max_tokens=20,
            temperature=0.8,
            preferred_provider="openai"
        )
        
        return tagline.strip()


# Export the agent class
__all__ = ["CreativeAgent"]
