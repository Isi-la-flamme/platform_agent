from typing import Any, cast

from groq import AsyncGroq

from src.domain.protocols.llm_provider import LLMProvider
from src.domain.protocols.logger import LoggerProtocol


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, logger: LoggerProtocol) -> None:
        self.client = AsyncGroq(api_key=api_key)
        self.model = model
        self.logger = logger

    async def generate(self, prompt: str) -> str:
        self.logger.debug("Groq generate called")

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.choices[0].message.content or ""

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.logger.debug("Groq chat called")

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, messages),
        )

        return response.choices[0].message.content or ""

    async def stream(self, messages: list[dict[str, str]]) -> Any:
        self.logger.debug("Groq stream called")

        return await self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, messages),
            stream=True,
        )
