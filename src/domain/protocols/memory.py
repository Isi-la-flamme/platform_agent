from typing import Protocol

from src.domain.entities.memory import MemoryFact


class LongTermMemory(Protocol):
    def remember(self, key: str, value: str, text: str) -> None:
        ...

    def get(self, key: str) -> MemoryFact | None:
        ...

    def search(self, query: str, limit: int = 5) -> list[MemoryFact]:
        ...

    def all(self) -> list[MemoryFact]:
        ...
