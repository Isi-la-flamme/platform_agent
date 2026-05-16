import asyncio
import functools
import time
from typing import Any
from src.domain.protocols.tool import Tool, ToolProvider
from src.domain.protocols.logger import LoggerProtocol

class ToolExecutionError(Exception):
    pass

class ToolExecutor:
    def __init__(
        self, 
        tools: ToolProvider, 
        logger: LoggerProtocol,
        default_timeout: float = 5.0,
        allowed_tools: set[str] | None = None
    ) -> None:
        self.tools = tools
        self.logger = logger
        self.default_timeout = default_timeout
        self.allowed_tools = allowed_tools

    async def execute(self, tool_name: str, args: dict[str, Any], user_input: str) -> str:
        # 1. Vérification des Permissions
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            self.logger.warning(f"Tentative d'accès refusée : tool={tool_name}")
            raise ToolExecutionError(f"Permission refusée pour l'outil '{tool_name}'.")

        tool = self.tools.get(tool_name)
        if not tool:
            raise ToolExecutionError(f"Outil '{tool_name}' inconnu.")

        # 2. Audit Log (Audit Trailing)
        self.logger.info(f"[AUDIT] START | tool={tool_name} | args={args}")
        start_time = time.perf_counter()

        try:
            if hasattr(tool, "infer_args"):
                args = tool.infer_args(user_input, args)

            # Validation stricte des arguments par rapport au schéma de l'outil
            for arg_name in args.keys():
                if arg_name not in tool.args_schema:
                    raise ToolExecutionError(f"Argument '{arg_name}' invalide pour l'outil '{tool_name}'.")
            
            for req_arg in tool.args_schema.keys():
                if req_arg not in args:
                    raise ToolExecutionError(f"Argument manquant '{req_arg}' pour l'outil '{tool_name}'.")

            # 3. Exécution avec Timeout strict et isolation de thread
            # On utilise run_in_executor pour ne pas bloquer l'event loop si le tool est CPU-bound
            loop = asyncio.get_running_loop()
            
            # Si execute n'est pas déjà une coroutine, on l'enveloppe
            execute_func = functools.partial(tool.execute, **args)
            
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: asyncio.run(tool.execute(**args)) if asyncio.iscoroutinefunction(tool.execute) else tool.execute(**args)),
                timeout=self.default_timeout
            )
            
            duration = time.perf_counter() - start_time
            self.logger.info(f"[AUDIT] SUCCESS | tool={tool_name} | duration={duration:.3f}s")
            
            return str(result)

        except asyncio.TimeoutError:
            self.logger.error(f"Timeout sur l'outil {tool_name}")
            return f"Erreur : L'outil {tool_name} a dépassé le temps limite de {self.default_timeout}s."
        except Exception as e:
            self.logger.error(f"Erreur tool {tool_name}: {str(e)}")
            raise ToolExecutionError(f"Erreur d'exécution : {str(e)}")