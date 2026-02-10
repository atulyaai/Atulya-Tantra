"""
Atulya Main Entry Point and CLI Interface
"""

import argparse
import json
import logging
from datetime import datetime
from typing import Optional

from atulya import Atulya

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Atulya - AGI-Evolving AI Assistant")
    parser.add_argument("--config", help="Path to config YAML file", default=None)
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Task execution command
    task_parser = subparsers.add_parser("task", help="Execute a task")
    task_parser.add_argument("description", help="Task description")
    task_parser.add_argument("--context", help="Task context (JSON)")
    
    # Status command
    subparsers.add_parser("status", help="Get system status")
    
    # Learn command
    learn_parser = subparsers.add_parser("learn", help="Teach a new skill")
    learn_parser.add_argument("skill_name", help="Skill name")
    learn_parser.add_argument("--data", help="Training data (JSON)")
    
    # Evolution command
    subparsers.add_parser("evolution", help="Get evolution metrics")
    
    # Interactive mode
    subparsers.add_parser("interactive", help="Start interactive mode")
    
    args = parser.parse_args()
    
    # Initialize Atulya
    assistant = Atulya(name="Atulya", config_path=args.config)
    
    # Route to appropriate command
    if args.command == "task":
        execute_task(assistant, args)
    elif args.command == "status":
        show_status(assistant)
    elif args.command == "learn":
        teach_skill(assistant, args)
    elif args.command == "evolution":
        show_evolution(assistant)
    elif args.command == "interactive":
        interactive_mode(assistant)
    else:
        parser.print_help()


def execute_task(assistant: Atulya, args):
    """Execute a task"""
    context = {}
    if args.context:
        context = json.loads(args.context)
    
    print(f"\n[Atulya] Executing: {args.description}")
    result = assistant.execute_task(args.description, context)
    
    print(f"\n[Result]")
    print(json.dumps(result, indent=2))


def show_status(assistant: Atulya):
    """Show system status"""
    status = assistant.get_evolution_status()
    
    print("\n[Atulya Status]")
    print(f"Name: {status['name']}")
    print(f"Version: {status['version']}")
    print(f"Created: {status['created_at']}")
    print(f"\n[Statistics]")
    for key, value in status['stats'].items():
        print(f"  {key}: {value}")
    
    print(f"\n[Memory]")
    for key, value in status['memory_size'].items():
        print(f"  {key}: {value}")


def teach_skill(assistant: Atulya, args):
    """Teach a new skill"""
    skill_data = {"description": "New skill"}
    
    if args.data:
        skill_data = json.loads(args.data)
    
    success = assistant.acquire_skill(args.skill_name, skill_data)
    
    if success:
        print(f"\n[Success] Skill '{args.skill_name}' learned")
    else:
        print(f"\n[Error] Failed to learn skill '{args.skill_name}'")


def show_evolution(assistant: Atulya):
    """Show evolution metrics"""
    status = assistant.get_evolution_status()
    metrics = status['evolution_metrics']
    
    print("\n[Evolution Metrics]")
    print(f"Generation: {metrics['generation']}")
    print(f"Average Fitness: {metrics['avg_fitness']}")
    print(f"Max Fitness: {metrics['max_fitness']}")
    print(f"Progress: {metrics['evolution_progress']}")
    print(f"\n[Parameters]")
    for param, value in metrics['parameters'].items():
        print(f"  {param}: {value:.6f}")


def interactive_mode(assistant: Atulya):
    """Start interactive mode"""
    print("\n" + "="*50)
    print("Atulya - Interactive Mode")
    print("="*50)
    print("Commands: task, status, learn, evolution, help, exit")
    print("="*50 + "\n")
    
    while True:
        try:
            user_input = input("Atulya> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "exit":
                print("\nGoodbye!")
                break
            
            elif user_input.lower() == "status":
                show_status(assistant)
            
            elif user_input.lower() == "evolution":
                show_evolution(assistant)
            
            elif user_input.lower() == "help":
                print("\nAvailable commands:")
                print("  task <description> - Execute a task")
                print("  status - Show system status")
                print("  evolution - Show evolution metrics")
                print("  exit - Exit interactive mode\n")
            
            elif user_input.lower().startswith("task "):
                task_desc = user_input[5:]
                result = assistant.execute_task(task_desc)
                print(f"\nResult: {json.dumps(result, indent=2)}\n")
            
            else:
                # Default: treat as task
                result = assistant.execute_task(user_input)
                print(f"\nResult: {json.dumps(result, indent=2)}\n")
        
        except KeyboardInterrupt:
            print("\n\nExiting... (Ctrl+C)")
            break
        except Exception as e:
            print(f"Error: {str(e)}\n")


if __name__ == "__main__":
    main()
