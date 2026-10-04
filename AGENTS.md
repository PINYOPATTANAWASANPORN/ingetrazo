# Agent entry point

Before changing this repository, read `docs/agent-handoff/README.md` and
`docs/agent-handoff/state.json`. They describe the stacked development work,
the implemented contracts, validation evidence, and the next safe slices.

Key rules:

- Treat every fork PR listed in `docs/agent-handoff/pr-index.json` as open
  until GitHub proves otherwise. A feature present on the current stacked
  branch is not necessarily present on `main` or in an installed build.
- Preserve the documented PR base chain. Start new work from the latest stack
  head unless the user explicitly chooses another base.
- Keep AI reads bounded and revision-aware. Keep writes typed, scoped,
  previewed, validated, idempotent, and undoable.
- Never turn chat inference into durable project memory. Only an explicit user
  edit may change `scene.ai_memory`.
- Run tests relevant to the changed contract and update the handoff pack when
  status, evidence, architecture, or the next recommended task changes.

