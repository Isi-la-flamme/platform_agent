# models.py
from dataclasses import dataclass
from typing import Any
from datetime import datetime
import uuid


@dataclass
class MemoryItem:
    id: str
    content: str
    metadata: dict[str, Any]
    timestamp: datetime
    importance: float = 0.5
    access_count: int = 0


def new_id() -> str:
    return str(uuid.uuid4())