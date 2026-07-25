// Build a three.js scene from a Tessera catalog and layout.
// SPDX-License-Identifier: 0BSD
//
// Import three.js yourself and pass it in, so this module never pins a version
// and never ends up bundled twice:
//
//   import * as THREE from 'three';
//   import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
//   import { TesseraScene } from '@tessera/three/three';
//
//   const scene = new TesseraScene({ THREE, GLTFLoader, baseUrl: './build/' });
//   await scene.loadCatalog('./build/catalog.json');
//   const group = await scene.buildLayout(layout);
//
// Coordinate handling is the part people get wrong, so it is done once here:
// the shipped GLB files are already converted to glTF's Y-up right-handed
// space, but layout transforms are in canonical Z-up Tessera space. This class
// converts each instance transform on the way in. Do not convert twice.

const DEG = Math.PI / 180;

export class TesseraScene {
  constructor({ THREE, GLTFLoader, baseUrl = './' }) {
    if (!THREE) throw new Error('pass your three.js namespace as { THREE }');
    this.THREE = THREE;
    this.loader = GLTFLoader ? new GLTFLoader() : null;
    this.baseUrl = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;
    this.catalog = null;
    this.index = new Map();
    this.cache = new Map();
  }

  async loadCatalog(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`cannot read catalog at ${url}`);
    this.catalog = await response.json();
    if (this.catalog.schema !== 'tessera.catalog/1') {
      throw new Error(`unsupported catalog schema ${this.catalog.schema}`);
    }
    for (const asset of this.catalog.assets) this.index.set(asset.id, asset);
    return this.catalog;
  }

  async asset(id) {
    if (this.cache.has(id)) return this.cache.get(id);
    const record = this.index.get(id);
    if (!record) {
      throw new Error(`asset ${id} is not in this catalog; try one of `
        + `${[...this.index.keys()].slice(0, 4).join(', ')} ...`);
    }
    if (!this.loader) throw new Error('pass { GLTFLoader } to load meshes');
    const gltf = await this.loader.loadAsync(this.baseUrl + record.files.glb);
    const proto = gltf.scene.children[0] ?? gltf.scene;
    this.cache.set(id, proto);
    return proto;
  }

  /**
   * Canonical Tessera space is Z-up right-handed; three.js is Y-up.
   * position (x, y, z) -> (x, z, -y); yaw about Z -> rotation about Y.
   */
  applyTransform(object3d, instance) {
    const [x, y, z] = instance.position;
    object3d.position.set(x, z, -y);
    const [yaw, pitch, roll] = instance.rotation_degrees ?? [0, 0, 0];
    object3d.rotation.set(roll * DEG, yaw * DEG, pitch * DEG, 'YXZ');
    const s = instance.scale ?? 1;
    object3d.scale.setScalar(s);
    return object3d;
  }

  async buildLayout(layout, { onInstance } = {}) {
    const group = new this.THREE.Group();
    group.name = layout.name ?? 'tessera-layout';
    for (const instance of layout.instances) {
      const proto = await this.asset(instance.asset);
      const node = proto.clone(true);
      node.name = instance.id;
      node.userData.tessera = {
        asset: instance.asset,
        record: this.index.get(instance.asset),
        instance,
      };
      this.applyTransform(node, instance);
      group.add(node);
      if (onInstance) onInstance(node, instance);
    }
    return group;
  }

  /** Collision hulls as wireframes. Useful for proving a doorway survived. */
  collisionHelper(layout, { color = 0x40e0d0 } = {}) {
    const { THREE } = this;
    const group = new THREE.Group();
    group.name = 'tessera-collision';
    const material = new THREE.LineBasicMaterial({ color });
    for (const instance of layout.instances) {
      const record = this.index.get(instance.asset);
      if (!record) continue;
      for (const hull of record.collision.hulls) {
        const size = [hull[3] - hull[0], hull[4] - hull[1], hull[5] - hull[2]];
        const centre = [(hull[0] + hull[3]) / 2, (hull[1] + hull[4]) / 2,
                        (hull[2] + hull[5]) / 2];
        const box = new THREE.BoxGeometry(size[0], size[2], size[1]);
        const lines = new THREE.LineSegments(new THREE.EdgesGeometry(box), material);
        lines.position.set(centre[0], centre[2], -centre[1]);
        const holder = new THREE.Group();
        this.applyTransform(holder, instance);
        holder.add(lines);
        group.add(holder);
      }
    }
    return group;
  }

  /** Aperture volumes as translucent boxes: "here is where you can walk". */
  apertureHelper(layout, { color = 0x66ff99, opacity = 0.25 } = {}) {
    const { THREE } = this;
    const group = new THREE.Group();
    group.name = 'tessera-apertures';
    const material = new THREE.MeshBasicMaterial({
      color, transparent: true, opacity, depthWrite: false,
    });
    for (const instance of layout.instances) {
      const record = this.index.get(instance.asset);
      for (const ap of record?.apertures ?? []) {
        if (!ap.traversable) continue;
        const size = [ap.bounds.max[0] - ap.bounds.min[0],
                      ap.bounds.max[1] - ap.bounds.min[1],
                      ap.bounds.max[2] - ap.bounds.min[2]];
        const centre = [(ap.bounds.min[0] + ap.bounds.max[0]) / 2,
                        (ap.bounds.min[1] + ap.bounds.max[1]) / 2,
                        (ap.bounds.min[2] + ap.bounds.max[2]) / 2];
        const mesh = new THREE.Mesh(
          new THREE.BoxGeometry(size[0], size[2], size[1]), material);
        mesh.position.set(centre[0], centre[2], -centre[1]);
        const holder = new THREE.Group();
        this.applyTransform(holder, instance);
        holder.add(mesh);
        group.add(holder);
      }
    }
    return group;
  }
}

export { validateLayout, solveGround, Transform } from './tessera-core.mjs';
