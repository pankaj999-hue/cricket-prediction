# backend/app/security_headers.py
"""Security response headers for the FastAPI app.

Attaches the OWASP-recommended headers to every response:
  - Content-Security-Policy (XSS / injection)
  - Strict-Transport-Security (HSTS, HTTPS-only)
  - X-Content-Type-Options (nosniff)
  - X-Frame-Options (clickjacking)
  - Referrer-Policy (referrer leakage)
  - Permissions-Policy (browser-feature lockdown)
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# The frontend loads Google Fonts (preconnect + stylesheet + font files) and
# uses inline `style="..."` attributes (JS-built DOM) — hence style-src keeps
# 'unsafe-inline' for styles only. No inline scripts are used, so script-src
# stays 'self' (no 'unsafe-inline') which is the important XSS win.
DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data:; "
    "font-src 'self' https://fonts.gstatic.com; "
    "connect-src 'self'; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)


def build_security_headers(csp: str = None, hsts: bool = False) -> dict:
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        ),
        "Content-Security-Policy": csp or DEFAULT_CSP,
    }
    if hsts:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Appends the security headers to every response."""

    def __init__(self, app, csp: str = None, hsts: bool = False):
        super().__init__(app)
        self._headers = build_security_headers(csp, hsts)

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        for key, value in self._headers.items():
            response.headers.setdefault(key, value)
        return response