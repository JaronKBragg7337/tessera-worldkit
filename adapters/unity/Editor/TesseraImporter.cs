// Import a Tessera catalog and layout into Unity.
// SPDX-License-Identifier: 0BSD
//
// Menu: Tessera / Import Catalog...  and  Tessera / Build Layout...
//
// Coordinate handling
// -------------------
// Unity is Y-up and LEFT-handed with +Z forward; canonical Tessera space is
// Z-up and right-handed with +Y forward. The shipped GLB files are already in
// glTF's Y-up right-handed space, so a glTF importer places the mesh correctly
// on its own. What still needs converting is the LAYOUT transform, and that is
// done in exactly one place below, in ToUnity(). Do not convert twice.
//
// Collision
// ---------
// Unity's automatic MeshCollider on a doorway wall is fine, but convex mesh
// colliders are not, and physics-friendly convex hulls seal openings. Every
// Tessera asset carries its own convex decomposition -- derived from the carved
// solid, so apertures are holes in the collision too. BuildColliders() creates a
// compound BoxCollider set from that instead.

using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using UnityEditor;
using UnityEngine;

namespace Tessera
{
    [Serializable] public class Bounds3 { public float[] min; public float[] max; }
    [Serializable] public class Aperture { public string id; public string kind;
        public Bounds3 bounds; public bool traversable; public float clear_width;
        public float clear_height; }
    [Serializable] public class Collision { public string mode; public bool exact;
        public int hull_count; public float[][] hulls; public bool preserves_apertures; }
    [Serializable] public class Files { public string glb; public string obj; }
    [Serializable] public class Dimensions { public Bounds3 bounds; public float[] size; }
    [Serializable] public class Pivot { public string convention; public float base_offset_z; }
    [Serializable] public class Asset {
        public string id; public string name; public string semantic_role;
        public Dimensions dimensions; public Pivot pivot; public Files files;
        public Collision collision; public Aperture[] apertures;
    }
    [Serializable] public class Catalog {
        public string schema; public string fingerprint; public int asset_count;
        public Asset[] assets;
    }

    [Serializable] public class Instance {
        public string id; public string asset; public float[] position;
        public float[] rotation_degrees; public float scale;
    }
    [Serializable] public class Layout {
        public string schema; public string name; public int instance_count;
        public Instance[] instances;
    }

    public static class TesseraImporter
    {
        /// Canonical Tessera (x, y, z) metres -> Unity (x, z, y) metres.
        public static Vector3 ToUnity(float[] p) => new Vector3(p[0], p[2], p[1]);

        /// Canonical yaw about +Z -> Unity yaw about +Y, negated for handedness.
        public static Quaternion ToUnityRotation(float[] euler)
        {
            float yaw = euler != null && euler.Length > 0 ? euler[0] : 0f;
            return Quaternion.Euler(0f, -yaw, 0f);
        }

        [MenuItem("Tessera/Import Catalog...")]
        public static void ImportCatalog()
        {
            string path = EditorUtility.OpenFilePanel("catalog.json", "", "json");
            if (string.IsNullOrEmpty(path)) return;
            Catalog catalog = LoadCatalog(path);
            Debug.Log($"[Tessera] catalog {catalog.schema} with {catalog.assets.Length} assets. " +
                      "Import the GLB files under build/meshes with a glTF importer " +
                      "(glTFast or UnityGLTF), then run Tessera/Build Layout.");
        }

        public static Catalog LoadCatalog(string path)
        {
            // JsonUtility does not support nested containers such as the
            // float[][] used by collision.hulls. Json.NET is the Unity-maintained
            // package dependency declared by this adapter's package.json.
            Catalog catalog = JsonConvert.DeserializeObject<Catalog>(
                File.ReadAllText(path));
            if (catalog == null)
                throw new Exception($"could not parse catalog {path}");
            if (catalog.schema != "tessera.catalog/1")
                throw new Exception($"unsupported catalog schema {catalog.schema}");
            return catalog;
        }

