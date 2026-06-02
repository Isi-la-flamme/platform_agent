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

        try:
            if isinstance(parsed, dict):
                return ToolCall.model_validate(parsed)
        except Exception as e:
            self.logger.warning(f"Validation Pydantic échouée: {e}")

        # Fallback sécurisé en cas d'échec de validation ou JSON corrompu
        content = str(parsed) if parsed is not None else raw.strip()
        return ToolCall(tool="final", args={"content": content}, plan=None)

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

        # 3. Recherche du premier objet ou chaîne dans le texte
        for index, character in enumerate(text):
            if character not in ('{', '"'):
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
                if isinstance(value, dict | str):
                    return value
            except json.JSONDecodeError:
                continue
        return raw