from dependency_injector import containers, providers

from src.config.settings import get_settings
from src.infrastructure.logging.loguru_logger import LoguruLogger
from src.infrastructure.llm.openai_provider import OpenAIProvider
from src.infrastructure.llm.groq_provider import GroqProvider


class Container(containers.DeclarativeContainer):

    settings = providers.Singleton(get_settings)

    logger = providers.Singleton(LoguruLogger)

    llm_provider = providers.Selector(
        settings.provided.APP_ENV,
        development=providers.Factory(
            GroqProvider,
            api_key=providers.Callable(
                lambda s: s.GROQ_API_KEY.get_secret_value(),
                settings,
            ),
            model=providers.Callable(lambda s: s.GROQ_MODEL, settings),
            logger=logger,
        ),
        testing=providers.Factory(
            GroqProvider,
            api_key=providers.Callable(
                lambda s: s.GROQ_API_KEY.get_secret_value(),
                settings,
            ),
            model=providers.Callable(lambda s: s.GROQ_MODEL, settings),
            logger=logger,
        ),
        production=providers.Factory(
            OpenAIProvider,
            api_key=providers.Callable(
                lambda s: s.OPENAI_API_KEY.get_secret_value(),
                settings,
            ),
            model=providers.Callable(lambda s: s.OPENAI_MODEL, settings),
            logger=logger,
        ),
    )