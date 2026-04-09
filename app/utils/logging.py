import logging
import sys

from pythonjsonlogger import jsonlogger


def setup_logging() -> None:
    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)