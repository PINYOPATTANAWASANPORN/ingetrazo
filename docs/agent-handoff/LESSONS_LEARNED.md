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

## External role assignment is correlation, not identity

A role token binds submission to one review and snapshot, but a coordinator
with the bridge credential receives all assignments. Do not claim isolated
agent identities or independent authorship. Keep transport authentication,
role correlation and document write authority distinct. Idempotent identical
retries are safe; a different repeated submission must not overwrite findings.
Invalidate historical review reports on content changes before returning them.
Bridge cancellation rejects results but cannot cancel a provider owned by an
external process. Advertise that boundary and cap retained/active sessions.

## Model preferences belong to a provider and role

A model name accepted by one provider may fail on another. Store per-role
model choices under the provider, inherit the main model for blank fields,
and freeze the resolved choices before starting parallel requests. Preserve
requested model identity on failures as well as successes; do not silently
fallback or put credentials in a review report. Recorded names describe the
request, not proof of the backend model a remote service actually used.


## Review export (2026-10-05)

Finished current-revision reviews can be exported with Assistant **Export review…**
or MCP `export_specialist_review(review_id)`. MCP returns data only; the caller
chooses whether and where to save it. Assistant writes UTF-8 JSON atomically via
QSaveFile and rechecks document/task identity and revision after the save dialog.
Completed, partial and failed two-role outcomes are retained; unfinished,
cancelled and stale reviews cannot be exported. Export does not modify geometry
or Undo history.

Schema 1.0 includes UTC export time, revision, snapshot digest, role outcomes,
requested provider/model labels when available, findings and unresolved conflicts.
Only allowlisted report fields are serialized: connection settings, API keys,
submission tokens, raw snapshots and project-memory records are excluded.
Reviewer prose is included and can contain project-sensitive information; this
is not a general-purpose secret redactor. External roles may have no model label.

`integrity.payload_digest` is SHA-256 over UTF-8 JSON of `payload` with sorted
keys, no ASCII escaping, compact comma/colon separators and no NaN values
(Python `json.dumps(..., ensure_ascii=False, sort_keys=True,
separators=(",", ":"), allow_nan=False)`). It is an unsigned corruption check,
not proof of authorship or a tamper-proof audit trail. Reports are advisory
metadata checks, not geometric validation or regulatory certification.

Next: append-only audit history, provider compatibility/real token baselines,
and separately scoped cross-provider role credentials before modeler agents.


## Session review audit trail (2026-10-05)
Keep review history separate from the mutable latest report. A stale transition clears the report for current use but appends a metadata event, so a coordinator can see both states. Store only status/IDs/digests, deduplicate identical retries, paginate reads, and label the hash chain as unsigned session evidence. A chain kept in process memory is not durable or tamper-proof.


## Explicit review history file (2026-10-05)
A paged in-memory event trail is useful live but vanishes at session end. Add an explicit atomic save path and an offline verifier before calling it a reusable record. Verify both the outer checksum and each inner chain link; recomputing the outer checksum alone cannot validate sequence continuity. Use a larger input-byte limit than canonical payload size because pretty-printed JSON expands on disk. State clearly that unsigned files can be rewritten with new checksums.


## Separate provider routing for read-only reviewers (2026-10-05)
Resolve each reviewer connection on the GUI thread before dispatch and freeze both credential bundles for workers. A missing key must stop the entire review before a partial provider request is sent. Reuse existing provider-scoped saved keys; persist only role provider/model choices, and never serialize keys into task reports or audit exports. Exception text from provider libraries may contain a key, so redact every configured key before surfacing a role failure. Distinct connections still do not prove independent reviewer identities or quality.


## Windows frozen-build verification (2026-10-06)

A successful PyInstaller run did not guarantee a runnable executable. The
build environment's PATH exposed Poppler's `icuuc.dll`; PyInstaller copied it
into `_internal`, and `PySide6.QtCore` failed with "The specified procedure
could not be found." Qt6Core imported unversioned ICU symbols, while that DLL
exported versioned symbols. Comparing PE imports with DLL exports isolated the
conflict; removing the foreign ICU pair made the frozen `--check` pass. The
Windows spec now excludes those DLLs. Always test the frozen executable before
deployment, then test the copy under `Program Files` independently.

