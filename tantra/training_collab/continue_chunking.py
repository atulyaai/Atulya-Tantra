#!/usr/bin/env python3
"""Compatibility launcher for chunking only previously unprocessed inputs."""

from __future__ import annotations

import sys

from chunk_data import main


if __name__ == "__main__":
    if "--only-new" not in sys.argv:
        sys.argv.append("--only-new")
    main()
