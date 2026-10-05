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
- **Phase 4 — 15%:** plans name roles, but no specialist actually executes.
- **Phase 5 — 35%:** the early local-security gate exists; audit export,
  recovery, resources/prompts, compatibility tests, and benchmarks remain.

## Recommended next sequence

### 1. Extend architectural editing after this creation slice

Wall creation with door/window openings, rectangular slabs, top-level component
copies, and scoped parent-coordinate primitives are implemented. See
[the creation contract](../ai-creation-contract.md). Remaining work includes
cutting existing walls, arbitrary slab profiles, shared-definition insertion,
and an isolated geometry viewport preview.

### 2. Read-only specialist execution

Start with two concurrent reviewers pinned to one revision. Specialists return
structured findings and cannot mutate the live scene. Add conflict detection
before permitting modeler proposals, then coordinator-only merge/commit.

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
  tests/test_ai_architectural_creation.py tests/test_ai_changes.py `
  tests/test_ai_tasks.py tests/test_ai_assistant.py tests/test_ai_bridge.py `
  tests/test_ai_context.py tests/test_transactional_history.py
```

Result: **95 passed**. This covers architectural topology/volume, parent
placement, source purity, task scope, Assistant approval and Undo/Redo, plus
existing bridge/context/history regressions. Initial execution without
`PYTHONUTF8=1` produced two cp874 decoding failures in packaging tests; the
configured run passes. This is a selected suite, not release certification.

## Stack base for continuation

The architectural-creation slice is on `feature/ai-architectural-creation`,
stacked on `feature/ai-context-suggestions` (PR #37). Refer to `state.json` for
the delivery commit and PR after publication. Verify GitHub and the branch
head before starting the next narrow PR.
