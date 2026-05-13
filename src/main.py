import asyncio

from src.application.orchestrators.agent_runtime import AgentRuntime
from src.config.container import Container
from src.config.logging import setup_logging
from src.infrastructure.tools.echo_tool import EchoTool


async def main() -> None:
    setup_logging()

    container = Container()

    registry = container.tool_registry()
    registry.register(EchoTool())

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
