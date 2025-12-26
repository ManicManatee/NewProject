from __future__ import annotations

import json
import logging
import sys
from collections import deque
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Deque, Dict, List, Optional


@dataclass
class AuditEvent:
    timestamp: str
    level: str
    message: str
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class InMemoryAuditStore:
    """Thread-safe audit event buffer for reporting and UI consumption."""

    def __init__(self, max_events: int = 1000):
        self._events: Deque[AuditEvent] = deque(maxlen=max_events)
        self._lock = Lock()

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.appendleft(event)

    def list(self, limit: int = 100) -> List[AuditEvent]:
        with self._lock:
            return list(list(self._events)[:limit])


class JsonAuditLogger:
    """Structured logger for audit and operational events.

    Logs JSON to stdout and optionally mirrors events to an in-memory store
    for UI reporting.
    """

    def __init__(
        self,
        name: str = "control_plane",
        level: int = logging.INFO,
        store: Optional[InMemoryAuditStore] = None,
    ):
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(_JsonFormatter())
            self.logger.addHandler(handler)
        self.logger.setLevel(level)
        self.logger.propagate = False
        self.store = store

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        event = self._build_event(level, message, **kwargs)
        if self.store:
            self.store.append(event)
        self.logger.log(level, message, extra={"extra": kwargs})

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(logging.INFO, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def _build_event(self, level: int, message: str, **kwargs: Any) -> AuditEvent:
        return AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=logging.getLevelName(level),
            message=message,
            tenant_id=kwargs.get("tenant_id"),
            correlation_id=kwargs.get("correlation_id"),
            extra={k: v for k, v in kwargs.items() if k not in {"tenant_id", "correlation_id"}},
        )


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        extra: Optional[Dict[str, Any]] = getattr(record, "extra", None)  # type: ignore[attr-defined]
        if extra:
            payload.update(extra)

        return json.dumps(payload)
