#!/usr/bin/env python3
"""
Quick start script for Atulya
"""

from atulya import Atulya
import json

def main():
    print("=" * 70)
    print("  ATULYA - AGI-Evolving AI Assistant System")
    print("=" * 70)
    print()
    
    # Create instance
    atulya = Atulya(name="Atulya")
    print(f"✓ {atulya.name} initialized successfully")
    print()
    
    # Demo task (configured)
    print("-" * 70)
    print("Demo: Executing configured startup tasks and sample task")
    print("-" * 70)

    # Config-driven demo: run a sample task from config if present
    try:
        startup_tasks = atulya.config.get("automation", {}).get("startup_tasks", [])
        if startup_tasks:
            for t in startup_tasks:
                task_desc = t.get("task") or t.get("description")
                if task_desc:
                    print(f"Running startup task: {task_desc}")
                    print(json.dumps(atulya.execute_task(task_desc), indent=2))
        else:
            # fallback
            result = atulya.execute_task("What are the key features of artificial intelligence?")
            print(json.dumps(result, indent=2))
    except Exception:
        print("Startup demo tasks failed; running fallback task")

    print()

    # Skill learning from config
    print("-" * 70)
    print("Demo: Learning configured skills")
    print("-" * 70)
    skills_to_learn = atulya.config.get("initial_skills", [])
    if not skills_to_learn:
        skills_to_learn = [
            {"name": "natural_language_processing", "data": {"category": "AI"}},
            {"name": "machine_learning", "data": {"category": "AI"}},
        ]
    for skill in skills_to_learn:
        name = skill.get("name")
        data = skill.get("data", {})
        if name:
            atulya.acquire_skill(name, data)
            print(f"✓ Learned: {name}")
    print()
    
    # Status
    print("-" * 70)
    print("System Status")
    print("-" * 70)
    
    status = atulya.get_evolution_status()
    print(f"Name: {status['name']}")
    print(f"Version: {status['version']}")
    print(f"Tasks Executed: {status['stats']['tasks_executed']}")
    print(f"Skills Learned: {status['stats']['skills_learned']}")
    print(f"Evolution Generation: {status['evolution_metrics']['generation']}")
    print(f"Average Fitness: {status['evolution_metrics']['avg_fitness']:.4f}")
    print()
    
    print("=" * 70)
    print("Run 'python main.py --help' for CLI interface options")
    print("Run 'python examples.py' for detailed examples")
    print("=" * 70)

if __name__ == "__main__":
    main()
