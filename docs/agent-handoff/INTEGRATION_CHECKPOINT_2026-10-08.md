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
CI and full native Windows testing for #82 are in progress; this is not yet
proof that the entire suite passes.

## Remaining release evidence

Finish the one-process native Windows suite at #82's final SHA, verify #82
hosted CI, build the frozen Windows app/MCP from that SHA, and perform the
representative GUI and document/MCP smoke in Gate 0. Preserve the older
installed build and its rollback until those checks are complete.
