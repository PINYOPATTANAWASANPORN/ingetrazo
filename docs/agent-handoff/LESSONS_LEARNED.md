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

Roadmap wording must match code. A line-wrap edit once produced the misleading
phrase “project streaming”; it was corrected in `6c8364c`. Keep a structured
state file beside prose so future agents can detect contradictions instead of
propagating them.

