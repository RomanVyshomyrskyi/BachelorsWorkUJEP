"""
Observability module: metrics collection, Prometheus endpoint, and error tracking.

Provides:
- MetricsCollector class with labeled counters and histograms
- Prometheus-compatible /metrics HTTP endpoint
- Error ring buffer (last 100 errors) with /errors endpoint
- Structured JSON log file: logs/metrics.jsonl
"""

import json
import os
import time
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


# ── Ring buffer for errors ─────────────────────────────────────────────

class ErrorRingBuffer:
    """Keeps the last N error entries in memory for the /errors endpoint."""

    def __init__(self, capacity: int = 100):
        self._buffer: deque[Dict[str, Any]] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def add(self, tool: str, error_message: str, status_code: int = 0,
            duration_ms: int = 0, **extra: Any) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "error_message": error_message,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }
        entry.update(extra)
        with self._lock:
            self._buffer.append(entry)

    def get_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._buffer)


# ── JSON log writer ────────────────────────────────────────────────────

class JsonLogFile:
    """Append-only structured JSON log file."""

    def __init__(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._path = path

    def write(self, entry: Dict[str, Any]) -> None:
        line = json.dumps(entry, default=str) + "\n"
        with open(self._path, "a") as f:
            f.write(line)


# ── Prometheus metric factories ────────────────────────────────────────

def _make_counter(name: str, labelnames: list[str]) -> Counter:
    return Counter(name, "", labelnames=labelnames)


def _make_histogram(name: str) -> Histogram:
    return Histogram(name, "", buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0])


# ── MetricsCollector ───────────────────────────────────────────────────

class MetricsCollector:
    """
    In-process metrics collector that writes to Prometheus and a JSON log file.

    Usage:
        mc = MetricsCollector()
        with mc.tool_timing("superset_create_chart", status="success"):
            ...
        mc.increment_counter("resources_created", {"resource_type": "chart"})
    """

    def __init__(self, log_path: Optional[str] = None) -> None:
        # Prometheus counters
        self.tool_calls = _make_counter(
            "tool_calls_total", ["tool", "status"]
        )
        self.resources_created = _make_counter(
            "resources_created_total", ["resource_type"]
        )
        self.transfers_total = _make_counter(
            "transfers_total", ["status"]
        )
        self.transfers_items = _make_counter(
            "transfers_items_total", ["status", "item_type"]
        )
        self.queries_executed = _make_counter(
            "queries_executed_total", ["source"]
        )
        self.charts_generated = _make_counter(
            "charts_generated_total", ["chart_type"]
        )
        self.dashboards_generated = _make_counter(
            "dashboards_generated_total", ["layout_type"]
        )
        self.api_requests = _make_counter(
            "api_requests_total", ["method", "endpoint", "status_code"]
        )
        self.db_queries = _make_counter(
            "db_queries_total", ["db_type", "status"]
        )

        # Prometheus histogram
        self.tool_duration = _make_histogram("tool_duration_seconds")

        # Infrastructure
        self._errors = ErrorRingBuffer(capacity=100)
        self._json_log = JsonLogFile(log_path or "logs/metrics.jsonl")

    # ── Context manager for tool timing ────────────────────────────────

    class _tool_timing:
        def __init__(self, collector: "MetricsCollector", tool: str,
                     status: str = "success") -> None:
            self._collector = collector
            self._tool = tool
            self._status = status
            self._start = time.monotonic()

        def __enter__(self) -> "_tool_timing":
            return self

        def __exit__(self, *exc: Any) -> None:
            elapsed = time.monotonic() - self._start
            elapsed_ms = int(elapsed * 1000)

            self._collector.tool_calls.labels(tool=self._tool, status=self._status).inc()
            self._collector.tool_duration.labels(tool=self._tool).observe(elapsed)

            self._collector._json_log.write({
                "ts": datetime.now(timezone.utc).isoformat(),
                "tool": self._tool,
                "status": self._status,
                "duration_ms": elapsed_ms,
            })

    def tool_timing(self, tool: str, status: str = "success"):
        return self._tool_timing(self, tool, status)

    # ── Decorator for async tools ──────────────────────────────────────

    def tool_wrapper(self, tool: str):
        """Decorator for async functions that tracks execution."""
        def decorator(fn):
            async def wrapper(*args, **kwargs):
                start = time.monotonic()
                status = "success"
                try:
                    result = await fn(*args, **kwargs)
                    if isinstance(result, str) and ("Error" in result or "error" in result.lower()):
                        status = "error"
                    return result
                except Exception as e:
                    status = "error"
                    raise
                finally:
                    elapsed = time.monotonic() - start
                    self.tool_calls.labels(tool=tool, status=status).inc()
                    self.tool_duration.labels(tool=tool).observe(elapsed)
                    self._json_log.write({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "tool": tool,
                        "status": status,
                        "duration_ms": int(elapsed * 1000),
                    })
                    if status == "error":
                        self.record_error(tool=tool, error_message=str(e), duration_ms=int(elapsed * 1000))
            return wrapper
        return decorator

    # ── Counter helpers ────────────────────────────────────────────────

    def increment_counter(self, metric_name: str, labels: Dict[str, str]) -> None:
        """Increment any registered counter by name."""
        counters = {
            "resources_created": self.resources_created,
            "transfers": self.transfers_total,
            "transfer_items": self.transfers_items,
            "queries_executed": self.queries_executed,
            "charts_generated": self.charts_generated,
            "dashboards_generated": self.dashboards_generated,
            "api_requests": self.api_requests,
            "db_queries": self.db_queries,
        }
        metric = counters.get(metric_name)
        if metric is None:
            raise ValueError(f"Unknown metric: {metric_name}")
        metric.labels(**labels).inc()

    # ── Error tracking ─────────────────────────────────────────────────

    def record_error(self, tool: str, error_message: str,
                     status_code: int = 0, duration_ms: int = 0) -> None:
        """Record an error in the ring buffer and log file."""
        self._errors.add(tool=tool, error_message=error_message,
                         status_code=status_code, duration_ms=duration_ms)
        self._json_log.write({
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "error_message": error_message,
            "status_code": status_code,
            "duration_ms": duration_ms,
        })

    # ── Accessors ──────────────────────────────────────────────────────

    def get_errors(self) -> list[dict]:
        return self._errors.get_all()


# ── Singleton instance ────────────────────────────────────────────────

_instance: Optional[MetricsCollector] = None
_instance_lock = threading.Lock()


def get_metrics() -> MetricsCollector:
    """Get or create the singleton MetricsCollector instance."""
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = MetricsCollector(log_path="logs/metrics.jsonl")
        return _instance


def reset_metrics_for_testing() -> None:
    """Reset the singleton (tests only)."""
    global _instance
    with _instance_lock:
        _instance = None
