from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import time

from fastapi import HTTPException, status


@dataclass(frozen=True, slots=True)
class RateRule:
    limit: int
    window_seconds: int


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str, *, rule: RateRule) -> tuple[bool, int]:
        now = time()
        floor = now - rule.window_seconds

        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= floor:
                bucket.popleft()

            if len(bucket) >= rule.limit:
                retry_after = int(max(1, bucket[0] + rule.window_seconds - now))
                return False, retry_after

            bucket.append(now)
            return True, 0


_RULES: dict[str, RateRule] = {
    'viewer_session': RateRule(limit=12, window_seconds=10 * 60),
    'reservation': RateRule(limit=80, window_seconds=60 * 60),
    'contribution': RateRule(limit=45, window_seconds=60 * 60),
}

_limiter = SlidingWindowLimiter()


def enforce_public_action_limit(action: str, key_suffix: str) -> None:
    rule = _RULES.get(action)
    if not rule:
        return

    allowed, retry_after = _limiter.hit(f'{action}:{key_suffix}', rule=rule)
    if allowed:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f'Rate limit exceeded. Retry in {retry_after}s',
    )
