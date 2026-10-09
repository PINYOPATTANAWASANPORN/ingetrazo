"""Create a small disposable IGZ with nested, shared component geometry."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtGui import QVector3D as V

from core.group import Group, copy_group
from core.mesh import Mesh
from core.scene import Scene
from formats.igz import save_scene


def make_fixture(path: Path) -> None:
    scene = Scene()
    children = []
    for x, name in ((0, "Left"), (3, "Right")):
        mesh = Mesh()
        mesh.add_face([V(x, 0, 0), V(x + 1, 0, 0),
                       V(x + 1, 1, 0), V(x, 1, 0)])
        children.append(Group(mesh, name=name))
    parent = Group(name="Nested component")
    parent.adopt(children)
    scene.groups.extend((parent, copy_group(parent, V(0, 4, 0))))
    path.parent.mkdir(parents=True, exist_ok=True)
    save_scene(scene, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    make_fixture(args.output)
