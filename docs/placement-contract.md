# The placement contract

SPDX-License-Identifier: CC0-1.0

Schema: [`schema/asset.schema.json`](../schema/asset.schema.json) ·
Version: `tessera.asset/1`

Every field below exists because something goes wrong without it. This page is
organised by the failure each field prevents, because that is the only useful
way to read a schema.

Inspect any asset live:

```bash
./tessera describe wall.doorway.4m
```

---

## "How big is this actually?"

| Field | |
|---|---|
| `dimensions.bounds` | measured min/max in local metres |
| `dimensions.size` | measured extent per axis |
| `dimensions.grounded_bounds` | the bounds it would have sitting exactly on `z = 0` |
| `dimensions.base_z_local`, `top_z_local` | the two planes that matter most |
| `geometry.triangles`, `vertices`, `surface_area`, `signed_volume` | budget and sanity |
| `geometry.sha256` | changes if and only if the mesh changes |

All measured from the solid at build time. `size` and `bounds` are cross-checked
against each other by a rule, because two fields describing one measurement must
agree.

## "Where is the origin, and will this float?"

| Field | |
|---|---|
| `pivot.base_offset_z` | **the important one.** `world_z = support_top + base_offset_z` |
| `pivot.convention` | the named rule this asset follows |
| `pivot.rationale` | why the origin is there, in prose |
| `pivot.offset_from_bounds_min` | origin relative to the minimum corner |
| `pivot.offset_from_footprint_centre` | origin relative to the footprint centre |
| `placement.support.datum_connector` | when grounding is measured at a connector plane rather than the lowest vertex |

Getting the pivot wrong is the single most common cause of a floating or buried
object, so `asset.pivot.on_base` is a **hard rule** rather than a documented
convention: an asset in a base-pivot role whose `base_offset_z` is not zero
fails the build, with the exact translation needed to fix it.

## "Which way does it face?"

`axes.forward`, `axes.up`, `axes.right`, `axes.ground_plane`,
`axes.intended_ground_normal`, and the whole `space` block: convention,
handedness, linear unit, angle unit, rotation order.

Mixed coordinate systems in one catalog is the failure that produces mirrored
buildings and sideways roofs, so `asset.space.canonical` refuses anything not in
canonical space and `asset.space.linear_unit` refuses anything not in metres — a
centimetre asset in a metre catalog is a silent 100x bug.

## "What am I allowed to do to it?"

| Field | |
|---|---|
| `placement.grid.policy` | `module`, `module_xy`, `mated` or `free` |
| `placement.grid.snap_xy`, `snap_z` | the lattice, or `null` for unconstrained |
| `placement.grid.rationale` | why this policy |
| `placement.allowed_rotations` | legal yaws, or `null` for unrestricted |
| `placement.allow_pitch_roll` | almost always false |
| `placement.allowed_scaling` | `min`, `max`, `uniform_only`, and a `rationale` |
| `placement.prohibited_scaling` | stated explicitly, not implied |
| `placement.support` | `requires_support`, `rests_on`, `may_float`, `datum_connector` |
| `placement.footprint_rects`, `footprint_area` | where it actually touches its support |

Footprint is not silhouette. A workbench's footprint is its four legs, not its
overhanging top — which is what makes "is this supported" a meaningful question
rather than a bounding-box guess.

Every restriction ships with its reason. `allowed_scaling.rationale` for a wall
reads: *"Modular pieces are a dimensional standard. Scaling one moves its
connectors off the grid and stops it seaming with every other piece in the
kit."* An agent that can read the reason is far less likely to decide the rule
is arbitrary.

## "How does it attach to other things?"

Each entry in `connectors[]`:

