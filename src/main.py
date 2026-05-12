from src.config.container import Container
from src.config.logging import setup_logging


async def main() -> None:
    setup_logging()

    container = Container()

    agent = container.agent_runtime()

    response1 = await agent.run("Qui es-tu ?")
    print(response1)

    response2 = await agent.run("Explique Python simplement")
    print(response2)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())