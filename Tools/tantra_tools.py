"""
Tantra Tools - Utility functions for Atulya Tantra AGI
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

def get_user_id() -> str:
    """Get or create a unique user ID"""
    user_id_file = Path("user_id.txt")
    
    if user_id_file.exists():
        try:
            with open(user_id_file, 'r') as f:
                return f.read().strip()
        except:
            pass
    
    # Generate new user ID
    user_id = str(uuid.uuid4())
    
    try:
        with open(user_id_file, 'w') as f:
            f.write(user_id)
    except:
        pass
    
    return user_id

def get_session_paths(user_id: str) -> Dict[str, str]:
    """Get session file paths for a user"""
    sessions_dir = Path("sessions")
    sessions_dir.mkdir(exist_ok=True)
    
    user_dir = sessions_dir / user_id
    user_dir.mkdir(exist_ok=True)
    
    return {
        'session': str(user_dir / f"session_{datetime.now().strftime('%Y%m%d')}.jsonl"),
        'latest': str(user_dir / "latest.jsonl")
    }

def append_jsonl(file_path: str, data: Dict[str, Any]) -> bool:
    """Append data to a JSONL file"""
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')
        return True
    except Exception as e:
        print(f"Error appending to {file_path}: {e}")
        return False

def backup_file(file_path: str, user_id: str) -> bool:
    """Create a backup of a file"""
    try:
        if not os.path.exists(file_path):
            return True
        
        backup_dir = Path("backups") / user_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f"{Path(file_path).stem}_{timestamp}.jsonl"
        
        import shutil
        shutil.copy2(file_path, backup_path)
        return True
    except Exception as e:
        print(f"Error backing up {file_path}: {e}")
        return False

def load_memory(user_id: str) -> Dict[str, Any]:
    """Load user memory from file"""
    memory_file = Path("memory") / f"{user_id}_memory.json"
    
    if memory_file.exists():
        try:
            with open(memory_file, 'r') as f:
                return json.load(f)
        except:
            pass
    
    return {'name': 'friend', 'preferences': {}}

def save_memory(user_id: str, memory: Dict[str, Any]) -> bool:
    """Save user memory to file"""
    try:
        memory_dir = Path("memory")
        memory_dir.mkdir(exist_ok=True)
        
        memory_file = memory_dir / f"{user_id}_memory.json"
        
        with open(memory_file, 'w') as f:
            json.dump(memory, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving memory: {e}")
        return False

def get_config() -> Dict[str, Any]:
    """Get configuration settings"""
    config_file = Path("config.json")
    
    default_config = {
        "ai_provider": "ollama",
        "ollama_model": "gemma2:2b",
        "ollama_url": "http://localhost:11434",
        "voice_enabled": True,
        "autonomous_operations": False,
        "streaming_enabled": True
    }
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except:
            pass
    
    return default_config

def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration settings"""
    try:
        with open("config.json", 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False