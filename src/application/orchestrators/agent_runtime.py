import json

from src.domain.entities.agent import AgentState
from src.domain.entities.message import Message
from src.domain.protocols.llm_provider import LLMProvider
from src.domain.protocols.logger import LoggerProtocol


SYSTEM_PROMPT = """
Tu es un agent logiciel.

Tu peux :
- appeler des tools
- ou répondre directement

RÈGLE ABSOLUE :
Tu dois répondre uniquement en JSON valide.

FORMAT 1 (appel tool) :
{
  "tool": "nom_du_tool",
  "args": { ... }
}

FORMAT 2 (réponse finale) :
{
  "tool": "final",
  "args": {
    "content": "réponse finale"
  }
}
"""


class AgentRuntime:
    MAX_MESSAGES = 10

    def __init__(self, llm: LLMProvider, logger: LoggerProtocol, tools):
        self.llm = llm
        self.logger = logger
        self.tools = tools
        self.state = AgentState()

    def add_user_message(self, content: str) -> None:
        self.state.messages.append(
            Message(role="user", content=content)
        )

    def add_assistant_message(self, content: str) -> None:
        self.state.messages.append(
            Message(role="assistant", content=content)
        )

    def _trim_history(self) -> None:
        self.state.messages = self.state.messages[-self.MAX_MESSAGES:]

    def _ensure_json(self, text: str) -> str:
        text = text.strip()

        if not text.startswith("{"):
            raise ValueError(f"Invalid agent output (not JSON): {text}")

        return text


    def _parse_action(self, raw: str) -> dict:
        raw = raw.strip()

        # 🔴 CAS 1 : JSON correct
        if raw.startswith("{"):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass

        # 🔴 CAS 2 : LLM hors format → fallback intelligent
        return {
            "tool": "final",
            "args": {
                "content": raw
            }
        }


    async def run(self, user_input: str) -> str:
        self.logger.info("Agent runtime started")

        self.add_user_message(user_input)

        llm_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[
                {"role": m.role, "content": m.content}
                for m in self.state.messages
            ],
        ]

        raw = await self.llm.chat(llm_messages)

        action = self._parse_action(raw)

        tool_name = action.get("tool")
        args = action.get("args", {})

        # TOOL LOGIC
        if tool_name == "final":
            response = args.get("content", "")

        else:
            tool = self.tools.get(tool_name)

            if not tool:
                response = f"Tool introuvable: {tool_name}"
            else:
                result = await tool.execute(**args)

                # injecte observation proprement dans contexte
                self.add_assistant_message(f"[tool:{tool_name}] {result}")

                # rebuild contexte avec observation
                llm_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *[
                        {"role": m.role, "content": m.content}
                        for m in self.state.messages
                    ],
                ]

                raw2 = await self.llm.chat(llm_messages)
                action2 = self._parse_action(raw2)

                # sécurité finale
                response = (
                    action2.get("args", {}).get("content")
                    or str(result)
                    or "Erreur génération finale"
                )
        # SAFE FINAL
        if not response:
            response = raw  # dernier fallback

        self.add_assistant_message(response)
        self._trim_history()

        self.logger.info("Agent runtime finished")

        return response


    def reset(self) -> None:
        self.state = AgentState()
        self.logger.info("Agent state reset")