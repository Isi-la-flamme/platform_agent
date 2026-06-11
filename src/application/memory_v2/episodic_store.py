# episodic_store.py
from datetime import datetime
from .models import MemoryItem, new_id


class EpisodicMemory:
    def __init__(self):
        self.store: list[MemoryItem] = []

    def add(self, input: str, output: str, metadata: dict = None):
        self.store.append(
            MemoryItem(
                id=new_id(),
                content=f"Q:{input} | A:{output}",
                metadata=metadata or {},
                timestamp=datetime.utcnow(),
            )
        )

    def recent(self, limit: int = 10):
        return self.store[-limit:]