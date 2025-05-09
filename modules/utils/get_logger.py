import logging
import os


def get_logger(
    name: str,
    level: int = logging.WARNING,
    date_format: str = "%d/%m/%Y %H:%M:%S",
    format: str = "%(asctime)s %(levelname)s %(funcName)s %(message)s",
    file_name: str = None,
):
    logger = logging.getLogger(name=name)
    logger.setLevel(level=level)
    formatter = logging.Formatter(fmt=format, datefmt=date_format)
    if file_name is not None:
        dirname = os.path.dirname(file_name)
        os.makedirs(dirname, exist_ok=True)
        file_handler = logging.FileHandler(filename=file_name, mode="w", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger
