import json
import re
import time
import uuid
from typing import Any

from src.domain.entities.agent import AgentState
from src.domain.entities.message import Message
from src.domain.entities.tool_call import ToolCall
from src.domain.protocols.llm_provider import LLMProvider
from src.domain.protocols.logger import LoggerProtocol
from src.domain.protocols.memory import LongTermMemory
from src.domain.protocols.tool import Tool, ToolProvider
from src.domain.protocols.event_bus import EventBus
from src.application.orchestrators.tool_executor import ToolExecutor, ToolExecutionError
from src.application.orchestrators.response_parser import ResponseParser
from src.application.orchestrators.prompt_manager import PromptManager
from src.application.orchestrators.conversation_manager import ConversationManager
from src.application.orchestrators.memory_manager import MemoryManager


class AgentRuntime:
    MAX_MESSAGES = 10

    def __init__(
        self,
        llm: LLMProvider,
        logger: LoggerProtocol,
        tools: ToolProvider,
        memory: LongTermMemory | None = None,
        executor: ToolExecutor | None = None,
        event_bus: EventBus | None = None,
        parser: ResponseParser | None = None,
        prompter: PromptManager | None = None,
    ) -> None:
        self.llm = llm
        self.logger = logger
        self.tools = tools
        self.event_bus = event_bus
        
        # Initialisation des composants modulaires
        self.conversation = ConversationManager(self.MAX_MESSAGES)
        self.memory_manager = MemoryManager(memory)
        self.parser = parser or ResponseParser(logger)
        self.prompter = prompter or PromptManager()
        self.executor = executor or ToolExecutor(tools, logger, event_bus=event_bus)

    def _build_messages(self, system_prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            *self.conversation.get_messages_as_dicts()
        ]

    def _is_tool_allowed(self, tool: Tool, user_input: str) -> bool:
        if not tool.trigger_words:
            return True

        normalized = user_input.lower()
        return any(marker in normalized for marker in tool.trigger_words)

    async def _force_final_response(
        self,
        system_prompt: str,
        instruction: str,
    ) -> str:
        correction_prompt = (
            f"{system_prompt}\n\n"
            "CORRECTION OBLIGATOIRE : reponds maintenant avec le format "
            'JSON final uniquement: {"tool":"final","args":{"content":"..."}}.'
        )
        messages = [
            {"role": "system", "content": correction_prompt},
            *self.conversation.get_messages_as_dicts(),
            {"role": "user", "content": instruction},
        ]

        raw = await self.llm.chat(messages)
        action = self.parser.parse_action(raw)
        response = str(action.args.get("content", ""))

        if response:
            return response

        return "Je peux te repondre directement, sans utiliser de tool."

    async def _run_tool(
        self,
        tool: Tool,
        args: dict[str, Any],
        user_input: str,
        system_prompt: str,
        trace_id: str,
    ) -> str:
        try:
            # Délégation de l'exécution, des timeouts et de l'audit à l'exécuteur
            result = await self.executor.execute(
                tool.name, args, user_input, trace_id=trace_id
            )
            
            if tool.return_direct:
                return result

            self.conversation.add_assistant_message(f"[tool:{tool.name}] {result}")
            return await self._force_final_response(
                system_prompt,
                f'Observation du tool "{tool.name}": {result}. Utilise cette observation pour repondre.'
            )
        except ToolExecutionError as e:
            if self.event_bus:
                await self.event_bus.emit("agent.error", {"trace_id": trace_id, "error": str(e)})
            return str(e)

    async def run(self, user_input: str) -> str:
        trace_id = str(uuid.uuid4())
        self.logger.info("Agent runtime started")
        if self.event_bus:
            await self.event_bus.emit("agent.started", {"trace_id": trace_id, "user_input": user_input})

        try:
            self.conversation.add_user_message(user_input)
            self.memory_manager.learn_facts(user_input)
            memory_response = self.memory_manager.answer_from_memory(user_input)
            
            if memory_response:
                self.conversation.add_assistant_message(memory_response)
                self.conversation.trim_history()
                self.logger.info("Agent runtime finished")
                return memory_response

            system_prompt = self.prompter.build_system_prompt(
                self.tools, 
                self.memory_manager.memory, 
                user_input
            )

            raw = await self.llm.chat(self._build_messages(system_prompt))
            action = self.parser.parse_action(raw)

            tool_name = action.tool
            args = action.args

            if tool_name == "final":
                response = str(args.get("content", ""))
                if response.strip().lower() in {"", "final", "json", "reponse finale"}:
                    response = await self._force_final_response(
                        system_prompt,
                        "La reponse precedente est un marqueur technique. "
                        "Reponds vraiment a la demande de l utilisateur.",
                    )
            else:
                tool = self.tools.get(str(tool_name))

                if not tool:
                    available = ", ".join([t.name for t in self.tools.list_tools()])
                    response = f"Outil '{tool_name}' inconnu. Outils disponibles : {available}."
                elif not self._is_tool_allowed(tool, user_input):
                    response = await self._force_final_response(
                        system_prompt,
                        (
                            f'Le tool "{tool.name}" n est pas pertinent pour cette '
                            "demande. Reponds naturellement a l utilisateur."
                        ),
                    )
                else:
                    response = await self._run_tool(
                        tool=tool,
                        args=args,
                        user_input=user_input,
                        system_prompt=system_prompt,
                        trace_id=trace_id,
                    )

            if not response:
                response = raw.strip()

            self.conversation.add_assistant_message(response)
            self.conversation.trim_history()

            self.logger.info("Agent runtime finished")

            return response
        except Exception as e:
            self.logger.error(f"Agent runtime failed: {e}")
            if self.event_bus:
                await self.event_bus.emit("agent.failed", {"trace_id": trace_id, "error": str(e)})
            raise

    def reset(self) -> None:
        self.conversation.reset()
        self.logger.info("Agent state reset")
