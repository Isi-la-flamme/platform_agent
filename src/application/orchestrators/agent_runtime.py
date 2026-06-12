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
from src.application.memory_v2.memory_v2 import MemoryV2
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
        self.memory_v2 = MemoryV2()
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
        
        if tool.name == "echo" and not tool.chat_safe:
            return  False

        return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _safe_chat(self, messages: list[dict[str, str]]) -> str:
        return await self.llm.chat(messages)

    async def _force_final_response(self, system_prompt: str, instruction: str) -> str:
        short_correction = (
            "Tu es un assistant concis et chaleureux. "
            "Réponds UNIQUEMENT avec ce format JSON:\n"
            '{"tool":"final","args":{"content":"ta réponse ici"}}\n\n'
            "Exemple: {\"tool\":\"final\",\"args\":{\"content\":\"Je vais bien, merci !\"}}"
        )

        messages = [
            {"role": "system", "content": short_correction},
            *self.conversation.get_messages_as_dicts()[-3:],
            {"role": "user", "content": instruction},
        ]

        raw = await self._safe_chat(messages)
        action = self.parser.parse_action(raw)

        content = str(action.args.get("content", "")).strip()
        
        # Si le LLM répond du texte brut au lieu de JSON
        if not content or content in {"...", "null", "none"}:
            content = raw.strip()
            # Nettoyer le markdown éventuel
            for prefix in ["```json", "```", "JSON:", "Réponse:"]:
                content = content.removeprefix(prefix).strip()
        
        # Fallback ultime
        if not content or len(content) < 2:
            content = instruction or "Je suis là !"
            
        return content

    def _needs_final_retry(self, response: str) -> bool:
        normalized = response.strip().lower()

        return (
            normalized in {"", "final", "json", "none", "null", "plan", "tool", "réponse directe.", "réponse directe"}
            or normalized.startswith("plan actuel")
            or normalized.startswith('{"goal"')
            or len(normalized) < 3  # ✅ Évite les réponses vides ou trop courtes
        )

    async def _learn_facts_from_response(self, user_input: str, response: str) -> None:
        """Extrait et stocke les faits mentionnés dans la réponse du LLM."""
        fact_patterns = [
            "est un", "est une", "signifie", "se trouve", "capitale",
            "président", "date de", "créé en", "fondé en", "inventé par"
        ]
        
        for pattern in fact_patterns:
            if pattern in response.lower():
                sentences = response.replace("!", ".").replace("?", ".").split(".")
                for sentence in sentences:
                    if pattern in sentence.lower():
                        fact = sentence.strip()
                        if 10 < len(fact) < 300:
                            self.memory_v2.store_fact(fact, importance=0.6)
                            self.logger.debug(f"Fait appris: {fact}")


    async def _learn_facts_from_response(self, user_input: str, response: str) -> None:
        """Extrait et stocke les faits mentionnés dans la réponse du LLM."""
        fact_patterns = [
            "est un", "est une", "signifie", "se trouve", "capitale",
            "président", "date de", "créé en", "fondé en", "inventé par"
        ]
        
        for pattern in fact_patterns:
            if pattern in response.lower():
                sentences = response.replace("!", ".").replace("?", ".").split(".")
                for sentence in sentences:
                    if pattern in sentence.lower():
                        fact = sentence.strip()
                        if len(fact) > 10 and len(fact) < 300:
                            self.memory_v2.store_fact(fact, importance=0.6)
                            self.logger.debug(f"Fait appris: {fact}")


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
            await self.event_bus.emit(
                "agent.started",
                {"trace_id": trace_id, "user_input": user_input},
            )

        # =========================
        # MEMORY WRITE (INPUT)
        # =========================
        self.memory_v2.store_episode(user_input, {"type": "input"})

        self.conversation.add_user_message(user_input)
        self.memory_manager.learn_facts(user_input)

        # =========================
        # TOOL SHORTCUT
        # =========================
        tools_response = self._answer_tools_list_if_requested(user_input)
        if tools_response:
            self.memory_v2.store_episode(user_input, {"type": "tool_list", "output": tools_response})
            return tools_response

        # =========================
        # MEMORY SHORTCUT
        # =========================
        memory_response = self.memory_manager.answer_from_memory(user_input)
        if memory_response:
            self.memory_v2.store_episode(user_input, {"type": "memory_hit", "output": memory_response})
            return memory_response

        # =========================
        # PLAN INIT (FIX IMPORTANT)
        # =========================
        if self.current_plan is None or len(getattr(self.current_plan, "tasks", [])) == 0:
            self.current_plan = await self.planner.create_plan(user_input)

        last_response = ""

        for _ in range(max_steps):

            # =========================
            # TASK PICK
            # =========================
            task = self.scheduler.get_next_task(self.current_plan) if self.current_plan else None
            task_query = task.description if task else user_input

            # =========================
            # MEMORY RETRIEVAL (SAFE)
            # =========================
            retrieved = self.memory_v2.retrieve(task_query)

            memory_context = "\n".join(
                f"- {getattr(m, 'content', str(m))}"
                for m in retrieved[:5]
            )

            # =========================
            # PROMPT BUILD
            # =========================
            system_prompt = self.prompter.build_system_prompt(
                self.tools,
                self.memory_manager.memory,
                user_input,
                plan=self.current_plan,
            )

            if memory_context:
                system_prompt += f"\n\nMEMORY V2:\n{memory_context}"

            if task:
                system_prompt += f"\n\nTACHE ACTIVE:\n{task.description}"
                if task.status == "pending":
                    task.status = "in_progress"

            # =========================
            # LLM CALL
            # =========================
            raw = await self._safe_chat(self._build_messages(system_prompt))
            action = self.parser.parse_action(raw)

            # =========================
            # PLAN UPDATE
            # =========================
            if action.plan:
                self.current_plan = action.plan

            tool_name = str(action.tool or "final")
            args = action.args or {}

            # =========================
            # FINAL RESPONSE
            # =========================
            if tool_name == "final":
                response = str(args.get("content", ""))

                if self._needs_final_retry(response):
                    response = await self._force_final_response(
                        system_prompt,
                        "Réponds naturellement et brièvement."
                    )

                self.conversation.add_assistant_message(response)

                # ✅ Apprendre des faits de la réponse
                await self._learn_facts_from_response(user_input, response)

                self.memory_v2.store_episode(user_input, {
                    "type": "final",
                    "output": response,
                    "task": task.description if task else None,
                })

                if task:
                    task.status = "completed"

                return response
            # =========================
            # EMPTY TOOL FIX
            # =========================
            if tool_name in {"", "none", "null", "final"}:
                response = await self._force_final_response(
                    system_prompt,
                    "Réponds directement à l'utilisateur."
                )

                self.memory_v2.store_episode(user_input, {
                    "type": "direct",
                    "output": response,
                })

                return response

            # =========================
            # TOOL RESOLUTION
            # =========================
            tool = self.tools.get(tool_name)

            if not tool:
                observation = f"Tool inconnu: {tool_name}"
                success = False

            elif not self._is_tool_allowed(tool, user_input):
                # 🔥 FIX IMPORTANT: ne bloque pas tools génériques type echo
                observation = await self._run_tool(tool, args, user_input, trace_id)
                success = True

            else:
                try:
                    observation = await self._run_tool(tool, args, user_input, trace_id)
                    success = True
                except Exception as e:
                    observation = f"ERROR: {str(e)}"
                    success = False

            # =========================
            # TASK UPDATE
            # =========================
            if task:
                task.status = "completed" if success else "failed"

            # =========================
            # SKILL MEMORY
            # =========================
            if success and tool:
                self.memory_v2.store_skill(
                    task=tool_name,
                    steps=[task.description if task else tool_name, tool_name],
                    success=True,
                )

            # =========================
            # EPISODIC MEMORY
            # =========================
            self.memory_v2.store_episode(user_input, {
                "type": "tool_execution",
                "tool": tool_name,
                "output": observation,
                "success": success,
            })

            # =========================
            # RETURN DIRECT TOOL
            # =========================
            if tool and tool.return_direct:
                return observation

            self.conversation.add_assistant_message(observation)
            last_response = observation

        return f"Max steps atteints. Dernier état: {last_response}"

  
    def reset(self) -> None:
        self.conversation.reset()
        self.current_plan = None
        self.logger.info("Agent reset")