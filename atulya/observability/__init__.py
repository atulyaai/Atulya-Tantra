"""Observability system — usage tracking, metrics, traces, error tracking."""
from __future__ import annotations

import json
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
class MetricPoint:
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
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
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "usage"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._records: list[UsageRecord] = []
        self._costs: dict[str, float] = {}

    def record(self, record: UsageRecord):
        self._records.append(record)
        self._costs[record.provider] = self._costs.get(record.provider, 0) + record.cost

    def get_total_cost(self) -> float:
        return sum(self._costs.values())

    def get_by_provider(self) -> dict[str, dict[str, Any]]:
        result = {}
        for r in self._records:
            if r.provider not in result:
                result[r.provider] = {"requests": 0, "tokens": 0, "cost": 0.0}
            result[r.provider]["requests"] += 1
            result[r.provider]["tokens"] += r.input_tokens + r.output_tokens
            result[r.provider]["cost"] += r.cost
        return result

    def get_session_summary(self) -> dict[str, Any]:
        return {
            "total_requests": len(self._records),
            "total_cost": self.get_total_cost(),
            "by_provider": self.get_by_provider(),
        }


class MetricsCollector:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "metrics"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._points: list[MetricPoint] = []

    def counter(self, name: str, value: float = 1.0):
        self._counters[name] = self._counters.get(name, 0) + value
        self._points.append(MetricPoint(name=name, value=value))

    def gauge(self, name: str, value: float):
        self._gauges[name] = value
        self._points.append(MetricPoint(name=name, value=value))

    def histogram(self, name: str, value: float):
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

    def export_prometheus(self) -> str:
        lines = []
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter\n{name} {value}")
        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge\n{name} {value}")
        for name, values in self._histograms.items():
            lines.append(f"# TYPE {name} histogram\n{name}_sum {sum(values)}\n{name}_count {len(values)}")
        return "\n".join(lines)


class TraceCollector:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "traces"
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
                break

    def get_trace(self, trace_id: str) -> list[TraceSpan]:
        return self._traces.get(trace_id, [])


class ErrorTracker:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "errors"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._errors: list[ErrorRecord] = []

    def capture(self, error: ErrorRecord):
        self._errors.append(error)

    def get_summary(self) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        for e in self._errors:
            by_type[e.error_type] = by_type.get(e.error_type, 0) + 1
        return {"total_errors": len(self._errors), "by_type": by_type}


class ObservabilitySystem:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.usage = UsageTracker(self.data_dir)
        self.metrics = MetricsCollector(self.data_dir)
        self.traces = TraceCollector(self.data_dir)
        self.errors = ErrorTracker(self.data_dir)

    def record_llm_call(self, provider: str, model: str, input_tokens: int, output_tokens: int, cost: float, duration: float):
        self.usage.record(UsageRecord(provider=provider, model=model, input_tokens=input_tokens, output_tokens=output_tokens, cost=cost, duration=duration))
        self.metrics.counter("llm_calls")
        self.metrics.histogram("llm_duration", duration)

    def record_tool_call(self, tool_name: str, duration: float):
        self.metrics.counter(f"tool_{tool_name}")
        self.metrics.histogram("tool_duration", duration)

    def record_error(self, error: Exception, context: dict[str, Any] | None = None):
        self.errors.capture(ErrorRecord(error_type=type(error).__name__, message=str(error), context=context or {}))

    def start_trace(self, trace_id: str, name: str) -> TraceSpan:
        return self.traces.start_span(trace_id, f"{trace_id}_span_0", name)

    def end_trace(self, trace_id: str, status: str = "ok"):
        self.traces.end_span(trace_id, f"{trace_id}_span_0", status)

    def get_dashboard_data(self) -> dict[str, Any]:
        return {
            "usage": self.usage.get_session_summary(),
            "metrics": {
                "counters": self.metrics._counters,
                "gauges": self.metrics._gauges,
            },
            "traces": {"total_traces": len(self.traces._traces)},
            "errors": self.errors.get_summary(),
        }
