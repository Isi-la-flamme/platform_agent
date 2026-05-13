from pathlib import Path
from typing import Any

import pytest

from src.application.orchestrators.agent_runtime import AgentRuntime
from src.domain.protocols.logger import LoggerProtocol
from src.infrastructure.memory.json_memory_store import JsonMemoryStore
from src.infrastructure.tools.echo_tool import EchoTool
from src.infrastructure.tools.tool_registry import ToolRegistry


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses

    async def generate(self, prompt: str) -> str:
        return prompt

    async def chat(self, messages: list[dict[str, str]]) -> str:
        if not self.responses:
            return '{"tool":"final","args":{"content":"ok"}}'
        return self.responses.pop(0)

    async def stream(self, messages: list[dict[str, str]]) -> Any:
        return None

    async def close(self) -> None:
        return None


class NullLogger(LoggerProtocol):
    def debug(self, message: str, *args: object) -> None:
        pass

    def info(self, message: str, *args: object) -> None:
        pass

    def warning(self, message: str, *args: object) -> None:
        pass

    def error(self, message: str, *args: object) -> None:
        pass

    def critical(self, message: str, *args: object) -> None:
        pass


def build_runtime(memory: JsonMemoryStore) -> AgentRuntime:
    registry = ToolRegistry()
    registry.register(EchoTool())
    return AgentRuntime(FakeLLM([]), NullLogger(), registry, memory=memory)


def test_json_memory_store_persists_facts(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"
    memory = JsonMemoryStore(path)

    memory.remember("user.name", "Ada", "Le nom de l'utilisateur est Ada.")

    reloaded = JsonMemoryStore(path)
    fact = reloaded.get("user.name")

    assert fact is not None
    assert fact.value == "Ada"
    assert fact.text == "Le nom de l'utilisateur est Ada."


@pytest.mark.asyncio
async def test_runtime_remembers_user_name_after_short_term_reset(
    tmp_path: Path,
) -> None:
    memory = JsonMemoryStore(tmp_path / "memory.json")
    runtime = build_runtime(memory)

    await runtime.run("mon nom est Ada")
    runtime.reset()
    response = await runtime.run("quel est mon nom ?")

    assert response == "Ton nom est Ada."
