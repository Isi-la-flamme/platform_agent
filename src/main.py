import asyncio

from src.application.orchestrators.agent_runtime import AgentRuntime
from src.config.container import Container
from src.config.logging import setup_logging
from src.infrastructure.tools.default_tools import register_default_tools


async def main() -> None:
    setup_logging()

    container = Container()

    registry = container.tool_registry()
    register_default_tools(registry)

    agent: AgentRuntime = container.agent_runtime()

    print("Agent ready.")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You > ")

        if user_input.lower() in ["exit", "quit"]:
            break

        try:
            response = await agent.run(user_input)

            print(f"\nAgent > {response}\n")

        except Exception as exc:
            print(f"\nError > {exc}\n")


if __name__ == "__main__":
    asyncio.run(main())
