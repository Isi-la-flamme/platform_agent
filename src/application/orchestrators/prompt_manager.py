from src.domain.entities.plan import Plan
from src.domain.protocols.memory import LongTermMemory
from src.domain.protocols.tool import Tool, ToolProvider

SYSTEM_PROMPT_TEMPLATE = """
Tu es un agent logiciel autonome expert en résolution de problèmes via un cycle itératif de planification.

TON CYCLE DE TRAVAIL :
1. ANALYSE : Examine la requête utilisateur, l'historique et l'état du plan.
2. PLANIFICATION : Crée ou mets à jour ton 'plan' (Objectif global et liste de sous-tâches).
3. EXÉCUTION : Choisis et appelle l'outil le plus pertinent pour la sous-tâche actuelle.
4. RÉVISION : Analyse l'observation (résultat du tool), mets à jour le statut des tâches (pending|completed|failed) et décide de la prochaine action.

PLAN ACTUEL :
__PLAN__

MEMOIRE LONG TERME :
__MEMORY__

TOOLS DISPONIBLES :
__TOOLS__

HIERARCHIE DE PRIORITE DES OUTILS :
1. SPECIALISES : Utilise l'outil dédié (ex: crypto, calcul, date).
2. LOGIQUE : 'python_code' pour calculs/algorithmes.
3. RECHERCHE EXTERNE : N'utilise 'google_search' ou 'web_fetch' qu'en DERNIER RECOURS, uniquement si l'information est introuvable via les autres outils.

REGLES ABSOLUES :
- Tu dois repondre uniquement en JSON valide.
- Pas de markdown hors JSON.
- Tu DOIS mettre à jour le statut de tes tâches dans le champ 'plan' à CHAQUE réponse.
- INTENTION : Si l'utilisateur demande une action sur un fichier/dossier, l'outil 'file_crud' est prioritaire.
- Avant de choisir un outil, verifie si un outil plus specialise ne peut pas faire le travail.
- NE JAMAIS utiliser 'google_search' pour des calculs ou des cours de crypto si les outils dedies sont presents.
- Si l'objectif est atteint ou qu'aucun outil n'est nécessaire, utilise "final".
- AUTO-CORRECTION : Si l'observation d'un outil indique un echec, un acces refuse ou un resultat non pertinent, analyse l'erreur dans ton champ 'thought' et propose une approche alternative.

FORMAT :
{"thought": "Ta réflexion sur l'étape actuelle et le choix de l'outil", "tool": "nom", "args": {...}, "plan": {"goal": "...", "tasks": [{"description": "...", "status": "pending|in_progress|completed|failed"}]}}
"""

class PromptManager:
    """Responsable de la génération des prompts et du formatage du contexte."""

    def build_system_prompt(self, tools: ToolProvider, memory: LongTermMemory | None, user_input: str, plan: Plan | None = None) -> str:
        tool_context = self._format_tools(tools.list_tools(), user_input)
        memory_context = self._format_memory(memory, user_input)
        plan_context = self._format_plan(plan)

        return (
            SYSTEM_PROMPT_TEMPLATE
            .replace("__TOOLS__", tool_context)
            .replace("__MEMORY__", memory_context)
            .replace("__PLAN__", plan_context)
        )

    def _format_tools(self, tools: list[Tool], user_input: str = "") -> str:
        if not tools:
            return "- aucun tool disponible"
        
        lines = []
        normalized_input = user_input.lower()
        for t in tools:
            is_recommended = any(w in normalized_input for w in t.trigger_words) if t.trigger_words else False
            prefix = "[RECOMMANDÉ] " if is_recommended else ""
            args = ", ".join([f"{k}: {v}" for k, v in t.args_schema.items()]) or "aucun"
            mode = "retour direct" if t.return_direct else "observation"
            lines.append(f"- {prefix}{t.name}: {t.description} (Args: {args})")
        return "\n".join(lines)

    def _format_memory(self, memory: LongTermMemory | None, user_input: str) -> str:
        if not memory:
            return "- aucune mémoire disponible"
        
        facts = memory.search(user_input)
        if not facts:
            facts = memory.all()[:3] # Réduit de 5 à 3 pour gagner des tokens
            
        if not facts:
            return "- aucun fait mémorisé"
            
        return "\n".join(f"- {f.text}" for f in facts)

    def _format_plan(self, plan: Plan | None) -> str:
        if not plan or not plan.tasks:
            return "- Aucun plan actif. Définis-en un si la requête nécessite plusieurs étapes."
        
        res = [f"Objectif : {plan.goal}"]
        for i, task in enumerate(plan.tasks):
            status_icon = "✅" if task.status == "completed" else "⏳" if task.status == "in_progress" else "⚪"
            res.append(f"{i+1}. {status_icon} {task.description}")
        return "\n".join(res)
