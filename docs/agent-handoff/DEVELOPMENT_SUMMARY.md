# Development summary

## Delivery topology

The fork uses one long stacked chain. GitHub reported **80 open PRs and zero
merged PRs** on 2026-10-08. PR numbers 18 and 27 are absent from the pull list;
do not invent them. The chain begins at fork `main` (`6be29fe`) and currently
ends at `fix/igz-worker-quit-order` (`cfaacc8`). Merging or rebasing a lower PR
changes every PR above it, so preserve order and revalidate the affected stack.
The latest stack layer is
[#82](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/82).

## Product workstreams

The remaining implementation and release gates are prioritized in
[`REMAINING_DEVELOPMENT_PLAN.md`](REMAINING_DEVELOPMENT_PLAN.md). The estimates
below describe features in the open stack, not merge or release readiness.

| Workstream | Estimated implementation in stack | Delivered slices | Important remaining work |
| --- | ---: | --- | --- |
| Model Outliner | 85% | Full hierarchy, search, select, hide, lock, rename, undoable reorder | Face/edge-level hierarchy and large-tree UX |
| Move Autofold and mesh editing | 90% | Direct vertex edit, autofold preview, inference presentation | Complex-mesh stress cases and user controls |
| Tags/Layers | 95% | Active tag selector, inheritance for new containers, visible hidden/locked state | Final workflow polish and broader tests |
| Selection and Entity Info | 95% | Select by type/material/tag, multi-material edits, multi-transform, Alt-click cycling | Complex nested selection UX |
| Large-model performance | 70% | Shared instance pick geometry, responsive `.igz` open, loose-edge cache | True progressive paint, render chunking, broader benchmarks |
| Extension Manager | 75% | Enable/disable, local install/remove, safe manifests | Online catalog, version resolution, URL updates |
| File exchange | 30% | Windows SKP long-texture-path repair | IFC import, fuller SKP hierarchy fidelity, cross-platform DWG |
| Architectural tools | 10% | Existing BIM/export/composer/terrain foundations | Contours, axes/grid, room labels, doors/windows, schedules |
| AI Agent roadmap | about 72% overall | Bounded context, security gate, typed preview writes and architectural creation, task engine, concise UI, project memory, streaming/cancel, local suggestions, evaluation corpus, two read-only specialists with per-role model selection, external MCP review protocol, session-only Python gate | Existing-wall edits, modeler orchestration, measured provider baselines |

## PR chain by capability

### Foundation and SketchUp-style workflow

- [#1](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/1) — ASCII digits in numeric inputs.
- [#2](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/2) — active layers and direct vertex editing.
- [#3](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/3) — full model Outliner.
- [#4](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/4) — Move Autofold preview.
- [#5](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/5) — circle/polygon segment rebuild.
- [#6](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/6) — Windows-safe AI photo filenames.
- [#7](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/7) — Windows base-map network crash guard.
- [#8](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/8) — undoable Outliner reorder.

### Selection, Entity Info, tags, and performance

- [#9](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/9) — selection filters.
- [#10](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/10) — multi-entity material editing.
- [#11](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/11) — multi-object position and size.
- [#12](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/12) — shared component pick geometry.
- [#13](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/13) — always-visible Active Tag selector.
- [#14](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/14) — distinct Autofold inference preview.
- [#15](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/15) — responsive native-document opening.
- [#20](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/20) — loose-edge selection cache.
- [#21](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/21) — Active Tag inheritance for containers.
- [#22](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/22) — long Windows SKP texture paths.
- [#23](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/23) — consistent tag state labels.
- [#24](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/24) — Alt-click overlapping-selection cycling.

### Extension Manager

- [#16](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/16) — safe enable/disable UI.
- [#17](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/17) — local installation/removal.
- [#19](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/19) — safe manifest metadata.

### AI context, typed writes, and concise workflow

- [#25](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/25) — bounded context APIs.
- [#26](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/26) — bridge credentials and permissions.
- [#28](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/28) — preview-first property actions.
- [#29](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/29) — material and bounded transform actions.
- [#30](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/30) — scoped task engine.
- [#31](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/31) — compact intent controls.
- [#32](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/32) — explicit project AI memory.
- [#33](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/33) — durable AI development handoff pack.
- [#34](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/34) — typed previews in the in-app Assistant.
- [#35](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/35) — typed box/cylinder creation and session-only advanced Python permission.
- [#36](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/36) — streamed provider responses and cooperative cancellation.
- [#37](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/37) — local context suggestions and a versioned AI evaluation corpus.

- [#38](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/38) — walls with openings, slabs, component copies and scoped parent coordinates.

- [#39](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/39) — two read-only provider specialists, conflict reporting and cancellation.

- [#40](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/40) — external MCP review assignments, validated submissions, bounded retention and cancellation.

- [#41](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/41) — per-role model selection, provider-scoped settings and requested-model reporting.

## Claims that must stay qualified

All items above are implemented **in the open stack**. They are not on the
fork's `main`, not upstream, and not necessarily in the installed IngeTrazo
binary. The latest selected regression run covered 107 tests; it was not the
repository's complete test suite.


Architectural creation now includes walls with door/window openings, rectangular
slabs, component copies, and scoped parent-coordinate primitives. See
[`ai-creation-contract.md`](../ai-creation-contract.md) for supported cases and limits.


## Latest increment: AI review export
Branch `feature/ai-review-export`, based on `feature/specialist-model-selection`. Adds revision-checked JSON export in Assistant and MCP, atomic local saving and unsigned integrity digest. Settings/tokens excluded; prose may contain sensitive project content. No installed build update. See `docs/ai-specialist-review.md`.


Latest delivery: [PR #42](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/42), `feature/ai-review-export` on #41; implementation `5f1763b`. Selected regression suite: 113 passed with simulated providers. GitHub snapshot: 40 total, 40 open, 0 merged. Earlier snapshot counts above are historical. Installed build unchanged.


## Session review audit trail (2026-10-05)
Branch `feature/ai-review-audit-trail` builds on PR #42. `AITaskService` appends terminal/stale review metadata to an unsigned SHA-256 chain; MCP `get_review_audit` pages through it. No raw prose, tokens, credentials or snapshot content are in audit events. History resets on bridge restart/document replacement. Targeted suite: 115 passed (simulated providers); installed build unchanged. Persistent, user-controlled audit storage remains future work.


Latest delivery: [PR #43](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/43), `feature/ai-review-audit-trail` on #42; implementation `bf3ee67`. Selected regression suite: 115 passed with simulated providers. GitHub snapshot: 41 total, 41 open, 0 merged. Earlier counts are historical. Installed build unchanged.


## Explicit review history file (2026-10-05)
Branch `feature/ai-review-audit-file` builds on PR #43. Assistant can atomically save the complete current session metadata trail to a user-selected JSON file and independently verify that saved file after restart. The verifier checks bounded schema, ordered chain, head and payload digest. No automatic persistence or model mutation. Saved files are unsigned and can be rehashed by their holder; authenticated audit evidence is pending. Selected suite: 118 passed with simulated providers; installed build unchanged.


Latest delivery: [PR #44](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/44), `feature/ai-review-audit-file` on #43; implementation `703a156`. Selected regression suite: 118 passed with simulated providers. GitHub snapshot: 42 total, 42 open, 0 merged. Earlier counts are historical. Installed build unchanged.


## Separate provider routing for read-only reviewers (2026-10-05)
Branch `feature/ai-cross-provider-review` builds on PR #44. Assistant can choose a provider and model per read-only specialist. Role overrides reuse provider-scoped connection settings and validate all required keys before dispatch. The same detached snapshot goes to both workers; keys are absent from reports and error text is redacted. External MCP review protocol is unchanged. Selected suite: 123 passed with simulated providers; no real-provider baseline or installed build update.


Latest delivery: [PR #45](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/45), `feature/ai-cross-provider-review` on #44; implementation `23da695`. Selected regression suite: 123 passed with simulated providers. GitHub snapshot: 43 total, 43 open, 0 merged. Earlier counts are historical. The installed-build claim below supersedes the historical installation status.

## Local Windows installation (2026-10-06)

The stacked code through `b0dce0f` is installed under `C:\Program Files\IngeTrazo`. The main executable and MCP bridge match the recorded SHA-256 build manifest. The installed `--check` exits 0, the GUI opens an untitled document, and MCP `tools/list` returns 22 tools. This is a local installation check, not a claim that the stack was merged or that all real-provider workflows were tested. See [`INSTALLATION.md`](INSTALLATION.md).

## Repeatable specialist review measurements (2026-10-06)

The pushed branch `feature/ai-review-benchmark` (implementation `a33fb8a`)
adds stable, public read-only fixtures and an opt-in runner for two specialist
roles. It records elapsed time, status, finding and conflict counts without
saving credentials, raw snapshots or reviewer prose. Offline summaries report
p50/p95 and role success rates. Tokens and quality scores remain null until
measured separately. The selected AI suite passed 128 tests with fake
providers; no live provider benchmark has been run. It is in
[draft PR #46](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/46).
This code is included in the Windows build installed from `b2573b7` on
2026-10-06. The installed executable passed `--check` and the bridge returned
22 tools; no real-provider benchmark has been run.

The later narrow-tray control fix in
[draft PR #47](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/47)
was installed from `3815ef8` on 2026-10-06. At a fixed 340 px width, Export
review occupies its own row and suggestion labels use full-width rows. The
46 Assistant UI tests passed. The installed binaries passed hash comparison,
`--check`, and MCP `tools/list` (22 tools); the GUI was not visually relaunched.

## Move frame timing (2026-10-08)

The open Move performance stack now reaches
[draft PR #74](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/74)
on #73. A native Windows benchmark measures a queued planar Move through
Qt's `frameSwapped` signal: median 157.5 ms over seven trials on the bundled
7,633-face sample, with 135.4 ms in paint. Opt-in live performance telemetry
also records pointer-event-to-frame-submission time. This is diagnostic work,
not an input-to-visible-pixel measurement or an installed build. See
[`MOVE_QT_FRAME_LATENCY.md`](MOVE_QT_FRAME_LATENCY.md) for scope and evidence.

The follow-up [draft PR #75](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/75)
avoids whole-buffer CPU copies when a local edit only changes the end of a
large VBO. Its 64 MiB isolated benchmark improved, while the bundled smaller
model showed no established full-frame improvement. See
[`MOVE_VBO_CHANGED_TAIL.md`](MOVE_VBO_CHANGED_TAIL.md).

The next [draft PR #76](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/76)
computes a loose Face's silhouette plane once for all its adjacent soft
edges. On the bundled model, the arrays matched exactly and peak traced
allocation fell from 13.47 to 10.53 MiB; the measured CPU and full-frame
time differences are too small or variable to claim a visible speedup. See
[`MOVE_SOFT_EDGE_UNIQUE_PLANES.md`](MOVE_SOFT_EDGE_UNIQUE_PLANES.md).

The follow-up [draft PR #77](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/77)
reuses loose silhouette arrays after a Move that provably changes neither
soft-edge endpoints nor adjacent Face planes. On a 15,312-soft-edge bundled
model, the local paired native Qt benchmark reduced median queued
Move-to-`frameSwapped` time from 167.246 to 106.532 ms. The 52 focused tests
passed; hosted final-head CI and physical pointer-to-pixel timing remain to
be verified. See [`MOVE_SOFT_EDGE_CACHE.md`](MOVE_SOFT_EDGE_CACHE.md).

PR #77's final-head hosted Ubuntu and Windows smoke CI passed. The next
[draft PR #78](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/78)
keeps that cache valid through several safe Moves before a Qt paint and
across subsequent paints. On three coalesced Moves per frame, the local
Yanque comparison changed queued Move-to-`frameSwapped` median from 189.640
to 127.799 ms; 53 focused tests passed. This is Qt frame submission, not
physical pointer-to-pixel latency. See
[`MOVE_SOFT_EDGE_CHAIN.md`](MOVE_SOFT_EDGE_CHAIN.md).
