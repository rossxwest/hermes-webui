"""Regenerate the vendored openui-lang system prompt from the vendored bundle.

Maintainer chore — run after bumping @openuidev/browser-bundle (alongside
scripts/vendor_openui.sh). NOT part of the app or test suite. Requires
playwright + chromium.

It loads the prebuilt bundle in headless chromium and calls
`window.__OpenUI.openuiChatLibrary.prompt()` — the library's own canonical
language reference (syntax rules + every component signature) — and writes it to
static/vendor/openui/openui-system-prompt.txt. The Python side
(api/openui_prompt.py) strips the bundle's "entire response must be openui-lang"
preamble and substitutes our fenced-block framing, so only the language spec
below "## Syntax Rules" is actually used.
"""
import pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "static" / "vendor" / "openui" / "openui-bundle.min.js"
OUT = ROOT / "static" / "vendor" / "openui" / "openui-system-prompt.txt"


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = b.new_page()
            page.set_content("<!doctype html><html><body></body></html>")
            page.add_script_tag(path=str(BUNDLE))
            prompt = page.evaluate("() => window.__OpenUI.openuiChatLibrary.prompt()")
        finally:
            b.close()
    if not prompt or "## Syntax Rules" not in prompt:
        raise SystemExit("prompt() returned unexpected content; aborting")
    OUT.write_text(prompt, encoding="utf-8")
    print(f"Wrote {len(prompt)} chars -> {OUT}")


if __name__ == "__main__":
    main()
