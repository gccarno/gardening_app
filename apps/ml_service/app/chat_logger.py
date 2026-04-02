import json
import logging
from datetime import datetime, timezone
from pathlib import Path


def create_session_logger(session_id: str, logs_root: str) -> logging.Logger:
    chat_dir = Path(logs_root) / 'chat'
    chat_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime('%Y-%m-%d')
    log_path = chat_dir / f'{date_str}_session_{session_id}.log'

    logger = logging.getLogger(f'chat.{session_id}')
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)

    return logger


def log_event(logger: logging.Logger, event: str, **kwargs) -> None:
    payload = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'event': event,
        **kwargs,
    }
    logger.info(json.dumps(payload, default=str))


def close_session_logger(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        handler.flush()
        handler.close()
        logger.removeHandler(handler)
