// toon3d: a small stylized 3D world for the mystery series — the recurring detective (นักสืบภู and his owl
// ฮูก), per-episode suspects, three reusable night sets (office, apartment, cafe), clue props and one
// camera move per shot. Everything is built from primitives with toon shading + ink outlines, so it renders
// on software WebGL. setup(job) builds the episode; draw(beat, frame) renders one frame as a JPEG data URL.
import * as THREE from "three";

let R, scene, cam, job, W, Hh, world;
const starts = [];

// ---------------------------------------------------------------- helpers
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ease = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3);
const lerp = (a, b, k) => a + (b - a) * k;
const V = (x, y, z) => new THREE.Vector3(x, y, z);

const GRAD = (() => {
  const t = new THREE.DataTexture(new Uint8Array([86, 160, 255]), 3, 1, THREE.RedFormat);
  t.minFilter = t.magFilter = THREE.NearestFilter;
  t.generateMipmaps = false;
  t.needsUpdate = true;
  return t;
})();
const MATS = new Map();
function toon(color, extra = {}) {
  const k = `${color}|${JSON.stringify(Object.keys(extra).length ? extra : "")}`;
  if (!MATS.has(k)) MATS.set(k, new THREE.MeshToonMaterial({ color, gradientMap: GRAD, ...extra }));
  return MATS.get(k);
}
const OUTLINES = new Map();
function outlineMat(thick) {
  if (!OUTLINES.has(thick)) {
    OUTLINES.set(thick, new THREE.ShaderMaterial({
      uniforms: { thick: { value: thick } },
      vertexShader: "uniform float thick; void main(){ vec3 p = position + normal * thick;"
        + " gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0); }",
      fragmentShader: "void main(){ gl_FragColor = vec4(0.06, 0.05, 0.08, 1.0); }",
      side: THREE.BackSide,
    }));
  }
  return OUTLINES.get(thick);
}
// a toon-shaded part with an ink outline
function part(geom, color, { outline = true, thick = 0.008, cast = true, mat = null } = {}) {
  const g = new THREE.Group();
  const m = new THREE.Mesh(geom, mat || toon(color));
  m.castShadow = cast;
  m.receiveShadow = true;
  g.add(m);
  if (outline) g.add(new THREE.Mesh(geom, outlineMat(thick)));
  return g;
}
const box = (w, h, d) => new THREE.BoxGeometry(w, h, d);
const rbox = (w, h, d, r = 0.02) => {               // a box with softly rounded edges (toon reads better)
  const g = new THREE.BoxGeometry(w, h, d, 4, 4, 4);
  const p = g.attributes.position, v = new THREE.Vector3();
  const hw = w / 2 - r, hh = h / 2 - r, hd = d / 2 - r;
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const c = V(clamp(v.x, -hw, hw), clamp(v.y, -hh, hh), clamp(v.z, -hd, hd));
    v.sub(c).normalize().multiplyScalar(r).add(c);
    p.setXYZ(i, v.x, v.y, v.z);
  }
  g.computeVertexNormals();
  return g;
};
const sph = (r, w = 18, h = 14) => new THREE.SphereGeometry(r, w, h);
const cyl = (rt, rb, h, s = 20) => new THREE.CylinderGeometry(rt, rb, h, s);
const cap = (r, l) => new THREE.CapsuleGeometry(r, l, 6, 14);
function at(obj, x, y, z, parent) { obj.position.set(x, y, z); if (parent) parent.add(obj); return obj; }

function canvasTex(w, h, paint, repeat = null) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  paint(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(...repeat); }
  return t;
}

// ---------------------------------------------------------------- characters
const SKINS = [0xe9b98f, 0xd9a47a, 0xc68b62, 0xb07650, 0xf0c8a0];

