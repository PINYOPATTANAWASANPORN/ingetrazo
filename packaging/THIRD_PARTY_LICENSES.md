# Third-party package files in the frozen bundle

This directory contains `METADATA` and any `licenses/` files supplied by
selected runtime Python distributions used to build IngeTrazo. Each package
has its own subdirectory. The OpenSKP subdirectory also includes the license
copied from the exact source revision pinned by the project.

The presence of these files is a packaging check, not a complete review of
every notice needed for redistribution. In particular, the PySide6/Qt wheels
currently include a commercial-license reference file but no complete
community-license texts in their wheel metadata. Qt and other bundled binary
components still need a separate notice review before release.
The upstream inventory is maintained at
https://doc.qt.io/qtforpython-6/licenses.html.
