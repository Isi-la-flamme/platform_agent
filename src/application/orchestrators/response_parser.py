import json
from typing import Any

from src.domain.entities.tool_call import ToolCall
from src.domain.protocols.logger import LoggerProtocol


class ResponseParser:
    """Responsable de l'extraction et de la validation des réponses du LLM."""
    
    def __init__(self, logger: LoggerProtocol) -> None:
        self.logger = logger

    def parse_action(self, raw: str) -> ToolCall:
        """Parse une chaîne brute en un ToolCall validé."""
        parsed = self._extract_json(raw)

        if isinstance(parsed, dict):
            # Extraction et log de la pensée de l'agent pour audit avant validation
            thought = parsed.pop("thought", None) or parsed.pop("reasoning", None)
            if thought:
                self.logger.info(f"[AGENT-REASONING] {thought}")

        try:
            if isinstance(parsed, dict):
                normalized = self._normalize_common_variants(parsed)
                if normalized:
                    return normalized
                parsed = self._normalize_plan_statuses(parsed)
                return ToolCall.model_validate(parsed)
        except Exception as e:
            self.logger.warning(f"Validation Pydantic échouée: {e}")

        # Fallback sécurisé en cas d'échec de validation ou JSON corrompu
        content = raw.strip()
        return ToolCall(tool="final", args={"content": content}, plan=None)

    def _normalize_common_variants(self, parsed: dict[str, Any]) -> ToolCall | None:
        """
        Gère les cas où le LLM omet des champs obligatoires (tool, args)
        ou renvoie une structure de plan directement à la racine.
        """
        if "tool" in parsed:
            if "args" not in parsed:
                parsed["args"] = {}
            return None  # On laisse le flux normal pour la validation Pydantic

        # Si 'tool' est absent, on interprète la réponse comme une réponse finale
        response = str(parsed.get("response", "")).strip().lower()
        content = (
            parsed.get("text") or 
            parsed.get("content") or 
            parsed.get("message") or 
            "Analyse terminée (format corrigé)."
        )

        # Détection du plan si l'objet racine ressemble à un plan (cas de votre erreur)
        plan_data = parsed.get("plan")
        if not plan_data and ("goal" in parsed or "tasks" in parsed):
            plan_data = parsed.copy()

        # Normalisation des statuts du plan s'il est présent
        if isinstance(plan_data, dict) and "tasks" in plan_data:
            temp_wrapper = {"plan": plan_data}
            self._normalize_plan_statuses(temp_wrapper)
            plan_data = temp_wrapper["plan"]

        return ToolCall(
            tool="final",
            args={"content": str(content)},
            plan=plan_data if isinstance(plan_data, dict) and "goal" in plan_data else None,
        )

    def _normalize_plan_statuses(self, parsed: dict[str, Any]) -> dict[str, Any]:
        plan = parsed.get("plan")
        if not isinstance(plan, dict):
            return parsed

        tasks = plan.get("tasks")
        if not isinstance(tasks, list):
            return parsed

        status_aliases = {
            "done": "completed",
            "finished": "completed",
            "complete": "completed",
            "success": "completed",
            "todo": "pending",
            "to_do": "pending",
            "doing": "in_progress",
            "in progress": "in_progress",
            "error": "failed",
            "failure": "failed",
        }
        for task in tasks:
            if not isinstance(task, dict):
                continue
            status = str(task.get("status", "")).strip().lower()
            if status in status_aliases:
                task["status"] = status_aliases[status]

        return parsed

    def _extract_json(self, raw: str) -> Any:
        """Logique d'extraction robuste (Markdown, texte entourant, etc)."""
        text = raw.strip()
        decoder = json.JSONDecoder()

        # 1. Tentative directe
        try:
            value, _ = decoder.raw_decode(text)
            return value
        except json.JSONDecodeError:
            pass

        # 2. Nettoyage blocs Markdown
        if text.startswith("```"):
            cleaned = text.strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                value, _ = decoder.raw_decode(cleaned)
                return value
            except json.JSONDecodeError:
                pass

        # 3. Recherche du premier objet JSON dans le texte.
        # Les chaines JSON seules ("plan", "tool", etc.) ne sont pas des
        # actions valides pour l'agent.
        for index, character in enumerate(text):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                continue
        return raw