function character(spec) {
  const c = { spec, phase: spec.phase || 0 };
  const root = new THREE.Group();
  const body = at(new THREE.Group(), 0, 0, 0, root);
  const k = spec.height || 1;
  root.scale.setScalar(k);
  const skin = spec.skin, hipY = 0.6;

  c.legs = [-1, 1].map((s) => {
    const pv = at(new THREE.Group(), s * 0.1, hipY, 0, body);
    at(part(cap(0.075, 0.4), spec.bottom), 0, -0.26, 0, pv);
    const shoe = at(part(sph(0.085), spec.shoes || 0x2b2320), 0, -0.55, 0.045, pv);
    shoe.scale.set(1, 0.55, 1.5);
    return pv;
  });
  const torso = at(new THREE.Group(), 0, hipY, 0, body);
  const chest = at(part(cap(0.2, 0.3), spec.top), 0, 0.3, 0, torso);
  chest.scale.set(spec.build || 1, 1, 0.78);
  if (spec.coat) {
    const pts = [V(0.3, -0.4), V(0.27, -0.1), V(0.24, 0.2), V(0.25, 0.45), V(0.13, 0.6)].map((p) => new THREE.Vector2(p.x, p.y));
    const coat = at(part(new THREE.LatheGeometry(pts, 24), spec.coat), 0, 0, 0, torso);
    coat.scale.set(1, 1, 0.8);
    const belt = at(part(new THREE.TorusGeometry(0.245, 0.022, 6, 24), 0x5a3a22), 0, 0.12, 0, torso);
    belt.rotation.x = Math.PI / 2; belt.scale.set(1, 0.8, 1);
    for (const s of [-1, 1]) {                                     // lapels
      const l = at(part(box(0.09, 0.26, 0.02), spec.coatDark || spec.coat), s * 0.07, 0.45, 0.19, torso);
      l.rotation.z = s * 0.35;
    }
  }
  c.arms = [-1, 1].map((s) => {
    const pv = at(new THREE.Group(), s * 0.25, 0.52, 0, torso);
    at(part(cap(0.062, 0.34), spec.coat || spec.sleeve || spec.top), 0, -0.21, 0, pv);
    at(part(sph(0.066), skin), 0, -0.45, 0, pv);
    return pv;
  });
  if (spec.accessory === "apron") at(part(rbox(0.34, 0.5, 0.02, 0.008), 0xf4f1ea), 0, 0.12, 0.165, torso);
  if (spec.accessory === "tie") {
    at(part(box(0.05, 0.28, 0.015), spec.accent || 0xb3262e), 0, 0.33, 0.17, torso);
    at(part(box(0.2, 0.05, 0.03), spec.top), 0, 0.53, 0.12, torso);
  }
  if (spec.accessory === "scarf") {
    const sc = at(part(new THREE.TorusGeometry(0.12, 0.045, 8, 20), spec.accent || 0xc0392b), 0, 0.6, 0, torso);
    sc.rotation.x = Math.PI / 2;
  }
  if (spec.accessory === "bag") {
    at(part(rbox(0.22, 0.2, 0.08), spec.accent || 0x7a4a2a), -0.3, 0.0, 0.05, torso);
    const strap = at(part(box(0.03, 0.62, 0.03), spec.accent || 0x7a4a2a, { outline: false }), -0.05, 0.3, 0.15, torso);
    strap.rotation.z = -0.75;
  }

  const head = at(new THREE.Group(), 0, 0.8, 0, torso);
  const skull = at(part(sph(0.25, 24, 18), skin, { thick: 0.01 }), 0, 0.2, 0, head);
  skull.scale.set(1, 1.02, 0.95);
  for (const s of [-1, 1]) at(part(sph(0.055), skin), s * 0.245, 0.19, 0, head);
  at(part(sph(0.034), new THREE.Color(skin).multiplyScalar(0.9).getHex(), { outline: false }), 0, 0.13, 0.24, head);
  for (const s of [-1, 1]) at(new THREE.Mesh(sph(0.035, 10, 8), new THREE.MeshBasicMaterial({ color: 0xff7a7a, transparent: true, opacity: 0.35 })), s * 0.14, 0.12, 0.2, head).scale.set(1, 0.6, 0.4);
  c.eyes = [-1, 1].map((s) => {
    const e = at(new THREE.Group(), s * 0.088, 0.19, 0.212, head);
    const wht = at(part(sph(0.05), 0xffffff, { thick: 0.006 }), 0, 0, 0, e);
    wht.scale.set(1, 1.18, 0.55);
    at(new THREE.Mesh(sph(0.03), toon(0x1a1410)), 0, -0.004, 0.024, e);
    at(new THREE.Mesh(sph(0.009, 8, 6), new THREE.MeshBasicMaterial({ color: 0xffffff })), 0.011, 0.014, 0.05, e);
    return e;
  });
  c.brows = [-1, 1].map((s) => at(part(box(0.085, 0.02, 0.02), spec.hair, { outline: false }), s * 0.09, 0.275, 0.228, head));
  const mouth = at(new THREE.Group(), 0, 0.065, 0.222, head);
  c.mouth = {
    smile: at(new THREE.Mesh(new THREE.TorusGeometry(0.045, 0.01, 6, 14, Math.PI), toon(0x4a1e1e)), 0, 0.02, 0, mouth),
    flat: at(new THREE.Mesh(box(0.06, 0.012, 0.01), toon(0x4a1e1e)), 0, 0, 0, mouth),
    open: at(new THREE.Mesh(sph(0.032), toon(0x3a1214)), 0, 0, 0, mouth),
  };
  c.mouth.smile.rotation.z = Math.PI;
  c.mouth.open.scale.set(1, 1.3, 0.4);

  const hair = spec.hair;
  const style = spec.hairStyle || "short";
  if (style !== "bald") {                                          // a dome on top + the back of the head
    at(part(new THREE.SphereGeometry(0.262, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.36), hair, { thick: 0.008 }), 0, 0.2, -0.01, head);
    at(part(sph(0.252, 24, 16), hair, { thick: 0.008 }), 0, 0.22, -0.055, head);
  }
  if (style === "messy") {
    const r = rng(7);
    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * Math.PI * 2;
      at(part(sph(0.085 + r() * 0.03), hair, { thick: 0.007 }), Math.cos(a) * 0.16, 0.39 + r() * 0.05, Math.sin(a) * 0.14 - 0.02, head);
    }
    const curl = at(part(new THREE.TorusGeometry(0.035, 0.013, 6, 12, Math.PI * 1.5), hair), 0.04, 0.42, 0.22, head);
    curl.rotation.y = 0.3;
  } else if (style === "bun") {
    at(part(sph(0.1), hair), 0, 0.44, -0.1, head);
  } else if (style === "long") {
    at(part(rbox(0.5, 0.5, 0.16, 0.07), hair), 0, 0.05, -0.12, head);
  } else if (style === "spiky") {
    for (let i = 0; i < 7; i++) {
      const sp = at(part(new THREE.ConeGeometry(0.06, 0.16, 8), hair), (i - 3) * 0.06, 0.45, -0.02 + Math.abs(i - 3) * -0.02, head);
      sp.rotation.z = (i - 3) * -0.18;
    }
  }
  if (spec.accessory === "cap") {
    at(part(cyl(0.255, 0.265, 0.12, 24), spec.accent || 0x24324f), 0, 0.4, 0, head);
    at(part(cyl(0.2, 0.2, 0.02, 24), spec.accent || 0x24324f), 0, 0.35, 0.18, head).scale.set(1, 1, 0.8);
  }
  if (spec.accessory === "chef") {
    at(part(cyl(0.2, 0.2, 0.18, 20), 0xfafafa), 0, 0.47, 0, head);
    at(part(sph(0.17), 0xfafafa), 0, 0.6, 0, head).scale.set(1.3, 0.8, 1.3);
  }
  if (spec.glasses) {
    for (const s of [-1, 1]) at(part(new THREE.TorusGeometry(0.062, 0.009, 8, 22), spec.glasses, { outline: false }), s * 0.088, 0.19, 0.25, head);
    at(part(box(0.05, 0.01, 0.01), spec.glasses, { outline: false }), 0, 0.2, 0.255, head);
  }
  if (spec.accessory === "earrings") for (const s of [-1, 1]) at(part(sph(0.022), 0xf2c94c), s * 0.25, 0.1, 0.02, head);

  if (spec.owl) {                                                   // ฮูก on the detective's left shoulder
    const owl = at(new THREE.Group(), 0.25, 0.62, -0.02, torso);
    at(part(sph(0.11), 0x8d8a96), 0, 0.06, 0, owl).scale.set(1, 1.15, 0.95);
    at(part(sph(0.07), 0xd8cfc0, { outline: false }), 0, 0.03, 0.06, owl).scale.set(1, 1.2, 0.6);
    const oh = at(new THREE.Group(), 0, 0.19, 0, owl);
    at(part(sph(0.1), 0x9a97a3), 0, 0, 0, oh).scale.set(1.1, 0.9, 1);
    c.owlEyes = [-1, 1].map((s) => {
      const e = at(new THREE.Group(), s * 0.045, 0.01, 0.08, oh);
      at(part(sph(0.038), 0xf2b134, { thick: 0.005 }), 0, 0, 0, e).scale.set(1, 1, 0.5);
      at(new THREE.Mesh(sph(0.018), toon(0x111111)), 0, 0, 0.018, e);
      return e;
    });
    at(part(new THREE.ConeGeometry(0.018, 0.04, 6), 0xe08a2c, { outline: false }), 0, -0.035, 0.1, oh).rotation.x = Math.PI;
    for (const s of [-1, 1]) at(part(new THREE.ConeGeometry(0.025, 0.07, 6), 0x7c7986), s * 0.07, 0.08, 0, oh).rotation.z = s * -0.4;
    c.owl = owl; c.owlHead = oh;
  }
  Object.assign(c, { root, body, torso, head });
  return c;
}

