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

## Follow-up: bundled asset provenance

The same package audit found that `resources/colors/SOURCES.md` and
`resources/textures/SOURCES.md` were absent from the frozen bundle even though
their corresponding colour catalogue and texture library were present.
`resources/components/SOURCES.md` was already included. Stacked
[draft PR #84](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/84)
(`fix/bundled-asset-attributions`, based on #83) adds the first two files to the
PyInstaller spec, checks exact byte equality for all three in the Windows
build workflow, and lists their locations in the portable LEEME.

The local Windows bundle built from application/package code `8882e68d`
contains all three files with SHA-256 matching the repository originals;
`ingetrazo.exe --check` exited 0. The full hash manifest is outside the
repository at `C:\Users\Lenovo\Desktop\IngeTrazoTest\build-asset-gate.json`.
This closes the observed asset-provenance packaging omission only. Dependency
license texts, branding/version review, frozen editing workflows, and tested
rollback are still open Gate 0 work. The installed build remains unchanged.

## Follow-up: wheel notice files and OpenSKP

The final heads of [#83](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/83)
and [#84](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/84)
passed both hosted Ubuntu and Windows Qt offscreen jobs in
[runs 37786204798](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37786204798)
and [37786871404](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37786871404),
respectively. Those runs do not execute the Windows release-packaging workflow.

Stacked [draft PR #85](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/85)
(`fix/frozen-dependency-license-files`, based on #84) collects
`METADATA` and wheel-provided `licenses/` files for selected bundled runtime
distributions. The OpenSKP wheel has no license file in its `.dist-info`;
the branch includes the MIT license from the exact OpenSKP source revision
pinned in `requirements.txt`, with its source URL recorded in
`vendor/openskp/SOURCES.md`. A build verifier compares the frozen files byte
for byte with the build environment and repository sources.

The local Windows bundle built from package code `7f586984` passed that
verifier (**43 wheel metadata/license files**) and `ingetrazo.exe --check`
(exit 0). The exact file hashes and count are recorded outside the repository
at `C:\Users\Lenovo\Desktop\IngeTrazoTest\build-dependency-notices-final.json`.
This is a notice-file packaging result, not a full redistribution review:
the PySide6 wheel metadata in this build contains only a commercial-license
reference file, and Qt/framework notices still need a separate audit. Frozen
GUI editing and rollback remain unverified; the installed build was not changed.

## Follow-up: disposable Windows bundle rollback rehearsal

The final #85 head `159d499f` passed hosted Ubuntu and Windows Qt offscreen
jobs in [run 37788462080](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37788462080).
Stacked [draft PR #86](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/86)
adds `packaging/rehearse_windows_rollback.ps1`. The script exercises the bundle
replacement sequence in a new directory inside a nominated workspace. It
hashes every installed and staged source file, copies the installed bundle
into active and backup fixtures, activates staged `_internal` and the two
executables, runs the activated `ingetrazo.exe --check`, then injects a
failure and restores the old files. It compares SHA-256 manifests for the
restored fixture, backup, and unchanged original sources. All moves are
restricted to the workspace fixture; the source bundles are read-only.

On 2026-10-08, the rehearsal used the installed `3815ef8c` bundle (832
files) and staged dependency-notice `7f586984` bundle (874 files). The
activated self-check exited 0; the injected failure was observed; the full
restored manifest matched both the installed source and backup; both source
manifests were unchanged. The JSON report and retained fixtures are at
`C:\Users\Lenovo\Desktop\IngeTrazoTest\rollback-rehearsal-hardened-2026-10-08`.
Out-of-workspace and nested evidence paths were rejected before any copy or
move. The script rejects reparse points in either source bundle and requires
the evidence directory to be a new direct child of a real workspace directory.

This is a **filesystem transaction rehearsal**, not a test of the legacy
hardcoded elevated installer or Inno Setup uninstall/rollback. The actual
Program Files bundle was not upgraded. Gate 0 still needs a review of the
real installer/update and rollback path, frozen GUI document editing, and
remaining Qt/framework notices and branding/version decisions.

## Follow-up: reusable preview update transaction

`packaging/update_windows_preview.ps1` replaces the earlier hardcoded,
machine-specific Program Files update script with a parameterized transaction.
It checks both build manifests and hashes, refuses reparse points and running
target processes, takes a complete backup snapshot, stages the new runtime
and executables, updates `BUILD-INFO.json`, runs frozen `--check`, and restores
the old target on failure. `packaging/WINDOWS_PREVIEW_UPDATE.md` describes
the fixture and production gates.

The exact installed `3815ef8c` bundle was copied into a workspace fixture
and updated with the staged `7f586984` bundle. Injected failures after
`_internal`, app exe, MCP exe, metadata, and successful self-check each
returned `rolled_back` with a complete manifest match to the old snapshot.
The no-failure run returned `updated` and self-check exit 0. A second run
returned `already_current` without creating a backup. Calling the updater
against Program Files without `-AllowProgramFiles` was rejected before any
write. Reports and retained fixture are under
`C:\Users\Lenovo\Desktop\IngeTrazoTest\updater-fixture-2026-10-08`.

The updater has **not** been run on Program Files. This validates the shared
filesystem transaction in a fixture, not administrator access, in-use MCP
handling, Inno Setup, or frozen GUI editing. Those remain Gate 0 work.
