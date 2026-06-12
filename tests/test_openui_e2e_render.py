"""End-to-end: the real frontend render hook (ui.js highlightCode →
_renderOpenuiBlocks) swaps a `code.language-openui` block for a sandboxed iframe
that loads the server-served host.html and renders real openui-lang, reporting a
positive height back across the postMessage boundary.

Exercises the full parent+iframe integration against a live server (the
node-extraction tests only cover the pure helpers; A4 only covers host.html in
isolation). Requires playwright + chromium.
"""
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

FIXTURE = (
    'root = Card([header, body, tbl])\n'
    'header = CardHeader("Quarterly Revenue", "FY2026")\n'
    'body = TextContent("Revenue grew steadily across the year.", "default")\n'
    'tbl = Table(["Quarter", "Revenue"], [["Q1","$1.2M"],["Q2","$1.5M"],["Q3","$1.9M"],["Q4","$2.4M"]])\n'
)

# Build the block, enable the flag, run the real highlightCode, return nothing.
_MOUNT = r"""
(code) => {
  window.__HERMES_CONFIG__ = window.__HERMES_CONFIG__ || {};
  window.__HERMES_CONFIG__.openui = true;
  const wrap = document.createElement('div');
  wrap.id = 'openui-e2e';
  const pre = document.createElement('pre');
  const codeEl = document.createElement('code');
  codeEl.className = 'language-openui';
  codeEl.textContent = code;       // real text, no escaping issues
  pre.appendChild(codeEl);
  wrap.appendChild(pre);
  document.body.appendChild(wrap);
  // The real production hook:
  highlightCode(wrap);
}
"""


@pytest.mark.integration
def test_render_hook_mounts_iframe_card_and_renders(base_url):
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = b.new_page()
            page.goto(base_url, wait_until="domcontentloaded")
            # ui.js is a deferred classic script — wait until highlightCode exists.
            page.wait_for_function("typeof highlightCode === 'function'", timeout=15000)
            page.evaluate(_MOUNT, FIXTURE)
            # The <pre> must have been replaced by an .openui-card with an iframe.
            card_iframe = page.locator("#openui-e2e .openui-card iframe.openui-card__frame")
            card_iframe.wait_for(state="attached", timeout=5000)
            assert page.locator("#openui-e2e pre").count() == 0, "original <pre> should be swapped out"
            # The iframe loads host.html, renders, and posts a positive height back,
            # which the parent applies to frame.style.height.
            page.wait_for_function(
                """() => {
                    const f = document.querySelector('#openui-e2e iframe.openui-card__frame');
                    if (!f) return false;
                    const h = parseInt(f.style.height || '0', 10);
                    return h > 40;
                }""",
                timeout=10000,
            )
            height = page.evaluate(
                "parseInt(document.querySelector('#openui-e2e iframe.openui-card__frame').style.height||'0',10)")
            assert height > 40, "expected a rendered openui card height, got %r" % height
        finally:
            b.close()


@pytest.mark.integration
def test_render_hook_falls_back_to_code_block_on_invalid(base_url):
    """Invalid openui-lang → host posts openui:error → parent restores the <pre>."""
    invalid = "this is plainly not openui-lang at all"
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = b.new_page()
            page.goto(base_url, wait_until="domcontentloaded")
            page.wait_for_function("typeof highlightCode === 'function'", timeout=15000)
            page.evaluate(_MOUNT, invalid)
            # It mounts an iframe first, then falls back once the error arrives.
            page.wait_for_function(
                """() => {
                    const root = document.getElementById('openui-e2e');
                    return root && root.querySelector('pre > code.language-openui')
                                && !root.querySelector('.openui-card');
                }""",
                timeout=10000,
            )
            assert page.locator("#openui-e2e .openui-card").count() == 0
            assert page.locator("#openui-e2e pre > code.language-openui").count() == 1
            # A failed block must NOT be re-mounted on a subsequent highlightCode
            # pass (history reload / panel re-render). It stays a plain code block.
            page.evaluate("highlightCode(document.getElementById('openui-e2e'))")
            page.wait_for_timeout(300)
            assert page.locator("#openui-e2e .openui-card").count() == 0, "failed block was re-mounted"
            assert page.locator("#openui-e2e pre > code.language-openui").count() == 1
        finally:
            b.close()
