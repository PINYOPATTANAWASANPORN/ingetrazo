# Extracted engineering knowledge

## State belongs in the correct scope

- UI preferences such as the last selected intent mode belong in `QSettings`.
- Project facts belong in `Scene` and `.igz`, because collaborators opening
  the file must see the same facts.
- Per-request assumptions belong in the task contract and must not silently
  become durable memory.
- Tests that mutate `QSettings` must restore or isolate every related key.
  Resetting execution mode while leaving a persisted read-only goal caused
  later recipe tests to fail even though their code had not changed.

## A task is a contract, not a chat string

Resolve scope and document revision before model work begins. Store goal,
execution policy, constraints, assumptions, acceptance criteria, and a plan.
Return that same contract to UI and MCP clients. This prevents short prompts
from being ambiguous without forcing users to repeat technical context.

## Separate reads, proposals, and commits

Read tools may run freely against a pinned revision. A model can propose typed
actions, but preview and deterministic validation happen before approval. Only
the application commits, as one undoable command. Idempotency keys prevent a
network retry from duplicating edits, and a write lease prevents overlapping
commits.

## Read-only must be enforced below the prompt

Prompt wording is guidance, not a security boundary. The Assistant blocks
returned recipes when execution is `analysis_only` or the goal is `check`,
`quantify`, or `explain`. The change service also rejects writes for registered
read-only tasks. Keep both layers.

## A malformed typed reply must fail closed

The in-app Assistant treats a fenced JSON block as an attempted change
proposal. Incomplete JSON, extra top-level fields, empty actions, or a reply
that mixes JSON actions with Python is rejected visibly. It must never be
reinterpreted as prose or allowed to fall through to the legacy recipe path.
The preview holds no live mutation; revision and scope are checked again when
the user applies it.

## Creation previews must own prepared geometry off-scene

A typed creation action builds its complete Group or Component during
validation but does not append it to `Scene.groups`. The preview can therefore
report its stable UID, bounds, Tag, material, and component status without a
temporary live mutation. Approval inserts that same prepared entity through a
command; Discard simply releases it, and Undo removes it exactly.

Raw Python is a separate session capability. The model receives the current
permission in its task contract, and the UI still blocks returned code below
the prompt layer. A checkbox is explicit authorization for the current panel
session only and must not be persisted silently.

## Streaming output is not executable output

Provider chunks may be displayed as they arrive, but action parsing starts
only after the stream closes successfully. Cancellation must close the active
response, interrupt retry backoff, mark the task terminal, release a pending
proposal, and advance a local generation ID. The generation check is what
prevents already queued chunks or a late complete response from executing
after the user cancelled. A socket timeout by itself is not cancellation.

## Suggestions should be deterministic controls, not hidden prompts

A useful suggestion can be derived from empty/visible/selected document state
without spending tokens. A chip should fill the same visible Scope, Goal,
Execution, and prompt fields the user could edit manually; it must not send,
execute, or write project memory. Only selections with stable group/component
IDs may produce selection-scoped suggestions under the current contract.

A versioned corpus is evidence infrastructure, not evidence. Keep fixture
builders and required telemetry fields beside it, return null for metrics with
no samples, and report measured provider/model/hardware runs separately from
the task definitions.

## Revision semantics prevent false conflicts

Camera movement and selection changes are view state. They must not stale a
content proposal. Geometry, entity properties, tags, project memory, and other
saved document metadata are content changes and must advance content revision.

## Bounded context is a product feature

Stable UIDs, pagination, result caps, bounded metadata, and compact task
packets improve latency and safety together. Never fix a prompt-length problem
by serializing the entire scene. Component instances should share geometry in
render and pick structures rather than duplicating arrays.

## Platform fixes need platform-shaped tests

- Numeric widgets must force ASCII digits when the application language can
  otherwise select native digits unexpectedly.
- Windows paths and filenames need explicit handling for long paths and
  non-ASCII names.
- Network objects must be destroyed on the thread that owns them; this was
  material to the Windows base-map crash.

## UI state must stay truthful

Disable task controls while a task is active and restore them on every terminal
path. Show resolved scope, goal, entity count, and execution mode. Refresh the
Project Memory count after document changes. Never display “done” for a recipe
that was blocked, truncated, rolled back, or never executed.

## Stacked PRs change status language

The presence of code on the top branch proves implementation in the stack,
not delivery to `main`. Report branch, commit, PR state, validation scope, and
installation separately. Preserve base order; rebasing a lower layer requires
checking every dependent PR.

## Documentation is executable coordination data

Architectural creation adds three constraints worth preserving: a copy helper
can mutate live source children even when it appears to return a new object;
pure preview must never call that promotion path. Nested coordinates must
compose parent placements and scope-check parent/source IDs, not only edited
entity IDs. A parent transform in the same batch invalidates a precomputed
creation preview, so it needs a separate proposal. Tests should check closed
edges AND signed volume after openings; watertightness alone does not detect
reversed wall reveal normals.

On Thai Windows, the selected bridge packaging tests use default text encoding
and fail with cp874 on UTF-8 repository files. Run the documented suite with
`PYTHONUTF8=1`; the initial architectural run had 91 passes and two encoding
failures before enabling this environment setting.

Roadmap wording must match code. A line-wrap edit once produced the misleading
phrase “project streaming”; it was corrected in `6c8364c`. Keep a structured
state file beside prose so future agents can detect contradictions instead of
propagating them.


## Parallel reviewers need independent transport cancellation

A provider cancellation token owns one response handle. Sharing one token
between concurrent calls can leave a socket running; give each role a token
and cancel the group. Capture bounded JSON on the GUI thread before dispatch,
then recheck document identity/revision and generation before accepting output.
A review is advisory: preserve disagreements, label partial failures, and never
feed its response through typed-action or Python execution.

Review-only controls must not overwrite normal goal/execution preferences.
The UI tests caught this leakage and a misapplied scene-variable edit; both
were corrected before the 85-test regression run passed. Keep a GUI lifecycle
test as well as worker tests: Qt slot exceptions can otherwise leave the UI busy.
