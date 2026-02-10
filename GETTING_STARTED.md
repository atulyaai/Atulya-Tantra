# 🚀 Getting Started with Atulya

*Your personal AI assistant that learns, evolves, and automates—all driven by configuration!*

---

## ⚡ 60-Second Quickstart

```bash
# Clone the repo
git clone https://github.com/atulyaai/Atulya-Tantra.git
cd Atulya-Tantra

# Install dependencies
pip install -r requirements.txt

# Run it!
python quickstart.py
```

**Output you'll see:**
```
✓ Atulya initialized successfully
✓ Tasks Executed: 3
✓ Skills Learned: 2
✓ Average Fitness: 0.96
```

---

## 📖 Core Concepts (5-Minute Deep Dive)

### 🎯 **Tasks** - Your Commands
Ask Atulya to do things:
```python
from atulya import Atulya

atulya = Atulya(name="Atulya")

# Simple question
result = atulya.execute_task("What is machine learning?")
# → Returns structured response with confidence

# Complex request with context
result = atulya.execute_task(
    "Analyze the quarterly report",
    context={"priority": "high", "dept": "finance"}
)
```

**Task Types:**
- 📌 **Information** - "Tell me about...", "What is..."
- ⚙️ **Execution** - "Run...", "Execute...", "Do..."
- 📊 **Analysis** - "Analyze...", "Examine...", "Review..."
- 📚 **Learning** - "Learn...", "Study...", "Understand..."

---

### 🧠 **Skills** - Atulya's Superpowers
Teach it new capabilities:

```python
# Acquire a skill
atulya.acquire_skill("web_scraping", {
    "description": "Extract data from websites",
    "initial_proficiency": 0.7
})

# Use it (it improves with practice!)
atulya.skill_manager.use_skill("web_scraping")

# Check how good it got
skills = atulya.skill_manager.list_skills()
for skill in skills:
    print(f"{skill['name']}: {skill['proficiency']:.0%}")
    # → web_scraping: 75% (and improving!)
```

**Proficiency Scale:**
```
0%   ----+----+----+----+---- 100%
     Novice  Beginner  Expert  Master  Genius
```

---

### 💾 **Memory** - Learning Persistent
Atulya remembers everything:

```python
# Two-level memory system
atulya.memory.store_task_result("task_name", result)

# Search for similar past tasks
similar = atulya.memory.search_similar("web scraping")
# → Returns previously successful approaches

# Consolidate memory (short → long term)
consolidated = atulya.memory.consolidate_memory()
# → Moves successful strategies to permanent storage

# Optimize memory usage
optimized = atulya.memory.optimize()
# → Cleans up old, unsuccessful entries
```

**Memory Levels:**
```
Short-term: Fast, session-specific    (like tabs)
    ▼
Long-term: Persistent, learned!       (like files)
```

---

### 🧬 **Evolution** - Continuous Improvement
Atulya gets smarter every time:

```python
# Get evolution metrics
metrics = atulya.evolution.get_metrics()

print(f"Generation: {metrics['generation']}")
print(f"Fitness: {metrics['avg_fitness']:.4f}")
print(f"Progress: {metrics['evolution_progress']:.2%}")

# Visual progress
#
# Fitness over time:
# Gen 1:  ■■■■░░░░░░ 0.50
# Gen 5:  ■■■■■■░░░░ 0.65
# Gen 10: ■■■■■■■■░░ 0.80
# Gen 20: ■■■■■■■■■░ 0.95  ← Peak performance!
```

---

### ⚙️ **Automation** - Set It and Forget It
Config-driven task automation (no hardcoding!):

```yaml
# config/atulya_config.yaml
automation:
  # Tasks to run on startup
  startup_tasks:
    - task: "Initialize system and load data"
    - task: "Send good morning report"
  
  # Automation rules
  rules:
    # Simple on-startup rule
    - id: "welcome_task"
      type: "on_start"
      action_task: "Welcome the user and show status"
    
    # Interval-based execution
    - id: "health_check"
      type: "interval_seconds"
      every: 3600
      action_task: "Check system health and report"
```

Then just load it:
```python
atulya = Atulya()  # Auto-runs startup_tasks & rules!
```

No code changes needed! ✨

---

## 🎬 Common Workflows

### Workflow 1️⃣ : Daily Report Generator

**Goal:** Auto-generate report every morning

```yaml
# config/atulya_config.yaml
automation:
  rules:
    - id: "daily_report"
      type: "on_start"
      action_task: "Generate comprehensive daily performance report with KPIs and insights"
```

```python
atulya = Atulya()  # Report runs automatically!
```

---

### Workflow 2️⃣ : Learning New Skills

```python
# Define what you want to learn
skills_to_learn = [
    {"name": "data_analysis", "data": {"level": "expert"}},
    {"name": "api_integration", "data": {"level": "intermediate"}},
    {"name": "automation", "data": {"level": "advanced"}},
]

# Teach skills
for skill in skills_to_learn:
    atulya.acquire_skill(skill["name"], skill["data"])

# Practice with tasks
tasks = [
    "Analyze the dataset for patterns",
    "Integrate the payment API",
    "Automate the backup process"
]

for task in tasks:
    result = atulya.execute_task(task)
    print(f"✓ {task}")

# Skills improve automatically! 📈
```

