"""Subagent orchestrator — multi-agent parallel task execution
with task decomposition and results aggregation."""
from __future__ import annotations

from .orchestrator import SubAgentOrchestrator, AgentTask, AgentResult, AgentSpec

__all__ = ["SubAgentOrchestrator", "AgentTask", "AgentResult", "AgentSpec"]
