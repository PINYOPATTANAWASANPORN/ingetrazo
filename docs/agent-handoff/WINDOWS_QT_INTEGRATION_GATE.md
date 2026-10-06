# Windows Qt integration gate — 2026-10-06

This is a follow-up to the local AI review study in
`benchmarks/ai/review-local-study-2026-10-06.md`. It records the Windows test
and packaging evidence for branch `test/windows-qt-integration-gates` at
`d70e782`. It is not a release approval.

## Changes

- Outliner checkbox/text changes now schedule the tree rebuild for the next
  event-loop turn. A synchronous `QTreeWidget.clear()` from `itemChanged`
  deleted the item still being processed by Qt and reproducibly caused a
  native access violation at `tests/test_outliner.py:93` on Windows. The
  regression test processes events and checks the rebuilt lock row.
- The command-search test explicitly activates its window before opening a
  menu. The full-suite failure was caused by focus left on another popup;
  the isolated test passed.
- Two Composer layout tests use semantic font relationships or a small ink
  margin tolerance instead of platform-specific font-pixel thresholds.
- The Style Editor tooltip test now checks the scoped button stylesheet
  directly. Native Windows Qt did not create a visible tooltip window inside
  the test harness, even after its parent widget was shown. The scoped
  selector is the regression contract that prevents the swatch background
  from cascading to a tooltip.

## Validation actually completed

- `tests/test_outliner.py`: 7 passed on native Windows and offscreen Qt.
- Five related model test files: 37 passed.
- Selected AI suite: 178 passed with `PYTHONUTF8=1`.
- `tests/test_command_search.py`: 49 passed.
- `tests/test_composer_cajetin_rows.py`: 8 passed.
- Composer label-margin targeted test: passed.
- Later isolated `tests/test_pushpull_ux.py`: 41 passed; a following 40-test
  segment covering Python console, theme, translator, inferences, palette,
  rebuild, recent files and rectangle tools passed.
- A clean PyInstaller build from `d70e782` passed; the frozen executable's
  `--check` returned 0, and the frozen MCP executable's JSON-RPC `tools/list`
  returned 22 tools including `begin_specialist_review`.
- Files 300–420 of the 421 sorted `test_*.py` files were run in separate
  10-file native-Windows processes: **1,076 passed, 5 skipped**. The
  Style Editor test first failed in the 360–369 shard (109 passed, 1 failed),
  then its corrected 16-test file and the full 360–369 shard passed
  (110 passed). These counts use the successful rerun, not the failed run.
  Logs for shards 340–420 are outside the repo in
  `C:\Users\Lenovo\Desktop\IngeTrazoTest\test-shards-20261006`.

The **full single-process suite did not complete**. The offscreen run first
failed a Composer scale-label pixel test after 451 passed and 11 skipped;
that test passes with native Windows Qt. Native runs exposed the test focus
and font-metric assumptions above. A later continuation reached about 64%
before Python consumed approximately 20 GB of memory and was stopped. A
separate large batch was stopped at 4.6 GB near 9%. Cumulative GUI/OpenGL
test memory remains an integration risk. None of these partial runs should
be reported as a full-suite pass.

The staged bundle is in the ignored `dist/ingetrazo` directory. SHA-256:

- `ingetrazo.exe`: `D4EF7D5C86AAE55F8AB4F0EE07EC5F0852BF5D4A2AEE16B53F0972823549744B`
- `ingetrazo-mcp.exe`: `85A42FE3F0B106227A9E3B32F93D4A6C51FBC4D0A8ED724D8907412048C46DF5`

The installation at `C:\Program Files\IngeTrazo` remains the older verified
build from `3815ef8`. The staged bundle has **not** been installed. Before
installation or a merge of the stacked PRs, complete a memory-bounded broad
test run, then verify the frozen GUI and representative live workflows. AI
specialist factual quality also requires independent human evaluation and
deterministic checking of claims against the model snapshot.

The Style Editor change above is test-only and followed the staged build;
no application binary changed after `d70e782`.
