# Typed architectural creation

The Assistant and MCP `propose_actions` share this contract. Geometry is
prepared off-scene, previewed as parameters and model-space bounds, and only
inserted after in-app approval. A proposal is one Undo/Redo step. Existing
revision, idempotency, discard and task-scope rules still apply.

All distances use model units. Coordinates are bounded to +/-1,000,000.
Dimensions must be finite, positive, and at most 1,000,000; dimensions that
collapse at the mesh's precision are rejected.

| Action | Required geometric fields | Meaning |
| --- | --- | --- |
| `create_box` | `size: [x,y,z]` | Axis-aligned solid from `origin` (default `[0,0,0]`) |
| `create_cylinder` | `radius`, `height` | Vertical cylinder at `origin`; `segments` defaults to 24 |
| `create_slab` | `size: [width,depth,thickness]` | Rectangular solid growing upward from `origin` |
| `create_wall` | `start`, `end`, `height`, `thickness` | Horizontal baseline at one Z; thickness grows LEFT of start to end |
| `create_component_instance` | `source_id`, `offset: [x,y,z]` | Copy a top-level component, translated from its current placement in model coordinates |

Primitives require `name` and accept existing `tag`, `material`, and a
`component` boolean. Component copies inherit source metadata and may override
`name`. Copies have fresh UIDs, share prototype meshes and retain source
rotation/scale. Sources must be visible and unlocked, with valid instance
placements throughout their child tree. Classic children are rejected rather
than silently promoted during preview.

`create_wall.openings` is an optional array (maximum 32) of
`{offset, sill, width, height}`. Offset measures from start along the baseline;
sill measures above the baseline. A zero sill makes a door notch, a positive
sill makes a window hole. Openings must fit strictly within the ends and top,
and their horizontal intervals cannot overlap or touch. No clamping occurs.
This constructs openings in a new wall; it does not cut an existing wall or
add door/window assemblies. The result remains editable freeform geometry.

## Placement and scope

- `coordinate_space: "model"` is the backward-compatible default and has no
  `parent_id`.
- Nested primitives require `coordinate_space: "parent"` and an explicit
  `parent_id`. Coordinates refer to the parent's mesh frame; preview bounds
  compose all ancestor placements into model coordinates.
- The parent must be a non-component Group with an instance matrix. It and
  all ancestors must be visible and unlocked. No ancestor may be a shared
  Component definition. Classic parents are not converted implicitly.
- Close any active group-edit context first. Component copies currently have
  top-level sources and destinations only.
- Registered tasks check `parent_id` and `source_id` as well as `entity_ids`.
  Entity-scoped primitive creation requires an in-scope parent. Model-scoped
  tasks can create top-level objects, including in an empty model.
- A proposal cannot transform a creation parent, ancestor or copy source in
  the same batch. Apply the transform, then propose creation at the new
  revision so the preview is accurate.

```json
{
  "action": "create_wall",
  "name": "Entrance wall",
  "coordinate_space": "model",
  "start": [0, 0, 0],
  "end": [6, 0, 0],
  "height": 3,
  "thickness": 0.2,
  "openings": [
    {"offset": 1, "sill": 0, "width": 1, "height": 2.1},
    {"offset": 3, "sill": 1, "width": 2, "height": 1}
  ]
}
```

Validation is covered by `tests/test_ai_architectural_creation.py`, including
closed topology, outward volume after subtracting openings, transformed
parent bounds, source purity, scope escape rejection and one-step Undo/Redo.
Preview is currently textual; an isolated geometry viewport remains future work.
