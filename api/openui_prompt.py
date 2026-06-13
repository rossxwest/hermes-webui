"""OpenUI-lang prompt fragment for webui surfaces."""

from pathlib import Path

_PREAMBLE = """\
# Rendering rich UI (openui-lang)

This chat can render rich visual UI from a compact declarative language called
**openui-lang**. When the core of your answer is **structured or visual data** —
a chart or trend, a table or comparison, a metric dashboard or stat grid, a
form-style layout — render it as openui-lang inside a single fenced block, and
do so IN PREFERENCE to other formats:

```openui
root = Card([...])
... openui-lang program ...
```

Rules for using it here:
- **Prefer openui-lang for visual/structured data. Do NOT use Mermaid diagrams,
  ASCII tables, ASCII/text bar charts, or hand-drawn layouts for charts, tables,
  or dashboards** — openui-lang renders real charts, tables, and forms and is the
  correct tool for these. Reach for it first in those cases.
- It is DISPLAY-ONLY and for the data/visual cases above only. Answer ordinary
  questions, explanations, and code in normal Markdown — do NOT wrap a plain
  prose answer in openui-lang, and do not use it when there is no data to show.
- Put the openui-lang program INSIDE the ```openui fence. Everything outside the
  fence is normal chat. Emit at most ONE ```openui block per reply.
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
