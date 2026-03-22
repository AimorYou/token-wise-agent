"""Base event classes."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Event:
    """Base event with auto-generated id and timestamp."""

    name: str
    payload: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "payload": self.payload,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        return cls(**data)


@dataclass
class PriorityEvent(Event):
    """Event with priority (lower number = higher priority)."""

    priority: int = 10

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["priority"] = self.priority
        return d
