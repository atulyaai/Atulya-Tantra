"""Observability system - usage tracking, metrics, traces, error tracking."""
# NOTE: All observability data is intentionally kept in-memory only (no disk persistence).
# This is by design — lightweight telemetry without storage overhead.
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class UsageRecord:
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    duration: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class TraceSpan:
    trace_id: str
    span_id: str
    name: str
    start_time: float
    end_time: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"


@dataclass
class ErrorRecord:
    error_type: str
    message: str
    stack_trace: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class UsageTracker:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir) / "usage"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._records: list[UsageRecord] = []

    def record(self, record: UsageRecord):
        self._records.append(record)

    def get_total_cost(self) -> float:
        return sum(r.cost for r in self._records)


class MetricsCollector:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir) / "metrics"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}

    def counter(self, name: str, value: float = 1.0):
        self._counters[name] = self._counters.get(name, 0.0) + value

    def gauge(self, name: str, value: float):
        self._gauges[name] = value

    def export_prometheus(self) -> str:
        lines = []
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter\n{name} {value}")
        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge\n{name} {value}")
        return "\n".join(lines)


class TraceCollector:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir) / "traces"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._traces: dict[str, list[TraceSpan]] = {}

    def start_span(self, trace_id: str, span_id: str, name: str) -> TraceSpan:
        span = TraceSpan(trace_id=trace_id, span_id=span_id, name=name, start_time=time.time())
        self._traces.setdefault(trace_id, []).append(span)
        return span

    def end_span(self, trace_id: str, span_id: str, status: str = "ok"):
        for span in self._traces.get(trace_id, []):
            if span.span_id == span_id:
                span.end_time = time.time()
                span.status = status


class ErrorTracker:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir) / "errors"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._errors: list[ErrorRecord] = []

    def capture(self, error: ErrorRecord):
        self._errors.append(error)

    def get_summary(self) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        for error in self._errors:
            by_type[error.error_type] = by_type.get(error.error_type, 0) + 1
        return {"total_errors": len(self._errors), "by_type": by_type}
