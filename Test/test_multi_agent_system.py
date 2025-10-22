#!/usr/bin/env python3
"""
Test script for Atulya Tantra AGI Multi-Agent System
Tests agent framework, orchestration, and specialized agents
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.agents import (
    get_orchestrator, submit_task, get_task_status, cancel_task,
    CodeAgent, ResearchAgent, CreativeAgent, DataAgent, SystemAgent,
    AgentPriority, AgentCapability
)
from Core.config.logging import get_logger

logger = get_logger(__name__)


async def test_agent_registration():
    """Test agent registration and availability"""
    print("🤖 Testing agent registration...")
    
    try:
        orchestrator = await get_orchestrator()
        
        # Create and register agents
        code_agent = CodeAgent()
        research_agent = ResearchAgent()
        creative_agent = CreativeAgent()
        data_agent = DataAgent()
        system_agent = SystemAgent()
        
        orchestrator.registry.register_agent(code_agent)
        orchestrator.registry.register_agent(research_agent)
        orchestrator.registry.register_agent(creative_agent)
        orchestrator.registry.register_agent(data_agent)
        orchestrator.registry.register_agent(system_agent)
        
        # Check agent status
        status = orchestrator.registry.get_agent_status()
        
        print(f"✅ Registered {len(status)} agents:")
        for agent_id, agent_info in status.items():
            print(f"  - {agent_info['name']}: {agent_info['status']} ({len(agent_info['capabilities'])} capabilities)")
        
        return True
        
    except Exception as e:
        logger.error(f"Agent registration test failed: {e}")
        print(f"❌ Agent registration failed: {e}")
        return False


async def test_code_agent():
    """Test Code Agent functionality"""
    print("\n💻 Testing Code Agent...")
    
    try:
        # Submit a code generation task
        task_id = await submit_task(
            agent_type="CodeAgent",
            task_type="code_generation",
            description="Write a Python function to calculate fibonacci numbers",
            input_data={
                "language": "python",
                "requirements": "Function should be efficient and handle edge cases"
            },
            priority=AgentPriority.NORMAL,
            timeout_seconds=60
        )
        
        print(f"✅ Submitted code generation task: {task_id}")
        
        # Wait for task completion
        max_wait = 30  # seconds
        wait_time = 0
        
        while wait_time < max_wait:
            status = await get_task_status(task_id)
            if status:
                print(f"  Task status: {status['status']}")
                if status['status'] in ['completed', 'failed']:
                    break
            
            await asyncio.sleep(2)
            wait_time += 2
        
        # Get final status
        final_status = await get_task_status(task_id)
        if final_status and final_status['status'] == 'completed':
            print(f"✅ Code generation completed successfully")
            if final_status.get('result'):
                print(f"  Generated code preview: {str(final_status['result'])[:200]}...")
            return True
        else:
            print(f"❌ Code generation failed: {final_status.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"Code agent test failed: {e}")
        print(f"❌ Code agent test failed: {e}")
        return False


async def test_research_agent():
    """Test Research Agent functionality"""
    print("\n🔍 Testing Research Agent...")
    
    try:
        # Submit a research task
        task_id = await submit_task(
            agent_type="ResearchAgent",
            task_type="web_search",
            description="Research the latest trends in artificial intelligence",
            input_data={
                "query": "artificial intelligence trends 2024",
                "max_results": 5
            },
            priority=AgentPriority.NORMAL,
            timeout_seconds=60
        )
        
        print(f"✅ Submitted research task: {task_id}")
        
        # Wait for completion
        max_wait = 30
        wait_time = 0
        
        while wait_time < max_wait:
            status = await get_task_status(task_id)
            if status and status['status'] in ['completed', 'failed']:
                break
            await asyncio.sleep(2)
            wait_time += 2
        
        final_status = await get_task_status(task_id)
        if final_status and final_status['status'] == 'completed':
            print(f"✅ Research completed successfully")
            return True
        else:
            print(f"❌ Research failed: {final_status.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"Research agent test failed: {e}")
        print(f"❌ Research agent test failed: {e}")
        return False


async def test_creative_agent():
    """Test Creative Agent functionality"""
    print("\n🎨 Testing Creative Agent...")
    
    try:
        # Submit a creative writing task
        task_id = await submit_task(
            agent_type="CreativeAgent",
            task_type="creative_writing",
            description="Write a short story about a robot learning to paint",
            input_data={
                "content_type": "story",
                "style": "creative",
                "tone": "inspiring",
                "length": "short"
            },
            priority=AgentPriority.NORMAL,
            timeout_seconds=60
        )
        
        print(f"✅ Submitted creative writing task: {task_id}")
        
        # Wait for completion
        max_wait = 30
        wait_time = 0
        
        while wait_time < max_wait:
            status = await get_task_status(task_id)
            if status and status['status'] in ['completed', 'failed']:
                break
            await asyncio.sleep(2)
            wait_time += 2
        
        final_status = await get_task_status(task_id)
        if final_status and final_status['status'] == 'completed':
            print(f"✅ Creative writing completed successfully")
            return True
        else:
            print(f"❌ Creative writing failed: {final_status.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"Creative agent test failed: {e}")
        print(f"❌ Creative agent test failed: {e}")
        return False


async def test_data_agent():
    """Test Data Agent functionality"""
    print("\n📊 Testing Data Agent...")
    
    try:
        # Create sample data
        sample_data = [
            {"name": "Alice", "age": 25, "score": 85},
            {"name": "Bob", "age": 30, "score": 92},
            {"name": "Charlie", "age": 28, "score": 78},
            {"name": "Diana", "age": 35, "score": 88},
            {"name": "Eve", "age": 22, "score": 95}
        ]
        
        # Submit a data analysis task
        task_id = await submit_task(
            agent_type="DataAgent",
            task_type="data_analysis",
            description="Analyze the provided dataset and provide insights",
            input_data={
                "data": sample_data,
                "analysis_type": "comprehensive",
                "columns": ["age", "score"]
            },
            priority=AgentPriority.NORMAL,
            timeout_seconds=60
        )
        
        print(f"✅ Submitted data analysis task: {task_id}")
        
        # Wait for completion
        max_wait = 30
        wait_time = 0
        
        while wait_time < max_wait:
            status = await get_task_status(task_id)
            if status and status['status'] in ['completed', 'failed']:
                break
            await asyncio.sleep(2)
            wait_time += 2
        
        final_status = await get_task_status(task_id)
        if final_status and final_status['status'] == 'completed':
            print(f"✅ Data analysis completed successfully")
            return True
        else:
            print(f"❌ Data analysis failed: {final_status.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"Data agent test failed: {e}")
        print(f"❌ Data agent test failed: {e}")
        return False


async def test_system_agent():
    """Test System Agent functionality"""
    print("\n⚙️ Testing System Agent...")
    
    try:
        # Submit a system monitoring task
        task_id = await submit_task(
            agent_type="SystemAgent",
            task_type="system_monitoring",
            description="Monitor system performance and health",
            input_data={
                "metrics": ["cpu", "memory", "disk"],
                "duration": 10
            },
            priority=AgentPriority.NORMAL,
            timeout_seconds=60
        )
        
        print(f"✅ Submitted system monitoring task: {task_id}")
        
        # Wait for completion
        max_wait = 30
        wait_time = 0
        
        while wait_time < max_wait:
            status = await get_task_status(task_id)
            if status and status['status'] in ['completed', 'failed']:
                break
            await asyncio.sleep(2)
            wait_time += 2
        
        final_status = await get_task_status(task_id)
        if final_status and final_status['status'] == 'completed':
            print(f"✅ System monitoring completed successfully")
            return True
        else:
            print(f"❌ System monitoring failed: {final_status.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"System agent test failed: {e}")
        print(f"❌ System agent test failed: {e}")
        return False


async def test_orchestrator_status():
    """Test orchestrator status and metrics"""
    print("\n📈 Testing Orchestrator Status...")
    
    try:
        orchestrator = await get_orchestrator()
        status = await orchestrator.get_orchestrator_status()
        
        print(f"✅ Orchestrator Status:")
        print(f"  Running: {status['is_running']}")
        print(f"  Queued Tasks: {status['queued_tasks']}")
        print(f"  Running Tasks: {status['running_tasks']}")
        print(f"  Completed Tasks: {status['completed_tasks']}")
        print(f"  Registered Agents: {status['registered_agents']}")
        print(f"  Available Agents: {status['available_agents']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Orchestrator status test failed: {e}")
        print(f"❌ Orchestrator status test failed: {e}")
        return False


async def test_concurrent_tasks():
    """Test concurrent task execution"""
    print("\n🔄 Testing Concurrent Task Execution...")
    
    try:
        # Submit multiple tasks simultaneously
        tasks = []
        
        # Code generation task
        tasks.append(await submit_task(
            agent_type="CodeAgent",
            task_type="code_generation",
            description="Write a simple calculator function",
            priority=AgentPriority.NORMAL
        ))
        
        # Creative writing task
        tasks.append(await submit_task(
            agent_type="CreativeAgent",
            task_type="creative_writing",
            description="Write a haiku about technology",
            priority=AgentPriority.NORMAL
        ))
        
        # Data analysis task
        tasks.append(await submit_task(
            agent_type="DataAgent",
            task_type="data_analysis",
            description="Analyze sample data",
            input_data={"data": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]},
            priority=AgentPriority.NORMAL
        ))
        
        print(f"✅ Submitted {len(tasks)} concurrent tasks")
        
        # Wait for all tasks to complete
        completed_tasks = 0
        max_wait = 60
        wait_time = 0
        
        while wait_time < max_wait and completed_tasks < len(tasks):
            for task_id in tasks:
                status = await get_task_status(task_id)
                if status and status['status'] in ['completed', 'failed']:
                    completed_tasks += 1
            
            if completed_tasks < len(tasks):
                await asyncio.sleep(2)
                wait_time += 2
        
        print(f"✅ {completed_tasks}/{len(tasks)} tasks completed")
        return completed_tasks == len(tasks)
        
    except Exception as e:
        logger.error(f"Concurrent tasks test failed: {e}")
        print(f"❌ Concurrent tasks test failed: {e}")
        return False


async def main():
    """Run all multi-agent system tests"""
    print("🚀 Atulya Tantra AGI - Multi-Agent System Test Suite")
    print("=" * 70)
    
    # Test results
    test_results = []
    
    # Test 1: Agent Registration
    test_results.append(await test_agent_registration())
    
    # Test 2: Individual Agent Tests
    test_results.append(await test_code_agent())
    test_results.append(await test_research_agent())
    test_results.append(await test_creative_agent())
    test_results.append(await test_data_agent())
    test_results.append(await test_system_agent())
    
    # Test 3: Orchestrator Status
    test_results.append(await test_orchestrator_status())
    
    # Test 4: Concurrent Execution
    test_results.append(await test_concurrent_tasks())
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary:")
    
    test_names = [
        "Agent Registration",
        "Code Agent",
        "Research Agent", 
        "Creative Agent",
        "Data Agent",
        "System Agent",
        "Orchestrator Status",
        "Concurrent Tasks"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        print(f"  {name}: {'✅' if result else '❌'}")
    
    total_tests = len(test_results)
    passed_tests = sum(test_results)
    
    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Multi-agent system is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs for details.")
    
    # Cleanup
    try:
        orchestrator = await get_orchestrator()
        await orchestrator.stop()
        print("\n🛑 Orchestrator stopped")
    except Exception as e:
        logger.error(f"Error stopping orchestrator: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user.")
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        print(f"❌ Test suite failed: {e}")
