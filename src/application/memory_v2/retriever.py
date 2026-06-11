# retriever.py
from .models import MemoryItem


class MemoryRetriever:
    def score(self, item: MemoryItem, query: str) -> float:
        q = query.lower()
        c = item.content.lower()

        similarity = 1.0 if q in c else 0.2
        recency = 1 / (1 + (item.access_count * 0.1))
        importance = item.importance

        return 0.5 * similarity + 0.3 * recency + 0.2 * importance

    def retrieve(self, items: list[MemoryItem], query: str, top_k: int = 5):
        ranked = sorted(items, key=lambda x: self.score(x, query), reverse=True)

        for item in ranked:
            item.access_count += 1

        return ranked[:top_k]