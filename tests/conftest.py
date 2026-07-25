"""SPDX-License-Identifier: 0BSD"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "kits", "shell_v1"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "tests", "fixtures"))


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def catalog():
    import config
    import parts
    from tessera.catalog import build_catalog
    return build_catalog(parts.PARTS, os.path.join(ROOT, "build"),
                         config.KIT_ID, config.KIT_VERSION, config,
                         write_meshes=False)


@pytest.fixture(scope="session")
def layout(catalog):
    sys.path.insert(0, os.path.join(ROOT, "examples", "workshop_shell"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "workshop_build", os.path.join(ROOT, "examples", "workshop_shell", "build.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    b = module.build(catalog)
    lay = b.to_layout()
    lay["discovered_connections"] = b.discovered_connections
    return lay
