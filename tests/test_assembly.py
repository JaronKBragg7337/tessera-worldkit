"""The vertical slice: assembled from metadata, correct first time.
SPDX-License-Identifier: 0BSD"""
import pytest

from tessera.assemble import AssemblyError, Builder
from tessera.validate import validate_layout


def test_everything_is_solved_not_hand_placed(layout):
    assert layout["placement_method"]["explicit"] == 0, \
        "the demonstration must not hand-place anything"
    assert layout["placement_method"]["solved_from_contract"] == layout["instance_count"]


def test_scene_is_substantial(layout):
    assert layout["instance_count"] >= 35
    assert len(layout["assets_used"]) == 12, "the slice must exercise every asset"


def test_seams_are_discovered_from_the_contract(layout):
    assert layout["discovered_connections"] >= 30


def test_manual_placement_corrections_required_is_zero(catalog, layout):
    """The headline metric. Errors here are corrections a human would have made."""
    c = validate_layout(layout, catalog)
    assert len(c.errors) == 0


def test_mate_refuses_an_impossible_join(catalog):
    b = Builder(catalog, "negative")
    floor = b.ground("tsr:shell/floor.slab.4m", 0, 0)
    with pytest.raises(AssemblyError) as exc:
        b.mate("tsr:shell/roof.ridge.4m", "seat", floor, "top")
    assert "cannot mate" in str(exc.value)


def test_ground_reports_a_missing_surface_clearly(catalog):
    b = Builder(catalog, "negative")
    crate = b.ground("tsr:shell/prop.crate.small", 0, 0)
    with pytest.raises(AssemblyError) as exc:
        b.ground("tsr:shell/roof.panel.4m", 0, 0, on=crate)
    assert "wall_top" in str(exc.value)


def test_unknown_asset_names_the_alternatives(catalog):
    b = Builder(catalog, "negative")
    with pytest.raises(AssemblyError) as exc:
        b.ground("tsr:shell/nope", 0, 0)
    assert "not in the catalog" in str(exc.value)


def test_doorway_is_actually_walkable(catalog, layout):
    """Mesh, collision and layout must all agree that a character fits through."""
    wall = next(a for a in catalog["assets"] if a["id"].endswith("wall.doorway.4m"))
    ap = wall["apertures"][0]
    assert ap["traversable"]
    assert ap["fits_capsule"]["admits_reference_character"]
    assert wall["collision"]["preserves_apertures"]
    c = validate_layout(layout, catalog)
    assert not [d for d in c.errors if d.code == "TSR_LAYOUT_APERTURE_BLOCKED"]
