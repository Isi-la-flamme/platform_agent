import uuid
import re
from typing import Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

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
    MAX_MESSAGES = 6  # Réduit pour éviter l'erreur 413 (Payload Too Large)

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
        if any(marker in normalized for marker in tool.trigger_words):
            return True
            
        # Intelligence : Autorise file_crud si on detecte une extension de fichier (ex: index.html)
        if tool.name == "file_crud" and re.search(r'\.[a-z0-9]{1,5}\b', normalized):
            return True
            
        return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        # On peut affiner ici selon l'exception spécifique de Groq si disponible
        reraise=True 
    )
    async def _safe_chat(self, messages: list[dict[str, str]]) -> str:
        """Appelle le LLM avec une stratégie de retry pour gérer les erreurs 429."""
        return await self.llm.chat(messages)

    async def _force_final_response(
        self,
        system_prompt: str,
        instruction: str,
    ) -> str:
        """Version optimisée : évite de renvoyer tout le prompt système pour réduire la charge (413)."""
        short_correction = (
            "Tu es un assistant concis. REPONDS UNIQUEMENT AU FORMAT JSON FINAL. "
            "Exemple: {\"tool\":\"final\",\"args\":{\"content\":\"Message\"}}"
        )
        
        messages = [
            {"role": "system", "content": short_correction},
            # On ne garde que les 2 derniers messages pour le contexte de correction
            *self.conversation.get_messages_as_dicts()[-2:],
            {"role": "user", "content": instruction},
        ]

        raw = await self._safe_chat(messages)
        action = self.parser.parse_action(raw)
        response = str(action.args.get("content", ""))
        
        if response:
            return response

        return "Je peux te repondre directement, sans utiliser de tool."

    def _needs_final_retry(self, response: str) -> bool:
        normalized = response.strip().lower()
        if normalized in {"", "final", "json", "none", "null", "plan", "tool", "goal"}:
            return True

        return (
            normalized.startswith("plan actuel")
            or normalized.startswith('{"goal"')
            or normalized.startswith("{'goal'")
            or normalized.endswith("\nfinal")
            or "\npas encore de tâche à effectuer" in normalized
            or "\npas encore de tache a effectuer" in normalized
        )

    def _answer_tools_list_if_requested(self, user_input: str) -> str | None:
        normalized = user_input.lower()
        asks_for_tools = (
            "tool" in normalized
            and any(marker in normalized for marker in ("liste", "disponible", "quels"))
        )
        if not asks_for_tools:
            return None

        lines = ["Tools disponibles :"]
        for tool in self.tools.list_tools():
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

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
            error_msg = f"ERREUR TOOL : {str(e)}. Corrige tes arguments ou change de stratégie."
            if self.event_bus:
                await self.event_bus.emit("agent.error", {"trace_id": trace_id, "error": error_msg})
            return error_msg

    async def run(self, user_input: str, max_steps: int = 10) -> str:
        trace_id = str(uuid.uuid4())
        self.logger.info(f"Autonomous session started | trace_id={trace_id}")
        if self.event_bus:
            await self.event_bus.emit("agent.started", {"trace_id": trace_id, "user_input": user_input})

        self.conversation.add_user_message(user_input)
        self.memory_manager.learn_facts(user_input)

        tools_response = self._answer_tools_list_if_requested(user_input)
        if tools_response:
            self.conversation.add_assistant_message(tools_response)
            return tools_response

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

            raw = await self._safe_chat(self._build_messages(system_prompt))
            action = self.parser.parse_action(raw)

            # Mise à jour du plan si fourni par le LLM
            if action.plan and action.plan.tasks:
                self.current_plan = action.plan
                self.logger.info(f"Plan updated: {len(self.current_plan.tasks)} tasks.")

            tool_name = action.tool
            args = action.args

            if tool_name == "final":
                response = str(args.get("content", ""))
                if self._needs_final_retry(response):
                    response = await self._force_final_response(
                        system_prompt,
                        "Fournis une reponse conversationnelle courte et naturelle.",
                    )
                
                self.conversation.add_assistant_message(response)
                self.conversation.trim_history()
                return response

            # Exécution de l'outil
            if str(tool_name).strip().lower() in {"", "none", "null"}:
                response = await self._force_final_response(
                    system_prompt,
                    "Aucun outil n'est necessaire. Reponds simplement a l'utilisateur.",
                )
                self.conversation.add_assistant_message(response)
                self.conversation.trim_history()
                return response

            tool = self.tools.get(str(tool_name))
            if not tool:
                # Tool inexistant - retourner immédiatement l'erreur
                available_tools = ", ".join(t.name for t in self.tools.list_tools())
                observation = f'Je n\'ai pas acces au tool "{tool_name}". Tools disponibles: {available_tools}.'
                self.conversation.add_assistant_message(observation)
                self.conversation.trim_history()
                return observation
            elif not self._is_tool_allowed(tool, user_input):
                # Tool non autorisé pour cette demande - continuer la boucle
                observation = f'L\'outil "{tool_name}" n\'est pas autorisé pour cette demande.'
            else:
                observation = await self._run_tool(
                    tool=tool, args=args, user_input=user_input, 
                    system_prompt=system_prompt, trace_id=trace_id
                )

            # Si l'outil retourne directement ET était autorisé, retourner immédiatement
            if tool and tool.return_direct and self._is_tool_allowed(tool, user_input):
                self.conversation.add_assistant_message(observation)
                self.conversation.trim_history()
                return observation
            
            # Ajouter l'observation à l'historique et continuer la boucle
            self.conversation.add_assistant_message(observation)
            last_response = observation

        self.logger.warning(f"Max steps ({max_steps}) reached for goal.")
        return f"Désolé, je n'ai pas pu terminer l'objectif en {max_steps} étapes. Dernier état: {last_response}"


    def reset(self) -> None:
        self.conversation.reset()
        self.logger.info("Agent state reset")
