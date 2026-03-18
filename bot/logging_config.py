import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(
    level: int = logging.INFO,
    log_file: str = "logs/app.log",
    max_bytes: int = 1_048_576,
    backup_count: int = 3,
) -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    file_handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
