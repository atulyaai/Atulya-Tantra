#!/usr/bin/env python
"""CLI for Atulya Agent tools — list, test, download model."""
from __future__ import annotations

import argparse
import asyncio
import sys

from .tools import TOOL_REGISTRY, download_vision_model


async def _list_tools():
    print("Atulya Agent Tools:\n")
    for name, info in sorted(TOOL_REGISTRY.items()):
        params = ", ".join(info["parameters"].keys())
        print(f"  {name}({params})")
        print(f"    {info['description']}\n")
    return 0


async def _download(model_type: str):
    print(f"Downloading {model_type} vision model...")
    result = await download_vision_model(model_type=model_type)
    print(result)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Atulya Agent Tools CLI")
    parser.add_argument("--list-tools", action="store_true", help="List all registered tools")
    parser.add_argument("--download-vision", choices=["llava", "bakllava"], default=None, help="Download vision model")
    args = parser.parse_args()

    if args.list_tools:
        sys.exit(asyncio.run(_list_tools()))
    elif args.download_vision:
        sys.exit(asyncio.run(_download(args.download_vision)))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
