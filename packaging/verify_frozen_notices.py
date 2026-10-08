"""Verify that the frozen bundle retained the build wheels' notice files.

Run with the build environment's Python, after PyInstaller has finished:
    python packaging/verify_frozen_notices.py dist/ingetrazo
"""

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path


DISTRIBUTIONS = (
    "ezdxf", "fonttools", "manifold3d", "mapbox-earcut", "numpy", "openskp",
    "PySide6", "PySide6-Addons", "PySide6-Essentials", "shapely", "shiboken6",
    "trimesh",
)
REQUIRED = {"ezdxf", "manifold3d", "numpy", "openskp", "PySide6"}


def verify(bundle: Path) -> int:
    internal = bundle / "_internal"
    if not internal.is_dir():
        raise FileNotFoundError(f"PyInstaller data directory missing: {internal}")

    root = Path(__file__).resolve().parents[1]
    for relative in ("LICENSE", "vendor/openskp/LICENSE",
                     "vendor/openskp/SOURCES.md",
                     "packaging/THIRD_PARTY_LICENSES.md"):
        source = root / relative
        target = (internal / "LICENSE" if relative == "LICENSE"
                  else internal / "third_party_licenses" / source.name
                  if relative.startswith("packaging/")
                  else internal / "third_party_licenses/openskp" / source.name)
        if target.read_bytes() != source.read_bytes():
            raise ValueError(f"frozen notice differs from source: {target}")

    checked = 0
    for name in DISTRIBUTIONS:
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            if name in REQUIRED:
                raise
            continue
        destination = internal / "third_party_licenses" / name.lower().replace("-", "_")
        for item in dist.files or ():
            parts = item.parts
            if not parts or not parts[0].endswith(".dist-info"):
                continue
            if len(parts) == 2 and parts[1] == "METADATA":
                target = destination / "METADATA"
            elif len(parts) >= 3 and parts[1] == "licenses":
                target = destination.joinpath(*parts[1:])
            else:
                continue
            source = Path(dist.locate_file(item))
            if not source.is_file():
                raise FileNotFoundError(f"wheel notice missing: {source}")
            if target.read_bytes() != source.read_bytes():
                raise ValueError(f"frozen wheel notice differs from source: {target}")
            checked += 1
    print(f"Verified {checked} wheel metadata/license files and project/OpenSKP notices")
    return checked


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_frozen_notices.py BUNDLE_DIR")
    verify(Path(sys.argv[1]))
