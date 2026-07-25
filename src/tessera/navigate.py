"""Can a character actually get there?

SPDX-License-Identifier: 0BSD

This module exists because of one line in a benchmark draft. A model with no
tools was asked for a two-storey safe house, stacked three crates where a
staircase should be, and wrote "two stories with interior access". The geometry
validated. Nothing in the framework could contradict it, because reachability
was not a property anything measured.

So: a navigation solver over the exact occupancy sets, and a claim an author can
make that the validator will either prove or refuse.

How it works
------------
Occupancy is a set of axis-aligned boxes, which makes this much cheaper than a
voxel grid. For each column of the plan at ``cell`` resolution, the boxes
covering that column give a sorted set of *surface heights* -- the tops of
things you could stand on. A surface is **standable** when a box the size of the
character, standing on it, is free of every occupancy box in the scene.

Two standable surfaces in neighbouring columns are **connected** when the height
difference is within one step and the character fits at the higher of the two.
Flood filling that graph answers the question.

Direction of error
------------------
Every approximation here is deliberately conservative: the character is tested
as an axis-aligned box, which is *larger* than the capsule it stands for, so
anywhere this solver says you can stand, you can. It may refuse a squeeze that
would actually work. That is the correct direction -- a reachability claim that
is sometimes pessimistic is useful; one that is sometimes optimistic is the bug
this module was written to prevent.
"""
from __future__ import annotations

import math
from collections import deque

from .units import CONTACT_EPSILON, q

DEFAULT_CELL = 0.20
#: Matches Unreal's default MaxStepHeight of 45 cm, and Unity's default Step
#: Offset for a 1.8 m controller is in the same range. This is not a detail: at
#: 25 cm the solver called every real staircase unclimbable, because a character
#: with a 35 cm radius always has the tread two steps ahead inside its body box,
#: and that tread is 40 cm up. Modelling a tighter step limit than the runtime
#: actually uses produces false refusals on correct geometry.
DEFAULT_STEP_UP = 0.45
#: Falling further than this is a drop, not a walk. You can get down it, but the
#: solver will not claim it as a route in both directions.
DEFAULT_STEP_DOWN = 0.45
#: A cell centre this close to a box edge counts as over it.
EDGE_TOLERANCE = 1e-6


