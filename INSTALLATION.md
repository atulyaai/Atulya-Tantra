# Installation Guide

## System Requirements

- Python 3.8 or higher
- pip or conda package manager
- 4GB+ RAM recommended
- 2GB+ disk space for dependencies

## Installation Methods

### 1. From Source (Development)

```bash
# Clone the repository
git clone https://github.com/atulyaai/Atulya-Tantra.git
cd Atulya-Tantra

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install additional dependencies
pip install -e ".[ml,nlp,api,database,server,dev]"
```

### 2. Quick Installation (Minimal)

```bash
# Install core dependencies only
pip install -r requirements-core.txt
```

### 3. Docker Installation

```bash
# Build Docker image
docker build -t atulya:latest .

# Run Docker container
docker run -it atulya:latest
```

## Verification

After installation, verify it works:

```bash
# Run quickstart
python quickstart.py

# Or run the CLI
python main.py --help

# Or run examples
python examples.py
```

## Configuration

1. Copy default config:
```bash
cp config/atulya_config.yaml config/atulya_config.local.yaml
```

2. Edit configuration as needed:
```bash
nano config/atulya_config.local.yaml
```

## Optional Dependencies

### Machine Learning
```bash
pip install torch transformers scikit-learn
```

### Natural Language Processing
```bash
pip install spacy nltk
python -m spacy download en_core_web_sm
```

### LLM Integrations
```bash
pip install openai anthropic langchain groq
```

### Database Support
```bash
pip install sqlalchemy redis psycopg2-binary pymongo
```

### Web Server
```bash
pip install fastapi uvicorn
```

## Development Setup

For development and testing:

```bash
pip install -e ".[dev]"
pytest tests/
```

## Troubleshooting

### Issue: ImportError on startup

**Solution:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: Dependencies conflict

**Solution:**
```bash
pip install --upgrade --force-reinstall -r requirements.txt
```

### Issue: CUDA/GPU not found

**Solution:** Install CPU version of PyTorch:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## Uninstallation

```bash
# Remove virtual environment
rm -rf venv

# Or using conda
conda env remove --name atulya
```

## Next Steps

- Read [Getting Started](GETTING_STARTED.md)
- Check [Examples](examples.py)
- Review [Configuration](config/atulya_config.yaml)
- Join [Community](CONTRIBUTING.md)
