# Development summary

## Delivery topology

The fork uses one long stacked chain. GitHub reported **39 open PRs and zero
merged PRs** on 2026-10-05. PR numbers 18 and 27 are absent from the pull list;
do not invent them. The chain begins at fork `main` (`6be29fe`) and currently
ends at `feature/ai-context-suggestions` (`09bd5ce`). Merging or rebasing a lower PR
changes every PR above it, so preserve order and revalidate the affected stack.
The latest stack layer is
[#37](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/37).

## Product workstreams

| Workstream | Estimated implementation in stack | Delivered slices | Important remaining work |
| --- | ---: | --- | --- |
| Model Outliner | 85% | Full hierarchy, search, select, hide, lock, rename, undoable reorder | Face/edge-level hierarchy and large-tree UX |
| Move Autofold and mesh editing | 90% | Direct vertex edit, autofold preview, inference presentation | Complex-mesh stress cases and user controls |
| Tags/Layers | 95% | Active tag selector, inheritance for new containers, visible hidden/locked state | Final workflow polish and broader tests |
| Selection and Entity Info | 95% | Select by type/material/tag, multi-material edits, multi-transform, Alt-click cycling | Complex nested selection UX |
| Large-model performance | 70% | Shared instance pick geometry, responsive `.igz` open, loose-edge cache | True progressive paint, render chunking, broader benchmarks |
| Extension Manager | 75% | Enable/disable, local install/remove, safe manifests | Online catalog, version resolution, URL updates |
| File exchange | 30% | Windows SKP long-texture-path repair | IFC import, fuller SKP hierarchy fidelity, cross-platform DWG |
| Architectural tools | 10% | Existing BIM/export/composer/terrain foundations | Contours, axes/grid, room labels, doors/windows, schedules |
| AI Agent roadmap | about 72% overall | Bounded context, security gate, typed preview writes and architectural creation, task engine, concise UI, project memory, streaming/cancel, local suggestions, evaluation corpus, two read-only specialists with per-role model selection, external MCP review protocol, session-only Python gate | Existing-wall edits, modeler orchestration, measured provider baselines |

## PR chain by capability

### Foundation and SketchUp-style workflow

- [#1](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/1) — ASCII digits in numeric inputs.
- [#2](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/2) — active layers and direct vertex editing.
- [#3](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/3) — full model Outliner.
- [#4](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/4) — Move Autofold preview.
- [#5](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/5) — circle/polygon segment rebuild.
- [#6](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/6) — Windows-safe AI photo filenames.
- [#7](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/7) — Windows base-map network crash guard.
- [#8](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/8) — undoable Outliner reorder.

### Selection, Entity Info, tags, and performance

- [#9](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/9) — selection filters.
- [#10](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/10) — multi-entity material editing.
- [#11](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/11) — multi-object position and size.
- [#12](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/12) — shared component pick geometry.
- [#13](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/13) — always-visible Active Tag selector.
- [#14](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/14) — distinct Autofold inference preview.
- [#15](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/15) — responsive native-document opening.
- [#20](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/20) — loose-edge selection cache.
- [#21](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/21) — Active Tag inheritance for containers.
- [#22](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/22) — long Windows SKP texture paths.
- [#23](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/23) — consistent tag state labels.
- [#24](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/24) — Alt-click overlapping-selection cycling.

### Extension Manager

- [#16](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/16) — safe enable/disable UI.
- [#17](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/17) — local installation/removal.
- [#19](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/19) — safe manifest metadata.

### AI context, typed writes, and concise workflow

- [#25](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/25) — bounded context APIs.
- [#26](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/26) — bridge credentials and permissions.
- [#28](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/28) — preview-first property actions.
- [#29](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/29) — material and bounded transform actions.
- [#30](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/30) — scoped task engine.
- [#31](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/31) — compact intent controls.
- [#32](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/32) — explicit project AI memory.
- [#33](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/33) — durable AI development handoff pack.
- [#34](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/34) — typed previews in the in-app Assistant.
- [#35](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/35) — typed box/cylinder creation and session-only advanced Python permission.
- [#36](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/36) — streamed provider responses and cooperative cancellation.
- [#37](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/37) — local context suggestions and a versioned AI evaluation corpus.

- [#38](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/38) — walls with openings, slabs, component copies and scoped parent coordinates.

- [#39](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/39) — two read-only provider specialists, conflict reporting and cancellation.

- [#40](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/40) — external MCP review assignments, validated submissions, bounded retention and cancellation.

- [#41](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/41) — per-role model selection, provider-scoped settings and requested-model reporting.

## Claims that must stay qualified

All items above are implemented **in the open stack**. They are not on the
fork's `main`, not upstream, and not necessarily in the installed IngeTrazo
binary. The latest selected regression run covered 107 tests; it was not the
repository's complete test suite.


Architectural creation now includes walls with door/window openings, rectangular
slabs, component copies, and scoped parent-coordinate primitives. See
[`ai-creation-contract.md`](../ai-creation-contract.md) for supported cases and limits.


## Latest increment: AI review export
Branch `feature/ai-review-export`, based on `feature/specialist-model-selection`. Adds revision-checked JSON export in Assistant and MCP, atomic local saving and unsigned integrity digest. Settings/tokens excluded; prose may contain sensitive project content. No installed build update. See `docs/ai-specialist-review.md`.
