from src.domain.protocols.tool import Tool, ToolProvider
from src.domain.protocols.memory import LongTermMemory
from src.domain.entities.plan import Plan

SYSTEM_PROMPT_TEMPLATE = """
Tu es un agent logiciel autonome capable de planification complexe.

PLAN ACTUEL :
__PLAN__

MEMOIRE LONG TERME :
__MEMORY__

TOOLS DISPONIBLES :
__TOOLS__

REGLES ABSOLUES :
- Tu dois repondre uniquement en JSON valide.
- Pas de markdown hors JSON.
- Si la tâche est complexe, commence par définir ou mettre à jour un "plan" dans ta réponse.
- Si aucun tool ne correspond, utilise "final".

FORMAT :
{"tool": "nom", "args": {...}, "plan": {"goal": "...", "tasks": [{"description": "...", "status": "pending"}]}}
"""

class PromptManager:
    """Responsable de la génération des prompts et du formatage du contexte."""

    def build_system_prompt(self, tools: ToolProvider, memory: LongTermMemory | None, user_input: str, plan: Plan | None = None) -> str:
        tool_context = self._format_tools(tools.list_tools())
        memory_context = self._format_memory(memory, user_input)
        plan_context = self._format_plan(plan)

        return (
            SYSTEM_PROMPT_TEMPLATE
            .replace("__TOOLS__", tool_context)
            .replace("__MEMORY__", memory_context)
            .replace("__PLAN__", plan_context)
        )

    def _format_tools(self, tools: list[Tool]) -> str:
        if not tools:
            return "- aucun tool disponible"
        
        lines = []
        for t in tools:
            args = ", ".join([f"{k}: {v}" for k, v in t.args_schema.items()]) or "aucun"
            mode = "retour direct" if t.return_direct else "observation"
            lines.append(f"- {t.name}: {t.description} Args: {args}. Mode: {mode}.")
        return "\n".join(lines)

    def _format_memory(self, memory: LongTermMemory | None, user_input: str) -> str:
        if not memory:
            return "- aucune mémoire disponible"
        
        facts = memory.search(user_input)
        if not facts:
            facts = memory.all()[:5]
            
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