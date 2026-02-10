"""
Atulya - Real-World Usage Examples with Visual Progress
Shows best practices for automation, learning, and evolution.
"""

from atulya import Atulya
from datetime import datetime, timedelta
import json


def print_header(title):
    """Print formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def print_progress(current, total, title="Progress"):
    """Print visual progress bar"""
    percent = (current / total) * 100
    filled = int(30 * current / total)
    bar = "█" * filled + "░" * (30 - filled)
    print(f"{title}: [{bar}] {percent:.0f}%")


def example_1_basic_execution():
    """Example 1: Execute tasks with different intents"""
    print_header("📋 EXAMPLE 1: Basic Task Execution")

    atulya = Atulya(name="Atulya")
    print(f"✓ {atulya.name} initialized\n")

    # Different task types
    tasks = [
        ("information", "What is machine learning?"),
        ("analysis", "Analyze the data for patterns"),
        ("execution", "Execute the backup process"),
        ("learning", "Learn about quantum computing"),
    ]

    for i, (task_type, task_desc) in enumerate(tasks, 1):
        print_progress(i, len(tasks), f"Processing {task_type}")
        result = atulya.execute_task(task_desc)
        print(f"  Task: {task_desc}")
        print(f"  Status: {'✅ Success' if result.get('success') else '❌ Failed'}")
        print(f"  Confidence: {result.get('confidence', 0):.0%}\n")

    print(f"✓ Total tasks executed: {atulya.stats['tasks_executed']}")


def example_2_skill_learning():
    """Example 2: Dynamically learn skills and track proficiency"""
    print_header("🎓 EXAMPLE 2: Dynamic Skill Learning")

    atulya = Atulya(name="Atulya")

    # Skills to acquire
    skills_data = [
        ("data_analysis", {"level": "expert", "tools": ["pandas", "numpy"]}),
        ("web_scraping", {"level": "advanced", "framework": "beautiful-soup"}),
        ("nlp_processing", {"level": "intermediate", "library": "spacy"}),
        ("automation", {"level": "expert", "platform": "multi"}),
    ]

    # Learn skills
    print("Learning new skills:\n")
    for i, (skill_name, data) in enumerate(skills_data, 1):
        print_progress(i, len(skills_data), "Skill acquisition")
        success = atulya.acquire_skill(skill_name, data)
        print(f"  ✓ {skill_name}: {data.get('level', 'intermediate').upper()}\n")

    # Display skills
    print("\n📊 Skill Proficiency Report:\n")
    skills = atulya.skill_manager.list_skills()
    for skill in skills:
        prof_pct = skill["proficiency"]
        bar_len = int(20 * prof_pct)
        bar = "▰" * bar_len + "▱" * (20 - bar_len)
        print(f"  {skill['name']:20s} [{bar}] {prof_pct:6.1%}")

    print(f"\n✓ Total skills learned: {atulya.skills_manager.count_skills()}")


def example_3_evolution_tracking():
    """Example 3: Monitor fitness evolution across generations"""
    print_header("🧬 EXAMPLE 3: Evolution & Fitness Tracking")

    atulya = Atulya(name="Atulya")

    # Execute tasks to drive evolution
    print("Running evolution cycles:\n")
    num_cycles = 8
    for cycle in range(1, num_cycles + 1):
        print_progress(cycle, num_cycles, "Evolution cycles")
        task = f"Optimization task {cycle}: improve system efficiency"
        result = atulya.execute_task(task)

    # Get evolution metrics
    print("\n")
    metrics = atulya.evolution.get_metrics()

    display = f"""
📈 Evolution Report:
  Generation:      {metrics['generation']}
  Average Fitness: {metrics['avg_fitness']:.4f}
  Max Fitness:     {metrics['max_fitness']:.4f}
  Progress:        {metrics['evolution_progress']:.2%}

🔬 Learning Parameters:
  Learning Rate:   {metrics['parameters']['learning_rate']:.6f}
  Exploration:     {metrics['parameters']['exploration_factor']:.4f}
  Mutation Rate:   {metrics['parameters']['mutation_rate']:.4f}
"""
    print(display)


def example_4_memory_management():
    """Example 4: Memory consolidation and similarity search"""
    print_header("💾 EXAMPLE 4: Memory Management")

    atulya = Atulya(name="Atulya")

    # Execute tasks to populate memory
    print("Building memory from task execution:\n")
    tasks = [
        "Analyze customer behavior patterns",
        "Generate sales forecast report",
        "Analyze market trends data",
        "Create performance dashboards",
    ]

    for i, task in enumerate(tasks, 1):
        print_progress(i, len(tasks), "Memory building")
        atulya.execute_task(task)

    # Show memory stats
    print("\n")
    memory_size = atulya.memory.get_size()
    display = f"""
🧠 Memory Statistics:
  Short-term entries:  {memory_size['short_term']}
  Long-term entries:   {memory_size['long_term']}
  Task history:        {memory_size['task_history']}
  Experiences logged:  {memory_size['experiences']}
