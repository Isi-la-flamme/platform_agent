from src.domain.protocols.tool import Tool, ToolProvider
from src.domain.protocols.memory import LongTermMemory

SYSTEM_PROMPT_TEMPLATE = """
Tu es un agent logiciel.

MEMOIRE LONG TERME :
__MEMORY__

TOOLS DISPONIBLES :
__TOOLS__

REGLES ABSOLUES :
- Tu dois repondre uniquement en JSON valide.
- Pas de markdown hors JSON.
- Si aucun tool ne correspond, utilise "final".

FORMAT :
{"tool": "nom", "args": {...}} ou {"tool": "final", "args": {"content": "..."}}
"""

class PromptManager:
    """Responsable de la génération des prompts et du formatage du contexte."""

    def build_system_prompt(self, tools: ToolProvider, memory: LongTermMemory | None, user_input: str) -> str:
        tool_context = self._format_tools(tools.list_tools())
        memory_context = self._format_memory(memory, user_input)

        return (
            SYSTEM_PROMPT_TEMPLATE
            .replace("__TOOLS__", tool_context)
            .replace("__MEMORY__", memory_context)
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