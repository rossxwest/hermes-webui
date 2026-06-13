"""Tests: the served index.html contains the correct openui flag in __HERMES_CONFIG__.

Uses a _FakeHandler + handle_get() unit approach (same pattern as
test_dashboard_probe.py) so no live server is needed. Monkeypatches
api.config.get_config to return a controlled config dict.
"""
from urllib.parse import urlparse


class _FakeHandler:
    """Minimal stub that satisfies the handler interface used by routes.py helpers."""

    def __init__(self):
        self.status = None
        self.sent_headers = []
        self.body = bytearray()
        self.wfile = self
        # Minimal attributes that parse_cookie / auth helpers may inspect
        self.headers = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.sent_headers.append((name, value))

    def end_headers(self):
        pass

    def write(self, data):
        self.body.extend(data)

    def html_body(self):
        return bytes(self.body).decode("utf-8")


def _get_index_html(monkeypatch, config_data: dict) -> str:
    """Serve GET / with the given config_data and return the response HTML."""
    from api import config as _config_mod
    from api.routes import handle_get

    monkeypatch.setattr(_config_mod, "get_config", lambda: config_data)

    handler = _FakeHandler()
    parsed = urlparse("http://127.0.0.1:8787/")
    handle_get(handler, parsed)
    assert handler.status == 200, f"Expected 200, got {handler.status}"
    return handler.html_body()


def _strip_spaces(s: str) -> str:
    """Remove all ASCII whitespace so comparisons are whitespace-insensitive."""
    return "".join(s.split())


def test_openui_flag_is_false_by_default(monkeypatch):
    """When experimental.openui is absent, served index must have openui:false."""
    html = _get_index_html(monkeypatch, {})
    stripped = _strip_spaces(html)
    assert "openui:false" in stripped, (
        f"Expected 'openui:false' in stripped HTML, got fragment: "
        f"{stripped[max(0,stripped.find('openui')-20):stripped.find('openui')+40]!r}"
    )
    assert "__OPENUI_ENABLED__" not in html, (
        "Placeholder __OPENUI_ENABLED__ was not substituted in the served HTML"
    )


def test_openui_flag_is_true_when_experimental_openui_enabled(monkeypatch):
    """When experimental.openui is True, served index must have openui:true."""
    html = _get_index_html(monkeypatch, {"experimental": {"openui": True}})
    stripped = _strip_spaces(html)
    assert "openui:true" in stripped, (
        f"Expected 'openui:true' in stripped HTML, got fragment: "
        f"{stripped[max(0,stripped.find('openui')-20):stripped.find('openui')+40]!r}"
    )
    assert "__OPENUI_ENABLED__" not in html, (
        "Placeholder __OPENUI_ENABLED__ was not substituted in the served HTML"
    )


def test_openui_flag_false_when_experimental_openui_is_not_true(monkeypatch):
    """Truthy-but-not-True values (e.g. 1, 'yes') must NOT enable the flag."""
    for bad_val in (1, "yes", "true", True if False else 0):
        html = _get_index_html(monkeypatch, {"experimental": {"openui": bad_val}})
        stripped = _strip_spaces(html)
        assert "openui:false" in stripped, (
            f"openui:{bad_val!r} should yield openui:false, got: {stripped!r}"
        )
