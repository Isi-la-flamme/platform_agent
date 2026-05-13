from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryFact:
    key: str
    value: str
    text: str
    updated_at: str
