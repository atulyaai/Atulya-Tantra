# Contributing to Atulya

We welcome contributions! Here's how to get involved.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Report issues responsibly
- No harassment or discrimination

## Getting Started

1. Fork the repository
2. Clone your fork:
```bash
git clone https://github.com/YOUR_USERNAME/Atulya-Tantra.git
```

3. Create a feature branch:
```bash
git checkout -b feature/your-feature-name
```

4. Set up development environment:
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -e ".[dev]"
```

## Development Workflow

### Before Coding

- Check existing issues and pull requests
- Create an issue to discuss major changes
- Follow the existing code style

### Writing Code

1. **Follow PEP 8:**
```bash
black atulya/
flake8 atulya/
```

2. **Add type hints:**
```python
def process_task(task: str, context: Dict[str, Any]) -> Dict:
    """Process a task with given context."""
    pass
```

3. **Write docstrings:**
```python
def execute_task(self, task: str) -> Dict:
    """
    Execute a task.
    
    Args:
        task: Task description
        
    Returns:
        Task execution result
    """
```

4. **Add tests:**
```python
def test_task_execution(self):
    """Test task execution."""
    result = self.assistant.execute_task("test")
    self.assertTrue(result["success"])
```

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_atulya.py

# Run with coverage
pytest --cov=atulya tests/
```

## Commit Guidelines

- Use clear, descriptive commit messages
- Start with a verb (Add, Fix, Update, etc.)
- Reference issues: `Fix #123`

Examples:
```
Add skill learning module
Fix memory consolidation bug
Update evolution engine parameters
Refactor NLP engine for better performance
```

## Pull Request Process

1. Update documentation
2. Add/update tests for new features
3. Run all tests:
```bash
pytest tests/
black --check atulya/
flake8 atulya/
mypy atulya/
```

4. Create pull request with:
   - Clear title and description
   - Reference to related issues
   - List of changes
   - Any breaking changes

5. Respond to review feedback

## Areas for Contribution

### Core Engine
- Performance optimization
- New reasoning algorithms
- Memory efficiency improvements

### Agents & Automation
- New task types
- Advanced scheduling
- Workflow automation

### Integration
- LLM providers (GPT-4, Claude, etc.)
- Database drivers
- API connectors

### Skills & Learning
- New skill frameworks
- Improved proficiency tracking
- Knowledge transfer mechanisms

### Testing
- Unit test coverage
- Integration tests
- Performance benchmarks

### Documentation
- Usage guides
- API documentation
- Tutorial content

## Running the Project

```bash
# Quick start
python quickstart.py

# CLI interface
python main.py task "Your task here"

# Examples
python examples.py

# Tests
pytest tests/

# Interactive mode
python main.py interactive
```

## Project Structure

```
atulya/
├── core/          # Core AI engine
├── agents/        # Task agents
├── memory/        # Memory management
├── evolution/     # AGI evolution
├── skills/        # Skill management
├── automation/    # Task automation
└── integrations/  # External services

config/           # Configuration files
tests/            # Unit tests
examples.py       # Usage examples
main.py          # CLI interface
```

## Release Process

1. Update version in:
   - `atulya/__init__.py`
   - `pyproject.toml`
   - `README.md`

2. Create release notes
3. Tag release: `git tag v0.x.x`
4. Build package: `python -m build`
5. Publish to PyPI: `twine upload dist/*`

## Questions?

- Open an issue
- Join discussions
- Email: team@atulya.ai

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Atulya! 🚀
