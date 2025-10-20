#!/usr/bin/env python3
"""
Atulya Tantra - Startup Script
Version: 2.5.0
Main entry point for the application
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/atulya-tantra.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main startup function"""
    try:
        logger.info("Starting Atulya Tantra Level 5 AGI System...")
        
        # Check if we're in development or production mode
        environment = os.getenv("ENVIRONMENT", "development")
        debug = os.getenv("DEBUG", "true").lower() == "true"
        
        logger.info(f"Environment: {environment}")
        logger.info(f"Debug mode: {debug}")
        
        # Import and run the FastAPI application
        import uvicorn
        from src.main import app
        
        # Configure uvicorn
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))
        workers = int(os.getenv("WORKERS", "1" if debug else "4"))
        reload = debug
        
        logger.info(f"Starting server on {host}:{port}")
        logger.info(f"Workers: {workers}")
        logger.info(f"Reload: {reload}")
        
        # Run the application
        uvicorn.run(
            "src.main:app",
            host=host,
            port=port,
            workers=workers if not reload else 1,
            reload=reload,
            log_level="info" if not debug else "debug",
            access_log=True
        )
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Failed to start Atulya Tantra: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
