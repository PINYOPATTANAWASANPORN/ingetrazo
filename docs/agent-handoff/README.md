# IngeTrazo development handoff

This folder is the compact source of truth for an AI agent continuing the
work performed on the `PINYOPATTANAWASANPORN/ingetrazo` fork. It records what
exists in the stacked branches, what has actually been validated, what remains,
and the engineering knowledge extracted from the work.

- Snapshot date: **2026-10-05**
- Upstream/fork `main` baseline: **`6be29fe`**
- Handoff base: **`feature/ai-project-memory` at `6c8364c`**
- Delivery state: **39 open PRs; none merged into the fork's `main`**

## Read in this order

1. [`state.json`](state.json) — machine-readable current state and next work.
2. [`DEVELOPMENT_SUMMARY.md`](DEVELOPMENT_SUMMARY.md) — all product streams
   and their PRs.
3. [`AI_AGENT_HANDOFF.md`](AI_AGENT_HANDOFF.md) — AI architecture, contracts,
   test commands, and implementation gaps.
4. [`LESSONS_LEARNED.md`](LESSONS_LEARNED.md) — reusable engineering knowledge
   and failure patterns.
5. [`pr-index.json`](pr-index.json) — GitHub API snapshot of every fork PR.

The handoff pack itself is delivered by
[#33](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/33), stacked on
#32. The typed Assistant implementation continues in
[#34](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/34), followed by
typed box/cylinder creation and the session-only advanced Python gate in
[#35](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/35), followed by
streaming and cooperative cancellation in
[#36](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/36), followed by
local context suggestions and the evaluation corpus in
[#37](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/37), followed by
scoped wall/slab/component creation in
[#38](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/38), followed by
parallel read-only specialist reviews in
[#39](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/39), followed by
external MCP specialist coordination in
[#40](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/40), followed by
per-role specialist model selection in
[#41](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/41). New code
should preserve this documentation layer or update it in the same change.

The detailed design documents remain authoritative for their domains:

- [`../ai-agent-roadmap.md`](../ai-agent-roadmap.md)
- [`../ai-bridge.md`](../ai-bridge.md)
- [`../performance-plan.md`](../performance-plan.md)
- [`../plugins.md`](../plugins.md)
- [`../architecture.md`](../architecture.md)

## Status vocabulary

- **Implemented in stack** means code exists in an open branch/PR and passed
  the recorded targeted validation.
- **Merged** means GitHub reports a non-null merge time into the intended base.
- **Installed** means a build containing the commit was deployed on the local
  machine. This pack does not claim that deployment.
- Percentages are planning estimates derived from acceptance targets. They are
  not test coverage or proof of release readiness.

## Updating this pack

When work continues, update `state.json`, the affected summary, validation
evidence, and `pr-index.json`. Record exact commands and outcomes. Do not erase
failed attempts that reveal a reusable constraint; add the lesson to
`LESSONS_LEARNED.md`.


Latest delivery: [PR #42](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/42), `feature/ai-review-export` on #41; implementation `5f1763b`. Selected regression suite: 113 passed with simulated providers. GitHub snapshot: 40 total, 40 open, 0 merged. Earlier snapshot counts above are historical. Installed build unchanged.


Current development slice: `feature/ai-review-audit-trail` on PR #42 adds a session-only, hash-linked review status log through MCP. It is not a signed or persistent audit system.


Latest delivery: [PR #43](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/43), `feature/ai-review-audit-trail` on #42; implementation `bf3ee67`. Selected regression suite: 115 passed with simulated providers. GitHub snapshot: 41 total, 41 open, 0 merged. Earlier counts are historical. Installed build unchanged.


Current development slice: `feature/ai-review-audit-file` on PR #43 adds explicit atomic history-file export and offline verification in Assistant. Unsigned checksums detect accidental corruption, not authorship.


Latest delivery: [PR #44](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/44), `feature/ai-review-audit-file` on #43; implementation `703a156`. Selected regression suite: 118 passed with simulated providers. GitHub snapshot: 42 total, 42 open, 0 merged. Earlier counts are historical. Installed build unchanged.
