# Atulya Tantra - Installation Guide
Version: 2.0.1

## 🚀 Quick Installation

Atulya Tantra provides multiple installation methods for different platforms:

### Option 1: Auto-Installation Scripts (Recommended)

#### Linux/macOS
```bash
# Make script executable and run
chmod +x scripts/install.sh
./scripts/install.sh
```

#### Windows PowerShell
```powershell
# Run as Administrator (recommended)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\scripts\install.ps1
```

#### Cross-Platform Python Installer
```bash
# Works on any platform with Python 3.8+
python scripts/setup.py
```

### Option 2: Manual Installation

#### Prerequisites
- **Python 3.8+** (3.11 recommended)
- **Git** for version control
- **Package Manager** (apt/yum/brew/choco)

#### Step-by-Step Manual Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/atulyaai/Atulya-Tantra.git
   cd Atulya-Tantra
   ```

2. **Create Virtual Environment**
   ```bash
   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   
   # Windows
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Setup Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. **Initialize Data Directories**
   ```bash
   mkdir -p data/{logs,uploads,cache,security,analytics,database}
   mkdir -p data/models/{audio,vision,text}
   ```

6. **Initialize Database**
   ```bash
   python scripts/init_admin_db.py
   ```

7. **Start the Server**
   ```bash
   python server.py
   ```

## 🔧 System Requirements

### Minimum Requirements
- **OS:** Windows 10+, macOS 10.15+, Ubuntu 18.04+
- **RAM:** 4GB (8GB recommended)
- **Storage:** 2GB free space
- **Python:** 3.8+ (3.11 recommended)

### Recommended Requirements
- **OS:** Windows 11, macOS 12+, Ubuntu 20.04+
- **RAM:** 16GB+
- **Storage:** 10GB+ SSD
- **Python:** 3.11
- **GPU:** NVIDIA GPU with CUDA support (optional)

## 📋 API Keys Setup

Edit the `.env` file with your API keys:

```env
# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic API
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Google API
GOOGLE_API_KEY=your_google_api_key_here

# Security Keys (generate random strings)
JWT_SECRET=your_jwt_secret_here
ENCRYPTION_KEY=your_encryption_key_here
REDIS_PASSWORD=your_redis_password_here
```

## 🐳 Docker Installation

### Using Docker Compose (Recommended)
```bash
# Clone repository
git clone https://github.com/atulyaai/Atulya-Tantra.git
cd Atulya-Tantra

# Create .env file
cp .env.example .env
# Edit .env with your API keys

# Start with Docker Compose
docker-compose up -d
```

### Using Dockerfile
```bash
# Build image
docker build -t atulya-tantra .

# Run container
docker run -d -p 8000:8000 --env-file .env atulya-tantra
```

## 🔍 Verification

After installation, verify the system is working:

1. **Check Server Status**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Access Web Interface**
   - Main Interface: http://localhost:8000
   - Admin Panel: http://localhost:8000/admin
   - API Docs: http://localhost:8000/docs

3. **Run Tests**
   ```bash
   python -m pytest testing/ -v
   ```

## 🛠️ Development Setup

### For Developers
```bash
# Install development dependencies
pip install -r requirements.txt
pip install pytest black flake8 mypy

# Run linting
black .
flake8 .
mypy .

# Run tests
pytest testing/ -v --cov=core
```

### IDE Setup
- **VS Code:** Install Python extension and configure workspace
- **PyCharm:** Open project and configure Python interpreter
- **Vim/Neovim:** Use coc.nvim or similar LSP plugins

## 🔧 Configuration

### Unified Configuration System
Atulya Tantra uses a unified configuration system:

- **Main Config:** `configuration/config.yaml`
- **Environment:** `.env` file
- **Runtime:** Environment variables

### Key Configuration Areas
- **AI Models:** Provider settings, model selection, routing
- **Security:** Authentication, encryption, audit logging
- **Performance:** Caching, monitoring, optimization
- **Features:** Feature flags, integrations, plugins

## 🚨 Troubleshooting

### Common Issues

#### Python Environment Issues
```bash
# Fix virtual environment
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Permission Issues (Linux/macOS)
```bash
# Fix permissions
sudo chown -R $USER:$USER .
chmod +x scripts/install.sh
```

#### Windows PowerShell Execution Policy
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Port Already in Use
```bash
# Kill process using port 8000
lsof -ti:8000 | xargs kill -9

# Or use different port
python server.py --port 8001
```

### Getting Help
- **Documentation:** Check README.md and docs/
- **Issues:** GitHub Issues page
- **Discussions:** GitHub Discussions
- **Support:** Create an issue with detailed error logs

## 🔄 Updates

### Updating Atulya Tantra
```bash
# Pull latest changes
git pull origin master

# Update dependencies
pip install -r requirements.txt --upgrade

# Restart server
python server.py
```

### Database Migrations
```bash
# Run migrations (if available)
python scripts/migrate_db.py
```

## 📊 Monitoring

### Health Checks
- **Endpoint:** `/health`
- **Metrics:** `/metrics` (Prometheus format)
- **Logs:** `data/logs/atulya_tantra.log`

### Performance Monitoring
- **Response Times:** Tracked automatically
- **Resource Usage:** CPU, Memory, Disk
- **Error Rates:** Error tracking and alerting

## 🔐 Security

### Security Features
- **JWT Authentication:** Secure token-based auth
- **2FA Support:** Two-factor authentication
- **Audit Logging:** Complete audit trail
- **Encryption:** Data encryption at rest
- **CORS Protection:** Cross-origin request security

### Security Best Practices
1. **Change Default Passwords:** Update admin credentials
2. **Use HTTPS:** Enable SSL/TLS in production
3. **Regular Updates:** Keep system updated
4. **Monitor Logs:** Check security logs regularly
5. **Backup Data:** Regular data backups

## 🎯 Next Steps

After successful installation:

1. **Configure API Keys:** Add your AI provider keys
2. **Test Features:** Try voice, vision, and automation
3. **Customize Settings:** Adjust configuration as needed
4. **Set Up Monitoring:** Configure alerts and monitoring
5. **Create Backups:** Set up automated backups
6. **Join Community:** Connect with other users

---

**Need Help?** Check our [GitHub Issues](https://github.com/atulyaai/Atulya-Tantra/issues) or create a new issue with detailed information about your problem.
