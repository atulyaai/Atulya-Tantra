import sys
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from . import __version__, ATULYA_TOOLS, ATULYA_ORG
from . import core

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="atulya-launch")
@click.pass_context
def cli(ctx):
    ctx.ensure_object(dict)


@cli.command()
@click.option("--admin", default="admin", help="Admin username to record in local config")
@click.option("--password", default=None, help="Admin password; generated if omitted")
@click.option("--rotate-token", is_flag=True, help="Generate a new local API token")
def init(admin, password, rotate_token):
    result = core.panel_init(admin_user=admin, admin_password=password, rotate_token=rotate_token)
    console.print("[green]Atulya Launch initialized[/green]")
    console.print(f"Config: {result['config_dir']}")
    console.print(f"Admin:  {result['admin_user']}")
    console.print(f"Token:  {result['api_token']}")
    if result.get("generated_password"):
        console.print(f"Generated password: {result['generated_password']}")


@cli.group()
def site():
    """Manage local site records and generated web roots."""


@site.command("create")
@click.argument("domain")
@click.option("--web-root", default=None, help="Web root inside the Atulya config directory")
@click.option("--proxy-pass", default=None, help="Proxy target such as http://127.0.0.1:3000")
@click.option("--php", is_flag=True, help="Include a PHP-FPM block in the generated Nginx preview")
def site_create(domain, web_root, proxy_pass, php):
    try:
        site_data = core.site_create(domain, web_root=web_root, proxy_pass=proxy_pass, php=php)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        sys.exit(1)
    console.print(f"[green]Site created:[/green] {site_data['domain']}")
    console.print(f"Web root: {site_data['web_root']}")
    console.print(f"Nginx:    {site_data['nginx_config']}")


