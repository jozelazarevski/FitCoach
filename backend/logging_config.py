"""Structured logging configuration for FitCoach."""

import json
import logging
import sys
import time
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production use."""

    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry['exception'] = self.formatException(record.exc_info)
        # Include extra fields if present
        for key in ('request_id', 'user_id', 'endpoint', 'method', 'status_code', 'duration_ms', 'client_ip'):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        return json.dumps(log_entry)


class DevFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    def __init__(self):
        super().__init__('%(asctime)s %(levelname)-8s [%(name)s] %(message)s', datefmt='%H:%M:%S')


def setup_logging(env='production'):
    """Configure logging based on environment.

    Args:
        env: 'production' for JSON logs, 'development' for human-readable.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if env == 'production':
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(DevFormatter())

    root.addHandler(handler)

    # Suppress noisy libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
