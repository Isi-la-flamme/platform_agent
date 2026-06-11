from .models import MemoryItem, new_id
from datetime import datetime


class ProceduralMemory:
    def __init__(self):
        self.store: list[MemoryItem] = []

    def add_pattern(self, task: str, steps: list[str], success: bool):
        self.store.append(
            MemoryItem(
                id=new_id(),
                content=task,
                metadata={
                    "steps": steps,
                    "success": success
                },
                timestamp=datetime.utcnow(),
            )
        )

    def all(self):
        return self.store

    def best_strategy(self, task: str):
        candidates = [m for m in self.store if task in m.content]

        return sorted(
            candidates,
            key=lambda x: x.metadata.get("success", 0),
            reverse=True
        )