An active MCP host can restart `ingetrazo-mcp.exe` immediately after it is
stopped. Overwriting its file then fails with a sharing violation. Stage the
new executable beside the old one, rename the old image, and rename the staged
image into place; keep a verified backup and roll back if a later check fails.
The deployment's first failed self-check exercised that rollback successfully.


## Review benchmarks need reproducible inputs and honest missing values

Task IDs and group UIDs are random in normal documents. A benchmark that
builds the same scene twice can therefore send different snapshots to each
provider. Fix those IDs only in the public fixture path and assert the whole
snapshot is identical across runs. The default runner must validate without
making provider calls; live runs require explicit configuration and `--run`.
Save timing and parse metadata, not raw reviewer prose or credentials. A
successful parse is not a finding-quality score, and the current `ai.chat`
return type does not expose token usage: record both as null until separately
measured instead of estimating them from text length.

## Narrow Assistant controls must remain legible

Applying `narrow()` to a whole suggestion container gave it an ignored
horizontal size policy, so its text was clipped to fragments in the AI tray.
Apply shrink rules to the buttons instead and place suggestions in full-width
rows when a large font or narrow tray would clip two columns. Keep Export
review off the assumptions/memory row so those controls remain readable.
A disabled export button also needs visible context:
exporting the latest review requires a completed, current-revision
two-specialist review. The UI can explain this without enabling an invalid
export action.
## Local specialist failures need bounded categories

An `ok` flag alone made a 0/3 local review baseline impossible to diagnose
without exposing provider text. Keep the strict finding schema and scope
checks, but record one fixed failure code per failed specialist. A prompt
reminder about empty snapshots did not stop small local models from inventing
entity IDs; this is evidence to compare model choices and response handling,
not a reason to accept fabricated findings. When benchmarking with uncommitted
instrumentation, note the base commit and the uncommitted diff: a recorded
commit hash alone does not identify the exact code that produced the run.

## Structured generation still needs independent validation

An Ollama JSON-object request returned valid JSON but still failed the review
contract; a snapshot-specific JSON schema completed the three public fixtures
with the same local model pairing. The schema must include the actual allowed
entity IDs and use `maxItems: 0` for an empty snapshot: an empty ID enum was
rejected by the local server. Keep the parser's scope, uniqueness and length
checks even when the provider accepts a schema. Record a prompt fallback
separately so compatibility behavior does not contaminate schema benchmark
results. Passing the response contract says nothing about whether findings
are useful or correct.

## Do not turn absent provider usage into estimated tokens

Ollama's OpenAI-compatible response included `prompt_tokens`,
`completion_tokens` and `total_tokens` in the `usage` object. Capture those
integer fields directly; retain null when a provider omits them or reports
malformed values. A two-specialist total is measured only when both roles
reported totals. Keep each role's response mode and model name with the count,
and do not convert a three-case local run into a savings claim without a
comparable baseline and quality assessment.

## Bind manual judgments to the exact review response

Response validity and provider tokens cannot establish that a specialist's
claims are grounded. For public fixtures, show the snapshot and ordered
findings only through an explicit terminal option; keep the benchmark JSONL
prose-free. A digest of the parsed response plus run/case/role and finding
count lets an offline validator reject a judgment copied to a different
response. Record unassessed outcomes separately, and leave overall quality
null because grounding/relevance labels do not measure omitted findings.
An unsigned digest binds files against accidental mix-ups but does not prove
who reviewed them or prevent deliberate alteration.

## A valid specialist response can still misread a snapshot

The local `pinyo-chat` / `pinyo-coder` pairing produced parseable reviews that
confused an entity name with its tag, invented a child relationship, and
claimed metadata was absent when it was present. Explicitly describe the
meaning of each snapshot field in the role prompt and require the exact field
as evidence. A second public-fixture run completed 3/3 versus 2/3 before that
prompt change, but still had unsupported claims and a blank summary. Reject
whitespace-only summaries in the parser. Measure omissions separately: a
digest-bound reference-fact rubric can count yes/no/unclear human judgments,
whereas finding grounding/relevance alone cannot reveal missed facts. One
nondeterministic pairing and no completed human labels cannot justify a
semantic quality or token-savings claim.

