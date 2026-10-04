# AI Assistant and MCP agent roadmap

## Objective

Let a user state a short design intent, such as "make this room suitable for
six people", and have IngeTrazo gather the current model context, make a
reviewable plan, perform the work, verify the result, and report assumptions.
The same execution engine must serve the in-app assistant and external MCP
clients.

Success means fewer user words and fewer model/tool round trips, while every
model mutation remains attributable, bounded, validated, and undoable.

## Current baseline

The current implementation already has useful foundations:

- `core.ai.run_transactional` applies one Python recipe as one undo step and
  rolls it back on error.
- `core.ai_recipes` gives both AI entry points the same modelling reference
  and high-level geometry helpers.
- Groups already carry save/load-stable random `uid` values, and
  `Scene.groups_by_uid()` resolves the complete nested group tree.
- `scene.version` and `scene.content_version` already invalidate UI and
  geometry caches, although neither is yet a durable concurrency contract.
- The in-app assistant has a bounded agent loop, conversation compaction,
  provider selection, optional vision, and viewport feedback.
- The MCP server exposes `run_python`, `query_model`, `screenshot`, `undo`,
  and `redo` over a localhost bridge.

The main limitations are architectural rather than provider-specific:

- Natural-language intent is converted directly into arbitrary Python.
- The current bridge has no authentication: it trusts a loopback client, and
  `run_python` executes `exec` in the desktop application's process.
- A bridge/socket timeout only stops waiting for a reply; it cannot safely
  interrupt a Python recipe already running on the Qt UI thread.
- `SnapshotImport` is a useful rollback wrapper for mesh changes and newly
  appended scene lists, but it is not a general transaction log for every
  mutation an unrestricted script can make to existing groups and metadata.
- `query_model` is a shallow document summary; the model must spend calls
  discovering relevant entities and relationships.
- There is no structured plan, change set, validation report, task identity,
  or conflict control shared by the two AI entry points.
- Undo is global and positional. One agent can accidentally undo another
  agent's work.
- The in-app assistant is one model acting serially. MCP permits external
  agents, but IngeTrazo does not coordinate their roles or concurrent writes.
- Provider and connection settings dominate the UI, while common modelling
  intents have no compact controls, presets, or reusable project context.

## Target architecture

### 1. Deterministic action layer

Add a typed `core/ai_actions` layer above meshes and below agents. Actions
should express user intent with JSON-compatible parameters, for example:

- `inspect_scene`, `inspect_entities`, `inspect_selection`
- `create_group`, `create_component`, `create_wall`, `create_opening`
- `transform_entities`, `assign_material`, `assign_tag`
- `set_visibility`, `set_lock`, `rename_entities`
- `measure`, `validate_geometry`, `frame_entities`

Each action declares whether it is read-only, its affected entity IDs, input
schema, preconditions, estimated cost, permissions, and the existing command
class or reversible state needed for undo. The action implementation must use
the normal history command path; it must not rely on a generic mesh snapshot
to reverse arbitrary metadata edits.

Python recipes remain a migration and developer escape hatch, not the trusted
action layer. They require an explicit per-session “allow raw Python” choice,
a visible warning that they run in-process, a restricted capability scope,
an input-size limit, audit record, and a one-shot confirmation before a
write. A hard CPU-time limit is not credible inside the Qt process; reliable
cancellation requires actions that yield between bounded steps or execution
in a separate, restricted worker process with an explicit data boundary.

### 2. Structured model context and identity

Replace repeated discovery prompts with compact context assembled inside the
application:

- existing group UIDs and a hierarchical scene outline
- active edit context, selection, active tag, units, camera, and bounds
- entity names, types, transforms, materials, tags, hidden/locked state
- nearby or relevant entities selected by spatial and semantic filters
- a content revision and changes since the agent last looked

Do not replace the existing group UID or expose Python object identity. Extend
the current identity system to other user-addressable objects only where an
AI action needs durable references. Faces, edges, and vertices are frequently
rebuilt by modelling operations, so their references should be scoped to a
specific content revision and expressed as a group UID plus a revision-bound
topological selector. The API must report a stale reference instead of
silently resolving it to a different element.