// emotion + action → pose for this frame
function pose(c, t, act = "idle", emo = "neutral", look = 0) {
  const T = t + c.phase;
  c.torso.scale.y = 1 + 0.012 * Math.sin(T * 2.3);
  c.body.position.y = 0;
  c.torso.rotation.set(0, 0, 0);
  c.head.rotation.set(0, look, 0);
  for (const l of c.legs) l.rotation.set(0, 0, 0);
  for (const [i, a] of c.arms.entries()) a.rotation.set(0, 0, (i ? 1 : -1) * 0.08);
  const blink = (T % 3.4) < 0.11 ? 0.12 : 1;
  for (const e of c.eyes) e.scale.y = blink;

  if (act === "walk") {
    const s = Math.sin(T * 7);
    c.legs[0].rotation.x = s * 0.5; c.legs[1].rotation.x = -s * 0.5;
    c.arms[0].rotation.x = -s * 0.4; c.arms[1].rotation.x = s * 0.4;
    c.body.position.y = Math.abs(Math.cos(T * 7)) * 0.03;
  } else if (act === "point") {
    c.arms[0].rotation.set(-1.45, 0, -0.25);
    c.torso.rotation.y = 0.12;
  } else if (act === "think") {
    c.arms[0].rotation.set(-2.25, 0, 0.75);
    c.arms[1].rotation.set(-0.9, 0, -0.9);
    c.head.rotation.z = 0.1 + 0.03 * Math.sin(T);
  } else if (act === "inspect") {                                  // leaning in with the pen-light
    c.torso.rotation.x = 0.28;
    c.arms[0].rotation.set(-1.2, 0, -0.1);
    c.head.rotation.x = 0.25;
  } else if (act === "nervous") {
    c.head.rotation.y = look + Math.sin(T * 2.6) * 0.35 * (Math.sin(T * 0.7) > 0 ? 1 : 0.2);
    c.arms[0].rotation.set(-0.5, 0, 0.5 + Math.sin(T * 5) * 0.08);
    c.arms[1].rotation.set(-0.5, 0, -0.5 - Math.sin(T * 5) * 0.08);
    c.torso.rotation.z = Math.sin(T * 1.7) * 0.03;
  } else if (act === "shock") {
    c.arms[0].rotation.set(-0.35, 0, -1.05); c.arms[1].rotation.set(-0.35, 0, 1.05);
    c.torso.rotation.x = -0.12;
    c.head.rotation.x = -0.1;
  } else if (act === "wave") {
    c.arms[0].rotation.set(0, 0, -2.6 + Math.sin(T * 8) * 0.25);
  }
  const face = act === "shock" ? "shock" : emo;
  const m = c.mouth;
  m.smile.visible = face === "happy" || face === "neutral";
  m.smile.scale.setScalar(face === "happy" ? 1.15 : 0.7);
  m.open.visible = face === "shock" || face === "mindblown";
  m.flat.visible = !m.smile.visible && !m.open.visible;
  const [bl, br] = c.brows;
  bl.position.y = br.position.y = face === "shock" || face === "mindblown" ? 0.305 : 0.275;
  bl.rotation.z = br.rotation.z = 0;
  if (face === "worry") { bl.rotation.z = -0.35; br.rotation.z = 0.35; }
  if (face === "think") { br.position.y = 0.3; bl.rotation.z = 0.15; }
  if (face === "angry") { bl.rotation.z = 0.35; br.rotation.z = -0.35; }
  if (c.owl) {
    c.owlHead.rotation.y = Math.sin(T * 0.6) > 0.3 ? 0.7 : Math.sin(T * 0.6) < -0.5 ? -0.5 : 0;
    c.owlHead.rotation.z = Math.sin(T * 1.3) * 0.12;
    const ob = ((T + 1.3) % 2.7) < 0.12 ? 0.1 : 1;
    for (const e of c.owlEyes) e.scale.y = ob;
  }
}

