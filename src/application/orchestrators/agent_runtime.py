import uuid
import re
from typing import Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from src.application.orchestrators.conversation_manager import ConversationManager
from src.application.orchestrators.memory_manager import MemoryManager
from src.application.orchestrators.prompt_manager import PromptManager
from src.application.orchestrators.response_parser import ResponseParser
from src.application.orchestrators.tool_executor import ToolExecutionError, ToolExecutor
from src.application.orchestrators.planner import Planner
from src.application.orchestrators.scheduler import Scheduler

from src.domain.entities.plan import Plan
from src.domain.protocols.event_bus import EventBus
from src.domain.protocols.llm_provider import LLMProvider
from src.domain.protocols.logger import LoggerProtocol
from src.domain.protocols.memory import LongTermMemory
from src.domain.protocols.tool import Tool, ToolProvider


class AgentRuntime:
    MAX_MESSAGES = 6

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

        # Core modules
        self.conversation = ConversationManager(self.MAX_MESSAGES)
        self.memory_manager = MemoryManager(memory)
        self.parser = parser or ResponseParser(logger)
        self.prompter = prompter or PromptManager()
        self.executor = executor or ToolExecutor(tools, logger, event_bus=event_bus)

        # 🧠 FIX IMPORTANT : composants manquants ajoutés
        self.scheduler = Scheduler()
        self.planner = Planner(self.llm, self.parser)

        self.current_plan: Plan | None = None

    def _build_messages(self, system_prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            *self.conversation.get_messages_as_dicts()
        ]

    def _is_tool_allowed(self, tool: Tool, user_input: str) -> bool:
        if not tool.trigger_words:
            return True

        normalized = user_input.lower()

        if any(marker in normalized for marker in tool.trigger_words):
            return True

        if tool.name == "file_crud" and re.search(r'\.[a-z0-9]{1,5}\b', normalized):
            return True

        return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _safe_chat(self, messages: list[dict[str, str]]) -> str:
        return await self.llm.chat(messages)

    async def _force_final_response(self, system_prompt: str, instruction: str) -> str:
        short_correction = (
            "Tu es un assistant concis. REPONDS UNIQUEMENT EN JSON: "
            "{\"tool\":\"final\",\"args\":{\"content\":\"...\"}}"
        )

        messages = [
            {"role": "system", "content": short_correction},
            *self.conversation.get_messages_as_dicts()[-2:],
            {"role": "user", "content": instruction},
        ]

        raw = await self._safe_chat(messages)
        action = self.parser.parse_action(raw)

        return str(action.args.get("content", "")) or "Réponse directe."

    def _needs_final_retry(self, response: str) -> bool:
        normalized = response.strip().lower()

        return (
            normalized in {"", "final", "json", "none", "null", "plan", "tool"}
            or normalized.startswith("plan actuel")
            or normalized.startswith('{"goal"')
        )

    def _answer_tools_list_if_requested(self, user_input: str) -> str | None:
        normalized = user_input.lower()

        if "tool" in normalized and any(x in normalized for x in ["liste", "disponible", "quels"]):
            return "\n".join(
                ["Tools disponibles :"]
                + [f"- {t.name}: {t.description}" for t in self.tools.list_tools()]
            )

        return None

    async def _run_tool(self, tool: Tool, args: dict[str, Any], user_input: str, trace_id: str) -> str:
        try:
            return await self.executor.execute(tool.name, args, user_input, trace_id=trace_id)
        except ToolExecutionError as e:
            msg = f"ERREUR TOOL : {e}"
            if self.event_bus:
                await self.event_bus.emit("agent.error", {"trace_id": trace_id, "error": msg})
            return msg

    async def run(self, user_input: str, max_steps: int = 10) -> str:
        trace_id = str(uuid.uuid4())
        self.logger.info(f"Autonomous session started | trace_id={trace_id}")

        if self.event_bus:
            await self.event_bus.emit("agent.started", {"trace_id": trace_id})

        self.conversation.add_user_message(user_input)
        self.memory_manager.learn_facts(user_input)

        tools_response = self._answer_tools_list_if_requested(user_input)
        if tools_response:
            return tools_response

        memory_response = self.memory_manager.answer_from_memory(user_input)
        if memory_response:
            return memory_response

        last_response = ""

        for _ in range(max_steps):

            task = None

            if self.current_plan:
                task = self.scheduler.get_next_task(self.current_plan)

            system_prompt = self.prompter.build_system_prompt(
                self.tools,
                self.memory_manager.memory,
                user_input,
                plan=self.current_plan
            )

            if task:
                system_prompt += f"\n\nTACHE ACTIVE: {task.description}"
                task.status = "in_progress"

            raw = await self._safe_chat(self._build_messages(system_prompt))
            action = self.parser.parse_action(raw)

            if action.plan and action.plan.tasks:
                self.current_plan = action.plan

            tool_name = action.tool
            args = action.args

            if tool_name == "final":
                response = str(args.get("content", ""))

                if self._needs_final_retry(response):
                    response = await self._force_final_response(
                        system_prompt,
                        "Réponds naturellement et brièvement."
                    )

                self.conversation.add_assistant_message(response)
                return response

            if tool_name.strip().lower() in {"", "none", "null"}:
                response = await self._force_final_response(
                    system_prompt,
                    "Réponds directement à l'utilisateur."
                )
                return response

            tool = self.tools.get(tool_name)

            if not tool:
                return f"Tool inconnu: {tool_name}"

            if not self._is_tool_allowed(tool, user_input):
                observation = f"Tool '{tool_name}' non autorisé."
            else:
                observation = await self._run_tool(tool, args, user_input, trace_id)

            if tool.return_direct and self._is_tool_allowed(tool, user_input):
                return observation

            self.conversation.add_assistant_message(observation)
            last_response = observation

        return f"Max steps atteints. Dernier état: {last_response}"

    def reset(self) -> None:
        self.conversation.reset()
        self.current_plan = None
        self.logger.info("Agent reset")