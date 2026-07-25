// Verify the Unity adapter against a real Unity Editor.
// SPDX-License-Identifier: 0BSD
//
// Unity.exe -batchmode -nographics -quit \
//   -projectPath adapters/unity/verify-project \
//   -executeMethod Tessera.TesseraVerify.Run \
//   -tesseraRoot /absolute/path/to/tessera-worldkit \
//   -logFile unity-verify.log

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json;
using UnityEditor;
using UnityEngine;

namespace Tessera
{
    public static class TesseraVerify
    {
        private const float Tolerance = 0.001f;
        private static readonly List<VerifyResult> Results = new List<VerifyResult>();
        private static string root;
        private static Catalog catalog;

        [Serializable]
        private class VerifyResult
        {
            public string name;
            public bool ok;
            public string detail;
        }

        [Serializable]
        private class VerifyReport
        {
            public string engine;
            public string fingerprint;
            public int checks;
            public int failed;
            public List<VerifyResult> results;
        }

        /// Batch-mode entry point. Always writes build/unity-verify-report.json
        /// and exits non-zero when any assertion fails.
        public static void Run()
        {
            int exitCode = 1;
            try
            {
                root = ResolveRoot();
                string catalogPath = Path.Combine(root, "build", "catalog.json");
                catalog = TesseraImporter.LoadCatalog(catalogPath);
                var prefabs = ImportAndVerifyAssets();
                VerifyLayout(prefabs, catalogPath);
                exitCode = Results.All(r => r.ok) ? 0 : 1;
            }
            catch (Exception exc)
            {
                Check("verification harness completed", false, exc.ToString());
            }
            finally
            {
                WriteReport();
                int failed = Results.Count(r => !r.ok);
                Debug.Log($"VERIFY TOTAL {Results.Count} checks, {failed} failed");
                if (failed == 0)
                    Debug.Log("VERIFY Unity adapter VERIFIED");
                EditorApplication.Exit(exitCode);
            }
        }

        private static Dictionary<string, GameObject> ImportAndVerifyAssets()
        {
            const string assetDirectory = "Assets/Tessera";
            if (AssetDatabase.IsValidFolder(assetDirectory))
                AssetDatabase.DeleteAsset(assetDirectory);
            AssetDatabase.CreateFolder("Assets", "Tessera");

            var prefabs = new Dictionary<string, GameObject>();
            foreach (Asset record in catalog.assets)
            {
                string shortName = ShortName(record.id);
                string source = Path.Combine(
                    root, "build", record.files.glb.Replace('/', Path.DirectorySeparatorChar));
                string glbAssetPath = $"{assetDirectory}/{shortName}.glb";
                string glbDiskPath = Path.Combine(
                    Application.dataPath, "Tessera", $"{shortName}.glb");

                File.Copy(source, glbDiskPath, true);
                AssetDatabase.ImportAsset(
                    glbAssetPath,
                    ImportAssetOptions.ForceSynchronousImport |
                    ImportAssetOptions.ForceUpdate);

                GameObject imported =
                    AssetDatabase.LoadAssetAtPath<GameObject>(glbAssetPath);
                Check($"{shortName} imports", imported != null,
                      imported == null ? glbAssetPath : "");
                if (imported == null)
                    continue;

                CheckBounds(record, imported);
                VerifyCollision(record, imported);

                GameObject instance = UnityEngine.Object.Instantiate(imported);
                instance.name = shortName;
                string prefabPath = $"{assetDirectory}/{shortName}.prefab";
                GameObject saved = PrefabUtility.SaveAsPrefabAsset(instance, prefabPath);
                UnityEngine.Object.DestroyImmediate(instance);
                if (saved != null)
                    prefabs[record.id] = saved;
            }
            AssetDatabase.SaveAssets();
            return prefabs;
        }

        private static void CheckBounds(Asset record, GameObject imported)
        {
            string shortName = ShortName(record.id);
            GameObject instance = UnityEngine.Object.Instantiate(imported);
            instance.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            instance.transform.localScale = Vector3.one;
            Renderer[] renderers = instance.GetComponentsInChildren<Renderer>(true);

            bool hasBounds = renderers.Length > 0;
            Bounds measured = hasBounds ? renderers[0].bounds : new Bounds();
            for (int i = 1; i < renderers.Length; i++)
                measured.Encapsulate(renderers[i].bounds);

            Vector3 a = TesseraImporter.ToUnity(record.dimensions.bounds.min);
            Vector3 b = TesseraImporter.ToUnity(record.dimensions.bounds.max);
            Vector3 expectedMin = Vector3.Min(a, b);
            Vector3 expectedMax = Vector3.Max(a, b);
            float worst = hasBounds
                ? MaxAxisError(measured.min, measured.max, expectedMin, expectedMax)
                : float.PositiveInfinity;

            Check($"{shortName} bounds match the contract",
                  hasBounds && worst <= Tolerance,
                  hasBounds ? $"worst axis error {worst:F6} m" : "no Renderer found");
            UnityEngine.Object.DestroyImmediate(instance);
        }

