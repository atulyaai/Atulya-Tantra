"""Cryptographically signed MCP manifests."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MCPManifest:
    name: str
    version: str
    tools: list[dict[str, Any]]
    author: str = ""
    description: str = ""
    created_at: float = field(default_factory=time.time)
    signature: str = ""


class MCPManifestSigner:
    def __init__(self, secret: str | None = None):
        self._secret = secret or "mcp-signing-secret-change-in-production"

    def sign(self, manifest: MCPManifest) -> str:
        """Sign an MCP manifest."""
        payload = json.dumps({
            "name": manifest.name,
            "version": manifest.version,
            "tools": manifest.tools,
            "author": manifest.author,
            "created_at": manifest.created_at,
        }, sort_keys=True)
        signature = hmac.new(self._secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        manifest.signature = signature
        return signature

    def verify(self, manifest: MCPManifest) -> bool:
        """Verify an MCP manifest signature."""
        if not manifest.signature:
            return False
        payload = json.dumps({
            "name": manifest.name,
            "version": manifest.version,
            "tools": manifest.tools,
            "author": manifest.author,
            "created_at": manifest.created_at,
        }, sort_keys=True)
        expected = hmac.new(self._secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, manifest.signature)

    def save_manifest(self, manifest: MCPManifest, path: str | Path):
        """Save signed manifest to file."""
        self.sign(manifest)
        Path(path).write_text(json.dumps(vars(manifest), indent=2))

    def load_manifest(self, path: str | Path) -> MCPManifest | None:
        """Load and verify manifest from file."""
        if not Path(path).exists():
            return None
        data = json.loads(Path(path).read_text())
        manifest = MCPManifest(**data)
        if not self.verify(manifest):
            raise ValueError("Invalid manifest signature")
        return manifest
