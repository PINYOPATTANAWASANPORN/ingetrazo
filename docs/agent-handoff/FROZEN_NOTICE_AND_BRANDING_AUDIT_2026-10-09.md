# Frozen notice and branding inventory — 2026-10-09

This is a technical inventory of the staged #87 Windows bundle, not a legal
opinion or approval to distribute it. The inspected bundle is
`C:\Users\Lenovo\Desktop\IngeTrazoTest\dist-pr87\ingetrazo`; its application
code and packaging sources match `47fddb9`. The installed application remains
at `3815ef8`.

## What the bundle contains

- `packaging/verify_frozen_notices.py` passed: the project `LICENSE`, pinned
  OpenSKP notice, and 43 wheel metadata/license files match their sources.
- The bundled PySide6, PySide6-Addons, PySide6-Essentials and shiboken6 wheel
  metadata all report version **6.11.2**. Each bundled `licenses/` directory
  contains `LicenseRef-Qt-Commercial.txt`; none contains a complete community
  license text. The staged `PySide6` tree contains 44 DLLs, including 15
  `Qt6*.dll` files, and no file whose name matches LICENSE, NOTICE, COPYING,
  COPYRIGHT or ATTRIBUTION. This is a file inventory, not a conclusion about
  the applicable license for each library.
- The staged `ingetrazo.exe` has no Windows PE FileVersion, ProductVersion,
  ProductName, CompanyName or FileDescription fields. The source version is
  `0.5.7` in `core/version.py`; the Inno Setup source injects that version at
  build time and currently names the upstream author as publisher. A fork
  preview must choose accurate publisher/product identifiers before packaging.

The successor [draft PR #89](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/89)
on `fix/windows-exe-version-info` adds source-version PE
resources to the GUI and MCP executables and checks them in the Windows build
workflow. A local rebuild displays `FileVersion` and `ProductVersion` 0.5.7,
`ProductName` IngeTrazo, the expected original filename, and a nonempty file
description on both executables. The verifier rejects the older #87 bundle
whose PE fields are empty. This resolves the missing executable metadata
observation for that candidate build; it does not settle the fork's publisher,
name or update-channel policy, or the Qt notice inventory.

Qt's own [Qt for Python license inventory](https://doc.qt.io/qtforpython-6/licenses.html)
distinguishes Qt for Python contributions from Qt's separate third-party
source inventory. The current wheel-file verifier cannot establish which
additional texts and notices this exact frozen binary set needs.

## Next release-gate work

1. Map each included Qt module/plugin and other binary dependency to its
   exact-version upstream license and notice source; preserve the source URL,
   version and file hash in a reviewable manifest. Have the intended
   distributor review the resulting obligations before external distribution.
2. Add the applicable notice files to the bundle and extend the verifier to
   check byte equality and presence. Do not infer completeness from the
   current 43-file wheel check.
3. Decide fork name, publisher and version policy; then align installer,
   executable metadata, application About dialog and update channel. Preserve
   upstream authorship and attribution.
4. Complete interactive frozen document save/reopen and edit checks before
   promoting this staged bundle to `C:\Program Files\IngeTrazo`.
