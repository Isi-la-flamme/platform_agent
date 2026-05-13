from typing import Any


class EchoTool:
    name = "echo"
    description = (
        "Retourne exactement le texte fourni. A utiliser seulement si "
        "l'utilisateur demande explicitement de repeter ou d'echo."
    )

    async def execute(self, **kwargs: Any) -> str:
        return str(kwargs.get("text", ""))
