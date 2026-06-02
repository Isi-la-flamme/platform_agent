import json
from pathlib import Path

from src.domain.entities.memory import MemoryFact


class JsonMemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._facts: dict[str, MemoryFact] = {}
        self._load()

    def remember(self, key: str, value: str, text: str) -> None:
        fact = MemoryFact(
            key=key,
            value=value,
            text=text,
        )
        self._facts[key] = fact
        self._save()

    def get(self, key: str) -> MemoryFact | None:
        return self._facts.get(key)

    def search(self, query: str, limit: int = 5) -> list[MemoryFact]:
        query_terms = self._terms(query)
        scored: list[tuple[int, MemoryFact]] = []

        for fact in self._facts.values():
            fact_terms = self._terms(f"{fact.key} {fact.value} {fact.text}")
            score = len(query_terms & fact_terms)
            if score:
                scored.append((score, fact))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [fact for _, fact in scored[:limit]]

    def all(self) -> list[MemoryFact]:
        return list(self._facts.values())

    def _load(self) -> None:
        if not self.path.exists():
            return

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(raw, list):
            return

        for item in raw:
            if not isinstance(item, dict):
                continue

            try:
                fact = MemoryFact(
                    key=str(item["key"]),
                    value=str(item["value"]),
                    text=str(item["text"]),
                )
            except KeyError:
                continue

            self._facts[fact.key] = fact

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [fact.model_dump() for fact in self._facts.values()]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _terms(self, text: str) -> set[str]:
        return {
            term.strip(".,!?;:()[]{}\"'").lower()
            for term in text.split()
            if term.strip(".,!?;:()[]{}\"'")
        }
