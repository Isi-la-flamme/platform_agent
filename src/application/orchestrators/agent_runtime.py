import json
from typing import Any

from src.domain.entities.agent import AgentState
from src.domain.entities.message import Message
from src.domain.protocols.llm_provider import LLMProvider
from src.domain.protocols.logger import LoggerProtocol
from src.domain.protocols.tool import ToolProvider

SYSTEM_PROMPT = """
Tu es un agent logiciel.

Tu peux :
- appeler des tools
- ou repondre directement
- discuter normalement avec l'utilisateur

TOOLS DISPONIBLES :
__TOOLS__

REGLE ABSOLUE :
Tu dois repondre uniquement en JSON valide.
Tu dois appeler uniquement un tool liste dans TOOLS DISPONIBLES.
Si aucun tool disponible ne correspond, utilise le tool "final".
Pour une salutation ou une conversation simple, utilise toujours "final".
N'utilise pas le tool "echo" sauf si l'utilisateur demande explicitement
de repeter, echo, ou retourner exactement un texte.

FORMAT 1 (appel tool) :
{
  "tool": "nom_du_tool",
  "args": { ... }
}

FORMAT 2 (reponse finale) :
{
  "tool": "final",
  "args": {
    "content": "reponse finale"
  }
}
"""


class AgentRuntime:
    MAX_MESSAGES = 10

    def __init__(
        self,
        llm: LLMProvider,
        logger: LoggerProtocol,
        tools: ToolProvider,
    ) -> None:
        self.llm = llm
        self.logger = logger
        self.tools = tools
        self.state = AgentState()

    def add_user_message(self, content: str) -> None:
        self.state.messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        self.state.messages.append(Message(role="assistant", content=content))

    def _trim_history(self) -> None:
        self.state.messages = self.state.messages[-self.MAX_MESSAGES :]

    def _build_system_prompt(self) -> str:
        tools = self.tools.list_tools()

        if not tools:
            tool_context = "- aucun tool disponible"
        else:
            tool_context = "\n".join(
                f"- {tool.name}: {tool.description}" for tool in tools
            )

        return SYSTEM_PROMPT.replace("__TOOLS__", tool_context)

    def _build_messages(self, system_prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            *[
                {"role": message.role, "content": message.content}
                for message in self.state.messages
            ],
        ]

    def _parse_action(self, raw: str) -> dict[str, Any]:
        raw = raw.strip()

        if raw.startswith("{") or raw.startswith('"'):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, str):
                    return {
                        "tool": "final",
                        "args": {
                            "content": parsed,
                        },
                    }

        return {
            "tool": "final",
            "args": {
                "content": raw,
            },
        }

    def _final_content(self, action: dict[str, Any]) -> str:
        if action.get("tool") != "final":
            return ""

        args = action.get("args", {})
        if not isinstance(args, dict):
            return ""

        return str(args.get("content", ""))

    def _is_tool_allowed(self, tool_name: str, user_input: str) -> bool:
        if tool_name != "echo":
            return True

        normalized = user_input.lower()
        echo_markers = (
            "echo",
            "repete",
            "répète",
            "retourne exactement",
            "redis exactement",
        )
        return any(marker in normalized for marker in echo_markers)

    async def _force_final_response(
        self,
        system_prompt: str,
        instruction: str,
    ) -> str:
        messages = [
            *self._build_messages(system_prompt),
            {"role": "assistant", "content": instruction},
        ]

        raw = await self.llm.chat(messages)
        action = self._parse_action(raw)
        response = self._final_content(action)

        if response:
            return response

        return "Je peux te repondre directement, sans utiliser de tool."

    async def run(self, user_input: str) -> str:
        self.logger.info("Agent runtime started")

        self.add_user_message(user_input)
        system_prompt = self._build_system_prompt()

        raw = await self.llm.chat(self._build_messages(system_prompt))
        action = self._parse_action(raw)

        tool_name = action.get("tool")
        args = action.get("args", {})
        if not isinstance(args, dict):
            args = {}

        if tool_name == "final":
            response = self._final_content(action)
        else:
            tool_name = str(tool_name)
            tool = self.tools.get(tool_name)

            if not tool:
                self.add_assistant_message(
                    f"[tool_error] Tool introuvable: {tool_name}. "
                    'Reponds avec le tool "final".'
                )
                response = await self._force_final_response(
                    system_prompt,
                    'Le tool demande est introuvable. Reponds avec "final".',
                )
            elif not self._is_tool_allowed(tool_name, user_input):
                response = await self._force_final_response(
                    system_prompt,
                    (
                        f'Le tool "{tool_name}" n\'est pas utile pour cette '
                        'demande. Reponds naturellement avec "final".'
                    ),
                )
            else:
                result = await tool.execute(**args)

                self.add_assistant_message(f"[tool:{tool_name}] {result}")

                response = await self._force_final_response(
                    system_prompt,
                    (
                        f'Observation du tool "{tool_name}": {result}. '
                        'Reponds maintenant avec "final".'
                    ),
                )

        if not response:
            response = raw

        self.add_assistant_message(response)
        self._trim_history()

        self.logger.info("Agent runtime finished")

        return response

    def reset(self) -> None:
        self.state = AgentState()
        self.logger.info("Agent state reset")