Do not use `scene.version` directly as the optimistic concurrency token: it
also changes for selection and other UI operations. Introduce a monotonic
`content_revision` for saved model content, and a separate ephemeral
`view_revision` if agents need camera/selection freshness. Existing
`scene.content_version` can seed this design but its current cache-oriented
semantics must first be documented and tested.

Expose this through MCP resources and prompts only after capability
negotiation, with paginated tools as the compatibility path. The assistant
should receive a small automatic context packet for every user turn instead
of the full model or a long explanation written by the user. Context assembly
must be budgeted: start with selection/current edit context, include spatial
neighbours only when relevant, and return explicit “truncated” cursors rather
than silently dropping model data.

### 3. Task and change-set engine

Represent one user request as an `AITask` with:

- task ID, user intent, constraints, assumptions, and acceptance criteria
- base document revision and allowed scope
- plan steps and assigned agent role
- proposed actions and validation results
- status, timing, token/tool usage, and error history

Agents write declarative actions to an isolated `AIChangeSet`; a preview is
rendered from the change set or a clone, never by temporarily mutating the
live document and attempting to undo it. The engine validates the complete
set and commits its constituent history commands as one named compound undo
operation. A change set whose base revision is stale must rebase or request
review; it must never silently overwrite newer work.

Use a document-wide write lease while a commit is pending. The lease holder
may prepare only its declared scope; all other writers receive `busy` or
`stale_revision`, never a blocking wait. Manual user edits always take
priority: they invalidate a preview and release or deny the agent's commit.

### 4. Orchestrator and specialist roles

Use one coordinator and start specialists only when the task benefits from
them. Useful roles are:

- **Planner**: turns short intent into constraints and an action graph.
- **Modeler**: creates or edits geometry through typed actions.
- **BIM/architecture specialist**: checks rooms, openings, tags, levels, and
  domain rules.
- **Visual reviewer**: examines viewport renders and composition.
- **Geometry validator**: checks dimensions, watertight solids, collisions,
  normals, locked entities, and requested tolerances.

Read-only specialists can run concurrently on the same document revision.
Only the coordinator may request a commit, and the document service enforces
the write lease rather than trusting an agent role label. Independent write
branches may be prepared concurrently, but the coordinator must merge them
into one preview and resolve overlapping entity IDs before commit.

For small requests the coordinator should call the action layer directly;
multi-agent work must not be mandatory overhead.

### 5. Short-prompt experience

The input area should support compact intent plus optional chips instead of a
long prompt:

- Scope: selection, current group, current room, visible model, whole model
- Goal: create, revise, furnish, check, quantify, explain
- Constraints: dimensions, style, material, tag, budget/detail level
- Execution: preview first, apply safe changes, or analysis only

Add context-aware suggestions such as “align selected windows”, “create a
component from repeated groups”, and “check this room”. Store project facts
such as typical floor height and preferred wall thickness as explicit,
editable project memory. Never infer durable preferences from chat without
showing what will be saved.

The assistant should ask a question only when a missing answer changes the
geometry materially. Otherwise it should use visible assumptions and allow
the user to edit them before commit.

### 6. MCP evolution

Keep the five existing tools for compatibility and add versioned, focused
tools:

- `get_document_context`
- `find_entities`
- `get_entities`
- `create_task` / `get_task`
- `propose_actions`
- `preview_changes`
- `validate_changes`
- `commit_changes` / `discard_changes`
- `render_view`
- `get_capabilities`

Adopt the current MCP protocol through capability negotiation rather than a
single hard-coded version. Declare only the server features actually
implemented; add `tools/list` pagination, `listChanged` notifications when
permissions change, progress, cancellation, resources, and prompts in small,
independently tested increments. Keep the current five tools as a legacy
compatibility profile until common clients have been exercised against the
new profile.

