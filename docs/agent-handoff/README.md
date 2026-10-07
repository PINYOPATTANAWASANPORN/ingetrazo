# IngeTrazo development handoff

This folder is the compact source of truth for an AI agent continuing the
work performed on the `PINYOPATTANAWASANPORN/ingetrazo` fork. It records what
exists in the stacked branches, what has actually been validated, what remains,
and the engineering knowledge extracted from the work.

- Snapshot date: **2026-10-08**
- Upstream/fork `main` baseline: **`6be29fe`**
- Handoff base: **`feature/ai-project-memory` at `6c8364c`**
- PR inventory: **71 open PRs in the 2026-10-08 snapshot**; check GitHub
  before treating that count as current.
- Local installation: **verified on Windows 10** from code commit `3815ef8`;
  see [`INSTALLATION.md`](INSTALLATION.md) for exact evidence and scope.

## Read in this order

1. [`state.json`](state.json) — machine-readable current state and next work.
2. [`DEVELOPMENT_SUMMARY.md`](DEVELOPMENT_SUMMARY.md) — all product streams
   and their PRs.
3. [`AI_AGENT_HANDOFF.md`](AI_AGENT_HANDOFF.md) — AI architecture, contracts,
   test commands, and implementation gaps.
4. [`LESSONS_LEARNED.md`](LESSONS_LEARNED.md) — reusable engineering knowledge
   and failure patterns.
5. [`pr-index.json`](pr-index.json) — GitHub API snapshot of every fork PR.
6. [`INSTALLATION.md`](INSTALLATION.md) — verified local build and rollback record.
7. [`WINDOWS_QT_INTEGRATION_GATE.md`](WINDOWS_QT_INTEGRATION_GATE.md) —
   latest Windows test and staged-bundle evidence.
8. [`MOVE_FACE_GEOMETRY_CACHE.md`](MOVE_FACE_GEOMETRY_CACHE.md) —
   local-Move viewport geometry cache, validation and remaining paint cost.
9. [`MOVE_LOOSE_EDGE_RENDER.md`](MOVE_LOOSE_EDGE_RENDER.md) —
   loose-edge visibility optimization and native Windows paint evidence.
10. [`MOVE_FACE_COLOR_BUFFER.md`](MOVE_FACE_COLOR_BUFFER.md) —
    packed face-colour reuse, correctness checks and paint measurements.
11. [`MOVE_FACE_VISIBILITY_BACK_BUFFER.md`](MOVE_FACE_VISIBILITY_BACK_BUFFER.md) —
    batched face Tag visibility and default-back geometry reuse.
12. [`MOVE_FACE_SIGNATURE_TUPLES.md`](MOVE_FACE_SIGNATURE_TUPLES.md) —
    measured coordinate-key scan improvement and its frame-time limits.
13. [`MOVE_SILHOUETTE_REBUILD.md`](MOVE_SILHOUETTE_REBUILD.md) —
    batched loose soft-edge visibility and direct profile-plane preparation.
14. [`MOVE_FACE_BUCKET_KEY.md`](MOVE_FACE_BUCKET_KEY.md) — shared geometry key
    for front and default-back face buffers during Move paints.
15. [`MOVE_SILHOUETTE_FACE_PLANES.md`](MOVE_SILHOUETTE_FACE_PLANES.md) —
    batched Face-plane gathering for loose soft-edge silhouettes.

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
  machine and checked at the installed path. The Windows installation now
  contains code through `3815ef8`; subsequent staged bundles are not installed.
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


Current development slice: `feature/ai-cross-provider-review` on PR #44 enables separate provider/model routing for Assistant specialists with preflight credential checks. Real-provider compatibility and quality evidence are still pending.


