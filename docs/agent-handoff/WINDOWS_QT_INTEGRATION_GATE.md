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
- The remaining files 0–299 were then run in 30 separate 10-file processes:
  **3,518 passed, 6 skipped, 1 expected failure, 0 failed**. Across all
  421 files and 43 successful shards the final tally is **4,594 passed,
  11 skipped, 1 expected failure, 0 failed**. The selected results and
  per-shard log paths are recorded in the local `summary.json` in that same
  directory. It retains the original failing Style Editor log and uses the
  successful `shard-360-recheck.txt` after the test-only correction.

Before the Qt-lifetime follow-up, the **full single-process suite did not
complete**. The offscreen run first
failed a Composer scale-label pixel test after 451 passed and 11 skipped;
that test passes with native Windows Qt. Native runs exposed the test focus
and font-metric assumptions above. A later continuation reached about 64%
before Python consumed approximately 20 GB of memory and was stopped. A
separate large batch was stopped at 4.6 GB near 9%. Cumulative GUI/OpenGL
test memory remains an integration risk. None of these partial runs should
be reported as a single-process full-suite pass. The complete file-level
sharded run above validates the tests in isolated processes, but does not
exercise cross-file state and resource accumulation in one process.

## Follow-up: Qt object lifetime in a single Windows process

The full-suite memory failure was investigated on `fix/qt-test-lifecycle`
([draft PR #54](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/54),
stacked on PR #53).
The native Windows test process created about 41,862 Qt widgets after 90
tests, including 2,302 top-level widgets; one Assistant-heavy module
accounted for most of them. A 40-file probe exceeded 2.5 GB private memory
without cleanup. Releasing top-level test windows at module boundaries let
the same probe finish 335 tests at 1.34 GB peak. The cleanup runs after
pytest tears down module fixtures, drains queued layout callbacks while the
windows are valid, then processes deferred Qt deletion.

Delayed UI callbacks in MainWindow, Composer, and the tray are now scheduled
with their owning QObject as context. Qt can discard them when the owner is
destroyed. Before the Composer callback fix, a complete 72-file prefix
repeatedly ended with Windows access violation `0xC0000005` around its
Composer Items tests; each half passed separately. After the fix, that
72-file prefix passed **623 tests in one process**, exit code 0, with 1.97 GB
peak private memory and no fatal/runtime callback diagnostics. The broader
160-file prefix then passed **1,378 tests, 2 skipped**, exit code 0, with
2.006 GB peak private memory and no fatal/runtime callback diagnostics. Six
related GUI test files also passed 28 tests after the MainWindow/tray changes.

The final **421-file single-process native-Windows run passed**: 4,594 passed,
11 skipped, 1 expected failure, 0 failed; exit code 0 in 21 minutes 38
seconds. Peak private memory was **2.55 GB** under a 4 GB watchdog limit, and
stderr contained no fatal/runtime callback diagnostics. The same tests had
previously required 43 isolated processes, while an earlier single-process
run reached about 20 GB and was stopped at 64%. This closes the local
single-process memory gate; it does not certify the staged binary or replace
CI and live-GUI verification. The full-run log and memory trace are outside
the repository at
`C:\Users\Lenovo\Desktop\IngeTrazoTest\memory-fix-full-final-pytest.txt`
and `C:\Users\Lenovo\Desktop\IngeTrazoTest\memory-fix-full-final.csv`.

The staged bundle is in the ignored `dist/ingetrazo` directory. SHA-256:

- `ingetrazo.exe`: `D4EF7D5C86AAE55F8AB4F0EE07EC5F0852BF5D4A2AEE16B53F0972823549744B`
- `ingetrazo-mcp.exe`: `85A42FE3F0B106227A9E3B32F93D4A6C51FBC4D0A8ED724D8907412048C46DF5`

The installation at `C:\Program Files\IngeTrazo` remains the older verified
build from `3815ef8`. The staged bundle has **not** been installed. Before
installation or a merge of the stacked PRs, complete a memory-bounded broad
test run in CI, then verify the frozen GUI and representative live workflows. AI
specialist factual quality also requires independent human evaluation and
deterministic checking of claims against the model snapshot.

The Style Editor change above is test-only and followed the staged build;
no application binary changed after `d70e782`.

## Follow-up: Windows PR check and frozen smoke

The fork's GitHub Actions page reported that workflows are **disabled** for
forked repositories. PR #54 therefore showed no check runs. A new `windows-qt`
job in `.github/workflows/ci.yml` runs the entire suite on `windows-latest`
with native Windows Qt and a 60-minute timeout. The existing Ubuntu fast job
remains. The native backend was chosen because the exact 421-file sequence
passed locally in one Windows process (4,594 passed, 11 skipped, 1 xfailed).
Merely adding the job does not enable fork Actions; a repository maintainer
must explicitly enable workflows after reviewing all existing workflows,
including release workflows with write permissions and secrets.

An exploratory full offscreen run stopped making progress at
`test_document_caches_reset.py` after about 22% of the suite. The test passed
in 1.85 seconds alone and in an offscreen 46-test focused run. This is an
unresolved cross-file/offscreen interaction, not a full-suite pass. The
offscreen run also exposed repeated Composer radial-property callbacks to a
nonexistent `_single_selected` method. The handler now uses `_selected_item`
after the `_updating` guard; a regression test edits a selected radial
dimension and undoes the edit. Composer/radial tests passed 45/45 on native
Windows Qt and 46/46 offscreen (the latter also included the document-cache
test). A tiny scale-label pixel assertion is conditional on a platform that
rasterizes that glyph: local Windows offscreen produced no ink in the sampled
region, while native Qt did. Semantic placement and save/load assertions
still run in both backends.

A clean frozen bundle from current code commit `12d783c` was staged outside
the repo at `C:\Users\Lenovo\Desktop\IngeTrazoTest\dist-qt-12d783c\ingetrazo`.
`ingetrazo.exe --check` exited 0, the frozen MCP server listed 22 tools, and
an offscreen `--new-window` GUI process survived a ten-second startup smoke.
This was a **startup** check, not a live GUI interaction. The build includes
the radial-property fix and has not been installed. SHA-256:

- `ingetrazo.exe`: `D6B241FD58D82476BF6843FD538D78EE4EFF6DEB0DB2219D9CFBBFCFD2D7FE45`
- `ingetrazo-mcp.exe`: `67FCDFD3465314623EF22D60AD37B1730641197B4D1A7A2CA4731FA45B8702EA`

The installed `C:\Program Files\IngeTrazo` files remain from `3815ef8`.
