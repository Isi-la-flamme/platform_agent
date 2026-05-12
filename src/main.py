from src.config.container import Container
from src.config.logging import setup_logging


async def main() -> None:
    setup_logging()

    container = Container()

    logger = container.logger()
    llm = container.llm_provider()

    logger.info("Testing Groq/OpenAI provider...")

    response = await llm.generate("Explique Python en une phrase.")
    logger.info(response)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())