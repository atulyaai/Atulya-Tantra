"""Brain: brain tiers, the provider catalogue, safety rules, the tool belt, the failover router, the local model and the language-model layer."""
from __future__ import annotations

import asyncio
import base64
import inspect
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator

from atulya.persona import MoodState, Persona, build_emotional_directive, current_user, detect_emotion
from atulya.skills import Tool, ToolRegistry, ToolResult, create_default_registry


# Providers and tools are wired up as each module imports.
from . import tiers
from .tiers import *  # noqa: F401,F403
from . import catalog
from .catalog import *  # noqa: F401,F403
from . import policy
from .policy import *  # noqa: F401,F403
from . import tools
from .tools import *  # noqa: F401,F403
from . import providers
from .providers import *  # noqa: F401,F403
from . import local
from .local import *  # noqa: F401,F403
from . import language
from .language import *  # noqa: F401,F403

# Private helpers that callers and tests reach through the package.
from .tiers import _FALLBACK_ORDER, _HF  # noqa: F401
from .policy import _CHECKS, _CONFIRM_ACTIONS, _CONFIRM_TOOLS, _MCP_READONLY, _auto_approved, _mcp_readonly  # noqa: F401
from .providers import _FAIL_COOLDOWN, _FAIL_SCORE, _LOCAL_NAMES, _SPEED, _chunk_stream_text, _looks_like_safety_label  # noqa: F401
from .providers import _record_speed, _speed_score, _supports_tools  # noqa: F401
from .local import _ACTION_CUES, _DEFAULT_MODEL_DIR, _LEGACY_MODEL_DIR, _PORTABLE_MODEL_DIR, _REPO_ROOT, _THINK_RE  # noqa: F401
from .local import _asked, _download_progress, _ensure_model, _model_dirs, _normalize_tool_call_xml, _resolve_model_path  # noqa: F401
from .local import _strip_think, _with_think_switch  # noqa: F401
from .language import _HUMAN_STYLE, _PAST_CUES, _TOOL_PRIORITY, _chunk_text, _echoed_memory, _recent_feedback  # noqa: F401
from .language import _words  # noqa: F401
