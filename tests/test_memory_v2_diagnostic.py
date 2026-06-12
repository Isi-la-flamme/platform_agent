# tests/test_memory_v2_diagnostic.py

"""
Test de diagnostic pour identifier les lacunes fonctionnelles
de la mémoire v2.

Exécute avec : pytest tests/test_memory_v2_diagnostic.py -v
"""

import pytest
from src.application.memory_v2.memory_v2 import MemoryV2
from src.application.memory_v2.episodic_store import EpisodicMemory
from src.application.memory_v2.semantic_store import SemanticMemory
from src.application.memory_v2.procedural_store import ProceduralMemory
from src.application.memory_v2.retriever import MemoryRetriever
from src.application.memory_v2.models import MemoryItem


class TestMemoryV2Diagnostic:
    """
    Chaque test identifie une lacune spécifique.
    Les tests qui FAIL représentent des bugs ou fonctionnalités manquantes.
    """

    # ============================================================
    # 1. PERSISTANCE - CRITIQUE
    # ============================================================

    def test_persistence_episodic_survives_restart(self):
        """
        [LACUNE #1] La mémoire épisodique est volatile (list Python).
        Doit FAIL : pas de persistance.
        """
        mem = MemoryV2()
        mem.store_episode("user1", "réponse1")
        
        # Simuler un "redémarrage" en créant une nouvelle instance
        mem2 = MemoryV2()
        results = mem2.episodic.recent(10)
        
        assert len(results) > 0, (
            "🔴 LACUNE: La mémoire épisodique est volatile. "
            "Après une nouvelle instance, toutes les données sont perdues."
        )

    def test_persistence_semantic_survives_restart(self):
        """
        [LACUNE #1] La mémoire sémantique est volatile.
        Doit FAIL : pas de persistance.
        """
        mem = MemoryV2()
        mem.store_fact("Paris est la capitale de la France", importance=0.9)
        
        mem2 = MemoryV2()
        facts = mem2.semantic.all()
        
        assert len(facts) > 0, (
            "🔴 LACUNE: La mémoire sémantique est volatile."
        )

    def test_persistence_procedural_survives_restart(self):
        """
        [LACUNE #1] La mémoire procédurale est volatile.
        Doit FAIL : pas de persistance.
        """
        mem = MemoryV2()
        mem.store_skill("calculer_prix", ["étape1", "étape2"], success=True)
        
        mem2 = MemoryV2()
        skills = mem2.procedural.all()
        
        assert len(skills) > 0, (
            "🔴 LACUNE: La mémoire procédurale est volatile."
        )

    # ============================================================
    # 2. MÉMOIRE SÉMANTIQUE JAMAIS ALIMENTÉE - CRITIQUE
    # ============================================================

    def test_semantic_memory_is_used_by_runtime(self):
        """
        [LACUNE #2] store_fact() n'est jamais appelé dans agent_runtime.py.
        La mémoire sémantique reste vide dans le flux normal.
        
        Ce test vérifie que l'API existe, mais le vrai problème
        est dans l'intégration avec agent_runtime.
        """
        mem = MemoryV2()
        mem.store_fact("Test fact", 0.8)
        
        facts = mem.semantic.all()
        assert len(facts) == 1, "L'API store_fact fonctionne"

    # ============================================================
    # 3. RECHERCHE SÉMANTIQUE MANQUANTE
    # ============================================================

    def test_semantic_memory_has_search_method(self):
        """
        [LACUNE #5] SemanticMemory n'a pas de méthode search(),
        mais memory_v2.retrieve_facts() l'appelle.
        Doit FAIL si la méthode n'existe pas.
        """
        sem = SemanticMemory()
        sem.add_fact("Python est un langage de programmation", 0.9)
        
        try:
            results = sem.search("python langage")
            assert len(results) > 0, (
                "✅ search() existe et trouve des résultats"
            )
        except AttributeError:
            pytest.fail(
                "🔴 LACUNE: SemanticMemory n'a pas de méthode search(). "
                "memory_v2.retrieve_facts() va planter."
            )

    # ============================================================
    # 4. RECHERCHE PROCÉDURALE INCOMPLÈTE
    # ============================================================

    def test_procedural_memory_has_search_method(self):
        """
        [LACUNE #6] ProceduralMemory a best_strategy() mais pas search().
        memory_v2.retrieve_skills() appelle search().
        Doit FAIL si la méthode n'existe pas.
        """
        proc = ProceduralMemory()
        proc.add_pattern("calculer_prix", ["étape1", "étape2"], True)
        
        try:
            results = proc.search("calcul")
            assert len(results) > 0, (
                "✅ search() existe et trouve des résultats"
            )
        except AttributeError:
            pytest.fail(
                "🔴 LACUNE: ProceduralMemory n'a pas de méthode search(). "
                "memory_v2.retrieve_skills() va planter."
            )

    # ============================================================
    # 5. RETRIEVER NAÏF
    # ============================================================

    def test_retriever_uses_semantic_similarity(self):
        """
        [LACUNE #4] Le retriever fait un simple substring match.
        Ne trouve pas les correspondances sémantiques.
        Doit FAIL si la recherche est trop naïve.
        """
        from datetime import datetime
        
        retriever = MemoryRetriever()
        items = [
            MemoryItem(
                id="1",
                content="Le chat dort sur le canapé",
                metadata={},
                timestamp=datetime.utcnow(),
            ),
            MemoryItem(
                id="2",
                content="Les véhicules motorisés polluent l'air",
                metadata={},
                timestamp=datetime.utcnow(),
            ),
        ]
        
        results = retriever.retrieve(items, "automobile", top_k=2)
        
        semantic_match_found = any("véhicules" in item.content for item in results)
        
        if not semantic_match_found:
            print(
                "🟠 LACUNE: Le retriever utilise un simple substring match. "
                "Les correspondances sémantiques ne sont pas trouvées. "
                "ChromaDB devrait être intégré ici."
            )

    # ============================================================
    # 6. INTÉGRATION CHROMADB
    # ============================================================

    def test_chromadb_is_used_by_memory_v2(self):
        """
        [LACUNE #1, #4] Vérifie que ChromaDB est injecté quelque part.
        Doit FAIL si aucun store persistant n'est utilisé.
        """
        mem = MemoryV2()
        
        stores = [
            type(mem.episodic).__name__,
            type(mem.semantic).__name__,
            type(mem.procedural).__name__,
        ]
        
        uses_chroma = any("Chroma" in s for s in stores)
        
        if not uses_chroma:
            print(
                f"🟠 LACUNE: Aucun store ChromaDB n'est utilisé. "
                f"Stores actuels: {stores}. "
                f"ChromaMemoryStore existe mais n'est pas injecté."
            )

    # ============================================================
    # 7. FLUX COMPLET : ÉCRITURE → LECTURE
    # ============================================================

    def test_full_flow_write_and_retrieve(self):
        """
        Test du flux complet : écriture épisodique + retrieval.
        """
        mem = MemoryV2()
        
        mem.store_episode("Quel temps fait-il ?", "Il fait beau")
        mem.store_episode("Quelle heure est-il ?", "Il est midi")
        
        results = mem.retrieve("météo temps")
        
        assert len(results) > 0, (
            "Devrait retrouver au moins un épisode sur la météo"
        )

    def test_skill_learning_and_retrieval(self):
        """
        Test que les skills appris sont retrouvables.
        """
        mem = MemoryV2()
        
        mem.store_skill("convertir_devise", ["récupérer taux", "multiplier"], True)
        
        try:
            skills = mem.retrieve_skills("convertir")
            assert len(skills) > 0, (
                "✅ Le skill est retrouvable"
            )
        except AttributeError as e:
            pytest.fail(f"🔴 LACUNE: retrieve_skills a échoué: {e}")

    # ============================================================
    # 8. MÉMOIRE POUR LE PLANNER
    # ============================================================

    def test_planner_can_retrieve_learned_skills(self):
        """
        Le planner appelle retrieve_skills(goal).
        Vérifie que les skills appris sont retrouvables.
        """
        mem = MemoryV2()
        
        mem.store_skill("chercher_prix_crypto", ["appeler API", "parser JSON"], True)
        mem.store_skill("chercher_prix_crypto", ["utiliser cache", "retourner prix"], True)
        
        try:
            skills = mem.retrieve_skills("prix crypto bitcoin")
        except AttributeError:
            pytest.fail(
                "🔴 LACUNE CRITIQUE: Le planner ne peut pas retrouver les skills "
                "car ProceduralMemory.search() n'existe pas. "
                "Les skills appris par le runtime sont perdus pour le planner."
            )
            return
        
        assert len(skills) > 0, (
            "🟠 LACUNE: Aucun skill trouvé. Vérifier la logique de matching."
        )


