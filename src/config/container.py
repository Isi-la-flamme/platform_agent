from dependency_injector import containers, providers

from src.config.settings import get_settings
from src.infrastructure.logging.loguru_logger import LoguruLogger


class Container(containers.DeclarativeContainer):
    # SETTINGS (singleton)
    settings = providers.Singleton(get_settings)

    # LOGGER (singleton)
    logger = providers.Singleton(LoguruLogger)