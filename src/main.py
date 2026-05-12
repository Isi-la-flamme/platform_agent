from src.config.logging import setup_logging
from src.config.settings import get_settings
from src.infrastructure.logging.loguru_logger import LoguruLogger


async def main() -> None:
    setup_logging()

    settings = get_settings()

    logger = LoguruLogger()

    logger.info("Application starting...")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Model: {settings.OPENAI_MODEL}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())