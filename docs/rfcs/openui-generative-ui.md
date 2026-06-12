# Generative UI for Hermes WebUI (OpenUI integration)

- **Status:** Proposed
- **Author:** @rossxwest
- **Created:** 2026-06-12
- **Reference implementation:** [thesysdev/openclaw-os](https://github.com/thesysdev/openclaw-os) (integration *pattern* only — not forked)
- **Upstream renderer:** [thesysdev/openui](https://github.com/thesysdev/openui), specifically `@openuidev/browser-bundle`

## Problem

The Hermes agent can only express itself in the chat transcript as markdown text.
When the right answer is a chart, a table, a dashboard, or a structured layout,
the agent has to approximate it with prose, ASCII, or a fenced code block. There
is no way for the agent to emit *renderable UI*.

[OpenUI](https://github.com/thesysdev/openui) defines **OpenUI Lang** — a compact,
streaming-first markup that a model emits instead of JSON (~67% fewer tokens than
equivalent JSON) — plus a prebuilt browser renderer. We want the Hermes agent to
be able to emit OpenUI Lang and have it render inline in the transcript, so the
agent can build dynamic UIs easily.

## Goals

- Let the agent emit OpenUI Lang that renders as an **inline card** inside the
  assistant message.
- Reuse openui's **prebuilt** renderer (`@openuidev/browser-bundle`) — no React,
  no bundler, no build step added to the hermes-webui dev loop.
- Stay opt-in and **off by default**, consistent with the existing extension
  surface.
- Keep the renderer fully **sandboxed** from the host page.

## Non-goals

- **Interactive round-trip** (UI → agent events: clicks, form submits). Deferred;
  needs a UI→agent channel and a dedicated security review.
- **Persistent "app" surfaces** in the workspace panel (the openclaw-os
  apps/artifacts paradigm).
- **Forking or hosting** any part of openclaw-os.
- Adding React, a bundler, or a build step to the dev loop.

### Sequencing — v1 is the rendering foundation, not the product

This RFC delivers **layer-4 rendering only**: the agent can draw a live,
display-only UI inline. The genuinely hard, security-sensitive parts — an
interactive UI→agent round-trip (buttons/forms that trigger agent turns) and any
**persistence** (writing to a store, gated by an approval flow) — are
deliberately deferred to a **separate follow-up RFC**. Calibrate expectations
accordingly: v1 = "the agent can render a live table inline," not "a working
interactive app." The follow-up is where the larger share of the work and the
real threat-modeling lives.

## Background & key constraint

hermes-webui is a Python backend + **vanilla JS frontend with no build step, no
framework, no bundler** (`AGENTS.md`: *"Do not add dependencies, build tools,
frameworks, or long-lived processes without clear justification"*). It is a
**frontend for the Hermes agent**; the agent runs separately and streams output
into the chat.

openclaw-os solves the same problem for the OpenClaw gateway using a
`before_prompt_build` hook (inject an OpenUI system prompt) + a Next.js client
that renders OpenUI Lang. We adopt the **pattern**, not the code, because the two
seams it relies on already exist here:

| openclaw-os seam | hermes-webui equivalent |
|---|---|
| `before_prompt_build` injects OpenUI system prompt | `api/streaming.py:392` `_webui_ephemeral_system_prompt(...)` |
| Serves a prebuilt UI bundle over the gateway | `api/extensions.py` sandboxed same-origin static serving + `static/vendor/` |
| Next.js/React renderer | `@openuidev/browser-bundle` (prebuilt, iframe-targeted) in a sandboxed iframe |

The streaming-renderer lineage also already exists: `static/vendor/smd.min.js`
(streaming-markdown), whose token renderer `messages.js` already wraps
(`_smdRendererWithoutUnderscoreEmphasis`). That wrap point is where we intercept
the OpenUI fenced block.

## Proposal

### Data flow

```
Hermes agent  ──emits──▶  ```openui … ```  ──streams──▶  messages.js smd hook
   ▲                         (fenced block)                      │
   │ system prompt teaches OpenUI Lang                           ▼
api/streaming.py            detects info-string "openui"
_webui_ephemeral_system_prompt   → creates sandboxed <iframe src=host.html>
   (flag-gated, off by default)   → postMessage({type:'openui:code', code}) per delta
                                                       │
                                                       ▼
                              static/vendor/openui/host.html
                              loads browser-bundle (window.__OpenUI)
                              renders <Renderer code=… library schema/> via React,
                              re-rendering as `code` grows. Reports height back.
```

Five isolated components, each with a defined interface:

#### 1. Agent-side prompt injection (`openui-prompt`)
- **Where:** `api/streaming.py`, inside `_webui_ephemeral_system_prompt(...)`,
  alongside the existing `_webui_surface_context_prompt` section.
- **What:** append an "OpenUI Lang" section to the ephemeral system prompt: a
  short spec of the markup, the component vocabulary, the fenced-block contract
  (emit UI as ` ```openui … ``` `), and guidance on *when* to use it (display
  data/dashboards, not prose).
- **Per-session scoping (not global):** inject **only** when the flag is on
  **and** the session can actually render OpenUI — i.e. `surface_context.source
  == 'webui'`. Browser sessions already pass `source: 'webui'`
  (`streaming.py:6359`); messaging gateways and CLI/background/heartbeat runs
  carry a different (or absent) surface context and therefore never receive the
  spec. This keeps the always-on background loops (e.g. classification
  heartbeats) free of OpenUI tokens they can't use. (openclaw-os achieves the
  same with a workspace session-key suffix; `surface_context.source` is the
  hermes-native equivalent.)
- **Interface:** pure function `(flag_enabled, surface_context) -> prompt_fragment`.
  The prompt text lives in one module-level constant / sibling file so it is
  unit-testable and version-bumpable without touching streaming logic.
- **Default:** flag off → no fragment → byte-identical prompt to today.
- **Prompt-cache note:** `ephemeral_system_prompt` is the agent's own mechanism;
  where it sits relative to a cached prefix is owned by the **hermes-agent
  runtime**, not hermes-webui. The existing ephemeral blob already injects
  per-session-variable text every turn (`session_id`, `workspace`, `profile`),
  so this section introduces no new cache-busting class — it appends to an
  already-ephemeral payload. The lever we control is the per-session scoping
  above, which bounds how often any reprocessing cost is paid. Confirm during
  implementation that the addition doesn't measurably worsen
  `prompt_cache_hit_percent` for UI sessions; if it does, revisit placement with
  the agent runtime.

#### 2. Transport contract
- The agent emits a fenced block with info string `openui`:
  ````
  ```openui
  <openui lang here>
  ```
  ````
- Rides the **existing** streaming pipeline untouched — no new route, no new event
  type; it is just text in the assistant turn.
- A fenced block degrades gracefully: if rendering is disabled or fails, the user
  sees a normal code block (see component 4 fallback).

#### 3. Vendored renderer + host page (`openui-host`)
- **Vendored artifact:** `@openuidev/browser-bundle`'s prebuilt JS + CSS, checked
  into `static/vendor/openui/` exactly like `smd.min.js` and `katex`. The bundle
  exposes `window.__OpenUI = { React, createRoot, Renderer, openuiChatLibrary }`.
- **Host page:** `static/vendor/openui/host.html` — a minimal same-origin page that
  1. links the openui CSS + JS,
  2. listens for `postMessage({type:'openui:code', code})` from the parent,
  3. (re)renders `React.createElement(Renderer, { code, library, schema })` from
     `openuiChatLibrary` into a root div on each message,
  4. posts `{type:'openui:height', px}` back on resize and
     `{type:'openui:error', message}` on render failure.
- **Streaming (render on block-close, not per-token):** to avoid thrashing the
  React reconciler by re-parsing a growing table on every token (the real perf
  risk on modest hardware), v1 shows a lightweight "generating…" placeholder
  while the ` ```openui ` block streams, and renders the UI **once the fenced
  block closes** (with the complete `code`). An optional throttle (~100–250 ms
  mid-stream re-render) can be added later if live partial rendering is wanted;
  OpenUI Lang tolerates partial markup, but full re-parse per token is the trap.
- **No network egress:** the bundle is local; the iframe needs no outbound network.

#### 4. Render hook (`messages.js`)
- **Where:** the smd renderer wrap point already used for
  `_smdRendererWithoutUnderscoreEmphasis`, extended to recognize a code block whose
  info string is `openui`.
- **Behavior:**
  - On first sight of an `openui` block, create a card containing a **sandboxed
    iframe** (`sandbox="allow-scripts"`, no `allow-same-origin`) pointing at
    `static/vendor/openui/host.html`.
  - While the block streams, show a "generating…" placeholder; on block-close,
    postMessage the final `code` and size the iframe from `openui:height` messages
    (see Streaming, above).
  - **Fallback:** if the bundle fails to load, the iframe errors, the flag is off,
    or openui is unavailable → render the block as an ordinary fenced code block
    (current behavior). The user never loses content.
- **Isolation guarantee:** the iframe is sandboxed without `allow-same-origin`, so
  the openui React app runs in an opaque origin and cannot touch the parent DOM,
  cookies, or globals. Communication is postMessage only — v1 is strictly
  parent→iframe (code) and iframe→parent (height/error), authenticated per the
  opaque-origin scheme in Security & isolation (source-identity + per-card nonce).

#### 5. Feature flag / config
- One feature flag, **off by default**, following the house convention for
  feature toggles: a nested `experimental.openui` key in the profile `config.yaml`,
  read via an `is_openui_enabled(config_data)` helper that mirrors the existing
  `is_unified_session_db_enabled` (`api/config.py:386`) exactly — strict `is True`,
  **no env var** (there is no boolean `HERMES_WEBUI_*` feature-flag precedent in
  the repo, so we don't introduce one).
- The flag gates **both** prompt injection (1) and render hook (4), so the halves
  never drift: if the agent isn't taught OpenUI Lang, the renderer stays inert.

#### Model capability (recommendation)
Generative-UI quality scales with the model emitting the OpenUI Lang; a weak/cheap
model may produce malformed markup — which at least degrades safely to a plain
code block (see Error handling). **If** hermes supports per-turn / per-subagent
model override (to be confirmed; the WebUI today selects a model per session via
the composer footer), prefer routing UI-emitting turns to a more capable model
while keeping always-on background loops on the cheap model. Treat this as a
tuning recommendation, not a v1 requirement.

### Security & isolation
- **Sandboxed iframe, opaque origin** (`allow-scripts` only) — renderer cannot read
  parent state/cookies/localStorage or navigate the top frame.
- **postMessage authentication (opaque origin):** because the iframe has no
  `allow-same-origin`, its `event.origin` is the string `"null"`, so the usual
  `event.origin` allowlist check does **not** work. Authenticate messages instead
  by (a) verifying `event.source === iframe.contentWindow` on the parent and
  `event.source === window.parent` in the iframe, (b) a per-card random **nonce**
  established in an initial handshake and required on every subsequent message,
  and (c) sending with `postMessage(msg, '*')` targeted at the specific iframe
  window only. This stops any other frame/extension from injecting
  `openui:height`/`openui:error` messages across the trust boundary.
- **No UI→agent channel in v1** — display-only removes the largest attack surface.
- **Local-only assets** — no third-party CDN at runtime; matches
  `api/extensions.py`'s "never fetch third-party URLs" stance.
- **CSP:** confirm the host page + iframe pass existing security headers
  (`api/helpers.py` `_security_headers`); add a scoped allowance if needed.
- **Untrusted markup** is rendered by openui's renderer, not eval'd by us; the
  sandbox contains any renderer-level escape.

### Error handling
| Failure | Behavior |
|---|---|
| Flag off | No prompt injection, no render hook. Identical to today. |
| Bundle missing / fails to load | iframe posts `openui:error` → parent replaces card with the raw fenced code block. |
| Malformed / partial OpenUI Lang | renderer renders what it can; hard error → fallback to code block. |
| `openui:height` never arrives | iframe uses sensible min/max height; no layout break. |
| Many cards in one transcript | bundle is HTTP-cached (fetched once); see Performance. |

### Performance
- Bundle is ~650 KB gzipped — fetched **once** (HTTP cache), parsed per-iframe. For
  transcripts with many UI cards this is the main cost.
- v1 accepts per-card iframes for simplicity and isolation. **Future optimization
  (out of scope):** a single shared host iframe rendering multiple roots, or
  lazy-mounting cards only when scrolled into view.

### Vendoring / refresh + supply chain (preserves "no build step")
- The prebuilt bundle is committed under `static/vendor/openui/` like other
  vendored assets. The app **does not** build it.
- **Pin + provenance (load-bearing, not optional):** this is ~650 KB of
  third-party JS that renders agent output — and, in the broader vision, output
  influenced by *untrusted email* — so supply-chain hygiene matters more than for
  a typical vendored lib. The refresh procedure MUST:
  1. pin an **exact** `@openuidev/browser-bundle` version (no ranges),
  2. record a **SHA-256** of each committed file (JS + CSS) next to the assets,
  3. document the source (published dist, or `pnpm --filter
     @openuidev/browser-bundle build` in a throwaway checkout) and a brief
     review step before any version bump,
  4. land version bumps as their own reviewable commit (diff is a binary blob, so
     the pinned version + hash + provenance note are how a reviewer reasons about
     it).
- A documented one-time refresh procedure (in `scripts/` or a short doc) performs
  the above and copies JS+CSS in. A maintainer chore, not a dev-loop step.

### Testing
- **Python unit:** `_webui_ephemeral_system_prompt` includes the OpenUI section iff
  the flag is on; byte-identical to today when off.
- **Static JS runtime lint:** new `messages.js` passes `npm run lint:runtime`.
- **Render smoke:** a fixture OpenUI Lang string renders a known component in
  `host.html`.
- **Fallback:** with the bundle absent / flag off, an `openui` block renders as a
  plain code block — no error, no blank card.
- **Streaming:** feeding `code` in growing chunks converges to the same final render
  as feeding it whole.
- **OpenUI Lang validity eval (model-dependent):** a small manual/eval check that
  the model, under the injected prompt, actually emits *valid* OpenUI Lang for a
  few representative asks (table, chart, form). This is the thing most likely to
  disappoint in practice and it can't be a deterministic unit test — track it as a
  scored eval, not a pass/fail assertion.
- **Manual UI evidence:** before/after across desktop, narrow, mobile (per
  `AGENTS.md`).

## Open questions

1. ~~Streaming fidelity~~ **Resolved:** v1 renders on block-close with a
   "generating…" placeholder (no per-delta re-render); optional throttle deferred.
   See Streaming under component 3.
2. **Renderer API stability:** confirm `Renderer` props (`code`, `library`,
   `schema`) and `openuiChatLibrary` shape against the pinned bundle version.
3. ~~Config flag name/placement~~ **Resolved:** `experimental.openui` config key
   via `is_openui_enabled(config_data)`, mirroring `is_unified_session_db_enabled`
   (no env var). See component 5.
4. **CSP interaction:** confirm sandboxed iframe + vendored bundle pass
   `_security_headers`.
5. **Prompt-cache impact:** confirm the scoped injection doesn't measurably lower
   `prompt_cache_hit_percent` for UI sessions (placement is owned by the
   hermes-agent runtime — see the prompt-cache note in component 1).
6. **Per-turn model override:** confirm whether hermes can route UI-emitting turns
   to a stronger model while keeping background loops cheap (see Model capability).

## Rollout plan

1. **Spike (highest risk first):** vendor `browser-bundle`, build a static
   `host.html`, render a hard-coded OpenUI Lang fixture in a sandboxed iframe.
   Proves renderer + iframe + postMessage end to end.
2. **Render hook:** intercept the `openui` fenced block in `messages.js`, show a
   "generating…" placeholder while streaming, mount the iframe and render on
   block-close, with code-block fallback and the opaque-origin postMessage auth.
3. **Prompt injection:** teach the agent OpenUI Lang in
   `_webui_ephemeral_system_prompt`, flag-gated **and** scoped to
   `surface_context.source == 'webui'` so background/CLI/messaging runs are
   unaffected.
4. **Config flag** wiring both halves; default off.
5. **Tests + docs** (TESTING.md, docs/EXTENSIONS.md or a new doc, CHANGELOG).
