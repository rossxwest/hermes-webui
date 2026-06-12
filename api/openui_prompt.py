"""OpenUI-lang prompt fragment for webui surfaces."""

from pathlib import Path

_PREAMBLE = """\
# Rendering rich UI (openui-lang)

This chat can render rich visual UI from a compact declarative language called
**openui-lang**. When — and ONLY when — a visual layout communicates better than
prose (a table of data, a chart of a trend, a metric dashboard, a structured
display), you MAY include exactly one fenced block in your reply:

```openui
root = Card([...])
... openui-lang program ...
```

Rules for using it here:
- It is OPTIONAL and DISPLAY-ONLY. Use normal Markdown for ordinary answers,
  explanations, and code. Do NOT make your whole reply openui-lang.
- Put the openui-lang program INSIDE the ```openui fence. Everything outside the
  fence is normal chat as usual.
- Emit at most ONE ```openui block per reply. If unsure it will render, prefer a
  normal Markdown answer.
- The block renders read-only: the user cannot submit forms or trigger actions
  back to you from it yet, so do not rely on interaction.

The complete openui-lang language reference follows. Conform to it exactly.\
"""

_SPEC_MARKER = "## Syntax Rules"
_spec_loaded = False

_VENDOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "static"
    / "vendor"
    / "openui"
    / "openui-system-prompt.txt"
)

_spec = ""
try:
    _raw = _VENDOR_PATH.read_text(encoding="utf-8")
    _marker_idx = _raw.find(_SPEC_MARKER)
    if _marker_idx != -1:
        _spec = _raw[_marker_idx:]
        _spec_loaded = True
except Exception:
    pass

OPENUI_PROMPT = _PREAMBLE + "\n\n" + _spec


def openui_prompt_fragment(enabled: bool, surface_context) -> str:
    """OpenUI Lang instructions, or '' when not applicable.

    Scoped to WebUI surfaces only: background/CLI/messaging runs carry a
    different (or absent) surface_context and never receive the spec.
    """
    if (
        enabled
        and _spec_loaded
        and isinstance(surface_context, dict)
        and surface_context.get("source") == "webui"
    ):
        return OPENUI_PROMPT
    return ""