// ---------------------------------------------------------------- props (clue objects)
function prop(icon) {
  const g = new THREE.Group();
  const gold = 0xe0b040;
  if (icon === "key" || icon === "car") {
    const ring = at(part(new THREE.TorusGeometry(0.045, 0.012, 8, 20), gold), 0, 0.012, 0, g); ring.rotation.x = Math.PI / 2;
    const shaft = at(part(cyl(0.01, 0.01, 0.14, 8), gold), 0.11, 0.012, 0, g); shaft.rotation.z = Math.PI / 2;
    at(part(box(0.025, 0.012, 0.03), gold), 0.16, 0.012, 0.02, g);
    if (icon === "car") at(part(rbox(0.07, 0.03, 0.11, 0.012), 0x1d1d22), -0.07, 0.017, 0.02, g);
  } else if (icon === "clock") {
    const face = at(part(cyl(0.11, 0.11, 0.05, 28), 0xc0392b), 0, 0.12, 0, g); face.rotation.x = Math.PI / 2;
    const dial = at(new THREE.Mesh(cyl(0.09, 0.09, 0.01, 28), toon(0xfdf6e3)), 0, 0.12, 0.026, g); dial.rotation.x = Math.PI / 2;
    g.userData.hands = [at(new THREE.Mesh(box(0.008, 0.07, 0.006), toon(0x111111)), 0, 0.12, 0.034, g),
                        at(new THREE.Mesh(box(0.006, 0.05, 0.006), toon(0x111111)), 0, 0.12, 0.036, g)];
    g.userData.hands.forEach((h) => { h.geometry.translate(0, 0.03, 0); });
    for (const s of [-1, 1]) at(part(sph(0.03), 0xc0392b), s * 0.07, 0.24, -0.01, g);
    for (const s of [-1, 1]) at(part(cyl(0.012, 0.012, 0.06, 8), 0x333333), s * 0.06, 0.03, 0, g).rotation.z = s * 0.5;
  } else if (icon === "cup") {
    at(part(cyl(0.05, 0.042, 0.11, 20), 0xf5efe6), 0, 0.055, 0, g);
    at(new THREE.Mesh(cyl(0.045, 0.045, 0.005, 20), toon(0x3b2416)), 0, 0.1, 0, g);
    const h = at(part(new THREE.TorusGeometry(0.03, 0.009, 6, 12, Math.PI), 0xf5efe6), 0.05, 0.06, 0, g); h.rotation.z = -Math.PI / 2;
    g.userData.steam = [0, 1, 2].map((i) => at(new THREE.Mesh(sph(0.008, 10, 8), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.25, depthWrite: false })), 0, 0.14 + i * 0.05, 0, g));
  } else if (icon === "phone") {
    at(part(rbox(0.08, 0.012, 0.16, 0.006), 0x15151a), 0, 0.006, 0, g);
    const scr = at(new THREE.Mesh(new THREE.PlaneGeometry(0.07, 0.145), new THREE.MeshBasicMaterial({ map: canvasTex(64, 128, (x, w, h) => {
      const gr = x.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#3b6fd8"); gr.addColorStop(1, "#7b3fc4");
      x.fillStyle = gr; x.fillRect(0, 0, w, h);
      x.fillStyle = "rgba(255,255,255,.85)"; for (let i = 0; i < 4; i++) x.fillRect(8, 30 + i * 22, w - 16, 12);
    }) })), 0, 0.0125, 0, g);
    scr.rotation.x = -Math.PI / 2;
    g.userData.screen = scr;
  } else if (icon === "letter") {
    at(part(box(0.2, 0.006, 0.13), 0xf3ead2), 0, 0.003, 0, g);
    const flap = at(new THREE.Mesh(new THREE.CircleGeometry(0.1, 3), toon(0xe6dabb)), 0, 0.007, -0.02, g);
    flap.rotation.set(-Math.PI / 2, 0, -Math.PI / 2); flap.scale.set(0.75, 1, 1);
    at(part(cyl(0.02, 0.02, 0.008, 14), 0xa61e22), 0, 0.01, 0.0, g);
  } else if (icon === "umbrella") {
    const u = at(new THREE.Group(), 0, 0, 0, g); u.rotation.z = 0.35;
    at(part(new THREE.ConeGeometry(0.05, 0.42, 10), 0x1f3b73), 0, 0.3, 0, u);
    at(part(cyl(0.008, 0.008, 0.14, 8), 0x333333), 0, 0.07, 0, u);
    at(part(new THREE.TorusGeometry(0.035, 0.009, 6, 12, Math.PI), 0x5a3a22), -0.035, 0.0, 0, u).rotation.z = Math.PI;
    const pud = at(new THREE.Mesh(new THREE.CircleGeometry(0.16, 24), new THREE.MeshBasicMaterial({ color: 0x6f8fbf, transparent: true, opacity: 0.45 })), 0.05, 0.002, 0, g);
    pud.rotation.x = -Math.PI / 2;
  } else if (icon === "ring") {
    at(part(rbox(0.12, 0.06, 0.12, 0.02), 0x7a1630), 0, 0.03, 0, g);
    const r = at(part(new THREE.TorusGeometry(0.03, 0.007, 8, 24), gold), 0, 0.09, 0, g);
    at(new THREE.Mesh(new THREE.OctahedronGeometry(0.018), new THREE.MeshToonMaterial({ color: 0x9ff3ff, emissive: 0x2a8fa8, gradientMap: GRAD })), 0, 0.125, 0, g);
    g.userData.spin = r;
  } else if (icon === "photo") {
    const f = at(part(box(0.16, 0.2, 0.015), 0x6b4423), 0, 0.1, 0, g); f.rotation.x = -0.25;
    const pic = at(new THREE.Mesh(new THREE.PlaneGeometry(0.13, 0.17), new THREE.MeshBasicMaterial({ map: canvasTex(64, 80, (x, w, h) => {
      x.fillStyle = "#e9d8b4"; x.fillRect(0, 0, w, h);
      x.fillStyle = "#6f4e37"; for (const cx of [22, 42]) { x.beginPath(); x.arc(cx, 34, 8, 0, 7); x.fill(); x.fillRect(cx - 9, 44, 18, 30); }
      x.strokeStyle = "#b5302a"; x.lineWidth = 3; x.beginPath(); x.moveTo(36, 20); x.lineTo(56, 70); x.stroke();
    }) })), 0, 0.1, 0.009, g);
    pic.rotation.x = -0.25;
  } else if (icon === "light") {
    at(part(cyl(0.06, 0.08, 0.03, 16), 0x2d2d33), 0, 0.015, 0, g);
    at(part(cyl(0.012, 0.012, 0.16, 8), 0x2d2d33), 0, 0.1, 0, g);
    const bulb = at(new THREE.Mesh(sph(0.045), new THREE.MeshBasicMaterial({ color: 0xffe2a0 })), 0, 0.2, 0, g);
    g.userData.bulb = bulb;
  } else if (icon === "footprint") {
    const mud = new THREE.MeshBasicMaterial({ color: 0x2a1c12, transparent: true, opacity: 0.85 });
    for (let i = 0; i < 3; i++) {                                   // muddy shoe prints: sole + heel
      const fp = at(new THREE.Group(), 0, 0.003, -i * 0.42, g);
      const sole = at(new THREE.Mesh(new THREE.CircleGeometry(0.06, 20), mud), 0, 0, -0.06, fp);
      sole.rotation.x = -Math.PI / 2; sole.scale.set(1, 1.5, 1);
      const heel = at(new THREE.Mesh(new THREE.CircleGeometry(0.045, 20), mud), 0, 0, 0.1, fp);
      heel.rotation.x = -Math.PI / 2;
      for (let k = 0; k < 4; k++) at(new THREE.Mesh(box(0.08, 0.002, 0.01), new THREE.MeshBasicMaterial({ color: 0x5a4030 })), 0, 0.002, -0.12 + k * 0.03, fp);
    }
  } else { // door: the room's own door is the clue; keep a small brass handle here for the close-up
    at(part(sph(0.035), gold), 0, 0.05, 0, g);
  }
  return g;
}

// ---------------------------------------------------------------- sets
const PALETTE = {
  office: { wall: "#3d4f63", wall2: "#33445a", floor: "#6b5644", trim: 0x22303f, lamp: 0xffc070 },
  apartment: { wall: "#6a4e5e", wall2: "#5b4252", floor: "#7a5a40", trim: 0x3a2632, lamp: 0xffb35c },
  cafe: { wall: "#5d4636", wall2: "#4f3a2c", floor: "#3f3330", trim: 0x2e2018, lamp: 0xffa548 },
};

