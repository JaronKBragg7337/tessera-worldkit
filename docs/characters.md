# Characters

SPDX-License-Identifier: CC0-1.0

**Status: designed, not built.** Nothing in this document is implemented. It
exists now because the decision that matters — how characters integrate with the
shared contract — has to be made before the first vertex, not after.

## Why not yet

Characters are the obvious next thing to want and the wrong next thing to build.
A character is not a mesh problem: it is a mesh, a skeleton, skin weights, an
animation set, retargeting compatibility and a runtime, and each of those has
its own failure modes. Shipping a capsule figure to claim the box is ticked
would be worse than shipping nothing, because it would set the quality bar of
the whole project at "programmer art".

So the order is: prove the contract on static geometry (done — see
[`ROADMAP.md`](../ROADMAP.md) M1), then prototype **one** character end to end
and hold it to a stated quality bar, then scale the count. Never the reverse.

## Separate repository?

**Not yet, and the test is a dependency test rather than a taste one.**

Characters need: stable ids, provenance, licence, units and axes, bounds,
pivots, collision volumes, attachment sockets, validation, engine adapters.
That is the placement contract, almost unchanged. A socket is a connector; a hit
region is an occupancy box; a capsule is a clearance volume.

The parts that are genuinely new — skeleton, skin weights, animation, retarget
maps — are additive blocks on the same record, not a different record.

Split only when the character pipeline needs a build dependency the core does
not have (a mesh-deformation library, an animation runtime) and that dependency
would leak into the zero-dependency core. That is a concrete, checkable
condition. Until it is met, splitting adds a version-skew surface between the
contract and its largest consumer for no benefit.

## How characters extend the contract

The existing blocks carry over unchanged: `space`, `dimensions`, `pivot`,
`provenance`, `license`, `validation`. Pivot convention for a character is
`footprint_centre_on_base`, same as a prop, so `base_offset_z` grounding works
identically.

Connectors become attachment sockets:

```
kind: socket_hand_r | socket_hand_l | socket_spine | socket_head |
      socket_hip_r | socket_hip_l | socket_back
```

with the same `position` / `normal` / `tangent` frame and the same tolerance
block. A sword's `grip` connector mates a `socket_hand_r` under exactly the
rules that mate a wall edge to a wall edge — which means attachment validation
is already written.

New blocks:

| Block | Contents |
|---|---|
| `skeleton` | joint names, parents, rest transforms, naming convention id, joint count |
| `skinning` | max influences per vertex, normalisation, deform-quality notes |
| `animation` | clips with duration, loop flag, root-motion flag, sample rate |
| `retarget` | joint-name maps to Unity Humanoid and Unreal skeleton conventions |
| `hit_regions` | named capsules and boxes: head, torso, limbs |
| `body_modules` | which modular parts compose this character, and their swap sockets |
| `character_metrics` | eye height, shoulder width, stride length, capsule radius/height |

`character_metrics` is not decoration. It is what lets a validator answer "does
this character fit through that doorway" against a real figure instead of the
generic reference capsule the kit currently uses.

## The pipeline, in the order it should be built

1. **Parametric base mesh, scripted.** Height, proportion and build as
   parameters, exactly as the kit's dimensions come from `config.py`. Quad-
   dominant topology with proper edge loops at shoulder, elbow, hip and knee.
   This is the hard part and it should be attempted first, alone, on one figure.
2. **Skeleton generation** placed from the same parameters, so the rig cannot
   drift from the mesh.
3. **Skin weights**, generated and then measured — bend each joint through its
   range and check for candy-wrapper collapse and volume loss numerically. A
   deformation test that produces a number is worth more than a turntable.
4. **Modular body parts and clothing**, swapped at sockets, with seam-vertex
   compatibility as a validated property.
5. **Procedural materials and textures**, generated like the meshes.
6. **A locomotion set**: idle, walk, run, turn, jump, land. Six clips done well
   beat sixty done badly.
7. **Export and retarget**, then verify in each engine.

## Acceptance tests

The same standard as everything else: a milestone is done when a test says so,
not when it looks finished.

- [ ] one character generated end to end by script, from parameters only
- [ ] skeleton joint count and naming validated against the declared convention
- [ ] every vertex has `1..4` normalised influences, asserted
- [ ] deformation test: no joint through its full range loses more than 8% local
      volume or produces a self-intersection
- [ ] the character's capsule passes through `wall.doorway.4m` in the assembled
      workshop, checked by the aperture rules already in the validator
- [ ] a weapon mesh mates `socket_hand_r` and passes connector validation
- [ ] locomotion clips export and play in the three.js reference viewer
- [ ] Unity Humanoid retarget produces no missing required bones
- [ ] Unreal skeleton import produces no retarget warnings
- [ ] provenance shows `origin: original-generated` with empty `source_inputs`

## Licensing

Characters are the place where free-asset pipelines usually acquire an
obligation — a base mesh with attribution terms, an animation library with a
redistribution clause, a scan with unclear rights. The policy is unchanged and
non-negotiable: **generated originally, or not included.** See
[`provenance-policy.md`](provenance-policy.md).

Licensing is not a reason to avoid characters. It is a reason to create them.
