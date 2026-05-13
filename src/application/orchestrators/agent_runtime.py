import json
import re
from typing import Any

from src.domain.entities.agent import AgentState
from src.domain.entities.message import Message
from src.domain.protocols.llm_provider import LLMProvider
from src.domain.protocols.logger import LoggerProtocol
from src.domain.protocols.memory import LongTermMemory
from src.domain.protocols.tool import Tool, ToolProvider

SYSTEM_PROMPT = """
Tu es un agent logiciel.

Tu peux :
- appeler un tool disponible
- repondre directement
- discuter normalement avec l'utilisateur

STYLE :
- Reponds en francais naturel.
- Sois clair, court et utile.
- Ne dis pas que tu es "aux ordres".
- Si une information personnelle est dans MEMOIRE LONG TERME, utilise-la.
- Si tu ne sais pas une information personnelle, dis simplement que tu ne l'as
  pas encore.

MEMOIRE LONG TERME :
__MEMORY__

TOOLS DISPONIBLES :
__TOOLS__

REGLES ABSOLUES :
- Tu dois repondre uniquement en JSON valide.
- Tu ne dois jamais ajouter de markdown, texte, explication ou bloc code hors JSON.
- Tu dois appeler uniquement un tool liste dans TOOLS DISPONIBLES.
- Si aucun tool disponible ne correspond, utilise le tool "final".
- Pour une salutation ou une conversation simple, utilise toujours "final".
- N'utilise un tool que si cela aide vraiment a repondre a la demande.

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
        memory: LongTermMemory | None = None,
    ) -> None:
        self.llm = llm
        self.logger = logger
        self.tools = tools
        self.memory = memory
        self.state = AgentState()

    def add_user_message(self, content: str) -> None:
        self.state.messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        self.state.messages.append(Message(role="assistant", content=content))

    def _trim_history(self) -> None:
        self.state.messages = self.state.messages[-self.MAX_MESSAGES :]

    def _format_tool(self, tool: Tool) -> str:
        args = ", ".join(
            f"{name}: {description}"
            for name, description in tool.args_schema.items()
        )
        if not args:
            args = "aucun argument"

        behavior = "retour direct" if tool.return_direct else "observation"
        return f"- {tool.name}: {tool.description} Args: {args}. Mode: {behavior}."

    def _build_system_prompt(self, user_input: str = "") -> str:
        tools = self.tools.list_tools()

        if not tools:
            tool_context = "- aucun tool disponible"
        else:
            tool_context = "\n".join(self._format_tool(tool) for tool in tools)

        memory_context = self._format_memory_context(user_input)

        return (
            SYSTEM_PROMPT.replace("__TOOLS__", tool_context)
            .replace("__MEMORY__", memory_context)
        )

    def _format_memory_context(self, user_input: str) -> str:
        if not self.memory:
            return "- aucune memoire long terme disponible"

        facts = self.memory.search(user_input)
        if not facts:
            facts = self.memory.all()[:5]

        if not facts:
            return "- aucun fait memorise"

        return "\n".join(f"- {fact.text}" for fact in facts)

    def _build_messages(self, system_prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            *[
                {"role": message.role, "content": message.content}
                for message in self.state.messages
            ],
        ]

    def _parse_json_value(self, raw: str) -> Any:
        text = raw.strip()
        decoder = json.JSONDecoder()

        try:
            value, _ = decoder.raw_decode(text)
        except json.JSONDecodeError:
            pass
        else:
            return value

        if text.startswith("```"):
            cleaned = text.strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                value, _ = decoder.raw_decode(cleaned)
            except json.JSONDecodeError:
                pass
            else:
                return value

        for index, character in enumerate(text):
            if character not in ('{', '"'):
                continue

            try:
                value, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue

            if isinstance(value, dict | str):
                return value

        return raw

    def _parse_action(self, raw: str) -> dict[str, Any]:
        parsed = self._parse_json_value(raw)

        if isinstance(parsed, dict):
            tool_name = parsed.get("tool")
            args = parsed.get("args", {})
            if not isinstance(args, dict):
                args = {}

            if isinstance(tool_name, str):
                return {
                    "tool": tool_name,
                    "args": args,
                }

        if isinstance(parsed, str):
            content = parsed
        else:
            content = raw.strip()

        return {
            "tool": "final",
            "args": {
                "content": content,
            },
        }

    def _final_content(self, action: dict[str, Any]) -> str:
        if action.get("tool") != "final":
            return ""

        args = action.get("args", {})
        if not isinstance(args, dict):
            return ""

        return str(args.get("content", ""))

    def _is_low_quality_final(self, response: str) -> bool:
        normalized = response.strip().lower()
        technical_tokens = {
            "",
            "final",
            "tool",
            "json",
            "reponse finale",
            "réponse finale",
        }
        return normalized in technical_tokens

    def _is_tool_allowed(self, tool: Tool, user_input: str) -> bool:
        if not tool.trigger_words:
            return True

        normalized = user_input.lower()
        return any(marker in normalized for marker in tool.trigger_words)

    def _available_tool_names(self) -> str:
        names = [tool.name for tool in self.tools.list_tools()]
        if not names:
            return "aucun"
        return ", ".join(names)

    def _unknown_requested_tool(self, user_input: str) -> str | None:
        match = re.search(r"\btool\s+([a-zA-Z_][a-zA-Z0-9_-]*)", user_input)
        if not match:
            return None

        tool_name = match.group(1)
        if self.tools.get(tool_name):
            return None

        return tool_name

    def _learn_long_term_facts(self, user_input: str) -> None:
        if not self.memory:
            return

        patterns = (
            r"\bmon nom est\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '’-]{1,60})",
            r"\bje m'appelle\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '’-]{1,60})",
            r"\bje m appelle\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '’-]{1,60})",
            r"\bappelle-moi\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '’-]{1,60})",
        )
        for pattern in patterns:
            match = re.search(pattern, user_input, flags=re.IGNORECASE)
            if not match:
                continue

            name = match.group(1).strip(" .,!?:;")
            if not name:
                continue

            self.memory.remember(
                key="user.name",
                value=name,
                text=f"Le nom de l'utilisateur est {name}.",
            )
            return

    def _answer_from_memory(self, user_input: str) -> str | None:
        if not self.memory:
            return None

        normalized = user_input.lower()
        asks_name = (
            "mon nom" in normalized
            or "je m'appelle comment" in normalized
            or "je m appelle comment" in normalized
            or "qui je suis" in normalized
            or "qui suis-je" in normalized
        )
        if not asks_name:
            return None

        name = self.memory.get("user.name")
        if not name:
            return "Je ne connais pas encore ton nom."

        return f"Ton nom est {name.value}."

    def _fill_missing_tool_args(
        self,
        tool: Tool,
        args: dict[str, Any],
        user_input: str,
    ) -> dict[str, Any]:
        if tool.name == "calculator" and not args.get("expression"):
            return {
                **args,
                "expression": self._extract_calculation_expression(user_input),
            }

        if tool.name == "text_stats" and not args.get("text"):
            return {
                **args,
                "text": self._extract_text_payload(user_input),
            }

        if tool.name != "echo" or args.get("text"):
            return args

        return {
            **args,
            "text": self._extract_text_payload(user_input),
        }

    def _extract_text_payload(self, user_input: str) -> str:
        text = user_input
        for separator in (":", "->"):
            if separator in text:
                text = text.split(separator, 1)[1]
                break

        cleaned = text.strip()
        if cleaned.lower().startswith("echo"):
            cleaned = cleaned[4:].strip()
        if cleaned.lower().startswith("repete exactement"):
            cleaned = cleaned[len("repete exactement") :].strip()
        if cleaned.lower().startswith("répète exactement"):
            cleaned = cleaned[len("répète exactement") :].strip()

        return cleaned

    def _extract_calculation_expression(self, user_input: str) -> str:
        expression = user_input.lower()
        prefixes = (
            "calcule",
            "calcul",
            "combien font",
            "combien fait",
        )
        for prefix in prefixes:
            if expression.startswith(prefix):
                expression = expression[len(prefix) :]
                break

        expression = expression.replace("?", "").replace("=", "")
        return expression.strip()

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
            *[
                {"role": message.role, "content": message.content}
                for message in self.state.messages
            ],
            {"role": "user", "content": instruction},
        ]

        raw = await self.llm.chat(messages)
        action = self._parse_action(raw)
        response = self._final_content(action)

        if response:
            return response

        return "Je peux te repondre directement, sans utiliser de tool."

    async def _run_tool(
        self,
        tool: Tool,
        args: dict[str, Any],
        user_input: str,
        system_prompt: str,
    ) -> str:
        args = self._fill_missing_tool_args(tool, args, user_input)
        result = await tool.execute(**args)

        if tool.return_direct:
            return str(result)

        self.add_assistant_message(f"[tool:{tool.name}] {result}")
        return await self._force_final_response(
            system_prompt,
            (
                f'Observation du tool "{tool.name}": {result}. '
                'Utilise cette observation pour repondre a l utilisateur.'
            ),
        )

    async def run(self, user_input: str) -> str:
        self.logger.info("Agent runtime started")

        self.add_user_message(user_input)
        self._learn_long_term_facts(user_input)
        memory_response = self._answer_from_memory(user_input)
        if memory_response:
            self.add_assistant_message(memory_response)
            self._trim_history()
            self.logger.info("Agent runtime finished")
            return memory_response

        system_prompt = self._build_system_prompt(user_input)
        unknown_tool = self._unknown_requested_tool(user_input)

        if unknown_tool:
            response = (
                f'Je n\'ai pas acces au tool "{unknown_tool}". '
                f"Tools disponibles: {self._available_tool_names()}."
            )
            self.add_assistant_message(response)
            self._trim_history()
            self.logger.info("Agent runtime finished")
            return response

        raw = await self.llm.chat(self._build_messages(system_prompt))
        action = self._parse_action(raw)

        tool_name = action.get("tool")
        args = action.get("args", {})
        if not isinstance(args, dict):
            args = {}

        if tool_name == "final":
            response = self._final_content(action)
            if self._is_low_quality_final(response):
                response = await self._force_final_response(
                    system_prompt,
                    "La reponse precedente est un marqueur technique. "
                    "Reponds vraiment a la demande de l utilisateur.",
                )
        else:
            tool = self.tools.get(str(tool_name))

            if not tool:
                response = (
                    f'Je n\'ai pas acces au tool "{tool_name}". '
                    f"Tools disponibles: {self._available_tool_names()}."
                )
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
                )

        if not response:
            response = raw.strip()

        self.add_assistant_message(response)
        self._trim_history()

        self.logger.info("Agent runtime finished")

        return response

    def reset(self) -> None:
        self.state = AgentState()
        self.logger.info("Agent state reset")