function room(kind) {
  const P = PALETTE[kind];
  const g = new THREE.Group();
  const wallTex = canvasTex(256, 256, (x, w, h) => {
    x.fillStyle = P.wall; x.fillRect(0, 0, w, h);
    x.fillStyle = P.wall2; for (let i = 0; i < w; i += 32) x.fillRect(i, 0, 12, h);
  }, [6, 2]);
  const floorTex = canvasTex(256, 256, (x, w, h) => {
    const r = rng(3);
    for (let i = 0; i < 8; i++) {
      const c = new THREE.Color(P.floor).multiplyScalar(0.85 + r() * 0.3);
      x.fillStyle = `#${c.getHexString()}`; x.fillRect(0, i * 32, w, 32);
      x.fillStyle = "rgba(0,0,0,.35)"; x.fillRect(0, i * 32, w, 2); x.fillRect(r() * w, i * 32, 2, 32);
    }
  }, [4, 7]);
  const floor = at(new THREE.Mesh(new THREE.PlaneGeometry(9, 14), new THREE.MeshToonMaterial({ map: floorTex, gradientMap: GRAD })), 0, 0, 2.5, g);
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true;
  const wallMat = new THREE.MeshToonMaterial({ map: wallTex, gradientMap: GRAD });
  const wall = (w, h, x, y, z, ry = 0) => {
    const m = at(new THREE.Mesh(new THREE.PlaneGeometry(w, h), wallMat), x, y, z, g);
    m.rotation.y = ry; m.receiveShadow = true; return m;
  };
  // back wall with a window opening x∈[-2.4,-0.6], y∈[0.9,2.5]
  wall(1.1, 3.2, -3.05, 1.6, -4); wall(3.9, 3.2, 1.45, 1.6, -4);
  wall(1.8, 0.9, -1.5, 0.45, -4); wall(1.8, 0.7, -1.5, 2.85, -4);
  wall(14, 3.2, -3.6, 1.6, 2.5, Math.PI / 2); wall(14, 3.2, 3.6, 1.6, 2.5, -Math.PI / 2);
  const ceil = at(new THREE.Mesh(new THREE.PlaneGeometry(9, 14), toon(0x1c1a22)), 0, 3.2, 2.5, g); ceil.rotation.x = Math.PI / 2;
  at(part(box(7.2, 0.14, 0.05), P.trim, { outline: false }), 0, 0.07, -3.97, g);                 // skirting
  // window frame, sill and the city outside
  for (const [w, h, x, y] of [[1.9, 0.08, -1.5, 2.5], [1.9, 0.08, -1.5, 0.9], [0.08, 1.68, -2.44, 1.7], [0.08, 1.68, -0.56, 1.7],
    [0.05, 1.6, -1.5, 1.7], [1.8, 0.05, -1.5, 1.7]]) at(part(box(w, h, 0.1), P.trim), x, y, -3.97, g);
  at(part(box(2.0, 0.06, 0.25), P.trim), -1.5, 0.88, -3.88, g);
  const sky = at(new THREE.Mesh(new THREE.PlaneGeometry(9, 5), new THREE.MeshBasicMaterial({ map: canvasTex(1024, 512, (x, w, h) => {
    const gr = x.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#0b1030"); gr.addColorStop(0.6, "#2a2a5e"); gr.addColorStop(1, "#5a3a6e");
    x.fillStyle = gr; x.fillRect(0, 0, w, h);
    const r = rng(11);
    x.fillStyle = "#fff"; for (let i = 0; i < 90; i++) x.fillRect(r() * w, r() * h * 0.5, 1.5, 1.5);
    x.fillStyle = "#fff6d6"; x.beginPath(); x.arc(w * 0.42, h * 0.22, 34, 0, 7); x.fill();
    x.fillStyle = "rgba(255,246,214,.12)"; x.beginPath(); x.arc(w * 0.42, h * 0.22, 70, 0, 7); x.fill();
    for (let i = 0; i < 26; i++) {
      const bw = 30 + r() * 60, bh = 80 + r() * 260, bx = i * 40 - 20;
      x.fillStyle = "#0d0f1f"; x.fillRect(bx, h - bh, bw, bh);
      for (let yy = h - bh + 8; yy < h - 6; yy += 14) for (let xx = bx + 5; xx < bx + bw - 6; xx += 11)
        if (r() < 0.32) { x.fillStyle = r() < 0.8 ? "#ffc861" : "#8fd3ff"; x.fillRect(xx, yy, 5, 7); }
    }
  }) })), -1.2, 1.8, -5.2, g);
  sky.userData.sky = true;
  // rain beyond the glass
  const n = 260, pos = new Float32Array(n * 6), r = rng(5);
  for (let i = 0; i < n; i++) {
    const x = -2.6 + r() * 2.2, y = r() * 3.4, z = -4.15 - r() * 0.9;
    pos.set([x, y, z, x - 0.02, y - 0.18, z], i * 6);
  }
  const rg = new THREE.BufferGeometry(); rg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const rain = at(new THREE.LineSegments(rg, new THREE.LineBasicMaterial({ color: 0xa8c0ff, transparent: true, opacity: 0.45 })), 0, 0, 0, g);
  // door on the left wall
  const door = at(new THREE.Group(), -3.57, 0, 0.9, g);
  for (const [w, h, y, z] of [[0.1, 2.2, 1.1, -0.55], [0.1, 2.2, 1.1, 0.55], [0.1, 0.1, 2.2, 0]]) at(part(box(w, h, z ? 0.08 : 1.18), P.trim), 0, y, z, door);
  const leaf = at(new THREE.Group(), 0.02, 0, -0.5, door);
  at(part(rbox(0.05, 2.1, 1.0, 0.015), 0x6e4a2f), 0, 1.05, 0.5, leaf);
  at(part(sph(0.035), 0xe0b040), 0.06, 1.0, 0.88, leaf);
  leaf.rotation.y = -0.25;
  return { g, rain, door: V(-3.5, 1.0, 1.38), doorLeaf: leaf, lampColor: P.lamp };
}

