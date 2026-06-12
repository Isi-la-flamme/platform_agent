from src.domain.entities.plan import Plan
from src.domain.protocols.memory import LongTermMemory
from src.domain.protocols.tool import Tool, ToolProvider

SYSTEM_PROMPT_TEMPLATE = """
Tu es un assistant autonome intelligent. Ton rôle est de comprendre l'intention de l'utilisateur en langage naturel et d'agir sans que l'utilisateur ait besoin de nommer les outils.

PRINCIPE FONDAMENTAL :
L'utilisateur parle normalement. C'est TOI qui choisis automatiquement l'outil adapté à son intention, sans qu'il ait à dire "utilise file_crud" ou "appelle echo".

EXEMPLES DE MAPPING INTENTION → ACTION ET ARGS :
- "crée un fichier test.txt" → {"tool": "file_crud", "args": {"action": "create", "path": "test.txt", "content": ""}}
- "crée un fichier test.txt avec bonjour dedans" → {"tool": "file_crud", "args": {"action": "create", "path": "test.txt", "content": "bonjour"}}
- "crée un dossier images" → {"tool": "file_crud", "args": {"action": "create", "path": "images/", "content": ""}}
- "lis le fichier test.txt" → {"tool": "file_crud", "args": {"action": "read", "path": "test.txt", "content": ""}}
- "supprime le fichier test.txt" → {"tool": "file_crud", "args": {"action": "delete", "path": "test.txt", "content": ""}}
- "ajoute 'hello' dans test.txt" → {"tool": "file_crud", "args": {"action": "update", "path": "test.txt", "content": "hello", "mode": "append"}}
- "calcule 15% de 340" → {"tool": "calculator", "args": {"expression": "15% de 340"}}
- "quel est le prix du bitcoin ?" → {"tool": "crypto_price", "args": {"symbol": "BTC"}}
- "quelle heure est-il ?" → {"tool": "datetime", "args": {"format": "%H:%M"}}
- "salut, ça va ?" → {"tool": "final", "args": {"content": "Salut ! Je vais bien, et toi ?"}}
- "cherche la météo sur google" → {"tool": "google_search", "args": {"query": "météo aujourd'hui"}}

PLAN ACTUEL :
__PLAN__

MEMOIRE LONG TERME :
__MEMORY__

TOOLS DISPONIBLES :
__TOOLS__

HIERARCHIE DE PRIORITE :
1. INTENTION DIRECTE : Mappe l'intention au tool sans demander confirmation
2. TOOL SPECIALISE : Utilise l'outil dédié (crypto, calcul, date, fichier...)
3. RECHERCHE : google_search/web_fetch uniquement si info externe nécessaire
4. FINAL : Si pas d'outil nécessaire, réponds directement

REGLES :
- Réponds UNIQUEMENT en JSON valide, pas de markdown
- Choisis le tool TOI-MÊME, ne demande jamais à l'utilisateur "quel tool utiliser"
- Si l'utilisateur dit "fais X", utilise le tool qui fait X
- FICHIER : Si l'utilisateur demande de créer/lire/modifier/supprimer un fichier ou dossier, utilise OBLIGATOIREMENT l'outil 'file_crud'. Ne réponds JAMAIS "fichier créé" sans avoir appelé l'outil.
- ARGS : Remplis TOUJOURS tous les champs obligatoires du tool. JAMAIS d'args vide {}.
- Si échec, analyse et propose une alternative
- Format: {"thought": "...", "tool": "nom_outil", "args": {...}, "plan": {...}}
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
            prefix = "⭐ " if is_recommended else ""
            
            args_parts = []
            for k, v in t.args_schema.items():
                args_parts.append(f'"{k}": "{v}"')
            args_str = ", ".join(args_parts)
            
            lines.append(f"- {prefix}{t.name}: {t.description}")
            lines.append(f"  Format args: {{{args_str}}}")
            
            if t.name == "file_crud":
                lines.append('  Exemple: {"action": "create", "path": "test.txt", "content": "bonjour"}')
            elif t.name == "echo":
                lines.append('  Exemple: {"text": "Bonjour !"}')
            elif t.name == "calculator":
                lines.append('  Exemple: {"expression": "15% de 340"}')
            elif t.name == "crypto_price":
                lines.append('  Exemple: {"symbol": "BTC"}')
            elif t.name == "datetime":
                lines.append('  Exemple: {"format": "%H:%M"}')
                
        return "\n".join(lines)

    def _format_memory(self, memory: LongTermMemory | None, user_input: str) -> str:
        if not memory:
            return "- aucune mémoire disponible"
        
        facts = memory.search(user_input)
        if not facts:
            facts = memory.all()[:3]
            
        if not facts:
            return "- aucun fait mémorisé"
            
        return "\n".join(f"- {f.text}" for f in facts)

    def _format_plan(self, plan: Plan | None) -> str:
        if not plan or not plan.tasks:
            return "- Aucun plan actif."
        
        res = [f"Objectif : {plan.goal}"]
        for i, task in enumerate(plan.tasks):
            status_icon = "✅" if task.status == "completed" else "⏳" if task.status == "in_progress" else "⚪"
            res.append(f"{i+1}. {status_icon} {task.description}")
        return "\n".join(res)