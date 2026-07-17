import json
import logging
from typing import List


class LogCollector:
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._logs: List[str] = []

    def info(self, msg: str) -> None:
        self._logger.info(msg)
        self._logs.append(msg)

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)
        self._logs.append(f"WARN: {msg}")

    def error(self, msg: str) -> None:
        self._logger.error(msg)
        self._logs.append(f"ERROR: {msg}")

    def collect(self, result_str: str) -> str:
        try:
            d = json.loads(result_str)
            if isinstance(d, dict):
                d["_logs"] = list(self._logs)
                return json.dumps(d, indent=2, default=str)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return result_str
