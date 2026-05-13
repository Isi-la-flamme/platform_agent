from typing import Protocol, Any


class Tool(Protocol):
    name: str
    description: str

    async def execute(self, **kwargs) -> Any:
        ...