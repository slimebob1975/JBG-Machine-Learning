"""A readable run log for web runs (revision 300d, asked 2026-11-16).

The worker's output (the engine's console output and the worker's own
messages) becomes the run's log. Every line now starts with a timestamp and a
level, and empty lines are dropped (they were left from running in a
terminal):

    2026-11-18 14:03:12 INFO    -- Fetching data --
    2026-11-18 14:03:15 WARNING ConvergenceWarning: ...
    2026-11-18 14:05:40 ERROR   Traceback (most recent call last):

The level is read from the line: "[DEBUG]" gives DEBUG, a warning WARNING, an
error or traceback ERROR; otherwise INFO for normal output and ERROR for the
error stream. Only the web worker uses this; Voila's output is unchanged.
"""
from __future__ import annotations

import io
import re
from datetime import datetime

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
_ERROR = re.compile(r"traceback|\berror\b|exception|\[error\]", re.IGNORECASE)
_WARNING = re.compile(r"warning", re.IGNORECASE)


def level_of(line: str, default: str) -> str:
    if "[DEBUG]" in line:
        return "DEBUG"
    if _WARNING.search(line):
        return "WARNING"
    if _ERROR.search(line):
        return "ERROR"
    return default


class LineLogWriter(io.TextIOBase):
    """A text stream that writes whole lines with a timestamp and a level."""

    def __init__(self, stream, default_level: str = "INFO", clock=None) -> None:
        self._stream = stream
        self._default = default_level
        self._buffer = ""
        self._clock = clock or datetime.now

    @property
    def encoding(self):
        return getattr(self._stream, "encoding", "utf-8")

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        return self._stream.fileno()

    def write(self, text) -> int:
        if not isinstance(text, str):
            text = str(text)
        self._buffer += text.replace("\r\n", "\n").replace("\r", "\n")
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._emit(line)
        return len(text)

    def flush(self) -> None:
        if self._buffer:
            line, self._buffer = self._buffer, ""
            self._emit(line)
        self._stream.flush()

    def _emit(self, line: str) -> None:
        if not line.strip():
            return                                      # no empty lines
        stamp = self._clock().strftime("%Y-%m-%d %H:%M:%S")
        self._stream.write(f"{stamp} {level_of(line, self._default):<7} {line}\n")
        self._stream.flush()


def install(sys_module) -> None:
    """Wrap the process's output and error streams (the web worker only)."""
    if not isinstance(sys_module.stdout, LineLogWriter):
        sys_module.stdout = LineLogWriter(sys_module.stdout, "INFO")
    if not isinstance(sys_module.stderr, LineLogWriter):
        sys_module.stderr = LineLogWriter(sys_module.stderr, "ERROR")