Latest delivery: [PR #45](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/45), `feature/ai-cross-provider-review` on #44; implementation `23da695`. Selected regression suite: 123 passed with simulated providers. GitHub snapshot: 43 total, 43 open, 0 merged. Earlier counts are historical. Installed build unchanged.


Latest delivery: [draft PR #46](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/46),
`feature/ai-review-benchmark` on PR #45's branch, implementation `a33fb8a`.
It adds a deterministic metadata-only specialist review corpus and opt-in
measurement runner. The selected AI suite passed 128 tests, but no real
provider was called. GitHub snapshot: 44 total, 44 open, 0 merged. The
installed Windows binary still contains code through `b0dce0f` and does not
include this new slice.

Latest UI fix: [draft PR #47](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/47),
`fix/ai-assistant-review-controls`, follows PR #46. In the
narrow AI tray, suggestion buttons now use full-width rows and the suggestion
container keeps the tray width; Export review has its own row and explains that a
current-revision two-specialist review must finish first. The focused
Assistant UI suite passed 46 tests. GitHub snapshot: 45 total, 45 open,
0 merged. The Windows build from `3815ef8` is now installed and passed
installed-path `--check`, both SHA-256 comparisons, and MCP `tools/list`
(22 tools). A verified backup of the prior installation is available; see
[`INSTALLATION.md`](INSTALLATION.md).
The full-width row refinement is included in that installed build.

Latest measurement: [draft PR #48](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/48),
`feature/ai-review-measurement-evidence` on #47, implementation `d337e5d`.
The benchmark now records bounded failure codes without provider response text.
The first local Ollama pairing completed 0/3 public cases in two runs; the
diagnostic run found two invalid schemas and two out-of-scope entity references
across the six role outcomes. The selected AI suite passed 136 tests with
`PYTHONUTF8=1`. GitHub snapshot: 46 total PRs, 46 open, 0 merged. The
installed Windows build remains at `3815ef8`.

Latest structured review: [draft PR #49](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/49),
`feature/ai-review-structured-output` on #48. Local specialist requests use
a snapshot-specific JSON schema, with one prompt-only fallback if the local
server explicitly rejects the format feature. The clean-tree baseline at
implementation `5f6215f` completed 3/3 public metadata cases in schema mode
for both roles. The selected AI suite passed 141 tests. This is response
validity only; token usage and finding quality remain unmeasured. GitHub
snapshot: 47 total PRs, 47 open, 0 merged. Installed build remains `3815ef8`.

Latest usage measurement: [draft PR #50](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/50),
`feature/ai-review-provider-usage` on #49, implementation `eb748a2`.
Specialist benchmarks now retain only provider-reported token counts and keep
missing values null. A clean-tree Ollama run completed 3/3 public cases with
reported case totals 1,049, 1,217 and 726 tokens. The selected AI suite
passed 143 tests. Finding quality is still unscored; these counts do not
establish savings. GitHub snapshot: 48 total PRs, 48 open, 0 merged. The
installed Windows build remains at `3815ef8`.

Latest finding-assessment workflow: [draft PR #51](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/51),
`feature/ai-review-finding-audit` on #50, implementation `32068bd`.
An opt-in public-fixture display and digest-bound manual judgments permit
grounding/relevance review without saving provider prose in benchmark JSONL.
The selected AI suite passed 176 tests. No human assessments have been
collected yet, so `quality_score` remains null. GitHub snapshot: 49 total,
49 open, 0 merged. Installed Windows build remains at `3815ef8`.

Latest coverage work: [draft PR #52](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/52),
`feature/ai-review-field-semantics` on #51, implementations `0d04488` and
`312a5a3`. Specialist prompts now explain snapshot fields, whitespace-only
summaries are rejected, and a public reference-fact file supports manual
omission checks bound to benchmark responses. A local `pinyo-chat` /
`pinyo-coder` run completed 2/3 public cases before the prompt clarification
and 3/3 after it, but still made unsupported claims. These two runs preceded
the parser and coverage-reference changes. The selected AI suite passed 178
tests with `PYTHONUTF8=1`. No human labels or final-code live run exist; review
quality remains unscored. GitHub snapshot: 50 total, 50 open, 0 merged.
Installed Windows build remains at `3815ef8`.

Follow-up local study: [`review-local-study-2026-10-06.md`](../../benchmarks/ai/review-local-study-2026-10-06.md)
compares three named Ollama pairings on the same three public cases. Structural
completion ranged from 2/3 to 3/3, while preliminary Codex inspection found
unsupported field claims even in a 3/3 run. A stronger prompt trial did not
resolve them and was reverted. These agent labels are not independent human
assessment; quality remains unscored. The broad Windows test pass stopped at
an unmodified Composer scale-label pixel test after 451 passed and 11 skipped.
No new build was installed. The next review slice should validate claims
against snapshot fields, then rerun independent assessment and the broad gate.

Current Windows CI follow-up: [draft PR #55](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/55),
`ci/windows-qt-gate` on PR #54, adds an offscreen Windows Qt smoke job and
fixes Composer radial-property editing. Local targeted checks passed 45 tests
with native Qt, 46 with offscreen Qt, and 116 in the curated smoke. The first
hosted native full-suite job exited 1 at about 4% without a Python traceback;
the revised hosted Windows smoke passed 116 tests. The Ubuntu fast run found one platform-dependent width assertion (3,773 passed);
the test now compares short- and long-hint baselines. All 14 sheet-tab tests
pass locally with both native and offscreen Qt; hosted revalidation is pending. A frozen `12d783c`
bundle passed startup checks but is not installed; details and limitations
are in [`WINDOWS_QT_INTEGRATION_GATE.md`](WINDOWS_QT_INTEGRATION_GATE.md).

Latest verified CI: run [37465329555](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37465329555) passed both jobs at `1b8dfb2` (PR #55). This supersedes the pending status above.

Nested-selection follow-up on `fix/outliner-nested-selection`, based on
`ci/windows-qt-gate`: search visits every sibling and clearing it restores
all nested rows; cross-parent selections are reflected back into the tree
so hide/lock use the actual viewport selection. Nine Outliner tests passed
on both native Windows Qt and offscreen. Both added regressions fail on
the parent code. No installed-binary changes. See [OUTLINER_NESTED_SELECTION.md](OUTLINER_NESTED_SELECTION.md).

Outliner performance follow-up: [draft PR #57](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/57) on `perf/outliner-selection-sync` changes only
selected rows during viewport sync. See [OUTLINER_SELECTION_PERFORMANCE.md](OUTLINER_SELECTION_PERFORMANCE.md)
for measured scope and limits.

Outliner refresh follow-up: [draft PR #58](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/58) on `perf/outliner-incremental-refresh` updates
existing rows when the hierarchy is stable; see
[OUTLINER_INCREMENTAL_REFRESH.md](OUTLINER_INCREMENTAL_REFRESH.md) for
measured scope and regression checks.

Tag consistency follow-up: [draft PR #59](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/59) on `fix/tag-annotation-selection` clears selected
annotations when their Tag becomes hidden/locked or they are assigned to
one; see [TAG_ANNOTATION_SELECTION.md](TAG_ANNOTATION_SELECTION.md).

Active Tag indicator follow-up: [draft PR #60](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/60) on `fix/active-tag-indicator` keeps the Tags
panel marker aligned with the toolbar and scene; see
[ACTIVE_TAG_INDICATOR.md](ACTIVE_TAG_INDICATOR.md).

Move Autofold follow-up: [draft PR #61](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/61) on `test/autofold-shared-vertex-grid` adds a
multi-face topology/preview/Undo gate and includes the four Move suites in
Windows CI. See [AUTOFOLD_SHARED_VERTEX_GATE.md](AUTOFOLD_SHARED_VERTEX_GATE.md).

Further Autofold stress in [draft PR #62](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/62) on `test/autofold-holed-nonmanifold` checks a face
with an opening and a three-face radial edge. See
[AUTOFOLD_OPENING_RADIAL_GATE.md](AUTOFOLD_OPENING_RADIAL_GATE.md).

Move Autofold scope follow-up in [draft PR #63](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/63) on `perf/move-local-autofold` makes commit
inspect the same incident faces as preview. See
[AUTOFOLD_LOCAL_SCOPE.md](AUTOFOLD_LOCAL_SCOPE.md) for regression and
real-example phase timings.

The same branch now includes `scripts/bench_move_command.py` for repeatable
in-memory Move/Undo timing on bundled examples. A cumulative frozen build
from `7ebc770` is staged and self-checked, but remains separate from the
installed `3815ef8` build. See [AUTOFOLD_LOCAL_SCOPE.md](AUTOFOLD_LOCAL_SCOPE.md)
and [INSTALLATION.md](INSTALLATION.md).

Plain Move snapshot follow-up in [draft PR #64](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/64)
on `perf/move-position-snapshot` keeps only moved
positions and the vertex registry for local moves that stay planar, while
folding and broad edits retain full snapshots. See
[MOVE_POSITION_SNAPSHOT.md](MOVE_POSITION_SNAPSHOT.md) for correctness gates,
benchmark method, and limits.

The next Move follow-up in [draft PR #65](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/65)
on `perf/move-history-transaction` removes History's
redundant whole-mesh guard for fresh Move commands while retaining rollback
from the command's own pre-edit snapshot. A native Windows GL probe found
edge-buffer rebuilds still dominate the forced paint after a local Move. See
[MOVE_HISTORY_GUARD.md](MOVE_HISTORY_GUARD.md) for tests, benchmark method and
the next renderer target.

Loose-edge rebuild follow-up in [draft PR #67](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/67)
on `perf/move-loose-edge-render` skips soft/hidden edges before Tag lookup
and resolves Tag visibility once per rebuild. See
[MOVE_LOOSE_EDGE_RENDER.md](MOVE_LOOSE_EDGE_RENDER.md) for measurements,
regression checks and limits.

Face-colour buffer follow-up in [draft PR #68](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/68)
on `perf/move-face-color-buffer` reuses packed shaded triangles when both the
geometry and effective front colour agree. See
[MOVE_FACE_COLOR_BUFFER.md](MOVE_FACE_COLOR_BUFFER.md) for the measured scope
and remaining rendering work.

Face visibility and back-buffer follow-up in [draft PR #69](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/69)
on `perf/move-face-visibility-back-buffer` batches Tag lookup for the plain
scene and retains unchanged back-side positions. See
[MOVE_FACE_VISIBILITY_BACK_BUFFER.md](MOVE_FACE_VISIBILITY_BACK_BUFFER.md) for
validation, benchmark boundaries and the next renderer target.

Face geometry-key follow-up in [draft PR #70](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/70)
on `perf/move-face-signature-tuples` reads each Qt vertex position as a tuple
in one call. See [MOVE_FACE_SIGNATURE_TUPLES.md](MOVE_FACE_SIGNATURE_TUPLES.md)
for the measured scan reduction and frame-time limits.

Loose silhouette follow-up in [draft PR #71](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/71)
on `perf/move-silhouette-rebuild` batches soft-edge Tag visibility and reads
profile planes directly from shared vertices. See
[MOVE_SILHOUETTE_REBUILD.md](MOVE_SILHOUETTE_REBUILD.md) for validation,
benchmark scope and the next measured renderer bottleneck.

Face bucketing follow-up in [draft PR #72](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/72)
on `perf/move-face-bucket-key` shares the geometry retention and signature
lookup between front and default-back packing. See
[MOVE_FACE_BUCKET_KEY.md](MOVE_FACE_BUCKET_KEY.md) for the focused benchmark,
test scope, CI result, and remaining real-interaction measurement.

Silhouette plane follow-up in [draft PR #73](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/73)
on `perf/move-silhouette-face-plane` gathers shared Face planes through
NumPy indices once per renderer rebuild. See
[MOVE_SILHOUETTE_FACE_PLANES.md](MOVE_SILHOUETTE_FACE_PLANES.md) for exact
array comparison, local performance evidence, CI, and the next validation.
