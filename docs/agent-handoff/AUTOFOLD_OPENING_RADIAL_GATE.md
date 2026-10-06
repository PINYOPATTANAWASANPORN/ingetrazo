# Autofold opening and radial-edge gate

Base: draft PR #61 (`test/autofold-shared-vertex-grid`).
Branch: `test/autofold-holed-nonmanifold` ([draft PR #62](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/62)).

The previous shared-grid regression checked four ordinary incident quads. This
follow-up covers two distinct mesh contracts:

- A 4 × 4 face with a 2 × 2 opening is folded by lifting either an outer
  corner or a hole corner. The preview leaves the original face intact; the
  committed planar pieces retain material, their projected area remains 12,
  and Undo/Redo restores the opening and folded state.
- Three faces sharing one non-manifold edge are folded by lifting one shared
  endpoint. The preview predicts three affected faces, the committed pieces
  are planar, the edge still has three incident faces, material attributes
  survive, and the change is one undo step.

The four Move/Autofold suites pass 62 tests on native Windows Qt and 62 with
offscreen Qt. The expanded nine-file Windows CI selection passes 182 locally
offscreen. Hosted run [37479008698](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37479008698) passed both Windows and Ubuntu jobs. No product geometry code changed:
the new edge cases already satisfy the existing mesh contract.

Remaining: evaluate larger real meshes, self-intersecting or degenerate input,
and explicit Autofold controls. The installed Windows build is unchanged.
