# OpenUI generative-UI rendering

Hermes WebUI can render **inline, display-only generative UI** produced by the
agent. When the feature is enabled, the Hermes agent emits responses in
**openui-lang** — a compact declarative UI language — inside a ` ```openui `
fenced block. The WebUI intercepts the completed block and renders it as a
sandboxed iframe card directly in the chat transcript, so the agent can produce
live tables, dashboards, and structured layouts rather than approximating them
with prose or ASCII.

---

## Enabling the feature

OpenUI rendering is **off by default**. To enable it, add the following to the
active profile's `config.yaml`:

```yaml
experimental:
  openui: true
```

With the flag absent or set to any other value the feature is completely inert:
no prompt injection occurs and no special rendering happens. Existing
conversations are unaffected.

---

## How it works

### Agent side

When the flag is on and the request comes from the WebUI surface
(`surface_context.source == 'webui'`), `api/streaming.py` appends an
openui-lang system-prompt fragment to the ephemeral system prompt via
`api/openui_prompt.py`. The fragment is generated from the vendored bundle's
own `openuiChatLibrary.prompt()` by `scripts/openui_gen_prompt.py` and stored
at `static/vendor/openui/openui-system-prompt.txt`. Background runs, CLI
invocations, and messaging-gateway sessions never receive this injection and
are completely unaffected.

### Renderer

The prebuilt `@openuidev/browser-bundle` **0.1.1** is vendored at
`static/vendor/openui/openui-bundle.min.js` (+ `openui-styles.css`). It
exposes `window.__OpenUI = { React, createRoot, Renderer, openuiChatLibrary }`.
The renderer is driven as:

```js
<Renderer
  response={code}
  library={openuiChatLibrary}
  isStreaming={false}
  onParseResult={...}
/>
```

Note: the prop is `response` (not `code`) and `library` is the
`openuiChatLibrary` object directly — the package README's `{code, library,
schema}` signature is incorrect for version 0.1.1.

### Iframe host

`static/vendor/openui/host.html` loads the bundle inside an
`<iframe sandbox="allow-scripts">` (opaque origin). The route serving it
(`api/routes.py`) sets `Content-Security-Policy: sandbox allow-scripts`.

The parent page and the iframe communicate via a nonce-authenticated postMessage
protocol:

| Message | Direction | Purpose |
|---|---|---|
| `openui:ready` | iframe → parent | bundle loaded, ready for code |
| `openui:init {nonce, code}` | parent → iframe | send the openui-lang block |
| `openui:height {nonce, px}` | iframe → parent | iframe reports its rendered height |
| `openui:error {nonce, message}` | iframe → parent | render failure |

Authentication uses `event.source` identity (not `event.origin`, which is
`"null"` for opaque-origin iframes) combined with a per-card nonce established
at mount time.

### Frontend render hook

`static/ui.js` `_renderOpenuiBlocks(container)` is called at the top of
`highlightCode`, which covers both the live-finalize path and the
history/reload render path. It swaps each completed `pre > code.language-openui`
element for the iframe card, wires the postMessage handshake, and sizes the
iframe from incoming height messages. The hook is gated on
`window.__HERMES_CONFIG__.openui` (injected by `static/index.html`).

**Fallback:** if the bundle fails to load, the iframe errors, or a timeout
occurs, the original code block is restored. The user never loses content.

---

## Security model

- **Opaque-origin sandbox** — `allow-scripts` only, no `allow-same-origin`. The
  renderer cannot read the parent DOM, cookies, localStorage, or globals, and
  cannot navigate the top frame.
- **Source-identity + nonce postMessage** — because `event.origin` is `"null"`
  for opaque-origin iframes, messages are authenticated by `event.source`
  identity plus a per-card random nonce agreed during the `openui:ready`
  handshake.
- **Display-only** — there is no UI→agent channel in v1. Clicks and form events
  inside the iframe are not forwarded to the agent. This removes the largest
  attack surface.
- **Local assets only** — the bundle and all related assets are vendored locally.
  No third-party CDN is contacted at runtime.

---

## Vendoring and refreshing the bundle

The bundle is committed under `static/vendor/openui/`. To update to a new
version:

```bash
# 1. Fetch the new bundle, update VENDOR.md with the new SHA-256
scripts/vendor_openui.sh <version>

# 2. Regenerate the system-prompt fragment from the new bundle
python scripts/openui_gen_prompt.py
```

Both scripts record or refresh `static/vendor/openui/VENDOR.md` (pinned
version + SHA-256 of JS and CSS) and update
`static/vendor/openui/openui-system-prompt.txt`.

**Supply-chain note:** the bundle is ~2 MB of third-party JS that renders
agent output — output potentially influenced by untrusted email or user content
in the broader Hermes ecosystem. The version and SHA-256 in `VENDOR.md` are
therefore load-bearing: they are the primary way a reviewer can reason about a
bundle update. Land version bumps as their own reviewable commit.

---

## Running the tests

```bash
python -m pytest tests/test_openui_*.py
```

The test suite covers:

| File | Coverage |
|---|---|
| `test_openui_config_flag.py` | `is_openui_enabled` helper, strict flag semantics |
| `test_openui_prompt_injection.py` | prompt fragment present iff flag is on |
| `test_openui_prompt_wiring.py` | fragment injected into ephemeral system prompt |
| `test_openui_host_csp.py` | host.html served with correct sandbox CSP |
| `test_openui_host_render.py` | fixture openui-lang renders in host.html (playwright) |
| `test_openui_frontend_flag.py` | frontend flag gating |
| `test_openui_render_hook.py` | `_renderOpenuiBlocks` hook (node) |
| `test_openui_e2e_render.py` | end-to-end render + fallback (playwright) |

Tests marked `@pytest.mark.integration` (`test_openui_host_render.py`,
`test_openui_e2e_render.py`) drive a real browser and require:

```bash
pip install playwright && playwright install chromium
```
