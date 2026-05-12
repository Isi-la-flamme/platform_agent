from src.config.container import Container
from src.config.logging import setup_logging


async def main() -> None:
    setup_logging()

    container = Container()

    settings = container.settings()
    logger = container.logger()

    logger.info("System booting...")
    logger.info(f"Env: {settings.APP_ENV}")
    logger.info(f"Model: {settings.OPENAI_MODEL}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())