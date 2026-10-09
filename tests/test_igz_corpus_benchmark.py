"""The model corpus must reject a changed input and measure a real IGZ."""

import hashlib
import json

import pytest
from PySide6.QtGui import QVector3D as V

from core.scene import Scene
from formats.igz import save_scene
from scripts.bench_igz_corpus import cases_from_manifest, run


def _manifest(root, source):
    manifest = root / "corpus.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "cases": [{"id": "tiny", "path": source.name,
                   "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}],
    }), encoding="utf-8")
    return manifest


def test_benchmark_loads_in_a_fresh_process_and_preserves_source(tmp_path):
    scene = Scene()
    scene.mesh.add_face([V(0, 0, 0), V(1, 0, 0), V(0, 1, 0)])
    source = tmp_path / "tiny.igz"
    save_scene(scene, source)
    manifest = _manifest(tmp_path, source)
    before = source.read_bytes()

    report = run(manifest, repeats=1, root=tmp_path)

    assert report["cases"][0]["stats"]["unique_faces"] == 1
    assert report["cases"][0]["load_ms"][0] > 0
    assert report["cases"][0]["process_wall_ms"][0] > 0
    assert source.read_bytes() == before


def test_benchmark_rejects_changed_or_external_corpus_file(tmp_path):
    source = tmp_path / "tiny.igz"
    source.write_bytes(b"original")
    manifest = _manifest(tmp_path, source)
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        cases_from_manifest(manifest, tmp_path)

    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["cases"][0]["path"] = "../outside.igz"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="outside checkout"):
        cases_from_manifest(manifest, tmp_path)