function furnish(kind, R0) {
  const g = R0.g, lamps = [];
  const lamp = (x, y, z, inten = 6, dist = 6) => {
    const l = new THREE.PointLight(R0.lampColor, inten, dist, 1.6); l.position.set(x, y, z); g.add(l); lamps.push(l); return l;
  };
  let table;
  if (kind === "office") {
    const desk = at(new THREE.Group(), 1.5, 0, -1.6, g);
    at(part(rbox(1.8, 0.07, 0.85, 0.02), 0x5a3d28), 0, 0.76, 0, desk);
    for (const [x, z] of [[-0.82, -0.36], [0.82, -0.36], [-0.82, 0.36], [0.82, 0.36]]) at(part(box(0.06, 0.74, 0.06), 0x2c2c30), x, 0.37, z, desk);
    at(part(rbox(0.6, 0.38, 0.04, 0.015), 0x1b1d22), -0.3, 1.1, -0.25, desk);
    at(new THREE.Mesh(new THREE.PlaneGeometry(0.54, 0.32), new THREE.MeshBasicMaterial({ color: 0x4f86c9 })), -0.3, 1.1, -0.228, desk);
    at(part(box(0.08, 0.2, 0.06), 0x1b1d22), -0.3, 0.88, -0.25, desk);
    const dl = at(new THREE.Group(), 0.6, 0.8, -0.2, desk);
    at(part(cyl(0.01, 0.01, 0.4, 8), 0x2c2c30), 0, 0.2, 0, dl);
    const sh = at(part(new THREE.ConeGeometry(0.1, 0.14, 16, 1, true), 0x2f6b4f), 0.05, 0.4, 0.05, dl); sh.rotation.x = 0.5;
    lamp(2.1, 1.15, -1.7, 5, 5);
    const cab = at(new THREE.Group(), -2.9, 0, -3.4, g);
    at(part(rbox(0.6, 1.3, 0.55, 0.02), 0x6b7682), 0, 0.65, 0, cab);
    for (let i = 0; i < 3; i++) at(part(box(0.2, 0.03, 0.02), 0xc9cfd6, { outline: false }), 0, 0.3 + i * 0.4, 0.28, cab);
    const shelf = at(new THREE.Group(), 2.9, 0, -3.5, g);
    at(part(rbox(1.2, 2.2, 0.35, 0.02), 0x4a3424), 0, 1.1, 0, shelf);
    const r = rng(2), cols = [0xb03a2e, 0x2e6fb0, 0xd4a017, 0x3a8f5a, 0xe9e2d0];
    for (let s = 0; s < 4; s++) for (let i = 0; i < 9; i++) at(part(box(0.09, 0.3 + r() * 0.08, 0.25), cols[(i + s) % 5], { outline: false }), -0.45 + i * 0.11, 0.35 + s * 0.5, 0.06, shelf);
    const clock = at(part(cyl(0.22, 0.22, 0.04, 28), 0xf3ede0, { thick: 0.02 }), 0.4, 2.35, -3.96, g); clock.rotation.x = Math.PI / 2;
    for (const [w, h, rz] of [[0.02, 0.15, 0.6], [0.025, 0.1, -1.9]]) {
      const hand = at(new THREE.Mesh(box(w, h, 0.01), toon(0x1a1a1a)), 0.4, 2.35, -3.93, g);
      hand.geometry.translate(0, h / 2, 0); hand.rotation.z = rz;
    }
    const plant = at(new THREE.Group(), -0.2, 0, -3.5, g);
    at(part(cyl(0.16, 0.12, 0.35, 16), 0xc8643c), 0, 0.17, 0, plant);
    for (let i = 0; i < 6; i++) at(part(sph(0.17), 0x2f7d4a), Math.cos(i) * 0.12, 0.5 + (i % 3) * 0.12, Math.sin(i) * 0.12, plant);
    table = V(1.75, 0.8, -1.45);
  } else if (kind === "apartment") {
    const sofa = at(new THREE.Group(), -0.6, 0, -3.1, g);
    at(part(rbox(2.2, 0.42, 0.9, 0.1), 0x2f6f73), 0, 0.3, 0, sofa);
    at(part(rbox(2.2, 0.6, 0.25, 0.1), 0x2f6f73), 0, 0.7, -0.35, sofa);
    for (const s of [-1, 1]) at(part(rbox(0.25, 0.6, 0.9, 0.1), 0x2a6266), s * 1.1, 0.45, 0, sofa);
    for (const s of [-1, 1]) at(part(rbox(0.4, 0.35, 0.12, 0.06), 0xe0a03a), s * 0.6, 0.65, -0.18, sofa).rotation.z = s * 0.15;
    const rug = at(new THREE.Mesh(new THREE.CircleGeometry(1.4, 40), toon(0x8c3b3b)), 0.2, 0.004, -1.6, g); rug.rotation.x = -Math.PI / 2; rug.receiveShadow = true;
    const ct = at(new THREE.Group(), 0.2, 0, -1.9, g);
    at(part(rbox(1.0, 0.06, 0.55, 0.02), 0x5a3d28), 0, 0.42, 0, ct);
    for (const [x, z] of [[-0.42, -0.2], [0.42, -0.2], [-0.42, 0.2], [0.42, 0.2]]) at(part(cyl(0.025, 0.025, 0.4, 8), 0x3b281a), x, 0.2, z, ct);
    const st = at(new THREE.Group(), 1.75, 0, -1.4, g);
    at(part(cyl(0.3, 0.3, 0.05, 24), 0x6b4423), 0, 0.62, 0, st);
    at(part(cyl(0.04, 0.06, 0.6, 10), 0x3b281a), 0, 0.3, 0, st);
    const fl = at(new THREE.Group(), 2.6, 0, -3.2, g);
    at(part(cyl(0.02, 0.02, 1.6, 8), 0x2c2c30), 0, 0.8, 0, fl);
    at(part(cyl(0.18, 0.28, 0.3, 20, 1, true), 0xf0d9a8), 0, 1.65, 0, fl);
    lamp(2.6, 1.55, -3.0, 9, 7);
    const r = rng(4), cols = [0xd96c4a, 0x4a7fd9, 0xe8c547, 0x5fa86b];
    for (let i = 0; i < 3; i++) {
      const fr = at(part(box(0.5, 0.4, 0.03), 0x2a1d14), 1.0 + i * 0.65, 1.9 + (i % 2) * 0.15, -3.97, g);
      at(new THREE.Mesh(new THREE.PlaneGeometry(0.4, 0.3), toon(cols[(i + Math.floor(r() * 4)) % 4])), 0, 0, 0.02, fr);
    }
    table = V(1.75, 0.65, -1.4);
  } else { // cafe
    const counter = at(new THREE.Group(), 1.6, 0, -3.2, g);
    at(part(rbox(3.4, 1.05, 0.7, 0.03), 0x6b4423), 0, 0.52, 0, counter);
    at(part(rbox(3.5, 0.06, 0.8, 0.02), 0x2a2a2e), 0, 1.07, 0, counter);
    const mach = at(new THREE.Group(), 0.6, 1.1, -0.05, counter);
    at(part(rbox(0.6, 0.45, 0.4, 0.04), 0xb8bec6), 0, 0.23, 0, mach);
    for (const s of [-1, 1]) at(part(cyl(0.03, 0.03, 0.12, 10), 0x2a2a2e), s * 0.15, 0.02, 0.15, mach);
    for (let i = 0; i < 5; i++) at(part(cyl(0.04, 0.035, 0.08, 12), [0xf5efe6, 0xd96c4a, 0x4a7fd9][i % 3]), -1.4 + i * 0.18, 1.14, -0.15, counter);
    const board = at(part(box(1.6, 0.9, 0.04), 0x1f3b2f), 1.4, 2.2, -3.96, g);
    const r = rng(9);
    for (let i = 0; i < 6; i++) at(new THREE.Mesh(box(0.5 + r() * 0.6, 0.03, 0.01), new THREE.MeshBasicMaterial({ color: [0xf2e6c9, 0xf2b134, 0x9fd3c7][i % 3] })), -0.25 + r() * 0.2, 0.3 - i * 0.12, 0.03, board);
    for (const x of [-1.6, 0.0, 1.6]) {
      const pd = at(new THREE.Group(), x, 2.3, -1.4, g);
      at(part(cyl(0.006, 0.006, 0.9, 6), 0x111111, { outline: false }), 0, 0.45, 0, pd);
      at(part(new THREE.ConeGeometry(0.2, 0.22, 18, 1, true), 0xc98a2e), 0, 0, 0, pd);
      at(new THREE.Mesh(sph(0.06), new THREE.MeshBasicMaterial({ color: 0xffd28a })), 0, -0.08, 0, pd);
      lamp(x, 2.1, -1.4, 4, 4.5);
    }
    for (const [x, z] of [[1.6, -1.2], [-1.7, -2.0]]) {
      const tb = at(new THREE.Group(), x, 0, z, g);
      at(part(cyl(0.38, 0.38, 0.04, 28), 0x8a5a3a), 0, 0.74, 0, tb);
      at(part(cyl(0.035, 0.05, 0.72, 10), 0x2a2a2e), 0, 0.36, 0, tb);
      for (const s of [-1, 1]) {
        const ch = at(new THREE.Group(), s * 0.6, 0, 0, tb);
        at(part(rbox(0.38, 0.05, 0.38, 0.02), 0x7a3b2a), 0, 0.46, 0, ch);
        at(part(rbox(0.05, 0.45, 0.38, 0.02), 0x7a3b2a), s * 0.17, 0.7, 0, ch);
        for (const zz of [-0.15, 0.15]) at(part(cyl(0.015, 0.015, 0.45, 6), 0x2a2a2e, { outline: false }), 0, 0.22, zz, ch);
      }
    }
    table = V(1.6, 0.76, -1.2);
  }
  return { lamps, table };
}

