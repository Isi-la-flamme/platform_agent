# memory_v2.py

from typing import Any
import json

from .episodic_store import EpisodicMemory
from .semantic_store import SemanticMemory
from .procedural_store import ProceduralMemory
from .retriever import MemoryRetriever
from src.infrastructure.memory.chroma_memory_store import ChromaMemoryStore


class MemoryV2:
    def __init__(self, persist_path: str = "./data/chroma_db"):
        # Stores persistants
        self.episodic_store = ChromaMemoryStore(
            path=persist_path,
            collection_name="episodic_memory"
        )
        self.semantic_store = ChromaMemoryStore(
            path=persist_path,
            collection_name="semantic_memory"
        )
        self.procedural_store = ChromaMemoryStore(
            path=persist_path,
            collection_name="procedural_memory"
        )

        # Stores in-memory pour le cache rapide
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()
        self.retriever = MemoryRetriever()

    # =========================
    # WRITE API
    # =========================

    def store_episode(self, user_input: str, output: Any = None) -> None:
        if not isinstance(output, str):
            try:
                output = json.dumps(output, ensure_ascii=False)
            except Exception:
                output = str(output)

        # Persistant
        self.episodic_store.remember(
            key=user_input,
            value=output,
            text=f"Q:{user_input} | A:{output}"
        )
        # Cache rapide
        self.episodic.add(user_input, output)

    def store_fact(self, fact: str, importance: float = 0.5) -> None:
        # Persistant
        self.semantic_store.remember(
            key=fact,
            value=str(importance),
            text=fact
        )
        # Cache rapide
        self.semantic.add_fact(fact, importance)

    def store_skill(self, task: str, steps: list[str], success: bool) -> None:
        # Persistant
        self.procedural_store.remember(
            key=task,
            value=json.dumps({"steps": steps, "success": success}),
            text=f"Tâche: {task} | Étapes: {', '.join(steps)}"
        )
        # Cache rapide
        self.procedural.add_pattern(task, steps, success)

    # =========================
    # READ API (RAG CORE)
    # =========================

    def retrieve(self, query: str):
        # Chercher dans ChromaDB (vectoriel)
        episodic_results = self.episodic_store.search(query, limit=10)
        semantic_results = self.semantic_store.search(query, limit=10)
        procedural_results = self.procedural_store.search(query, limit=10)

        # Fallback sur le cache in-memory
        if not episodic_results:
            episodic_results = self.episodic.recent(20)
        if not semantic_results:
            semantic_results = self.semantic.all()
        if not procedural_results:
            procedural_results = self.procedural.all()

        pool = episodic_results + semantic_results + procedural_results
        return self.retriever.retrieve(pool, query)

    # =========================
    # HELPERS
    # =========================

    def retrieve_skills(self, query: str):
        # Essayer ChromaDB d'abord
        chroma_results = self.procedural_store.search(query, limit=10)
        if chroma_results:
            return chroma_results
        return self.procedural.search(query)

    def retrieve_facts(self, query: str):
        # Essayer ChromaDB d'abord
        chroma_results = self.semantic_store.search(query, limit=10)
        if chroma_results:
            return chroma_results
        return self.semantic.search(query)

    def clear(self):
        self.episodic.clear()
        self.semantic.clear()
        self.procedural.clear()