Long operations should use progress notifications and cooperative
cancellation between bounded action steps. Tool results should return
structured content plus a short human-readable summary. Large entity lists
and images need pagination or explicit detail levels. Every mutation call
needs a task ID, base revision, idempotency key, and affected scope.

The bridge should continue listening only on loopback by default and enforce
a bounded message size. For stdio MCP, deliver a short-lived bridge credential
to the local server process through its environment or an OS-protected
session channel; never persist it in desktop configuration, command history,
or logs. This is distinct from HTTP MCP authorization: if an HTTP transport
is added later, implement its standard OAuth/resource-server flow rather than
reusing a local bridge token. When a user deliberately configures a remote
tunnel, require explicit remote mode, mutually authenticated transport, and
a restricted tool policy.

Expose an activity panel showing the connected client, active task, requested
tools, write lease, permissions, and pending changes. Raw Python must be off
by default for external MCP clients and require the same explicit advanced
permission described above. Typed actions are the only write interface in
normal operation.

### 7. Provider connection layer

Separate provider setup from agent behaviour. Add:

- connection profiles with clear local/cloud and vision/tool capability
  indicators
- capability probing rather than relying only on model-name heuristics
- streaming output, cancellation, timeouts, retry policy, and rate-limit
  status
- per-task model routing: fast model for classification/context selection,
  capable model for planning, vision model only when a render is needed
- secret storage through the operating-system credential store rather than
  plain application settings
- usage telemetry shown locally: latency, input/output size, calls, retries,
  and estimated cost when the provider reports enough data

Model routing is opt-in and policy-driven. The UI must show which provider
receives model context, screenshots, and project memory before the task runs;
the routing layer must not send content to an additional cloud provider merely
to reduce latency or cost.

## Delivery plan

Implementation status (2026-10-04): Phase 1's bounded context contract and
MCP read profile are implemented. The first Phase 2 security gate is also in
place: the loopback bridge authenticates requests with a rotating local
credential, bounds messages, reports client activity, and keeps raw Python
and global undo/redo disabled unless the user opts in for that session. The
first typed-write slice implements preview, validation, idempotency, a
document write lease, stale-revision rejection, discard, and one-step undo for
container naming, visibility, locking, and existing-tag assignment. MCP can
request a commit, but only the in-app Apply button can approve it. Transforms,
materials, creation actions, and branch-rendered geometry previews remain for
later Phase 2 slices.

### Phase 1 — shared context and typed read tools

Extend the existing group UID system, add revision-bound references for
lower-level geometry, define content/view revision semantics, build
hierarchical context, `find_entities`, `get_entities`, and a capability
registry. Use them from both the in-app assistant and MCP. This immediately
shortens prompts and reduces introspection without changing write behaviour.

Acceptance targets:

- “What is in this model?” takes one tool call.
- A named or selected object can be resolved without Python introspection.
- Existing group UIDs remain stable across save/load, nested edits, and
  replacement operations; stale topology references fail explicitly.
- Selection-only and camera-only changes do not invalidate a pending content
  proposal.
- Context responses are paginated and remain bounded on large models.
- Existing MCP clients and tests keep working.
- Record a versioned baseline corpus, raw measurements, hardware/provider
  details, and a privacy-safe fixture model before setting improvement
  percentages.

### Phase 2 — typed writes and preview

Implement the first high-value actions for selection, groups/components,
transforms, materials, tags, walls, and openings. Add preview, validation,
commit, discard, and named undo.

Acceptance targets:

- Common edits require no generated Python.
- The user sees affected entities, assumptions, and validation before commit.
- A committed task is one undo item; discard leaves no document change.
- Repeating a request with the same idempotency key creates no duplicates.
- A failed or cancelled preview cannot change the live document.
- Each typed action proves its command-based undo/redo behaviour, including
  group properties and scene metadata, rather than only mesh geometry.

### Phase 3 — concise assistant workflow

Add intent classification, automatic scoped context, suggestion chips,
editable assumptions, project memory, streaming, and cancel. Route simple
requests directly and complex requests through a visible plan.

Acceptance targets:

