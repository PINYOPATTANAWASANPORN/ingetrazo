# AI Agent implementation handoff

## Current architecture

| Concern | Main modules | Contract |
| --- | --- | --- |
| Bounded reads | `core/ai_context.py`, `plugins/ai_bridge.py` | Paginated, revision-aware context and stable group UIDs |
| Permissions | `plugins/ai_bridge.py`, MCP server code | Loopback credential, bounded messages, session-only elevated permissions |
| Typed changes | `core/ai_changes.py` | Propose → preview → validate → request commit → in-app approval; idempotent and leased |
| Task contracts | `core/ai_tasks.py` | Short intent becomes a pinned goal, scope, constraints, assumptions, criteria, plan, and lifecycle |
| Assistant UI | `plugins/ai_assistant.py` | Scope/Goal/Execution controls, typed preview with Apply/Discard, visible assumptions, read-only enforcement |
| Project memory | `core/ai_memory.py`, `core/scene.py`, `formats/igz.py` | Explicit user-owned facts, bounded, `.igz`-persistent, undoable, snapshotted per task |
| Undo | `core/history.py` | Document mutations are commands and should be one reversible step |

## Non-negotiable invariants

1. Stable entity scope is resolved once when a task starts. An agent cannot
   silently widen `entity_ids` later.
2. Content revision and view revision have different meanings. Selection and
   camera changes must not stale a content proposal.
3. External clients cannot approve their own mutation. MCP requests commit;
   the in-app Apply action grants approval.
4. Read-only execution and `check`, `quantify`, or `explain` goals cannot run a
   Python recipe.
5. Raw Python is an explicitly enabled migration/developer escape hatch, not
   the normal agent write interface.
6. Persistent project memory is written only by an explicit user edit. Each
   task receives a snapshot, so memory cannot drift mid-run.
7. Large responses stay bounded; lists paginate and screenshots use explicit
   detail choices.
8. A failed, stale, discarded, or cancelled proposal leaves the live document
   unchanged.

## Phase status

- **Phase 1 — 90%:** context/read contract works; reproducible baseline corpus
  and token/latency measurements remain.
- **Phase 2 — 90%:** property, tag, material, top-level transform, box,
  cylinder, wall/openings, slab and component-copy actions work through
  preview and approval. Explicit parent coordinates support nested primitives
  in non-component instance containers. Cutting existing walls, nested transforms,
  and branch-rendered geometry previews remain. Raw Python is off by default
  and requires an explicit session permission.
- **Phase 3 — 90%:** task engine, compact controls, assumptions, project
  memory, in-app typed approval, streaming, cooperative cancellation, local
  suggestion chips, and the versioned evaluation corpus work. A richer visible
  plan and measured provider baselines remain.
- **Phase 4 — 55%:** two provider-backed read-only specialists execute in
  parallel in the Assistant over one bounded snapshot, with per-role provider
  and model choices using provider-scoped saved keys. Conflicts, partial
  failures, stale results and cancellation are handled. External MCP review
  assignments/submissions now share validation and conflict aggregation.
  General modeler orchestration remains.
- **Phase 5 — 45%:** the local-security gate and explicit unsigned audit files
  exist; signed evidence, recovery, compatibility tests and benchmarks remain.

## Recommended next sequence

### 1. Extend architectural editing after this creation slice

Wall creation with door/window openings, rectangular slabs, top-level component
copies, and scoped parent-coordinate primitives are implemented. See
[the creation contract](../ai-creation-contract.md). Remaining work includes
cutting existing walls, arbitrary slab profiles, shared-definition insertion,
and an isolated geometry viewport preview.

### 2. Extend specialist orchestration

The Assistant now executes `model_structure` and `task_requirements` through
two role-specific provider connections over one snapshot, with no scene or
write tools in the workers. External MCP clients can dispatch their own
reviewers using the role-bound snapshot protocol; the app does not launch
those providers. See [the review contract](../ai-specialist-review.md).
Measure provider compatibility and review quality before allowing modeler
proposals. Retain coordinator-only merge/commit and explicit approval.

### 3. Capture measurable provider baselines

Run `benchmarks/ai/task-corpus-v1.json` against named provider/model versions
and save the required JSONL telemetry. Record hardware and application commit
with each run. Compare completion, tokens, tool calls, p50/p95 latency, first
preview, rollback, and manual corrections; keep absent samples as null rather
than estimates.

## Validation evidence

Latest selected command:

```powershell
$env:PYTHONUTF8='1'
& 'C:\Users\Lenovo\Desktop\IngeTrazoTest\.venv\Scripts\python.exe' -m pytest -q `
  tests/test_ai_external_review.py tests/test_ai_review.py `
  tests/test_ai_assistant.py tests/test_ai_tasks.py tests/test_ai_context.py `
  tests/test_ai_bridge.py tests/test_ai_changes.py
```

Result: **107 passed** using fake provider results and authenticated local
bridge calls. This covers role/snapshot binding, retries, conflicts, quotas,
stale/cancelled results, session restart, MCP error markers, per-role model
routing, inheritance, configuration bounds and provider-scoped settings.
Compilation and `git diff --check` passed. No real-provider benchmark or full
repository release certification is claimed.

## Stack base for continuation

`feature/specialist-model-selection` is stacked on `feature/mcp-specialist-protocol`
(PR #40). Delivered by [#41](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/41)
at code commit `b7a181f`. Verify the latest branch head before continuation.


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


Latest delivery: [PR #45](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/45), `feature/ai-cross-provider-review` on #44; implementation `23da695`. Selected regression suite: 123 passed with simulated providers. GitHub snapshot: 43 total, 43 open, 0 merged. Earlier counts are historical. Installed build unchanged.


## Installed stack (2026-10-06)

The Windows installation now includes code through `b0dce0f`, including the
cross-provider read-only review workflow. Its main executable passed the
installed-path self-check and GUI launch; its MCP executable returned 22 tools,
including specialist review and audit endpoints. This does not supply the
missing real-provider quality or latency baseline. The source commit, hashes,
rollback location, and packaging failure analysis are in
[`INSTALLATION.md`](INSTALLATION.md).


## Review measurement slice (2026-10-06)

`feature/ai-review-benchmark` at `a33fb8a` adds three deterministic public
metadata fixtures, per-role elapsed time, an explicit `--run` benchmark CLI,
and offline p50/p95 summaries. `--run` resolves credentials from environment
variable names, not config literals; JSONL excludes snapshots, reviewer prose,
keys and error text. Reported tokens and quality scores remain null. The
selected AI regression suite passed 128 tests with fake providers, and the
default CLI validation contacted no provider. Read
[`../../benchmarks/ai/README.md`](../../benchmarks/ai/README.md) before a live
run. No real-provider results have been captured. The branch is in
[draft PR #46](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/46),
stacked on PR #45.

## Narrow AI tray and installed build (2026-10-06)

[Draft PR #47](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/47)
uses full-width suggestion rows, gives Export review its own row, and shows why it is disabled
before a completed, current-revision two-specialist review. Its Assistant UI
suite passed 46 tests. The Windows bundle built from `b2573b7` was installed
at `C:\Program Files\IngeTrazo`; installed-path hashes, `--check`, and MCP
`tools/list` (22 tools) passed. The GUI layout has not been visually rechecked
after installation, and no real-provider review benchmark has been run.
