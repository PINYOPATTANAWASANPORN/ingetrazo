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
- **Phase 4 — 45%:** two provider-backed read-only specialists execute in
  parallel in the Assistant over one bounded snapshot, with per-role model
  names saved separately for each provider. Conflicts, partial
  failures, stale results and cancellation are handled. External MCP review
  assignments/submissions now share validation and conflict aggregation.
  General modeler orchestration remains.
- **Phase 5 — 35%:** the early local-security gate exists; audit export,
  recovery, resources/prompts, compatibility tests, and benchmarks remain.

## Recommended next sequence

### 1. Extend architectural editing after this creation slice

Wall creation with door/window openings, rectangular slabs, top-level component
copies, and scoped parent-coordinate primitives are implemented. See
[the creation contract](../ai-creation-contract.md). Remaining work includes
cutting existing walls, arbitrary slab profiles, shared-definition insertion,
and an isolated geometry viewport preview.

### 2. Extend specialist orchestration

The Assistant now executes `model_structure` and `task_requirements` through
two calls to the selected provider, using per-role model choices, with no scene or write tools in the
workers. External MCP clients can dispatch their own reviewers using the
role-bound snapshot protocol; the app does not launch those providers. See [the review contract](../ai-specialist-review.md). Next add an
cross-provider role credentials and audit export before allowing
modeler proposals. Retain coordinator-only merge/commit and explicit approval.

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
