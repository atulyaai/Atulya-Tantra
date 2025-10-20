"""
Atulya Tantra - Creative Agent
Version: 2.5.0
Specialized agent for creative content generation and design
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import uuid
import random
from src.core.agents.specialized.base_agent import BaseAgent, AgentCapability, AgentTask, AgentResult, AgentStatus, TaskComplexity

logger = logging.getLogger(__name__)


@dataclass
class CreativeContent:
    """Creative content result"""
    content_type: str
    title: str
    content: str
    style: str
    tone: str
    word_count: int
    tags: List[str]
    metadata: Dict[str, Any]


@dataclass
class DesignSuggestion:
    """Design suggestion result"""
    design_type: str
    elements: List[Dict[str, Any]]
    color_scheme: Dict[str, str]
    layout_suggestions: List[str]
    accessibility_notes: List[str]


class CreativeAgent:
    """Specialized agent for creative content generation and design"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.agent_id = "creative_agent"
        self.name = "Creative Agent"
        self.status = AgentStatus.IDLE
        
        # Creative capabilities
        self.supported_content_types = [
            "article", "blog_post", "story", "poem", "script", "advertisement",
            "social_media", "email", "presentation", "proposal"
        ]
        
        self.supported_design_types = [
            "web_design", "ui_design", "logo_design", "poster_design",
            "presentation_design", "infographic", "brand_identity"
        ]
        
        # Initialize capabilities
        self.capabilities = [
            AgentCapability(
                name="content_creation",
                description="Generate creative written content",
                supported_languages=["english"],
                supported_formats=["text", "markdown", "html"],
                max_complexity=TaskComplexity.COMPLEX,
                estimated_time=25
            ),
            AgentCapability(
                name="design_assistance",
                description="Provide design suggestions and feedback",
                supported_languages=["english"],
                supported_formats=["text", "json"],
                max_complexity=TaskComplexity.MODERATE,
                estimated_time=20
            ),
            AgentCapability(
                name="style_adaptation",
                description="Adapt content to different styles and tones",
                supported_languages=["english"],
                supported_formats=["text", "markdown"],
                max_complexity=TaskComplexity.MODERATE,
                estimated_time=15
            ),
            AgentCapability(
                name="brainstorming",
                description="Generate creative ideas and concepts",
                supported_languages=["english"],
                supported_formats=["text", "json"],
                max_complexity=TaskComplexity.SIMPLE,
                estimated_time=10
            )
        ]
        
        # Creative templates and styles
        self.templates = self._initialize_templates()
        self.styles = self._initialize_styles()
        
        logger.info("CreativeAgent initialized")
    
    async def can_handle(self, task_type: str, requirements: Dict[str, Any]) -> bool:
        """Check if agent can handle a specific task"""
        
        supported_types = ["content_creation", "design_assistance", "style_adaptation", "brainstorming"]
        if task_type not in supported_types:
            return False
        
        # Check content type support
        if "content_type" in requirements:
            content_type = requirements["content_type"]
            if content_type not in self.supported_content_types:
                return False
        
        return True
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process a creative task"""
        
        self.status = AgentStatus.PROCESSING
        start_time = datetime.now()
        
        try:
            if task.task_type == "content_creation":
                result = await self._create_content(task.input_data, task.requirements)
            elif task.task_type == "design_assistance":
                result = await self._assist_design(task.input_data, task.requirements)
            elif task.task_type == "style_adaptation":
                result = await self._adapt_style(task.input_data, task.requirements)
            elif task.task_type == "brainstorming":
                result = await self._brainstorm_ideas(task.input_data, task.requirements)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=True,
                result=result,
                metadata={
                    "task_type": task.task_type,
                    "content_type": task.requirements.get("content_type", "general"),
                    "style": task.requirements.get("style", "neutral")
                },
                execution_time=execution_time,
                confidence=0.85,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Creative agent task failed: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=False,
                result=None,
                metadata={"error": str(e)},
                execution_time=execution_time,
                confidence=0.0,
                timestamp=datetime.now()
            )
        finally:
            self.status = AgentStatus.IDLE
    
    async def _create_content(self, input_data: Dict[str, Any], requirements: Dict[str, Any]) -> CreativeContent:
        """Create creative content"""
        
        topic = input_data.get("topic", "")
        content_type = requirements.get("content_type", "article")
        style = requirements.get("style", "neutral")
        tone = requirements.get("tone", "professional")
        length = requirements.get("length", "medium")
        
        # Generate content based on type
        if content_type == "article":
            content = await self._generate_article(topic, style, tone, length)
        elif content_type == "blog_post":
            content = await self._generate_blog_post(topic, style, tone, length)
        elif content_type == "story":
            content = await self._generate_story(topic, style, tone, length)
        elif content_type == "poem":
            content = await self._generate_poem(topic, style, tone, length)
        elif content_type == "script":
            content = await self._generate_script(topic, style, tone, length)
        elif content_type == "advertisement":
            content = await self._generate_advertisement(topic, style, tone, length)
        else:
            content = await self._generate_generic_content(topic, content_type, style, tone, length)
        
        # Generate title
        title = await self._generate_title(topic, content_type, style)
        
        # Extract tags
        tags = await self._extract_tags(topic, content)
        
        return CreativeContent(
            content_type=content_type,
            title=title,
            content=content,
            style=style,
            tone=tone,
            word_count=len(content.split()),
            tags=tags,
            metadata={
                "generated_at": datetime.now().isoformat(),
                "template_used": f"{content_type}_{style}",
                "creativity_score": random.uniform(0.7, 0.95)
            }
        )
    
    async def _assist_design(self, input_data: Dict[str, Any], requirements: Dict[str, Any]) -> DesignSuggestion:
        """Provide design assistance"""
        
        design_type = requirements.get("design_type", "web_design")
        context = input_data.get("context", "")
        brand_info = input_data.get("brand_info", {})
        
        # Generate design suggestions
        elements = await self._suggest_design_elements(design_type, context, brand_info)
        color_scheme = await self._suggest_color_scheme(brand_info)
        layout_suggestions = await self._suggest_layout(design_type, context)
        accessibility_notes = await self._generate_accessibility_notes(design_type)
        
        return DesignSuggestion(
            design_type=design_type,
            elements=elements,
            color_scheme=color_scheme,
            layout_suggestions=layout_suggestions,
            accessibility_notes=accessibility_notes
        )
    
    async def _adapt_style(self, input_data: Dict[str, Any], requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt content to different styles"""
        
        original_content = input_data.get("content", "")
        target_style = requirements.get("target_style", "professional")
        target_audience = requirements.get("audience", "general")
        
        # Adapt content to new style
        adapted_content = await self._adapt_content_style(original_content, target_style, target_audience)
        
        return {
            "original_content": original_content,
            "adapted_content": adapted_content,
            "target_style": target_style,
            "target_audience": target_audience,
            "adaptation_notes": await self._generate_adaptation_notes(target_style, target_audience)
        }
    
    async def _brainstorm_ideas(self, input_data: Dict[str, Any], requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Generate creative ideas through brainstorming"""
        
        topic = input_data.get("topic", "")
        idea_type = requirements.get("idea_type", "general")
        quantity = requirements.get("quantity", 5)
        
        # Generate ideas
        ideas = await self._generate_ideas(topic, idea_type, quantity)
        
        # Categorize ideas
        categorized_ideas = await self._categorize_ideas(ideas)
        
        return {
            "topic": topic,
            "idea_type": idea_type,
            "ideas": ideas,
            "categorized_ideas": categorized_ideas,
            "total_count": len(ideas),
            "brainstorming_technique": "free_association"
        }
    
    async def _generate_article(self, topic: str, style: str, tone: str, length: str) -> str:
        """Generate an article"""
        
        template = self.templates.get("article", {}).get(style, self.templates["article"]["default"])
        
        # Generate article sections
        introduction = await self._generate_introduction(topic, tone)
        body_sections = await self._generate_body_sections(topic, length)
        conclusion = await self._generate_conclusion(topic, tone)
        
        article = f"""
{introduction}

{body_sections}

{conclusion}
"""
        
        return article.strip()
    
    async def _generate_blog_post(self, topic: str, style: str, tone: str, length: str) -> str:
        """Generate a blog post"""
        
        # Blog posts are more conversational
        conversational_tone = "casual" if tone == "professional" else tone
        
        introduction = await self._generate_blog_introduction(topic, conversational_tone)
        body = await self._generate_blog_body(topic, length)
        conclusion = await self._generate_blog_conclusion(topic, conversational_tone)
        
        return f"""
{introduction}

{body}

{conclusion}
"""
    
    async def _generate_story(self, topic: str, style: str, tone: str, length: str) -> str:
        """Generate a creative story"""
        
        # Story elements
        characters = await self._create_characters(topic)
        setting = await self._create_setting(topic)
        plot = await self._create_plot(topic, length)
        
        story = f"""
# {topic}

## Setting
{setting}

## Characters
{characters}

## Story
{plot}
"""
        
        return story.strip()
    
    async def _generate_poem(self, topic: str, style: str, tone: str, length: str) -> str:
        """Generate a poem"""
        
        poem_lines = []
        
        # Generate poem based on style
        if style == "haiku":
            poem_lines = await self._generate_haiku(topic)
        elif style == "sonnet":
            poem_lines = await self._generate_sonnet(topic)
        elif style == "free_verse":
            poem_lines = await self._generate_free_verse(topic, length)
        else:
            poem_lines = await self._generate_rhyming_poem(topic, length)
        
        return "\n".join(poem_lines)
    
    async def _generate_script(self, topic: str, style: str, tone: str, length: str) -> str:
        """Generate a script"""
        
        # Script elements
        characters = await self._create_script_characters(topic)
        scenes = await self._create_scenes(topic, length)
        
        script = f"""
# {topic} - Script

## Characters
{characters}

## Scenes
{scenes}
"""
        
        return script.strip()
    
    async def _generate_advertisement(self, topic: str, style: str, tone: str, length: str) -> str:
        """Generate an advertisement"""
        
        headline = await self._generate_headline(topic, style)
        body_copy = await self._generate_body_copy(topic, tone, length)
        call_to_action = await self._generate_call_to_action(topic, style)
        
        return f"""
{headline}

{body_copy}

{call_to_action}
"""
    
    async def _generate_generic_content(self, topic: str, content_type: str, style: str, tone: str, length: str) -> str:
        """Generate generic content"""
        
        return f"""
# {topic}

This is a {content_type} about {topic} written in a {style} style with a {tone} tone.

The content explores various aspects of {topic} and provides insights that are relevant to the audience.

Key points covered include:
- Introduction to {topic}
- Main concepts and ideas
- Practical applications
- Future considerations

This {content_type} aims to provide valuable information about {topic} in an engaging and accessible format.
"""
    
    async def _generate_title(self, topic: str, content_type: str, style: str) -> str:
        """Generate a title for the content"""
        
        title_templates = {
            "article": [
                f"The Complete Guide to {topic}",
                f"Understanding {topic}: A Comprehensive Overview",
                f"{topic}: What You Need to Know"
            ],
            "blog_post": [
                f"My Thoughts on {topic}",
                f"Exploring {topic}: A Personal Perspective",
                f"Why {topic} Matters More Than You Think"
            ],
            "story": [
                f"The Tale of {topic}",
                f"Adventures in {topic}",
                f"{topic}: A Story of Discovery"
            ]
        }
        
        templates = title_templates.get(content_type, title_templates["article"])
        return random.choice(templates)
    
    async def _extract_tags(self, topic: str, content: str) -> List[str]:
        """Extract relevant tags from content"""
        
        # Simple tag extraction
        words = content.lower().split()
        common_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "a", "an", "is", "are", "was", "were"}
        
        # Get frequent words that aren't common
        word_freq = {}
        for word in words:
            if word not in common_words and len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top words as tags
        tags = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        return [tag[0] for tag in tags]
    
    async def _suggest_design_elements(self, design_type: str, context: str, brand_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Suggest design elements"""
        
        elements = []
        
        if design_type == "web_design":
            elements = [
                {"type": "header", "suggestion": "Clean, minimal header with clear navigation"},
                {"type": "hero_section", "suggestion": "Compelling hero section with call-to-action"},
                {"type": "content_blocks", "suggestion": "Well-organized content blocks with proper spacing"},
                {"type": "footer", "suggestion": "Informative footer with links and contact info"}
            ]
        elif design_type == "logo_design":
            elements = [
                {"type": "icon", "suggestion": "Simple, memorable icon that represents the brand"},
                {"type": "typography", "suggestion": "Clean, readable typography that matches brand personality"},
                {"type": "color", "suggestion": "Strategic use of brand colors for impact"}
            ]
        
        return elements
    
    async def _suggest_color_scheme(self, brand_info: Dict[str, Any]) -> Dict[str, str]:
        """Suggest color scheme"""
        
        brand_personality = brand_info.get("personality", "professional")
        
        color_schemes = {
            "professional": {
                "primary": "#2563eb",
                "secondary": "#64748b",
                "accent": "#059669",
                "neutral": "#f8fafc"
            },
            "creative": {
                "primary": "#7c3aed",
                "secondary": "#ec4899",
                "accent": "#f59e0b",
                "neutral": "#fef3c7"
            },
            "minimal": {
                "primary": "#000000",
                "secondary": "#6b7280",
                "accent": "#ffffff",
                "neutral": "#f9fafb"
            }
        }
        
        return color_schemes.get(brand_personality, color_schemes["professional"])
    
    async def _suggest_layout(self, design_type: str, context: str) -> List[str]:
        """Suggest layout options"""
        
        layouts = {
            "web_design": [
                "Single column layout for mobile-first design",
                "Grid-based layout for content organization",
                "Card-based layout for modern appearance"
            ],
            "presentation_design": [
                "Title slide with clear hierarchy",
                "Content slides with consistent formatting",
                "Summary slide with key takeaways"
            ]
        }
        
        return layouts.get(design_type, ["Standard layout with clear visual hierarchy"])
    
    async def _generate_accessibility_notes(self, design_type: str) -> List[str]:
        """Generate accessibility notes"""
        
        return [
            "Ensure sufficient color contrast ratios (4.5:1 for normal text)",
            "Use semantic HTML elements for screen readers",
            "Provide alt text for all images",
            "Ensure keyboard navigation is possible",
            "Use descriptive link text and button labels"
        ]
    
    async def _adapt_content_style(self, content: str, target_style: str, target_audience: str) -> str:
        """Adapt content to new style"""
        
        # Simple style adaptation
        if target_style == "casual" and "professional" in content.lower():
            adapted = content.replace("professional", "friendly")
            adapted = adapted.replace("utilize", "use")
            adapted = adapted.replace("facilitate", "help")
        elif target_style == "formal" and "casual" in content.lower():
            adapted = content.replace("casual", "professional")
            adapted = adapted.replace("use", "utilize")
            adapted = adapted.replace("help", "facilitate")
        else:
            adapted = content
        
        return adapted
    
    async def _generate_adaptation_notes(self, target_style: str, target_audience: str) -> List[str]:
        """Generate notes about the adaptation"""
        
        return [
            f"Content adapted for {target_style} style",
            f"Target audience: {target_audience}",
            "Vocabulary adjusted for appropriate tone",
            "Sentence structure modified for clarity",
            "Examples updated to match audience interests"
        ]
    
    async def _generate_ideas(self, topic: str, idea_type: str, quantity: int) -> List[str]:
        """Generate creative ideas"""
        
        ideas = []
        
        for i in range(quantity):
            if idea_type == "marketing":
                ideas.append(f"Create a viral social media campaign about {topic}")
            elif idea_type == "product":
                ideas.append(f"Develop a new product that solves {topic} problems")
            elif idea_type == "content":
                ideas.append(f"Write an engaging article about {topic}")
            else:
                ideas.append(f"Creative idea #{i+1}: {topic} innovation")
        
        return ideas
    
    async def _categorize_ideas(self, ideas: List[str]) -> Dict[str, List[str]]:
        """Categorize ideas by type"""
        
        categories = {
            "marketing": [],
            "product": [],
            "content": [],
            "other": []
        }
        
        for idea in ideas:
            if "campaign" in idea.lower() or "marketing" in idea.lower():
                categories["marketing"].append(idea)
            elif "product" in idea.lower() or "develop" in idea.lower():
                categories["product"].append(idea)
            elif "article" in idea.lower() or "write" in idea.lower():
                categories["content"].append(idea)
            else:
                categories["other"].append(idea)
        
        return categories
    
    # Helper methods for content generation
    async def _generate_introduction(self, topic: str, tone: str) -> str:
        """Generate introduction section"""
        return f"# Introduction to {topic}\n\nThis comprehensive guide explores the fascinating world of {topic} and its many applications."
    
    async def _generate_body_sections(self, topic: str, length: str) -> str:
        """Generate body sections"""
        return f"## Understanding {topic}\n\n{topic} represents a significant area of study with numerous practical applications."
    
    async def _generate_conclusion(self, topic: str, tone: str) -> str:
        """Generate conclusion section"""
        return f"## Conclusion\n\nIn conclusion, {topic} offers valuable insights and opportunities for further exploration."
    
    async def _generate_blog_introduction(self, topic: str, tone: str) -> str:
        """Generate blog introduction"""
        return f"# {topic}: My Take\n\nLet me share my thoughts on {topic} and why it matters."
    
    async def _generate_blog_body(self, topic: str, length: str) -> str:
        """Generate blog body"""
        return f"## Why {topic} Matters\n\n{topic} is more important than you might think. Here's why..."
    
    async def _generate_blog_conclusion(self, topic: str, tone: str) -> str:
        """Generate blog conclusion"""
        return f"## Final Thoughts\n\nWhat do you think about {topic}? Let me know in the comments!"
    
    async def _create_characters(self, topic: str) -> str:
        """Create story characters"""
        return f"## Characters\n\n- **Alex**: A curious explorer interested in {topic}\n- **Sam**: An expert guide who knows everything about {topic}"
    
    async def _create_setting(self, topic: str) -> str:
        """Create story setting"""
        return f"## Setting\n\nThe story takes place in a world where {topic} plays a central role."
    
    async def _create_plot(self, topic: str, length: str) -> str:
        """Create story plot"""
        return f"## Story\n\nAlex discovers the secrets of {topic} and embarks on an adventure to understand its mysteries."
    
    async def _generate_haiku(self, topic: str) -> List[str]:
        """Generate haiku"""
        return [
            f"{topic} flows free",
            "Nature's rhythm guides us all",
            "Peace in simple things"
        ]
    
    async def _generate_sonnet(self, topic: str) -> List[str]:
        """Generate sonnet"""
        return [
            f"Shall I compare thee to a {topic}?",
            "Thou art more lovely and more temperate:",
            "Rough winds do shake the darling buds of May,",
            "And summer's lease hath all too short a date."
        ]
    
    async def _generate_free_verse(self, topic: str, length: str) -> List[str]:
        """Generate free verse"""
        return [
            f"{topic}",
            "flows like water",
            "through the mind",
            "creating patterns",
            "of understanding"
        ]
    
    async def _generate_rhyming_poem(self, topic: str, length: str) -> List[str]:
        """Generate rhyming poem"""
        return [
            f"In the world of {topic},",
            "Where dreams come true,",
            "There's magic in the air,",
            "And skies so blue."
        ]
    
    async def _create_script_characters(self, topic: str) -> str:
        """Create script characters"""
        return f"## Characters\n\n- **Narrator**: Voice of authority on {topic}\n- **Expert**: Provides technical details about {topic}"
    
    async def _create_scenes(self, topic: str, length: str) -> str:
        """Create script scenes"""
        return f"## Scene 1: Introduction\n\nNarrator: Welcome to our exploration of {topic}."
    
    async def _generate_headline(self, topic: str, style: str) -> str:
        """Generate advertisement headline"""
        return f"Discover the Power of {topic}!"
    
    async def _generate_body_copy(self, topic: str, tone: str, length: str) -> str:
        """Generate advertisement body copy"""
        return f"Transform your life with {topic}. Experience the difference today."
    
    async def _generate_call_to_action(self, topic: str, style: str) -> str:
        """Generate call to action"""
        return "Get started now and see the results!"
    
    def _initialize_templates(self) -> Dict[str, Any]:
        """Initialize content templates"""
        return {
            "article": {
                "default": "Standard article template",
                "professional": "Professional article template",
                "casual": "Casual article template"
            },
            "blog_post": {
                "default": "Standard blog post template",
                "personal": "Personal blog post template"
            }
        }
    
    def _initialize_styles(self) -> Dict[str, Any]:
        """Initialize writing styles"""
        return {
            "professional": "Formal, business-like tone",
            "casual": "Friendly, conversational tone",
            "academic": "Scholarly, research-based tone",
            "creative": "Imaginative, artistic tone"
        }
    
    async def get_capabilities(self) -> List[AgentCapability]:
        """Get detailed capabilities"""
        return self.capabilities
    
    async def health_check(self) -> Dict[str, Any]:
        """Check agent health"""
        return {
            "creative_agent": True,
            "status": self.status.value,
            "supported_content_types": self.supported_content_types,
            "supported_design_types": self.supported_design_types,
            "capabilities": len(self.capabilities),
            "templates_available": len(self.templates),
            "styles_available": len(self.styles)
        }
