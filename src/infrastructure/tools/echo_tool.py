from typing import Any


class EchoTool:
    name = "echo"
    description = (
        "Retourne exactement le texte fourni. A utiliser seulement si "
        "l'utilisateur demande explicitement de repeter ou d'echo."
    )
    args_schema = {
        "text": "Texte exact a retourner.",
    }
    return_direct = True
    trigger_words: tuple[str, ...] = (
        "echo",
        "repete",
        "répète",
        "retourne exactement",
        "redis exactement",
    )

    async def execute(self, **kwargs: Any) -> str:
        return str(kwargs.get("text", ""))