"""
    print(display)

    # Similarity search
    print("🔎 Similarity Search Results:\n")
    query = "Analyze data and create report"
    similar = atulya.memory.search_similar(query, threshold=0.5)
    print(f"Query: '{query}'\n")
    for i, item in enumerate(similar[:3], 1):
        print(f"  {i}. Match: {item['task']}")
        print(f"     Similarity: {item['similarity']:.2%}\n")

    # Consolidate memory
    print("Consolidating memory to long-term storage...\n")
    consolidated = atulya.memory.consolidate_memory()
    print(f"✓ Consolidated: {consolidated['consolidated']} successful tasks")


def example_5_automation_config():
    """Example 5: Config-driven automation (most important!)"""
    print_header("⚙️  EXAMPLE 5: Config-Driven Automation")

    print("""
This example shows the power of CONFIGURATION over hardcoding!

Edit: config/atulya_config.yaml
    """)

    atulya = Atulya(name="Atulya")

    # Show config
    config = atulya.config
    automation_cfg = config.get("automation", {})

    print("📋 Loaded Configuration:\n")
    print(f"  Startup Tasks: {len(automation_cfg.get('startup_tasks', []))} defined")
    print(f"  Automation Rules: {len(automation_cfg.get('rules', []))} defined\n")

    print("🚀 Auto-executed on init:")
    startup_tasks = automation_cfg.get("startup_tasks", [])
    for i, task_cfg in enumerate(startup_tasks, 1):
        task_desc = task_cfg.get("task") or task_cfg.get("description")
        print(f"  {i}. {task_desc}")

    print("\n📌 Registered Rules:")
    rules = automation_cfg.get("rules", [])
    for rule in rules:
        rule_id = rule.get("id")
        rule_type = rule.get("type")
        print(f"  • {rule_id} (type: {rule_type})")

    print("\n✓ All automation defined in YAML - No code changes needed!")


def example_6_system_optimization():
    """Example 6: Performance optimization"""
    print_header("⚡ EXAMPLE 6: System Optimization")

    atulya = Atulya(name="Atulya")

    # Create some load
    print("Creating system load:\n")
    for i in range(5):
        print_progress(i + 1, 5, "Loading system")
        atulya.execute_task(f"Processing task {i+1}")

    print("\n")

    # Optimize
    print("🔧 Running optimizations...\n")
    optimizations = atulya.optimize_performance()

    for opt_name, opt_result in optimizations.items():
        print(f"  {opt_name.replace('_', ' ').title()}:")
        if isinstance(opt_result, dict):
            for k, v in opt_result.items():
                print(f"    • {k}: {v}")
        else:
            print(f"    • Result: {opt_result}")
        print()


def example_7_complete_workflow():
    """Example 7: End-to-end production workflow"""
    print_header("🎯 EXAMPLE 7: Production Workflow")

    print("Simulating a complete business workflow:\n")

    # Phase 1: Initialize
    print("Phase 1: Initialization")
    print_progress(1, 5, "Workflow")
    atulya = Atulya(name="ProductionAtulya")
    print("✓ System initialized\n")

    # Phase 2: Learn skills
    print("Phase 2: Skill Acquisition")
    print_progress(2, 5, "Workflow")
    atulya.acquire_skill("data_processing", {"level": "expert"})
    atulya.acquire_skill("report_generation", {"level": "advanced"})
    print("✓ Skills loaded\n")

    # Phase 3: Execute workflow
    print("Phase 3: Task Execution")
    print_progress(3, 5, "Workflow")
    workflow_tasks = [
        "Extract data from source system",
        "Process and validate data integrity",
        "Generate executive summary report",
    ]
    for task in workflow_tasks:
        atulya.execute_task(task)
        print(f"  ✓ {task}")
    print()

    # Phase 4: Monitor evolution
    print("Phase 4: Performance Monitoring")
    print_progress(4, 5, "Workflow")
    status = atulya.get_evolution_status()
    print(f"  Tasks executed: {status['stats']['tasks_executed']}")
    print(f"  Generation: {status['evolution_metrics']['generation']}")
    print(f"  Fitness: {status['evolution_metrics']['avg_fitness']:.4f}\n")

    # Phase 5: Optimize
    print("Phase 5: Optimization")
    print_progress(5, 5, "Workflow")
    atulya.optimize_performance()
    print("✓ System optimized\n")

    print("=" * 70)
    print("  🎉 Workflow Complete!")
    print("=" * 70)


def main():
    """Run all examples"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  🚀 ATULYA EXAMPLES - Production Scenarios".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")

    examples = [
        ("Basic Execution", example_1_basic_execution),
        ("Skill Learning", example_2_skill_learning),
        ("Evolution Tracking", example_3_evolution_tracking),
        ("Memory Management", example_4_memory_management),
        ("Config Automation", example_5_automation_config),
        ("System Optimization", example_6_system_optimization),
        ("Production Workflow", example_7_complete_workflow),
    ]

    print("\n📚 Available Examples:\n")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\n" + "=" * 70)
    print("Running all examples...\n")

    for i, (name, example_func) in enumerate(examples, 1):
        try:
            example_func()
            print(f"\n✓ Example {i} completed\n")
        except Exception as e:
            print(f"\n❌ Example {i} failed: {str(e)}\n")

    print("=" * 70)
    print("\n✨ All examples completed!\n")
    print("💡 Next steps:")
    print("  1. Customize config/atulya_config.yaml")
    print("  2. Run: python main.py interactive")
    print("  3. Build your own automation!")
    print("\n")


if __name__ == "__main__":
    main()
