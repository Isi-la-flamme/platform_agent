from src.infrastructure.tools.calculator_tool import CalculatorTool
from src.infrastructure.tools.datetime_tool import DateTimeTool
from src.infrastructure.tools.echo_tool import EchoTool
from src.infrastructure.tools.text_stats_tool import TextStatsTool
from src.infrastructure.tools.tool_registry import ToolRegistry


def register_default_tools(registry: ToolRegistry) -> None:
    registry.register(EchoTool())
    registry.register(CalculatorTool())
    registry.register(DateTimeTool())
    registry.register(TextStatsTool())
