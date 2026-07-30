import logging
from .config import settings
LOG_LEVEL = settings.LOG_LEVEL
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")