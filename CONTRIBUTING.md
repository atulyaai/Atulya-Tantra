# Contributing to Atulya Tantra AGI

Thank you for your interest in contributing to Atulya Tantra! We welcome contributions from the community.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

### Our Pledge

- Be respectful and inclusive
- Welcome newcomers
- Be patient with questions
- Provide constructive feedback
- Focus on what is best for the community

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment
4. Create a branch for your changes
5. Make your changes
6. Test your changes
7. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- Ollama (for local AI testing)
- PostgreSQL (optional, for database testing)
- Redis (optional, for caching testing)

### Setup Steps

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/Atulya-Tantra.git
cd Atulya-Tantra

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Copy environment template
cp env.example .env

# Edit .env with your configuration
# Install pre-commit hooks (optional)
pre-commit install
```

## How to Contribute

### Types of Contributions

We welcome many types of contributions:

- **Bug Fixes**: Fix issues in the codebase
- **Features**: Implement new features from the roadmap
- **Documentation**: Improve docs, add examples, fix typos
- **Tests**: Add or improve test coverage
- **Performance**: Optimize existing code
- **Refactoring**: Improve code quality

### Finding Something to Work On

- Check the [Issues](https://github.com/atulyaai/Atulya-Tantra/issues) page
- Look for issues labeled `good first issue` or `help wanted`
- Check the [ROADMAP](ROADMAP.md) for planned features
- Propose your own ideas in Discussions

## Code Style

We follow standard Python coding conventions with specific guidelines:

### Python Style

- **Formatting**: Use `black` for code formatting
- **Linting**: Code must pass `flake8` checks
- **Import Sorting**: Use `isort` for import organization
- **Type Hints**: Use type hints for function signatures
- **Docstrings**: Use Google-style docstrings

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description of function.
    
    Longer description if needed.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When something goes wrong
    """
    pass
```

### Running Code Quality Tools

```bash
# Format code
black Core/ Test/

# Sort imports
isort Core/ Test/

# Run linter
flake8 Core/ Test/

# Type checking
mypy Core/

# Run all checks
./scripts/lint.sh  # Coming soon
```

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `CodeAgent`, `LLMProvider`)
- **Functions/Methods**: `snake_case` (e.g., `get_response`, `send_message`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_TOKENS`, `DEFAULT_MODEL`)
- **Private**: Prefix with `_` (e.g., `_internal_method`)

## Testing

All contributions should include appropriate tests.

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest Test/test_capabilities.py

# Run with coverage
pytest --cov=Core --cov-report=html

# Run only unit tests
pytest Test/unit/

# Run only integration tests
pytest Test/integration/
```

### Writing Tests

```python
import pytest
from Core.brain.llm_provider import LLMProvider

def test_llm_provider_initialization():
    """Test LLM provider initializes correctly"""
    provider = LLMProvider("ollama")
    assert provider.name == "ollama"
    assert provider.is_available()

@pytest.mark.asyncio
async def test_async_function():
    """Test async functionality"""
    result = await some_async_function()
    assert result is not None
```

### Test Coverage

- Aim for 80%+ code coverage
- All new features must have tests
- Bug fixes should include regression tests
- Integration tests for API endpoints
- Unit tests for business logic

## Pull Request Process

### Before Submitting

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make Your Changes**
   - Write clean, readable code
   - Follow the code style guidelines
   - Add tests for your changes
   - Update documentation as needed

3. **Test Your Changes**
   ```bash
   pytest
   black Core/ Test/
   flake8 Core/ Test/
   ```

4. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature X"
   ```
   
   Use conventional commits format:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation
   - `test:` for tests
   - `refactor:` for refactoring
   - `chore:` for maintenance

5. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

### Submitting the PR

1. Go to the original repository on GitHub
2. Click "New Pull Request"
3. Select your fork and branch
4. Fill in the PR template:
   - **Title**: Clear, descriptive title
   - **Description**: What does this PR do?
   - **Related Issues**: Link related issues
   - **Testing**: How was this tested?
   - **Screenshots**: If applicable

### PR Review Process

- Maintainers will review your PR
- Address any requested changes
- Once approved, your PR will be merged
- Your contribution will be credited

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commits follow conventional format
- [ ] PR description is clear and complete
- [ ] No merge conflicts

## Reporting Bugs

### Before Reporting

- Search existing issues to avoid duplicates
- Collect relevant information
- Try to reproduce the bug

### Bug Report Template

```markdown
**Describe the Bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Screenshots**
If applicable, add screenshots.

**Environment:**
- OS: [e.g., Windows 10, Ubuntu 22.04]
- Python Version: [e.g., 3.11.5]
- Version: [e.g., 3.0.0]

**Additional Context**
Any other relevant information.
```

## Feature Requests

We welcome feature suggestions!

### Before Requesting

- Check the [ROADMAP](ROADMAP.md) to see if it's planned
- Search existing feature requests
- Consider if it aligns with project goals

### Feature Request Template

```markdown
**Feature Description**
Clear description of the feature.

**Use Case**
Why is this feature needed?

**Proposed Solution**
How might this work?

**Alternatives Considered**
What other solutions did you consider?

**Additional Context**
Any mockups, examples, or references.
```

## Development Workflow

### Branching Strategy

- `main`: Production-ready code
- `develop`: Development branch
- `feature/*`: New features
- `fix/*`: Bug fixes
- `docs/*`: Documentation updates
- `refactor/*`: Code improvements

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

Example:
```
feat(agents): add code agent with syntax highlighting

- Implement CodeAgent class
- Add syntax highlighting support
- Include code execution capability

Closes #123
```

## Questions?

- **GitHub Discussions**: [Ask questions](https://github.com/atulyaai/Atulya-Tantra/discussions)
- **GitHub Issues**: [Report bugs or request features](https://github.com/atulyaai/Atulya-Tantra/issues)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Atulya Tantra! 🚀

