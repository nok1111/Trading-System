"""Logging estructurado con redacción de secretos."""

import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

from app.config import get_settings


class SecretRedactingFilter(logging.Filter):
    """Filtro que reemplaza valores sensibles en los mensajes de log."""

    SECRET_NAMES = ("BROKER_API_KEY", "BROKER_API_SECRET")

    def filter(self, record: logging.LogRecord) -> bool:
        settings = get_settings()
        message = self._get_message(record)
        for name in self.SECRET_NAMES:
            value = getattr(settings, name, None)
            if value and isinstance(value, str):
                message = message.replace(value, "***REDACTED***")
        record.msg = message
        record.args = ()
        return True

    def _get_message(self, record: logging.LogRecord) -> str:
        try:
            return record.getMessage()
        except Exception:  # noqa: BLE001
            return str(record.msg)


def configure_logging(level: str | None = None, json_format: bool | None = None) -> None:
    """Configura el logger raíz con formato plano o JSON.

    Args:
        level: Nivel de logging. Si es None se usa el de la configuración.
        json_format: Si es True usa JSON, si es None usa la configuración.
    """
    settings = get_settings()
    effective_level = (level or settings.LOG_LEVEL).upper()
    use_json = json_format if json_format is not None else settings.JSON_LOGS

    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if use_json:
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            rename_fields={"message": "msg"},
        )
    else:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(getattr(logging, effective_level, logging.INFO))
    root.addFilter(SecretRedactingFilter())


def get_logger(name: str) -> logging.Logger:
    """Obtiene un logger configurado."""
    return logging.getLogger(name)


def log_structured(
    logger: logging.Logger,
    level: str,
    message: str,
    **kwargs: Any,
) -> None:
    """Escribe un log estructurado usando el formatter JSON si está activo.

    Los argumentos adicionales se añaden como campos extra.
    """
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, extra=kwargs)
