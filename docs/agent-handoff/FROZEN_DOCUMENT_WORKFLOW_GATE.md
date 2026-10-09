# Frozen Windows document workflow gate — 2026-10-09

Branch `test/frozen-document-workflow` builds on draft PR #89. The previous
release check showed that a staged GUI could open a copied document and stay
responsive, but it did not save, reopen or edit a document inside the frozen
process. `packaging/smoke_frozen_document.py` now exercises those paths using
the candidate `ingetrazo.exe` itself.

The runner creates isolated `%APPDATA%` and `%LOCALAPPDATA%` directories and a
temporary user plugin. The plugin executes after the frozen main window opens.
For a copy of a supplied `.igz`, it calls the window's open path, adds a face
through History, saves through the window, reopens, adds a second face,
performs Undo and Redo, saves again and reopens again. It checks face counts,
top-level group counts, cleared history on reopen and the unchanged source
SHA-256. A subprocess timeout or missing report fails the runner. All writes
go to the caller's output directory; the original input is never opened by
the frozen process. A pre-existing output document is rejected.

The Windows build workflow runs the probe offscreen after bundle and PE
version verification, before creating the portable ZIP and installer. It
uses an isolated temporary output directory. This makes a release build fail
if its frozen GUI cannot complete the basic document workflow.

## Local evidence

Candidate: `C:\Users\Lenovo\Desktop\IngeTrazoTest\dist-version-final\ingetrazo`
from the PR #89 build. The executable's SHA-256 is
`4ED1B83CA591DA2B89936890161EE6A07DBDFD46C253C943DDD8D8B78C9AB3AF`.

| Input copy | Platform | Groups before/after | Faces before/after | Result |
| --- | --- | ---: | ---: | --- |
| `resources/components/sofa.igz` | offscreen | 1 / 1 | 0 / 2 | passed |
| `examples/arco-yanque.igz` | native Windows | 30 / 30 | 0 / 2 | passed |
| `examples/pileta-fuente-yanque.igz` | native Windows | 39 / 39 | 0 / 2 | passed |

The JSON reports are in the adjacent workspace as
`frozen-workflow-pr90-final-offscreen.json`,
`frozen-workflow-pr90-final-arco.json` and
`frozen-workflow-pr90-final-pileta.json`. Every run exited 0, reopened after
both saves, exercised Undo/Redo, and reported an unchanged original hash.
This is stronger than the earlier frozen open-only smoke, but it does not
verify physical mouse interactions, viewport pixels, the full nested geometry
structure, or the elevated installer/update path. The installed Program Files
copy remains at `3815ef8`; these checks ran on the staged candidate only.

PR #89 CI run [37864181051](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37864181051)
passed Ubuntu non-slow and Windows Qt offscreen jobs. The new release-build
step still needs hosted build-workflow execution before it can be considered
verified on the runner.
