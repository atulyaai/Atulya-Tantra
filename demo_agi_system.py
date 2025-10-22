"""
Demo Script for JARVIS-Skynet AGI System
Demonstrates all capabilities including voice interaction, sentiment analysis, and autonomous operations
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any

# Import the unified AGI system
from Core.unified_agi_system import (
    get_agi_system, start_agi_system, stop_agi_system, 
    process_with_agi, get_agi_system_status, SystemMode
)
from Core.jarvis.sentiment_analyzer import analyze_user_sentiment, EmotionType
from Core.jarvis.enhanced_voice_interface import get_enhanced_voice_interface, ConversationMode


class AGISystemDemo:
    """Demo class for the AGI system"""
    
    def __init__(self):
        self.agi_system = get_agi_system()
        self.voice_interface = get_enhanced_voice_interface()
        self.demo_running = False
        
        # Set up callbacks
        self.agi_system.set_callbacks(
            on_user_input=self._on_user_input,
            on_system_response=self._on_system_response,
            on_system_state_change=self._on_system_state_change,
            on_error=self._on_error
        )
    
    def _on_user_input(self, input_text: str, context: Dict[str, Any]):
        """Handle user input callback"""
        print(f"\n🎤 User Input: {input_text}")
        if context.get("emotional_context"):
            emotion = context["emotional_context"].get("current_emotion", "neutral")
            intensity = context["emotional_context"].get("intensity", "moderate")
            print(f"😊 Detected Emotion: {emotion} ({intensity})")
    
    def _on_system_response(self, response: str, context: Dict[str, Any]):
        """Handle system response callback"""
        print(f"\n🤖 JARVIS Response: {response}")
        if context.get("source") == "voice":
            print("🔊 (Spoken via voice interface)")
    
    def _on_system_state_change(self, component: str, old_state: str, new_state: str):
        """Handle system state change callback"""
        print(f"🔄 {component}: {old_state} → {new_state}")
    
    def _on_error(self, error: Exception):
        """Handle error callback"""
        print(f"❌ Error: {error}")
    
    async def run_demo(self):
        """Run the complete AGI system demo"""
        print("🚀 Starting JARVIS-Skynet AGI System Demo")
        print("=" * 50)
        
        try:
            # Start the AGI system
            print("\n1. Initializing AGI System...")
            await start_agi_system(SystemMode.CONVERSATIONAL)
            print("✅ AGI System started successfully")
            
            # Show system status
            await self._show_system_status()
            
            # Run interactive demo
            await self._run_interactive_demo()
            
            # Run automated tests
            await self._run_automated_tests()
            
            # Run voice demo (if available)
            await self._run_voice_demo()
            
        except Exception as e:
            print(f"❌ Demo error: {e}")
        finally:
            # Stop the system
            print("\n🛑 Stopping AGI System...")
            await stop_agi_system()
            print("✅ AGI System stopped")
    
    async def _show_system_status(self):
        """Show current system status"""
        print("\n2. System Status:")
        status = get_agi_system_status()
        
        print(f"   • Active: {status['is_active']}")
        print(f"   • Mode: {status['system_mode']}")
        print(f"   • Voice State: {status['voice_state']['state']}")
        print(f"   • Active Sessions: {status['active_sessions']}")
        print(f"   • Learning Entries: {status['learning_entries']}")
        
        if status.get('system_health'):
            health = status['system_health']
            print(f"   • System Health: {health.get('status', 'unknown')}")
    
    async def _run_interactive_demo(self):
        """Run interactive demo with various inputs"""
        print("\n3. Interactive Demo:")
        print("   Testing various types of inputs and responses...")
        
        # Test cases with different emotional contexts
        test_cases = [
            {
                "input": "Hello JARVIS, how are you today?",
                "description": "Friendly greeting"
            },
            {
                "input": "I'm feeling really excited about this new project!",
                "description": "Positive emotion (joy)"
            },
            {
                "input": "I'm so frustrated with this bug in my code!",
                "description": "Negative emotion (anger/frustration)"
            },
            {
                "input": "Can you help me organize my tasks for today?",
                "description": "Task assistance request"
            },
            {
                "input": "What's the weather like today?",
                "description": "Information request"
            },
            {
                "input": "I'm feeling a bit sad about the recent news.",
                "description": "Sad emotion"
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n   Test {i}: {test_case['description']}")
            print(f"   Input: \"{test_case['input']}\"")
            
            # Process with AGI system
            result = await process_with_agi(
                test_case['input'],
                user_id=f"demo_user_{i}",
                context={"demo": True}
            )
            
            if result['success']:
                print(f"   Response: \"{result['response']}\"")
                
                # Show emotional analysis
                if result.get('emotional_context'):
                    emotion = result['emotional_context'].get('current_emotion', 'neutral')
                    intensity = result['emotional_context'].get('intensity', 'moderate')
                    print(f"   Emotion: {emotion} ({intensity})")
                
                # Show AGI analysis
                if result.get('agi_analysis', {}).get('success'):
                    decision = result['agi_analysis'].get('decision', {})
                    if decision.get('decision') == 'proceed':
                        print(f"   AGI Decision: Proceed with confidence {decision.get('confidence', 0):.2f}")
                    else:
                        print(f"   AGI Decision: {decision.get('decision', 'unknown')}")
            else:
                print(f"   Error: {result.get('error', 'Unknown error')}")
            
            # Small delay between tests
            await asyncio.sleep(1)
    
    async def _run_automated_tests(self):
        """Run automated tests"""
        print("\n4. Automated Tests:")
        print("   Running comprehensive system tests...")
        
        # Test sentiment analysis
        print("   • Testing sentiment analysis...")
        await self._test_sentiment_analysis()
        
        # Test AGI reasoning
        print("   • Testing AGI reasoning...")
        await self._test_agi_reasoning()
        
        # Test system monitoring
        print("   • Testing system monitoring...")
        await self._test_system_monitoring()
        
        print("   ✅ All automated tests completed")
    
    async def _test_sentiment_analysis(self):
        """Test sentiment analysis capabilities"""
        test_texts = [
            "I'm so happy and excited!",
            "This is terrible and awful.",
            "I'm feeling neutral about this.",
            "I'm absolutely furious!",
            "I'm scared and worried."
        ]
        
        for text in test_texts:
            context = await analyze_user_sentiment(text, "test_user")
            print(f"     \"{text}\" → {context.current_emotion} ({context.intensity})")
    
    async def _test_agi_reasoning(self):
        """Test AGI reasoning capabilities"""
        reasoning_tests = [
            "Help me plan my day",
            "What should I do about this problem?",
            "Analyze this situation and give me advice"
        ]
        
        for test in reasoning_tests:
            result = await process_with_agi(test, "test_user")
            if result['success']:
                agi_result = result.get('agi_analysis', {})
                if agi_result.get('success'):
                    print(f"     \"{test}\" → AGI processed successfully")
                else:
                    print(f"     \"{test}\" → AGI processing failed")
    
    async def _test_system_monitoring(self):
        """Test system monitoring capabilities"""
        status = get_agi_system_status()
        if status.get('system_health'):
            health = status['system_health']
            print(f"     System Health: {health.get('status', 'unknown')}")
        else:
            print("     System Health: Not available")
    
    async def _run_voice_demo(self):
        """Run voice interface demo"""
        print("\n5. Voice Interface Demo:")
        print("   Testing voice interaction capabilities...")
        
        # Check if voice interface is available
        voice_state = self.voice_interface.get_current_state()
        print(f"   Voice Interface State: {voice_state['state']}")
        
        if voice_state['is_active']:
            print("   • Voice interface is active")
            print("   • Try saying 'JARVIS' to activate voice commands")
            print("   • Voice demo would run here in a real environment")
        else:
            print("   • Voice interface not active (may require microphone setup)")
            print("   • This is normal in demo environments")
    
    async def run_continuous_demo(self, duration_minutes: int = 5):
        """Run continuous demo for specified duration"""
        print(f"\n🔄 Running continuous demo for {duration_minutes} minutes...")
        print("   The system will process random inputs and demonstrate autonomous behavior")
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        demo_inputs = [
            "What's the current time?",
            "How are you feeling today?",
            "Can you help me with a task?",
            "Tell me something interesting",
            "What should I do next?",
            "I need some advice",
            "How's the system performing?",
            "What can you do for me?"
        ]
        
        input_count = 0
        
        while time.time() < end_time:
            # Select random input
            import random
            input_text = random.choice(demo_inputs)
            input_count += 1
            
            print(f"\n🔄 Continuous Demo - Input {input_count}: \"{input_text}\"")
            
            # Process input
            result = await process_with_agi(input_text, f"continuous_user_{input_count}")
            
            if result['success']:
                print(f"   Response: {result['response'][:100]}...")
            else:
                print(f"   Error: {result.get('error', 'Unknown error')}")
            
            # Wait before next input
            await asyncio.sleep(30)  # 30 seconds between inputs
        
        print(f"\n✅ Continuous demo completed after {input_count} inputs")


async def main():
    """Main demo function"""
    print("🤖 JARVIS-Skynet AGI System Demo")
    print("=" * 50)
    print("This demo showcases the complete AGI system with:")
    print("• Advanced sentiment analysis and emotional intelligence")
    print("• Natural voice interaction and conversation")
    print("• Autonomous reasoning and decision making")
    print("• Skynet integration for system monitoring and healing")
    print("• Multi-agent orchestration")
    print("• Continuous learning and adaptation")
    print("=" * 50)
    
    # Create and run demo
    demo = AGISystemDemo()
    
    try:
        # Run main demo
        await demo.run_demo()
        
        # Ask if user wants to run continuous demo
        print("\n" + "=" * 50)
        print("Would you like to run a continuous demo? (y/n)")
        print("This will run the system for 5 minutes with random inputs")
        
        # In a real environment, you would get user input here
        # For demo purposes, we'll skip the continuous demo
        print("Skipping continuous demo for this automated run")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
    finally:
        print("\n👋 Demo completed. Thank you for testing the JARVIS-Skynet AGI System!")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
