"""The unverified Unity adapter must still be reproducible from a clone.
SPDX-License-Identifier: 0BSD
"""
import json
import os


def test_unity_adapter_is_a_local_upm_package(root):
    package_path = os.path.join(root, "adapters", "unity", "package.json")
    with open(package_path, encoding="utf-8") as fh:
        package = json.load(fh)
    assert package["name"] == "org.tessera.worldkit"
    assert package["dependencies"]["com.unity.nuget.newtonsoft-json"] == "3.2.1"

    manifest_path = os.path.join(
        root, "adapters", "unity", "verify-project", "Packages", "manifest.json")
    with open(manifest_path, encoding="utf-8") as fh:
        project = json.load(fh)
    local = project["dependencies"]["org.tessera.worldkit"]
    assert local == "file:../.."
    resolved = os.path.normpath(os.path.join(os.path.dirname(manifest_path), local[5:]))
    assert os.path.samefile(resolved, os.path.dirname(package_path))


def test_unity_verification_entry_point_and_importer_are_pinned(root):
    editor = os.path.join(root, "adapters", "unity", "Editor")
    with open(os.path.join(editor, "TesseraVerify.cs"), encoding="utf-8") as fh:
        verify = fh.read()
    for required in (
        "public static void Run()",
        "CheckBounds",
        "VerifyCollision",
        "VerifyLayout",
        "unity-verify-report.json",
        "EditorApplication.Exit(exitCode)",
    ):
        assert required in verify

    with open(os.path.join(editor, "TesseraImporter.cs"), encoding="utf-8") as fh:
        importer = fh.read()
    assert "JsonConvert.DeserializeObject" in importer
    assert "JsonUtility.FromJson" not in importer

    manifest_path = os.path.join(
        root, "adapters", "unity", "verify-project", "Packages", "manifest.json")
    with open(manifest_path, encoding="utf-8") as fh:
        project = json.load(fh)
    assert project["dependencies"]["org.khronos.unitygltf"].endswith(
        "#release/2.14.1")