// ---------------------------------------------------------------- episode
export function setup(j) {
  job = j; W = j.width; Hh = j.height;
  const canvas = document.getElementById("c");
  canvas.width = W; canvas.height = Hh;
  R = new THREE.WebGLRenderer({ canvas, antialias: j.antialias !== false, preserveDrawingBuffer: true });
  R.setPixelRatio(1);
  R.setSize(W, Hh, false);
  R.shadowMap.enabled = true;
  R.shadowMap.type = THREE.PCFShadowMap;
  R.toneMapping = THREE.ACESFilmicToneMapping;
  R.toneMappingExposure = 1.15;
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x07080f);
  scene.fog = new THREE.Fog(0x0b0d1a, 7, 16);
  cam = new THREE.PerspectiveCamera(42, W / Hh, 0.03, 40);

  const kind = PALETTE[j.set] ? j.set : "apartment";
  const R0 = room(kind);
  scene.add(R0.g);
  const F = furnish(kind, R0);
  const hemi = new THREE.HemisphereLight(0x8090d0, 0x2a1c26, 1.1);
  scene.add(hemi);
  const moon = new THREE.DirectionalLight(0xa9bcff, 1.6);
  moon.position.set(-2.5, 4.5, -6); moon.target.position.set(0.5, 0, 0);
  moon.castShadow = true; moon.shadow.mapSize.set(1024, 1024);
  Object.assign(moon.shadow.camera, { left: -5, right: 5, top: 5, bottom: -5, near: 1, far: 16 });
  moon.shadow.bias = -0.0015;
  scene.add(moon, moon.target);
  const key = new THREE.DirectionalLight(0xffd7a8, 0.9);             // soft fill from the camera side
  key.position.set(2, 3, 5); scene.add(key);
  const pen = new THREE.SpotLight(0xfff1c9, 0, 4, 0.22, 0.5, 1.2);   // the detective's pen-light
  pen.castShadow = false; scene.add(pen, pen.target);
  const beamMat = new THREE.MeshBasicMaterial({ color: 0xfff1c9, transparent: true, opacity: 0.08, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending });
  const beam = new THREE.Mesh(new THREE.ConeGeometry(0.16, 1, 20, 1, true), beamMat);
  beam.geometry.translate(0, -0.5, 0); beam.geometry.rotateX(-Math.PI / 2);
  scene.add(beam);
  const rim = new THREE.SpotLight(0xff3040, 0, 6, 0.5, 0.6, 1);       // red back-light on the culprit
  scene.add(rim, rim.target);

  const det = character({
    skin: 0xc68b62, hair: 0x15110f, hairStyle: "messy", top: 0x2f3036, bottom: 0x3a3a44, coat: 0xd9a52b,
    coatDark: 0xb8861c, glasses: 0x5a3a1e, owl: true, height: 1.0, phase: 0.3,
  });
  scene.add(det.root);
  const torch = at(part(cyl(0.012, 0.012, 0.12, 8), 0xc9a243), 0, -0.5, 0.04, det.arms[0]);
  torch.rotation.x = Math.PI / 2;

  const sus = (j.suspects || []).map((s, i) => {
    const c = character({ ...s, phase: 1.1 + i * 0.77 });
    scene.add(c.root);
    return c;
  });
  const props = j.beats.map((b) => (b.icon ? prop(b.icon) : null));
  props.forEach((p) => { if (p) { p.visible = false; scene.add(p); } });
  world = { R0, F, hemi, moon, key, pen, beam, rim, det, sus, props, lamps: F.lamps, kind };
  let s = 0;
  for (const b of j.beats) { starts.push(s); s += b.frames; }
  console.log(`setup ${kind}: ${sus.length} suspects, ${j.beats.length} shots, ${W}x${Hh}`);
}

function lookAt(pos, target, fov = 42) {
  cam.fov = fov; cam.updateProjectionMatrix();
  cam.position.copy(pos); cam.lookAt(target);
}
function place(c, x, z, ry = 0, visible = true) {
  c.root.position.set(x, 0, z); c.root.rotation.set(0, ry, 0); c.root.visible = visible;
}
function faceTo(c, x, z) { return Math.atan2(x - c.root.position.x, z - c.root.position.z); }
// x positions that line people up with evenly spaced name plates at this camera distance
function lineup(n, dist) {
  const vis = 2 * dist * Math.tan(THREE.MathUtils.degToRad(cam.fov / 2)) * (W / Hh);
  return [...Array(n)].map((_, k) => -vis / 2 + vis * (k + 1) / (n + 1));
}

