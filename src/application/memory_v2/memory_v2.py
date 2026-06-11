from typing import Any
import json

from .episodic_store import EpisodicMemory
from .semantic_store import SemanticMemory
from .procedural_store import ProceduralMemory
from .retriever import MemoryRetriever


class MemoryV2:
    def __init__(self):
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()
        self.retriever = MemoryRetriever()

    # =========================
    # WRITE API (FIXED)
    # =========================

    def store_episode(self, user_input: str, output: Any = None) -> None:
        """
        Accepte str, dict, list, etc.
        Toujours sérialisé proprement pour éviter crash futur.
        """
        if not isinstance(output, str):
            try:
                output = json.dumps(output, ensure_ascii=False)
            except Exception:
                output = str(output)

        self.episodic.add(user_input, output)

    def store_fact(self, fact: str, importance: float = 0.5) -> None:
        self.semantic.add_fact(fact, importance)

    def store_skill(self, task: str, steps: list[str], success: bool) -> None:
        self.procedural.add_pattern(task, steps, success)

    # =========================
    # READ API (RAG CORE)
    # =========================

    def retrieve(self, query: str):
        episodic = self.episodic.recent(20)
        semantic = self.semantic.all()
        procedural = self.procedural.all()

        pool = episodic + semantic + procedural
        return self.retriever.retrieve(pool, query)

    # =========================
    # HELPERS
    # =========================

    def retrieve_skills(self, query: str):
        return self.procedural.search(query)

    def retrieve_facts(self, query: str):
        return self.semantic.search(query)

    def clear(self):
        self.episodic.clear()
        self.semantic.clear()
        self.procedural.clear()