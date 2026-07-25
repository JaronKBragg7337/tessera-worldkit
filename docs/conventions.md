# Conventions

SPDX-License-Identifier: CC0-1.0

One page. If something here is ambiguous, the code in `src/tessera/units.py` is
authoritative and this document is the bug.

## Space

| | |
|---|---|
| Handedness | right |
| Up | `+Z` |
| Forward | `+Y` |
| Right | `+X` |
| Linear unit | metre |
| Angle unit | degree — radians never appear in serialized data |
| Rotation | `[yaw about Z, pitch about Y, roll about X]`, applied ZYX-intrinsic |
| Coordinate lattice | `1e-6 m`; every coordinate is snapped before comparison |
| Contact tolerance | `5e-4 m` — below this, two surfaces are touching |

Degrees rather than quaternions because layouts get hand-edited and inspected,
and a quaternion in a JSON file is a reliable source of silent error. The
lattice exists so a build is byte-identical across machines.

## Pivots

There is **one rule per family**, deliberately, so an agent never has to branch.

| Convention | Used by | Origin sits at |
|---|---|---|
| `bay_min_corner_on_base` | foundations, floors, walls, corners, openings | minimum corner of the bay, on the asset's own base |
| `footprint_centre_on_base` | props | centre of the footprint, on the base |
| `leaf_min_corner_on_base` | door and window leaves | minimum corner, on the base, matching the aperture's minimum corner |
| `bay_min_x_at_bearing_plane` | roof panels | minimum X, on the plane where the panel bears on a wall top |
| `bay_min_x_at_ridge_line` | ridge caps | minimum X, on the ridge line |

Every asset publishes `pivot.base_offset_z`. Place the origin at
`supporting_surface_z + base_offset_z` and it is grounded exactly. Every asset
also publishes `pivot.rationale` in prose, so the reason travels with the number.

The two roof conventions exist because a roof panel's lowest vertex is its eave
overhang, which legitimately hangs *below* the plane it bears on. Using the
lowest vertex as the datum would report every correctly placed roof as buried.
Those assets declare `placement.support.datum_connector` and grounding is
measured there instead.

## Grid

| | |
|---|---|
| Bay module | `4.00 m` |
| Wall height | `3.00 m` |
| Wall thickness | `0.20 m` |
| Translation snap | `0.20 m` |
| Vertical snap | `0.05 m` |
| Yaw step | `90°` for modular pieces |

The translation lattice must divide **both** the bay module and the wall
thickness, because a wall rotated 90 degrees is offset from its bay line by its
own thickness. A lattice that divides only the module reports every correctly
placed side wall as off-grid — this was a real bug, caught by the validator on
the first assembly, and `config.validate()` now refuses the combination.

90-degree yaw steps are not a style choice. At 90-degree steps an axis-aligned
box stays axis aligned under rotation, so occupancy, collision and aperture
tests remain **exact**. Off-axis rotation falls back to a conservative bounding
box, and the validator says so rather than quietly losing precision. Props are
exempt and declare `allowed_rotations: null`.

## Stack heights

Published in `catalog.derived` so nobody adds them up by hand:

| Plane | Z |
|---|---|
| Terrain | `0.00` |
| Foundation top | `0.30` |
| Floor top — the walking surface | `0.50` |
| Wall top / roof bearing | `3.50` |
| Ridge | `6.02` |

## Naming

| Thing | Form | Example |
|---|---|---|
| Asset id | `tsr:<kit>/<family>.<variant>.<size>` | `tsr:shell/wall.doorway.4m` |
| Instance id | `<short_name>_<nn>` | `wall_doorway_4m_01` |
| Connector id | lowercase, role-descriptive | `edge_pos_x`, `jamb_neg_y`, `bearing` |
| Material | `M_PascalCase` | `M_Concrete`, `M_RoofSheet` |
| Diagnostic code | `TSR_<SCOPE>_<PROBLEM>` | `TSR_LAYOUT_FLOATING` |

Asset ids are stable. They are never reused and never renamed in place; a
renamed asset is a new id and the old one is retired in the changelog.

## Connectors

A connector is a full local frame, not a point:

- `position` — where it is, in local metres
- `normal` — unit vector pointing **out** of the asset, along the direction a
  partner approaches from
- `tangent` — unit vector orthogonal to the normal, fixing roll

The tangent is what makes a mate a complete rigid transform rather than a
position plus an ambiguous spin. Without it, a piece can mate correctly and
still be rolled 90 degrees about the join axis, with trim and panel lines not
lining up — a failure neither source repository could detect.

`mating_mode` is `point` (the two points must coincide — seams, ridges, hinges)
or `surface` (the two planes must be coplanar and the smaller extent contained
in the larger — a wall standing on a floor). Modelling support as a *surface*
relation rather than a point coincidence is why "wall base rests on floor top"
is expressible at all.

Two connectors mate only when **all** of: kinds mutually compatible, scale
classes equal, points within `tolerance.position_metres`, normals opposed within
`tolerance.angle_degrees`, tangents aligned within `tolerance.roll_degrees`.
Every tolerance travels with the connector; none is a magic constant in a
snapping function.

## Scale classes

`mini` 0.5x, `standard` 1.0x, `mega` 2.0x. These are **module standards, not
multipliers you may improvise**. Two assets in different classes never mate,
even if the geometry happens to line up, because a join that is geometrically
close but dimensionally wrong is worse than one that is refused.
