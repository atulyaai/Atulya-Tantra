import os
import json
import shutil
from datetime import datetime
from typing import Dict, Any, Optional


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def get_user_id() -> str:
    try:
        username = os.getlogin()
    except Exception:
        username = os.environ.get('USERNAME') or os.environ.get('USER') or 'user'
    machine = os.environ.get('COMPUTERNAME') or os.environ.get('HOSTNAME') or 'local'
    return f"{username}@{machine}"


def get_conversations_root() -> str:
    root = os.path.join('data', 'conversations')
    ensure_dir(root)
    return root


def get_user_conversation_dir(user_id: Optional[str] = None) -> str:
    if user_id is None:
        user_id = get_user_id()
    user_dir = os.path.join(get_conversations_root(), sanitize_filename(user_id))
    ensure_dir(user_dir)
    ensure_dir(os.path.join(user_dir, 'sessions'))
    return user_dir


def sanitize_filename(name: str) -> str:
    return ''.join(c for c in name if c.isalnum() or c in ('-', '_', '@', '.')).strip()


def get_session_paths(user_id: Optional[str] = None) -> Dict[str, str]:
    user_dir = get_user_conversation_dir(user_id)
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    session_file = os.path.join(user_dir, 'sessions', f'session-{ts}.jsonl')
    latest_file = os.path.join(user_dir, 'latest.jsonl')
    return { 'session': session_file, 'latest': latest_file }


def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')


def write_atomic(path: str, content: str) -> None:
    ensure_dir(os.path.dirname(path))
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write(content)
    os.replace(tmp_path, path)


def backup_file(src_path: str, user_id: Optional[str] = None) -> Optional[str]:
    if not os.path.exists(src_path):
        return None
    if user_id is None:
        user_id = get_user_id()
    backup_dir = os.path.join(get_user_conversation_dir(user_id), 'backups')
    ensure_dir(backup_dir)
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    dst = os.path.join(backup_dir, f"{os.path.basename(src_path)}.{ts}.bak")
    shutil.copy2(src_path, dst)
    return dst


def list_recent_sessions(user_id: Optional[str] = None, limit: int = 10):
    user_dir = get_user_conversation_dir(user_id)
    sessions_dir = os.path.join(user_dir, 'sessions')
    if not os.path.exists(sessions_dir):
        return []
    files = [os.path.join(sessions_dir, f) for f in os.listdir(sessions_dir) if f.endswith('.jsonl')]
    files.sort(key=os.path.getmtime, reverse=True)
    return files[:limit]


