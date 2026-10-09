# Remaining development and release plan

Snapshot: 2026-10-09. This plan follows draft PR #88 on the fork's stacked
branch. GitHub showed 86 open PRs and zero merged PRs. The last verified
installed Windows build was made from `3815ef8`, not the current stack.
Percentages in `DEVELOPMENT_SUMMARY.md` estimate implementation in the stack;
they are neither test coverage nor release readiness. Recheck GitHub and the
installed binary before acting on this snapshot.

## Decision: what the first usable fork version contains

Ship a **limited preview** of the integrated, tested modelling and Assistant
features before attempting every item in the long-term roadmap. It may say
that IFC import, cross-platform DWG import, an online extension catalog, and
the complete architectural toolset are experimental or unavailable. Never
present those items as complete merely because an adjacent feature exists.
The preview still needs correct attribution, notices and naming review; a
source-branch or successful test run alone is not a release.

The preview can proceed only after Gate 0 and the high-risk checks in Gate 1
and Gate 2 below. Broader beta follows the AI reliability and interchange
gates. A full feature target follows the remaining architecture and extension
work. The gates describe evidence, not dates or promises.

## Gate 0 — integrate and prove the current stack (highest priority)

1. Record the exact PR dependency graph and final head SHA. Audit every open
   PR for an obsolete base, conflicts, duplicate scope and unreviewed code.
   Merge in dependency order in small batches; after each batch, rebase the
   remaining stack and verify the diff against the previous head. Keep a
   recoverable tag and build manifest for every integration checkpoint.
2. Run the complete native Windows suite in one process and the Ubuntu
   non-slow suite on the same final head. Keep the Windows offscreen smoke
   gate as an early signal, not a substitute for native testing. The #76/#78
   Ubuntu stalls led to a diagnosed IGZ worker deadlock fixed in #82. Confirm
   #87 final-head CI and investigate any new timeout before promotion.
3. Build the frozen Windows application and MCP bridge from that SHA. Check
   executable hashes, `--check`, MCP `tools/list`, GUI startup, document
   open/save/reopen, Undo/Redo, Outliner, Move/Autofold, Tags, AI read-only
   review and typed preview/commit on representative files. Record failures
   and a rollback to the currently installed build. Do not silently overwrite
   the user's live document during installation.
4. Review bundled license notices, branding and version identifiers before
   a fork-branded package is distributed. Keep upstream copyright and
   third-party notices required by their licenses.

**Done when:** the intended release SHA is reproducible, both platform gates
pass at that SHA, the frozen app passes the listed workflows, the integration
branch has no unexplained delta from the reviewed PRs, and rollback is tested.
Only then promote a built artifact to the installed preview.

## Gate 1 — finish the core modelling workflows

| Stream | Next bounded slices | Acceptance evidence |
| --- | --- | --- |
| Outliner (85%) | Face/Edge representation scoped to the active edit context; bulk hide/lock/tag/rename where meaningful; virtualized or incremental large-tree filtering | Nested groups and components retain correct selection/visibility on Undo/Redo; representative large model has measured search and scroll latency, not only synthetic rows |
| Move/Autofold (90%) | Degenerate and non-manifold stress corpus; explicit Autofold control and preview; verify vertex/edge drag in real projects | No corrupted topology or lost undo identity across holes, shared vertices and snapped endpoints; preview equals commit result |
| Tags/Layers (95%) | Audit inherited tags and hidden/locked states through create, group edit, copy, import and Undo/Redo | One end-to-end workflow matrix passes, including active-tag changes and hidden/locked ancestors |
| Selection/Entity Info (95%) | Nested hit cycling and inspector for the selected path; bulk edits with clear mixed-value feedback | Users can choose a nested target predictably; multi-object edit has one undo step and never edits a locked/hidden ancestor unexpectedly |

Each slice should have one focused PR and regression evidence. Run a small
human usability check with actual nested models before declaring any stream
complete; implementation presence is insufficient.

## Gate 2 — representative large-model performance

Create a versioned corpus of at least a small, medium and large real model,
including many instances, loose soft edges, textures and nested groups.
Capture hardware, viewport, model statistics and the same interactions on
the parent and candidate commits. Measure cold-open time-to-first-paint and
time-to-interactive, p50/p95 paint and queued Move-to-`frameSwapped`, memory
peak, selection/hover latency and save/reopen correctness. Add physical
pointer-to-visible-pixel observation separately; Qt `frameSwapped` is not
monitor scanout.

