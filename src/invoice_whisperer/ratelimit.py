"""Sliding-window token budget: keeps us under Groq's tokens-per-minute limit."""
import time
from collections import deque
from typing import Callable


class TokenBudget:
    """Tracks tokens used in the last 60s and tells us how long to wait."""

    def __init__(self, tokens_per_minute: int, safety: float = 0.95,
                 min_gap: float = 0.0, default_estimate: int = 2500,
                 clock: Callable[[], float] = time.monotonic,
                 sleeper: Callable[[float], None] = time.sleep) -> None:
        self.budget = tokens_per_minute * safety
        self.min_gap = min_gap
        self.estimate = default_estimate          # expected tokens for the next call
        self._clock, self._sleep = clock, sleeper
        self._window: deque[tuple[float, int]] = deque()   # (time, tokens)
        self._recent: deque[int] = deque(maxlen=5)         # last observed call sizes

    def _prune(self, now: float) -> None:
        while self._window and now - self._window[0][0] >= 60:
            self._window.popleft()

    def wait_time(self) -> float:
        """Seconds to wait before the next call fits in budget (0 = go now)."""
        now = self._clock()
        self._prune(now)
        gap = max(0.0, self._window[-1][0] + self.min_gap - now) if self._window else 0.0
        remaining = sum(tok for _, tok in self._window)
        if remaining + self.estimate <= self.budget:
            return gap
        for t, tok in self._window:               # oldest first: when does enough expire?
            remaining -= tok
            if remaining + self.estimate <= self.budget:
                return max(gap, t + 60 - now)
        return max(gap, 60.0)

    def acquire(self) -> None:
        """Block until the next call fits within the per-minute token budget."""
        w = self.wait_time()
        if w > 0:
            print(f"  waiting {w:.0f}s (token budget)...")
            self._sleep(w)

    def record(self, tokens: int) -> None:
        """Log a finished call and refine the estimate (max of last 5, +5%)."""
        self._window.append((self._clock(), tokens))
        self._recent.append(tokens)
        self.estimate = int(max(self._recent) * 1.05)
