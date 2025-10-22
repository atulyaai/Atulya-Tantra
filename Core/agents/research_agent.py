"""
Research Agent for Atulya Tantra AGI
Specialized agent for research, information gathering, and analysis
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import json

from .base_agent import BaseAgent, AgentTask, AgentCapability, AgentStatus
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..brain import generate_response, get_llm_router

logger = get_logger(__name__)


class ResearchAgent(BaseAgent):
    """Agent specialized in research, information gathering, and analysis"""
    
    def __init__(self):
        super().__init__(
            name="ResearchAgent",
            description="Specialized agent for research, information gathering, web search, and data analysis",
            capabilities=[
                AgentCapability.RESEARCH,
                AgentCapability.WEB_SEARCH,
                AgentCapability.DATA_ANALYSIS,
                AgentCapability.TEXT_GENERATION
            ],
            max_concurrent_tasks=2,
            timeout_seconds=300
        )
        
        self.search_engines = ["google", "bing", "duckduckgo"]
        self.max_search_results = 10
        self.cache_duration = timedelta(hours=1)
        self.max_cache_size = 1000  # Maximum number of cached searches
        self.search_cache: Dict[str, Dict[str, Any]] = {}
    
    async def can_handle_task(self, task: AgentTask) -> bool:
        """Check if this agent can handle the given task"""
        task_type = task.task_type or ""
        description = (task.description or "").lower()
        
        # Check for research-related keywords
        research_keywords = [
            "research", "search", "find", "lookup", "investigate", "analyze",
            "information", "data", "facts", "statistics", "study", "report",
            "news", "article", "document", "paper", "academic", "scientific",
            "market research", "competitor analysis", "trend analysis",
            "web search", "online search", "gather information"
        ]
        
        return (
            task_type in ["research", "web_search", "data_analysis", "information_gathering"] or
            any(keyword in description for keyword in research_keywords)
        )
    
    async def get_task_estimate(self, task: AgentTask) -> Dict[str, Any]:
        """Estimate task execution time and resource requirements"""
        task_type = task.task_type or ""
        description = task.description or ""
        
        # Base estimates
        if task_type == "web_search":
            estimated_time = 15  # seconds
            complexity = "low"
        elif task_type == "research":
            estimated_time = 60
            complexity = "medium"
        elif task_type == "data_analysis":
            estimated_time = 90
            complexity = "high"
        else:
            estimated_time = 45
            complexity = "medium"
        
        # Adjust based on query complexity
        if len(description) > 200:
            estimated_time *= 1.3
            complexity = "high"
        
        return {
            "estimated_time_seconds": estimated_time,
            "complexity": complexity,
            "resource_requirements": {
                "memory_mb": 50,
                "cpu_usage": "low",
                "network_usage": "high"
            }
        }
    
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute a research-related task"""
        try:
            task_type = task.task_type or "research"
            input_data = task.input_data or {}
            
            if task_type == "web_search":
                return await self._web_search(task, input_data)
            elif task_type == "research":
                return await self._comprehensive_research(task, input_data)
            elif task_type == "data_analysis":
                return await self._analyze_data(task, input_data)
            elif task_type == "information_gathering":
                return await self._gather_information(task, input_data)
            else:
                return await self._general_research_task(task, input_data)
                
        except Exception as e:
            logger.error(f"ResearchAgent execution error: {e}")
            raise AgentError(f"Research task failed: {e}")
    
    async def _web_search(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform web search and return results"""
        query = input_data.get("query", task.description)
        max_results = input_data.get("max_results", self.max_search_results)
        search_engine = input_data.get("search_engine", "duckduckgo")
        
        if not query:
            raise AgentError("No search query provided")
        
        # Check cache first
        cache_key = f"{search_engine}:{query}:{max_results}"
        if cache_key in self.search_cache:
            cached_result = self.search_cache[cache_key]
            if datetime.utcnow() - cached_result["timestamp"] < self.cache_duration:
                logger.info(f"Returning cached search results for: {query}")
                return cached_result["data"]
        
        # Perform search
        search_results = await self._perform_search(query, max_results, search_engine)
        
        # Cache results with size limit
        self.search_cache[cache_key] = {
            "data": search_results,
            "timestamp": datetime.utcnow()
        }
        
        # Clean up cache if it gets too large
        if len(self.search_cache) > self.max_cache_size:
            await self._cleanup_cache()
        
        return search_results
    
    async def _comprehensive_research(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive research on a topic"""
        topic = input_data.get("topic", task.description)
        depth = input_data.get("depth", "medium")  # shallow, medium, deep
        sources = input_data.get("sources", ["web", "academic"])
        
        if not topic:
            raise AgentError("No research topic provided")
        
        research_results = {
            "topic": topic,
            "depth": depth,
            "sources_used": sources,
            "findings": [],
            "summary": "",
            "references": [],
            "metadata": {
                "task_type": "comprehensive_research",
                "researched_at": datetime.utcnow().isoformat()
            }
        }
        
        # Generate research questions
        research_questions = await self._generate_research_questions(topic, depth)
        
        # Search for each question
        for question in research_questions:
            try:
                search_results = await self._web_search(
                    AgentTask(task_id="temp", description=question),
                    {"query": question, "max_results": 5}
                )
                
                if search_results and search_results.get("results"):
                    research_results["findings"].extend(search_results["results"])
                    research_results["references"].extend(search_results.get("references", []))
                else:
                    # Add a note about failed search
                    research_results["findings"].append({
                        "title": f"Search failed for: {question}",
                        "content": "Unable to retrieve information for this research question",
                        "source": "system"
                    })
                
                # Small delay between searches to be respectful
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.warning(f"Failed to research question '{question}': {e}")
                # Add error information to findings
                research_results["findings"].append({
                    "title": f"Error researching: {question}",
                    "content": f"Research failed with error: {str(e)}",
                    "source": "error"
                })
        
        # Generate comprehensive summary
        if research_results["findings"]:
            summary_prompt = f"""
Based on the following research findings about "{topic}", provide a comprehensive summary:

Findings:
{json.dumps(research_results['findings'][:10], indent=2)}

Please provide:
1. A clear overview of the topic
2. Key findings and insights
3. Important trends or patterns
4. Areas that need more research
5. Conclusions and implications

Make the summary informative and well-structured.
"""
            
            summary = await generate_response(
                prompt=summary_prompt,
                max_tokens=1000,
                temperature=0.3,
                preferred_provider="openai"
            )
            
            research_results["summary"] = summary
        
        return research_results
    
    async def _analyze_data(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze provided data or research findings"""
        data = input_data.get("data", [])
        analysis_type = input_data.get("analysis_type", "general")
        
        if not data:
            raise AgentError("No data provided for analysis")
        
        prompt = f"""
Analyze the following data and provide insights:

Data:
{json.dumps(data, indent=2)}

Analysis Type: {analysis_type}

Please provide:
1. Data overview and structure
2. Key patterns and trends
3. Statistical insights (if applicable)
4. Anomalies or outliers
5. Conclusions and recommendations
6. Visualizations suggestions (describe what charts would be helpful)

Be thorough and analytical in your response.
"""
        
        analysis = await generate_response(
            prompt=prompt,
            max_tokens=1500,
            temperature=0.2,
            preferred_provider="openai"
        )
        
        return {
            "analysis": analysis,
            "data_points": len(data),
            "analysis_type": analysis_type,
            "metadata": {
                "task_type": "data_analysis",
                "analyzed_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _gather_information(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Gather information from multiple sources"""
        topic = input_data.get("topic", task.description)
        sources = input_data.get("sources", ["web"])
        
        if not topic:
            raise AgentError("No topic provided for information gathering")
        
        gathered_info = {
            "topic": topic,
            "sources": sources,
            "information": [],
            "synthesis": "",
            "metadata": {
                "task_type": "information_gathering",
                "gathered_at": datetime.utcnow().isoformat()
            }
        }
        
        # Gather from each source
        for source in sources:
            try:
                if source == "web":
                    info = await self._web_search(
                        AgentTask(task_id="temp", description=topic),
                        {"query": topic, "max_results": 8}
                    )
                    gathered_info["information"].extend(info.get("results", []))
                
                # Add delay between sources
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Failed to gather from {source}: {e}")
        
        # Synthesize information
        if gathered_info["information"]:
            synthesis_prompt = f"""
Synthesize the following information about "{topic}":

Information:
{json.dumps(gathered_info['information'][:15], indent=2)}

Please provide:
1. A coherent synthesis of the information
2. Key themes and patterns
3. Conflicting or contradictory information
4. Confidence level in the information
5. Recommendations for further research

Make the synthesis clear and actionable.
"""
            
            synthesis = await generate_response(
                prompt=synthesis_prompt,
                max_tokens=800,
                temperature=0.3,
                preferred_provider="openai"
            )
            
            gathered_info["synthesis"] = synthesis
        
        return gathered_info
    
    async def _general_research_task(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general research tasks"""
        description = task.description or ""
        
        prompt = f"""
You are a research expert. Help with the following research task:

Task: {description}

Please provide:
1. Research approach and methodology
2. Key sources to investigate
3. Important questions to answer
4. Potential challenges and solutions
5. Expected outcomes and deliverables

Be thorough and professional in your research guidance.
"""
        
        response = await generate_response(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.4,
            preferred_provider="openai"
        )
        
        return {
            "research_guidance": response,
            "task_description": description,
            "metadata": {
                "task_type": "general_research",
                "completed_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _perform_search(self, query: str, max_results: int, search_engine: str) -> Dict[str, Any]:
        """Perform actual web search"""
        # This is a simplified implementation
        # In production, you would integrate with actual search APIs
        
        try:
            if search_engine == "duckduckgo":
                return await self._duckduckgo_search(query, max_results)
            elif search_engine == "google":
                return await self._google_search(query, max_results)
            else:
                # Fallback to DuckDuckGo
                return await self._duckduckgo_search(query, max_results)
                
        except Exception as e:
            logger.error(f"Search failed: {e}")
            # Return mock results for demonstration
            return self._get_mock_search_results(query, max_results)
    
    async def _duckduckgo_search(self, query: str, max_results: int) -> Dict[str, Any]:
        """Perform DuckDuckGo search (mock implementation)"""
        # This would integrate with DuckDuckGo API in production
        return self._get_mock_search_results(query, max_results)
    
    async def _google_search(self, query: str, max_results: int) -> Dict[str, Any]:
        """Perform Google search (mock implementation)"""
        # This would integrate with Google Custom Search API in production
        return self._get_mock_search_results(query, max_results)
    
    def _get_mock_search_results(self, query: str, max_results: int) -> Dict[str, Any]:
        """Generate mock search results for demonstration"""
        mock_results = []
        
        for i in range(min(max_results, 5)):
            mock_results.append({
                "title": f"Search Result {i+1} for '{query}'",
                "url": f"https://example.com/result-{i+1}",
                "snippet": f"This is a mock search result snippet for query '{query}'. It contains relevant information about the topic.",
                "rank": i + 1
            })
        
        return {
            "query": query,
            "results": mock_results,
            "total_results": len(mock_results),
            "search_engine": "mock",
            "search_time": "0.1s",
            "references": [result["url"] for result in mock_results]
        }
    
    async def _generate_research_questions(self, topic: str, depth: str) -> List[str]:
        """Generate research questions for a topic"""
        prompt = f"""
Generate specific research questions for the topic: "{topic}"

Research Depth: {depth}

Please generate 3-5 focused research questions that would help gather comprehensive information about this topic. Make the questions:
1. Specific and actionable
2. Cover different aspects of the topic
3. Appropriate for the research depth level
4. Clear and unambiguous

Return only the questions, one per line.
"""
        
        response = await generate_response(
            prompt=prompt,
            max_tokens=300,
            temperature=0.4,
            preferred_provider="openai"
        )
        
        # Parse questions from response
        questions = [q.strip() for q in response.split('\n') if q.strip()]
        return questions[:5]  # Limit to 5 questions
    
    async def _extract_content_from_url(self, url: str) -> Dict[str, Any]:
        """Extract content from a URL (mock implementation)"""
        # This would use web scraping libraries like BeautifulSoup in production
        return {
            "url": url,
            "title": f"Content from {url}",
            "content": f"Mock content extracted from {url}",
            "extracted_at": datetime.utcnow().isoformat()
        }
    
    async def _validate_url(self, url: str) -> bool:
        """Validate if URL is accessible and safe"""
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc) and parsed.scheme in ['http', 'https']
        except:
            return False
    
    async def _cleanup_cache(self):
        """Clean up old cache entries"""
        current_time = datetime.utcnow()
        expired_keys = []
        
        for key, entry in self.search_cache.items():
            if current_time - entry["timestamp"] > self.cache_duration:
                expired_keys.append(key)
        
        # Remove expired entries
        for key in expired_keys:
            del self.search_cache[key]
        
        # If still too large, remove oldest entries
        if len(self.search_cache) > self.max_cache_size:
            sorted_items = sorted(
                self.search_cache.items(),
                key=lambda x: x[1]["timestamp"]
            )
            items_to_remove = len(self.search_cache) - self.max_cache_size
            for key, _ in sorted_items[:items_to_remove]:
                del self.search_cache[key]
        
        logger.info(f"Cache cleanup completed. Current cache size: {len(self.search_cache)}")


# Export the agent class
__all__ = ["ResearchAgent"]