        public static Layout LoadLayout(string path)
        {
            Layout layout = JsonConvert.DeserializeObject<Layout>(
                File.ReadAllText(path));
            if (layout == null)
                throw new Exception($"could not parse layout {path}");
            if (layout.schema != "tessera.layout/1")
                throw new Exception($"unsupported layout schema {layout.schema}");
            return layout;
        }

        [MenuItem("Tessera/Build Layout...")]
        public static void BuildLayoutMenu()
        {
            string catalogPath = EditorUtility.OpenFilePanel("catalog.json", "", "json");
            if (string.IsNullOrEmpty(catalogPath)) return;
            string layoutPath = EditorUtility.OpenFilePanel("layout.json", "", "json");
            if (string.IsNullOrEmpty(layoutPath)) return;
            BuildLayout(catalogPath, layoutPath);
        }

        /// Instantiate a layout. Prefabs are looked up by asset short name under
        /// Assets/Tessera/, which is where a glTF importer puts them by default.
        public static GameObject BuildLayout(string catalogPath, string layoutPath,
            string prefabRoot = "Assets/Tessera")
        {
            Catalog catalog = LoadCatalog(catalogPath);
            Layout layout = LoadLayout(layoutPath);

            var index = new Dictionary<string, Asset>();
            foreach (Asset a in catalog.assets) index[a.id] = a;

            var root = new GameObject(layout.name ?? "TesseraLayout");
            int missing = 0;
            foreach (Instance inst in layout.instances)
            {
                if (!index.TryGetValue(inst.asset, out Asset record)) { missing++; continue; }
                string shortName = record.id.Substring(record.id.LastIndexOf('/') + 1);
                string prefabPath = $"{prefabRoot}/{shortName}.prefab";
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);

                GameObject node = prefab != null
                    ? (GameObject)PrefabUtility.InstantiatePrefab(prefab)
                    : new GameObject(inst.id);
                if (prefab == null) missing++;

                node.name = inst.id;
                node.transform.SetParent(root.transform, false);
                node.transform.localPosition = ToUnity(inst.position);
                node.transform.localRotation = ToUnityRotation(inst.rotation_degrees);
                node.transform.localScale = Vector3.one * (inst.scale <= 0 ? 1f : inst.scale);

                BuildColliders(node, record);
                var marker = node.AddComponent<TesseraInstance>();
                marker.assetId = record.id;
                marker.semanticRole = record.semantic_role;
                marker.pivotConvention = record.pivot != null ? record.pivot.convention : "";
            }
            if (missing > 0)
                Debug.LogWarning($"[Tessera] {missing} instance(s) had no prefab under {prefabRoot}. " +
                                 "Import the GLB meshes first.");
            Undo.RegisterCreatedObjectUndo(root, "Build Tessera Layout");
            return root;
        }

        /// Compound BoxColliders straight from the contract's convex decomposition.
        /// This is what keeps doorways walkable; a convex MeshCollider would not.
        public static int BuildColliders(GameObject node, Asset record)
        {
            if (record.collision == null || record.collision.hulls == null) return 0;
            foreach (Collider existing in node.GetComponentsInChildren<Collider>())
                UnityEngine.Object.DestroyImmediate(existing);

            var holder = new GameObject("Collision");
            holder.transform.SetParent(node.transform, false);
            int made = 0;
            foreach (float[] h in record.collision.hulls)
            {
                var box = holder.AddComponent<BoxCollider>();
                // canonical (x, y, z) -> Unity (x, z, y) for both centre and size
                box.center = new Vector3((h[0] + h[3]) * 0.5f, (h[2] + h[5]) * 0.5f,
                                         (h[1] + h[4]) * 0.5f);
                box.size = new Vector3(h[3] - h[0], h[5] - h[2], h[4] - h[1]);
                made++;
            }
            return made;
        }
    }

    /// Keeps the contract reachable at runtime, so gameplay code can ask what a
    /// thing is instead of parsing its name.
    public class TesseraInstance : MonoBehaviour
    {
        public string assetId;
        public string semanticRole;
        public string pivotConvention;
    }
}
