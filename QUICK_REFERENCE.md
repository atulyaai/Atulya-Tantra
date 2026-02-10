# Quick Reference Guide - Atulya

## 🚀 Quick Start (60 seconds)

```bash
# Clone and setup
git clone https://github.com/atulyaai/Atulya-Tantra.git
cd Atulya-Tantra

# Install and run
pip install -r requirements.txt
python quickstart.py
```

## 📝 Common Commands

| Command | Purpose |
|---------|---------|
| `python main.py task "Task description"` | Execute a task |
| `python main.py status` | Show system status |
| `python main.py evolution` | Show evolution metrics |
| `python main.py interactive` | Interactive mode |
| `python examples.py` | Run examples |
| `pytest tests/` | Run tests |

## 🎯 Core Concepts in 1 Minute

### Tasks
Instructions Atulya executes:
```python
result = atulya.execute_task("What is AI?")
```

### Skills
Atulya learns and improves:
```python
atulya.acquire_skill("web_scraping", {"level": "advanced"})
```

### Memory
Two-level storage system:
```python
atulya.memory.search_similar("web scraping")
```

### Evolution
Continuous self-improvement:
```python
metrics = atulya.evolution.get_metrics()
```

### Automation
Schedule and automate tasks:
```python
scheduler.schedule_task("id", func, datetime.now(), repeat="daily")
```

## 📊 System Status

```python
from atulya import Atulya

atulya = Atulya("Atulya")
status = atulya.get_evolution_status()

# View metrics
print(f"Tasks: {status['stats']['tasks_executed']}")
print(f"Skills: {status['stats']['skills_learned']}")
print(f"Generation: {status['evolution_metrics']['generation']}")
print(f"Fitness: {status['evolution_metrics']['avg_fitness']}")
```

## 🛠️ Configuration

Edit `config/atulya_config.yaml`:

```yaml
core:
  max_workers: 4
  debug_mode: false

memory:
  short_term_max: 1000
  long_term_enabled: true

evolution:
  learning_rate: 0.001
  mutation_rate: 0.05
```

## 🧠 Task Types

### Information Retrieval
```python
atulya.execute_task("What is the latest AI trend?")
```

### Execution
```python
atulya.execute_task("Execute the backup procedure")
```

### Analysis
```python
atulya.execute_task("Analyze the dataset patterns")
```

### Learning
```python
atulya.execute_task("Learn about quantum computing")
```

## 📚 Skill Management

```python
# Add skill
atulya.acquire_skill("python_coding", {"version": "3.10"})

# Use skill
atulya.skill_manager.use_skill("python_coding")

# List skills
skills = atulya.skill_manager.list_skills()

# Check proficiency
for skill in skills:
    print(f"{skill['name']}: {skill['proficiency']:.0%}")
```

## 💾 Memory Operations

```python
# Store result
atulya.memory.store_task_result("task", result)

# Search similar
similar = atulya.memory.search_similar("query", threshold=0.7)

# Consolidate
atulya.memory.consolidate_memory()

# Get size
size = atulya.memory.get_size()
```

## ⚡ Automation Rules

```python
from atulya.automation.task_scheduler import TaskScheduler

scheduler = TaskScheduler()

# Create rule
def trigger():
    return condition_met

def action():
    atulya.execute_task("Automated action")

scheduler.add_automation_rule("rule_id", trigger, action)

# Evaluate
results = scheduler.evaluate_automation_rules()
```

## 🔌 Integrations

```python
from atulya.integrations.integration_manager import IntegrationManager, APIIntegration

manager = IntegrationManager()

# Register API
api = APIIntegration("api_name", "https://api.example.com")
manager.register_integration("api", api)

# Connect
manager.connect_all()

# Execute
result = manager.execute_integration("api", "endpoint", {"param": "value"})
```

## 📈 Evolution Tracking

```python
# Get metrics
metrics = atulya.evolution.get_metrics()

print(f"Generation: {metrics['generation']}")
print(f"Avg Fitness: {metrics['avg_fitness']}")
print(f"Max Fitness: {metrics['max_fitness']}")
print(f"Progress: {metrics['evolution_progress']}")

# Boost learning
boost = atulya.evolution.boost_learning()
```

## 🧪 Testing

```bash
# All tests
pytest tests/

# Specific test
pytest tests/test_atulya.py::TestAtulyaCore

# With coverage
pytest --cov=atulya tests/

# Verbose
pytest -v tests/
```

## 🐳 Docker Usage

```bash
# Run with Docker Compose (includes Redis & PostgreSQL)
docker-compose up -d

# Run standalone image
docker run -it atulya:latest

# Interactive mode
docker run -it atulya:latest python main.py interactive
```

## ⚙️ Advanced: Custom Agent

```python
from atulya.agents.task_agent import TaskAgent

class CustomAgent(TaskAgent):
    def execute(self, task, context=None):
        # Custom logic
        return super().execute(task, context)
```

## 📁 File Structure

```
atulya/
├── core/            # NLP, reasoning, main engine
├── agents/          # Task execution
├── memory/          # Memory management
├── evolution/       # Self-improvement
├── skills/          # Skill management
├── automation/      # Scheduling, rules
└── integrations/    # External services
```

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Import error | `pip install -r requirements.txt` |
| Memory full | `atulya.memory.optimize()` |
| Low fitness | `atulya.evolution.boost_learning()` |
| Slow execution | Enable caching in config |

## 📖 Documentation Files

- [README.md](README.md) - Overview
- [GETTING_STARTED.md](GETTING_STARTED.md) - Detailed guide
- [INSTALLATION.md](INSTALLATION.md) - Setup instructions
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development guide
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Full architecture

## 🔗 Useful Links

- GitHub: https://github.com/atulyaai/Atulya-Tantra
- Issues: https://github.com/atulyaai/Atulya-Tantra/issues
- Email: team@atulya.ai

## ✅ Checklist: First Steps

- [ ] Clone repository
- [ ] Install dependencies
- [ ] Run `python quickstart.py`
- [ ] Read GETTING_STARTED.md
- [ ] Try basic task execution
- [ ] Learn a skill
- [ ] Run examples
- [ ] Explore configuration

## 📊 Key Metrics to Monitor

```python
status = atulya.get_evolution_status()

# Essential metrics
tasks = status['stats']['tasks_executed']
skills = status['stats']['skills_learned']
fitness = status['evolution_metrics']['avg_fitness']
generation = status['evolution_metrics']['generation']
memory = status['memory_size']['short_term']
```

## 🎓 Learning Path

1. **Beginner**: Run quickstart, read GETTING_STARTED
2. **Intermediate**: Execute custom tasks, learn skills
3. **Advanced**: Create automation rules, integrate APIs
4. **Expert**: Extend agents, optimize evolution

---

**Version**: 0.1.0 | **Updated**: Feb 2026 | **Status**: Ready ✅
