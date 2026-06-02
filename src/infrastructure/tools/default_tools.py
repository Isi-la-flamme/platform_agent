from src.infrastructure.tools.calculator_tool import CalculatorTool
from src.infrastructure.tools.datetime_tool import DateTimeTool
from src.infrastructure.tools.echo_tool import EchoTool
from src.infrastructure.tools.crypto_price_tool import CryptoPriceTool
from src.infrastructure.tools.file_crud_tool import FileCrudTool
from src.infrastructure.tools.file_list_tool import FileListTool
from src.infrastructure.tools.python_code_tool import PythonCodeTool
from src.infrastructure.tools.google_search_tool import GoogleSearchTool
from src.infrastructure.tools.text_stats_tool import TextStatsTool
from src.infrastructure.tools.tool_registry import ToolRegistry


def register_default_tools(registry: ToolRegistry) -> None:
    registry.register(EchoTool())
    registry.register(CalculatorTool())
    registry.register(DateTimeTool())
    registry.register(CryptoPriceTool())
    registry.register(FileCrudTool())
    registry.register(FileListTool())
    registry.register(PythonCodeTool())
    registry.register(GoogleSearchTool())
    registry.register(TextStatsTool())