        private static void VerifyCollision(Asset record, GameObject imported)
        {
            string shortName = ShortName(record.id);
            GameObject instance = UnityEngine.Object.Instantiate(imported);
            int made = TesseraImporter.BuildColliders(instance, record);
            BoxCollider[] boxes = instance.GetComponentsInChildren<BoxCollider>(true);
            MeshCollider[] meshes = instance.GetComponentsInChildren<MeshCollider>(true);

            Check($"{shortName} collision rebuilt from the contract",
                  made == record.collision.hull_count &&
                  boxes.Length == record.collision.hull_count,
                  $"{boxes.Length} of {record.collision.hull_count} boxes");
            Check($"{shortName} has no MeshCollider", meshes.Length == 0,
                  $"{meshes.Length} MeshCollider(s)");

            bool exact = record.collision.hulls.All(hull =>
            {
                Vector3 expectedCenter = new Vector3(
                    (hull[0] + hull[3]) * 0.5f,
                    (hull[2] + hull[5]) * 0.5f,
                    (hull[1] + hull[4]) * 0.5f);
                Vector3 expectedSize = new Vector3(
                    hull[3] - hull[0],
                    hull[5] - hull[2],
                    hull[4] - hull[1]);
                return boxes.Any(box =>
                    Near(box.center, expectedCenter) &&
                    Near(box.size, expectedSize));
            });
            Check($"{shortName} box collision persisted", exact,
                  exact ? $"{boxes.Length} exact box(es)" : "box values differ");

            foreach (Aperture aperture in record.apertures ?? Array.Empty<Aperture>())
            {
                if (!aperture.traversable)
                    continue;
                Vector3 a = TesseraImporter.ToUnity(aperture.bounds.min);
                Vector3 b = TesseraImporter.ToUnity(aperture.bounds.max);
                Vector3 apertureMin = Vector3.Min(a, b);
                Vector3 apertureMax = Vector3.Max(a, b);
                int intruders = boxes.Count(box =>
                    Overlaps(box.center - box.size * 0.5f,
                             box.center + box.size * 0.5f,
                             apertureMin, apertureMax, Tolerance));
                Check($"{shortName} {aperture.id} collision is void",
                      intruders == 0, $"{intruders} box(es) in the aperture");
            }
            UnityEngine.Object.DestroyImmediate(instance);
        }

        private static void VerifyLayout(
            Dictionary<string, GameObject> prefabs, string catalogPath)
        {
            string layoutPath = Path.Combine(
                root, "examples", "safehouse_two_storey", "layout.json");
            Layout layout = TesseraImporter.LoadLayout(layoutPath);

            bool allPrefabs = catalog.assets.All(a => prefabs.ContainsKey(a.id));
            Check("every catalog asset became a prefab", allPrefabs,
                  $"{prefabs.Count} of {catalog.assets.Length}");

            GameObject layoutRoot = TesseraImporter.BuildLayout(
                catalogPath, layoutPath, "Assets/Tessera");
            TesseraInstance[] markers =
                layoutRoot.GetComponentsInChildren<TesseraInstance>(true);
            Check("layout spawns every instance",
                  markers.Length == layout.instances.Length,
                  $"{markers.Length} of {layout.instances.Length}");

            var byName = markers.ToDictionary(m => m.gameObject.name, m => m);
            float worstPosition = 0f;
            float worstRotation = 0f;
            float worstScale = 0f;
            bool allFound = true;
            foreach (Instance spec in layout.instances)
            {
                if (!byName.TryGetValue(spec.id, out TesseraInstance marker))
                {
                    allFound = false;
                    continue;
                }
                Transform transform = marker.transform;
                Vector3 expectedPosition = TesseraImporter.ToUnity(spec.position);
                Quaternion expectedRotation =
                    TesseraImporter.ToUnityRotation(spec.rotation_degrees);
                float expectedScale = spec.scale <= 0 ? 1f : spec.scale;
                worstPosition = Math.Max(
                    worstPosition,
                    MaxAbs(transform.localPosition - expectedPosition));
                worstRotation = Math.Max(
                    worstRotation,
                    Quaternion.Angle(transform.localRotation, expectedRotation));
                worstScale = Math.Max(
                    worstScale,
                    MaxAbs(transform.localScale - Vector3.one * expectedScale));
            }
            bool transformsMatch = allFound &&
                                   worstPosition <= Tolerance &&
                                   worstRotation <= 0.01f &&
                                   worstScale <= Tolerance;
            Check("instances land at the layout transforms", transformsMatch,
                  $"position {worstPosition:F6} m, rotation " +
                  $"{worstRotation:F6} deg, scale {worstScale:F6}");

            int expectedBoxes = layout.instances.Sum(spec =>
            {
                Asset record = catalog.assets.First(a => a.id == spec.asset);
                return record.collision.hull_count;
            });
            int actualBoxes =
                layoutRoot.GetComponentsInChildren<BoxCollider>(true).Length;
            int meshColliders =
                layoutRoot.GetComponentsInChildren<MeshCollider>(true).Length;
            Check("layout uses only contract collision",
                  actualBoxes == expectedBoxes && meshColliders == 0,
                  $"{actualBoxes} of {expectedBoxes} boxes; " +
                  $"{meshColliders} MeshCollider(s)");
            UnityEngine.Object.DestroyImmediate(layoutRoot);
        }

