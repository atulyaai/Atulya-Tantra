#!/usr/bin/env python
"""Atulya Agent CLI — manage tools, chat, users, config, server."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from .tools import TOOL_REGISTRY, execute_tool, get_tool_schemas, download_vision_model


async def _cmd_list(args):
    print("Atulya Agent Tools:\n")
    for name, info in sorted(TOOL_REGISTRY.items()):
        params = ", ".join(info["parameters"].keys())
        print(f"  {name}({params})")
        print(f"    {info['description']}\n")
    return 0


async def _cmd_schemas(args):
    print(json.dumps(get_tool_schemas(), indent=2))
    return 0


async def _cmd_run(args):
    result = await execute_tool(args.tool, **{})
    print(result)
    return 0


async def _cmd_download(args):
    print(f"Downloading {args.model} vision model...")
    result = await download_vision_model(model_type=args.model)
    print(result)
    return 0


async def _cmd_chat(args):
    from .core import AgentCore
    from atulya.llm import ProviderRouter
    router = ProviderRouter()
    core = AgentCore(llm_provider=router)
    print(f"You: {args.text}")
    print(f"Atulya: ", end="", flush=True)
    result = await core.process(args.text)
    print(result)
    return 0


def _cmd_users(args):
    from drishti.dashboard import users
    if args.action == "list":
        for u in users.list_users():
            print(f"  {u['username']:20s} role={u.get('role','user'):10s} display={u.get('display_name','')}")
    elif args.action == "create":
        result = users.create_user(args.username, args.password, role=args.role or "user", display_name=args.display_name or "")
        if result:
            print(f"User '{args.username}' created (role={args.role or 'user'}).")
        else:
            print(f"User '{args.username}' already exists.")
    elif args.action == "delete":
        if users.delete_user(args.username):
            print(f"User '{args.username}' deleted.")
        else:
            print(f"User '{args.username}' not found.")
    elif args.action == "token":
        token = users.create_session(args.username)
        print(f"Session token: {token}")
    return 0


def _cmd_config(args):
    from drishti.dashboard.state import ADMIN_TOKEN, ADMIN_TOKEN_SOURCE
    print(f"Admin token: {ADMIN_TOKEN[:16]}... (source: {ADMIN_TOKEN_SOURCE})")
    path = Path("config")
    for p in sorted(path.rglob("*")):
        if p.is_file() and p.stat().st_size > 0:
            print(f"  config/{p.name}: {p.stat().st_size:,} bytes")
    return 0


def _cmd_server(args):
    import uvicorn
    from drishti.dashboard.app import app
    host = args.host or "127.0.0.1"
    port = args.port or 7090
    print(f"Starting Atulya Dashboard on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level=args.log_level or "info")


def _cmd_health(args):
    import urllib.request
    import json as _json
    base = args.url or "http://127.0.0.1:7090"
    try:
        with urllib.request.urlopen(f"{base}/api/health", timeout=5) as resp:
            data = _json.loads(resp.read())
            print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Health check failed: {e}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Atulya Agent CLI")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="List all tools")
    p_list.set_defaults(func=_cmd_list)

    p_schemas = sub.add_parser("schemas", help="Print tool JSON schemas")
    p_schemas.set_defaults(func=_cmd_schemas)

    p_run = sub.add_parser("run", help="Run a tool (quick test)")
    p_run.add_argument("tool", help="Tool name")
    p_run.set_defaults(func=_cmd_run)

    p_dl = sub.add_parser("download", help="Download vision model")
    p_dl.add_argument("--model", default="llava", choices=["llava", "bakllava"])
    p_dl.set_defaults(func=_cmd_download)

    p_chat = sub.add_parser("chat", help="Chat with the agent")
    p_chat.add_argument("text", help="Your message")
    p_chat.set_defaults(func=_cmd_chat)

    p_users = sub.add_parser("users", help="Manage users")
    p_users.add_argument("action", choices=["list", "create", "delete", "token"])
    p_users.add_argument("--username", default="")
    p_users.add_argument("--password", default="")
    p_users.add_argument("--role", default="")
    p_users.add_argument("--display-name", default="")
    p_users.set_defaults(func=_cmd_users)

    p_cfg = sub.add_parser("config", help="Show configuration")
    p_cfg.set_defaults(func=_cmd_config)

    p_srv = sub.add_parser("serve", help="Start the dashboard server")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=7090)
    p_srv.add_argument("--log-level", default="info")
    p_srv.set_defaults(func=_cmd_server)

    p_hlth = sub.add_parser("health", help="Check server health")
    p_hlth.add_argument("--url", default="http://127.0.0.1:7090")
    p_hlth.set_defaults(func=_cmd_health)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    cmd = args.func
    if asyncio.iscoroutinefunction(cmd):
        sys.exit(asyncio.run(cmd(args)))
    else:
        sys.exit(cmd(args))


if __name__ == "__main__":
    main()
