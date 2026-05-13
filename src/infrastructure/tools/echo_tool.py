from src.domain.protocols.tool import Tool


class EchoTool:
    name = "echo"
    description = "Retourne exactement ce que l'utilisateur envoie"

    async def execute(self, **kwargs):
        return kwargs.get("text", "")