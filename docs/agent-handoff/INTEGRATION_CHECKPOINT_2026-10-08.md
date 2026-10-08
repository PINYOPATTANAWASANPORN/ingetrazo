# Integration checkpoint — 2026-10-08

This is evidence for Gate 0 of `REMAINING_DEVELOPMENT_PLAN.md`, not release
approval. The tested head and installed application are different: the last
verified installed Windows build is from `3815ef8`; this checkpoint remains
on open draft branches.

## Stack topology

The fork had 80 open PRs and zero merged PRs after opening
[#82](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/82).
PRs #18 and #27 do not exist. After fetching all fork branches, the local
`pr-index.json` audit found **zero** sequence mismatches, **zero** cases where
the base ref was not an ancestor of the head ref, and **zero** empty diffs.
This proves the branch chain is mechanically coherent; it does not review
every change for correctness, duplicate scope, or release suitability.

## Hosted CI and stalled historical runs

- The final head of [#79](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/79)
  (`1a304084`) passed Ubuntu `pytest (not slow)` and Windows Qt offscreen
  smoke in [run 37724304752](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37724304752).
- The CI timeout/traceback change on
  [#80](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/80)
  (`dd1785f4`) passed both jobs in
  [run 37727270338](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37727270338).
  New Ubuntu runs stop after 30 minutes and request thread traces after an
  individual test takes 180 seconds.
- The #82 cumulative head `31ae5b7c` passed Ubuntu `pytest (not slow)` and
  Windows Qt offscreen smoke in
  [run 37728913441](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37728913441).
  Ubuntu passed the former 26% stall point and completed in about ten minutes.
- Earlier Ubuntu jobs on [#76](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/76)
  ([run 37715521408](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37715521408))
  and [#78](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/78)
  ([run 37722385356](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37722385356))
  each stopped printing progress at 26% while their Windows smoke jobs passed.
  They stayed in the Tests step for more than an hour and were canceled after
  the later stack head passed. Their logs have no Python stack trace, so the
  precise hanging test was not visible in those older logs. The later #81
  diagnostic run stalled at the same 26% point and emitted a Python stack at
  `views/main_window.py:4584`, inside `_load_igz_threaded` while reopening a
  document in `test_document_caches_reset.py`. That run was canceled after
  the traceback was captured.

## Native Windows regression found during the gate

An initial full local run with no `QT_QPA_PLATFORM` override used Qt offscreen
because `tests/conftest.py` sets that default. It failed a known
font/pixel-sensitive Composer label assertion at 12%. It is **not** a native
Windows result. An explicit `QT_QPA_PLATFORM=windows` made that isolated label
test pass.

The explicit native-Windows full run then exited with access violation
`0xC0000005` near 13%. A logged rerun located the deterministic crash in
`tests/test_composer_items_panel.py::test_an_item_renamed_in_the_list_keeps_its_name_and_undoes`:
the queued rename callback cleared a live `QTreeWidget`. The
[#81](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/81) fix updates
only the resolved row label with signals blocked. The existing Composer Items
file now passes **7 native Windows tests**; Composer Items plus Outliner pass
**18 offscreen tests**. These focused results do not yet close the full native
suite gate.

## IGZ worker shutdown follow-up

The #81 Ubuntu traceback showed that the UI thread was blocked in
`thread.wait()` after a nested event loop exited. `worker.finished` had
queued `thread.quit()` onto the UI-owned `QThread`, but the UI could not
deliver that queued slot while it was waiting. On
[#82](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/82),
`_load_igz_threaded` requests `thread.quit()` synchronously after the nested
loop returns and before the join. Focused document-cache/camera tests passed
offscreen (7) and with native Windows Qt alongside Composer Items (14). Full
Hosted CI passed on the cumulative `31ae5b7c` head. The complete local
one-process native Windows suite (`QT_QPA_PLATFORM=windows`, `pytest -q tests
--disable-warnings`) also completed with exit 0: **4,633 passed, 11 skipped,
1 xfailed, 238 warnings** in 1,317.53 seconds (21m57s). Its log is outside
the repository at `C:\Users\Lenovo\Desktop\IngeTrazoTest\native-pr82-full.txt`.
The sampled process private memory near the end was 2.67 GiB; this is not a
measured peak. This native run began before the documentation-only `31ae5b7c`
commit, with the same application and test code (`cfaacc8`).

## Staged Windows bundle

The cumulative `31ae5b7c` head was built with the Windows PyInstaller spec
into `C:\Users\Lenovo\Desktop\IngeTrazoTest\dist-pr82\ingetrazo`. The frozen
`ingetrazo.exe --check` exited 0, the frozen MCP server returned 22 tools,
and an offscreen GUI process stayed alive for ten seconds. The bundle has
825 files. SHA-256: main
`7971B36538E552F96CD60AFA4EDF886159F783EA7D42236D76C17CD0DFD29B53`,
MCP `B0F7B61C1CE48E0300747530B2D18DEDEE0C585F807889C5452CEF2426E81EA4`.
The complete manifest is outside the repository at
`C:\Users\Lenovo\Desktop\IngeTrazoTest\build-staged-pr82.json`. The bundle
has **not** been installed or visually exercised with a real document.

## Remaining release evidence

The automated suite, hosted CI, frozen self-check, MCP tool listing and
offscreen startup are verified for the current code. Gate 0 still needs
representative frozen GUI document workflows (open/save/reopen, Undo/Redo,
Outliner, Move/Autofold, Tags, AI read-only review and typed preview/commit),
review of the PR code and license/branding notices, and a tested rollback
before promoting this bundle to the installed preview. Preserve the older
installed build and its rollback until those checks are complete.

## Follow-up: final #82 bundle and packaged license

The final #82 head `4c34cbbf` passed hosted Ubuntu and Windows smoke in
[run 37730658123](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37730658123).
An exact-head staged bundle is recorded outside the repository in
`C:\Users\Lenovo\Desktop\IngeTrazoTest\build-staged-pr82-final.json`.
It passed `--check`, returned 22 MCP tools and opened a copied starter
`sofa.igz` as a native GUI window titled `IngeTrazo — sofa-copy.igz`.
Process path and command line confirmed the staged executable; the installed
build was not changed. The complete observation and limitation record is at
`C:\Users\Lenovo\Desktop\IngeTrazoTest\smoke-pr82\FROZEN_GUI_SMOKE.md`.
Open/save/reopen and editing workflows remain unverified in the frozen GUI
because native capture timed out on its OpenGL window and file-dialog fields
could not be targeted reliably. The live sample copy was not changed.

A packaging audit found that the #82 frozen bundle omitted the repository's
`LICENSE`. The follow-up [draft PR #83](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/83)
(`fix/frozen-license-notice`), based on #82,
adds it to PyInstaller data and checks its presence and byte equality in the
Windows build workflow. Local build from code commit `19b62c47` placed it at
`_internal/LICENSE`; its SHA-256 matched the repository source
(`3972DC9744F6499F0F9B2DBF76696F2AE7AD8AF9B23DDE66D6AF86C9DFB36986`),
and frozen `ingetrazo.exe --check` exited 0. The Windows portable LEEME now
uses the repository's `GPL-3.0-or-later` designation and names that path.
This verifies only the project's license text, not the completeness of all
third-party notices or fork branding. Do not treat it as distribution approval.
