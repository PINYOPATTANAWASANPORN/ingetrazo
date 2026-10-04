# AI Agent implementation handoff

## Current architecture

| Concern | Main modules | Contract |
| --- | --- | --- |
| Bounded reads | `core/ai_context.py`, `plugins/ai_bridge.py` | Paginated, revision-aware context and stable group UIDs |
| Permissions | `plugins/ai_bridge.py`, MCP server code | Loopback credential, bounded messages, session-only elevated permissions |
| Typed changes | `core/ai_changes.py` | Propose → preview → validate → request commit → in-app approval; idempotent and leased |
| Task contracts | `core/ai_tasks.py` | Short intent becomes a pinned goal, scope, constraints, assumptions, criteria, plan, and lifecycle |
| Assistant UI | `plugins/ai_assistant.py` | Scope/Goal/Execution controls, visible assumptions, read-only enforcement |
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
- **Phase 2 — 70%:** property, tag, material, and top-level transform actions
  work through preview and approval. Creation actions, nested world-space
  transforms, and branch-rendered geometry previews remain.
- **Phase 3 — 70%:** task engine, compact controls, assumptions, and project
  memory work. Suggestion chips, streaming, cooperative cancel, visible plan,
  and corpus evaluation remain.
- **Phase 4 — 15%:** plans name roles, but no specialist actually executes.
- **Phase 5 — 35%:** the early local-security gate exists; audit export,
  recovery, resources/prompts, compatibility tests, and benchmarks remain.

## Recommended next sequence

### 1. Share typed tools with the in-app Assistant

Replace the Assistant's normal write path from generated Python recipes to the
same typed `AIChangeService` used by MCP. Keep recipes available only under the
advanced permission. Acceptance criteria:

- a rename/tag/material/top-level transform request produces a visible preview;
- Apply makes exactly one undo item and Discard makes none;
- stale revision, scope violation, duplicate idempotency key, and validation
  failure are visible and leave the model unchanged;
- read-only goals never create a pending change.

### 2. Streaming and cooperative cancellation

Stream provider text without allowing partial model writes. Add Cancel to stop
network generation immediately and long typed work between bounded steps.
Cancellation must transition the task to a terminal state and release leases.
A timeout or disconnected socket alone is not proof of cancellation.

### 3. Context-aware suggestions and measurable evaluation

Generate local suggestion chips from deterministic document state before
asking a model. Establish a fixed request corpus and record completion,
tokens, provider/tool calls, p50/p95 latency, time to first preview, rollback,
and manual corrections. Never report projected savings as measured results.

### 4. Read-only specialist execution

Start with two concurrent reviewers pinned to one revision. Specialists return
structured findings and cannot mutate the live scene. Add conflict detection
before permitting modeler proposals, then coordinator-only merge/commit.

## Validation evidence

Latest selected command:

```powershell
$env:PYTHONUTF8='1'
& 'C:\Users\Lenovo\Desktop\IngeTrazoTest\.venv\Scripts\python.exe' -m pytest -q `
  tests/test_ai_memory.py tests/test_ai_assistant.py tests/test_ai_tasks.py `
  tests/test_ai_changes.py tests/test_ai_bridge.py tests/test_ai_context.py `
  tests/test_group_material.py tests/test_entity_info_transform.py `
  tests/test_transactional_history.py tests/test_autosave.py `
  tests/test_document_camera.py
```

Result: **89 passed**. Python compilation for touched modules and
`git diff --check` also passed. Run the relevant subset again after every
contract change; run the full suite before claiming release readiness.

## Stack base for continuation

Start from `feature/ai-project-memory`/`6c8364c` unless the stack has since
merged or changed. Verify GitHub first, then create one narrow branch and PR
per independently reviewable slice.

