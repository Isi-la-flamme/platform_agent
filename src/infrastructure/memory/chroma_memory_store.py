import chromadb
from typing import List, Optional
from src.domain.entities.memory import MemoryFact

class ChromaMemoryStore:
    """
    Implémentation d'une mémoire vectorielle utilisant ChromaDB.
    Permet une recherche sémantique des faits passés pour une meilleure pertinence.
    """
    def __init__(self, path: str = "./data/chroma_db", collection_name: str = "agent_memory"):
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def remember(self, key: str, value: str, text: str) -> None:
        """Persiste ou met à jour un fait avec indexation vectorielle."""
        self.collection.upsert(
            ids=[key],
            documents=[text],
            metadatas=[{"key": key, "value": value}]
        )

    def get(self, key: str) -> Optional[MemoryFact]:
        """Récupère un fait spécifique par sa clé."""
        result = self.collection.get(ids=[key])
        if not result["ids"]:
            return None
        return MemoryFact(
            key=result["ids"][0],
            value=result["metadatas"][0]["value"],
            text=result["documents"][0]
        )

    def search(self, query: str, limit: int = 5) -> List[MemoryFact]:
        """Effectue une recherche sémantique (similarité) sur les faits mémorisés."""
        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        facts = []
        if not results["ids"] or not results["ids"][0]:
            return facts
            
        for i in range(len(results["ids"][0])):
            facts.append(MemoryFact(
                key=results["ids"][0][i],
                value=results["metadatas"][0][i]["value"],
                text=results["documents"][0][i]
            ))
        return facts

    def all(self) -> List[MemoryFact]:
        """Récupère tous les faits mémorisés (utile pour le contexte global)."""
        results = self.collection.get()
        facts = []
        for i in range(len(results["ids"])):
            facts.append(MemoryFact(
                key=results["ids"][i],
                value=results["metadatas"][i]["value"],
                text=results["documents"][i]
            ))
        return facts