- Representative tasks can start from compact intent, without sacrificing a
  measurable acceptance rate on the fixed corpus.
- Clarifying questions occur only for acceptance-critical ambiguity, or the
  assistant records a visible assumption.
- Targets for median tokens, tool calls, p95 latency, and first-preview time
  are set after Phase 1's baseline; each target is reported by task category
  and provider rather than as one aggregate percentage.

### Phase 4 — multi-agent orchestration

Add the task graph, specialist roles, read concurrency, branch previews,
conflict detection, coordinator-only commit, and an agent activity view.

Acceptance targets:

- Two read-only reviewers can operate concurrently on one revision.
- Concurrent proposals touching the same entity produce a visible conflict.
- No specialist can directly mutate the live model.
- One final commit contains provenance and validation from every contributor.

### Phase 5 — hardening and ecosystem

Add session authentication, permissions, audit export, recovery, MCP
resources/prompts, compatibility tests against common MCP clients, provider
capability tests, and large-model performance benchmarks.

Do the bridge authentication and raw-Python gating at the start of Phase 2,
not as a final hardening task: `run_python` is already remotely reachable by
any local process while the bridge is active. Phase 5 then extends this with
remote-mode transport, recovery, and ecosystem compatibility.

## Evaluation suite

Keep a fixed set of short requests covering inspection, precise edits,
architecture, visual matching, and destructive mistakes. Record:

- completion and geometry-validation rate
- user words and clarification count
- model tokens, provider calls, MCP calls, and screenshots
- time to first preview and time to accepted result
- rollback, duplicate, conflict, and stale-revision failures
- manual corrections after the agent reports completion

For each case, define an expected action trace, valid tolerances, whether
preview/confirmation is required, and an independent deterministic validator.
Score task completion only when that validator passes and the user-accepted
state is preserved after save/load. Report medians and p95 values separately,
retain failed runs, and never label projected token savings as measured.

Include adversarial cases: hidden or locked objects, nested components,
ambiguous units, stale entity IDs, disconnected clients, cancelled tasks,
provider truncation, two agents editing the same object, and a validator that
rejects the modeler's proposal.

Also test a malicious or faulty local client: missing/incorrect session token,
oversized request, forbidden raw-Python call, infinite or long-running action,
client disconnect during preview, user edit during a write lease, and a
metadata mutation that must be rolled back. Define expected behaviour before
implementation; “the socket timed out” is not cancellation.

## PR sequence and decision gates

Keep the roadmap reversible by delivering it in the following order:

1. **Context contract and baseline:** document content/view revision rules;
   add fixture models, read-only context tests, and measurement capture. Do
   not change MCP behaviour yet.
2. **Context service and MCP read profile:** implement paginated context,
   search, and entity-detail tools backed by the new contract; retain the
   five legacy tools and test both profiles.
3. **Permission and bridge controls:** add visible client activity,
   bounded requests, raw-Python gating, and the local credential mechanism.
   Do not advertise typed writes before this gate passes.
4. **Typed actions and preview:** implement a small action set with command
   undo/redo, deterministic validation, preview/discard, idempotency, and
   write leases. Begin with transforms, tags, materials, and naming; add
   architecture-specific creation after the generic mechanics are proven.
5. **Assistant and multi-agent orchestration:** add compact intent UI,
   automatic scoped context, then specialist proposals and coordinator-only
   commits. Enable each role only after its corpus tests meet the agreed
   baseline targets.

At each gate, stop expansion if compatibility, rollback, privacy, or
measurement evidence fails. Fix the contract and its tests before adding more
tools or roles.

## Recommended first implementation slice

Start with the first PR-sequence item: a context contract and baseline. Reuse
group UIDs, specify revision-bound references for other addressable entities,
and add fixture models plus tests that pin the response shape, pagination,
stale-reference handling, and measurement format. The next PR can then add
the three read-only APIs — document context, entity search, and entity detail
— to both assistant context assembly and MCP while retaining every current
tool. This sequence provides immediate value and establishes the contracts
required by preview, typed writes, and multiple agents without risking model
mutations.
