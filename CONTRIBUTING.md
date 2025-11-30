# Contributing to Atulya Tantra

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/yourusername/atulya-tantra.git
   cd atulya-tantra
   ```

3. Install in development mode:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

## Project Structure

- `atulya_tantra/` - Main package modules
- `tests/` - Test suite
- `models/cache/` - Model storage (not tracked in git)
- `main.py` - Entry point

## Running Tests

```bash
# Voice I/O tests
python tests/test_voice.py

# Camera tests
python tests/test_camera.py

# Vision AI tests (requires model download)
python tests/test_vision.py
```

## Code Style

- Follow PEP 8
- Add docstrings to functions and classes
- Keep functions focused and modular
- Add type hints where appropriate

## Adding Features

1. Create a feature branch
2. Implement your changes
3. Add tests
4. Update documentation
5. Submit a pull request

## Reporting Issues

Please include:
- Python version
- OS and version
- Steps to reproduce
- Error messages
- Expected vs actual behavior

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