export function draw(b, f) {
  const beat = job.beats[b];
  const n = Math.max(beat.frames - 1, 1);
  const p = f / n, t = (starts[b] + f) / job.fps;
  const { det, sus, pen, beam, rim, hemi, key, F, R0, props } = world;
  const tbl = F.table;
  pen.intensity = 0; beam.visible = false; rim.intensity = 0;
  hemi.intensity = 1.1; key.intensity = 0.9;
  props.forEach((q) => { if (q) q.visible = false; });
  for (const l of world.lamps) l.intensity = l.userData.base ?? (l.userData.base = l.intensity);
  const pr = props[b];
  const prPos = beat.icon === "footprint" ? V(tbl.x - 0.6, 0.0, tbl.z + 1.2) : beat.icon === "umbrella" ? V(tbl.x - 0.5, 0.0, tbl.z + 0.5)
    : beat.icon === "door" ? R0.door.clone() : tbl.clone();
  if (pr) { pr.position.copy(prPos); pr.visible = beat.icon !== "door"; pr.rotation.y = 0.4; }
  if (pr?.userData.hands) { pr.userData.hands[0].rotation.z = -t * 0.2; pr.userData.hands[1].rotation.z = -t * 0.02 - 1.2; }
  if (pr?.userData.steam) pr.userData.steam.forEach((s, i) => { const k = (t * 0.4 + i / 3) % 1; s.position.y = 0.12 + k * 0.18; s.material.opacity = 0.25 * (1 - k); s.scale.setScalar(1 + k); });
  if (pr?.userData.bulb) pr.userData.bulb.material.color.setHex(Math.sin(t * 23) > 0.6 || Math.sin(t * 7) > 0.85 ? 0x55452a : 0xffe2a0);
  if (pr?.userData.spin) pr.userData.spin.rotation.set(Math.PI / 2 - 0.4, 0, t * 0.6);
  const pos = R0.rain.geometry.attributes.position;          // rain falls
  for (let i = 0; i < pos.count; i += 2) {
    const y0 = (pos.array[i * 3 + 1] - 0.06 + 3.4) % 3.4;
    pos.array[i * 3 + 1] = y0; pos.array[i * 3 + 4] = y0 - 0.18;
  }
  pos.needsUpdate = true;
  const n_s = sus.length;
  const pen_on = (from, to) => {
    pen.intensity = 9; pen.position.copy(from); pen.target.position.copy(to);
    beam.visible = true; beam.position.copy(from); beam.lookAt(to); beam.scale.set(1, 1, from.distanceTo(to));
  };
  const emo = beat.emotion || "neutral";

  if (beat.shot === "hook") {
    // dark room, a lightning flash, the pen-light finds the clue, the camera rushes in
    hemi.intensity = 0.55; key.intensity = 0.2;
    for (const l of world.lamps) l.intensity *= 0.35;
    const flash = f < 3 ? 2.6 : f < 6 ? 0.6 : f < 8 ? 1.8 : 0;
    hemi.intensity += flash;
    sus.forEach((c, i) => { place(c, -1.0 + i * 0.7, -3.0, 0, true); pose(c, t, "idle", "neutral"); });
    place(det, tbl.x - 1.6, tbl.z + 1.6, 0, false);
    const target = prPos.clone().add(V(0, 0.06, 0));
    if (pr) pr.visible = beat.icon !== "door";
    const sweep = easeOut(p * 1.6);
    pen_on(V(tbl.x - 1.2, 1.4, tbl.z + 1.3), target.clone().add(V((1 - sweep) * -1.2, 0, (1 - sweep) * 0.6)));
    const k = easeOut(p * 1.3);
    const far = beat.icon === "footprint" ? 1.5 : 1.3;
    lookAt(V(lerp(tbl.x - 1.8, target.x - 0.35, k), lerp(2.6, target.y + 0.75, k), lerp(tbl.z + 4.2, target.z + far, k)), target, lerp(48, 38, k));
  } else if (beat.shot === "arrive") {
    // the detective walks in from the door; suspects wait across the room
    const k = ease(p * 1.15);
    const x = lerp(-3.1, -0.6, k), z = lerp(0.9, 0.3, k);
    place(det, x, z, Math.PI / 2 - 0.35 * k, true);
    pose(det, t, k < 0.98 ? "walk" : "idle", emo, 0.2);
    const xs = [1.6, 0.4, 2.4, -0.8];
    sus.forEach((c, i) => { place(c, xs[i % 4] * 0.9, -2.2 - (i % 2) * 0.5, 0, true); c.root.rotation.y = faceTo(c, x, z) * 0.6; pose(c, t, "idle", "neutral"); });
    lookAt(V(lerp(0.6, 1.0, p), 1.45, 3.4), V(x * 0.6, 1.1, -0.4), 44);
  } else if (beat.shot === "think") {
    // medium close-up: the detective thinks it over, the owl looks around
    place(det, 0.0, 0.0, 0.15, true);
    pose(det, t, emo === "shock" ? "shock" : "think", emo === "neutral" ? "think" : emo, 0);
    sus.forEach((c, i) => { place(c, -1.3 + i * 0.9, -2.6, 0, true); pose(c, t, "idle", "neutral"); });
    const a = lerp(-0.25, 0.1, ease(p));
    lookAt(V(Math.sin(a) * 1.6, 1.55, Math.cos(a) * 1.6), V(0, 1.42, 0), 38);
  } else if (beat.shot === "suspects") {
    const need = 0.66 * (n_s + 1) / (2 * Math.tan(THREE.MathUtils.degToRad(17)) * (W / Hh));
    const dist = need * lerp(1.06, 1.0, ease(p));
    lookAt(V(0, 1.05, dist), V(0, 0.92, 0), 34);
    const xs = lineup(n_s, dist);
    sus.forEach((c, i) => {
      const appear = ease((f - i * 6) / 10);
      place(c, xs[i], -0.0 - (1 - appear) * 0.6, 0, appear > 0);
      pose(c, t, beat.focus === i ? "nervous" : "idle", beat.focus === i ? "worry" : "neutral");
    });
    place(det, 0, 0, 0, false);
  } else if (beat.shot === "clue") {
    // close-up on the clue under the pen-light, slow orbit; the suspect it concerns hovers behind
    const target = prPos.clone().add(V(0, beat.icon === "door" ? 0 : 0.05, 0));
    place(det, target.x - 0.8, target.z + 0.15, 0, true);
    det.root.rotation.y = faceTo(det, target.x, target.z);
    pose(det, t, "inspect", "think", 0);
    const hand = V(target.x - 0.45, target.y + 0.5, target.z + 0.15);
    pen_on(hand, target);
    sus.forEach((c, i) => {
      const show = beat.focus === i;
      place(c, target.x + 0.4, target.z - 1.3, 0, show);
      if (show) { c.root.rotation.y = faceTo(c, target.x, target.z + 1); pose(c, t, "nervous", "worry"); }
    });
    hemi.intensity = 0.8;
    const floorProp = beat.icon === "footprint" || beat.icon === "umbrella";
    if (beat.icon === "door") {                                    // the room's door, seen from across the room
      hemi.intensity = 1.4;
      place(det, -2.75, 1.75, 0, true); det.root.rotation.y = faceTo(det, -3.5, 1.2);
      pose(det, t, "inspect", "think", 0);
      pen_on(V(-3.0, 1.45, 1.55), V(-3.48, 1.0, 1.25)); pen.intensity = 30;
      lookAt(V(lerp(-0.4, -0.7, ease(p)), 1.45, lerp(4.0, 3.6, ease(p))), V(-3.0, 1.0, 1.0), 44);
      R.render(scene, cam);
      return R.domElement.toDataURL("image/jpeg", 0.9);
    }
    const a = lerp(0.75, 0.35, ease(p)), r = floorProp ? 1.0 : 0.7;
    const look = target.clone().add(V(0, beat.icon === "umbrella" ? 0.2 : beat.icon === "footprint" ? 0 : 0.02, beat.icon === "footprint" ? -0.35 : 0));
    lookAt(V(target.x + Math.sin(a) * r, target.y + (floorProp ? 1.0 : 0.3), target.z + Math.cos(a) * r), look, 38);
  } else if (beat.shot === "reveal" || beat.shot === "reveal2") {
    // the culprit in red back-light; the detective points from the foreground
    const ci = job.answer >= 0 && job.answer < n_s ? job.answer : 0;
    const cul = sus[ci];
    sus.forEach((c, i) => { place(c, i === ci ? 0 : (i < ci ? -1.4 : 1.4) + (i - ci) * 0.2, i === ci ? -0.6 : -1.6, 0, true); pose(c, t, i === ci ? (beat.shot === "reveal" ? "shock" : "nervous") : "idle", i === ci ? "worry" : "shock"); });
    place(det, -0.32, 1.25, 0, true); det.root.rotation.y = faceTo(det, 0, -0.6);
    pose(det, t, "point", "think", 0);
    rim.intensity = 30; rim.position.set(0.3, 2.6, -2.4); rim.target.position.set(0, 1.0, -0.6);
    hemi.intensity = 0.7;
    for (const l of world.lamps) l.intensity *= 0.5;
    const k = beat.shot === "reveal" ? easeOut(p) : ease(p);
    if (beat.shot === "reveal") lookAt(V(lerp(0.15, 0.3, k), lerp(1.55, 1.5, k), lerp(3.0, 2.5, k)), V(0.0, lerp(1.0, 1.2, k), -0.6), lerp(44, 38, k));
    else lookAt(V(lerp(0.9, 0.7, k), 1.4, lerp(1.9, 1.6, k)), V(-0.05, 1.3, -0.6), 36);
  } else { // ending: the detective faces us, the owl waves, the camera eases back
    place(det, 0, 0.2, 0, true);
    pose(det, t, p > 0.55 ? "wave" : "idle", "happy", 0);
    sus.forEach((c) => { c.root.visible = false; });
    const k = ease(p);
    lookAt(V(0.15, 1.5, lerp(1.4, 2.6, k)), V(0, lerp(1.45, 1.2, k), 0), 40);
  }
  R.render(scene, cam);
  return R.domElement.toDataURL("image/jpeg", 0.9);
}