Prioritize progressive viewport paint after load, chunked edge/face work and
cache invalidation on edits. Profile before adding native code or new render
architecture. Keep PR #71–#78 microbenchmarks as diagnostic evidence, but
do not extrapolate one Yanque model to all projects.

**Done when:** every corpus model opens and remains interactive without a
regression against the recorded parent baseline, p95 stalls are attributed
and reduced on the identified worst case, and representative visual output
and picking remain correct. Set numeric release budgets from the captured
baseline rather than inventing them in advance.

## Gate 3 — reliable, concise AI Assistant and MCP work

1. Add deterministic checks that specialist findings cite fields actually
   present in the detached snapshot. Reject or mark unsupported assertions
   before showing them as model facts. Keep review agents read-only.
2. Expand the public review corpus and obtain independent human labels for
   relevance, unsupported claims and reference-fact coverage. Report task
   completion, quality, latency and provider-reported token usage separately
   for named provider/model combinations.
3. Continue short-intent UI and typed modelling actions only through scoped,
   revision-checked preview/commit with one undoable result. Exercise stale
   revision, cancellation, permission denial and conflicting-agent cases.
4. Introduce multi-agent write coordination only after a write lease, typed
   action boundary, per-role identity and audit behavior are tested. The
   in-process Python escape hatch stays explicit and session-scoped.

**Done when:** a user can make a short request, inspect context and proposed
changes, commit or reject safely, and tell what each specialist actually
verified. The evaluation report must show measured reliability, not merely
valid JSON or a successful provider connection.

## Gate 4 — file interchange and extensions

Treat each format as an adapter with a public fixture corpus and a declared
fidelity matrix: geometry, units, groups/components, materials, tags and
metadata. First preserve more of the existing SKP hierarchy and material
structure, then deliver IFC import with a documented supported subset, then
resolve DWG import packaging and behavior on Windows, macOS and Linux.
Compare source and imported model counts/structure and inspect representative
rendered output. A file that opens is not sufficient evidence of fidelity.

For extensions, first define catalog metadata, compatibility and dependency
rules. Then implement a curated online catalog and URL update path with
integrity verification, clear source/version display and explicit install
choice. Test a malicious or malformed manifest, incompatible version,
interrupted update and rollback. Do not execute downloaded code merely to
inspect its metadata.

**Done when:** supported format subsets and loss cases are visible to users,
fixture round trips meet their declared tolerances on supported platforms,
and extension install/update/remove can be recovered safely.

## Gate 5 — architectural toolset

Build on the existing BIM, IFC export, Composer and Terrain foundations in
small vertical slices: (1) contour and reference grid/axes, (2) room labels
and areas, (3) parametric doors/windows and openings in existing walls,
(4) schedules and numbered sheet legends. Define units, object identity,
rebuild behavior and IFC/export mapping before writing the UI for each slice.

**Done when:** a saved example project can create, edit, undo, reopen and
export each object without losing its parameters or sheet references, and
quantities/schedules agree with the model after edits.

## Immediate next work order

1. PR #87 final-head CI and PR #88 cumulative-head CI passed both Ubuntu and
   Windows offscreen jobs; the complete native Windows suite on the #87
   application/test code passed 4,633 tests. Keep both runs and the local log
   in the integration checkpoint.
2. The staged #87 bundle passed notices, hashes, `--check`, MCP `tools/list`
   and an offscreen sample-file open. Review it, then exercise frozen GUI
   save/reopen and editing workflows on representative project copies. A
   native staged app opened a copied sofa document, but interactive actions
   could not be driven in this session. Complete the Qt notice and
   fork-branding review documented in the frozen-package audit. Test the
   real update path and rollback only after those checks. The successor
   `fix/windows-exe-version-info` candidate now has checked PE version
   resources for both Windows executables; publisher/name policy and Qt
   notices remain open. The installed application remains at `3815ef8`.
3. Establish the real-model performance corpus and capture baseline numbers;
   use it to choose the next renderer or progressive-paint slice.
4. In parallel with performance measurement, start one bounded Outliner
   Face/Edge or nested-selection slice with a real-model UX check.
5. Start the deterministic AI finding-grounding gate and human evaluation
   corpus before expanding autonomous writes.

Update this plan when a gate closes. Link its PR, final-head CI, model corpus
and installed-build evidence; do not raise a percentage just because code was
written or a draft PR opened.
