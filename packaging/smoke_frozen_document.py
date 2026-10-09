"""Exercise a frozen Windows GUI's document workflow on disposable copies.

This is deliberately an external packaging probe.  Its temporary user plugin
runs inside the frozen executable, so imports, Qt, document I/O and History
come from the actual candidate bundle rather than the source checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


PROBE_PLUGIN = r'''
import hashlib
import json
import os
import traceback
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

from core.history import AddFaceCommand


def _point(p):
    return tuple(round(float(n), 4) for n in (p.x(), p.y(), p.z()))


def _ring(points):
    # A save may rotate or reverse a polygon loop without changing its shape.
    coords = [_point(p) for p in points]
    if not coords:
        return ()
    turns = (tuple(coords[i:] + coords[:i]) for i in range(len(coords)))
    reverse = list(reversed(coords))
    back = (tuple(reverse[i:] + reverse[:i]) for i in range(len(reverse)))
    return min(*turns, *back)


def _mesh_signature(mesh):
    vertices = sorted(_point(v.position) for v in mesh.vertices)
    edges = sorted(tuple(sorted((_point(e.a), _point(e.b))))
                   for e in mesh.edges)
    faces = sorted((_ring(f.vertices),
                    tuple(sorted(_ring(h) for h in f.holes)))
                   for f in mesh.faces)
    return vertices, edges, faces


def _group_signature(group):
    matrix = (tuple(round(float(n), 4) for n in group.xform.data())
              if group.xform is not None else None)
    return (group.uid, group.name, group.layer, bool(group.hidden),
            bool(group.locked), matrix, _mesh_signature(group.mesh),
            tuple(_group_signature(c) for c in group.children))


def _group_snapshot(groups):
    tree = tuple(_group_signature(g) for g in groups)
    encoded = repr(tree).encode("utf-8")
    mesh_ordinals = {}
    sharing = []
    def visit(nodes):
        for group in nodes:
            key = id(group.mesh)
            sharing.append(mesh_ordinals.setdefault(key, len(mesh_ordinals)))
            visit(group.children)
    visit(groups)
    return {"sha256": hashlib.sha256(encoded).hexdigest(),
            "total": len(sharing), "top_level": len(groups),
            "nested": len(sharing) - len(groups),
            "shared_mesh_pattern": sharing}


def setup(app):
    def run():
        report_path = Path(os.environ["INGETRAZO_FROZEN_SMOKE_REPORT"])
        source = Path(os.environ["INGETRAZO_FROZEN_SMOKE_INPUT"])
        saved = Path(os.environ["INGETRAZO_FROZEN_SMOKE_OUTPUT"])
        result = {"source": str(source), "saved": str(saved)}
        code = 1
        try:
            window = app.window
            assert window.open_path(source), "window.open_path failed"
            before = len(app.scene.mesh.faces)
            groups_before = _group_snapshot(app.scene.groups)
            result.update(faces_before=before, groups_before=groups_before)
            face = [QVector3D(1000, 1000, 0), QVector3D(1001, 1000, 0),
                    QVector3D(1001, 1001, 0), QVector3D(1000, 1001, 0)]
            app.viewport.history.execute(AddFaceCommand(face))
            assert app.viewport.history.last_error is None
            assert len(app.scene.mesh.faces) == before + 1, "first edit failed"
            window._do_save(saved)
            assert saved.is_file(), "save produced no document"
            assert window._current_path == saved, "save did not update document"
            assert window.open_path(saved), "saved document did not reopen"
            assert len(app.scene.mesh.faces) == before + 1, "reopen lost edit"
            assert _group_snapshot(app.scene.groups) == groups_before, (
                "reopen changed nested group geometry or hierarchy")
            assert not app.viewport.history.undo_stack, "reopen retained old history"

            second = [QVector3D(1002, 1000, 0), QVector3D(1003, 1000, 0),
                      QVector3D(1003, 1001, 0), QVector3D(1002, 1001, 0)]
            app.viewport.history.execute(AddFaceCommand(second))
            assert app.viewport.history.last_error is None
            assert len(app.scene.mesh.faces) == before + 2, "second edit failed"
            assert app.viewport.history.undo(), "undo failed"
            assert len(app.scene.mesh.faces) == before + 1, "undo count wrong"
            assert app.viewport.history.redo(), "redo failed"
            assert len(app.scene.mesh.faces) == before + 2, "redo count wrong"
            window._do_save(saved)
            assert window.open_path(saved), "final saved document did not reopen"
            assert len(app.scene.mesh.faces) == before + 2, "final reopen lost redo"
            assert _group_snapshot(app.scene.groups) == groups_before, (
                "final reopen changed nested group geometry or hierarchy")
            result.update(status="passed", faces_after=before + 2,
                          groups_after=_group_snapshot(app.scene.groups))
            code = 0
        except BaseException:
            result.update(status="failed", error=traceback.format_exc())
        finally:
            report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            QApplication.instance().exit(code)

    # Let the real MainWindow finish construction and show before exercising it.
    QTimer.singleShot(250, run)
'''


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(bundle: Path, source: Path, output_dir: Path, timeout: int,
        platform: str = "windows", require_nested: bool = False) -> dict:
    exe = bundle / "ingetrazo.exe"
    if not exe.is_file():
        raise FileNotFoundError(exe)
    if not source.is_file() or source.suffix.lower() != ".igz":
        raise ValueError("input must be an existing .igz document")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source = source.resolve()
    if output_dir == source.parent:
        raise ValueError("output directory must differ from input directory")
    original_hash = sha256(source)
    with tempfile.TemporaryDirectory(prefix="ingetrazo-frozen-smoke-") as folder:
        root = Path(folder)
        plugins = root / "appdata" / "ingetrazo" / "plugins"
        plugins.mkdir(parents=True)
        (plugins / "frozen_document_probe.py").write_text(
            PROBE_PLUGIN, encoding="utf-8")
        report_path = root / "probe-report.json"
        copied = root / "input.igz"
        shutil.copyfile(source, copied)
        saved = output_dir / "frozen-workflow.igz"
        if saved.exists():
            raise FileExistsError(saved)
        env = os.environ.copy()
        env.update(
            APPDATA=str(root / "appdata"),
            LOCALAPPDATA=str(root / "localappdata"),
            QT_QPA_PLATFORM=platform,
            INGETRAZO_FROZEN_SMOKE_INPUT=str(copied),
            INGETRAZO_FROZEN_SMOKE_OUTPUT=str(saved),
            INGETRAZO_FROZEN_SMOKE_REPORT=str(report_path),
        )
        process = subprocess.run(
            [str(exe), "--new-window"], env=env, cwd=str(root),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=timeout, check=False,
        )
        report = (json.loads(report_path.read_text(encoding="utf-8"))
                  if report_path.is_file() else {"status": "no_report"})
        report.update(exit_code=process.returncode,
                      qt_platform=platform,
                      source_sha256=original_hash,
                      source_unchanged=sha256(source) == original_hash,
                      saved_sha256=sha256(saved) if saved.is_file() else None)
        if process.returncode != 0 or report.get("status") != "passed":
            report["stderr_tail"] = process.stderr[-2000:]
            raise RuntimeError(json.dumps(report, indent=2))
        if not report["source_unchanged"] or report["saved_sha256"] is None:
            raise RuntimeError(json.dumps(report, indent=2))
        if require_nested and report.get("groups_before", {}).get("nested", 0) < 1:
            raise RuntimeError("input has no nested groups: " + json.dumps(report))
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("source_igz", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--platform", choices=("windows", "offscreen"),
                        default="windows")
    parser.add_argument("--require-nested", action="store_true",
                        help="fail unless the input exercises nested groups")
    parser.add_argument("--report", type=Path,
                        help="also write the JSON result to this path")
    args = parser.parse_args()
    result = run(args.bundle, args.source_igz, args.output_dir,
                 args.timeout, args.platform, args.require_nested)
    output = json.dumps(result, indent=2)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    print(output)
