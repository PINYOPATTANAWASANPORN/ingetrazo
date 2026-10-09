# Frozen nested-document round-trip gate — 2026-10-09

[Draft PR #91](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/91)
on `test/frozen-nested-roundtrip` builds on the frozen open/edit/save
probe in draft PR #90. The original probe counted only top-level groups; a
document could pass after losing a child group, changing its face geometry,
or breaking mesh sharing between component copies.

`packaging/smoke_frozen_document.py` now snapshots the entire group tree at
open, after the first save/reopen, and after the second save/reopen. It checks
group order, stable UIDs, names, tags, visibility and lock flags, instance
transforms, the sorted vertex and edge positions, canonical face outer and
hole loops, and the shared-mesh identity pattern. Coordinates are rounded to
four decimals for comparison, matching the mesh's weld precision. The two
intentional new faces live in the scene mesh, outside this group snapshot.

`packaging/make_frozen_nested_fixture.py` generates a disposable IGZ with
two copies of a component, each with two nested face-bearing children. The
Windows packaging workflow runs both its existing sofa case and this fixture
against the newly frozen executable. `--require-nested` prevents a fixture
without children from silently passing.

## Local frozen-process evidence

Candidate bundle: `C:\Users\Lenovo\Desktop\IngeTrazoTest\dist-version-final\ingetrazo`
from the PR #89 build; executable SHA-256
`4ED1B83CA591DA2B89936890161EE6A07DBDFD46C253C943DDD8D8B78C9AB3AF`.

| Source | Qt platform | Group nodes | Nested | Sharing | Result |
| --- | --- | ---: | ---: | --- | --- |
| generated nested component | Windows | 6 | 4 | `[0,1,2,0,1,2]` | passed |
| `examples/pileta-fuente-yanque.igz` | Windows | 39 | 0 | multiple copies | passed |
| `examples/arco-yanque.igz` | offscreen | 30 | 0 | checked | passed |

The report files are adjacent to the checkout:
`frozen-nested-final.json`, `frozen-nested-pileta.json`, and
`frozen-nested-arco-final.json`. The original input SHA-256 was unchanged in every
run. The nested-only flag rejected `sofa.igz` (zero nested groups) with exit 1.
The component-sharing source regression suite passed 5 tests. These checks
establish in-memory round-trip geometry and sharing for the
tested files. They do not inspect materials, UVs, rendered pixels, mouse
interaction, or an elevated installation. The hosted Windows release workflow
has not yet executed this new step, and `C:\Program Files\IngeTrazo` remains
at commit `3815ef8`.
