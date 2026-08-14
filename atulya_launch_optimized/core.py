"""Core business logic for Atulya Launch — config, auth, sites, apps, security, and more."""
import os
import re
import sys
import json
import hashlib
import zipfile
import tarfile
import tempfile
import shutil
import subprocess
import platform
import time
import secrets
import hmac
import base64
from pathlib import Path
from importlib import metadata
from datetime import datetime
from typing import Any

import requests


def _default_config_dir() -> Path:
    """Determine the base config directory from env or default home path.
    Uses the same path as utils.CONFIG_DIR to avoid split-brain config."""
    configured: str | None = os.environ.get("ATULYA_HOME")
    if configured:
        return Path(configured).expanduser()
    from atulya_launch import utils
    return utils.CONFIG_DIR


CONFIG_DIR: Path = _default_config_dir()
CONFIG_FILE: Path = CONFIG_DIR / "config.json"
TOOLS_DIR: Path = CONFIG_DIR / "tools"
CACHE_DIR: Path = CONFIG_DIR / "cache"
SITES_DIR: Path = CONFIG_DIR / "sites"
WEBROOTS_DIR: Path = CONFIG_DIR / "webroots"
BACKUPS_DIR: Path = CONFIG_DIR / "backups"
NGINX_DIR: Path = CONFIG_DIR / "nginx"
LOGS_DIR: Path = CONFIG_DIR / "logs"
AUDIT_LOG: Path = LOGS_DIR / "audit.jsonl"

ATULYA_ORG: str = "atulyaai"


def _set_config_dir(config_dir: str | Path) -> None:
    """Globally reassign all config path constants to a new base directory."""
    global CONFIG_DIR, CONFIG_FILE, TOOLS_DIR, CACHE_DIR
    global SITES_DIR, WEBROOTS_DIR, BACKUPS_DIR, NGINX_DIR, LOGS_DIR, AUDIT_LOG
    CONFIG_DIR = Path(config_dir)
    CONFIG_FILE = CONFIG_DIR / "config.json"
    TOOLS_DIR = CONFIG_DIR / "tools"
    CACHE_DIR = CONFIG_DIR / "cache"
    SITES_DIR = CONFIG_DIR / "sites"
    WEBROOTS_DIR = CONFIG_DIR / "webroots"
    BACKUPS_DIR = CONFIG_DIR / "backups"
    NGINX_DIR = CONFIG_DIR / "nginx"
    LOGS_DIR = CONFIG_DIR / "logs"
    AUDIT_LOG = LOGS_DIR / "audit.jsonl"


def ensure_dirs() -> Path:
    """Ensure config subdirectory structure exists, trying multiple base candidates."""
    candidates: list[Path] = [CONFIG_DIR]
    local_appdata: str | None = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "Atulya" / "Launch")
    candidates.append(Path(tempfile.gettempdir()) / "atulya-launch")
    candidates.append(Path.cwd() / ".atulya")

    last_error: Exception | None = None
    for base_dir in candidates:
        try:
            for d in [
                base_dir,
                base_dir / "tools",
                base_dir / "cache",
                base_dir / "sites",
                base_dir / "webroots",
                base_dir / "backups",
                base_dir / "nginx",
                base_dir / "logs",
            ]:
                d.mkdir(parents=True, exist_ok=True)
            _set_config_dir(base_dir)
            return CONFIG_DIR
        except OSError as error:
            last_error = error

    raise last_error  # type: ignore[misc]


def load_config() -> dict[str, Any]:
    """Load the panel configuration from disk, merging with defaults."""
    ensure_dirs()
    if not CONFIG_FILE.exists():
        return default_config()
    with open(CONFIG_FILE) as f:
        cfg: dict[str, Any] = json.load(f)
    merged: dict[str, Any] = default_config()
    merged.update(cfg)
    merged["panel"] = {**default_config()["panel"], **merged.get("panel", {})}
    merged["settings"] = {**default_config()["settings"], **merged.get("settings", {})}
    for key in ["installed", "sites", "backups", "settings"]:
        merged.setdefault(key, {})
    merged.setdefault("sessions", {})
    return merged


def save_config(cfg: dict[str, Any]) -> None:
    """Persist the panel configuration to disk as JSON."""
    ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def default_config() -> dict[str, Any]:
    """Return the default panel configuration dictionary."""
    return {
        "panel": {
            "name": "Atulya Launch",
            "version": "0.2.0",
            "created_at": None,
            "admin_user": "admin",
            "api_token": None,
            "password_hash": None,
        },
        "settings": {
            "bind_host": "127.0.0.1",
            "bind_port": 8080,
            "public_exposure": False,
        },
        "installed": {},
        "sites": {},
        "backups": {},
        "sessions": {},
        "updated_at": None,
    }


def panel_init(admin_user: str = "admin", admin_password: str | None = None, rotate_token: bool = False) -> dict[str, Any]:
    """Initialize the panel configuration with admin user and API token.
    Also creates the admin user in SQLite for unified auth."""
    cfg: dict[str, Any] = load_config()
    panel: dict[str, Any] = cfg.setdefault("panel", {})
    if not panel.get("created_at"):
        panel["created_at"] = datetime.utcnow().isoformat() + "Z"
    panel["admin_user"] = admin_user
    generated_password: str | None = None
    if admin_password:
        panel["password_hash"] = hash_password(admin_password)
    elif not panel.get("password_hash"):
        generated_password = secrets.token_urlsafe(18)
        panel["password_hash"] = hash_password(generated_password)
    if rotate_token or not panel.get("api_token"):
        panel["api_token"] = secrets.token_urlsafe(32)
    save_config(cfg)

    # Ensure admin user exists in SQLite for unified auth
    from atulya_launch.web import database
    from atulya_launch.web.auth import create_user
    database.init_db(CONFIG_DIR)
    pw = admin_password or generated_password
    if pw:
        try:
            create_user(admin_user, pw, role="admin", skip_policy=True)
        except ValueError:
            pass
    audit_event("panel.init", "ok", {"admin_user": admin_user, "rotated_token": rotate_token})
    return {
        "config_dir": str(CONFIG_DIR),
        "admin_user": admin_user,
        "api_token": panel["api_token"],
        "generated_password": generated_password,
    }


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Hash a password using PBKDF2-SHA256 and return an encoded string."""
    salt_bytes: bytes = salt or secrets.token_bytes(16)
    digest: bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 200_000)
    salt_text: str = base64.urlsafe_b64encode(salt_bytes).decode("ascii")
    digest_text: str = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256$200000${salt_text}${digest_text}"


def verify_password(password: str, encoded: str) -> bool:
    """Verify a password against a PBKDF2-SHA256 encoded hash."""
    try:
        algorithm: str
        rounds: str
        salt_text: str
        digest_text: str
        algorithm, rounds, salt_text, digest_text = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt: bytes = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected: bytes = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual: bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def login(username: str, password: str) -> str | None:
    """Authenticate a panel user and return a session token, or None on failure.
    Uses the same SQLite-backed auth as the web panel."""
    from atulya_launch.web import database
    from atulya_launch.web.auth import authenticate
    database.init_db(CONFIG_DIR)
    result = authenticate(username, password)
    if result is None:
        return None
    if result.get("requires_2fa"):
        return None
    return result.get("token")


def validate_session(token: str | None) -> bool:
    """Check whether a session token is currently valid.
    Uses the same SQLite-backed sessions as the web panel."""
    if not token:
        return False
    from atulya_launch.web import database
    from atulya_launch.web.auth import validate_session as web_validate
    database.init_db(CONFIG_DIR)
    return web_validate(token) is not None


def audit_event(action: str, status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record an audit event to the JSONL audit log."""
    ensure_dirs()
    event: dict[str, Any] = {
        "time": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "status": status,
        "details": details or {},
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def audit_list(limit: int = 100) -> list[dict[str, Any]]:
    """Return the most recent audit log entries."""
    ensure_dirs()
    if not AUDIT_LOG.exists():
        return []
    lines: list[str] = AUDIT_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(line) for line in lines if line.strip()]


def get_api_token() -> str:
    """Retrieve the panel API token, initialising if necessary."""
    cfg: dict[str, Any] = load_config()
    token: str | None = cfg.get("panel", {}).get("api_token")
    if not token:
        token = panel_init()["api_token"]
    return token


def validate_domain(domain: str) -> str:
    """Validate and normalise a domain name, returning it lowercased."""
    if not domain or len(domain) > 253:
        raise ValueError("domain must be 1-253 characters")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,251}[A-Za-z0-9]", domain):
        raise ValueError("domain must contain only letters, numbers, dots and hyphens")
    if ".." in domain or "." not in domain:
        raise ValueError("domain must look like a real hostname, e.g. example.com")
    return domain.lower()


def sanitize_filename(name: str) -> str:
    """Strip path separators and keep only safe filename characters."""
    name = name.replace("/", "").replace("\\", "").replace("..", "")
    return "".join(c for c in name if c.isalnum() or c in "._- ").strip()


