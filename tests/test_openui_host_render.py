"""Integration test: the sandboxed openui host.html renders real openui-lang and
speaks the nonce postMessage protocol. Requires playwright + chromium.

Loads host.html as a top-level page (so `window.parent === window`, satisfying
host.html's source-identity check) and drives it via window.postMessage, exactly
as the real parent iframe will. Verifies:
  - a valid openui-lang program renders and the host reports a positive height
  - invalid openui-lang yields an openui:error (drives the parent's fallback)
  - no uncaught page errors
"""
import pathlib
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

HOST = (pathlib.Path(__file__).resolve().parents[1]
        / "static" / "vendor" / "openui" / "host.html").as_uri()

VALID = (
    'root = Card([header, body, tbl])\n'
    'header = CardHeader("Quarterly Revenue", "FY2026")\n'
    'body = TextContent("Revenue grew steadily across the year.", "default")\n'
    'tbl = Table(["Quarter", "Revenue"], [["Q1","$1.2M"],["Q2","$1.5M"],["Q3","$1.9M"],["Q4","$2.4M"]])\n'
)
INVALID = "this is plainly not openui-lang at all"

_DRIVE = r"""
async ({code, nonce}) => {
  return await new Promise((resolve) => {
    const done = (v) => resolve(v);
    window.addEventListener('message', (ev) => {
      const d = ev.data;
      if (!d || d.nonce !== nonce) return;
      if (d.type === 'openui:height') done({kind:'height', px:d.px});
      else if (d.type === 'openui:error') done({kind:'error', message:d.message});
    });
    // host.html attaches its listener at load; send the init directly.
    window.postMessage({type:'openui:init', nonce, code}, '*');
    setTimeout(() => done({kind:'timeout'}), 5000);
  });
}
"""


def _run(code, nonce):
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = b.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(HOST)
            result = page.evaluate(_DRIVE, {"code": code, "nonce": nonce})
        finally:
            b.close()
    return result, errors


@pytest.mark.integration
def test_valid_openui_lang_renders_and_reports_height():
    result, errors = _run(VALID, "nonce-valid-1")
    assert result["kind"] == "height", result
    assert result["px"] > 0, result
    assert errors == [], errors


@pytest.mark.integration
def test_invalid_openui_lang_reports_error():
    result, _ = _run(INVALID, "nonce-invalid-1")
    assert result["kind"] == "error", result
