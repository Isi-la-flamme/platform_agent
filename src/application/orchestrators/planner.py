from src.domain.protocols.tool import Tool, ToolProvider
from src.domain.protocols.memory import LongTermMemory

class Planner:
    """Responsable de la construction du contexte et des instructions (System Prompt)."""
    
    def __init__(self, template: str) -> None:
        self.template = template

    def build_system_prompt(
        self, 
        tools: ToolProvider, 
        memory: LongTermMemory | None, 
        user_input: str
    ) -> str:
        tool_context = self._format_tools(tools.list_tools())
        memory_context = self._format_memory(memory, user_input)

        return (
            self.template
            .replace("__TOOLS__", tool_context)
            .replace("__MEMORY__", memory_context)
        )

    def _format_tools(self, tools: list[Tool]) -> str:
        if not tools:
            return "- aucun tool disponible"
        
        lines = []
        for t in tools:
            args = ", ".join([f"{k}: {v}" for k, v in t.args_schema.items()]) or "aucun"
            behavior = "retour direct" if t.return_direct else "observation"
            lines.append(f"- {t.name}: {t.description} Args: {args}. Mode: {behavior}.")
        return "\n".join(lines)

    def _format_memory(self, memory: LongTermMemory | None, user_input: str) -> str:
        if not memory:
            return "- aucune memoire long terme disponible"
        
        facts = memory.search(user_input)
        if not facts:
            facts = memory.all()[:5]
            
        if not facts:
            return "- aucun fait memorise"
            
        return "\n".join(f"- {f.text}" for f in facts)