# semantic_store.py
from .models import MemoryItem, new_id
from datetime import datetime


class SemanticMemory:
    def __init__(self):
        self.store: list[MemoryItem] = []

    def add_fact(self, content: str, importance: float = 0.5):
        self.store.append(
            MemoryItem(
                id=new_id(),
                content=content,
                metadata={"type": "fact"},
                timestamp=datetime.utcnow(),
                importance=importance,
            )
        )

    def all(self):
        return self.store