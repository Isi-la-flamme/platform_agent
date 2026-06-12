# retriever.py

from .models import MemoryItem


class MemoryRetriever:
    def score(self, item: MemoryItem, query: str) -> float:
        q = query.lower()
        c = item.content.lower()

        # Score de correspondance par mots
        query_terms = set(q.split())
        content_terms = set(c.split())
        
        if q in c:
            similarity = 1.0
        elif query_terms & content_terms:
            overlap = len(query_terms & content_terms)
            similarity = 0.3 + (0.5 * overlap / len(query_terms))
        else:
            similarity = 0.1

        recency = 1 / (1 + (item.access_count * 0.1))
        importance = item.importance

        return 0.5 * similarity + 0.3 * recency + 0.2 * importance

    def retrieve(self, items: list[MemoryItem], query: str, top_k: int = 5):
        # Si items viennent de ChromaDB, ils sont déjà triés par similarité vectorielle
        # On applique juste le boosting recency + importance
        ranked = sorted(items, key=lambda x: self.score(x, query), reverse=True)

        for item in ranked:
            item.access_count += 1

        return ranked[:top_k]