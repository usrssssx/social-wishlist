from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import time


@dataclass(frozen=True, slots=True)
class MonitoringSnapshot:
    requests_last_5m: int
    errors_4xx_last_5m: int
    errors_5xx_last_5m: int


class RollingRequestMonitor:
    def __init__(self, window_seconds: int = 300) -> None:
        self.window_seconds = window_seconds
        self._all: deque[float] = deque()
        self._errors_4xx: deque[float] = deque()
        self._errors_5xx: deque[float] = deque()
        self._lock = Lock()

    def _trim(self, now: float) -> None:
        floor = now - self.window_seconds
        while self._all and self._all[0] <= floor:
            self._all.popleft()
        while self._errors_4xx and self._errors_4xx[0] <= floor:
            self._errors_4xx.popleft()
        while self._errors_5xx and self._errors_5xx[0] <= floor:
            self._errors_5xx.popleft()

    def record(self, status_code: int) -> None:
        now = time()
        with self._lock:
            self._trim(now)
            self._all.append(now)
            if 400 <= status_code < 500:
                self._errors_4xx.append(now)
            elif status_code >= 500:
                self._errors_5xx.append(now)

    def snapshot(self) -> MonitoringSnapshot:
        now = time()
        with self._lock:
            self._trim(now)
            return MonitoringSnapshot(
                requests_last_5m=len(self._all),
                errors_4xx_last_5m=len(self._errors_4xx),
                errors_5xx_last_5m=len(self._errors_5xx),
            )


monitor = RollingRequestMonitor()
