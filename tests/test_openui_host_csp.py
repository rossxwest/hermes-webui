"""
Tests for CSP sandbox on the openui host.html renderer.

GET /static/vendor/openui/host.html must respond with
  Content-Security-Policy: sandbox allow-scripts

so that even a direct navigation to that URL cannot grant same-origin
access to the app. The sibling subresource files (openui-styles.css,
openui-bundle.min.js) must NOT carry the sandbox CSP — they are
subresources fetched by the sandboxed document, not HTML entry points.

Implementation uses _serve_static in api/routes.py (no live server needed —
mirrors the pattern in test_static_asset_compression_and_cache.py).
"""
from pathlib import Path
from urllib.parse import urlparse


# ── Minimal fake HTTP handler (same shape as sibling tests) ──────────────────

class _FakeHandler:
    def __init__(self, request_headers=None):
        self.status = None
        self.sent_headers: list[tuple[str, str]] = []
        self.body = bytearray()
        self.wfile = self
        self.headers = dict(request_headers or {})

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, name: str, value: str) -> None:
        self.sent_headers.append((name, value))

    def end_headers(self) -> None:
        pass

    def write(self, data: bytes) -> None:
        self.body.extend(data)

    def header(self, name: str) -> str | None:
        """Return the first response header value matching *name* (case-insensitive)."""
        needle = name.lower()
        for k, v in self.sent_headers:
            if k.lower() == needle:
                return v
        return None


# ── Helper: drive _serve_static against the REAL static/ tree ────────────────

def _serve(path: str, query: str = "", request_headers=None):
    from api import routes
    parsed = urlparse(f"http://localhost{path}{('?' + query) if query else ''}")
    h = _FakeHandler(request_headers)
    routes._serve_static(h, parsed)
    return h


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_openui_host_html_has_sandbox_csp():
    """host.html must be served with Content-Security-Policy: sandbox allow-scripts."""
    h = _serve("/static/vendor/openui/host.html")
    assert h.status == 200, f"Expected 200, got {h.status}"
    csp = h.header("Content-Security-Policy")
    assert csp == "sandbox allow-scripts", (
        f"Expected 'Content-Security-Policy: sandbox allow-scripts', got {csp!r}. "
        "The openui renderer must be sandboxed so direct navigation cannot grant "
        "same-origin access to the app."
    )


def test_openui_styles_css_has_no_sandbox_csp():
    """openui-styles.css must NOT carry the sandbox CSP — it is a subresource."""
    h = _serve("/static/vendor/openui/openui-styles.css")
    assert h.status == 200, f"Expected 200, got {h.status}"
    csp = h.header("Content-Security-Policy")
    assert csp != "sandbox allow-scripts", (
        "openui-styles.css must not have sandbox CSP — only host.html needs it."
    )


def test_openui_bundle_js_has_no_sandbox_csp():
    """openui-bundle.min.js must NOT carry the sandbox CSP — it is a subresource."""
    h = _serve("/static/vendor/openui/openui-bundle.min.js")
    assert h.status == 200, f"Expected 200, got {h.status}"
    csp = h.header("Content-Security-Policy")
    assert csp != "sandbox allow-scripts", (
        "openui-bundle.min.js must not have sandbox CSP — only host.html needs it."
    )
