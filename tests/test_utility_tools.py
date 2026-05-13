import re

import pytest

from src.infrastructure.tools.calculator_tool import CalculatorTool
from src.infrastructure.tools.datetime_tool import DateTimeTool
from src.infrastructure.tools.text_stats_tool import TextStatsTool


@pytest.mark.asyncio
async def test_calculator_evaluates_safe_math_expression() -> None:
    tool = CalculatorTool()

    result = await tool.execute(expression="2 + 3 * 4")

    assert result == "14"


@pytest.mark.asyncio
async def test_calculator_rejects_unsupported_expression() -> None:
    tool = CalculatorTool()

    result = await tool.execute(expression="__import__('os').system('dir')")

    assert result.startswith("Calcul impossible:")


@pytest.mark.asyncio
async def test_datetime_returns_current_utc_timestamp() -> None:
    tool = DateTimeTool()

    result = await tool.execute(timezone="UTC")

    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC", result)


@pytest.mark.asyncio
async def test_text_stats_counts_text() -> None:
    tool = TextStatsTool()

    result = await tool.execute(text="bonjour agent\nca va")

    assert result == "Caracteres: 19; Mots: 4; Lignes: 2"