class NavGrid:
    """A character-aware walkable graph built from world occupancy boxes."""

    def __init__(self, boxes, *, cell=DEFAULT_CELL, radius=0.35, height=1.80,
                 step_up=DEFAULT_STEP_UP, step_down=DEFAULT_STEP_DOWN,
                 ground_z=0.0, margin=2.5):
        self.cell = cell
        self.radius = radius
        self.height = height
        self.step_up = step_up
        self.step_down = step_down
        self.ground_z = ground_z
        self.boxes = [tuple(b) for b in boxes]

        self.margin = margin
        if self.boxes:
            self.min_x = min(b[0] for b in self.boxes) - margin
            self.min_y = min(b[1] for b in self.boxes) - margin
            self.max_x = max(b[3] for b in self.boxes) + margin
            self.max_y = max(b[4] for b in self.boxes) + margin
        else:
            self.min_x = self.min_y = -margin
            self.max_x = self.max_y = margin

        # Snap the grid origin to the cell lattice. Assets in this framework sit
        # on a lattice by construction, so an unaligned grid puts cell centres
        # exactly on box edges, and whether a column sees the box it is standing
        # on then comes down to the last bit of a float. That produced a stoop
        # with a hole in the middle of it.
        self.min_x = math.floor(self.min_x / cell) * cell
        self.min_y = math.floor(self.min_y / cell) * cell

        # Two indices, because the two questions have different reach.
        #
        # _column: which boxes are directly under this column's centre. Answers
        #          "what could I stand on here".
        # _fat:    which boxes come within one character radius of this column.
        #          Answers "would a character standing here be inside something".
        #
        # Dilating the boxes by the radius once, at index time, is what makes
        # this tractable. Scanning a neighbourhood per query instead turned a
        # 12 x 12 m building into tens of seconds.
        self._column = {}
        self._fat = {}
        for i, b in enumerate(self.boxes):
            for ix in range(self._ci(b[0], self.min_x), self._ci(b[3], self.min_x) + 1):
                for iy in range(self._ci(b[1], self.min_y), self._ci(b[4], self.min_y) + 1):
                    self._column.setdefault((ix, iy), []).append(i)
            for ix in range(self._ci(b[0] - radius, self.min_x),
                            self._ci(b[3] + radius, self.min_x) + 1):
                for iy in range(self._ci(b[1] - radius, self.min_y),
                                self._ci(b[4] + radius, self.min_y) + 1):
                    self._fat.setdefault((ix, iy), []).append(i)

        # The world has an edge, and it must, because the terrain plane is
        # otherwise infinite: every empty column is standable, so a flood fill
        # started outdoors walks away forever and never terminates. Bounding the
        # grid to the scene plus a margin is not an optimisation, it is what
        # makes the question answerable at all.
        self.nx = int((self.max_x - self.min_x) / self.cell) + 1
        self.ny = int((self.max_y - self.min_y) / self.cell) + 1

        self._surface_cache = {}
        self._free_cache = {}
        self._nodes = None

    def in_bounds(self, ix, iy):
        return 0 <= ix < self.nx and 0 <= iy < self.ny

    # ------------------------------------------------------------- helpers
    def _ci(self, value, origin):
        return int((value - origin) // self.cell)

    def _centre(self, ix, iy):
        return (self.min_x + (ix + 0.5) * self.cell,
                self.min_y + (iy + 0.5) * self.cell)

    def _free_cell(self, ix, iy, z):
        """Is a character standing on surface z in this column clear of everything?"""
        key = (ix, iy, z)
        cached = self._free_cache.get(key)
        if cached is not None:
            return cached
        x, y = self._centre(ix, iy)
        r, h = self.radius, self.height
        lo_x, lo_y, hi_x, hi_y = x - r, y - r, x + r, y + r
        # Clearance is measured from one step height above the surface, not from
        # the surface itself. On any staircase the next riser is always within a
        # character's radius, so testing from the floor up reports every stair in
        # existence as impassable -- which is exactly what happened here first.
        # Real character controllers allow overlap inside the step-offset band
        # and so does this. Above that band the test is strict.
        bottom = z + self.step_up
        top = z + h
        result = True
        for i in self._fat.get((ix, iy), ()):
            b = self.boxes[i]
            if b[0] >= hi_x - 1e-9 or b[3] <= lo_x + 1e-9:
                continue
            if b[1] >= hi_y - 1e-9 or b[4] <= lo_y + 1e-9:
                continue
            if b[2] >= top - 1e-9 or b[5] <= bottom + 1e-9:
                continue
            result = False
            break
        self._free_cache[key] = result
        return result

    def surfaces(self, ix, iy):
        """Standable heights in one column, low to high."""
        if not self.in_bounds(ix, iy):
            return ()
        key = (ix, iy)
        cached = self._surface_cache.get(key)
        if cached is not None:
            return cached
        x, y = self._centre(ix, iy)
        heights = {self.ground_z}
        for i in self._column.get(key, ()):
            b = self.boxes[i]
            # Tolerance because a cell centre can still land on an edge after
            # alignment, when an asset's own dimensions are off the lattice.
            if (b[0] - EDGE_TOLERANCE <= x <= b[3] + EDGE_TOLERANCE
                    and b[1] - EDGE_TOLERANCE <= y <= b[4] + EDGE_TOLERANCE):
                heights.add(q(b[5]))
        out = tuple(sorted(z for z in heights if self._free_cell(ix, iy, z)))
        self._surface_cache[key] = out
        return out

    # -------------------------------------------------------------- graph
    def nodes(self):
        if self._nodes is None:
            nodes = set()
            for ix in range(self.nx):
                for iy in range(self.ny):
                    for z in self.surfaces(ix, iy):
                        nodes.add((ix, iy, z))
            self._nodes = nodes
        return self._nodes

    def neighbours(self, node):
        ix, iy, z = node
        out = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            jx, jy = ix + dx, iy + dy
            if not self.in_bounds(jx, jy):
                continue
            for nz in self.surfaces(jx, jy):
                rise = nz - z
                if rise > self.step_up + 1e-9 or -rise > self.step_down + 1e-9:
                    continue
                # the character has to fit at the higher of the two surfaces,
                # in both columns, or it clips the nosing on the way
                higher = max(z, nz)
                if self._free_cell(ix, iy, higher) and self._free_cell(jx, jy, higher):
                    out.append((jx, jy, nz))
        return out

    def locate(self, point, tolerance=0.35):
        """The standable node nearest a world point, or None."""
        ix, iy = self._ci(point[0], self.min_x), self._ci(point[1], self.min_y)
        best, best_d = None, None
        for dx in (0, -1, 1, -2, 2):
            for dy in (0, -1, 1, -2, 2):
                if not self.in_bounds(ix + dx, iy + dy):
                    continue
                for z in self.surfaces(ix + dx, iy + dy):
                    d = abs(z - point[2])
                    if d <= tolerance and (best_d is None or d < best_d):
                        best, best_d = (ix + dx, iy + dy, z), d
        return best

    def flood(self, start):
        """Every node reachable from a start node."""
        seen = {start}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for n in self.neighbours(node):
                if n not in seen:
                    seen.add(n)
                    queue.append(n)
        return seen

    def route_exists(self, a, b, tolerance=0.35):
        """Can a character walk from world point ``a`` to world point ``b``?

        Returns ``(ok, detail)`` where detail explains a failure well enough to
        act on -- which is the difference between a useful answer and 'no'.
        """
        start = self.locate(a, tolerance)
        if start is None:
            return False, {"reason": "no_standable_surface_at_start", "point": list(a)}
        goal = self.locate(b, tolerance)
        if goal is None:
            return False, {"reason": "no_standable_surface_at_goal", "point": list(b)}
        if start == goal:
            return True, {"reason": "same_surface", "nodes_explored": 1}

        seen = {start}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for n in self.neighbours(node):
                if n in seen:
                    continue
                if n == goal:
                    return True, {"reason": "route_found", "nodes_explored": len(seen)}
                seen.add(n)
                queue.append(n)
        reached_heights = sorted({round(n[2], 2) for n in seen})
        return False, {
            "reason": "no_route",
            "nodes_explored": len(seen),
            "start_height": round(start[2], 3),
            "goal_height": round(goal[2], 3),
            "heights_reached": reached_heights[:12],
            "hint": ("the goal is on a level the flood never reached; check that "
                     "a stair exists, that its landing meets the floor above, and "
                     "that the floor above has an opening over the flight"),
        }

    def standable_area(self, nodes=None):
        nodes = self.nodes() if nodes is None else nodes
        return len(nodes) * self.cell * self.cell


def grid_from_instances(instances, **kw):
    """Build a NavGrid from validator Instance objects."""
    boxes = []
    for inst in instances:
        boxes.extend(inst.occupancy)
    return NavGrid(boxes, **kw)