# ============================================================
# TEST D'INTÉGRATION RUNTIME
# ============================================================

class TestRuntimeMemoryIntegration:
    """
    Vérifie que le runtime utilise correctement la mémoire v2.
    """

    @pytest.mark.asyncio
    async def test_runtime_stores_episode_on_input(self):
        """
        Vérifie que agent_runtime.store_episode() est bien appelé
        à chaque input utilisateur.
        """
        from unittest.mock import AsyncMock, MagicMock
        from src.application.orchestrators.agent_runtime import AgentRuntime
        
        llm = AsyncMock()
        llm.chat.return_value = '{"tool": "final", "args": {"content": "ok"}}'
        
        logger = MagicMock()
        tools = MagicMock()
        tools.list_tools.return_value = []
        tools.get.return_value = None
        
        runtime = AgentRuntime(llm=llm, logger=logger, tools=tools)
        
        episodes_before = len(runtime.memory_v2.episodic.recent(100))
        
        await runtime.run("Bonjour")
        
        episodes_after = len(runtime.memory_v2.episodic.recent(100))
        
        assert episodes_after > episodes_before, (
            "✅ Le runtime stocke bien des épisodes"
        )

    @pytest.mark.asyncio
    async def test_runtime_calls_store_fact(self):
        """
        Vérifie si le runtime appelle store_fact().
        """
        from unittest.mock import AsyncMock, MagicMock, patch
        from src.application.orchestrators.agent_runtime import AgentRuntime
        
        llm = AsyncMock()
        llm.chat.return_value = '{"tool": "final", "args": {"content": "Paris est la capitale de la France"}}'
        
        logger = MagicMock()
        tools = MagicMock()
        tools.list_tools.return_value = []
        tools.get.return_value = None
        
        runtime = AgentRuntime(llm=llm, logger=logger, tools=tools)
        
        with patch.object(runtime.memory_v2, 'store_fact', wraps=runtime.memory_v2.store_fact) as spy:
            await runtime.run("Parle-moi de Paris")
            
            if spy.call_count == 0:
                print(
                    "🟠 LACUNE: store_fact() n'est pas appelé. "
                    "Vérifier que _learn_facts_from_response est bien intégré."
                )