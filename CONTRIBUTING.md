# 🤝 Contributing to Atulya Tantra

**Welcome to our project!**

We're excited that you're interested in contributing to Atulya Tantra. This document outlines our development process and guidelines.

---

## 🎯 Our Values

- **Quality over Quantity** - We value well-written, tested code
- **Collaboration** - We work together and help each other
- **Documentation** - We document our code and decisions
- **Innovation** - We encourage new ideas and approaches
- **Professionalism** - We maintain high standards

---

## 🚀 Getting Started

### 1. Fork the Repository

```bash
# Fork on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/Atulya-Tantra.git
cd Atulya-Tantra
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest black flake8 mypy
```

### 3. Verify Installation

```bash
# Run tests
python -m testing

# Check code style
black --check .
flake8 .
mypy .
```

---

## 📋 Development Workflow

### Our Process

1. **Create Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write code
   - Add tests
   - Update documentation

3. **Test Thoroughly**
   ```bash
   python -m testing
   python testing/test_deep_analysis.py
   ```

4. **Format Code**
   ```bash
   black .
   flake8 .
   ```

5. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   ```

6. **Push & Create PR**
   ```bash
   git push origin feature/your-feature-name
   # Create Pull Request on GitHub
   ```

---

## 💻 Code Standards

### Python Style Guide

We follow **PEP 8** with these conventions:

```python
"""
Module docstring - what this module does.
"""

from typing import Dict, List, Optional
from core.logger import get_logger

logger = get_logger(__name__)


class MyClass:
    """Class docstring - what this class does."""
    
    def __init__(self, param: str):
        """
        Initialize MyClass.
        
        Args:
            param: Parameter description
        """
        self.param = param
    
    def my_method(self, value: int) -> Dict[str, Any]:
        """
        Method docstring - what this method does.
        
        Args:
            value: Value description
            
        Returns:
            Dictionary containing result
            
        Raises:
            ValueError: If value is invalid
        """
        if value < 0:
            raise ValueError("Value must be positive")
        
        return {'result': value * 2}
