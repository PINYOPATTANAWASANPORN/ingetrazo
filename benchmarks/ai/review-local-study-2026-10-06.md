# Local specialist review study, 2026-10-06

This is a small developer-side diagnostic, not a release quality score. All
three runs used the same three public metadata fixtures in
`review-corpus-v1.json`, Ollama schema mode, and the Windows host's local
models. Each case sent one request to each read-only specialist. No private
document was sent. Results and bounded public-fixture displays are stored in
the workspace root outside Git; benchmark JSONL contains no provider prose.

| Clean code commit | Structure / requirements models | Completed cases | Failure | Median reported total tokens per case |
| --- | --- | ---: | --- | ---: |
| `c25c69b` | `pinyo-chat:latest` / `pinyo-coder:latest` | 3/3 | none | 1,204 |
| `c25c69b` | `llama3.2:latest` / `qwen2.5-coder:1.5b` | 2/3 | duplicate finding | 1,251 among cases with both totals |
| `c25c69b` | `llama3.2:latest` / `llama3.2:latest` | 2/3 | duplicate finding | 1,177 among cases with both totals |
| `7d3984f` | `pinyo-chat:latest` / `pinyo-coder:latest` | 3/3 | none | 1,443 |

The last commit tried more explicit instructions about zero counts, empty
material, tag locks, empty scopes and complete evidence. It did not prevent
wrong factual statements and was reverted. The measured token totals are
provider-reported, not estimated; three cases do not establish a cost or speed
ranking. The runs were sequential but local runtime load and generation vary.

The digest-bound rubric in `review-coverage-v1.json` was applied by Codex as a
**preliminary agent inspection**, not by an independent human assessor. On the
first pairing, four of ten reference-fact judgments were `yes` and six were
`no`; four of six summaries were judged unsupported. The second pairing had
five `yes` and three `no` coverage judgments across its five successful role
outcomes, with all five summaries judged grounded. These are subjective,
unblinded labels on a tiny corpus, not a general quality metric. The third and
fourth runs were inspected for obvious errors but not fully labeled.

Observed errors include claiming a material exists when the snapshot's
`material` is empty, describing a locked tag as an entity lock, assigning
`hidden=true` to the wrong entity, inventing a document name for an empty
scope, and using a `material` topic for tag status. A successful parse and a
`completed` review status therefore demonstrate contract validity only.
Prompt wording alone did not remove these errors. The next implementation
should validate structured evidence against the snapshot and expose
unsupported claims as unverified or rejected, with separate tests for
grounding and response completion.

## Integration gate at the same snapshot

The fork had 50 open PRs, zero merged PRs, and seven drafts. Their bases formed
one continuous chain ending at PR #52. GitHub reported PR #52 mergeable with a
clean merge state, but its head had zero reported check runs. Relative to fork
`main`, the stack contained 83 commits and roughly 15,000 inserted lines.
These facts support staged review and a broad test pass before merging or
installing a new build. The installed Windows executables still matched the
documented `3815ef8` manifest; this study did not update them.

The broad local `pytest -x -q -m 'not slow' tests --tb=short` gate stopped at
`tests/test_composer_borders.py::test_frame_scale_label_follows_the_scale_and_its_position`:
451 passed, 11 skipped, one failed, and 805 deselected before the stop. The
isolated test also failed on this Windows host at the `under-right` pixel probe.
Neither the test nor `views/composer.py` differs from fork `main` in this
stack, so this is not evidence that the new AI review code caused it. The
whole suite remains **unverified**, and no frozen build was staged from this
head. The selected AI suite passed 178 tests before this study; its own code
is unchanged by the report.

The local result and agent-label filenames are `review-pinyo-current-20261006`,
`review-baseline-current-20261006`, `review-llama-both-20261006`, and
`review-pinyo-grounded-20261006` in the workspace root. Keep displays and
agent labels separate from the privacy-safe repository corpus. A later
independent human assessment may disagree with these preliminary labels.
