"""Utility functions for Atulya Launch.

Provides platform detection, config file management, password generation, service
management, and template rendering helpers.
"""

import os
import sys
import subprocess
import secrets
import string
import socket
import logging
import threading
from pathlib import Path
from typing import Any

import yaml


CONFIG_DIR: Path = Path.home() / ".atulya-launch"
CONFIG_FILE: Path = CONFIG_DIR / "config.yaml"

TEMPLATES_DIR: Path = Path(__file__).parent / "templates"

_config_lock = threading.Lock()


def is_linux() -> bool:
    """Check if the current platform is Linux."""
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    """Check if the current platform is macOS."""
    return sys.platform == "darwin"


def is_windows() -> bool:
    """Check if the current platform is Windows."""
    return sys.platform == "win32"


def get_platform() -> str:
    """Return a normalized platform name: linux, macos, windows, or sys.platform."""
    if is_linux():
        return "linux"
    if is_macos():
        return "macos"
    if is_windows():
        return "windows"
    return sys.platform


def run_command(command: str | list[str], capture_output: bool = True, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess | subprocess.CalledProcessError | None:
    """Run a shell command and return the result."""
    if isinstance(command, str):
        command = command.split()
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=True,
            check=check,
            timeout=timeout,
        )
        return result
    except subprocess.CalledProcessError as error:
        return error
    except FileNotFoundError:
        return None


def load_config() -> dict:
    """Load the YAML config file, returning an empty dict if missing."""
    if not CONFIG_FILE.exists():
        return {}
    with _config_lock:
        with open(CONFIG_FILE, "r") as file_handle:
            return yaml.safe_load(file_handle) or {}


def save_config(config_data: dict) -> None:
    """Save a dict to the YAML config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with _config_lock:
        with open(CONFIG_FILE, "w") as file_handle:
            yaml.dump(config_data, file_handle, default_flow_style=False)


def get_config_value(key_path: str, default: Any = None) -> Any:
    """Get a nested config value using a dot-separated key path."""
    config_data = load_config()
    keys = key_path.split(".")
    current = config_data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
    return current if current is not None else default


def set_config_value(key_path: str, value: Any) -> None:
    """Set a nested config value using a dot-separated key path and persist."""
    config_data = load_config()
    keys = key_path.split(".")
    current = config_data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
    save_config(config_data)


def generate_password(length: int = 24) -> str:
    """Generate a cryptographically random password of the given length."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Check whether a TCP port is available on the given host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        result = sock.connect_ex((host, port))
        return result != 0


def get_service_manager() -> str | None:
    """Detect the system service manager (systemd, launchd, windows, or None)."""
    if is_linux():
        return "systemd"
    if is_macos():
        return "launchd"
    if is_windows():
        return "windows"
    return None


def service_action(action: str, service_name: str) -> subprocess.CompletedProcess | subprocess.CalledProcessError | None:
    """Perform a service action (start, stop, restart, enable, disable, status)."""
    service_manager = get_service_manager()
    if service_manager == "systemd":
        command = ["systemctl", action, service_name]
        return run_command(command)
    if service_manager == "launchd":
        plist_path = f"/Library/LaunchDaemons/{service_name}.plist"
        if action == "enable":
            return run_command(["launchctl", "load", plist_path])
        if action == "disable":
            return run_command(["launchctl", "unload", plist_path])
        if action == "start":
            return run_command(["launchctl", "start", service_name])
        if action == "stop":
            return run_command(["launchctl", "stop", service_name])
        if action == "restart":
            run_command(["launchctl", "stop", service_name])
            return run_command(["launchctl", "start", service_name])
        if action == "status":
            return run_command(["launchctl", "list", service_name])
    if service_manager == "windows":
        if action in ("start", "stop", "restart"):
            cmd = ["sc.exe", action, service_name]
            return run_command(cmd)
        if action == "enable":
            return run_command(["sc.exe", "config", service_name, "start=", "auto"])
        if action == "disable":
            return run_command(["sc.exe", "config", service_name, "start=", "disabled"])
        if action == "status":
            return run_command(["sc.exe", "query", service_name])
    return None


def service_exists(service_name: str) -> bool:
    """Check whether the named service is installed and active."""
    service_manager = get_service_manager()
    if service_manager == "systemd":
        result = run_command(["systemctl", "is-active", service_name], check=False)
        return result is not None and result.returncode == 0
    if service_manager == "launchd":
        result = run_command(["launchctl", "list"], check=False)
        if result and result.stdout:
            return service_name in result.stdout
        return False
    if service_manager == "windows":
        result = run_command(["sc.exe", "query", service_name], check=False)
        if result and result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip().startswith("STATE"):
                    if "RUNNING" in line:
                        return True
                    else:
                        return False
        return False
    return False


def render_template(template_name: str, variables: dict) -> str | None:
    """Render a Jinja2 template with the given variables dict."""
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        return None
    from jinja2 import Environment, FileSystemLoader
    env_loader = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env_loader.get_template(template_name)
    return template.render(**variables)


def ensure_config_dir() -> Path:
    """Create all required config subdirectories and return the config dir."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    sites_dir = CONFIG_DIR / "sites"
    sites_dir.mkdir(exist_ok=True)
    ssl_dir = CONFIG_DIR / "ssl"
    ssl_dir.mkdir(exist_ok=True)
    backups_dir = CONFIG_DIR / "backups"
    backups_dir.mkdir(exist_ok=True)
    dbs_dir = CONFIG_DIR / "databases"
    dbs_dir.mkdir(exist_ok=True)
    users_dir = CONFIG_DIR / "users"
    users_dir.mkdir(exist_ok=True)
    ai_models_dir = CONFIG_DIR / "ai-models"
    ai_models_dir.mkdir(exist_ok=True)
    logs_dir = CONFIG_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)
    return CONFIG_DIR


def linux_command(command: str | list[str], capture_output: bool = True, check: bool = False, timeout: int = 60) -> subprocess.CompletedProcess | subprocess.CalledProcessError | None:
    """Run a Linux-only command; warn and return a mock success on other platforms."""
    if is_linux():
        return run_command(command, capture_output, check, timeout)
    else:
        logging.warning(f"Command {command} is Linux-only and was skipped on {get_platform()}")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
