# backend/app/rate_limit.py
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Sliding-window rate limiter keyed by an arbitrary string (e.g. client IP)."""

    def __init__(self, max_requests: int, window_seconds: int, name: str = "rate"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True


# Limits
PREDICT_LIMITER = RateLimiter(
    max_requests=20, window_seconds=60, name="predict"
)
LOGIN_LIMITER = RateLimiter(
    max_requests=5, window_seconds=300, name="login"
)
AUTH_LIMITER = RateLimiter(
    max_requests=60, window_seconds=60, name="auth"
)


def _client_key(request: Request) -> str:
    """Client identity for rate limiting.

    IMPORTANT: do NOT trust the X-Forwarded-For header here. It is supplied by
    the client and can be spoofed to reset the limiter (brute-force bypass).
    When the app runs directly behind uvicorn there is no proxy to sanitise it,
    so we key on the real connection peer (request.client.host), which the
    network stack controls. If you later deploy behind a trusted reverse proxy,
    that proxy MUST strip/overwrite X-Forwarded-For itself.
    """
    return request.client.host if request.client else "unknown"


def check_rate(limiter: RateLimiter, request: Request) -> None:
    if not limiter.allow(_client_key(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: too many {limiter.name} requests. Try again later.",
        )


def check_predict(request: Request) -> None:
    check_rate(PREDICT_LIMITER, request)


def check_login(request: Request) -> None:
    check_rate(LOGIN_LIMITER, request)


def check_auth(request: Request) -> None:
    check_rate(AUTH_LIMITER, request)


# ---------------------------------------------------------------------------
# Per-account login lockout (anti brute-force, independent of client IP)
# ---------------------------------------------------------------------------
class AccountLockout:
    """Tracks failed login attempts per email address.

    After max_failures failed logins within the window, the *email* is blocked
    for cooldown_seconds. This cannot be bypassed by spoofing / rotating client
    IPs, which defeats the per-IP limiter for one victim account.
    """

    def __init__(self, max_failures: int = 5, cooldown_seconds: int = 900):
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        self._fails: dict[str, deque] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}
        self._lock = Lock()

    def is_blocked(self, email: str) -> bool:
        """True if the email is currently in a cooldown lockout."""
        with self._lock:
            until = self._blocked_until.get(email, 0)
            if time.monotonic() < until:
                return True
            if until:
                self._blocked_until.pop(email, None)
            return False

    def record_failure(self, email: str) -> None:
        now = time.monotonic()
        with self._lock:
            fails = self._fails[email]
            cutoff = now - 60 * 60  # keep one hour of history
            while fails and fails[0] <= cutoff:
                fails.popleft()
            fails.append(now)
            if len(fails) >= self.max_failures:
                self._blocked_until[email] = now + self.cooldown_seconds
                self._fails.pop(email, None)

    def record_success(self, email: str) -> None:
        with self._lock:
            self._fails.pop(email, None)
            self._blocked_until.pop(email, None)


LOGIN_LOCKOUT = AccountLockout(max_failures=5, cooldown_seconds=900)