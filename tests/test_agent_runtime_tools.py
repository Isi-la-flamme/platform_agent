from typing import Any

import pytest

from src.application.orchestrators.agent_runtime import AgentRuntime
from src.domain.protocols.logger import LoggerProtocol
from src.infrastructure.tools.calculator_tool import CalculatorTool
from src.infrastructure.tools.echo_tool import EchoTool
from src.infrastructure.tools.text_stats_tool import TextStatsTool
from src.infrastructure.tools.tool_registry import ToolRegistry


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.messages: list[list[dict[str, str]]] = []

    async def generate(self, prompt: str) -> str:
        return prompt

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.messages.append(messages)
        if not self.responses:
            return '{"tool":"final","args":{"content":"fallback"}}'
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


def build_runtime(responses: list[str]) -> AgentRuntime:
    registry = ToolRegistry()
    registry.register(EchoTool())
    return AgentRuntime(FakeLLM(responses), NullLogger(), registry)


def build_runtime_with_utilities(responses: list[str]) -> AgentRuntime:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(CalculatorTool())
    registry.register(TextStatsTool())
    return AgentRuntime(FakeLLM(responses), NullLogger(), registry)


@pytest.mark.asyncio
async def test_extracts_json_when_model_wraps_it_in_text() -> None:
    runtime = build_runtime(
        [
            'Voici la reponse: {"tool":"final","args":{"content":"Bonjour"}}',
        ]
    )

    response = await runtime.run("salut")

    assert response == "Bonjour"


@pytest.mark.asyncio
async def test_echo_returns_directly_when_requested() -> None:
    runtime = build_runtime(
        [
            '{"tool":"echo","args":{"text":"bonjour agent"}}',
        ]
    )

    response = await runtime.run("repete exactement: bonjour agent")

    assert response == "bonjour agent"


@pytest.mark.asyncio
async def test_echo_args_are_filled_from_user_input_when_missing() -> None:
    runtime = build_runtime(
        [
            '{"tool":"echo","args":{}}',
        ]
    )

    response = await runtime.run("echo: test 123")

    assert response == "test 123"


@pytest.mark.asyncio
async def test_unknown_tool_is_converted_to_final_response() -> None:
    runtime = build_runtime([])

    response = await runtime.run("utilise le tool helloworld")

    assert response == (
        'Je n\'ai pas acces au tool "helloworld". Tools disponibles: echo.'
    )


@pytest.mark.asyncio
async def test_echo_is_rejected_for_plain_conversation() -> None:
    runtime = build_runtime(
        [
            '{"tool":"echo","args":{"text":"salut"}}',
            '{"tool":"final","args":{"content":"Salut !"}}',
        ]
    )

    response = await runtime.run("salut")

    assert response == "Salut !"


@pytest.mark.asyncio
async def test_low_quality_final_marker_is_retried() -> None:
    runtime = build_runtime(
        [
            '{"tool":"final","args":{"content":"final"}}',
            '{"tool":"final","args":{"content":"Salut, a bientot !"}}',
        ]
    )

    response = await runtime.run("salut et bye")

    assert response == "Salut, a bientot !"


@pytest.mark.asyncio
async def test_calculator_returns_directly() -> None:
    runtime = build_runtime_with_utilities(
        [
            '{"tool":"calculator","args":{"expression":"2 + 2 * 3"}}',
        ]
    )

    response = await runtime.run("calcule 2 + 2 * 3")

    assert response == "8"


@pytest.mark.asyncio
async def test_text_stats_fills_missing_text_from_user_input() -> None:
    runtime = build_runtime_with_utilities(
        [
            '{"tool":"text_stats","args":{}}',
        ]
    )

    response = await runtime.run("compte: bonjour agent")

    assert response == "Caracteres: 13; Mots: 2; Lignes: 1"
