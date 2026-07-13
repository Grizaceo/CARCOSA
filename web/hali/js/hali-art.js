/* ============================================================================
 * HALI · arte — pintura procedural estilo Robert W. Chambers / El Rey de Amarillo
 * Decadencia fin-de-siècle: hueso, oro enfermizo, vino seco, estrellas negras.
 * Todo se dibuja con código; no hay ni un asset externo.
 * ==========================================================================*/
'use strict';

HALI.art = (() => {
  const { TW2, TH2, WALL_H, INNER_WALL_H, GRID_W, GRID_H, ROOM_RECTS, iso, mulberry32 } = HALI;

  // ── Paleta ──────────────────────────────────────────────────────────────
  const PAL = {
    void:       '#0d0b14',  // noche de estrellas negras
    skyHigh:    '#141021',
    skyLow:     '#3d2f3a',  // crepúsculo enfermo sobre Hali
    lake:       '#191527',
    lakeSheen:  '#463a55',
    hueso:      '#e6d8b4',  // pergamino / hueso
    palido:     '#f2e8c4',  // la Máscara Pálida
    oro:        '#d4a017',  // el oro del Rey
    oroSucio:   '#9a7a1e',
    vino:       '#6b2e3e',  // vino seco / heridas
    hali:       '#26203a',  // profundidades del lago
    gangrena:   '#8a8544',  // verde-amarillo de descomposición
    madera:     '#40342c',
    maderaLuz:  '#54453a',
    alfombra:   '#4c2733',
    muro:       '#2e2536',
    muroLuz:    '#3b2f45',
    sombra:     'rgba(6,4,10,0.55)',
    players: { P1: '#6f9d9c', P2: '#c08a3e', P3: '#8e6e95', P4: '#a94b4b' },
  };

  const ROLE_GLYPH = {
    SCOUT: '◊', HIGH_ROLLER: '⚄', TANK: '▣', BRAWLER: '✕',
    HEALER: '✚', PSYCHIC: '◉', DEFAULT: '·',
  };

  const SPECIAL_META = {
    MOTEMEY:          { glyph: '⚖', name: 'Motemey' },
    CAMARA_LETAL:     { glyph: '☠', name: 'Cámara Letal' },
    PUERTAS_AMARILLO: { glyph: '𝍑', name: 'Puertas Amarillas' },
    PUERTAS:          { glyph: '𝍑', name: 'Puertas Amarillas' },
    TABERNA:          { glyph: '👁', name: 'Taberna' },
    PEEK:             { glyph: '👁', name: 'Taberna' },
    ARMERY:           { glyph: '⚔', name: 'Armería' },
    ARMERIA:          { glyph: '⚔', name: 'Armería' },
    MONASTERIO_LOCURA:{ glyph: '♆', name: 'Monasterio de la Locura' },
    CAPILLA:          { glyph: '♆', name: 'Monasterio de la Locura' },
    SALON_BELLEZA:    { glyph: '❦', name: 'Salón de Belleza' },
  };

  const MONSTER_NAMES = {
    ARANA: 'La Araña', 'ARAÑA': 'La Araña', SPIDER: 'La Araña',
    DUENDE: 'El Duende', REINA_HELADA: 'La Reina Helada',
    VIEJO_DEL_SACO: 'El Viejo del Saco', TUE_TUE: 'El Tue-Tué', TUETUE: 'El Tue-Tué',
    SPIDER_BABY: 'Cría de Araña', 'ARAÑA_BEBE': 'Cría de Araña', ARANA_BEBE: 'Cría de Araña',
    ICE_SERVANT: 'Sirviente de Hielo', SIRVIENTE_HIELO: 'Sirviente de Hielo',
  };

  // ── La Señal Amarilla (firma visual) ────────────────────────────────────
  // Trazada como espiral con tres brazos serpenteantes; `t` ∈ [0,1] controla
  // cuánto de la Señal se ha manifestado (medidor de tensión).
  function drawYellowSign(ctx, cx, cy, radius, t, alpha = 1) {
    if (t <= 0.01) return;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.strokeStyle = PAL.oro;
    ctx.globalAlpha = alpha;
    ctx.lineWidth = Math.max(1.4, Math.min(4.5, radius * 0.09));
    ctx.lineCap = 'round';

    const paths = [];
    // espiral central
    paths.push((p) => {
      ctx.beginPath();
      for (let i = 0; i <= 64 * p; i++) {
        const a = i / 64 * Math.PI * 3.2;
        const r = radius * 0.30 * (i / 64);
        const x = Math.cos(a) * r, y = Math.sin(a) * r;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.stroke();
    });
    // tres tentáculos que caen desde la espiral
    for (let arm = 0; arm < 3; arm++) {
      const baseA = arm * (Math.PI * 2 / 3) + Math.PI / 2.3;
      paths.push((p) => {
        ctx.beginPath();
        for (let i = 0; i <= 40 * p; i++) {
          const s = i / 40;
          const a = baseA + Math.sin(s * 5.5 + arm) * 0.35 * s;
          const r = radius * (0.30 + 0.66 * s);
          const x = Math.cos(a) * r, y = Math.sin(a) * r * 1.12;
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
      });
    }
    // dibujar progresivamente: cada trazo consume una fracción de t
    const per = 1 / paths.length;
    paths.forEach((draw, i) => {
      const local = Math.max(0, Math.min(1, (t - i * per) / per));
      if (local > 0) draw(local);
    });
    ctx.restore();
  }

  // ── Fondo: noche de Carcosa ─────────────────────────────────────────────
  // Estrellas negras, lunas extrañas, soles gemelos hundiéndose en el lago.
  let _stars = null;
  function _initStars(w, h) {
    const rnd = mulberry32(1895); // año de "The King in Yellow"
    _stars = [];
    for (let i = 0; i < 46; i++) {
      _stars.push({
        x: rnd(), y: rnd() * 0.52, r: 3 + rnd() * 7,
        spin: rnd() * Math.PI * 2, drift: 0.002 + rnd() * 0.006,
      });
    }
  }

  function _blackStar(ctx, x, y, r, rot) {
    ctx.save();
    ctx.translate(x, y); ctx.rotate(rot);
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const a = i * Math.PI / 5 - Math.PI / 2;
      const rr = i % 2 === 0 ? r : r * 0.42;
      i === 0 ? ctx.moveTo(Math.cos(a) * rr, Math.sin(a) * rr)
              : ctx.lineTo(Math.cos(a) * rr, Math.sin(a) * rr);
    }
    ctx.closePath();
    ctx.fillStyle = PAL.void;
    ctx.shadowColor = 'rgba(212,160,23,0.25)';
    ctx.shadowBlur = r * 1.1;
    ctx.fill();
    ctx.restore();
  }

  function drawBackdrop(ctx, w, h, now, tension) {
    if (!_stars) _initStars(w, h);
    // cielo crepuscular
    const sky = ctx.createLinearGradient(0, 0, 0, h);
    sky.addColorStop(0, PAL.skyHigh);
    sky.addColorStop(0.55, '#241a2b');
    sky.addColorStop(0.78, PAL.skyLow);
    sky.addColorStop(1, PAL.lake);
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, w, h);

    // soles gemelos hundiéndose tras el lago
    const horizon = h * 0.78;
    for (const [dx, r, a] of [[-0.06, 34, 0.5], [0.045, 24, 0.42]]) {
      const g = ctx.createRadialGradient(w * (0.72 + dx), horizon - 8, 2, w * (0.72 + dx), horizon - 8, r * 2.4);
      g.addColorStop(0, `rgba(242,232,196,${a})`);
      g.addColorStop(0.5, `rgba(212,160,23,${a * 0.5})`);
      g.addColorStop(1, 'rgba(212,160,23,0)');
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(w * (0.72 + dx), horizon - 8, r * 2.4, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = `rgba(230,216,180,${a + 0.15})`;
      ctx.beginPath(); ctx.arc(w * (0.72 + dx), horizon - 8, r, 0, Math.PI * 2); ctx.fill();
    }

    // estrellas negras a la deriva
    for (const s of _stars) {
      const x = ((s.x + now * 0.0000035 * s.drift * 900) % 1.06) * w - w * 0.03;
      _blackStar(ctx, x, s.y * h, s.r, s.spin + now * 0.00008);
    }

    // el lago de Hali: banda oscura con reflejos ondulantes
    ctx.fillStyle = PAL.lake;
    ctx.fillRect(0, horizon, w, h - horizon);
    ctx.save();
    ctx.globalAlpha = 0.16;
    for (let i = 0; i < 9; i++) {
      const y = horizon + 8 + i * (h - horizon) / 10;
      const amp = 5 + i * 1.4;
      ctx.strokeStyle = i % 2 ? PAL.lakeSheen : PAL.oroSucio;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = 0; x <= w; x += 14) {
        const yy = y + Math.sin(x * 0.02 + now * 0.0006 + i * 1.7) * amp * 0.24;
        x === 0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy);
      }
      ctx.stroke();
    }
    ctx.restore();

    // a alta tensión, la Señal se insinúa gigante tras el tablero
    if (tension > 0.62) {
      const a = (tension - 0.62) / 0.38;
      drawYellowSign(ctx, w * 0.5, h * 0.42, Math.min(w, h) * 0.34, 1,
        0.05 + 0.10 * a * (0.75 + 0.25 * Math.sin(now * 0.0011)));
    }
  }

  // ── Piso: losa, parquet, muros, puertas ────────────────────────────────
  function _poly(ctx, pts) {
    ctx.beginPath();
    pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
    ctx.closePath();
  }

  function _shade(hex, f) {
    // aclara (f>0) u oscurece (f<0) un color hex
    const n = parseInt(hex.slice(1), 16);
    const ch = (sh) => {
      let c = (n >> sh) & 255;
      c = Math.round(f > 0 ? c + (255 - c) * f : c * (1 + f));
      return Math.max(0, Math.min(255, c));
    };
    return `rgb(${ch(16)},${ch(8)},${ch(0)})`;
  }

  /**
   * Dibuja un piso completo. view: frame normalizado; fx: {now, alpha, warp}.
   * El origen del contexto ya está en el centro-mundo del tablero.
   */
  function drawFloor(ctx, floor, view, fx) {
    const { now, alpha } = fx;
    const wc = HALI.worldCenter();
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(-wc.x, -wc.y);

    // distorsión por cordura: el piso "respira" cuando el equipo colapsa
    const warp = fx.warp * Math.sin(now * 0.0012 + floor * 2.1);
    if (fx.warp > 0.001) {
      const c = iso(GRID_W / 2, GRID_H / 2, floor);
      ctx.translate(c.x, c.y);
      ctx.transform(1, warp * 0.05, warp * 0.07, 1, 0, 0);
      ctx.translate(-c.x, -c.y);
    }

    const P = (x, y) => iso(x, y, floor);

    // sombra proyectada de la losa
    ctx.save();
    ctx.translate(6, 14);
    _poly(ctx, [P(0, 0), P(GRID_W, 0), P(GRID_W, GRID_H), P(0, GRID_H)]);
    ctx.fillStyle = PAL.sombra;
    ctx.filter = 'blur(6px)';
    ctx.fill();
    ctx.restore();

    // canto de la losa
    const SLAB = 12;
    ctx.fillStyle = _shade(PAL.madera, -0.45);
    _poly(ctx, [P(0, GRID_H), P(GRID_W, GRID_H),
      { x: P(GRID_W, GRID_H).x, y: P(GRID_W, GRID_H).y + SLAB },
      { x: P(0, GRID_H).x, y: P(0, GRID_H).y + SLAB }]);
    ctx.fill();
    _poly(ctx, [P(GRID_W, 0), P(GRID_W, GRID_H),
      { x: P(GRID_W, GRID_H).x, y: P(GRID_W, GRID_H).y + SLAB },
      { x: P(GRID_W, 0).x, y: P(GRID_W, 0).y + SLAB }]);
    ctx.fillStyle = _shade(PAL.madera, -0.6);
    ctx.fill();

    // suelos por sala
    const rnd = mulberry32(floor * 977);
    for (const [key, r] of Object.entries(ROOM_RECTS)) {
      const isCorr = key === 'P';
      for (let x = r.x; x < r.x + r.w; x++) {
        for (let y = r.y; y < r.y + r.h; y++) {
          _poly(ctx, [P(x, y), P(x + 1, y), P(x + 1, y + 1), P(x, y + 1)]);
          if (isCorr) {
            ctx.fillStyle = (x + y) % 2 ? PAL.alfombra : _shade(PAL.alfombra, 0.08);
          } else {
            const base = (x + y) % 2 ? PAL.madera : PAL.maderaLuz;
            ctx.fillStyle = _shade(base, (rnd() - 0.5) * 0.12);
          }
          ctx.fill();
          ctx.strokeStyle = 'rgba(10,8,6,0.35)';
          ctx.lineWidth = 0.7;
          ctx.stroke();
        }
      }
    }

    // greca dorada del pasillo
    ctx.save();
    ctx.strokeStyle = PAL.oroSucio;
    ctx.globalAlpha = alpha * 0.5;
    ctx.lineWidth = 1.2;
    const pr = ROOM_RECTS.P;
    _poly(ctx, [P(pr.x + 0.18, pr.y + 0.18), P(pr.x + pr.w - 0.18, pr.y + 0.18),
                P(pr.x + pr.w - 0.18, pr.y + pr.h - 0.18), P(pr.x + 0.18, pr.y + pr.h - 0.18)]);
    ctx.stroke();
    ctx.restore();

    // ── muros traseros (norte y oeste) con empapelado ──
    _wallpaperWall(ctx, floor, [P(0, 0), P(GRID_W, 0)], 'N', now);
    _wallpaperWall(ctx, floor, [P(0, GRID_H), P(0, 0)], 'W', now);

    // ── muros interiores bajos (corte) con huecos de puerta ──
    const seg = (x1, y1, x2, y2) => _innerWall(ctx, P(x1, y1), P(x2, y2));
    // R1|R2 y R3|R4 (x=3), puerta en el tile central
    seg(3, 0, 3, 1); seg(3, 2, 3, 3);
    seg(3, 4, 3, 5); seg(3, 6, 3, 7);
    // salas norte | pasillo (y=3), puertas en x∈[1,2] y x∈[4,5]
    seg(0, 3, 1, 3); seg(2, 3, 4, 3); seg(5, 3, 6, 3);
    // pasillo | salas sur (y=4)
    seg(0, 4, 1, 4); seg(2, 4, 4, 4); seg(5, 4, 6, 4);

    ctx.restore();
  }

  function _innerWall(ctx, a, b) {
    const h = INNER_WALL_H;
    _poly(ctx, [a, b, { x: b.x, y: b.y - h }, { x: a.x, y: a.y - h }]);
    ctx.fillStyle = PAL.muro;
    ctx.fill();
    ctx.strokeStyle = 'rgba(230,216,180,0.14)';
    ctx.lineWidth = 0.8;
    ctx.stroke();
  }

  function _wallpaperWall(ctx, floor, [a, b], side, now) {
    const h = WALL_H;
    ctx.save();
    _poly(ctx, [a, b, { x: b.x, y: b.y - h }, { x: a.x, y: a.y - h }]);
    const g = ctx.createLinearGradient(0, a.y - h, 0, a.y);
    g.addColorStop(0, _shade(PAL.muro, side === 'N' ? 0.10 : -0.06));
    g.addColorStop(1, _shade(PAL.muro, side === 'N' ? -0.12 : -0.30));
    ctx.fillStyle = g;
    ctx.fill();
    ctx.clip();

    // empapelado: damasco de pequeñas Señales, medio borradas
    const steps = 7;
    for (let i = 0; i < steps; i++) {
      const t = (i + 0.5) / steps;
      const x = a.x + (b.x - a.x) * t;
      const y = a.y + (b.y - a.y) * t - h * (0.36 + 0.28 * (i % 2));
      drawYellowSign(ctx, x, y, 7.5, 1, 0.10 + 0.03 * (i % 3));
    }
    // zócalo dorado
    ctx.strokeStyle = PAL.oroSucio;
    ctx.globalAlpha = 0.5;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y - 3);
    ctx.lineTo(b.x, b.y - 3);
    ctx.stroke();
    ctx.restore();
  }

  // ── Detalles de sala: escaleras, Umbral, especiales, mazos ─────────────
  function drawStairs(ctx, rid) {
    const c = HALI.roomCenter(rid);
    if (!c) return;
    const p0 = iso(c.lx + 0.85, c.ly + 0.85, c.floor);
    ctx.save();
    ctx.translate(p0.x, p0.y);
    // caracol de peldaños ascendentes
    for (let i = 0; i < 6; i++) {
      const a = i * 0.9;
      const x = Math.cos(a) * 7, y = Math.sin(a) * 3.5 - i * 5;
      ctx.fillStyle = i % 2 ? PAL.maderaLuz : _shade(PAL.maderaLuz, 0.15);
      ctx.beginPath();
      ctx.ellipse(x, y, 9 - i * 0.7, 3.6 - i * 0.25, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.strokeStyle = _shade(PAL.madera, -0.3);
    ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(0, 4); ctx.lineTo(0, -28); ctx.stroke();
    ctx.restore();
  }

  function drawUmbral(ctx, now, tension) {
    // El Umbral: sello dorado en el suelo del pasillo F2
    const c = HALI.roomCenter('F2_P');
    const p = iso(c.lx, c.ly, 2);
    ctx.save();
    const pulse = 0.75 + 0.25 * Math.sin(now * 0.0016);
    ctx.globalAlpha = 0.75;
    ctx.strokeStyle = PAL.oro;
    ctx.lineWidth = 1.6;
    for (const k of [1, 0.72]) {
      ctx.beginPath();
      ctx.ellipse(p.x, p.y, TW2 * 1.35 * k, TH2 * 1.35 * k, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    drawYellowSign(ctx, p.x, p.y - 4, 15, 1, 0.5 + 0.3 * pulse);
    // resplandor
    const g = ctx.createRadialGradient(p.x, p.y, 2, p.x, p.y, 55);
    g.addColorStop(0, `rgba(212,160,23,${0.10 * pulse})`);
    g.addColorStop(1, 'rgba(212,160,23,0)');
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.ellipse(p.x, p.y, 60, 30, 0, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }

  function drawSpecial(ctx, rid, specialId, revealed, destroyed, now) {
    const c = HALI.roomCenter(rid);
    if (!c) return;
    const p = iso(c.lx - 0.85, c.ly - 0.85, c.floor);
    const meta = SPECIAL_META[specialId] || { glyph: '★', name: specialId };
    ctx.save();
    ctx.translate(p.x, p.y);
    if (!revealed) {
      // loseta boca abajo
      ctx.fillStyle = _shade(PAL.hali, 0.15);
      ctx.strokeStyle = PAL.oroSucio;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, -8); ctx.lineTo(13, 0); ctx.lineTo(0, 8); ctx.lineTo(-13, 0);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = PAL.hueso;
      ctx.font = '10px Georgia, serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.globalAlpha = 0.8;
      ctx.fillText('?', 0, 0);
    } else {
      ctx.fillStyle = destroyed ? PAL.vino : PAL.oro;
      ctx.font = '15px Georgia, serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.shadowColor = destroyed ? 'rgba(107,46,62,0.8)' : 'rgba(212,160,23,0.6)';
      ctx.shadowBlur = 7;
      ctx.fillText(meta.glyph, 0, -6);
      if (destroyed) {
        ctx.strokeStyle = PAL.vino;
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(-8, -13); ctx.lineTo(8, 1); ctx.stroke();
      }
    }
    ctx.restore();
  }

  function drawDeck(ctx, rid, remaining) {
    if (remaining <= 0) return;
    const c = HALI.roomCenter(rid);
    if (!c || c.key === 'P') return;
    const p = iso(c.lx + 0.85, c.ly - 0.85, c.floor);
    ctx.save();
    ctx.translate(p.x, p.y);
    const n = Math.min(remaining, 6);
    for (let i = 0; i < n; i++) {
      const y = -i * 1.8;
      ctx.fillStyle = i === n - 1 ? '#3a3050' : _shade('#3a3050', -0.25);
      ctx.strokeStyle = 'rgba(212,160,23,0.5)';
      ctx.lineWidth = 0.7;
      ctx.beginPath();
      ctx.moveTo(0, y - 5); ctx.lineTo(9, y); ctx.lineTo(0, y + 5); ctx.lineTo(-9, y);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    }
    drawYellowSign(ctx, 0, -(n - 1) * 1.8, 3.4, 1, 0.55);
    ctx.fillStyle = PAL.hueso;
    ctx.font = 'bold 8px Georgia, serif';
    ctx.textAlign = 'center';
    ctx.globalAlpha = 0.85;
    ctx.fillText(String(remaining), 12, 2);
    ctx.restore();
  }

  // ── Piezas ──────────────────────────────────────────────────────────────
  function drawPlayer(ctx, pid, sx, sy, pdata, isActive, now) {
    const col = PAL.players[pid] || PAL.hueso;
    ctx.save();
    ctx.translate(sx, sy);

    // sombra
    ctx.fillStyle = 'rgba(0,0,0,0.4)';
    ctx.beginPath(); ctx.ellipse(0, 2, 9, 4, 0, 0, Math.PI * 2); ctx.fill();

    // halo de turno activo
    if (isActive) {
      ctx.strokeStyle = PAL.oro;
      ctx.globalAlpha = 0.6 + 0.4 * Math.sin(now * 0.005);
      ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.ellipse(0, 2, 12.5, 5.8, 0, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // túnica (peón)
    const g = ctx.createLinearGradient(0, -22, 0, 2);
    g.addColorStop(0, _shade(col, 0.18));
    g.addColorStop(1, _shade(col, -0.38));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(-7.5, 0);
    ctx.bezierCurveTo(-7, -10, -4.5, -13, -3.5, -16);
    ctx.lineTo(3.5, -16);
    ctx.bezierCurveTo(4.5, -13, 7, -10, 7.5, 0);
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = 'rgba(10,8,12,0.6)';
    ctx.lineWidth = 0.8;
    ctx.stroke();

    // cabeza
    ctx.fillStyle = PAL.palido;
    ctx.beginPath(); ctx.arc(0, -20, 4.6, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(10,8,12,0.45)';
    ctx.stroke();

    // sigilo de rol al pecho
    ctx.fillStyle = PAL.palido;
    ctx.font = 'bold 8px Georgia, serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(ROLE_GLYPH[pdata.role] || '·', 0, -8);

    // vela de cordura sobre la cabeza
    const sMax = Math.max(1, pdata.sanityMax || 5);
    const s01 = Math.max(0, Math.min(1, (pdata.sanity + 5) / (sMax + 5)));
    const flameH = 3 + 6 * s01;
    const flick = Math.sin(now * 0.02 + sx) * 0.8;
    ctx.fillStyle = pdata.sanity <= -3 ? PAL.vino : (pdata.sanity <= 0 ? PAL.gangrena : PAL.oro);
    ctx.beginPath();
    ctx.ellipse(flick * 0.4, -28 - flameH / 2, 1.8, flameH / 2 + flick * 0.3, 0, 0, Math.PI * 2);
    ctx.fill();

    // llaves
    if (pdata.keys > 0) {
      ctx.fillStyle = PAL.oro;
      ctx.font = '9px Georgia, serif';
      ctx.fillText('🗝'.repeat(Math.min(pdata.keys, 3)), 0, 8.5);
    }
    // estados
    if (pdata.statuses && pdata.statuses.length) {
      ctx.fillStyle = PAL.vino;
      ctx.font = 'bold 7px Georgia, serif';
      ctx.fillText(pdata.statuses.map(s => s[0]).join(''), 0, 15);
    }
    // etiqueta
    ctx.fillStyle = 'rgba(230,216,180,0.85)';
    ctx.font = '8px Georgia, serif';
    ctx.fillText(pid, 0, -37 - flameH);
    ctx.restore();
  }

  function drawMonster(ctx, id, sx, sy, stunned, now) {
    const key = String(id).toUpperCase().replace(/-\d+$/, '').replace(/[0-9]/g, '').replace(/__+/g, '_').replace(/_$/, '');
    ctx.save();
    ctx.translate(sx, sy);
    ctx.fillStyle = 'rgba(0,0,0,0.45)';
    ctx.beginPath(); ctx.ellipse(0, 2, 10, 4.4, 0, 0, Math.PI * 2); ctx.fill();
    const bob = Math.sin(now * 0.003 + sx * 0.1) * 1.4;
    ctx.translate(0, bob);
    if (stunned) ctx.globalAlpha = 0.55;

    if (key.includes('ARAN') || key.includes('SPIDER')) {
      ctx.strokeStyle = '#151019'; ctx.lineWidth = 1.6;
      for (let i = 0; i < 8; i++) {
        const a = (i / 8) * Math.PI * 2;
        ctx.beginPath(); ctx.moveTo(0, -7);
        ctx.quadraticCurveTo(Math.cos(a) * 12, -7 + Math.sin(a) * 5, Math.cos(a) * 15, Math.sin(a) * 6);
        ctx.stroke();
      }
      ctx.fillStyle = '#1d1524';
      ctx.beginPath(); ctx.ellipse(0, -8, 7.5, 6, 0, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = PAL.oro;
      for (const [ex, ey] of [[-2.5, -9], [2.5, -9], [-1, -11], [1, -11]]) {
        ctx.beginPath(); ctx.arc(ex, ey, 0.9, 0, Math.PI * 2); ctx.fill();
      }
    } else if (key.includes('DUENDE')) {
      ctx.fillStyle = '#4a5d3a';
      ctx.beginPath();
      ctx.moveTo(-5.5, 0); ctx.quadraticCurveTo(-6, -11, 0, -12);
      ctx.quadraticCurveTo(6, -11, 5.5, 0); ctx.closePath(); ctx.fill();
      ctx.beginPath(); ctx.moveTo(-3, -12); ctx.lineTo(0, -21); ctx.lineTo(3, -12);
      ctx.closePath(); ctx.fill();
      ctx.fillStyle = PAL.oro;
      ctx.beginPath(); ctx.arc(-1.8, -9, 1, 0, Math.PI * 2); ctx.arc(2, -9, 1, 0, Math.PI * 2); ctx.fill();
    } else if (key.includes('REINA')) {
      const g = ctx.createLinearGradient(0, -26, 0, 0);
      g.addColorStop(0, '#cfe0ea'); g.addColorStop(1, '#5d7285');
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.moveTo(-6.5, 0); ctx.lineTo(-3, -24); ctx.lineTo(3, -24); ctx.lineTo(6.5, 0);
      ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#e8f2f8';
      ctx.beginPath(); ctx.arc(0, -26, 3.6, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = '#bcd4e2'; ctx.lineWidth = 1.3;
      for (const dx of [-3, 0, 3]) {
        ctx.beginPath(); ctx.moveTo(dx, -29); ctx.lineTo(dx, -33); ctx.stroke();
      }
    } else if (key.includes('VIEJO') || key.includes('SACO')) {
      ctx.fillStyle = '#4d4356';
      ctx.beginPath();
      ctx.moveTo(-6, 0); ctx.quadraticCurveTo(-7, -13, -1, -16);
      ctx.quadraticCurveTo(5, -14, 5, 0); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#37303f';
      ctx.beginPath(); ctx.ellipse(7, -6, 5.5, 7, -0.4, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = PAL.palido;
      ctx.beginPath(); ctx.arc(-2, -17, 3, 0, Math.PI * 2); ctx.fill();
    } else if (key.includes('TUE')) {
      ctx.fillStyle = '#2c2033';
      ctx.beginPath(); ctx.ellipse(0, -12, 6, 5, 0, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = '#2c2033'; ctx.lineWidth = 2;
      for (const dir of [-1, 1]) {
        ctx.beginPath(); ctx.moveTo(dir * 4, -14);
        ctx.quadraticCurveTo(dir * 14, -20 - Math.sin(now * 0.01) * 3, dir * 17, -12);
        ctx.stroke();
      }
      ctx.fillStyle = PAL.oro;
      ctx.beginPath(); ctx.arc(-2, -13, 1.2, 0, Math.PI * 2); ctx.arc(2, -13, 1.2, 0, Math.PI * 2); ctx.fill();
    } else {
      ctx.fillStyle = '#241d2e';
      ctx.beginPath(); ctx.ellipse(0, -8, 7, 8, 0, 0, Math.PI * 2); ctx.fill();
    }

    if (stunned) {
      ctx.globalAlpha = 1;
      ctx.fillStyle = PAL.hueso;
      ctx.font = 'italic 9px Georgia, serif';
      ctx.textAlign = 'center';
      const a = now * 0.004;
      ctx.fillText('✶', Math.cos(a) * 8, -26 + Math.sin(a) * 3);
      ctx.fillText('✶', Math.cos(a + Math.PI) * 8, -26 + Math.sin(a + Math.PI) * 3);
    }
    ctx.restore();
  }

  /** El Rey de Amarillo: presencia sobre su piso, no una pieza. */
  function drawKing(ctx, floor, now, isFalse) {
    const wc = HALI.worldCenter();
    ctx.save();
    ctx.translate(-wc.x, -wc.y);
    // aura en el borde de la losa
    const c1 = iso(0, 0, floor), c2 = iso(GRID_W, 0, floor),
          c3 = iso(GRID_W, GRID_H, floor), c4 = iso(0, GRID_H, floor);
    ctx.strokeStyle = isFalse ? 'rgba(230,216,180,0.5)' : PAL.oro;
    ctx.globalAlpha = 0.35 + 0.2 * Math.sin(now * 0.002);
    ctx.lineWidth = 2.2;
    ctx.setLineDash([7, 9]);
    ctx.lineDashOffset = -now * 0.02;
    _poly(ctx, [c1, c2, c3, c4]);
    ctx.stroke();
    ctx.setLineDash([]);

    // figura alta y andrajosa al fondo del pasillo
    const p = iso(GRID_W - 0.4, 3.5, floor);
    ctx.globalAlpha = 0.9;
    ctx.translate(p.x + 12, p.y);
    const sway = Math.sin(now * 0.0014) * 2;
    const g = ctx.createLinearGradient(0, -56, 0, 0);
    g.addColorStop(0, isFalse ? '#b9a86a' : PAL.oro);
    g.addColorStop(1, 'rgba(90,70,10,0.0)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(-9, 0);
    ctx.bezierCurveTo(-11 + sway, -22, -7 + sway, -38, -4 + sway, -50);
    ctx.lineTo(4 + sway, -50);
    ctx.bezierCurveTo(8 + sway, -36, 12 + sway, -20, 9, 0);
    // jirones del manto
    ctx.lineTo(6, -6); ctx.lineTo(3, 0); ctx.lineTo(0, -5); ctx.lineTo(-3, 0); ctx.lineTo(-6, -4);
    ctx.closePath(); ctx.fill();
    // la Máscara Pálida (sin rasgos)
    ctx.fillStyle = PAL.palido;
    ctx.beginPath();
    ctx.ellipse(sway, -53, 4.5, 6, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  // ── Niebla y grano ──────────────────────────────────────────────────────
  const _mist = [];
  function drawMist(ctx, w, h, now, intensity) {
    if (_mist.length === 0) {
      const rnd = mulberry32(451);
      for (let i = 0; i < 26; i++) {
        _mist.push({ x: rnd(), y: rnd(), r: 40 + rnd() * 90, v: 0.004 + rnd() * 0.012, ph: rnd() * 7 });
      }
    }
    ctx.save();
    for (const m of _mist) {
      const x = ((m.x + now * 0.00001 * m.v * 500) % 1.2 - 0.1) * w;
      const y = m.y * h + Math.sin(now * 0.0004 + m.ph) * 12;
      const g = ctx.createRadialGradient(x, y, 1, x, y, m.r);
      g.addColorStop(0, `rgba(212,180,90,${0.014 + 0.03 * intensity})`);
      g.addColorStop(1, 'rgba(212,180,90,0)');
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(x, y, m.r, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }

  let _grainCanvas = null;
  function drawGrainAndVignette(ctx, w, h, now) {
    if (!_grainCanvas) {
      _grainCanvas = document.createElement('canvas');
      _grainCanvas.width = 128; _grainCanvas.height = 128;
      const gctx = _grainCanvas.getContext('2d');
      const img = gctx.createImageData(128, 128);
      const rnd = mulberry32(777);
      for (let i = 0; i < img.data.length; i += 4) {
        const v = rnd() * 255;
        img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
        img.data[i + 3] = 14;
      }
      gctx.putImageData(img, 0, 0);
    }
    ctx.save();
    ctx.globalAlpha = 0.5;
    const ox = (now * 0.06) % 128, oy = (now * 0.11) % 128;
    for (let x = -ox; x < w; x += 128) {
      for (let y = -oy; y < h; y += 128) ctx.drawImage(_grainCanvas, x, y);
    }
    ctx.restore();
    // viñeta
    const v = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.34, w / 2, h / 2, Math.max(w, h) * 0.78);
    v.addColorStop(0, 'rgba(0,0,0,0)');
    v.addColorStop(1, 'rgba(5,3,10,0.62)');
    ctx.fillStyle = v;
    ctx.fillRect(0, 0, w, h);
  }

  return {
    PAL, ROLE_GLYPH, SPECIAL_META, MONSTER_NAMES,
    drawYellowSign, drawBackdrop, drawFloor, drawStairs, drawUmbral,
    drawSpecial, drawDeck, drawPlayer, drawMonster, drawKing,
    drawMist, drawGrainAndVignette,
  };
})();