| Field | |
|---|---|
| `id`, `kind`, `role` | identity |
| `position` | local metres |
| `normal` | unit, points **out**, along the direction a partner approaches from |
| `tangent` | unit, orthogonal to the normal — **fixes roll** |
| `mating_mode` | `point` (coincident points) or `surface` (coplanar planes, contained extents) |
| `extent_half` | half-extent in the (tangent, binormal) frame; required for surface mates |
| `scale_class` | `mini`, `standard`, `mega` |
| `compatible_kinds`, `incompatible_kinds` | both stated, not one inferred |
| `tolerance.position_metres` | maximum gap |
| `tolerance.angle_degrees` | maximum deviation from opposed normals |
| `tolerance.roll_degrees` | maximum tangent misalignment |
| `required` | whether the asset is meaningless unconnected |

Three things here are improvements over what came before:

- **The tangent.** Without it a mate is a position plus an ambiguous spin, and a
  piece can join correctly while rolled 90 degrees about the axis, with trim and
  panel lines not lining up.
- **`mating_mode: surface`.** Support is a plane-and-extent relation, not a point
  coincidence. Without it, "a wall rests on a floor" is not expressible.
- **Tolerances on the connector.** "Nearly opposite" used to be a magic `-0.965`
  buried in a snapping function. Now it is `angle_degrees` and it travels with
  the connector that needs it.

## "What space does it fill, and what must stay empty?"

| Field | |
|---|---|
| `occupancy.boxes` | disjoint AABBs — the solid itself |
| `occupancy.exact` | false only for extruded profiles |
| `occupancy.approximation_tolerance` | how far an inexact set may fall short; zero when exact |
| `occupancy.volume`, `disjoint` | invariants a rule checks |
| `clearance.boxes` | volumes that must remain free for the asset to **function** |

Clearance is reserved for function-critical volumes — a door swing, a walk-up, a
maintenance gap. It is deliberately *not* used for headroom above a floor:
overstating clearance flags every wall and prop standing on that floor and turns
the report into noise. That was a real early mistake.

## "Can I walk through it?"

Each entry in `apertures[]`:

| Field | |
|---|---|
| `kind` | `door`, `window`, `hatch`, `vent`, `passage` |
| `bounds` | the hole, in local metres |
| `traversal_axis` | which way you go through |
| `clear_width`, `clear_height` | the numbers that decide |
| `traversable` | a window is a sight line, not a route |
| `fits_capsule.admits_reference_character` | does an adult-sized capsule actually fit |

An opening nobody can walk through is a wall with a decoration, so an aperture
marked traversable whose clear size rejects the reference character **fails the
build**.

## "Will collision seal the doorway?"

| Field | |
|---|---|
| `collision.hulls` | convex decomposition, derived from the carved occupancy set |
| `collision.mode`, `source`, `exact` | how it was produced |
| `collision.preserves_apertures` | checked, not claimed |
| `collision.auto_convex_would_seal_apertures` | true when letting the engine generate it would close a doorway |
| `collision.engine_hint` | import as convex hulls; do **not** auto-generate |

This is the trap that makes a mesh look right and the level play wrong. Because
the hulls *are* the carved solid, the aperture is a hole in the collision too —
and a rule asserts it on every build.

## "Where did it come from, legally?"

| Field | |
|---|---|
| `provenance.generator`, `generator_version` | the exact function and version |
| `provenance.created_utc`, `authored_by` | when and who |
| `provenance.origin` | `original-generated`, `original-authored`, `third-party` |
| `provenance.source_inputs` | empty for every asset here, and a rule enforces it |
| `provenance.third_party_review` | required and non-empty if origin is third-party |
| `license.code_spdx`, `assets_spdx` | `0BSD` and `CC0-1.0` |
| `license.attribution_required`, `commercial_use`, `redistribution` | the permissions, machine-readably |

Per asset rather than per repository, because "the repo is CC0" is not an
auditable statement.

## "Has any of this been checked?"

`validation.status`, `validator_version`, `checked_utc`, `checks_passed`,
`checks_failed`, `coverage`.

Recording the checks that *passed* is what turns a report into a coverage
statement. "No errors" only means something alongside "and here are the nineteen
rules that were evaluated".