---

### Workflow 3️⃣ : Custom Automation with Rules

```python
from atulya.automation.task_scheduler import TaskScheduler
from datetime import datetime, timedelta

scheduler = TaskScheduler()

# Define a trigger condition
def is_production_ready():
    return True  # Your condition

# Define an action
def deploy_to_production():
    return atulya.execute_task("Deploy application to production")

# Register the rule
scheduler.add_automation_rule(
    "auto_deploy",
    is_production_ready,
    deploy_to_production
)

# Evaluate continuously
results = scheduler.evaluate_automation_rules()
print(f"Triggered: {len(results['triggered'])} rules")
```

---

## ⚙️ Configuration Guide

### Memory Tuning
```yaml
memory:
  short_term_max: 1000        # How many recent tasks to remember
  long_term_enabled: true     # Save successful approaches
  consolidation_interval: 3600  # Promote short→long term every hour
  similarity_threshold: 0.7   # How similar tasks must be (0-1)
```

### Evolution Tuning
```yaml
evolution:
  learning_rate: 0.001        # How fast to adapt (higher = faster)
  exploration_factor: 0.1     # Try new approaches vs exploit known
  mutation_rate: 0.05         # Explore variations in strategy
```

### Automation Tuning
```yaml
automation:
  concurrent_tasks: 5         # Run up to 5 tasks in parallel
  enable_scheduling: true     # Allow time-based tasks
  enable_rules: true          # Allow trigger-based rules
```

---

## 🖥️ CLI Commands

### Execute Tasks
```bash
# Ask a question
python main.py task "What is artificial intelligence?"

# Complex task with multiple words
python main.py task "Analyze the sales data and create summary"
```

### Check Status
```bash
# Full system status
python main.py status

# Evolution metrics only
python main.py evolution

# Get help
python main.py --help
```

### Interactive Mode
```bash
# Chat with Atulya
python main.py interactive

# Then just type:
# > What is Python?
# > Learn web development
# > status
# > exit
```

### Custom Config
```bash
# Use different config file
python main.py --config ./production_config.yaml task "Your task"
```

---

## 📊 Monitoring & Debugging

### Real-Time Status
```python
# Get full system snapshot
status = atulya.get_evolution_status()

print(f"Name: {status['name']}")
print(f"Version: {status['version']}")
print(f"Tasks done: {status['stats']['tasks_executed']}")
print(f"Skills learned: {status['stats']['skills_learned']}")
print(f"Memory: {status['memory_size']}")
print(f"Evolution: {status['evolution_metrics']}")
```

### Enable Debug Logging
```python
import logging

logging.basicConfig(level=logging.DEBUG)

atulya = Atulya()  # Now see detailed logs
```

---

## 🐳 Docker Deployment

### One-Click Full Stack
```bash
docker-compose up -d
```

This starts:
- 🧠 **Atulya** on port 8000
- 🔴 **Redis** on port 6379 (caching)
- 🐘 **PostgreSQL** on port 5432 (database)

All config-driven! No code changes needed.

---

## 📚 Advanced Topics

### Custom Agents
```python
from atulya.agents.task_agent import TaskAgent

class MyCustomAgent(TaskAgent):
    def execute(self, task, context=None):
        # Your custom logic here
        result = super().execute(task, context)
        # Post-process result
        return result
```

### API Integrations
```python
from atulya.integrations.integration_manager import IntegrationManager, APIIntegration

mgr = IntegrationManager()

# Connect to external API
api = APIIntegration("weather", "https://api.weather.com")
mgr.register_integration("weather", api)
mgr.connect_all()

# Use it
result = mgr.execute_integration("weather", "forecast", {"city": "NYC"})
```

### Memory Consolidation
```python
# Move successful tasks to long-term storage
consolidated = atulya.memory.consolidate_memory()
print(f"Moved to long-term: {consolidated['consolidated']}")

# Get memory stats
sizes = atulya.memory.get_size()
print(f"Short-term: {sizes['short_term']}")
print(f"Long-term: {sizes['long_term']}")
```

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| **Import Error** | `pip install -r requirements.txt` |
| **YAML parsing error** | Check config file syntax (spaces not tabs) |
| **Memory too large** | Call `atulya.memory.optimize()` |
| **Low fitness scores** | Call `atulya.evolution.boost_learning()` |
| **Tasks failing** | Check logs with `debug_mode: true` in config |

---

## 📞 Getting Help

- 📖 Read [README.md](README.md)
- 🔍 Check [examples.py](examples.py) for scenarios
- 💬 Open a GitHub issue
- 📧 Email team@atulya.ai

---

## ✅ Next Steps

1. ✨ **Run** `python quickstart.py`
2. 📖 **Read** [examples.py](examples.py)
3. ⚙️ **Customize** `config/atulya_config.yaml`
4. 🚀 **Deploy** with `docker-compose up -d`
5. 🎓 **Learn** more in PROJECT_SUMMARY.md

---

<div align="center">

**Happy automating! 🎉**

Atulya is always learning and improving.

