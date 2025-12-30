import os
import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[BOOTSTRAP] %(message)s")
logger = logging.getLogger("Bootstrap")

def check_dependencies():
    logger.info("Checking dependencies (pip install -r requirements.txt)...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    except Exception as e:
        logger.error(f"Failed to install dependencies: {e}")
        return False
    return True

def verify_env():
    logger.info("Verifying environment (.env)...")
    if not os.path.exists(".env"):
        logger.warning(".env not found. Creating from example...")
        if os.path.exists(".env.example"):
            import shutil
            shutil.copy(".env.example", ".env")
        else:
            with open(".env", "w") as f:
                f.write("GEMINI_API_KEY=your_key_here\n")
    
    # Check for Gemini Key
    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") == "your_key_here":
        logger.error("GEMINI_API_KEY not set in .env. Advisor brain will be disabled.")
    else:
        logger.info("GEMINI_API_KEY detected.")
    return True

def download_local_model():
    logger.info("Initializing Local Brain (RWKV)...")
    try:
        # We manually trigger the loader's download logic
        sys.path.append(os.getcwd())
        from core.brain import RWKVLoader
        loader = RWKVLoader()
        if not loader._model_exists():
            logger.info("Model missing. Starting download (~800MB). This may take a while...")
            # We mock a trace id for the download
            loader._download_model("BOOTSTRAP")
        else:
            logger.info("Local model verified: RWKV-6-World ready.")
    except Exception as e:
        logger.error(f"Failed to initialize local model: {e}")
        logger.info("Tip: Ensure 'huggingface_hub' and 'rwkv' are installed.")
        return False
    return True

if __name__ == "__main__":
    logger.info("=== ATULYA TANTRA BOOTSTRAP ===")
    if check_dependencies() and verify_env() and download_local_model():
        logger.info("SUCCESS: System is ready for JARVIS activation.")
        logger.info("RUN: python launch.py")
    else:
        logger.error("FAILURE: Setup incomplete. Please check the logs above.")
        sys.exit(1)
