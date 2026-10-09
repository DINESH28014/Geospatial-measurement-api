import logging
import sys

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configures structured logging for the application."""
    logger = logging.getLogger("geospatial_api")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d]: %(message)s"
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

logger = setup_logging()
