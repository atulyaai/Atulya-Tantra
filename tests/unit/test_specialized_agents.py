"""
Atulya Tantra - Specialized Agents Unit Tests
Version: 2.5.0
Comprehensive unit tests for specialized agents
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import uuid

# Import agents to test
from src.core.agents.specialized.code_agent import CodeAgent
from src.core.agents.specialized.research_agent import ResearchAgent
from src.core.agents.specialized.creative_agent import CreativeAgent
from src.core.agents.specialized.data_agent import DataAgent
from src.core.agents.agent_coordinator import AgentCoordinator
from src.core.agents.specialized.base_agent import AgentTask, AgentResult, AgentStatus, TaskComplexity


class TestCodeAgent:
    """Test CodeAgent"""
    
    @pytest.fixture
    def code_agent(self):
        return CodeAgent({"models": {}})
    
    @pytest.mark.asyncio
    async def test_can_handle_code_generation(self, code_agent):
        """Test code generation capability"""
        can_handle = await code_agent.can_handle("code_generation", {"language": "python"})
        assert can_handle is True
    
    @pytest.mark.asyncio
    async def test_can_handle_unsupported_task(self, code_agent):
        """Test unsupported task handling"""
        can_handle = await code_agent.can_handle("unsupported_task", {})
        assert can_handle is False
    
    @pytest.mark.asyncio
    async def test_process_code_generation_task(self, code_agent):
        """Test processing code generation task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="code_agent",
            task_type="code_generation",
            input_data={"specification": "Write a function to calculate factorial"},
            requirements={"language": "python"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await code_agent.process_task(task)
        
        assert result.success is True
        assert result.agent_id == "code_agent"
        assert result.result is not None
        assert "code" in result.result
        assert "language" in result.result
    
    @pytest.mark.asyncio
    async def test_process_code_analysis_task(self, code_agent):
        """Test processing code analysis task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="code_agent",
            task_type="code_analysis",
            input_data={"code": "def hello():\n    print('Hello, World!')"},
            requirements={"language": "python"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await code_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "language" in result.result
        assert "complexity_score" in result.result
        assert "issues" in result.result
    
    @pytest.mark.asyncio
    async def test_process_debugging_task(self, code_agent):
        """Test processing debugging task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="code_agent",
            task_type="debugging",
            input_data={"code": "def broken():\n    return x", "error": "NameError: name 'x' is not defined"},
            requirements={"language": "python"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await code_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "error_analysis" in result.result
        assert "potential_fixes" in result.result
    
    @pytest.mark.asyncio
    async def test_process_refactoring_task(self, code_agent):
        """Test processing refactoring task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="code_agent",
            task_type="refactoring",
            input_data={"code": "def long_function():\n    # Very long function\n    pass"},
            requirements={"language": "python"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await code_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "extract_methods" in result.result
        assert "rename_variables" in result.result
    
    @pytest.mark.asyncio
    async def test_health_check(self, code_agent):
        """Test health check"""
        health = await code_agent.health_check()
        
        assert "code_agent" in health
        assert health["code_agent"] is True
        assert "status" in health
        assert "supported_languages" in health


class TestResearchAgent:
    """Test ResearchAgent"""
    
    @pytest.fixture
    def research_agent(self):
        return ResearchAgent({"models": {}})
    
    @pytest.mark.asyncio
    async def test_can_handle_information_gathering(self, research_agent):
        """Test information gathering capability"""
        can_handle = await research_agent.can_handle("information_gathering", {"domain": "technology"})
        assert can_handle is True
    
    @pytest.mark.asyncio
    async def test_process_information_gathering_task(self, research_agent):
        """Test processing information gathering task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="research_agent",
            task_type="information_gathering",
            input_data={"topic": "artificial intelligence"},
            requirements={"domain": "technology"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await research_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "topic" in result.result
        assert "sources" in result.result
        assert "summary" in result.result
    
    @pytest.mark.asyncio
    async def test_process_fact_checking_task(self, research_agent):
        """Test processing fact checking task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="research_agent",
            task_type="fact_checking",
            input_data={"claim": "The Earth is flat"},
            requirements={"domain": "science"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await research_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "claim" in result.result
        assert "verification_status" in result.result
        assert "sources" in result.result
    
    @pytest.mark.asyncio
    async def test_process_analysis_task(self, research_agent):
        """Test processing analysis task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="research_agent",
            task_type="analysis",
            input_data={"information": "Market research data on AI adoption"},
            requirements={"analysis_type": "trend_analysis"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await research_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "analysis_type" in result.result
    
    @pytest.mark.asyncio
    async def test_process_citation_task(self, research_agent):
        """Test processing citation task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="research_agent",
            task_type="citation",
            input_data={"sources": [{"title": "AI Research Paper", "author": "Dr. Smith"}]},
            requirements={"style": "apa"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await research_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "citations" in result.result
        assert "style" in result.result
    
    @pytest.mark.asyncio
    async def test_health_check(self, research_agent):
        """Test health check"""
        health = await research_agent.health_check()
        
        assert "research_agent" in health
        assert health["research_agent"] is True
        assert "status" in health
        assert "supported_domains" in health


class TestCreativeAgent:
    """Test CreativeAgent"""
    
    @pytest.fixture
    def creative_agent(self):
        return CreativeAgent({"models": {}})
    
    @pytest.mark.asyncio
    async def test_can_handle_content_creation(self, creative_agent):
        """Test content creation capability"""
        can_handle = await creative_agent.can_handle("content_creation", {"content_type": "article"})
        assert can_handle is True
    
    @pytest.mark.asyncio
    async def test_process_content_creation_task(self, creative_agent):
        """Test processing content creation task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="creative_agent",
            task_type="content_creation",
            input_data={"topic": "The future of technology"},
            requirements={"content_type": "article", "style": "professional"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await creative_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "content_type" in result.result
        assert "title" in result.result
        assert "content" in result.result
    
    @pytest.mark.asyncio
    async def test_process_design_assistance_task(self, creative_agent):
        """Test processing design assistance task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="creative_agent",
            task_type="design_assistance",
            input_data={"context": "Website design for a tech company"},
            requirements={"design_type": "web_design"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await creative_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "design_type" in result.result
        assert "elements" in result.result
        assert "color_scheme" in result.result
    
    @pytest.mark.asyncio
    async def test_process_style_adaptation_task(self, creative_agent):
        """Test processing style adaptation task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="creative_agent",
            task_type="style_adaptation",
            input_data={"content": "This is a formal document"},
            requirements={"target_style": "casual", "target_audience": "general"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await creative_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "original_content" in result.result
        assert "adapted_content" in result.result
        assert "target_style" in result.result
    
    @pytest.mark.asyncio
    async def test_process_brainstorming_task(self, creative_agent):
        """Test processing brainstorming task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="creative_agent",
            task_type="brainstorming",
            input_data={"topic": "Innovative product ideas"},
            requirements={"idea_type": "product", "quantity": 5},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await creative_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "topic" in result.result
        assert "ideas" in result.result
        assert "categorized_ideas" in result.result
    
    @pytest.mark.asyncio
    async def test_health_check(self, creative_agent):
        """Test health check"""
        health = await creative_agent.health_check()
        
        assert "creative_agent" in health
        assert health["creative_agent"] is True
        assert "status" in health
        assert "supported_content_types" in health


class TestDataAgent:
    """Test DataAgent"""
    
    @pytest.fixture
    def data_agent(self):
        return DataAgent({"models": {}})
    
    @pytest.mark.asyncio
    async def test_can_handle_data_analysis(self, data_agent):
        """Test data analysis capability"""
        can_handle = await data_agent.can_handle("data_analysis", {"format": "csv"})
        assert can_handle is True
    
    @pytest.mark.asyncio
    async def test_process_data_analysis_task(self, data_agent):
        """Test processing data analysis task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="data_agent",
            task_type="data_analysis",
            input_data={"data": {"values": [1, 2, 3, 4, 5]}},
            requirements={"analysis_type": "descriptive", "format": "json"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await data_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "analysis_type" in result.result
        assert "dataset_info" in result.result
        assert "insights" in result.result
    
    @pytest.mark.asyncio
    async def test_process_data_processing_task(self, data_agent):
        """Test processing data processing task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="data_agent",
            task_type="data_processing",
            input_data={"data": {"values": [1, 2, 3, 4, 5]}},
            requirements={"operations": ["clean", "normalize"]},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await data_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "operation_type" in result.result
        assert "input_data_info" in result.result
        assert "output_data_info" in result.result
    
    @pytest.mark.asyncio
    async def test_process_data_visualization_task(self, data_agent):
        """Test processing data visualization task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="data_agent",
            task_type="data_visualization",
            input_data={"data": {"values": [1, 2, 3, 4, 5]}},
            requirements={"chart_type": "bar_chart", "title": "Sample Chart"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await data_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "chart_type" in result.result
        assert "title" in result.result
        assert "configuration" in result.result
    
    @pytest.mark.asyncio
    async def test_process_statistical_analysis_task(self, data_agent):
        """Test processing statistical analysis task"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="data_agent",
            task_type="statistical_analysis",
            input_data={"data": {"values": [1, 2, 3, 4, 5]}},
            requirements={"statistical_type": "descriptive"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await data_agent.process_task(task)
        
        assert result.success is True
        assert result.result is not None
        assert "mean" in result.result
        assert "median" in result.result
        assert "standard_deviation" in result.result
    
    @pytest.mark.asyncio
    async def test_health_check(self, data_agent):
        """Test health check"""
        health = await data_agent.health_check()
        
        assert "data_agent" in health
        assert health["data_agent"] is True
        assert "status" in health
        assert "supported_formats" in health


class TestAgentCoordinator:
    """Test AgentCoordinator"""
    
    @pytest.fixture
    def agent_coordinator(self):
        return AgentCoordinator({"models": {}})
    
    @pytest.mark.asyncio
    async def test_coordinate_complex_task(self, agent_coordinator):
        """Test coordinating a complex task"""
        task_id = await agent_coordinator.coordinate_complex_task(
            name="Test Task",
            description="Write a Python function and create documentation",
            goal="Complete development task",
            requirements={"language": "python", "include_docs": True}
        )
        
        assert task_id is not None
        assert isinstance(task_id, str)
    
    @pytest.mark.asyncio
    async def test_get_coordination_status(self, agent_coordinator):
        """Test getting coordination status"""
        # First create a task
        task_id = await agent_coordinator.coordinate_complex_task(
            name="Test Task",
            description="Test task description",
            goal="Test goal",
            requirements={}
        )
        
        # Get status
        status = await agent_coordinator.get_coordination_status(task_id)
        
        assert "task_id" in status
        assert "name" in status
        assert "status" in status
        assert "progress" in status
    
    @pytest.mark.asyncio
    async def test_suggest_agent_combination(self, agent_coordinator):
        """Test suggesting agent combinations"""
        combinations = await agent_coordinator.suggest_agent_combination(
            "Write a research paper about AI"
        )
        
        assert isinstance(combinations, list)
        assert len(combinations) > 0
        assert all(isinstance(combo, list) for combo in combinations)
    
    @pytest.mark.asyncio
    async def test_get_agent_collaboration_history(self, agent_coordinator):
        """Test getting agent collaboration history"""
        history = await agent_coordinator.get_agent_collaboration_history(limit=10)
        
        assert isinstance(history, list)
        assert len(history) <= 10
    
    @pytest.mark.asyncio
    async def test_health_check(self, agent_coordinator):
        """Test health check"""
        health = await agent_coordinator.health_check()
        
        assert "agent_coordinator" in health
        assert health["agent_coordinator"] is True
        assert "total_agents" in health
        assert "coordination_tasks" in health


# Performance tests
class TestAgentPerformance:
    """Performance tests for agents"""
    
    @pytest.mark.asyncio
    async def test_code_agent_performance(self):
        """Test code agent performance"""
        agent = CodeAgent({"models": {}})
        
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="code_agent",
            task_type="code_generation",
            input_data={"specification": "Write a simple function"},
            requirements={"language": "python"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        start_time = datetime.now()
        result = await agent.process_task(task)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        assert duration < 5.0  # Should complete within 5 seconds
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_research_agent_performance(self):
        """Test research agent performance"""
        agent = ResearchAgent({"models": {}})
        
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="research_agent",
            task_type="information_gathering",
            input_data={"topic": "machine learning"},
            requirements={"domain": "technology"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        start_time = datetime.now()
        result = await agent.process_task(task)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        assert duration < 5.0  # Should complete within 5 seconds
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_creative_agent_performance(self):
        """Test creative agent performance"""
        agent = CreativeAgent({"models": {}})
        
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="creative_agent",
            task_type="content_creation",
            input_data={"topic": "Technology trends"},
            requirements={"content_type": "article"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        start_time = datetime.now()
        result = await agent.process_task(task)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        assert duration < 5.0  # Should complete within 5 seconds
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_data_agent_performance(self):
        """Test data agent performance"""
        agent = DataAgent({"models": {}})
        
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="data_agent",
            task_type="data_analysis",
            input_data={"data": {"values": [1, 2, 3, 4, 5]}},
            requirements={"analysis_type": "descriptive"},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        start_time = datetime.now()
        result = await agent.process_task(task)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        assert duration < 5.0  # Should complete within 5 seconds
        assert result.success is True


# Error handling tests
class TestAgentErrorHandling:
    """Test error handling in agents"""
    
    @pytest.mark.asyncio
    async def test_code_agent_error_handling(self):
        """Test code agent error handling"""
        agent = CodeAgent({"models": {}})
        
        # Test with invalid task type
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="code_agent",
            task_type="invalid_task",
            input_data={},
            requirements={},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await agent.process_task(task)
        
        assert result.success is False
        assert result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_research_agent_error_handling(self):
        """Test research agent error handling"""
        agent = ResearchAgent({"models": {}})
        
        # Test with invalid task type
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="research_agent",
            task_type="invalid_task",
            input_data={},
            requirements={},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await agent.process_task(task)
        
        assert result.success is False
        assert result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_creative_agent_error_handling(self):
        """Test creative agent error handling"""
        agent = CreativeAgent({"models": {}})
        
        # Test with invalid task type
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="creative_agent",
            task_type="invalid_task",
            input_data={},
            requirements={},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await agent.process_task(task)
        
        assert result.success is False
        assert result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_data_agent_error_handling(self):
        """Test data agent error handling"""
        agent = DataAgent({"models": {}})
        
        # Test with invalid task type
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id="data_agent",
            task_type="invalid_task",
            input_data={},
            requirements={},
            priority=5,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        result = await agent.process_task(task)
        
        assert result.success is False
        assert result.error_message is not None


if __name__ == "__main__":
    pytest.main([__file__])
