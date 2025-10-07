import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            stream = self.stream
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                enc = getattr(stream, "encoding", "utf-8") or "utf-8"
                safe = (msg + self.terminator).encode(enc, errors="replace").decode(enc, errors="replace")
                stream.write(safe)
            self.flush()
        except Exception:
            self.handleError(record)


def setup_logger(level: str = "INFO", log_file: str = "trading_bot.log") -> logging.Logger:
    logger = logging.getLogger("bybit_trading_bot")
    if logger.handlers:
        return logger

    logger.setLevel(level.upper())
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = SafeStreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("Logger initialized")
    return logger


def log_signal(logger: logging.Logger, payload: dict) -> None:
    logger.info(f"Signal received: {payload}")


def log_order(logger: logging.Logger, info: dict) -> None:
    logger.info(f"Order event: {info}")


def log_error(logger: logging.Logger, msg: str, extra: Optional[dict] = None) -> None:
    if extra:
        logger.error(f"{msg} | extra={extra}")
    else:
        logger.error(msg)


