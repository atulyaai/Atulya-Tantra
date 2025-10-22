"""
File utilities for Atulya Tantra AGI
Safe file operations with error handling
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional


def safe_read_file(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """Safely read a file with error handling"""
    try:
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}
        
        if not path.is_file():
            return {"error": f"Path is not a file: {file_path}"}
        
        # Check file size (limit to 10MB)
        if path.stat().st_size > 10 * 1024 * 1024:
            return {"error": f"File too large: {file_path}"}
        
        with open(path, 'r', encoding=encoding) as f:
            content = f.read()
        
        return {
            "success": True,
            "content": content,
            "size": len(content),
            "path": str(path)
        }
        
    except PermissionError:
        return {"error": f"Permission denied: {file_path}"}
    except UnicodeDecodeError:
        return {"error": f"Unable to decode file: {file_path}"}
    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}


def safe_write_file(file_path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """Safely write to a file with error handling"""
    try:
        path = Path(file_path)
        
        # Create directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temporary file first, then move
        temp_path = path.with_suffix(path.suffix + '.tmp')
        
        with open(temp_path, 'w', encoding=encoding) as f:
            f.write(content)
        
        # Move to final location
        shutil.move(str(temp_path), str(path))
        
        return {
            "success": True,
            "path": str(path),
            "size": len(content)
        }
        
    except PermissionError:
        return {"error": f"Permission denied: {file_path}"}
    except Exception as e:
        return {"error": f"Error writing file: {str(e)}"}


def safe_search_files(directory: str, pattern: str = "*", recursive: bool = True) -> Dict[str, Any]:
    """Safely search for files with error handling"""
    try:
        path = Path(directory)
        if not path.exists():
            return {"error": f"Directory not found: {directory}"}
        
        if not path.is_dir():
            return {"error": f"Path is not a directory: {directory}"}
        
        if recursive:
            files = list(path.rglob(pattern))
        else:
            files = list(path.glob(pattern))
        
        # Filter to only files
        files = [f for f in files if f.is_file()]
        
        return {
            "success": True,
            "files": [str(f) for f in files],
            "count": len(files),
            "directory": str(path)
        }
        
    except PermissionError:
        return {"error": f"Permission denied: {directory}"}
    except Exception as e:
        return {"error": f"Error searching files: {str(e)}"}


def list_dir_safe(directory: str) -> Dict[str, Any]:
    """Safely list directory contents with error handling"""
    try:
        path = Path(directory)
        if not path.exists():
            return {"error": f"Directory not found: {directory}"}
        
        if not path.is_dir():
            return {"error": f"Path is not a directory: {directory}"}
        
        items = []
        for item in path.iterdir():
            items.append({
                "name": item.name,
                "path": str(item),
                "is_file": item.is_file(),
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else None
            })
        
        return {
            "success": True,
            "items": items,
            "count": len(items),
            "directory": str(path)
        }
        
    except PermissionError:
        return {"error": f"Permission denied: {directory}"}
    except Exception as e:
        return {"error": f"Error listing directory: {str(e)}"}


def safe_delete_file(file_path: str) -> Dict[str, Any]:
    """Safely delete a file with error handling"""
    try:
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}
        
        if not path.is_file():
            return {"error": f"Path is not a file: {file_path}"}
        
        path.unlink()
        
        return {
            "success": True,
            "path": str(path)
        }
        
    except PermissionError:
        return {"error": f"Permission denied: {file_path}"}
    except Exception as e:
        return {"error": f"Error deleting file: {str(e)}"}


def safe_create_dir(dir_path: str) -> Dict[str, Any]:
    """Safely create a directory with error handling"""
    try:
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)
        
        return {
            "success": True,
            "path": str(path)
        }
        
    except PermissionError:
        return {"error": f"Permission denied: {dir_path}"}
    except Exception as e:
        return {"error": f"Error creating directory: {str(e)}"}


# Export public API
__all__ = [
    "safe_read_file",
    "safe_write_file",
    "safe_search_files",
    "list_dir_safe",
    "safe_delete_file",
    "safe_create_dir"
]