## More explicit prompting is not a grounding gate

Three local model pairings on identical public fixtures showed that structural
completion (2/3 or 3/3) does not rank factual reliability. Codex's
preliminary labels favored some responses from a pairing with lower completion,
but that tiny unblinded sample is not a quality score. A follow-up prompt
spelling out zero counts, empty material, tag locks and empty scopes still
produced reversed hidden/visible claims and an invented empty document name.
Revert an ineffective prompt experiment rather than promoting its 3/3 parse
rate. The next safeguard needs deterministic checks of claims against snapshot
facts and a larger independently judged corpus.

## A broad test gate must report its first real blocker

The Windows `pytest -x -q -m 'not slow' tests` run passed 451 tests before
an unmodified Composer scale-label pixel test failed at `under-right`. It also
failed in isolation with both offscreen and native Qt platform settings.
Neither that test nor its painter implementation changed in this PR stack.
Do not describe the entire stack as fully tested or install a fresh binary
based only on the selected 178 AI tests. First isolate or fix the renderer
regression and complete the broad suite, then verify the frozen bundle.

## Direct paint and Qt submission answer different latency questions

Calling `paintGL` directly isolates renderer cost but omits Qt's event queue
and composition. A native `QOpenGLWidget.frameSwapped` benchmark closes those
two gaps, provided the window is visible: an off-screen-positioned viewport
did not emit that signal on local Windows. Even this boundary is not monitor
scanout or physical pointer latency. Keep command, scheduling, paint and
paint-to-swap components separate; in the 7,633-face Move sample, paint took
about 135 ms of a 158 ms queued-command-to-swap frame. Use the opt-in
`frame.submitted` log for real-pointer sessions before attributing their
latency to the same stage.

## A partial GPU write can still pay for a whole CPU buffer

Compare cached byte parts before joining them. The old VBO helper kept a
large unchanged prefix on the GPU yet copied the entire prefix in Python on
every local edit. Joining only the changed suffix removes that copy and
reduces peak temporary memory. Preserve the full join after a reallocation,
when the GPU has no prefix to keep. An isolated 64 MiB test can show this
cost clearly, but a small real model may spend under 1 ms there; measure the
full viewport separately before claiming a user-visible speedup.

## Share Face planes across adjacent silhouette edges

An edge-indexed NumPy gather can reuse a normal computed once per unique
Face. On the Yanque mesh, 15,312 soft edges reference 7,632 faces; replacing
two edge-sized triangle copies and crosses with one Face-sized cross preserved
all six output arrays and reduced peak traced allocation by about 2.94 MiB.
The CPU median moved only from 55.05 to 54.686 ms in an alternating run, and
four small frame samples varied widely. Treat this as a memory improvement,
and profile the Python edge/Face collection separately before claiming a
frame-rate improvement.

## Tie position-only cache reuse to exact scene transitions

A vertex Move does not always invalidate every derived mesh array. Loose
soft-edge silhouette arrays stay valid when the moved vertices are not soft
edge endpoints and no touched Face supplies a plane to a soft edge. Checking
only edge endpoints is insufficient: another vertex on an adjacent Face can
change its plane. Record an exact old/new scene-version and loose-mesh-serial
pair on the command, and let the renderer reuse only a matching cached mesh
under the standard visibility path. Undo, redo, an intervening edit, custom
visibility, and group editing need separate regression coverage. Measure
both array-build counts and Qt frame submission; an isolated CPU gain does
not by itself establish a display improvement.

## Coalesced edits need a cache lineage across paints

An exact one-step transition works when Qt paints after every Move, but a
drag can issue several safe edits before a frame. Compose only transitions
whose previous end exactly matches the next starting scene version and mesh
serial. When the renderer paints, retain that chain origin with the cached
arrays; otherwise an Undo or later Move after the paint needlessly rebuilds.
Do not carry the origin across a non-Move scene edit, a different mesh or a
custom visibility path. A paired native Qt benchmark should perform several
commands within one queued frame; a one-command-per-paint benchmark cannot
exercise this failure mode.
