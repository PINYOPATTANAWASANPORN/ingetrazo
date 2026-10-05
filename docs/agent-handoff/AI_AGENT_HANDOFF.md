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
- **Phase 2 — 85%:** property, tag, material, top-level transform, box, and
  cylinder actions work through preview and approval in MCP and the in-app
  Assistant. More architectural primitives, nested world-space transforms,
  and branch-rendered geometry previews remain. Raw Python is off by default
  and requires an explicit session permission.
- **Phase 3 — 78%:** task engine, compact controls, assumptions, project
  memory, and in-app typed approval work. Suggestion chips, streaming,
  cooperative cancel, visible plan, and corpus evaluation remain.
- **Phase 4 — 15%:** plans name roles, but no specialist actually executes.
- **Phase 5 — 35%:** the early local-security gate exists; audit export,
  recovery, resources/prompts, compatibility tests, and benchmarks remain.

## Recommended next sequence

### 1. Streaming and cooperative cancellation

Stream provider text without allowing partial model writes. Add Cancel to stop
network generation immediately and long typed work between bounded steps.
Cancellation must transition the task to a terminal state and release leases.
A timeout or disconnected socket alone is not proof of cancellation.

### 2. Context-aware suggestions and measurable evaluation

Generate local suggestion chips from deterministic document state before
asking a model. Establish a fixed request corpus and record completion,
tokens, provider/tool calls, p50/p95 latency, time to first preview, rollback,
and manual corrections. Never report projected savings as measured results.

### 3. Expand typed architectural creation

Build wall, opening, slab, and component-instance actions on the same pure
preview contract. Do not wrap the existing in-process recipe executor; build
prepared entities off-scene and commit them through commands. Add an explicit
parent/local-coordinate contract before allowing nested creation.

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

Result: **99 passed**. The primitive-creation slice adds focused off-scene
preview, material/tag, component, undo/redo, MCP approval, and session
permission tests. Python compilation for touched modules and
`git diff --check` also passed. Run the relevant subset again
after every contract change; run the full suite before claiming release
readiness.

## Stack base for continuation

The primitive-creation slice is on `feature/ai-typed-creation`, stacked on
`feature/ai-assistant-typed-preview` and delivered by
[#35](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/35) at code commit
`f9cca37`. Verify GitHub and the branch head before starting the next narrow PR.