        private static bool Overlaps(
            Vector3 aMin, Vector3 aMax, Vector3 bMin, Vector3 bMax, float pad)
        {
            return aMin.x < bMax.x - pad && aMax.x > bMin.x + pad &&
                   aMin.y < bMax.y - pad && aMax.y > bMin.y + pad &&
                   aMin.z < bMax.z - pad && aMax.z > bMin.z + pad;
        }

        private static bool Near(Vector3 a, Vector3 b)
        {
            return MaxAbs(a - b) <= Tolerance;
        }

        private static float MaxAbs(Vector3 value)
        {
            return Math.Max(Math.Abs(value.x),
                            Math.Max(Math.Abs(value.y), Math.Abs(value.z)));
        }

        private static float MaxAxisError(
            Vector3 actualMin, Vector3 actualMax,
            Vector3 expectedMin, Vector3 expectedMax)
        {
            return Math.Max(
                MaxAbs(actualMin - expectedMin),
                MaxAbs(actualMax - expectedMax));
        }

        private static string ShortName(string assetId)
        {
            return assetId.Substring(assetId.LastIndexOf('/') + 1);
        }

        private static void Check(string name, bool ok, string detail = "")
        {
            Results.Add(new VerifyResult { name = name, ok = ok, detail = detail });
            string line = $"VERIFY {(ok ? "ok  " : "FAIL")} {name} {detail}";
            if (ok)
                Debug.Log(line);
            else
                Debug.LogError(line);
        }

        private static string ResolveRoot()
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "-tesseraRoot" && i + 1 < args.Length)
                    return RequireRoot(args[i + 1]);
                if (args[i].StartsWith("-tesseraRoot=", StringComparison.Ordinal))
                    return RequireRoot(args[i].Substring("-tesseraRoot=".Length));
            }

            string inferred = Path.GetFullPath(Path.Combine(
                Application.dataPath, "..", "..", "..", ".."));
            return RequireRoot(inferred);
        }

        private static string RequireRoot(string candidate)
        {
            string path = Path.GetFullPath(candidate);
            if (!File.Exists(Path.Combine(path, "build", "catalog.json")))
                throw new DirectoryNotFoundException(
                    $"Tessera root has no build/catalog.json: {path}");
            return path;
        }

        private static void WriteReport()
        {
            try
            {
                if (string.IsNullOrEmpty(root))
                    return;
                var report = new VerifyReport
                {
                    engine = Application.unityVersion,
                    fingerprint = catalog?.fingerprint,
                    checks = Results.Count,
                    failed = Results.Count(r => !r.ok),
                    results = Results,
                };
                string path = Path.Combine(root, "build", "unity-verify-report.json");
                string json = JsonConvert.SerializeObject(report, Formatting.Indented);
                File.WriteAllText(path, json + "\n", new UTF8Encoding(false));
                Debug.Log($"VERIFY report {path}");
            }
            catch (Exception exc)
            {
                Debug.LogError($"VERIFY could not write report: {exc}");
            }
        }
    }
}
