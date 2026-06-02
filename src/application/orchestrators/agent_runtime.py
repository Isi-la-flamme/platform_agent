import uuid
from typing import Any

from src.application.orchestrators.conversation_manager import ConversationManager
from src.application.orchestrators.memory_manager import MemoryManager
from src.application.orchestrators.prompt_manager import PromptManager
from src.application.orchestrators.response_parser import ResponseParser
from src.application.orchestrators.tool_executor import ToolExecutionError, ToolExecutor
from src.domain.entities.plan import Plan
from src.domain.protocols.event_bus import EventBus
from src.domain.protocols.llm_provider import LLMProvider
from src.domain.protocols.logger import LoggerProtocol
from src.domain.protocols.memory import LongTermMemory
from src.domain.protocols.tool import Tool, ToolProvider


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

    async def run(self, user_input: str, max_steps: int = 5) -> str:
        trace_id = str(uuid.uuid4())
        self.logger.info(f"Autonomous session started | trace_id={trace_id}")
        if self.event_bus:
            await self.event_bus.emit("agent.started", {"trace_id": trace_id, "user_input": user_input})

        self.conversation.add_user_message(user_input)
        self.memory_manager.learn_facts(user_input)

        # Court-circuit mémoire
        memory_response = self.memory_manager.answer_from_memory(user_input)
        if memory_response:
            self.conversation.add_assistant_message(memory_response)
            return memory_response

        step_count = 0
        last_response = ""

        while step_count < max_steps:
            step_count += 1
            system_prompt = self.prompter.build_system_prompt(
                self.tools, 
                self.memory_manager.memory, 
                user_input,
                plan=self.current_plan
            )

            raw = await self.llm.chat(self._build_messages(system_prompt))
            action = self.parser.parse_action(raw)

            # Mise à jour du plan si fourni par le LLM
            if action.plan:
                self.current_plan = action.plan
                self.logger.info(f"Plan updated: {len(self.current_plan.tasks)} tasks.")

            tool_name = action.tool
            args = action.args

            if tool_name == "final":
                response = str(args.get("content", ""))
                if response.strip().lower() in {"", "final", "json"}:
                    response = await self._force_final_response(system_prompt, "Fournis une réponse réelle.")
                
                self.conversation.add_assistant_message(response)
                self.conversation.trim_history()
                return response

            # Exécution de l'outil
            tool = self.tools.get(str(tool_name))
            if not tool or not self._is_tool_allowed(tool, user_input):
                observation = f"Erreur: Outil '{tool_name}' non autorisé ou inconnu."
            else:
                observation = await self._run_tool(
                    tool=tool, args=args, user_input=user_input, 
                    system_prompt=system_prompt, trace_id=trace_id
                )

            # Si l'outil ne retourne pas direct, l'observation est déjà dans l'historique
            # via _run_tool. Si tool.return_direct est True, on l'ajoute ici.
            if tool and tool.return_direct:
                self.conversation.add_assistant_message(f"Observation: {observation}")
            
            last_response = observation

        self.logger.warning(f"Max steps ({max_steps}) reached for goal.")
        return f"Désolé, je n'ai pas pu terminer l'objectif en {max_steps} étapes. Dernier état: {last_response}"


    def reset(self) -> None:
        self.conversation.reset()
        self.logger.info("Agent state reset")
