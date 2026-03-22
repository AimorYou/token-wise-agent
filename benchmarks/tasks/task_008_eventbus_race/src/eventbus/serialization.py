"""Event serialization to/from JSON."""

from __future__ import annotations

import json
from .events import Event, PriorityEvent


def serialize_event(event: Event) -> str:
    """Serialize an event to a JSON string."""
    data = event.to_dict()
    data["__type__"] = type(event).__name__
    return json.dumps(data)


def deserialize_event(raw: str) -> Event:
    """Deserialize a JSON string back to an Event."""
    data = json.loads(raw)
    event_type = data.pop("__type__", "Event")
    if event_type == "PriorityEvent":
        return PriorityEvent(**data)
    return Event(**data)