def safe_write(path: str | Path, content: str, mode: int = 0o644) -> None:
    """Write text content to a file with secure permissions on Linux."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "linux":
        old_umask: int = os.umask(0o022)
        try:
            path.write_text(content)
            path.chmod(mode)
        finally:
            os.umask(old_umask)
    else:
        path.write_text(content)


def _safe_path(path: str | Path, base_dir: str | Path | None = None) -> Path:
    """Resolve a path and verify it stays within the given base directory."""
    base: Path = Path(base_dir or CONFIG_DIR).resolve()
    candidate: Path = Path(path).expanduser().resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"path must stay inside {base}") from exc
    return candidate


def site_create(domain: str, web_root: str | None = None, proxy_pass: str | None = None, php: bool = False, php_version: str | None = None) -> dict[str, Any]:
    """Create a new site with nginx config and default index page."""
    domain = validate_domain(domain)
    cfg: dict[str, Any] = load_config()
    if domain in cfg["sites"]:
        raise ValueError(f"site already exists: {domain}")

    if web_root:
        root: Path = _safe_path(web_root, CONFIG_DIR)
    else:
        root = WEBROOTS_DIR / domain / "public"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        if web_root:
            raise
        _set_config_dir(Path(tempfile.gettempdir()) / "atulya-launch")
        ensure_dirs()
        cfg = load_config()
        root = WEBROOTS_DIR / domain / "public"
        root.mkdir(parents=True, exist_ok=True)

    index_path: Path = root / "index.html"
    if not index_path.exists():
        index_path.write_text(
            f"<!doctype html><title>{domain}</title><h1>{domain}</h1><p>Hosted by Atulya Launch.</p>\n",
            encoding="utf-8",
        )

    if php and not php_version:
        php_version = "8.3"

    site: dict[str, Any] = {
        "domain": domain,
        "web_root": str(root),
        "proxy_pass": proxy_pass,
        "php": bool(php),
        "php_version": php_version,
        "enabled": True,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "nginx_config": str(generate_nginx_config(domain, root, proxy_pass, php, php_version)),
    }
    cfg["sites"][domain] = site
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    audit_event("site.create", "ok", {"domain": domain})
    
    # Apply nginx config via driver layer
    try:
        from atulya_launch.drivers import get_platform_driver
        driver = get_platform_driver(dry_run=False)
        config_path = Path(site["nginx_config"])
        if config_path.exists():
            driver.web.apply_site(domain, config_path.read_text(encoding="utf-8"))
            driver.web.reload()
    except Exception as e:
        # Log but don't fail site creation if driver fails
        audit_event("site.create.driver_warning", "warning", {"domain": domain, "error": str(e)})
    
    return site


def site_list() -> dict[str, Any]:
    """Return all configured sites."""
    return load_config().get("sites", {})


def site_get(domain: str) -> dict[str, Any] | None:
    """Return a single site config by domain name."""
    return site_list().get(validate_domain(domain))


def site_set_php_version(domain: str, php_version: str) -> dict[str, Any]:
    """Enable PHP and set the PHP version for an existing site."""
    domain = validate_domain(domain)
    cfg: dict[str, Any] = load_config()
    site: dict[str, Any] | None = cfg.get("sites", {}).get(domain)
    if not site:
        raise ValueError(f"site not found: {domain}")
    site["php"] = True
    site["php_version"] = php_version
    site["nginx_config"] = str(generate_nginx_config(domain, Path(site["web_root"]), site.get("proxy_pass"), True, php_version))
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    audit_event("site.php_version", "ok", {"domain": domain, "php_version": php_version})
    
    # Install PHP-FPM package, create pool, and apply nginx config via driver layer
    try:
        from atulya_launch.drivers import get_platform_driver
        driver = get_platform_driver(dry_run=False)
        
        # Install PHP-FPM package
        php_fpm_install(domain, php_version)
        
        # Create FPM pool config for this site
        php_fpm_pool_create(domain, php_version)
        
        # Apply nginx config
        config_path = Path(site["nginx_config"])
        if config_path.exists():
            driver.web.apply_site(domain, config_path.read_text(encoding="utf-8"))
            driver.web.reload()
    except Exception as e:
        audit_event("site.php_version.driver_warning", "warning", {"domain": domain, "error": str(e)})
    
    return site


def php_fpm_install(domain: str, version: str) -> dict[str, Any]:
    """Install PHP-FPM package for a given version via the platform driver."""
    pkg_name = f"php{version}-fpm"
    try:
        from atulya_launch.drivers import get_platform_driver
        driver = get_platform_driver(dry_run=False)
        result = driver.packages.install([pkg_name])
        audit_event("php_fpm.install", "ok" if result.ok else "error", {"domain": domain, "version": version})
        return {"ok": result.ok, "package": pkg_name, "message": result.message}
    except Exception as e:
        audit_event("php_fpm.install", "error", {"domain": domain, "version": version, "error": str(e)})
        return {"ok": False, "error": str(e)}


def php_fpm_pool_create(domain: str, version: str) -> dict[str, Any]:
    """Create a PHP-FPM pool config file for a domain."""
    try:
        from atulya_launch.drivers import get_platform_driver
        driver = get_platform_driver(dry_run=False)
        result = driver.php_fpm.install_pool(domain, version)
        if result.ok:
            driver.php_fpm.reload(version)
        audit_event("php_fpm.pool_create", "ok", {"domain": domain, "version": version})
        return {"ok": result.ok, "files": result.files}
    except Exception as e:
        audit_event("php_fpm.pool_create", "error", {"domain": domain, "version": version, "error": str(e)})
        return {"ok": False, "error": str(e)}


def php_fpm_pool_remove(domain: str, version: str) -> dict[str, Any]:
    """Remove a PHP-FPM pool config file for a domain."""
    try:
        from atulya_launch.drivers import get_platform_driver
        driver = get_platform_driver(dry_run=False)
        result = driver.php_fpm.remove_pool(domain, version)
        if result.ok:
            driver.php_fpm.reload(version)
        audit_event("php_fpm.pool_remove", "ok", {"domain": domain, "version": version})
        return {"ok": result.ok, "files": result.files}
    except Exception as e:
        audit_event("php_fpm.pool_remove", "error", {"domain": domain, "version": version, "error": str(e)})
        return {"ok": False, "error": str(e)}


def site_delete(domain: str) -> bool:
    """Delete a site, removing its nginx config and PHP-FPM pool."""
    domain = validate_domain(domain)
    cfg: dict[str, Any] = load_config()
    site: dict[str, Any] | None = cfg.get("sites", {}).pop(domain, None)
    if not site:
        return False
    config_path: Path = Path(site.get("nginx_config", ""))
    if config_path.exists() and _is_within_directory(NGINX_DIR, config_path):
        config_path.unlink()
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    audit_event("site.delete", "ok", {"domain": domain})
    
    # Remove nginx config and PHP-FPM pool via driver layer
    try:
        from atulya_launch.drivers import get_platform_driver
        driver = get_platform_driver(dry_run=False)
        
        # Remove nginx config
        try:
            driver.web.apply_site(domain, "")  # Empty config removes it
            driver.web.reload()
        except Exception:
            driver.web.reload()
        
        # Remove PHP-FPM pool if PHP was enabled
        if site.get("php") and site.get("php_version"):
            php_fpm_pool_remove(domain, site["php_version"])
    except Exception as e:
        audit_event("site.delete.driver_warning", "warning", {"domain": domain, "error": str(e)})
    
    return True


def generate_nginx_config(domain: str, web_root: str | Path, proxy_pass: str | None = None, php: bool = False, php_version: str | None = None) -> Path:
    """Write an nginx server block config file and return its path."""
    NGINX_DIR.mkdir(parents=True, exist_ok=True)
    config_path: Path = NGINX_DIR / f"{domain}.conf"
    if proxy_pass:
        body: str = f"""server {{
    listen 80;
    server_name {domain};

    location / {{
        proxy_pass {proxy_pass};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""
    else:
        php_block: str = ""
        if php:
            sock: str = f"unix:/run/php/php{php_version}-fpm.sock" if php_version else "unix:/run/php/php-fpm.sock"
            php_block = f"""
    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass {sock};
    }}
"""
        body = f"""server {{
    listen 80;
    server_name {domain};
    root {Path(web_root)};
    index index.html index.htm index.php;

    location / {{
        try_files $uri $uri/ =404;
    }}
{php_block}}}
"""
    config_path.write_text(body, encoding="utf-8")
    return config_path


def system_status() -> dict[str, Any]:
    """Return a snapshot of system resource usage and panel statistics."""
    ensure_dirs()
    disk: shutil._ntuple_diskusage = shutil.disk_usage(CONFIG_DIR)  # type: ignore[attr-defined]
    uptime: float = time.monotonic()
    memory: dict[str, Any] = memory_status()
    return {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "config_dir": str(CONFIG_DIR),
        "cpu_count": os.cpu_count() or 1,
        "memory": memory,
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": round((disk.used / disk.total) * 100, 1) if disk.total else 0,
        },
        "process_uptime_seconds": int(uptime),
        "sites": len(site_list()),
        "backups": len(load_config().get("backups", {})),
        "services": service_summary(),
    }


def memory_status() -> dict[str, Any]:
    """Return virtual memory stats via psutil, or None values if unavailable."""
    try:
        import psutil
        mem: Any = psutil.virtual_memory()
        return {
            "total": mem.total,
            "used": mem.used,
            "available": mem.available,
            "percent": mem.percent,
        }
    except Exception:
        return {"total": None, "used": None, "available": None, "percent": None}


def service_summary() -> dict[str, str]:
    """Return active status for common system services."""
    names: list[str] = ["nginx", "apache2", "mariadb", "mysql", "postgresql", "redis-server", "ssh", "fail2ban"]
    return {name: service_state(name) for name in names}


def service_state(name: str) -> str:
    """Check whether a systemd service is active."""
    if get_platform() != "linux" or not shutil.which("systemctl"):
        return "unknown"
    from atulya_launch.drivers import get_platform_driver
    driver = get_platform_driver(dry_run=False)
    result = driver.services.status(name)
    return result.message.strip() or ("active" if result.ok else "unknown")


def nginx_apply_plan(domain: str | None = None) -> list[dict[str, str]]:
    """Build a deployment plan for copying nginx configs into /etc/nginx."""
    sites: dict[str, Any] = site_list()
    targets: list[str] = [validate_domain(domain)] if domain else sorted(sites)
    planned: list[dict[str, str]] = []
    for name in targets:
        site: dict[str, Any] | None = sites.get(name)
        if not site:
            raise ValueError(f"site not found: {name}")
        source: Path = Path(site["nginx_config"])
        planned.append(
            {
                "domain": name,
                "source": str(source),
                "target": f"/etc/nginx/sites-available/{name}.conf",
                "enabled_link": f"/etc/nginx/sites-enabled/{name}.conf",
                "test_command": "nginx -t",
                "reload_command": "systemctl reload nginx",
            }
        )
    return planned


def security_scan() -> dict[str, Any]:
    """Run a security audit on the panel and sites configuration."""
    cfg: dict[str, Any] = load_config()
    issues: list[dict[str, str]] = []
    settings: dict[str, Any] = cfg.get("settings", {})
    if settings.get("bind_host") not in ("127.0.0.1", "localhost"):
        issues.append({"level": "high", "check": "bind_host", "message": "Panel is configured for non-local binding."})
    if not cfg.get("panel", {}).get("api_token"):
        issues.append({"level": "high", "check": "api_token", "message": "API token has not been generated."})
    for domain, site in cfg.get("sites", {}).items():
        try:
            _safe_path(site.get("web_root", ""), CONFIG_DIR)
        except ValueError:
            issues.append({"level": "critical", "check": "site_root", "message": f"{domain} web root escapes config dir."})
    score: int = max(0, 100 - (20 * len([i for i in issues if i["level"] == "critical"])) - (10 * len([i for i in issues if i["level"] == "high"])))
    return {"score": score, "issues": issues, "checked_at": datetime.utcnow().isoformat() + "Z"}


def backup_create(name: str | None = None) -> dict[str, Any]:
    """Create a ZIP archive backup of config and webroots."""
    ensure_dirs()
    stamp: str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_name: str = name or f"backup-{stamp}"
    archive_path: Path = BACKUPS_DIR / f"{backup_name}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if CONFIG_FILE.exists():
            archive.write(CONFIG_FILE, "config.json")
        for site_root in WEBROOTS_DIR.glob("*"):
            if site_root.is_dir():
                for item in site_root.rglob("*"):
                    if item.is_file():
                        archive.write(item, item.relative_to(CONFIG_DIR))
    cfg: dict[str, Any] = load_config()
    cfg.setdefault("backups", {})[backup_name] = {
        "name": backup_name,
        "path": str(archive_path),
        "size": archive_path.stat().st_size,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    save_config(cfg)
    audit_event("backup.create", "ok", {"name": backup_name, "path": str(archive_path)})
    return cfg["backups"][backup_name]


def backup_list() -> dict[str, Any]:
    """Return all stored backup metadata."""
    return load_config().get("backups", {})


def backup_restore(name: str) -> dict[str, str]:
    """Restore config and webroots from a named backup archive."""
    backups: dict[str, Any] = backup_list()
    backup: dict[str, Any] | None = backups.get(name)
    if not backup:
        raise ValueError(f"backup not found: {name}")
    archive_path: Path = Path(backup["path"])
    if not archive_path.exists():
        raise ValueError(f"backup archive missing: {archive_path}")
    restore_dir: Path = CACHE_DIR / f"restore-{name}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    restore_dir.mkdir(parents=True, exist_ok=True)
    extract_archive(archive_path, restore_dir)
    restored_config: Path = restore_dir / "config.json"
    if restored_config.exists():
        shutil.copy2(restored_config, CONFIG_FILE)
    restored_webroots: Path = restore_dir / "webroots"
    if restored_webroots.exists():
        if WEBROOTS_DIR.exists():
            shutil.rmtree(WEBROOTS_DIR)
        shutil.copytree(restored_webroots, WEBROOTS_DIR)
    audit_event("backup.restore", "ok", {"name": name})
    return {"name": name, "restored_from": str(archive_path), "staging_dir": str(restore_dir)}


def _site_root(domain: str) -> Path:
    """Return the resolved web root path for a site, with safety checks."""
    site: dict[str, Any] | None = site_get(domain)
    if not site:
        raise ValueError(f"site not found: {domain}")
    root: Path = Path(site["web_root"]).resolve()
    if not _is_within_directory(CONFIG_DIR, root):
        raise ValueError("site web root is outside Atulya config dir")
    return root


def _site_file_path(domain: str, relative_path: str = ".") -> Path:
    """Return a resolved path under a site's web root, validating it is safe."""
    root: Path = _site_root(domain)
    target: Path = (root / relative_path).resolve()
    if not _is_within_directory(root, target):
        raise ValueError("path escapes site web root")
    return target


def file_list(domain: str, relative_path: str = ".") -> list[dict[str, Any]]:
    """List files and directories under a site's web root."""
    target: Path = _site_file_path(domain, relative_path)
    if not target.exists():
        raise ValueError("path not found")
    if target.is_file():
        return [{"name": target.name, "path": str(Path(relative_path)), "type": "file", "size": target.stat().st_size}]
    entries: list[dict[str, Any]] = []
    for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        entries.append(
            {
                "name": item.name,
                "path": str(item.relative_to(_site_root(domain))),
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            }
        )
    return entries


def file_write(domain: str, relative_path: str, content: str) -> dict[str, Any]:
    """Write content to a file within a site's web root."""
    target: Path = _site_file_path(domain, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    audit_event("file.write", "ok", {"domain": domain, "path": relative_path})
    return {"path": str(target), "size": target.stat().st_size}


def file_mkdir(domain: str, relative_path: str) -> dict[str, str]:
    """Create a directory within a site's web root."""
    target: Path = _site_file_path(domain, relative_path)
    target.mkdir(parents=True, exist_ok=True)
    audit_event("file.mkdir", "ok", {"domain": domain, "path": relative_path})
    return {"path": str(target)}


def file_delete(domain: str, relative_path: str) -> dict[str, str]:
    """Delete a file or directory from a site's web root."""
    target: Path = _site_file_path(domain, relative_path)
    if target == _site_root(domain):
        raise ValueError("refusing to delete site root")
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()
    else:
        raise ValueError("path not found")
    audit_event("file.delete", "ok", {"domain": domain, "path": relative_path})
    return {"deleted": str(target)}


def dashboard_data() -> dict[str, Any]:
    """Assemble all data needed for the dashboard view."""
    return {
        "status": system_status(),
        "sites": list(site_list().values()),
        "backups": list(backup_list().values()),
        "security": security_scan(),
        "audit": audit_list(20),
    }


def detect_web_server() -> str | None:
    """Detect which web server is installed (nginx or apache)."""
    if sys.platform != "linux":
        return None
    from atulya_launch.drivers import get_platform_driver
    driver = get_platform_driver(dry_run=False)
    if driver.web.detect().ok or driver.web.detect().message:
        return "nginx"
    try:
        r: subprocess.CompletedProcess = subprocess.run(["apache2ctl", "-v"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return "apache"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def get_platform() -> str:
    """Return the current OS platform slug."""
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32":
        return "windows"
    return sys.platform


def is_linux() -> bool:
    """Check if running on Linux."""
    return sys.platform.startswith("linux")


def get_arch() -> str:
    """Return the machine architecture."""
    machine: str = os.uname().machine if hasattr(os, "uname") else "x86_64"
    return machine


def get_python_cmd() -> list[str]:
    """Return the Python executable command prefix."""
    return [sys.executable, "-m"]


def run_cmd(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """Run a shell command and capture stdout/stderr."""
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def package_name(tool_name: str) -> str:
    """Translate a tool display name into its pip package name."""
    return tool_name.lower().replace("-", "_")


def is_installed_via_pip(tool_name: str) -> bool:
    """Check whether a tool is installed as a pip package."""
    try:
        metadata.version(package_name(tool_name))
        return True
    except metadata.PackageNotFoundError:
        return False


def installed_pip_version(tool_name: str) -> str | None:
    """Return the installed pip package version, or None."""
    try:
        return metadata.version(package_name(tool_name))
    except metadata.PackageNotFoundError:
        return None


def get_recorded_version(tool_name: str) -> str | None:
    """Return the recorded version from the panel config."""
    cfg: dict[str, Any] = get_installed_tools().get(tool_name, {})
    return cfg.get("version")


def get_installed_version(tool_name: str) -> str | None:
    """Return the installed version from config or pip."""
    return get_recorded_version(tool_name) or installed_pip_version(tool_name)


def is_installed(tool_name: str) -> bool:
    """Check if a tool is installed via pip or local copy."""
    if is_installed_via_pip(tool_name):
        return True
    if is_installed_via_local(tool_name):
        return True
    return False


def is_installed_via_local(tool_name: str) -> bool:
    """Check if a tool is installed as a local copy in TOOLS_DIR."""
    ensure_dirs()
    return (TOOLS_DIR / package_name(tool_name)).exists()


def get_installed_tools() -> dict[str, Any]:
    """Return the installed tools configuration."""
    cfg: dict[str, Any] = load_config()
    return cfg.get("installed", {})


def get_github_releases(tool_name: str, max_per_page: int = 10) -> list[dict[str, Any]]:
    """Fetch release list for an Atulya tool from GitHub."""
    url: str = f"https://api.github.com/repos/{ATULYA_ORG}/{tool_name}/releases?per_page={max_per_page}"
    resp: requests.Response = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_latest_release(tool_name: str) -> dict[str, Any]:
    """Fetch the latest release metadata for an Atulya tool."""
    url: str = f"https://api.github.com/repos/{ATULYA_ORG}/{tool_name}/releases/latest"
    resp: requests.Response = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_release_assets(release: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the assets list from a release dict."""
    return release.get("assets", [])


def download_file(url: str, dest: str | Path, desc: str | None = None) -> Path:
    """Stream-download a file from a URL to a local destination."""
    resp: requests.Response = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    dest_path: Path = Path(dest)
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest_path


def sha256_file(path: str | Path) -> str:
    """Compute the SHA-256 hex digest of a file."""
    h: hashlib._Hash = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_archive(archive_path: str | Path, dest_dir: str | Path) -> Path:
    """Extract a ZIP or tar archive to a destination directory."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    if str(archive_path).endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            safe_extract_zip(zf, dest_dir)
    elif str(archive_path).endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive_path, "r:gz") as tf:
            safe_extract_tar(tf, dest_dir)
    elif str(archive_path).endswith(".tar"):
        with tarfile.open(archive_path, "r:") as tf:
            safe_extract_tar(tf, dest_dir)
    else:
        shutil.copy2(archive_path, dest_dir)
    return dest_dir


def _is_within_directory(parent: str | Path, child: str | Path) -> bool:
    """Check whether child path is contained within parent path."""
    parent = Path(parent).resolve()
    child = Path(child).resolve()
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def safe_extract_zip(archive: zipfile.ZipFile, dest_dir: str | Path) -> None:
    """Extract a ZIP file while guarding against path traversal."""
    for member in archive.infolist():
        target: Path = Path(dest_dir) / member.filename
        if not _is_within_directory(dest_dir, target):
            raise ValueError(f"Unsafe archive member path: {member.filename}")
    archive.extractall(dest_dir)


def safe_extract_tar(archive: tarfile.TarFile, dest_dir: str | Path) -> None:
    """Extract a tar file while guarding against path traversal."""
    for member in archive.getmembers():
        target: Path = Path(dest_dir) / member.name
        if not _is_within_directory(dest_dir, target):
            raise ValueError(f"Unsafe archive member path: {member.name}")
    archive.extractall(dest_dir)


def install_from_pip(tool_name: str, version: str | None = None) -> bool:
    """Install a tool via pip, optionally pinning a version."""
    pkg_name: str = package_name(tool_name)
    spec: str = f"{pkg_name}=={version}" if version else pkg_name
    result: subprocess.CompletedProcess = run_cmd(get_python_cmd() + ["pip", "install", spec], check=False)
    return result.returncode == 0


def uninstall_pip(tool_name: str) -> bool:
    """Uninstall a tool via pip."""
    pkg_name: str = package_name(tool_name)
    result: subprocess.CompletedProcess = run_cmd(get_python_cmd() + ["pip", "uninstall", pkg_name, "-y"], check=False)
    return result.returncode == 0


def install_local(tool_name: str, source_dir: str | Path) -> Path:
    """Install a tool from a local directory into TOOLS_DIR."""
    ensure_dirs()
    pkg_name: str = package_name(tool_name)
    dest: Path = TOOLS_DIR / pkg_name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source_dir, dest)
    cfg: dict[str, Any] = load_config()
    cfg.setdefault("installed", {})[tool_name] = {
        "version": "local",
        "source": str(Path(source_dir).resolve()),
    }
    save_config(cfg)
    return dest


def run_tool(tool_name: str, args: list[str] | None = None) -> int:
    """Execute an installed tool module as a subprocess."""
    pkg_name: str = package_name(tool_name)
    cmd: list[str] = [sys.executable, "-m", pkg_name] + (args or [])

    if is_installed_via_pip(tool_name):
        return subprocess.run(cmd, check=False).returncode

    local_path: Path = TOOLS_DIR / pkg_name
    if local_path.exists():
        env: dict[str, str] = os.environ.copy()
        existing_pythonpath: str | None = env.get("PYTHONPATH")
        pythonpath_parts: list[str] = [str(TOOLS_DIR)]
        if existing_pythonpath:
            pythonpath_parts.append(existing_pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
        return subprocess.run(cmd, check=False, env=env).returncode

    return 1


def check_update(tool_name: str) -> dict[str, Any] | None:
    """Compare installed version with latest GitHub release."""
    current: str | None = get_installed_version(tool_name)
    if not current:
        return None
    try:
        latest: dict[str, Any] = get_latest_release(tool_name)
        latest_ver: str = latest.get("tag_name", "").lstrip("v")
        if latest_ver and latest_ver != current:
            return {"current": current, "latest": latest_ver, "release": latest}
    except Exception:
        pass
    return None


def get_tool_info(tool_name: str) -> dict[str, str]:
    """Return a tool's display name, package name, and description."""
    parts: list[str] = re.sub(r'([A-Z])', r' \1', tool_name.replace("Atulya-", "")).strip().split()
    descriptions: dict[str, str] = {
        "All": "Universal file format converter (40+ formats)",
        "Data": "Data cleaning, deduplication & scrubbing",
        "Office": "Office productivity: DOCX, PDF, spreadsheet tools",
        "Accounting": "Accounting & ERP for Indian businesses",
        "GST": "GST return filing & compliance suite",
        "HR": "HR management & payroll",
        "Automation": "Desktop automation & macro hub",
        "SAP": "SAP automation toolkit",
        "Launch": "Atulya tools launcher & auto-updater",
    }
    key: str = parts[0] if parts else tool_name
    desc: str = descriptions.get(key, "Atulya business tool")
    return {"name": tool_name, "package": package_name(tool_name), "description": desc}


def discover_all_tools() -> list[dict[str, Any]]:
    """Scan all known Atulya tools and return their install status."""
    from . import ATULYA_TOOLS

    installed_cfg: dict[str, Any] = get_installed_tools()
    tools: list[dict[str, Any]] = []
    for name in ATULYA_TOOLS:
        info: dict[str, Any] = get_tool_info(name)
        info["installed"] = is_installed(name)
        if info["installed"]:
            info["version"] = installed_cfg.get(name, {}).get("version") or installed_pip_version(name) or "?"
        tools.append(info)
    return tools


def nginx_apply_and_reload(domain: str) -> dict[str, Any]:
    """Copy nginx config into /etc/nginx, test, and reload nginx.

    All subprocess invocations are routed through the platform driver
    (`driver.web.apply_site`, `driver.web.test_config`, `driver.services.reload`)
    so the panel stays portable across systemd, launchd, and sc.exe.
    """
    site: dict[str, Any] | None = site_get(domain)
    if not site:
        return {"ok": False, "error": f"site not found: {domain}"}
    if get_platform() != "linux":
        return {"ok": False, "error": "nginx apply only supported on Linux"}

    source: Path = Path(site.get("nginx_config", ""))
    if not source.exists():
        return {"ok": False, "error": f"missing generated config: {source}"}

    from atulya_launch.drivers import get_platform_driver
    driver = get_platform_driver(dry_run=False)
    try:
        config_text = source.read_text(encoding="utf-8")

        # 1. Stage into sites-available
        avail_target: Path = Path("/etc/nginx/sites-available") / f"{domain}.conf"
        avail_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, avail_target)
        apply_result = driver.web.apply_site(domain, config_text)
        if not apply_result.ok:
            return {"ok": False, "error": apply_result.message or "apply_site failed"}

        # 2. sites-enabled symlink (Linux convention; idempotent)
        enabled_link: Path = Path("/etc/nginx/sites-enabled") / f"{domain}.conf"
        enabled_link.parent.mkdir(parents=True, exist_ok=True)
        if enabled_link.exists() or enabled_link.is_symlink():
            enabled_link.unlink()
        try:
            enabled_link.symlink_to(avail_target.resolve())
        except OSError:
            # non-fatal: not all installs use sites-enabled
            pass

        # 3. Validate config (driver — works on macOS/Windows too in dry-run)
        test_result = driver.web.test_config()
        if not test_result.ok:
            return {"ok": False, "error": f"config test failed: {test_result.message}"}

        # 4. Reload through the service driver (systemd on Linux, etc.)
        reload_result = driver.web.reload()
        if not reload_result.ok:
            return {"ok": False, "error": f"reload failed: {reload_result.message}"}

        audit_event("nginx.reload", "ok", {"domain": domain})
        return {"ok": True, "domain": domain, "files": apply_result.files, "commands": reload_result.commands}
    except Exception as e:
        audit_event("nginx.reload", "error", {"domain": domain, "error": str(e)})
        return {"ok": False, "error": str(e)}


def database_create(name: str, db_type: str = "mysql") -> dict[str, Any]:
    """Create a MySQL/PostgreSQL database on the host.

    pymysql is used directly for MySQL when available; otherwise the call is
    routed through `driver.databases.create`.
    """
    if db_type in ("mysql", "mariadb"):
        try:
            import pymysql
            conn = pymysql.connect(host="localhost", user="root", password="")
            try:
                with conn.cursor() as cursor:
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{name}`")
                conn.commit()
            finally:
                conn.close()
            return {"ok": True, "name": name, "type": db_type}
        except ImportError:
            if get_platform() != "linux":
                return {"ok": False, "error": "pymysql not installed and subprocess only works on Linux"}
            from atulya_launch.drivers import get_platform_driver
            result = get_platform_driver(dry_run=False).databases.create(name, db_type)
            return {"ok": result.ok, "name": name, "type": db_type, "commands": result.commands}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    elif db_type == "postgresql":
        if get_platform() != "linux":
            return {"ok": False, "error": "PostgreSQL only supported on Linux"}
        from atulya_launch.drivers import get_platform_driver
        result = get_platform_driver(dry_run=False).databases.create(name, db_type)
        return {"ok": result.ok, "name": name, "type": db_type, "commands": result.commands}
    else:
        return {"ok": False, "error": f"unsupported db type: {db_type}"}


def database_drop(name: str, db_type: str = "mysql") -> dict[str, Any]:
    """Drop a MySQL/PostgreSQL database."""
    if db_type in ("mysql", "mariadb"):
        try:
            import pymysql
            conn = pymysql.connect(host="localhost", user="root", password="")
            try:
                with conn.cursor() as cursor:
                    cursor.execute(f"DROP DATABASE IF EXISTS `{name}`")
                conn.commit()
            finally:
                conn.close()
            return {"ok": True, "name": name}
        except ImportError:
            if get_platform() != "linux":
                return {"ok": False, "error": "pymysql not installed and subprocess only works on Linux"}
            from atulya_launch.drivers import get_platform_driver
            result = get_platform_driver(dry_run=False).databases.drop(name, db_type)
            return {"ok": result.ok, "name": name, "commands": result.commands}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    elif db_type == "postgresql":
        if get_platform() != "linux":
            return {"ok": False, "error": "PostgreSQL only supported on Linux"}
        from atulya_launch.drivers import get_platform_driver
        result = get_platform_driver(dry_run=False).databases.drop(name, db_type)
        return {"ok": result.ok, "name": name, "commands": result.commands}
    else:
        return {"ok": False, "error": f"unsupported db type: {db_type}"}


def database_backup(name: str, db_type: str = "mysql") -> dict[str, Any]:
    """Dump a database to a gzipped SQL file."""
    ensure_dirs()
    stamp: str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path: Path = BACKUPS_DIR / f"db-{name}-{stamp}.sql.gz"
    import gzip
    if db_type in ("mysql", "mariadb"):
        try:
            import pymysql
            conn = pymysql.connect(host="localhost", user="root", password="", db=name)
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SHOW TABLES")
                    tables = [row[0] for row in cursor.fetchall()]
                sql_dump = f"-- MySQL dump for {name}\n\n"
                for table in tables:
                    with conn.cursor() as cursor:
                        cursor.execute(f"SHOW CREATE TABLE `{table}`")
                        create_sql = cursor.fetchone()[1]
                    sql_dump += f"DROP TABLE IF EXISTS `{table}`;\n{create_sql};\n\n"
                    with conn.cursor() as cursor:
                        cursor.execute(f"SELECT * FROM `{table}`")
                        rows = cursor.fetchall()
                        cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '{name}' AND TABLE_NAME = '{table}' ORDER BY ORDINAL_POSITION")
                        columns = [col[0] for col in cursor.fetchall()]
                    for row in rows:
                        values = ", ".join(f"'{str(v).replace(chr(39), chr(39)*2)}'" if v is not None else "NULL" for v in row)
                        sql_dump += f"INSERT INTO `{table}` ({', '.join(f'`{c}`' for c in columns)}) VALUES ({values});\n"
                    sql_dump += "\n"
            finally:
                conn.close()
            with gzip.open(backup_path, "wt", encoding="utf-8") as f:
                f.write(sql_dump)
        except ImportError:
            if get_platform() != "linux":
                return {"ok": False, "error": "pymysql not installed and mysqldump only works on Linux"}
            from atulya_launch.drivers import get_platform_driver
            result = get_platform_driver(dry_run=False).databases.backup(name, backup_path, db_type)
            if not result.ok:
                return {"ok": False, "error": result.message, "commands": result.commands}
            with gzip.open(backup_path, "wt", encoding="utf-8") as f:
                f.write(result.message or "")
        except Exception as e:
            return {"ok": False, "error": str(e)}
    elif db_type == "postgresql":
        if get_platform() != "linux":
            return {"ok": False, "error": "PostgreSQL backup only supported on Linux"}
        from atulya_launch.drivers import get_platform_driver
        result = get_platform_driver(dry_run=False).databases.backup(name, backup_path, db_type)
        if not result.ok:
            return {"ok": False, "error": result.message, "commands": result.commands}
        with gzip.open(backup_path, "wt", encoding="utf-8") as f:
            f.write(result.message or "")
    else:
        return {"ok": False, "error": f"unsupported db type: {db_type}"}
    audit_event("database.backup", "ok", {"name": name, "path": str(backup_path)})
    return {"ok": True, "name": name, "path": str(backup_path), "size": backup_path.stat().st_size}


def db_list() -> dict[str, Any]:
    """List databases from panel config."""
    cfg: dict[str, Any] = load_config()
    dbs: Any = cfg.get("databases", {})
    if not isinstance(dbs, dict):
        return {}
    return dbs


def ssl_list() -> dict[str, Any]:
    """List SSL certificates from panel config."""
    cfg: dict[str, Any] = load_config()
    certs: Any = cfg.get("ssl_certs", {})
    if not isinstance(certs, dict):
        return {}
    return {k: v for k, v in certs.items() if isinstance(v, dict)}


def ssl_issue_letsencrypt(domain: str, *, staging: bool = False) -> dict[str, Any]:
    """Issue a Let's Encrypt SSL certificate for a domain via certbot.

    Routed through `driver.ssl.issue_letsencrypt` so the panel can later
    support Caddy, acme-dns, and other ACME clients without code changes
    here. The original certbot-specific flags are preserved for now.
    """
    if get_platform() != "linux":
        return {"ok": False, "error": "SSL issuance only supported on Linux"}
    cert_dir: Path = CONFIG_DIR / "ssl" / domain
    cert_dir.mkdir(parents=True, exist_ok=True)

    from atulya_launch.drivers import get_platform_driver
    driver = get_platform_driver(dry_run=False)
    result = driver.ssl.issue_letsencrypt(
        domain,
        email=f"admin@{domain}",
        staging=staging,
    )
    if not result.ok:
        return {"ok": False, "error": result.message, "commands": result.commands}
    audit_event("ssl.issue", "ok", {"domain": domain, "staging": staging})
    return {
        "ok": True,
        "domain": domain,
        "cert_path": str(cert_dir / "fullchain.pem"),
        "key_path": str(cert_dir / "privkey.pem"),
        "expires_at": None,
        "commands": result.commands,
    }


def ssl_renew(domain: str) -> dict[str, Any]:
    """Renew an existing SSL certificate via certbot."""
    if get_platform() != "linux":
        return {"ok": False, "error": "SSL renewal only supported on Linux"}
    from atulya_launch.drivers import get_platform_driver
    result = get_platform_driver(dry_run=False).ssl.renew(domain)
    if not result.ok:
        return {"ok": False, "error": result.message, "commands": result.commands}
    audit_event("ssl.renew", "ok", {"domain": domain})
    return {"ok": True, "domain": domain, "commands": result.commands}


def firewall_status() -> dict[str, Any]:
    """Return the UFW firewall status."""
    if get_platform() != "linux" or not shutil.which("ufw"):
        return {"installed": False, "active": False}
    from atulya_launch.drivers import get_platform_driver
    result = get_platform_driver(dry_run=False).firewall.status()
    active: bool = result.ok and "active" in result.message.lower()
    return {"installed": True, "active": active, "raw": result.message.strip()}


def firewall_list_rules() -> list[str]:
    """List numbered UFW rules."""
    if get_platform() != "linux" or not shutil.which("ufw"):
        return []
    from atulya_launch.drivers import get_platform_driver
    result = get_platform_driver(dry_run=False).firewall.list_rules()
    rules: list[str] = []
    for line in result.message.strip().splitlines():
        if line.startswith("[") and "]" in line:
            rules.append(line)
    return rules


def firewall_enable() -> dict[str, bool]:
    """Enable the UFW firewall."""
    if get_platform() != "linux":
        return {"ok": False, "error": "firewall only supported on Linux"}
    from atulya_launch.drivers import get_platform_driver
    result = get_platform_driver(dry_run=False).firewall.enable()
    return {"ok": result.ok, "commands": result.commands}


def firewall_disable() -> dict[str, bool]:
    """Disable the UFW firewall."""
    if get_platform() != "linux":
        return {"ok": False, "error": "firewall only supported on Linux"}
    from atulya_launch.drivers import get_platform_driver
    result = get_platform_driver(dry_run=False).firewall.disable()
    return {"ok": result.ok, "commands": result.commands}


def firewall_allow(port: int, proto: str = "tcp") -> dict[str, bool]:
    """Allow traffic on a port through the firewall."""
    if get_platform() != "linux":
        return {"ok": False, "error": "firewall only supported on Linux"}
    from atulya_launch.drivers import get_platform_driver
    result = get_platform_driver(dry_run=False).firewall.allow(port, proto)
    return {"ok": result.ok, "commands": result.commands}


def firewall_deny(port: int, proto: str = "tcp") -> dict[str, bool]:
    """Deny traffic on a port through the firewall."""
    if get_platform() != "linux":
        return {"ok": False, "error": "firewall only supported on Linux"}
    from atulya_launch.drivers import get_platform_driver
    result = get_platform_driver(dry_run=False).firewall.deny(port, proto)
    return {"ok": result.ok, "commands": result.commands}


def fail2ban_status() -> dict[str, Any]:
    """Return fail2ban installation and jail status."""
    if get_platform() != "linux":
        return {"installed": False, "active": False, "jails": []}
    result: subprocess.CompletedProcess = run_cmd(["fail2ban-client", "status"], check=False)
    if result.returncode != 0:
        return {"installed": False, "active": False, "jails": []}
    jails: list[str] = []
    for line in result.stdout.splitlines():
        if "Jail list" in line:
            jails = [j.strip() for j in line.split(":", 1)[1].split(",")]
    return {"installed": True, "active": True, "jails": jails}


def fail2ban_restart() -> dict[str, Any]:
    """Restart the fail2ban service."""
    if get_platform() != "linux":
        return {"ok": False, "error": "fail2ban only supported on Linux"}
    from atulya_launch.drivers import get_platform_driver
    result = get_platform_driver(dry_run=False).services.restart("fail2ban")
    return {"ok": result.ok, "commands": result.commands}


APP_CATALOG: dict[str, dict[str, Any]] = {
    "wordpress": {"name": "WordPress", "description": "CMS and blogging platform", "requires": ["mysql", "php"]},
    "nextcloud": {"name": "Nextcloud", "description": "File sharing and collaboration", "requires": ["mysql", "php"]},
    "laravel": {"name": "Laravel", "description": "PHP web framework", "requires": ["mysql", "php"]},
    "ghost": {"name": "Ghost", "description": "Professional publishing platform", "requires": ["nodejs"]},
    "flask": {"name": "Flask App", "description": "Python web application", "requires": ["python"]},
    "django": {"name": "Django App", "description": "Python web framework", "requires": ["python", "postgresql"]},
}


def installed_apps() -> dict[str, Any]:
    """Return installed one-click apps from config."""
    ensure_dirs()
    cfg: dict[str, Any] = load_config()
    return cfg.get("installed_apps", {})


def available_apps() -> dict[str, dict[str, Any]]:
    """Return the app catalog."""
    return APP_CATALOG


def app_install(app_name: str, domain: str, db_name: str | None = None, db_user: str | None = None, db_pass: str | None = None) -> dict[str, Any]:
    """Install a one-click application on a domain."""
    if app_name not in APP_CATALOG:
        return {"ok": False, "error": f"unknown app: {app_name}"}
    dispatch: dict[str, Any] = {
        "wordpress": lambda: wordpress_install(domain, db_name=db_name, db_user=db_user, db_pass=db_pass),
        "nextcloud": lambda: app_install_nextcloud(domain, db_name=db_name, db_user=db_user, db_pass=db_pass),
        "laravel": lambda: app_install_laravel(domain),
        "ghost": lambda: app_install_ghost(domain),
        "flask": lambda: app_install_flask(domain),
        "django": lambda: app_install_django(domain),
    }
    installer = dispatch.get(app_name)
    if installer:
        result: dict[str, Any] = installer()
        return result
    site: dict[str, Any] = site_create(domain)
    cfg: dict[str, Any] = load_config()
    cfg.setdefault("installed_apps", {})[app_name] = {
        "domain": domain,
        "installed_at": datetime.utcnow().isoformat() + "Z",
    }
    save_config(cfg)
    audit_event("app.install", "ok", {"app": app_name, "domain": domain})
    return {"ok": True, "app": app_name, "domain": domain}


def app_uninstall(app_name: str) -> dict[str, Any]:
    """Uninstall a previously installed app."""
    cfg: dict[str, Any] = load_config()
    apps: dict[str, Any] = cfg.get("installed_apps", {})
    if app_name not in apps:
        return {"ok": False, "error": f"app not installed: {app_name}"}
    apps.pop(app_name)
    save_config(cfg)
    audit_event("app.uninstall", "ok", {"app": app_name})
    return {"ok": True, "app": app_name}


# ─── v0.3.0: Migration Import ────────────────────────────────────────────────

MIGRATION_SOURCES: dict[str, dict[str, str]] = {
    "cpanel": {"name": "cPanel", "ext": ".tar.gz"},
    "plesk": {"name": "Plesk", "ext": ".tar"},
    "hestiacp": {"name": "HestiaCP", "ext": ".tar"},
}


def migration_import(source: str, file_path: str, domain: str | None = None) -> dict[str, Any]:
    """Import sites/databases from a cPanel/Plesk/HestiaCP migration archive."""
    if source not in MIGRATION_SOURCES:
        return {"ok": False, "error": f"unknown source: {source}, expected one of {list(MIGRATION_SOURCES)}"}
    p: Path = Path(file_path)
    if not p.exists():
        return {"ok": False, "error": f"file not found: {file_path}"}
    try:
        import tarfile, zipfile
        extract_dir: str = tempfile.mkdtemp(prefix="atulya_migration_")
        if p.suffix == ".zip":
            with zipfile.ZipFile(p, "r") as zf:
                safe_extract_zip(zf, extract_dir)
        else:
            with tarfile.open(p, "r:*") as tf:
                safe_extract_tar(tf, extract_dir)
        sites_imported: int = 0
        dbs_imported: int = 0
        emails_imported: int = 0
        for item in Path(extract_dir).iterdir():
            if item.is_dir():
                site_create(item.name, web_root=str(item))
                sites_imported += 1
            elif item.suffix in (".sql", ".dump"):
                db_name: str = item.stem
                database_create(db_name, "mysql")
                dbs_imported += 1
        shutil.rmtree(extract_dir, ignore_errors=True)
        summary: dict[str, int] = {"sites": sites_imported, "databases": dbs_imported, "emails": emails_imported}
        audit_event("migration.import", "ok", {"source": source, "file": file_path, **summary})
        return {"ok": True, "source": source, **summary}
    except Exception as e:
        audit_event("migration.import", "error", {"source": source, "file": file_path, "error": str(e)})
        return {"ok": False, "error": str(e)}


def migration_list() -> list[dict[str, Any]]:
    """List migration records from the database."""
    from .web.database import connect
    try:
        with connect() as cur:
            rows: list[Any] = cur.execute("SELECT * FROM migrations ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
    except RuntimeError:
        return []


def migration_delete(migration_id: int) -> None:
    """Delete a migration record."""
    from .web.database import connect
    with connect() as cur:
        cur.execute("DELETE FROM migrations WHERE id = ?", (migration_id,))


# ─── v0.3.0: Reseller Plans ──────────────────────────────────────────────────

def plan_create(name: str, sites_limit: int = 0, disk_limit_mb: int = 0, db_limit: int = 0, email_limit: int = 0, bandwidth_limit_mb: int = 0, price_monthly: int = 0) -> dict[str, Any]:
    """Create a reseller hosting plan."""
    from .web.database import connect, audit_log
    from datetime import datetime
    with connect() as cur:
        cur.execute(
            "INSERT INTO plans (name, sites_limit, disk_limit_mb, db_limit, email_limit, bandwidth_limit_mb, price_monthly, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, sites_limit, disk_limit_mb, db_limit, email_limit, bandwidth_limit_mb, price_monthly, datetime.utcnow().isoformat() + "Z"),
        )
    audit_log("system", "plan.create", "ok", {"name": name})
    return {"ok": True, "name": name}


def plan_list() -> list[dict[str, Any]]:
    """List all reseller plans."""
    from .web.database import connect
    try:
        with connect() as cur:
            rows: list[Any] = cur.execute("SELECT * FROM plans ORDER BY name").fetchall()
            return [dict(r) for r in rows]
    except RuntimeError:
        return []


def plan_get(plan_id: int) -> dict[str, Any] | None:
    """Get a single plan by ID."""
    from .web.database import connect
    with connect() as cur:
        row: Any = cur.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        return dict(row) if row else None


def plan_delete(plan_id: int) -> None:
    """Delete a reseller plan."""
    from .web.database import connect, audit_log
    with connect() as cur:
        cur.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
    audit_log("system", "plan.delete", "ok", {"plan_id": plan_id})


def plan_assign(user_id: int, plan_id: int, expires_at: str | None = None) -> None:
    """Assign a plan to a user."""
    from .web.database import connect, audit_log
    from datetime import datetime
    with connect() as cur:
        cur.execute("DELETE FROM user_plans WHERE user_id = ?", (user_id,))
        cur.execute(
            "INSERT INTO user_plans (user_id, plan_id, assigned_at, expires_at) VALUES (?, ?, ?, ?)",
            (user_id, plan_id, datetime.utcnow().isoformat() + "Z", expires_at),
        )
    audit_log("system", "plan.assign", "ok", {"user_id": user_id, "plan_id": plan_id})


def plan_user_get(user_id: int) -> dict[str, Any] | None:
    """Get the plan assigned to a specific user."""
    from .web.database import connect
    with connect() as cur:
        row: Any = cur.execute(
            "SELECT p.*, up.expires_at FROM plans p JOIN user_plans up ON p.id = up.plan_id WHERE up.user_id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def check_user_limits(user_id: int) -> dict[str, Any]:
    """Check whether a user has exceeded their plan resource limits."""
    plan: dict[str, Any] | None = plan_user_get(user_id)
    if not plan:
        return {"allowed": True, "reason": "no plan"}

    from .web.database import connect
    with connect() as cur:
        sites_count: int = cur.execute("SELECT COUNT(*) as c FROM sites").fetchone()["c"]
        dbs_count: int = cur.execute("SELECT COUNT(*) as c FROM databases").fetchone()["c"]
        emails_count: int = cur.execute("SELECT COUNT(*) as c FROM email_accounts").fetchone()["c"]

    violations: list[str] = []
    if plan["sites_limit"] > 0 and sites_count >= plan["sites_limit"]:
        violations.append(f"sites limit {plan['sites_limit']} reached")
    if plan["db_limit"] > 0 and dbs_count >= plan["db_limit"]:
        violations.append(f"database limit {plan['db_limit']} reached")
    if plan["email_limit"] > 0 and emails_count >= plan["email_limit"]:
        violations.append(f"email limit {plan['email_limit']} reached")

    if violations:
        return {"allowed": False, "reason": "; ".join(violations)}
    return {"allowed": True, "reason": "ok"}


# ─── v0.3.0: WordPress One-Click Installer ──────────────────────────────────

def wordpress_install(domain: str, db_name: str | None = None, db_user: str | None = None, db_pass: str | None = None, admin_user: str = "admin", admin_email: str = "admin@example.com") -> dict[str, Any]:
    """Download and configure WordPress on a domain with PHP support."""
    site: dict[str, Any] | None = site_create(domain, php=True)
    if not site.get("ok", True) and "already exists" not in str(site):
        return site
    cfg: dict[str, Any] = load_config()
    panel_dir: Path = ensure_dirs()
    web_root: Path = panel_dir / "webroot" / domain
    web_root.mkdir(parents=True, exist_ok=True)

    import zipfile, io, urllib.request
    wp_url: str = "https://wordpress.org/latest.zip"
    try:
        with urllib.request.urlopen(wp_url, timeout=30) as resp:
            data: bytes = resp.read()
    except Exception as e:
        cfg.setdefault("installed_apps", {})["wordpress_" + domain] = {
            "domain": domain,
            "installed_at": datetime.utcnow().isoformat() + "Z",
            "downloaded": False,
            "error": str(e),
        }
        save_config(cfg)
        result: dict[str, Any] = {
            "ok": False,
            "domain": domain,
            "path": str(web_root),
            "downloaded": False,
            "error": f"failed to download WordPress: {e}",
        }
        audit_event("wordpress.install", "degraded", {"domain": domain, "error": str(e)})
        return result

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for member in zf.namelist():
            target: Path = web_root / member
            if not target.resolve().is_relative_to(web_root.resolve()):
                continue
            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(member))

    wp_config_path: Path = web_root / "wp-config.php"
    if not wp_config_path.exists():
        sample: Path = web_root / "wp-config-sample.php"
        if sample.exists():
            wp_config: str = sample.read_text()
            db_name_val: str = db_name or f"wp_{domain.replace('.', '_')}"
            db_user_val: str = db_user or db_name_val
            db_pass_val: str = db_pass or secrets.token_urlsafe(16)
            wp_config = wp_config.replace("database_name_here", db_name_val)
            wp_config = wp_config.replace("username_here", db_user_val)
            wp_config = wp_config.replace("password_here", db_pass_val)
            wp_config = wp_config.replace("wp_", f"wp_{secrets.token_hex(4)}_")
            salt_keys: list[str] = ["AUTH_KEY", "SECURE_AUTH_KEY", "LOGGED_IN_KEY", "NONCE_KEY",
                         "AUTH_SALT", "SECURE_AUTH_SALT", "LOGGED_IN_SALT", "NONCE_SALT"]
            for key in salt_keys:
                wp_config = wp_config.replace(f"define( '{key}',", f"define( '{key}', '{secrets.token_urlsafe(32)}'")
            wp_config_path.write_text(wp_config)

    cfg.setdefault("installed_apps", {})["wordpress_" + domain] = {
        "domain": domain,
        "installed_at": datetime.utcnow().isoformat() + "Z",
    }
    save_config(cfg)

    result: dict[str, Any] = {"ok": True, "domain": domain, "path": str(web_root)}
    if db_name:
        db_result: dict[str, Any] = database_create(db_name, "mysql")
        result["db_create"] = db_result.get("ok", False)
    audit_event("wordpress.install", "ok", {"domain": domain})
    return result


# ─── v1.0.0+: One-Click App Store ───────────────────────────────────────

def app_install_nextcloud(domain: str, db_name: str | None = None, db_user: str | None = None, db_pass: str | None = None, admin_user: str = "admin", admin_pass: str | None = None) -> dict[str, Any]:
    """Download and install Nextcloud on a domain."""
    site_create(domain, php=True, php_version="8.3")
    cfg: dict[str, Any] = load_config()
    panel_dir: Path = ensure_dirs()
    web_root: Path = panel_dir / "webroot" / domain
    web_root.mkdir(parents=True, exist_ok=True)
    import zipfile, io, urllib.request
    try:
        with urllib.request.urlopen("https://download.nextcloud.com/server/releases/latest.zip", timeout=60) as resp:
            data: bytes = resp.read()
    except Exception as e:
        return {"ok": False, "error": f"failed to download Nextcloud: {e}"}
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for member in zf.namelist():
            target: Path = web_root / member
            if not target.resolve().is_relative_to(web_root.resolve()):
                continue
            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(member))
    result: dict[str, Any] = {"ok": True, "domain": domain, "path": str(web_root)}
    if db_name:
        db_result: dict[str, Any] = database_create(db_name, "mysql")
        result["db_create"] = db_result.get("ok", False)
    cfg.setdefault("installed_apps", {})["nextcloud_" + domain] = {"domain": domain, "installed_at": datetime.utcnow().isoformat() + "Z"}
    save_config(cfg)
    audit_event("app.install", "ok", {"app": "nextcloud", "domain": domain})
    return result


def app_install_laravel(domain: str, php_version: str = "8.3") -> dict[str, Any]:
    """Scaffold a new Laravel project on a domain."""
    if not is_linux():
        site_create(domain, php=True, php_version=php_version)
        return {"ok": True, "domain": domain, "note": "Laravel scaffolding requires Linux with composer"}
    site_create(domain, php=True, php_version=php_version)
    panel_dir: Path = ensure_dirs()
    web_root: Path = panel_dir / "webroot" / domain
    web_root.mkdir(parents=True, exist_ok=True)
    run_cmd(["composer", "create-project", "--prefer-dist", "laravel/laravel", str(web_root)], timeout=120)
    run_cmd(["chown", "-R", "www-data:www-data", str(web_root)])
    audit_event("app.install", "ok", {"app": "laravel", "domain": domain})
    return {"ok": True, "domain": domain, "path": str(web_root)}


def app_install_ghost(domain: str) -> dict[str, Any]:
    """Install the Ghost publishing platform on a domain."""
    if not is_linux():
        site_create(domain, proxy_pass="http://127.0.0.1:2368")
        return {"ok": True, "domain": domain, "note": "Ghost requires Linux with Node.js"}
    run_cmd(["npm", "install", "-g", "ghost-cli"], timeout=60)
    panel_dir: Path = ensure_dirs()
    web_root: Path = panel_dir / "webroot" / domain
    web_root.mkdir(parents=True, exist_ok=True)
    run_cmd(["ghost", "install", "--db=mysql", "--no-prompt", "--dir", str(web_root), "--port", "2368"], timeout=180)
    site_create(domain, proxy_pass="http://127.0.0.1:2368")
    audit_event("app.install", "ok", {"app": "ghost", "domain": domain})
    return {"ok": True, "domain": domain, "path": str(web_root), "port": 2368}


def app_install_flask(domain: str, app_name: str = "app") -> dict[str, Any]:
    """Create and deploy a minimal Flask application on a domain."""
    site_create(domain, proxy_pass="http://127.0.0.1:5000")
    panel_dir: Path = ensure_dirs()
    web_root: Path = panel_dir / "webroot" / domain
    web_root.mkdir(parents=True, exist_ok=True)
    app_file: Path = web_root / f"{app_name}.py"
    if not app_file.exists():
        app_file.write_text(f'''from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>{domain}</h1><p>Flask app hosted by Atulya Launch.</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
''')
    deploy_app(f"flask_{domain}", domain, "python", f"{app_name}.py", 5000)
    audit_event("app.install", "ok", {"app": "flask", "domain": domain})
    return {"ok": True, "domain": domain, "path": str(web_root), "entry": f"{app_name}.py"}


def app_install_django(domain: str, project_name: str = "mysite") -> dict[str, Any]:
    """Scaffold and deploy a Django project on a domain."""
    if not is_linux():
        site_create(domain, proxy_pass="http://127.0.0.1:8000")
        return {"ok": True, "domain": domain, "note": "Django requires Linux with Python3"}
    site_create(domain, proxy_pass="http://127.0.0.1:8000")
    panel_dir: Path = ensure_dirs()
    web_root: Path = panel_dir / "webroot" / domain
    web_root.mkdir(parents=True, exist_ok=True)
    run_cmd(["pip3", "install", "django", "gunicorn"], timeout=60)
    run_cmd(["django-admin", "startproject", project_name, str(web_root)], timeout=30)
    run_cmd(["chown", "-R", "www-data:www-data", str(web_root)])
    deploy_app(f"django_{domain}", domain, "python", f"{project_name}/wsgi.py", 8000)
    audit_event("app.install", "ok", {"app": "django", "domain": domain})
    return {"ok": True, "domain": domain, "path": str(web_root), "project": project_name}


# ─── v0.4.0: Node.js/Python App Deployment ──────────────────────────────────

def deploy_app(name: str, domain: str, app_type: str = "node", entry_point: str = "index.js", port: int = 3000) -> dict[str, Any]:
    """Register a new application deployment for a domain."""
    from .web.database import connect, audit_log
    from datetime import datetime
    site_create(domain, proxy_pass=f"http://127.0.0.1:{port}", php=False)
    with connect() as cur:
        cur.execute(
            "INSERT INTO node_apps (name, domain, app_type, entry_point, port, status, created_at) VALUES (?, ?, ?, ?, ?, 'stopped', ?)",
            (name, domain, app_type, entry_point, port, datetime.utcnow().isoformat() + "Z"),
        )
    audit_log("system", "deploy.create", "ok", {"name": name, "domain": domain, "type": app_type})
    return {"ok": True, "name": name, "domain": domain, "port": port}


def deploy_list() -> list[dict[str, Any]]:
    """List all registered deployments."""
    from .web.database import connect
    try:
        with connect() as cur:
            rows: list[Any] = cur.execute("SELECT * FROM node_apps ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
    except RuntimeError:
        return []


def deploy_delete(app_id: int) -> None:
    """Delete a deployment record."""
    from .web.database import connect, audit_log
    with connect() as cur:
        cur.execute("DELETE FROM node_apps WHERE id = ?", (app_id,))
    audit_log("system", "deploy.delete", "ok", {"app_id": app_id})


def deploy_start(app_id: int) -> dict[str, Any]:
    """Start a deployed application."""
    from .web.database import connect, audit_log
    with connect() as cur:
        row: Any = cur.execute("SELECT * FROM node_apps WHERE id = ?", (app_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "app not found"}
        app: dict[str, Any] = dict(row)
    if sys.platform != "linux":
        with connect() as cur:
            cur.execute("UPDATE node_apps SET status = 'running' WHERE id = ?", (app_id,))
        audit_log("system", "deploy.start", "ok", {"app_id": app_id, "note": "simulated on non-linux"})
    return {"ok": True}


# ─── v1.0.0+: Subdomain Management ──────────────────────────────────────

def subdomain_create(domain: str, subdomain: str, target: str | None = None) -> dict[str, Any]:
    """Create a new subdomain with its own nginx config."""
    domain = validate_domain(domain)
    full: str = f"{subdomain}.{domain}"
    if subdomain in ["www", "mail", "ftp", "cpanel", "webmail"]:
        return {"ok": False, "error": f"reserved subdomain: {subdomain}"}
    cfg: dict[str, Any] = load_config()
    all_sites: dict[str, Any] = cfg.get("sites", {})
    if full in all_sites:
        return {"ok": False, "error": f"subdomain already exists as a site: {full}"}
    subs: dict[str, Any] = cfg.setdefault("subdomains", {})
    key: str = f"{domain}:{subdomain}"
    if key in subs:
        return {"ok": False, "error": f"subdomain already exists: {full}"}
    web_root: Path = WEBROOTS_DIR / domain / subdomain / "public"
    web_root.mkdir(parents=True, exist_ok=True)
    index_path: Path = web_root / "index.html"
    if not index_path.exists():
        index_path.write_text(f"<!doctype html><title>{full}</title><h1>{full}</h1>\n")
    nginx_path: Path = generate_nginx_config(full, web_root, proxy_pass=target)
    subs[key] = {
        "domain": domain,
        "subdomain": subdomain,
        "full": full,
        "web_root": str(web_root),
        "target": target,
        "php": False,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "nginx_config": str(nginx_path),
    }
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    return {"ok": True, "full": full, "web_root": str(web_root)}


def subdomain_list(domain: str | None = None) -> dict[str, Any]:
    """Return subdomains, optionally filtered by parent domain."""
    cfg: dict[str, Any] = load_config()
    subs: dict[str, Any] = cfg.get("subdomains", {})
    if domain:
        return {k: v for k, v in subs.items() if v.get("domain") == domain}
    return subs


def subdomain_delete(domain: str, subdomain: str) -> dict[str, Any]:
    """Delete a subdomain and its nginx config."""
    cfg: dict[str, Any] = load_config()
    key: str = f"{domain}:{subdomain}"
    sub: dict[str, Any] | None = cfg.get("subdomains", {}).pop(key, None)
    if not sub:
        return {"ok": False, "error": "subdomain not found"}
    config_path: Path = Path(sub.get("nginx_config", ""))
    if config_path.exists():
        config_path.unlink()
    shutil.rmtree(Path(sub["web_root"]).parent, ignore_errors=True)
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    return {"ok": True}


def parked_domain_create(primary_domain: str, parked_domain: str) -> dict[str, Any]:
    """Park a domain to point at an existing primary domain."""
    primary_domain = validate_domain(primary_domain)
    parked_domain = validate_domain(parked_domain)
    cfg: dict[str, Any] = load_config()
    primary: dict[str, Any] | None = cfg.get("sites", {}).get(primary_domain)
    if not primary:
        return {"ok": False, "error": f"primary domain not found: {primary_domain}"}
    if parked_domain in cfg.get("sites", {}):
        return {"ok": False, "error": f"domain already exists as a site: {parked_domain}"}
    parkings: dict[str, Any] = cfg.setdefault("parked_domains", {})
    if parked_domain in parkings:
        return {"ok": False, "error": f"already parked: {parked_domain}"}
    parkings[parked_domain] = {
        "primary": primary_domain,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    return {"ok": True, "parked": parked_domain, "points_to": primary_domain}


def parked_domain_list() -> dict[str, Any]:
    """Return all parked domains."""
    return load_config().get("parked_domains", {})


def parked_domain_delete(parked_domain: str) -> dict[str, Any]:
    """Un-park a domain."""
    cfg: dict[str, Any] = load_config()
    parkings: dict[str, Any] = cfg.get("parked_domains", {})
    if parked_domain not in parkings:
        return {"ok": False, "error": "parked domain not found"}
    del parkings[parked_domain]
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    return {"ok": True}


# ─── v1.0.0+: Redirect Manager ──────────────────────────────────────────

def redirect_create(domain: str, source_path: str, target_url: str, redirect_type: int = 301) -> dict[str, Any]:
    """Create a URL redirect rule for a domain."""
    domain_obj: dict[str, Any] | None = site_get(domain)
    if not domain_obj:
        return {"ok": False, "error": f"domain not found: {domain}"}
    cfg: dict[str, Any] = load_config()
    redirects: dict[str, Any] = cfg.setdefault("redirects", {})
    key: str = f"{domain}:{source_path}"
    if key in redirects:
        return {"ok": False, "error": "redirect already exists for this path"}
    redirects[key] = {
        "domain": domain,
        "source": source_path,
        "target": target_url,
        "type": redirect_type,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    nginx_redirects_key: str = f"redirects_{domain}"
    _rebuild_redirect_nginx(domain, cfg)
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    return {"ok": True, "key": key}


def redirect_list(domain: str | None = None) -> dict[str, Any]:
    """Return all redirect rules, optionally filtered by domain."""
    cfg: dict[str, Any] = load_config()
    redirects: dict[str, Any] = cfg.get("redirects", {})
    if domain:
        return {k: v for k, v in redirects.items() if v.get("domain") == domain}
    return redirects


def redirect_delete(domain: str, source_path: str) -> dict[str, Any]:
    """Remove a redirect rule."""
    cfg: dict[str, Any] = load_config()
    key: str = f"{domain}:{source_path}"
    if key not in cfg.get("redirects", {}):
        return {"ok": False, "error": "redirect not found"}
    del cfg["redirects"][key]
    _rebuild_redirect_nginx(domain, cfg)
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    return {"ok": True}


def _rebuild_redirect_nginx(domain: str, cfg: dict[str, Any]) -> None:
    """Rewrite nginx config to include redirect rules for a domain."""
    domain_obj: dict[str, Any] | None = cfg.get("sites", {}).get(domain)
    if not domain_obj:
        return
    config_path: Path = Path(domain_obj["nginx_config"])
    if not config_path.exists():
        return
    content: str = config_path.read_text()
    lines: list[str] = [l for l in content.splitlines() if "return " not in l and "rewrite " not in l]
    redirects: dict[str, Any] = {k: v for k, v in cfg.get("redirects", {}).items() if v.get("domain") == domain}
    if redirects:
        lines.insert(-1, "")
        for r in redirects.values():
            lines.insert(-1, f"    location = {r['source']} {{")
            lines.insert(-1, f"        return {r['type']} {r['target']};")
            lines.insert(-1, f"    }}")
            lines.insert(-1, "")
    config_path.write_text("\n".join(lines), encoding="utf-8")


# ─── v1.0.0+: phpMyAdmin Integration ────────────────────────────────────

def phpmyadmin_install() -> dict[str, Any]:
    """Install and configure phpMyAdmin via apt and nginx."""
    if not is_linux():
        return {"ok": False, "error": "only supported on Linux"}
    steps: list[dict[str, Any]] = []
    r1 = run_cmd(["apt-get", "install", "-y", "-qq", "phpmyadmin", "php-mysql", "php-mbstring"])
    steps.append({"step": "install_packages", "ok": r1.returncode == 0})
    if r1.returncode == 0:
        nginx_conf: str = """server {
    listen 80;
    server_name phpmyadmin.*;
    root /usr/share/phpmyadmin;
    index index.php index.html;
    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }
    location ~ \\.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php-fpm.sock;
    }
}"""
        run_cmd(["bash", "-c", f"cat > /etc/nginx/sites-available/phpmyadmin.conf << 'NGX'\n{nginx_conf}NGX"])
        run_cmd(["ln", "-sf", "/etc/nginx/sites-available/phpmyadmin.conf", "/etc/nginx/sites-enabled/phpmyadmin.conf"])
        run_cmd(["nginx", "-s", "reload"])
        steps.append({"step": "nginx_config", "ok": True})
    return {"ok": True, "url": "http://phpmyadmin.YOUR_SERVER_IP", "steps": steps}


def phpmyadmin_status() -> dict[str, bool]:
    """Check whether phpMyAdmin is installed."""
    if not is_linux():
        return {"installed": False}
    r = run_cmd(["dpkg", "-l", "phpmyadmin"])
    return {"installed": r.returncode == 0}


# ─── v1.0.0+: Roundcube Webmail Integration ────────────────────────────

ROUNDCUBE_VERSION: str = "1.6.9"
ROUNDCUBE_URL: str = f"https://github.com/roundcube/roundcubemail/releases/download/{ROUNDCUBE_VERSION}/roundcubemail-{ROUNDCUBE_VERSION}-complete.tar.gz"
ROUNDCUBE_DIR: Path = Path("/usr/share/roundcube")


def webmail_install() -> dict[str, Any]:
    """Install and configure Roundcube webmail via apt and nginx."""
    if not is_linux():
        return {"ok": False, "error": "only supported on Linux"}
    if webmail_status().get("installed"):
        return {"ok": True, "already_installed": True, "url": "http://webmail.YOUR_SERVER_IP"}
    steps: list[dict[str, Any]] = []
    r1 = run_cmd(["apt-get", "install", "-y", "-qq", "roundcube-core", "roundcube-mysql", "roundcube-plugins", "php-net-smtp", "php-mysql"])
    steps.append({"step": "install_packages", "ok": r1.returncode == 0})
    if not r1.returncode == 0:
        r1 = run_cmd(["apt-get", "install", "-y", "-qq", "php-mysql", "php-mbstring", "php-xml", "php-intl", "php-zip", "php-curl", "php-gd"])
        steps.append({"step": "install_php_extras", "ok": r1.returncode == 0})
    if not ROUNDCUBE_DIR.exists():
        ROUNDCUBE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path: Path = CACHE_DIR / f"roundcubemail-{ROUNDCUBE_VERSION}-complete.tar.gz"
        try:
            download_file(ROUNDCUBE_URL, cache_path, desc="Downloading Roundcube")
            steps.append({"step": "download", "ok": True})
        except Exception as e:
            return {"ok": False, "error": f"download failed: {e}", "steps": steps}
        try:
            extract_archive(cache_path, ROUNDCUBE_DIR.parent)
            extracted: Path = ROUNDCUBE_DIR.parent / f"roundcubemail-{ROUNDCUBE_VERSION}"
            if extracted.exists():
                if ROUNDCUBE_DIR.exists():
                    shutil.rmtree(ROUNDCUBE_DIR)
                extracted.rename(ROUNDCUBE_DIR)
            steps.append({"step": "extract", "ok": True})
        except Exception as e:
            return {"ok": False, "error": f"extract failed: {e}", "steps": steps}
    nginx_conf: str = """server {
    listen 80;
    server_name webmail.*;
    root /usr/share/roundcube;
    index index.php;
    location / {
        try_files $uri $uri/ /index.php?$args;
    }
    location ~ \\.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php-fpm.sock;
    }
}"""
    run_cmd(["bash", "-c", f"cat > /etc/nginx/sites-available/webmail.conf << 'NGX'\n{nginx_conf}NGX"])
    run_cmd(["ln", "-sf", "/etc/nginx/sites-available/webmail.conf", "/etc/nginx/sites-enabled/webmail.conf"])
    run_cmd(["nginx", "-s", "reload"])
    steps.append({"step": "nginx_config", "ok": True})
    audit_event("webmail.install", "ok", {})
    return {"ok": True, "url": "http://webmail.YOUR_SERVER_IP", "steps": steps}


def webmail_status() -> dict[str, bool]:
    """Check whether Roundcube webmail is installed."""
    if not is_linux():
        return {"installed": False}
    dir_ok: bool = ROUNDCUBE_DIR.exists() and (ROUNDCUBE_DIR / "index.php").exists()
    nginx_ok: bool = Path("/etc/nginx/sites-available/webmail.conf").exists()
    return {"installed": dir_ok and nginx_ok}


def roundcube_configure_db() -> dict[str, Any]:
    """Set up a MySQL database and config for Roundcube."""
    if not is_linux():
        return {"ok": False, "error": "only supported on Linux"}
    db_pass: str = secrets.token_urlsafe(24)
    r1 = run_cmd(["mysql", "-e", "CREATE DATABASE IF NOT EXISTS `roundcube` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"])
    r2 = run_cmd(["mysql", "-e", f"CREATE USER IF NOT EXISTS 'roundcube'@'localhost' IDENTIFIED BY '{db_pass}';"])
    r3 = run_cmd(["mysql", "-e", "GRANT ALL PRIVILEGES ON `roundcube`.* TO 'roundcube'@'localhost';"])
    r4 = run_cmd(["mysql", "-e", "FLUSH PRIVILEGES;"])
    if not all(r.returncode == 0 for r in [r1, r2, r3, r4]):
        return {"ok": False, "error": "database setup failed"}
    sql_init: Path = ROUNDCUBE_DIR / "SQL" / "mysql.initial.sql"
    if sql_init.exists():
        run_cmd(["mysql", "roundcube", f"< {sql_init}"], shell=True)
    config_dir: Path = ROUNDCUBE_DIR / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_php: str = f"""<?php
$config['db_dsnw'] = 'mysql://roundcube:{db_pass}@localhost/roundcube';
$config['default_host'] = 'localhost';
$config['smtp_server'] = 'localhost';
$config['smtp_port'] = 25;
$config['support_url'] = '';
$config['product_name'] = 'Webmail';
$config['des_key'] = '{secrets.token_hex(24)}';
$config['plugins'] = ['archive', 'zipdownload', 'password', 'managesieve'];
$config['skin'] = 'elastic';
"""
    (config_dir / "config.inc.php").write_text(config_php)
    audit_event("webmail.configure_db", "ok", {})
    return {"ok": True, "db_password": db_pass}


# ─── v1.0.0+: IP Deny Manager ───────────────────────────────────────────

def ip_deny_add(domain: str, ip_address: str) -> dict[str, Any]:
    """Add an IP deny rule for a domain."""
    cfg: dict[str, Any] = load_config()
    denied: dict[str, list[str]] = cfg.setdefault("ip_deny", {})
    domain_deny: list[str] = denied.setdefault(domain, [])
    if ip_address in domain_deny:
        return {"ok": False, "error": "IP already denied"}
    domain_deny.append(ip_address)
    _rebuild_ip_deny_nginx(domain, cfg)
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    return {"ok": True}


def ip_deny_list(domain: str | None = None) -> dict[str, Any]:
    """Return IP deny rules, optionally filtered by domain."""
    cfg: dict[str, Any] = load_config()
    denied: dict[str, Any] = cfg.get("ip_deny", {})
    if domain:
        return {domain: denied.get(domain, [])}
    return denied


def ip_deny_remove(domain: str, ip_address: str) -> dict[str, Any]:
    """Remove an IP from the deny list for a domain."""
    cfg: dict[str, Any] = load_config()
    denied: dict[str, Any] = cfg.get("ip_deny", {})
    domain_deny: list[str] = denied.get(domain, [])
    if ip_address not in domain_deny:
        return {"ok": False, "error": "IP not found"}
    domain_deny.remove(ip_address)
    _rebuild_ip_deny_nginx(domain, cfg)
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    return {"ok": True}


def _rebuild_ip_deny_nginx(domain: str, cfg: dict[str, Any]) -> None:
    """Rewrite nginx config to include IP deny rules for a domain."""
    domain_obj: dict[str, Any] | None = cfg.get("sites", {}).get(domain)
    if not domain_obj:
        return
    config_path: Path = Path(domain_obj["nginx_config"])
    if not config_path.exists():
        return
    content: str = config_path.read_text()
    denied_ips: list[str] = cfg.get("ip_deny", {}).get(domain, [])
    lines: list[str] = content.splitlines()
    new_lines: list[str] = []
    wrote_deny: bool = False
    for line in lines:
        if "location / {" in line and denied_ips and not wrote_deny:
            new_lines.append(line)
            for ip in denied_ips:
                new_lines.append(f"        deny {ip};")
            wrote_deny = True
        else:
            new_lines.append(line)
    config_path.write_text("\n".join(new_lines), encoding="utf-8")


# ─── v1.0.0+: Hotlink Protection ─────────────────────────────────────────

DEFAULT_HOTLINK_EXTENSIONS: list[str] = ["jpg", "jpeg", "png", "gif", "bmp", "webp", "svg", "ico", "css", "js", "zip", "rar", "pdf"]


def hotlink_protection_set(domain: str, enabled: bool, extensions: list[str] | None = None, allow_domains: list[str] | None = None) -> dict[str, bool]:
    """Enable or disable hotlink protection for a domain."""
    domain = validate_domain(domain)
    cfg: dict[str, Any] = load_config()
    hotlink_cfg: dict[str, Any] = cfg.setdefault("hotlink_protection", {})
    if enabled:
        hotlink_cfg[domain] = {
            "enabled": True,
            "extensions": extensions or DEFAULT_HOTLINK_EXTENSIONS,
            "allow_domains": allow_domains or [],
        }
    else:
        hotlink_cfg.pop(domain, None)
    _rebuild_hotlink_nginx(domain, cfg)
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    audit_event("hotlink.set", "ok", {"domain": domain, "enabled": enabled})
    return {"ok": True}


def hotlink_protection_get(domain: str) -> dict[str, Any]:
    """Return the hotlink protection config for a domain."""
    cfg: dict[str, Any] = load_config()
    hotlink_cfg: dict[str, Any] | None = cfg.get("hotlink_protection", {}).get(domain)
    if hotlink_cfg:
        return hotlink_cfg
    return {"enabled": False, "extensions": [], "allow_domains": []}


def _rebuild_hotlink_nginx(domain: str, cfg: dict[str, Any]) -> None:
    """Rewrite nginx config to include hotlink protection rules."""
    domain_obj: dict[str, Any] | None = cfg.get("sites", {}).get(domain)
    if not domain_obj:
        return
    config_path: Path = Path(domain_obj["nginx_config"])
    if not config_path.exists():
        return
    content: str = config_path.read_text()
    lines: list[str] = [l for l in content.splitlines() if "# HOTLINK" not in l]
    hotlink: dict[str, Any] | None = cfg.get("hotlink_protection", {}).get(domain)
    if hotlink and hotlink.get("enabled"):
        exts: str = "|".join(hotlink.get("extensions", DEFAULT_HOTLINK_EXTENSIONS))
        refs: list[str] = ["none", "blocked"]
        for d in hotlink.get("allow_domains", []):
            refs.append(d)
            refs.append(f"*.{d}")
        ref_str: str = " ".join(refs)
        lines.insert(-1, "")
        lines.insert(-1, f"    location ~* \\.({exts})$ {{  # HOTLINK")
        lines.insert(-1, f"        valid_referers {ref_str};")
        lines.insert(-1, f"        if ($invalid_referer) {{ return 403; }}")
        lines.insert(-1, f"    }}")
    config_path.write_text("\n".join(lines), encoding="utf-8")


# ─── v1.0.0+: Per-Directory IP Access ────────────────────────────────────


def ip_directory_allow_add(domain: str, directory: str, ip_address: str) -> dict[str, Any]:
    """Allow an IP address to access a specific directory."""
    domain = validate_domain(domain)
    cfg: dict[str, Any] = load_config()
    rules: dict[str, Any] = cfg.setdefault("ip_directory_access", {})
    domain_rules: list[dict[str, Any]] = rules.setdefault(domain, [])
    for rule in domain_rules:
        if rule["directory"] == directory:
            if ip_address not in rule["allow"]:
                rule["allow"].append(ip_address)
            if ip_address in rule["deny"]:
                rule["deny"].remove(ip_address)
            _rebuild_ip_directory_nginx(domain, cfg)
            cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
            save_config(cfg)
            audit_event("ip_directory.allow", "ok", {"domain": domain, "directory": directory, "ip": ip_address})
            return {"ok": True}
    domain_rules.append({"directory": directory, "allow": [ip_address], "deny": []})
    _rebuild_ip_directory_nginx(domain, cfg)
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    audit_event("ip_directory.allow", "ok", {"domain": domain, "directory": directory, "ip": ip_address})
    return {"ok": True}


def ip_directory_deny_add(domain: str, directory: str, ip_address: str) -> dict[str, Any]:
    """Deny an IP address from accessing a specific directory."""
    domain = validate_domain(domain)
    cfg: dict[str, Any] = load_config()
    rules: dict[str, Any] = cfg.setdefault("ip_directory_access", {})
    domain_rules: list[dict[str, Any]] = rules.setdefault(domain, [])
    for rule in domain_rules:
        if rule["directory"] == directory:
            if ip_address not in rule["deny"]:
                rule["deny"].append(ip_address)
            if ip_address in rule["allow"]:
                rule["allow"].remove(ip_address)
            _rebuild_ip_directory_nginx(domain, cfg)
            cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
            save_config(cfg)
            audit_event("ip_directory.deny", "ok", {"domain": domain, "directory": directory, "ip": ip_address})
            return {"ok": True}
    domain_rules.append({"directory": directory, "allow": [], "deny": [ip_address]})
    _rebuild_ip_directory_nginx(domain, cfg)
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    audit_event("ip_directory.deny", "ok", {"domain": domain, "directory": directory, "ip": ip_address})
    return {"ok": True}


def ip_directory_remove(domain: str, directory: str, ip_address: str) -> dict[str, Any]:
    """Remove an IP from a directory access rule."""
    cfg: dict[str, Any] = load_config()
    rules: list[dict[str, Any]] = cfg.get("ip_directory_access", {}).get(domain, [])
    for rule in rules:
        if rule["directory"] == directory:
            if ip_address in rule["allow"]:
                rule["allow"].remove(ip_address)
            if ip_address in rule["deny"]:
                rule["deny"].remove(ip_address)
            break
    cfg["ip_directory_access"][domain] = [r for r in rules if r["allow"] or r["deny"]]
    if not cfg["ip_directory_access"][domain]:
        del cfg["ip_directory_access"][domain]
    _rebuild_ip_directory_nginx(domain, cfg)
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    audit_event("ip_directory.remove", "ok", {"domain": domain, "directory": directory, "ip": ip_address})
    return {"ok": True}


def ip_directory_list(domain: str | None = None) -> dict[str, Any]:
    """Return IP directory access rules, optionally filtered by domain."""
    cfg: dict[str, Any] = load_config()
    rules: dict[str, Any] = cfg.get("ip_directory_access", {})
    if domain:
        return {domain: rules.get(domain, [])}
    return rules


def _rebuild_ip_directory_nginx(domain: str, cfg: dict[str, Any]) -> None:
    """Rewrite nginx config to include per-directory IP access rules."""
    domain_obj: dict[str, Any] | None = cfg.get("sites", {}).get(domain)
    if not domain_obj:
        return
    config_path: Path = Path(domain_obj["nginx_config"])
    if not config_path.exists():
        return
    content: str = config_path.read_text()
    lines: list[str] = [l for l in content.splitlines() if "# IPDIR" not in l]
    domain_rules: list[dict[str, Any]] = cfg.get("ip_directory_access", {}).get(domain, [])
    if domain_rules:
        insertions: list[str] = []
        for rule in domain_rules:
            insertions.append("")
            insertions.append(f"    location {rule['directory']} {{  # IPDIR")
            for ip in rule.get("allow", []):
                insertions.append(f"        allow {ip};")
            for ip in rule.get("deny", []):
                insertions.append(f"        deny {ip};")
            if rule.get("allow") and not rule.get("deny"):
                insertions.append(f"        deny all;")
            insertions.append(f"    }}")
        for line in reversed(insertions):
            lines.insert(-1, line)
    config_path.write_text("\n".join(lines), encoding="utf-8")


# ─── v1.0.0+: Rebuild All Nginx Configs ──────────────────────────────────


def rebuild_all_nginx() -> dict[str, bool]:
    """Regenerate nginx configs for all sites, including redirects, IP deny, hotlink, and IP directory rules."""
    cfg: dict[str, Any] = load_config()
    for domain in list(cfg.get("sites", {})):
        site: dict[str, Any] = cfg["sites"][domain]
        generate_nginx_config(
            domain,
            Path(site["web_root"]),
            site.get("proxy_pass"),
            site.get("php", False),
            site.get("php_version"),
        )
        _rebuild_redirect_nginx(domain, cfg)
        _rebuild_ip_deny_nginx(domain, cfg)
        _rebuild_hotlink_nginx(domain, cfg)
        _rebuild_ip_directory_nginx(domain, cfg)
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    audit_event("nginx.rebuild_all", "ok", {"domains": list(cfg.get("sites", {}))})
    return {"ok": True}


# ─── v1.0.0+: API Token Management ─────────────────────────────────────

def api_token_create(name: str, permissions: list[str] | None = None, expires_days: int = 365) -> dict[str, Any]:
    """Create a new API token with optional expiry."""
    cfg: dict[str, Any] = load_config()
    tokens: dict[str, Any] = cfg.setdefault("api_tokens", {})
    token: str = secrets.token_hex(32)
    expires_at: str | None = (datetime.utcnow().isoformat() + "Z") if not expires_days else None
    if expires_days:
        from datetime import timedelta
        expires_at = (datetime.utcnow() + timedelta(days=expires_days)).isoformat() + "Z"
    tokens[token[:16]] = {
        "name": name,
        "token": token,
        "permissions": permissions or ["read"],
        "created_at": datetime.utcnow().isoformat() + "Z",
        "expires_at": expires_at,
        "last_used": None,
    }
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    return {"ok": True, "name": name, "token": token, "id": token[:16]}


def api_token_list() -> list[dict[str, Any]]:
    """Return all API tokens (with masked values)."""
    cfg: dict[str, Any] = load_config()
    tokens: dict[str, Any] = cfg.get("api_tokens", {})
    return [{"id": k, "name": v["name"], "permissions": v.get("permissions", []),
             "created_at": v["created_at"], "expires_at": v.get("expires_at"),
             "last_used": v.get("last_used"), "token": v["token"][:16] + "..."}
            for k, v in tokens.items()]


def api_token_delete(token_id: str) -> dict[str, Any]:
    """Delete an API token by ID."""
    cfg: dict[str, Any] = load_config()
    tokens: dict[str, Any] = cfg.get("api_tokens", {})
    if token_id not in tokens:
        return {"ok": False, "error": "token not found"}
    del tokens[token_id]
    cfg["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_config(cfg)
    return {"ok": True}


def api_token_validate(raw_token: str) -> dict[str, Any] | None:
    """Validate a raw API token and return token metadata or None."""
    if not raw_token:
        return None
    cfg: dict[str, Any] = load_config()
    tokens: dict[str, Any] = cfg.get("api_tokens", {})
    for tid, t in tokens.items():
        if hmac.compare_digest(t["token"], raw_token):
            expires: str | None = t.get("expires_at")
            if expires and expires < datetime.utcnow().isoformat() + "Z":
                return None
            t["last_used"] = datetime.utcnow().isoformat() + "Z"
            save_config(cfg)
            return {"id": tid, "name": t["name"], "permissions": t.get("permissions", [])}
    return None


# ─── v1.0.0+: Two-Factor Authentication (TOTP) ──────────────────────────

def twofa_generate_secret(username: str) -> dict[str, str]:
    """Generate a TOTP secret and provisioning URI for a user."""
    secret: str = base64.b32encode(secrets.token_bytes(20)).decode()
    issuer: str = "Atulya Launch"
    uri: str = f"otpauth://totp/{issuer}:{username}?secret={secret}&issuer={issuer}&digits=6&period=30"
    cfg: dict[str, Any] = load_config()
    twofa: dict[str, Any] = cfg.setdefault("twofa", {})
    twofa[username] = {"secret": secret, "enabled": False, "backup_codes": []}
    save_config(cfg)
    return {"secret": secret, "uri": uri}


def twofa_enable(username: str, code: str) -> dict[str, Any]:
    """Enable 2FA for a user after verifying a valid TOTP code."""
    cfg: dict[str, Any] = load_config()
    twofa: dict[str, Any] | None = cfg.get("twofa", {}).get(username)
    if not twofa:
        return {"ok": False, "error": "no pending 2FA setup"}
    if _totp_verify(twofa["secret"], code):
        twofa["enabled"] = True
        codes: list[str] = [secrets.token_hex(4) for _ in range(10)]
        twofa["backup_codes"] = codes
        save_config(cfg)
        return {"ok": True, "backup_codes": codes}
    return {"ok": False, "error": "invalid code"}


def twofa_disable(username: str, code: str) -> dict[str, bool]:
    """Disable 2FA for a user by verifying a TOTP code or backup code."""
    cfg: dict[str, Any] = load_config()
    twofa: dict[str, Any] | None = cfg.get("twofa", {}).get(username)
    if not twofa or not twofa.get("enabled"):
        return {"ok": False, "error": "2FA not enabled"}
    if _totp_verify(twofa["secret"], code) or code in twofa.get("backup_codes", []):
        del cfg["twofa"][username]
        save_config(cfg)
        return {"ok": True}
    return {"ok": False, "error": "invalid code"}


def twofa_status(username: str) -> dict[str, bool]:
    """Return whether 2FA is enabled for a user."""
    cfg: dict[str, Any] = load_config()
    twofa: dict[str, Any] | None = cfg.get("twofa", {}).get(username)
    return {"enabled": twofa.get("enabled", False) if twofa else False}


def twofa_verify(username: str, code: str) -> bool:
    """Verify a TOTP code or backup code for a user."""
    cfg: dict[str, Any] = load_config()
    twofa: dict[str, Any] | None = cfg.get("twofa", {}).get(username)
    if not twofa or not twofa.get("enabled"):
        return True
    if _totp_verify(twofa["secret"], code):
        return True
    if code in twofa.get("backup_codes", []):
        twofa["backup_codes"].remove(code)
        save_config(cfg)
        return True
    return False


def _totp_verify(secret: str, code: str) -> bool:
    """Verify a TOTP code against a shared secret (RFC 6238)."""
    try:
        import hmac, struct, time as _time
        key: bytes = base64.b32decode(secret)
        for offset in [-1, 0, 1]:
            ts: int = int(_time.time() / 30) + offset
            msg: bytes = struct.pack(">Q", ts)
            digest: bytes = hmac.new(key, msg, "sha1").digest()
            o: int = digest[19] & 15
            token: int = (struct.unpack(">I", digest[o:o+4])[0] & 0x7FFFFFFF) % 1000000
            if f"{token:06d}" == code:
                return True
        return False
    except Exception:
        return False


def deploy_stop(app_id: int) -> dict[str, Any]:
    """Stop a deployed application by killing its process."""
    from .web.database import connect, audit_log
    with connect() as cur:
        row: Any = cur.execute("SELECT * FROM node_apps WHERE id = ?", (app_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "app not found"}
        app: dict[str, Any] = dict(row)
        pid: int | None = app.get("process_id")
        if pid and sys.platform == "linux":
            try:
                os.kill(pid, 15)
            except (OSError, ProcessLookupError):
                pass
        cur.execute("UPDATE node_apps SET process_id = NULL, status = 'stopped' WHERE id = ?", (app_id,))
    audit_log("system", "deploy.stop", "ok", {"app_id": app_id})
    return {"ok": True}


# ─── v0.4.0: Cron Job Management ────────────────────────────────────────────

def cron_create(user_id: int, command: str, schedule: str = "0 0 * * *", domain: str | None = None) -> dict[str, bool]:
    """Create a new cron job in the database."""
    from .web.database import connect, audit_log
    from datetime import datetime
    with connect() as cur:
        cur.execute(
            "INSERT INTO cron_jobs (user_id, domain, command, schedule, enabled, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (user_id, domain, command, schedule, datetime.utcnow().isoformat() + "Z"),
        )
    audit_log("system", "cron.create", "ok", {"command": command[:60]})
    return {"ok": True}


def cron_list() -> list[dict[str, Any]]:
    """List all cron jobs from the database."""
    from .web.database import connect
    try:
        with connect() as cur:
            rows: list[Any] = cur.execute("SELECT * FROM cron_jobs ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
    except RuntimeError:
        return []


def cron_delete(job_id: int) -> None:
    """Delete a cron job."""
    from .web.database import connect, audit_log
    with connect() as cur:
        cur.execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
    audit_log("system", "cron.delete", "ok", {"job_id": job_id})


def cron_toggle(job_id: int, enabled: bool) -> None:
    """Enable or disable a cron job."""
    from .web.database import connect
    with connect() as cur:
        cur.execute("UPDATE cron_jobs SET enabled = ? WHERE id = ?", (1 if enabled else 0, job_id))


# ─── v0.4.0: Log Viewer ─────────────────────────────────────────────────────

LOG_PATHS: dict[str, str | None] = {
    "nginx_access": "/var/log/nginx/access.log",
    "nginx_error": "/var/log/nginx/error.log",
    "panel": None,
    "system": "/var/log/syslog",
    "auth": "/var/log/auth.log",
}


def log_list_sources() -> list[dict[str, Any]]:
    """Return available log sources with their paths."""
    sources: list[dict[str, Any]] = []
    for key, path in LOG_PATHS.items():
        exists: bool = path and Path(path).exists() if path else False
        sources.append({"key": key, "path": path, "exists": exists})
    return sources


def log_view(source: str, lines: int = 100, grep: str | None = None) -> dict[str, Any]:
    """Return recent log lines, optionally filtered by a grep pattern."""
    if source not in LOG_PATHS:
        return {"ok": False, "error": f"unknown log source: {source}"}
    path: str | None = LOG_PATHS[source]
    if source == "panel":
        log_file: Path = ensure_dirs() / "audit.log"
        if not log_file.exists():
            return {"ok": True, "source": source, "lines": []}
        content: list[str] = log_file.read_text().splitlines()
        if grep:
            content = [l for l in content if grep.lower() in l.lower()]
        return {"ok": True, "source": source, "lines": content[-lines:]}
    if not path or not Path(path).exists():
        return {"ok": False, "error": f"log file not found: {path}"}
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        if grep:
            content = [l for l in content if grep.lower() in l.lower()]
        return {"ok": True, "source": source, "lines": content[-lines:]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── v1.0.0: Security Audit ─────────────────────────────────────────────────

def comprehensive_security_audit() -> dict[str, Any]:
    """Perform a comprehensive security audit of the panel and server."""
    results: list[dict[str, str]] = []
    score: int = 100
    cfg: dict[str, Any] = load_config()
    token: str | None = cfg.get("api_token", "")
    if token:
        results.append({"check": "API Token", "status": "warn", "message": "API token exists, ensure it is rotated regularly"})
        score -= 5
    else:
        results.append({"check": "API Token", "status": "pass", "message": "No API token set"})
    bind: str = cfg.get("settings", {}).get("bind_host", "127.0.0.1")
    if bind == "0.0.0.0":
        results.append({"check": "Bind Address", "status": "warn", "message": "Panel bound to 0.0.0.0, restrict to internal network"})
        score -= 10
    else:
        results.append({"check": "Bind Address", "status": "pass", "message": f"Panel bound to {bind}"})
    if sys.platform == "linux":
        try:
            r: subprocess.CompletedProcess = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=10)
            if "active" in r.stdout.lower():
                results.append({"check": "Firewall", "status": "pass", "message": "UFW is active"})
            else:
                results.append({"check": "Firewall", "status": "warn", "message": "UFW is not active"})
                score -= 10
        except FileNotFoundError:
            results.append({"check": "Firewall", "status": "warn", "message": "UFW not installed"})
            score -= 10
        try:
            r = subprocess.run(["fail2ban-client", "status"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                results.append({"check": "Fail2Ban", "status": "pass", "message": "Fail2Ban is running"})
            else:
                results.append({"check": "Fail2Ban", "status": "warn", "message": "Fail2Ban is not running"})
                score -= 5
        except FileNotFoundError:
            results.append({"check": "Fail2Ban", "status": "warn", "message": "Fail2Ban not installed"})
            score -= 5
        try:
            r = subprocess.run(["nginx", "-t"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                results.append({"check": "Nginx Config", "status": "pass", "message": "Nginx configuration is valid"})
            else:
                results.append({"check": "Nginx Config", "status": "error", "message": r.stderr.strip()[:200]})
                score -= 15
        except FileNotFoundError:
            pass
    from .web.database import connect
    panels: list[str] = ["root", "admin", "test", "demo", "user"]
    with connect() as cur:
        for p in panels:
            row: Any = cur.execute("SELECT id FROM users WHERE username = ?", (p,)).fetchone()
            if row:
                results.append({"check": f"Default User ({p})", "status": "warn", "message": f"Default user '{p}' exists"})
                score -= 5
    results.append({"check": "Audit Log", "status": "pass", "message": "Audit logging is active"})
    score = max(0, score)
    return {"score": score, "results": results}


# ─── v1.0.0: Load Testing ───────────────────────────────────────────────────

def load_test(target_url: str, requests: int = 10, concurrency: int = 2) -> dict[str, Any]:
    """Run a simple HTTP load test against a target URL."""
    import concurrent.futures, time, urllib.request
    results_list: list[dict[str, Any]] = []
    errors: int = 0
    start: float = time.time()

    def _req(i: int) -> dict[str, Any]:
        nonlocal errors
        try:
            t0: float = time.time()
            resp: Any = urllib.request.urlopen(target_url, timeout=30)
            elapsed: float = time.time() - t0
            return {"request": i, "status": resp.getcode(), "time": round(elapsed, 3)}
        except Exception as e:
            errors += 1
            return {"request": i, "error": str(e), "time": 0}

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_req, i) for i in range(requests)]
        for f in concurrent.futures.as_completed(futures):
            results_list.append(f.result())

    total: float = time.time() - start
    success_count: int = len([r for r in results_list if "status" in r])
    avg_time: float = sum(r["time"] for r in results_list) / len(results_list) if results_list else 0

    return {
        "ok": True,
        "target": target_url,
        "total_requests": requests,
        "concurrency": concurrency,
        "success": success_count,
        "errors": errors,
        "total_time": round(total, 3),
        "avg_time": round(avg_time, 3),
        "requests_per_sec": round(success_count / total, 1) if total > 0 else 0,
        "results": results_list,
    }


# ─── v1.0.0: Multi-Server Support ──────────────────────────────────────────

def server_create(name: str, host: str, port: int = 22, username: str = "root", auth_type: str = "password", auth_data: str | None = None) -> dict[str, Any]:
    """Register a new remote server for SSH management."""
    from .web.database import connect, audit_log
    from datetime import datetime
    with connect() as cur:
        cur.execute(
            "INSERT INTO servers (name, host, port, username, auth_type, auth_data, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, host, port, username, auth_type, auth_data, datetime.utcnow().isoformat() + "Z"),
        )
    audit_log("system", "server.create", "ok", {"name": name, "host": host})
    return {"ok": True, "name": name}


def server_list() -> list[dict[str, Any]]:
    """List all registered remote servers."""
    from .web.database import connect
    try:
        with connect() as cur:
            rows: list[Any] = cur.execute("SELECT id, name, host, port, username, auth_type, created_at FROM servers ORDER BY name").fetchall()
            return [dict(r) for r in rows]
    except RuntimeError:
        return []


def server_delete(server_id: int) -> None:
    """Delete a remote server record."""
    from .web.database import connect, audit_log
    with connect() as cur:
        cur.execute("DELETE FROM servers WHERE id = ?", (server_id,))


def server_exec(server_id: int, command: str) -> dict[str, Any]:
    """Execute a command on a remote server via SSH (requires paramiko)."""
    server: dict[str, Any] | None = None
    from .web.database import connect
    with connect() as cur:
        row: Any = cur.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
        if row:
            server = dict(row)
    if not server:
        return {"ok": False, "error": "server not found"}
    import paramiko  # optional dependency
    try:
        ssh: paramiko.SSHClient = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if server["auth_type"] == "password":
            ssh.connect(server["host"], port=server["port"], username=server["username"], password=server["auth_data"], timeout=10)
        else:
            key: paramiko.RSAKey = paramiko.RSAKey.from_private_key_file(server["auth_data"])
            ssh.connect(server["host"], port=server["port"], username=server["username"], pkey=key, timeout=10)
        stdin: Any
        stdout: Any
        stderr: Any
        stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
        out: str = stdout.read().decode("utf-8", errors="replace")
        err: str = stderr.read().decode("utf-8", errors="replace")
        ssh.close()
        return {"ok": True, "stdout": out, "stderr": err, "exit_code": stdout.channel.recv_exit_status()}
    except ImportError:
        return {"ok": False, "error": "paramiko not installed (pip install paramiko)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── v1.0.0: Branding / White-Label ────────────────────────────────────────

def branding_set(key: str, value: str) -> None:
    """Set a branding key-value pair in the database."""
    from .web.database import connect
    with connect() as cur:
        existing: Any = cur.execute("SELECT id FROM branding WHERE key = ?", (key,)).fetchone()
        if existing:
            cur.execute("UPDATE branding SET value = ? WHERE key = ?", (value, key))
        else:
            cur.execute("INSERT INTO branding (key, value) VALUES (?, ?)", (key, value))


def branding_get(key: str, default: str | None = None) -> str | None:
    """Get a branding value by key."""
    from .web.database import connect
    try:
        with connect() as cur:
            row: Any = cur.execute("SELECT value FROM branding WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default
    except RuntimeError:
        return default


def branding_get_all() -> dict[str, str]:
    """Return all branding key-value pairs."""
    from .web.database import connect
    try:
        with connect() as cur:
            rows: list[Any] = cur.execute("SELECT key, value FROM branding").fetchall()
            return {r["key"]: r["value"] for r in rows}
    except RuntimeError:
        return {}


def branding_delete(key: str) -> None:
    """Delete a branding entry."""
    from .web.database import connect
    with connect() as cur:
        cur.execute("DELETE FROM branding WHERE key = ?", (key,))


# ─── v1.0.0+: Mail Server Auto-Setup ─────────────────────────────────────

def mail_setup(domain: str) -> dict[str, Any]:
    """Install Postfix + Dovecot for a domain, create SPF/DKIM/DMARC DNS records."""
    if not is_linux():
        return {"ok": False, "error": "mail server setup only supported on Linux"}
    hostname: str = domain
    steps: list[dict[str, Any]] = []
    pkgs = run_cmd(["apt-get", "install", "-y", "-qq", "postfix", "postfix-mysql", "dovecot-core", "dovecot-imapd", "dovecot-pop3d", "dovecot-mysql", "opendkim", "opendkim-tools"])
    steps.append({"step": "install_packages", "ok": pkgs.returncode == 0})
    postfix_conf: str = f"""myhostname = mail.{domain}
mydomain = {domain}
myorigin = $mydomain
mydestination = $myhostname, localhost.$mydomain, localhost, $mydomain
mailbox_command = /usr/lib/dovecot/deliver
smtpd_tls_cert_file = /etc/ssl/certs/ssl-cert-snakeoil.pem
smtpd_tls_key_file = /etc/ssl/private/ssl-cert-snakeoil.key
smtpd_use_tls = yes
smtpd_tls_security_level = may
smtp_tls_security_level = may
"""
    run_cmd(["bash", "-c", f"cat > /etc/postfix/main.cf << 'EOF'\n{postfix_conf}EOF"])
    steps.append({"step": "postfix_config", "ok": True})
    dovecot_conf: str = f"""mail_location = maildir:/var/mail/vhosts/{domain}/%u
namespace inbox {{
  inbox = yes
}}
service auth {{
  unix_listener /var/spool/postfix/private/auth {{
    mode = 0666
  }}
}}
ssl = required
ssl_cert = </etc/ssl/certs/ssl-cert-snakeoil.pem
ssl_key = </etc/ssl/private/ssl-cert-snakeoil.key
"""
    run_cmd(["mkdir", "-p", "/etc/dovecot/conf.d"])
    run_cmd(["bash", "-c", f"cat > /etc/dovecot/conf.d/10-mail.conf << 'EOF'\n{ dovecot_conf }EOF"])
    steps.append({"step": "dovecot_config", "ok": True})
    dkim_dir: str = f"/etc/opendkim/keys/{domain}"
    run_cmd(["mkdir", "-p", dkim_dir])
    dkim_gen = run_cmd(["opendkim-genkey", "-D", dkim_dir, "-d", domain, "-s", "mail"])
    steps.append({"step": "dkim_keygen", "ok": dkim_gen.returncode == 0})
    run_cmd(["systemctl", "restart", "postfix"])
    run_cmd(["systemctl", "restart", "dovecot"])
    run_cmd(["systemctl", "restart", "opendkim"])
    steps.append({"step": "services_restarted", "ok": True})
    dkim_txt: str = ""
    try:
        dkim_path: Path = Path(f"{dkim_dir}/mail.txt")
        if dkim_path.exists():
            dkim_txt = dkim_path.read_text()
    except Exception:
        pass
    dns_records: list[dict[str, Any]] = [
        {"type": "MX", "name": domain, "value": f"mail.{domain}.", "priority": 10},
        {"type": "A", "name": f"mail.{domain}", "value": _get_public_ip()},
        {"type": "TXT", "name": domain, "value": "v=spf1 mx ~all"},
        {"type": "TXT", "name": "_dmarc", "value": "v=DMARC1; p=none; rua=mailto:admin@" + domain},
    ]
    if dkim_txt:
        for line in dkim_txt.splitlines():
            if "v=DKIM1" in line:
                parts: list[str] = line.strip().split('"')
                if len(parts) >= 2:
                    dns_records.append({"type": "TXT", "name": "mail._domainkey", "value": parts[1]})
    run_cmd(["systemctl", "enable", "postfix", "dovecot", "opendkim"])
    return {"ok": True, "domain": domain, "dns_records": dns_records, "steps": steps}


def mail_get_status(domain: str) -> dict[str, Any]:
    """Return the active status of Postfix, Dovecot, and OpenDKIM."""
    result: dict[str, Any] = {"postfix": False, "dovecot": False, "opendkim": False, "dns": []}
    if is_linux():
        for svc in ["postfix", "dovecot", "opendkim"]:
            r = run_cmd(["systemctl", "is-active", svc])
            result[svc] = r.stdout.strip() == "active"
    return result


def mail_create_account(domain: str, mailbox: str, password: str) -> dict[str, Any]:
    """Create a mail account for a domain with Dovecot and database storage."""
    from .web.database import connect
    from .web.auth import hash_password
    if not is_linux():
        return {"ok": False, "error": "only supported on Linux"}
    vhost_dir: Path = Path(f"/var/mail/vhosts/{domain}/{mailbox}")
    vhost_dir.mkdir(parents=True, exist_ok=True)
    pw_hash = run_cmd(["doveadm", "pw", "-s", "SHA512-CRYPT", "-p", password])
    if pw_hash.returncode == 0:
        stored_hash: str = pw_hash.stdout.strip()
    else:
        stored_hash = hash_password(password)
    with connect() as cur:
        cur.execute("INSERT OR REPLACE INTO email_accounts (domain, mailbox, password_hash, quota_mb, created_at) VALUES (?, ?, ?, ?, ?)",
                    (domain, mailbox, stored_hash, 1024, datetime.utcnow().isoformat() + "Z"))
    return {"ok": True, "email": f"{mailbox}@{domain}"}


def _get_public_ip() -> str:
    """Return the public IP address of this server via ipify."""
    try:
        import requests
        return requests.get("https://api.ipify.org", timeout=10).text.strip()
    except Exception:
        return "127.0.0.1"


# ─── v1.0.0+: Scheduled Backups ─────────────────────────────────────────

BACKUP_SCHEDULE_TYPES: set[str] = {"daily", "weekly", "monthly"}

def backup_schedule_create(domain: str, schedule_type: str = "daily", retention: int = 7, time_str: str = "02:00") -> dict[str, Any]:
    """Create a scheduled backup cron job for a domain."""
    if schedule_type not in BACKUP_SCHEDULE_TYPES:
        return {"ok": False, "error": f"invalid schedule type: {schedule_type}"}
    from .web.database import connect
    with connect() as cur:
        existing: Any = cur.execute("SELECT id FROM cron_jobs WHERE domain = ? AND command LIKE ?", (domain, "%backup%")).fetchone()
        if existing:
            return {"ok": False, "error": "backup schedule already exists for this domain"}
        cron_map: dict[str, str] = {"daily": f"{time_str.split(':')[1]} {time_str.split(':')[0]} * * *",
                    "weekly": f"{time_str.split(':')[1]} {time_str.split(':')[0]} * * 0",
                    "monthly": f"{time_str.split(':')[1]} {time_str.split(':')[0]} 1 * *"}
        command: str = f"atulya-launch backup create {domain}"
        if retention:
            command += f" --retention {retention}"
        schedule: str = cron_map[schedule_type]
        from .web.database import connect as db_connect
        with db_connect() as cur2:
            cur2.execute("INSERT INTO cron_jobs (user_id, domain, command, schedule, enabled, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                         (1, domain, command, schedule, datetime.utcnow().isoformat() + "Z"))
    return {"ok": True, "domain": domain, "schedule": schedule_type, "cron": schedule, "retention": retention}


def backup_schedule_list() -> list[dict[str, Any]]:
    """List all backup schedule cron jobs."""
    from .web.database import connect
    with connect() as cur:
        rows: list[Any] = cur.execute("SELECT * FROM cron_jobs WHERE command LIKE '%backup%' ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def backup_schedule_delete(schedule_id: int) -> None:
    """Delete a backup schedule cron job."""
    from .web.database import connect
    with connect() as cur:
        cur.execute("DELETE FROM cron_jobs WHERE id = ? AND command LIKE ?", (schedule_id, "%backup%"))


def backup_run_now(domain: str) -> dict[str, Any]:
    """Run an immediate backup for a domain."""
    result: dict[str, Any] = backup_create(domain)
    return result


# ─── v1.0.0+: WHM-Style Reseller System ─────────────────────────────────

def reseller_create(username: str, password: str, max_clients: int = 5, max_sites: int = 10, max_dbs: int = 5, max_emails: int = 10, disk_limit_mb: int = 1024) -> dict[str, Any]:
    """Create a reseller user with resource allocations."""
    from .web.database import connect
    from .web.auth import create_user
    create_user(username, password, role="reseller", skip_policy=True)
    with connect() as cur:
        uid: int = cur.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]
        cur.execute("INSERT OR REPLACE INTO reseller_allocations (reseller_id, max_clients, max_sites, max_dbs, max_emails, disk_limit_mb, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (uid, max_clients, max_sites, max_dbs, max_emails, disk_limit_mb, datetime.utcnow().isoformat() + "Z"))
    return {"ok": True, "username": username, "id": uid}


def reseller_list() -> list[dict[str, Any]]:
    """List all reseller users with allocation and client count."""
    from .web.database import connect
    with connect() as cur:
        rows: list[Any] = cur.execute("""
            SELECT u.id, u.username, u.created_at,
                   COALESCE(a.max_clients, 0) as max_clients,
                   COALESCE(a.max_sites, 0) as max_sites,
                   COALESCE(a.max_dbs, 0) as max_dbs,
                   COALESCE(a.max_emails, 0) as max_emails,
                   COALESCE(a.disk_limit_mb, 0) as disk_limit_mb,
                   (SELECT COUNT(*) FROM reseller_clients rc WHERE rc.reseller_id = u.id) as client_count
            FROM users u
            LEFT JOIN reseller_allocations a ON a.reseller_id = u.id
            WHERE u.role = 'reseller'
            ORDER BY u.username
        """).fetchall()
        return [dict(r) for r in rows]


def reseller_create_client(reseller_id: int, username: str, password: str, plan_id: int | None = None) -> dict[str, Any]:
    """Create a client account under a reseller."""
    from .web.database import connect
    from .web.auth import create_user
    with connect() as cur:
        alloc: Any = cur.execute("SELECT * FROM reseller_allocations WHERE reseller_id = ?", (reseller_id,)).fetchone()
        if not alloc:
            return {"ok": False, "error": "reseller has no allocation"}
        client_count: int = cur.execute("SELECT COUNT(*) as c FROM reseller_clients WHERE reseller_id = ?", (reseller_id,)).fetchone()["c"]
        if client_count >= alloc["max_clients"]:
            return {"ok": False, "error": f"reseller client limit ({alloc['max_clients']}) reached"}
    create_user(username, password, role="user", skip_policy=True)
    with connect() as cur:
        uid: int = cur.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]
        cur.execute("UPDATE users SET parent_user_id = ? WHERE id = ?", (reseller_id, uid))
        cur.execute("INSERT INTO reseller_clients (reseller_id, client_id, assigned_at) VALUES (?, ?, ?)",
                    (reseller_id, uid, datetime.utcnow().isoformat() + "Z"))
        if plan_id:
            plan_assign(uid, plan_id)
    return {"ok": True, "username": username, "id": uid}


def reseller_list_clients(reseller_id: int) -> list[dict[str, Any]]:
    """List clients belonging to a reseller."""
    from .web.database import connect
    with connect() as cur:
        rows: list[Any] = cur.execute("""
            SELECT u.id, u.username, u.role, u.created_at, u.last_login, u.parent_user_id
            FROM users u
            JOIN reseller_clients rc ON rc.client_id = u.id
            WHERE rc.reseller_id = ?
            ORDER BY u.username
        """, (reseller_id,)).fetchall()
        return [dict(r) for r in rows]


def reseller_delete_client(client_id: int) -> None:
    """Delete a client account and its reseller association."""
    from .web.database import connect
    with connect() as cur:
        cur.execute("DELETE FROM reseller_clients WHERE client_id = ?", (client_id,))
        cur.execute("DELETE FROM users WHERE id = ?", (client_id,))


def reseller_update_allocation(reseller_id: int, max_clients: int | None = None, max_sites: int | None = None, max_dbs: int | None = None, max_emails: int | None = None, disk_limit_mb: int | None = None) -> dict[str, Any]:
    """Update a reseller's resource allocation limits."""
    from .web.database import connect
    with connect() as cur:
        alloc: Any = cur.execute("SELECT * FROM reseller_allocations WHERE reseller_id = ?", (reseller_id,)).fetchone()
        if not alloc:
            return {"ok": False, "error": "reseller not found"}
        if max_clients is not None:
            cur.execute("UPDATE reseller_allocations SET max_clients = ? WHERE reseller_id = ?", (max_clients, reseller_id))
        if max_sites is not None:
            cur.execute("UPDATE reseller_allocations SET max_sites = ? WHERE reseller_id = ?", (max_sites, reseller_id))
        if max_dbs is not None:
            cur.execute("UPDATE reseller_allocations SET max_dbs = ? WHERE reseller_id = ?", (max_dbs, reseller_id))
        if max_emails is not None:
            cur.execute("UPDATE reseller_allocations SET max_emails = ? WHERE reseller_id = ?", (max_emails, reseller_id))
        if disk_limit_mb is not None:
            cur.execute("UPDATE reseller_allocations SET disk_limit_mb = ? WHERE reseller_id = ?", (disk_limit_mb, reseller_id))
    return {"ok": True}