```

### Type Hints

Always use type hints:

```python
# Good
def process_message(message: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    pass

# Bad
def process_message(message, context=None):
    pass
```

### Documentation

Use Google-style docstrings:

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description of what the function does.
    
    Longer description if needed, explaining the logic
    and any important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When value is invalid
        
    Example:
        >>> result = function_name("test", 42)
        >>> print(result)
        True
    """
    pass
```

---

## 🧪 Testing Guidelines

### Writing Tests

1. **Test File Location**
   ```
   testing/test_<module_name>.py
   ```

2. **Test Class Naming**
   ```python
   class TestMyFeature(unittest.TestCase):
       pass
   ```

3. **Test Method Naming**
   ```python
   def test_feature_does_something(self):
       """Test that feature does something correctly"""
       pass
   ```

### Test Example

```python
import unittest
from protocols.jarvis import JarvisInterface


class TestJarvisInterface(unittest.TestCase):
    """Test JARVIS interface functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.jarvis = JarvisInterface()
    
    def test_initialization(self):
        """Test interface initializes correctly"""
        self.assertIsNotNone(self.jarvis)
        self.assertFalse(self.jarvis.is_active)
    
    def test_activation(self):
        """Test interface activation"""
        result = asyncio.run(self.jarvis.activate())
        self.assertTrue(self.jarvis.is_active)
        self.assertEqual(result['status'], 'active')
```

---

## 📝 Commit Message Guidelines

We follow **Conventional Commits**:

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat:** New feature
- **fix:** Bug fix
- **docs:** Documentation changes
- **style:** Code style changes (formatting)
- **refactor:** Code refactoring
- **test:** Adding or updating tests
- **chore:** Maintenance tasks

### Examples

```bash
# Feature
git commit -m "feat(jarvis): add emotion detection to personality engine"

# Bug fix
git commit -m "fix(skynet): resolve agent coordination race condition"

# Documentation
git commit -m "docs(readme): update installation instructions"

# Refactor
git commit -m "refactor(core): improve logging performance"
```

---

## 🏗️ Architecture Guidelines

### Module Organization

```
module_name/
├── __init__.py          # Module exports
├── interface.py         # Public interface
├── implementation.py    # Implementation details
└── utils.py            # Module-specific utilities
```

### Adding New Features

1. **Plan First**
   - Design the interface
   - Consider integration points
   - Document the approach

2. **Implement Incrementally**
   - Start with interface
   - Add implementation
   - Write tests
   - Update docs

3. **Follow Patterns**
   - Use existing patterns
   - Maintain consistency
   - Follow SOLID principles

---

## 🔍 Code Review Process

### What We Look For

1. **Functionality**
   - Does it work correctly?
   - Are edge cases handled?

2. **Tests**
   - Are there comprehensive tests?
   - Do all tests pass?

3. **Code Quality**
   - Is it readable?
   - Is it maintainable?
   - Does it follow our standards?

4. **Documentation**
   - Are docstrings complete?
   - Is README updated if needed?

5. **Performance**
   - Is it efficient?
   - Are there any bottlenecks?

### Review Response

- Be respectful and constructive
- Ask questions if unclear
- Make suggested changes
- Respond to all comments

---

## 🎨 Adding New Protocols

### Protocol Structure

```python
# protocols/my_protocol/__init__.py
"""My Protocol - Description"""

from .interface import MyProtocolInterface

__all__ = ['MyProtocolInterface']


# protocols/my_protocol/interface.py
"""My Protocol - Main Interface"""

from core.logger import get_logger

logger = get_logger('protocols.my_protocol')


class MyProtocolInterface:
    """My Protocol implementation"""
    
    def __init__(self):
        logger.info("My Protocol initialized")
    
    async def activate(self):
        """Activate protocol"""
        pass
```

---

## 🤖 Adding New Agents

### Agent Structure

```python
from protocols.skynet import BaseAgent, AgentType


class MyAgent(BaseAgent):
    """My specialized agent"""
    
    def __init__(self):
        super().__init__(
            AgentType.CUSTOM,
            "MyAgent",
            config={}
        )
    
    async def execute(self, task: str, context: Dict = None):
        """Execute agent task"""
        # Implementation
        return {'success': True}
```

---

## 📚 Documentation Standards

### README Updates

Update README when:
- Adding major features
- Changing installation process
- Modifying API
- Adding new dependencies

### Code Comments

```python
# Good - Explain WHY, not WHAT
# Use cache to avoid redundant API calls
cache = load_cache()

# Bad - States the obvious
# Load the cache
cache = load_cache()
```

---

## 🐛 Reporting Issues

### Bug Reports

Include:
- Clear description
- Steps to reproduce
- Expected behavior
- Actual behavior
- System information
- Error messages/logs

### Feature Requests

Include:
- Clear description
- Use case
- Expected behavior
- Why it's useful
- Possible implementation

---

## 📊 Pull Request Checklist

Before submitting:

- [ ] Code follows our style guide
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] No merge conflicts
- [ ] Code is formatted (black)
- [ ] Type hints added
- [ ] Docstrings complete

---

## 🎓 Learning Resources

### Our Codebase
- Read `ARCHITECTURE.md` for system design
- Check `PROJECT_INFO.md` for project details
- Review existing code for patterns

### Python Best Practices
- [PEP 8](https://pep8.org/)
- [Type Hints](https://docs.python.org/3/library/typing.html)
- [Async/Await](https://docs.python.org/3/library/asyncio.html)

### Testing
- [unittest](https://docs.python.org/3/library/unittest.html)
- [pytest](https://docs.pytest.org/)

---

## 💬 Communication

### Where to Ask Questions

- **GitHub Issues** - Bug reports, feature requests
- **Pull Requests** - Code-specific discussions
- **Email** - admin@atulvij.com

### Response Time

We aim to respond:
- Critical bugs: Within 24 hours
- Features/enhancements: Within 1 week
- Questions: Within 3 days

---

## 🏆 Recognition

### Contributors

We recognize contributors:
- In commit history
- In CHANGELOG.md
- In project documentation
- Special thanks for major contributions

---

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## 🙏 Thank You!

Thank you for contributing to Atulya Tantra! Our project is better because of contributors like you.

**Together, we're building the future of personal AI.**

---

<div align="center">

**Questions? Need Help?**

Reach out at admin@atulvij.com

**Happy Contributing!** 🚀

</div>

