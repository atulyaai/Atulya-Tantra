# Contributing to Atulya Tantra

Thank you for your interest in contributing! We welcome contributions from the community to make Atulya Tantra even better.

## 🛠️ Development Setup

1. **Fork the repository** on GitHub.
2. **Clone your fork:**
   ```bash
   git clone https://github.com/yourusername/Atulya-Tantra.git
   cd Atulya-Tantra
   ```

3. **Run the installation script:**
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

4. **Activate the environment:**
   ```bash
   source venv/bin/activate
   ```

## 📂 Project Structure

- `atulya_tantra/` - Core package
  - `core.py` - Main engine logic
  - `text_ai.py` - LLM integration
  - `tools.py` - Search, price, and routing tools
  - `memory.py` - RAG memory system
  - `config_loader.py` - Configuration management
- `web/` - Web interface
- `main.py` - CLI entry point
- `config.yaml` - Configuration file

## 🧪 Testing

Since we have streamlined the codebase, please verify your changes manually:

1. **Run the assistant:**
   ```bash
   python main.py
   ```
2. **Test core features:**
   - Voice interaction (if enabled)
   - Text chat
   - Tool usage (ask for prices, search)
   - Memory (tell it a fact, ask it later)

## 📝 Code Style

- **PEP 8:** Follow standard Python style guidelines.
- **Type Hints:** Use type hints for function arguments and return values.
- **Docstrings:** Add clear docstrings to all classes and functions.
- **Imports:** Keep imports organized (standard lib, third-party, local).
- **No Hardcoding:** Use `constants.py` or `config.yaml` for values.

## 🚀 Adding Features

1. **Create a branch:** `git checkout -b feature/my-feature`
2. **Implement changes:** Keep changes focused and modular.
3. **Update documentation:** If you change behavior, update README.md.
4. **Submit PR:** Open a Pull Request with a clear description.

## 🐛 Reporting Issues

Please include:
- Python version
- OS and hardware details (RAM, CPU)
- Logs (check `logs/` directory)
- Steps to reproduce the issue

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.
