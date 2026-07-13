/* ============================================================================
 * HALI · núcleo — motor 2.5D isométrico ad hoc para CARCOSA
 * "Along the shore the cloud waves break, the twin suns sink behind the lake"
 *
 * Sin dependencias. Canvas 2D + proyección dimétrica 2:1.
 * Namespace global: HALI (los módulos hali-art / hali-data / hali-main lo extienden)
 * ==========================================================================*/
'use strict';

const HALI = (() => {

  // ── Proyección isométrica ──────────────────────────────────────────────
  const TW2 = 36;          // medio-ancho de tile en pantalla
  const TH2 = 18;          // medio-alto  de tile en pantalla
  const FLOOR_DY = 208;    // separación vertical entre pisos
  const WALL_H = 62;       // altura de muros traseros
  const INNER_WALL_H = 20; // altura de muros interiores (corte de casa de muñecas)

  /** (x,y) locales de piso → coordenadas de pantalla (sin cámara). floor 1..3 */
  function iso(x, y, floor) {
    return {
      x: (x - y) * TW2,
      y: (x + y) * TH2 + (3 - floor) * FLOOR_DY,
    };
  }

  // ── Geometría canónica del tablero (canon PDF §2.1) ────────────────────
  // Pasillo conecta con R1–R4; R1↔R2; R3↔R4. Grid local 6×7 por piso.
  const ROOM_RECTS = {
    R1: { x: 0, y: 0, w: 3, h: 3 },
    R2: { x: 3, y: 0, w: 3, h: 3 },
    P:  { x: 0, y: 3, w: 6, h: 1 },
    R3: { x: 0, y: 4, w: 3, h: 3 },
    R4: { x: 3, y: 4, w: 3, h: 3 },
  };

  const GRID_W = 6, GRID_H = 7;

  function parseRoomId(rid) {
    // "F2_R3" → {floor: 2, key: "R3"}   ·   "F1_P" → {floor: 1, key: "P"}
    const m = /^F(\d)_(R\d|P)$/.exec(rid);
    if (!m) return null;
    return { floor: +m[1], key: m[2] };
  }

  function roomCenter(rid) {
    const p = parseRoomId(rid);
    if (!p) return null;
    const r = ROOM_RECTS[p.key];
    return { lx: r.x + r.w / 2, ly: r.y + r.h / 2, floor: p.floor, key: p.key };
  }

  /** Slots de posición dentro de una sala para que las piezas no se pisen. */
  const SLOTS = [
    [0, 0], [-0.75, -0.45], [0.75, -0.45], [-0.75, 0.55], [0.75, 0.55],
    [0, -0.85], [0, 0.85], [-1.3, 0], [1.3, 0],
  ];
  function slotFor(rid, index, isCorridor) {
    const c = roomCenter(rid);
    if (!c) return null;
    const s = SLOTS[index % SLOTS.length];
    // el pasillo es angosto: repartir a lo largo, no a lo ancho
    const dx = isCorridor ? (index - 1.5) * 1.05 : s[0];
    const dy = isCorridor ? (index % 2 ? 0.28 : -0.28) * 0.6 : s[1];
    return { lx: c.lx + dx, ly: c.ly + dy, floor: c.floor };
  }

  // ── RNG determinista para arte procedural ──────────────────────────────
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ── Tweens ──────────────────────────────────────────────────────────────
  const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
  const easeInOut = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

  class Tween {
    constructor(from, to, ms, ease = easeOutCubic) {
      this.from = from; this.to = to; this.ms = ms; this.ease = ease;
      this.t0 = performance.now(); this.done = ms <= 0;
    }
    value(now = performance.now()) {
      if (this.done) return this.to;
      const t = Math.min(1, (now - this.t0) / this.ms);
      if (t >= 1) this.done = true;
      const k = this.ease(t);
      return this.from + (this.to - this.from) * k;
    }
  }

  /** Posición animable en coordenadas locales de tablero (lx, ly, floor). */
  class AnimPos {
    constructor(lx, ly, floor) {
      this.lx = lx; this.ly = ly; this.floor = floor;
      this._tx = null; this._ty = null; this._tf = null;
    }
    goTo(lx, ly, floor, ms = 340) {
      if (lx === this.lx && ly === this.ly && floor === this.floor) return;
      this._tx = new Tween(this.lx, lx, ms);
      this._ty = new Tween(this.ly, ly, ms);
      this._tf = new Tween(this.floor, floor, ms, easeInOut);
      this.lx = lx; this.ly = ly; this.floor = floor;
    }
    current(now) {
      return {
        lx: this._tx && !this._tx.done ? this._tx.value(now) : this.lx,
        ly: this._ty && !this._ty.done ? this._ty.value(now) : this.ly,
        floor: this._tf && !this._tf.done ? this._tf.value(now) : this.floor,
      };
    }
  }

  // ── Cámara ──────────────────────────────────────────────────────────────
  const camera = {
    x: 0, y: 0, zoom: 1,
    focusFloor: 0, // 0 = todos
    apply(ctx, w, h) {
      ctx.translate(w / 2 + this.x, h / 2 + this.y);
      ctx.scale(this.zoom, this.zoom);
    },
    /** pantalla → coordenadas de mundo (pre-piso) */
    unproject(px, py, w, h) {
      return { wx: (px - w / 2 - this.x) / this.zoom, wy: (py - h / 2 - this.y) / this.zoom };
    },
    fit(w, h) {
      // Caja proyectada real del tablero (3 pisos + muros), relativa al centro-mundo
      const bw = (GRID_W + GRID_H) * TW2 + 40;                       // ~472
      const bh = 2 * FLOOR_DY + (GRID_W + GRID_H) * TH2 + WALL_H + 80; // ~730
      const freeW = Math.max(320, w - 300);  // margen para HUD lateral
      const freeH = Math.max(320, h - 130);  // margen para timeline/título
      this.zoom = Math.min(freeW / bw, freeH / bh);
      this.zoom = Math.max(0.4, Math.min(1.5, this.zoom));
      this.x = -70 * this.zoom;  // corrido a la izquierda: las fichas viven a la derecha
      this.y = 14;
    },
  };

  /** centro-mundo del tablero (para centrar cámara) */
  function worldCenter() {
    const top = iso(0, 0, 3);
    const bot = iso(GRID_W, GRID_H, 1);
    return { x: (top.x + bot.x) / 2, y: (top.y + bot.y) / 2 };
  }

  // ── Picking: pantalla → sala ────────────────────────────────────────────
  function pickRoom(px, py, w, h) {
    const { wx, wy } = camera.unproject(px, py, w, h);
    const wc = worldCenter();
    const ax = wx + wc.x, ay = wy + wc.y; // deshacer el centrado del render
    for (let floor = 1; floor <= 3; floor++) {
      // invertir iso: x−y = ax/TW2 ; x+y = (ay − (3−floor)*FLOOR_DY)/TH2
      const u = ax / TW2;
      const v = (ay - (3 - floor) * FLOOR_DY) / TH2;
      const x = (u + v) / 2, y = (v - u) / 2;
      if (x < 0 || x > GRID_W || y < 0 || y > GRID_H) continue;
      for (const [key, r] of Object.entries(ROOM_RECTS)) {
        if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) {
          return `F${floor}_${key}`;
        }
      }
    }
    return null;
  }

  // ── Bucle principal ─────────────────────────────────────────────────────
  const loop = {
    _fns: [], running: false,
    add(fn) { this._fns.push(fn); },
    start() {
      if (this.running) return;
      this.running = true;
      const tick = (now) => {
        if (!this.running) return;
        for (const fn of this._fns) fn(now);
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    },
    stop() { this.running = false; },
  };

  return {
    TW2, TH2, FLOOR_DY, WALL_H, INNER_WALL_H, GRID_W, GRID_H,
    ROOM_RECTS, iso, parseRoomId, roomCenter, slotFor, worldCenter,
    mulberry32, Tween, AnimPos, easeOutCubic, easeInOut,
    camera, pickRoom, loop,
  };
})();
