"""301w (asked 2026-11-27): how many processes a run uses and how much memory.

The run's worker samples its own process tree (itself and the processes it
starts, such as parallel cross-validation workers) every five seconds
(decided 2026-11-27) and writes one JSON line per sample to
``resources.jsonl`` in the run's folder. The Training tab draws the samples
while the run has no results yet; the Overview shows each recent run's peak
memory, peak processes and duration.

Memory is the sum of the processes' resident memory (RSS), so memory shared
between them is counted more than once: a ceiling, not an exact figure.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

INTERVAL = 5.0                       # seconds (decided 2026-11-27)
FILENAME = "resources.jsonl"


def sample(process=None) -> dict:
    """The process tree now: number of processes and their memory in MB."""
    import psutil
    root = process or psutil.Process(os.getpid())
    tree = [root]
    try:
        tree += root.children(recursive=True)
    except psutil.Error:
        pass
    memory = 0
    alive = 0
    for proc in tree:
        try:
            memory += proc.memory_info().rss
            alive += 1
        except psutil.Error:
            continue
    return {"processes": alive, "memory_mb": round(memory / (1024 * 1024), 1)}


class ResourceSampler:
    """A daemon thread that appends a sample every ``interval`` seconds while
    the run lasts, with one at the start and one at the end. Never lets a
    failure reach the run."""

    def __init__(self, folder: Path | None, interval: float = INTERVAL):
        self._path = Path(folder) / FILENAME if folder is not None else None
        self._interval = interval
        self._stop = threading.Event()
        self._thread = None
        self._start = time.monotonic()

    def _write(self):
        if self._path is None:
            return
        try:
            found = sample()
            found.update(t=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         s=round(time.monotonic() - self._start, 1))
            with self._path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(found) + "\n")
        except Exception:
            pass

    def _loop(self):
        while not self._stop.wait(self._interval):
            self._write()

    def __enter__(self):
        if self._path is not None:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                self._path = None
        self._write()
        self._thread = threading.Thread(target=self._loop, name="jbg-resources", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._write()
        return False


def read(folder: Path) -> list:
    path = Path(folder) / FILENAME
    if not path.is_file():
        return []
    samples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            samples.append(json.loads(line))
        except ValueError:
            continue
    return samples


def summary(samples: list) -> dict | None:
    if not samples:
        return None
    return {"peak_memory_mb": max(s.get("memory_mb", 0) for s in samples),
            "peak_processes": max(s.get("processes", 0) for s in samples),
            "duration_s": max(s.get("s", 0) for s in samples),
            "samples": len(samples)}
