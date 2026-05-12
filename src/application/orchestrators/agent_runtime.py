import json

from src.domain.entities.agent import AgentState
from src.domain.entities.message import Message
from src.domain.protocols.llm_provider import LLMProvider
from src.domain.protocols.logger import LoggerProtocol


SYSTEM_PROMPT = """
Tu es un moteur d'exécution.

RÈGLE ABSOLUE :
Tu DOIS répondre UNIQUEMENT en JSON valide.
Aucun texte hors JSON n'est autorisé.

FORMAT STRICT :
{"content": "..."}

INTERDICTION :
- texte hors JSON
- explications
- markdown
"""


class AgentRuntime:
    MAX_MESSAGES = 10

    def __init__(self, llm: LLMProvider, logger: LoggerProtocol):
        self.llm = llm
        self.logger = logger
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

    async def run(self, user_input: str) -> str:
        self.logger.info("Agent runtime started")

        # 1. input utilisateur
        self.add_user_message(user_input)

        # 2. contexte LLM
        llm_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[
                {"role": m.role, "content": m.content}
                for m in self.state.messages
            ],
        ]

        # 3. appel LLM
        raw_response = await self.llm.chat(llm_messages)

        for _ in range(2):
            try:
                raw_response = self._ensure_json(raw_response)
                data = json.loads(raw_response)
                break
            except Exception:
                self.logger.warning("Retrying malformed output from LLM")

                raw_response = await self.llm.chat(llm_messages)
        else:
            raise ValueError("LLM failed to produce valid JSON")

        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError:
            self.logger.error(f"Broken JSON: {raw_response}")
            raise

        response = data.get("content", "")
        # 6. mémoire
        self._trim_history()

        self.logger.info("Agent runtime finished")

        return response

    def reset(self) -> None:
        self.state = AgentState()
        self.logger.info("Agent state reset")