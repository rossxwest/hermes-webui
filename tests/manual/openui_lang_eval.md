# Manual eval — does the agent emit valid OpenUI Lang?

The automated suite proves the *plumbing* (prompt injection, the renderer, the
iframe protocol, the render hook, fallback). It cannot prove the thing most
likely to disappoint in practice: **that the model, given the injected
openui-lang spec, actually emits a single valid ` ```openui ` block that
renders** rather than malformed markup (which degrades to a code block — safe,
but not the goal). That quality is model-dependent, so it is a scored manual
eval, not a pass/fail unit test.

## Setup

1. Enable the feature in the profile you're testing: add to that profile's
   `config.yaml`:
   ```yaml
   experimental:
     openui: true
   ```
2. Start the WebUI and open a browser chat session (the spec is injected only for
   `surface_context.source == 'webui'` — CLI/messaging sessions won't get it).
3. For each prompt below, send it and observe the assistant's reply.

## Scoring (per prompt)

Record one of:

- **2 — Rendered:** reply contained exactly one ` ```openui ` block and it
  rendered as a card (no fallback to a raw code block).
- **1 — Fell back:** a ` ```openui ` block was emitted but it was invalid
  openui-lang, so it showed as a code block (graceful degradation worked, but the
  UI didn't render).
- **0 — No UI:** the model didn't use openui-lang where it clearly should have
  (answered in prose/markdown only), OR emitted more than one block, OR put
  non-openui content inside the fence.

Also note qualitatively: did it pick a sensible component (table for tabular
data, a chart for a trend, a form layout for inputs)?

## Prompts (representative of the genui-lib component groups)

1. **Table:** "Show me a comparison table of three cloud providers (AWS, GCP,
   Azure) across price, regions, and free tier."
2. **Bar chart:** "Chart our quarterly revenue: Q1 $1.2M, Q2 $1.5M, Q3 $1.9M,
   Q4 $2.4M."
3. **Line/area trend:** "Plot a plausible 12-month active-users growth curve for
   a new SaaS app."
4. **Metric dashboard:** "Give me a dashboard summarizing a web server's health:
   uptime, p95 latency, error rate, requests/sec."
5. **Form layout (display-only):** "Lay out a sign-up form with name, email, a
   plan selector, and a submit button." (Note: interactions don't round-trip yet
   — we're only scoring whether it renders.)
6. **Mixed prose + UI:** "Explain what a p99 latency is, and include a small
   table of example p50/p90/p99 values." (Expect prose OUTSIDE the fence and one
   ` ```openui ` block for the table — tests that it doesn't make the whole reply
   openui-lang.)
7. **Should NOT use UI:** "What's the capital of France?" (Expect a plain prose
   answer and NO openui block — tests restraint / the 'only when it helps' rule.)

## Model comparison

Run the full set against:

- the **cheap / heartbeat** model (the always-on brain), and
- a **capable** model.

Generative-UI quality scales with model capability; expect the cheap model to
score lower (more 1s/0s). If hermes supports per-turn / per-subagent model
override, this eval is the evidence for routing UI-intended turns to a stronger
model while keeping background loops cheap (see the RFC's model-capability note).

## Record results

| # | Prompt | Cheap model | Capable model | Notes |
|---|--------|-------------|---------------|-------|
| 1 | Table | | | |
| 2 | Bar chart | | | |
| 3 | Line/area | | | |
| 4 | Dashboard | | | |
| 5 | Form | | | |
| 6 | Mixed | | | |
| 7 | Restraint | | | |

**Totals:** cheap __ / 14 · capable __ / 14. A capable model should land most
prompts at 2; widespread 1s mean the injected spec or examples need tuning;
widespread 0s mean the model isn't reaching for openui-lang and the preamble's
"when to use it" guidance needs strengthening.
