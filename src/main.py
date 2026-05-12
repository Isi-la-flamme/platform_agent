from src.config.settings import get_settings


async def main() -> None:
    settings = get_settings()

    print(settings.APP_NAME)
    print(settings.APP_ENV)
    print(settings.OPENAI_MODEL)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())