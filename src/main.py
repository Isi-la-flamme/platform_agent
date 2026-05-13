import asyncio

from src.config.container import Container
from src.infrastructure.tools.echo_tool import EchoTool
from src.application.orchestrators.agent_runtime import AgentRuntime
from src.config.logging import setup_logging

async def main():
    setup_logging()

    container = Container()

    registry = container.tool_registry()
    registry.register(EchoTool())

    agent = AgentRuntime(
        llm=container.llm_provider(),
        logger=container.logger(),
        tools=registry,
    )

    print("Agent ready.")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You > ")

        if user_input.lower() in ["exit", "quit"]:
            break

        try:
            response = await agent.run(user_input)

            print(f"\nAgent > {response}\n")

        except Exception as e:
            print(f"\nError > {e}\n")


if __name__ == "__main__":
    asyncio.run(main())