@site.command("list")
@click.option("--json", "as_json", is_flag=True)
def site_list(as_json):
    sites = core.site_list()
    if as_json:
        console.print(json.dumps(sites, indent=2))
        return
    table = Table(box=box.ROUNDED)
    table.add_column("Domain", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Web Root")
    table.add_column("Proxy")
    for site_data in sites.values():
        table.add_row(
            site_data["domain"],
            "yes" if site_data.get("enabled") else "no",
            site_data.get("web_root", "-"),
            site_data.get("proxy_pass") or "-",
        )
    console.print(table)


@site.command("delete")
@click.argument("domain")
def site_delete(domain):
    try:
        deleted = core.site_delete(domain)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        sys.exit(1)
    if deleted:
        console.print(f"[green]Deleted site:[/green] {domain}")
    else:
        console.print(f"[yellow]Site not found:[/yellow] {domain}")


@site.command("nginx-plan")
@click.argument("domain", required=False)
@click.option("--json", "as_json", is_flag=True)
def site_nginx_plan(domain, as_json):
    try:
        plan = core.nginx_apply_plan(domain)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        sys.exit(1)
    if as_json:
        console.print(json.dumps(plan, indent=2))
        return
    table = Table(box=box.ROUNDED)
    table.add_column("Domain", style="cyan")
    table.add_column("Source")
    table.add_column("Target")
    for item in plan:
        table.add_row(item["domain"], item["source"], item["target"])
    console.print(table)


@cli.command("system")
@click.option("--json", "as_json", is_flag=True)
def system_status(as_json):
    data = core.system_status()
    if as_json:
        console.print(json.dumps(data, indent=2))
        return
    panel = Panel(
        f"Platform: {data['platform']}\n"
        f"Python:   {data['python']}\n"
        f"Config:   {data['config_dir']}\n"
        f"CPU:      {data['cpu_count']} cores\n"
        f"Disk:     {data['disk']['percent']}% used\n"
        f"Sites:    {data['sites']}\n"
        f"Backups:  {data['backups']}",
        title="Atulya Launch System",
    )
    console.print(panel)


@cli.group()
def backup():
    """Create and list Atulya Launch backups."""


@backup.command("create")
@click.option("--name", default=None)
def backup_create(name):
    result = core.backup_create(name)
    console.print(f"[green]Backup created:[/green] {result['name']}")
    console.print(f"Path: {result['path']}")
    console.print(f"Size: {result['size']} bytes")


@backup.command("list")
@click.option("--json", "as_json", is_flag=True)
def backup_list(as_json):
    backups = core.backup_list()
    if as_json:
        console.print(json.dumps(backups, indent=2))
        return
    table = Table(box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Created")
    table.add_column("Size", justify="right")
    table.add_column("Path")
    for backup_data in backups.values():
        table.add_row(
            backup_data["name"],
            backup_data.get("created_at", "-"),
            str(backup_data.get("size", 0)),
            backup_data.get("path", "-"),
        )
    console.print(table)


@backup.command("restore")
@click.argument("name")
def backup_restore(name):
    try:
        result = core.backup_restore(name)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        sys.exit(1)
    console.print(f"[green]Backup restored:[/green] {result['name']}")
    console.print(f"Archive: {result['restored_from']}")


@cli.group()
def files():
    """Manage files inside a recorded site's web root."""


@files.command("list")
@click.argument("domain")
@click.argument("path", required=False, default=".")
@click.option("--json", "as_json", is_flag=True)
def files_list(domain, path, as_json):
    try:
        entries = core.file_list(domain, path)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        sys.exit(1)
    if as_json:
        console.print(json.dumps(entries, indent=2))
        return
    table = Table(box=box.ROUNDED)
    table.add_column("Type", style="cyan")
    table.add_column("Name")
    table.add_column("Size", justify="right")
    for entry in entries:
        table.add_row(entry["type"], entry["path"], str(entry.get("size") or "-"))
    console.print(table)


@files.command("write")
@click.argument("domain")
@click.argument("path")
@click.argument("content")
def files_write(domain, path, content):
    try:
        result = core.file_write(domain, path, content)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        sys.exit(1)
    console.print(f"[green]Wrote file:[/green] {result['path']}")


@files.command("mkdir")
@click.argument("domain")
@click.argument("path")
def files_mkdir(domain, path):
    try:
        result = core.file_mkdir(domain, path)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        sys.exit(1)
    console.print(f"[green]Created directory:[/green] {result['path']}")


@files.command("delete")
@click.argument("domain")
@click.argument("path")
def files_delete(domain, path):
    try:
        result = core.file_delete(domain, path)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        sys.exit(1)
    console.print(f"[green]Deleted:[/green] {result['deleted']}")


@cli.command("audit")
@click.option("--limit", default=50)
@click.option("--json", "as_json", is_flag=True)
def audit(limit, as_json):
    events = core.audit_list(limit)
    if as_json:
        console.print(json.dumps(events, indent=2))
        return
    table = Table(box=box.ROUNDED)
    table.add_column("Time")
    table.add_column("Action", style="cyan")
    table.add_column("Status")
    for event in events:
        table.add_row(event["time"], event["action"], event["status"])
    console.print(table)


@cli.command("security-scan")
@click.option("--json", "as_json", is_flag=True)
def security_scan(as_json):
    result = core.security_scan()
    if as_json:
        console.print(json.dumps(result, indent=2))
        return
    console.print(f"Security score: [bold]{result['score']}/100[/bold]")
    if not result["issues"]:
        console.print("[green]No high-risk local configuration issues found.[/green]")
    for issue in result["issues"]:
        console.print(f"[yellow]{issue['level']}[/yellow] {issue['check']}: {issue['message']}")


@cli.group()
def database():
    """Manage databases (MySQL/PostgreSQL)."""


@database.command("create")
@click.argument("name")
@click.option("--type", "db_type", default="mysql", help="Database type: mysql, mariadb, postgresql")
def database_create(name, db_type):
    result = core.database_create(name, db_type)
    if result.get("ok"):
        console.print(f"[green]Database created:[/green] {name} ({db_type})")
    else:
        console.print(f"[red]Failed:[/red] {result.get('error', 'unknown error')}")


@database.command("drop")
@click.argument("name")
@click.option("--type", "db_type", default="mysql")
def database_drop(name, db_type):
    result = core.database_drop(name, db_type)
    if result.get("ok"):
        console.print(f"[green]Database dropped:[/green] {name}")
    else:
        console.print(f"[red]Failed:[/red] {result.get('error', 'unknown error')}")


@database.command("backup")
@click.argument("name")
@click.option("--type", "db_type", default="mysql")
def database_backup_cmd(name, db_type):
    result = core.database_backup(name, db_type)
    if result.get("ok"):
        console.print(f"[green]Backup created:[/green] {result['path']} ({result['size']} bytes)")
    else:
        console.print(f"[red]Failed:[/red] {result.get('error', 'unknown error')}")


@cli.group()
def ssl():
    """Manage SSL/TLS certificates."""


@ssl.command("issue")
@click.argument("domain")
def ssl_issue(domain):
    result = core.ssl_issue_letsencrypt(domain)
    if result.get("ok"):
        console.print(f"[green]Certificate issued:[/green] {domain}")
    else:
        console.print(f"[red]Failed:[/red] {result.get('error', 'unknown error')}")


@ssl.command("renew")
@click.argument("domain")
def ssl_renew_cmd(domain):
    result = core.ssl_renew(domain)
    if result.get("ok"):
        console.print(f"[green]Certificate renewed:[/green] {domain}")
    else:
        console.print(f"[red]Failed:[/red] {result.get('error', 'unknown error')}")


@cli.group()
def firewall():
    """Manage UFW firewall and Fail2Ban."""


@firewall.command("status")
@click.option("--json", "as_json", is_flag=True)
def firewall_status_cmd(as_json):
    status = core.firewall_status()
    rules = core.firewall_list_rules()
    f2b = core.fail2ban_status()
    data = {"ufw": status, "rules": rules, "fail2ban": f2b}
    if as_json:
        console.print(json.dumps(data, indent=2))
        return
    console.print(f"UFW: {'[green]Active[/green]' if status.get('active') else '[yellow]Inactive[/yellow]'}")
    console.print(f"Fail2Ban: {'[green]Active[/green]' if f2b.get('active') else '[yellow]Inactive[/yellow]'}")
    if f2b.get("jails"):
        console.print(f"Jails: {', '.join(f2b['jails'])}")


@firewall.command("ufw-enable")
def firewall_enable_cmd():
    result = core.firewall_enable()
    console.print("[green]UFW enabled[/green]" if result.get("ok") else "[red]Failed to enable UFW[/red]")


@firewall.command("ufw-disable")
def firewall_disable_cmd():
    result = core.firewall_disable()
    console.print("[green]UFW disabled[/green]" if result.get("ok") else "[red]Failed[/red]")


@firewall.command("allow")
@click.argument("port")
@click.option("--proto", default="tcp")
def firewall_allow_cmd(port, proto):
    result = core.firewall_allow(port, proto)
    console.print(f"[green]Allowed {port}/{proto}[/green]" if result.get("ok") else "[red]Failed[/red]")


@firewall.command("deny")
@click.argument("port")
@click.option("--proto", default="tcp")
def firewall_deny_cmd(port, proto):
    result = core.firewall_deny(port, proto)
    console.print(f"[green]Denied {port}/{proto}[/green]" if result.get("ok") else "[red]Failed[/red]")


@cli.command("serve")
@click.option("--host", default=None, help="Bind host (default: 127.0.0.1, or PANEL_HOST env)")
@click.option("--port", default=None, help="Bind port (default: 8080, or PANEL_PORT env)")
@click.option("--workers", default=1, help="Number of worker processes")
@click.option("--https/--no-https", default=False, help="Attempt auto HTTPS via certbot")
@click.option("--log-level", default="info", help="Log level: debug, info, warning, error")
def serve(host, port, workers, https, log_level):
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn not installed. Run: pip install 'atulya-launch[web]'[/red]")
        sys.exit(1)
    import os as _os
    host = host or _os.environ.get("PANEL_HOST", "127.0.0.1")
    port = int(port or _os.environ.get("PANEL_PORT", "8080"))
    workers = int(_os.environ.get("PANEL_WORKERS", str(workers)))
    core.ensure_dirs()
    from .web.app import create_app
    app = create_app()

    if https and host != "127.0.0.1":
        import subprocess as _sp
        try:
            domain = host if host != "0.0.0.0" else _os.environ.get("PANEL_DOMAIN", "")
            if domain:
                _sp.run(["certbot", "--nginx", "-d", domain, "--non-interactive", "--agree-tos", "-m", "admin@" + domain], timeout=60)
                _os.environ["PANEL_HTTPS"] = "1"
                console.print(f"[green]HTTPS enabled for {domain}[/green]")
        except Exception as e:
            console.print(f"[yellow]HTTPS setup skipped: {e}[/yellow]")

    scheme = "https" if _os.environ.get("PANEL_HTTPS", "").lower() in ("1", "true") else "http"
    console.print(f"[bold green]Atulya Launch v{core.__version__ if hasattr(core, '__version__') else '?'}[/bold green]")
    console.print(f"[green]Dashboard:[/green] {scheme}://{host if host != '0.0.0.0' else 'localhost'}:{port}")
    console.print(f"[dim]API docs: {scheme}://{host if host != '0.0.0.0' else 'localhost'}:{port}/api/docs[/dim]")
    console.print("[dim]Change default password after first login.[/dim]")
    uvicorn.run(
        "atulya_launch.web.app:create_app",
        factory=True,
        host=host,
        port=port,
        workers=workers,
        log_level=log_level,
        access_log=True,
        server_header=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


@cli.command(name="list")
def list_tools():
    tools = core.discover_all_tools()
    table = Table(box=box.ROUNDED)
    table.add_column("Tool", style="cyan", no_wrap=True)
    table.add_column("Package", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Version", style="yellow")
    table.add_column("Description")
    for t in tools:
        status = "[green]Installed[/green]" if t["installed"] else "[dim]Not installed[/dim]"
        ver = t.get("version", "-") if t["installed"] else "-"
        table.add_row(t["name"], t["package"], status, ver, t["description"])
    console.print(table)
    console.print(f"\n[dim]{len(tools)} tools | org: {ATULYA_ORG}[/dim]")


@cli.command()
@click.argument("tool_name")
def info(tool_name):
    if tool_name not in ATULYA_TOOLS:
        console.print(f"[red]Unknown tool: {tool_name}[/red]")
        console.print(f"Available: {', '.join(ATULYA_TOOLS)}")
        sys.exit(1)
    info = core.get_tool_info(tool_name)
    installed = core.is_installed(tool_name)
    cfg = core.get_installed_tools().get(tool_name, {})
    version = cfg.get("version") or core.installed_pip_version(tool_name) or "-"
    panel = Panel(
        f"[bold cyan]{tool_name}[/bold cyan]\n"
        f"[blue]Package:[/blue] {info['package']}\n"
        f"[blue]Description:[/blue] {info['description']}\n"
        f"[blue]Status:[/blue] {'[green]Installed[/green]' if installed else '[red]Not installed[/red]'}\n"
        f"[blue]Version:[/blue] {version if installed else '-'}\n"
        f"[blue]GitHub:[/blue] https://github.com/{ATULYA_ORG}/{tool_name}",
        title=f"Atulya {tool_name}",
    )
    console.print(panel)


@cli.command()
@click.argument("tool_name")
@click.option("--version", "-v", "ver", default=None, help="Specific version (tag)")
@click.option("--local", "-l", "local_path", default=None, help="Install from local path")
def install(tool_name, ver, local_path):
    if tool_name not in ATULYA_TOOLS:
        console.print(f"[red]Unknown tool: {tool_name}[/red]")
        sys.exit(1)
    if local_path:
        src = Path(local_path)
        if not src.exists():
            console.print(f"[red]Local path not found: {local_path}[/red]")
            sys.exit(1)
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
            p.add_task(description=f"Installing {tool_name} from {local_path}...")
            core.install_local(tool_name, src)
        console.print(f"[green]Installed {tool_name} from local path[/green]")
    else:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
            p.add_task(description=f"Installing {tool_name} via pip...")
            ok = core.install_from_pip(tool_name, ver)
        if ok:
            installed_ver = ver or "latest"
            cfg = core.load_config()
            cfg.setdefault("installed", {})[tool_name] = {"version": installed_ver, "installed_at": __import__("datetime").datetime.now().isoformat()}
            core.save_config(cfg)
            console.print(f"[green]Installed {tool_name} ({installed_ver})[/green]")
        else:
            console.print(f"[red]Failed to install {tool_name}[/red]")
            sys.exit(1)


@cli.command()
@click.argument("tool_name")
def uninstall(tool_name):
    if tool_name not in ATULYA_TOOLS:
        console.print(f"[red]Unknown tool: {tool_name}[/red]")
        sys.exit(1)
    ok = core.uninstall_pip(tool_name)
    if not ok:
        pkg_dir = core.TOOLS_DIR / core.package_name(tool_name)
        if pkg_dir.exists():
            import shutil
            shutil.rmtree(pkg_dir)
            ok = True
    if ok:
        cfg = core.load_config()
        cfg.get("installed", {}).pop(tool_name, None)
        core.save_config(cfg)
        console.print(f"[green]Uninstalled {tool_name}[/green]")
    else:
        console.print(f"[red]Failed to uninstall {tool_name}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("tool_name")
@click.argument("args", nargs=-1)
def run(tool_name, args):
    if tool_name not in ATULYA_TOOLS:
        console.print(f"[red]Unknown tool: {tool_name}[/red]")
        sys.exit(1)
    exit_code = core.run_tool(tool_name, list(args))
    sys.exit(exit_code)


@cli.command()
@click.argument("tool_name", required=False, default=None)
def update(tool_name=None):
    targets = [tool_name] if tool_name else ATULYA_TOOLS
    results = []
    for name in targets:
        if name not in ATULYA_TOOLS:
            console.print(f"[red]Unknown tool: {name}[/red]")
            sys.exit(1)
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
            p.add_task(description=f"Checking {name}...")
            update_info = core.check_update(name)
        if update_info:
            results.append((name, update_info))
            console.print(f"[yellow]{name}: {update_info['current']} -> {update_info['latest']}[/yellow]")
        else:
            installed = core.is_installed(name)
            if installed:
                console.print(f"[green]{name}: up to date[/green]")
            else:
                console.print(f"[dim]{name}: not installed[/dim]")

    if not results:
        console.print("[green]All tools up to date[/green]")
        return

    console.print("\nUpdates available. Run [bold]atulya-launch install <tool> --version <ver>[/bold] to update.")


@cli.command()
@click.option("--version", "-v", "ver", default=None, help="Specific version (tag)")
def self_update(ver):
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
        p.add_task(description="Updating Atulya-Launch...")
        ok = core.install_from_pip("Atulya-Launch", ver)
    if ok:
        console.print(f"[green]Atulya-Launch updated to {ver or 'latest'}[/green]")
    else:
        console.print("[red]Self-update failed[/red]")
        sys.exit(1)


@cli.command()
@click.argument("tool_name")
@click.option("--count", "-c", default=5, help="Number of recent releases")
def releases(tool_name, count):
    if tool_name not in ATULYA_TOOLS:
        console.print(f"[red]Unknown tool: {tool_name}[/red]")
        sys.exit(1)
    try:
        releases = core.get_github_releases(tool_name, count)
    except Exception as e:
        console.print(f"[red]Failed to fetch releases: {e}[/red]")
        sys.exit(1)

    table = Table(box=box.ROUNDED)
    table.add_column("Version", style="cyan")
    table.add_column("Published", style="white")
    table.add_column("Assets", style="blue")
    for r in releases:
        tag = r["tag_name"]
        published = r.get("published_at", "").split("T")[0] if r.get("published_at") else "-"
        assets = ", ".join(a["name"] for a in r.get("assets", [])) or "(source only)"
        table.add_row(tag, published, assets)
    console.print(table)


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def status(as_json):
    tools = core.discover_all_tools()
    data = {}
    for t in tools:
        name = t["name"]
        data[name] = {
            "installed": t["installed"],
            "description": t["description"],
            "version": t.get("version") if t["installed"] else None,
        }
    if as_json:
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(box=box.ROUNDED)
        table.add_column("Tool", style="cyan")
        table.add_column("Installed", style="green")
        table.add_column("Version", style="yellow")
        for name, info in data.items():
            status_str = "[green]Yes[/green]" if info["installed"] else "[red]No[/red]"
            ver = info.get("version") or "-"
            table.add_row(name, status_str, ver)
        console.print(table)


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
