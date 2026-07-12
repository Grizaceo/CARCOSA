/* ============================================================================
 * HALI · main — orquestación, HUD, lobby y reproducción
 *
 * Jugable de punta a punta contra el game_server local:
 *   crear partida (asientos local/bot/amigo) → jugar (click + botones de
 *   /legal, hotseat multi-asiento) → guardar → reproducir el jsonl guardado.
 * ==========================================================================*/
'use strict';

HALI.app = (() => {
  const { camera, loop, iso, slotFor, worldCenter, AnimPos, pickRoom } = HALI;
  const art = HALI.art;
  const data = HALI.data;

  // ── Estado de la aplicación ─────────────────────────────────────────────
  const S = {
    canvas: null, ctx: null, w: 0, h: 0, dpr: 1,
    session: null,        // replay cargado {frames,...} o null
    live: null,           // LiveClient o null
    frameIdx: 0,
    playing: false,
    speed: 1,
    lastAdvance: 0,
    view: null,           // frame actual normalizado
    stairs: {},
    umbral: 'F2_P',
    anim: new Map(),      // entityKey → AnimPos
    floats: [],           // textos flotantes
    hoverRoom: null,
    legal: [],            // acciones legales (live)
    legalActor: null,     // asiento al que pertenecen S.legal
    outcomeShown: false,
    clientId: null,
  };

  function _cid() {
    if (S.clientId) return S.clientId;
    let cid = null;
    try { cid = localStorage.getItem('carcosa_client_id'); } catch (e) {}
    if (!cid) {
      cid = 'hali-' + Math.random().toString(36).slice(2, 10);
      try { localStorage.setItem('carcosa_client_id', cid); } catch (e) {}
    }
    S.clientId = cid;
    return cid;
  }

  function _serverBase() {
    const el = document.getElementById('live-url');
    let v = (el && el.value.trim()) || '';
    if (!v) v = (location.protocol.startsWith('http') ? location.origin : 'http://127.0.0.1:8765');
    try { localStorage.setItem('hali_server', v); } catch (e) {}
    return v;
  }

  // ── Bootstrap ───────────────────────────────────────────────────────────
  function init() {
    S.canvas = document.getElementById('stage');
    S.ctx = S.canvas.getContext('2d');
    _resize();
    window.addEventListener('resize', _resize);
    _bindInput();
    _bindUI();
    loop.add(render);
    loop.start();

    const urlInput = document.getElementById('live-url');
    if (urlInput && !urlInput.value) {
      let saved = null;
      try { saved = localStorage.getItem('hali_server'); } catch (e) {}
      urlInput.value = saved || (location.protocol.startsWith('http') ? location.origin : 'http://127.0.0.1:8765');
    }

    // ¿replay embebido? (build standalone / demo)
    if (window.HALI_EMBEDDED_REPLAY) {
      loadReplayObject(window.HALI_EMBEDDED_REPLAY);
    } else if (location.protocol.startsWith('http')) {
      fetch('replays/goal_s4_win.json')
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => { if (j && !S.session && !S.live) loadReplayObject(j); })
        .catch(() => {});
    }
  }

  function _resize() {
    S.dpr = Math.min(2, window.devicePixelRatio || 1);
    S.w = window.innerWidth; S.h = window.innerHeight;
    S.canvas.width = S.w * S.dpr;
    S.canvas.height = S.h * S.dpr;
    S.canvas.style.width = S.w + 'px';
    S.canvas.style.height = S.h + 'px';
    camera.fit(S.w, S.h);
  }

  // ── Carga de replays ────────────────────────────────────────────────────
  function loadReplayObject(json) {
    const session = data.loadReplay(json);
    if (S.live) { S.live.close(); S.live = null; }
    S.session = session;
    S.stairs = session.stairs || {};
    S.umbral = session.umbral;
    S.frameIdx = 0;
    S.playing = false;
    S.outcomeShown = false;
    S.anim.clear();
    S.legal = []; S.legalActor = null;
    _renderActionBar([]);
    _applyFrame(session.frames[0], true);
    _updateTimeline();
    _setStatus(`Replay: ${session.meta.policy || 'humano'} · seed ${session.meta.seed} · ${session.frames.length} pasos · ${data.describeOutcome(session.meta.outcome) || 'parcial'}`);
    document.getElementById('timeline-bar').classList.remove('hidden');
    document.getElementById('live-tools').classList.add('hidden');
    document.getElementById('overlay-gameover').classList.add('hidden');
  }

  function loadReplayText(name, text) {
    try {
      if (name.endsWith('.jsonl') || text.trimStart()[0] !== '{' ||
          (text.includes('\n') && text.trimStart().split('\n', 2)[0].includes('"full_state"'))) {
        loadReplayObject(data.distillJsonl(text));
      } else {
        loadReplayObject(JSON.parse(text));
      }
    } catch (e) {
      _setStatus('No se pudo leer el replay: ' + e.message);
    }
  }

  function loadReplayFile(file) {
    const reader = new FileReader();
    reader.onload = () => loadReplayText(file.name, String(reader.result));
    reader.readAsText(file);
  }

  // ── Live ────────────────────────────────────────────────────────────────
  async function connectLive(baseUrl, gameId) {
    S.session = null;
    if (S.live) S.live.close();
    document.getElementById('timeline-bar').classList.add('hidden');
    S.anim.clear();
    S.outcomeShown = false;

    S.live = new data.LiveClient(baseUrl, gameId, {
      clientId: _cid(),
      onFrame: (frame) => {
        if (S.live && S.live.stairs) S.stairs = S.live.stairs;
        _applyFrame(frame, !S.view);
        _syncTurn(frame);
      },
    });
    try {
      await S.live.fetchState();
      S.live.connect();
      document.getElementById('live-tools').classList.remove('hidden');
      document.getElementById('overlay-gameover').classList.add('hidden');
      const seats = S.live.mySeats();
      _setStatus(`Live: ${gameId} · tus asientos: ${seats.length ? seats.join(', ') : 'observador'}`);
      _syncTurn(S.live.lastFrame);
    } catch (e) {
      _setStatus('No se pudo conectar: ' + e.message);
      S.live = null;
      document.getElementById('live-tools').classList.add('hidden');
    }
  }

  /** Si el turno es de un asiento mío, trae /legal y arma la botonera. */
  async function _syncTurn(frame) {
    if (!S.live) return;
    const mine = S.live.myTurnActor(frame);
    if (!mine) {
      S.legal = []; S.legalActor = null;
      _renderActionBar([]);
      return;
    }
    if (S.legalActor === mine && S.legal.length && S.view && !S.view.done) return;
    try {
      const legal = await S.live.fetchLegal(mine);
      // el estado pudo avanzar mientras pedíamos /legal
      if (S.live && S.live.myTurnActor() === mine) {
        S.legal = legal; S.legalActor = mine;
        _renderActionBar(legal);
      }
    } catch (e) { /* reintentará con el próximo frame */ }
  }

  async function _doAct(action) {
    if (!S.live || !S.legalActor) return;
    const actor = S.legalActor;
    S.legal = []; S.legalActor = null;
    _renderActionBar([]);
    try {
      await S.live.act(actor, action);
    } catch (e) {
      _setStatus('Acción rechazada: ' + e.message);
      _syncTurn(S.live && S.live.lastFrame);
    }
  }

  async function createGame() {
    const base = _serverBase();
    const seedRaw = document.getElementById('new-seed').value.trim();
    const seed = seedRaw ? parseInt(seedRaw, 10) : Math.floor(Math.random() * 1e6);
    const players_config = [];
    for (const pid of ['P1', 'P2', 'P3', 'P4']) {
      players_config.push({ pid, control: document.getElementById('seat-' + pid).value });
    }
    if (!players_config.some((p) => p.control === 'local' || p.control === 'remote')) {
      _setStatus('Configura al menos un asiento humano (tú o amigo).');
      return;
    }
    try {
      _setStatus('Creando partida…');
      const res = await data.LiveClient.startGame(base, {
        seed, players_config,
        draw_mode: document.getElementById('new-drawmode').value,
        client_id: _cid(),
      });
      document.getElementById('live-game').value = res.game_id;
      await connectLive(base, res.game_id);
      _setStatus(`Partida ${res.game_id} · seed ${seed} · comparte el game_id para asientos remotos`);
    } catch (e) {
      _setStatus('No se pudo crear: ' + e.message + ' — ¿está corriendo el server? (uvicorn sim.game_server:app)');
    }
  }

  async function saveCurrentGame() {
    if (!S.live) return;
    try {
      const res = await S.live.save();
      _setStatus(`Guardada: ${res.saved_to} (${res.steps} pasos)`);
      refreshGamesList();
    } catch (e) {
      _setStatus('No se pudo guardar: ' + e.message);
    }
  }

  async function watchSavedGame(gameId) {
    try {
      _setStatus(`Descargando ${gameId}…`);
      const text = await data.LiveClient.downloadReplayJsonl(_serverBase(), gameId);
      loadReplayObject(data.distillJsonl(text));
    } catch (e) {
      _setStatus('No se pudo abrir: ' + e.message);
    }
  }

  async function refreshGamesList() {
    const ul = document.getElementById('games-list');
    try {
      const games = await data.LiveClient.listGames(_serverBase());
      ul.innerHTML = '';
      if (!games.length) {
        ul.innerHTML = '<li class="muted">no hay partidas guardadas</li>';
        return;
      }
      for (const g of games.slice(0, 12)) {
        const li = document.createElement('li');
        const outcome = data.describeOutcome(g.outcome) || 'parcial';
        li.innerHTML = `<span class="mono">${g.id}</span> · r${g.rounds ?? '—'} · ${outcome}`;
        li.title = 'ver replay';
        li.onclick = () => watchSavedGame(g.id);
        ul.appendChild(li);
      }
    } catch (e) {
      ul.innerHTML = `<li class="muted">sin conexión al server</li>`;
    }
  }

  // ── Aplicar frame → animaciones + HUD ───────────────────────────────────
  function _applyFrame(frame, snap) {
    const prev = S.view;
    S.view = frame;

    const byRoom = new Map();
    const put = (rid, key) => {
      if (!byRoom.has(rid)) byRoom.set(rid, []);
      byRoom.get(rid).push(key);
    };
    for (const pid of Object.keys(frame.P)) put(frame.P[pid].room, 'pl:' + pid);
    frame.M.forEach((m, i) => put(m[1], 'mn:' + i + ':' + m[0]));

    for (const [rid, keys] of byRoom) {
      const isCorr = rid.endsWith('_P');
      keys.sort();
      keys.forEach((key, i) => {
        const slot = slotFor(rid, i, isCorr);
        if (!slot) return;
        let ap = S.anim.get(key);
        if (!ap || snap) {
          S.anim.set(key, new AnimPos(slot.lx, slot.ly, slot.floor));
        } else {
          ap.goTo(slot.lx, slot.ly, slot.floor, 340);
        }
      });
    }

    if (prev && !snap) {
      for (const pid of Object.keys(frame.P)) {
        const a = prev.P[pid], b = frame.P[pid];
        if (!a || !b) continue;
        const ds = b.sanity - a.sanity;
        const dk = b.keys - a.keys;
        if (ds !== 0) _float(b.room, `${ds > 0 ? '+' : ''}${ds} cordura`, ds > 0 ? art.PAL.oro : art.PAL.vino);
        if (dk > 0) _float(b.room, `+${dk} 🗝`, art.PAL.oro);
        if (dk < 0) _float(b.room, `pierde ${-dk} 🗝`, art.PAL.vino);
      }
    }

    _renderHUD(frame);
    if (frame.a) _ticker(data.describeAction(frame));
    if (frame.done && !S.outcomeShown) _showOutcome(frame.outcome);
    _updateTimeline();
  }

  function _float(rid, text, color) {
    const c = HALI.roomCenter(rid);
    if (!c) return;
    S.floats.push({ lx: c.lx, ly: c.ly, floor: c.floor, text, color, t0: performance.now() });
    if (S.floats.length > 24) S.floats.shift();
  }

  // ── Reproducción ────────────────────────────────────────────────────────
  function _advance(now) {
    if (!S.session || !S.playing) return;
    const interval = 900 / S.speed;
    if (now - S.lastAdvance < interval) return;
    S.lastAdvance = now;
    if (S.frameIdx < S.session.frames.length - 1) {
      S.frameIdx++;
      _applyFrame(S.session.frames[S.frameIdx], false);
    } else {
      S.playing = false;
      _updPlayBtn();
    }
  }

  function seek(idx) {
    if (!S.session) return;
    idx = Math.max(0, Math.min(S.session.frames.length - 1, idx));
    const snap = Math.abs(idx - S.frameIdx) > 1;
    S.frameIdx = idx;
    S.outcomeShown = idx < S.session.frames.length - 1 ? false : S.outcomeShown;
    if (!S.session.frames[idx].done) document.getElementById('overlay-gameover').classList.add('hidden');
    _applyFrame(S.session.frames[idx], snap);
  }

  // ── Render ──────────────────────────────────────────────────────────────
  function render(now) {
    _advance(now);
    const { ctx, w, h } = S;
    ctx.save();
    ctx.scale(S.dpr, S.dpr);

    const view = S.view;
    const tension = view ? (view.T || 0) : 0.1;

    art.drawBackdrop(ctx, w, h, now, tension);

    if (view) {
      const sanities = Object.values(view.P).map((p) => p.sanity);
      const meanS = sanities.reduce((a, b) => a + b, 0) / Math.max(1, sanities.length);
      const warp = Math.max(0, Math.min(1, (1 - (meanS + 5) / 10))) * (0.4 + 0.6 * tension);

      ctx.save();
      camera.apply(ctx, w, h);

      for (const floor of [3, 2, 1]) {
        const focused = camera.focusFloor === 0 || camera.focusFloor === floor;
        const alpha = focused ? 1 : 0.18;
        art.drawFloor(ctx, floor, view, { now, alpha, warp: warp * 0.5 });

        ctx.save();
        ctx.globalAlpha = alpha;
        const wc = worldCenter();
        ctx.translate(-wc.x, -wc.y);

        const stairRoom = S.stairs[String(floor)];
        if (stairRoom) art.drawStairs(ctx, stairRoom);
        if (floor === 2) art.drawUmbral(ctx, now, tension);

        for (const [rid, sp] of Object.entries(view.SP || {})) {
          if (HALI.parseRoomId(rid)?.floor === floor) art.drawSpecial(ctx, rid, sp[0], sp[1], sp[2], now);
        }
        for (const [rid, n] of Object.entries(view.D || {})) {
          if (HALI.parseRoomId(rid)?.floor === floor) art.drawDeck(ctx, rid, n);
        }

        if (S.hoverRoom && HALI.parseRoomId(S.hoverRoom)?.floor === floor && _isLegalMove(S.hoverRoom)) {
          const c = HALI.roomCenter(S.hoverRoom);
          const p = iso(c.lx, c.ly, floor);
          ctx.strokeStyle = art.PAL.oro;
          ctx.globalAlpha = alpha * (0.5 + 0.3 * Math.sin(now * 0.006));
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.ellipse(p.x, p.y, HALI.TW2 * 1.15, HALI.TH2 * 1.15, 0, 0, Math.PI * 2);
          ctx.stroke();
          ctx.globalAlpha = alpha;
        }
        ctx.restore();

        if (Math.round(view.k) === floor) {
          ctx.save(); ctx.globalAlpha = alpha;
          art.drawKing(ctx, floor, now, false);
          ctx.restore();
        }
        if (view.fk != null && Math.round(view.fk) === floor) {
          ctx.save(); ctx.globalAlpha = alpha * 0.8;
          art.drawKing(ctx, floor, now, true);
          ctx.restore();
        }

        _drawEntities(ctx, floor, view, now, alpha);
      }

      _drawFloats(ctx, now);
      ctx.restore();
    }

    art.drawMist(ctx, w, h, now, tension);
    art.drawGrainAndVignette(ctx, w, h, now);
    ctx.restore();
  }

  function _drawEntities(ctx, floor, view, now, alpha) {
    const wc = worldCenter();
    const items = [];
    for (const [pid, pdata] of Object.entries(view.P)) {
      const ap = S.anim.get('pl:' + pid);
      if (!ap) continue;
      const cur = ap.current(now);
      if (Math.round(cur.floor) !== floor) continue;
      items.push({ depth: cur.lx + cur.ly, kind: 'pl', pid, pdata, cur });
    }
    view.M.forEach((m, i) => {
      const ap = S.anim.get('mn:' + i + ':' + m[0]);
      if (!ap) return;
      const cur = ap.current(now);
      if (Math.round(cur.floor) !== floor) return;
      items.push({ depth: cur.lx + cur.ly, kind: 'mn', id: m[0], stun: m[2], cur });
    });
    items.sort((a, b) => a.depth - b.depth);

    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(-wc.x, -wc.y);
    for (const it of items) {
      const p = iso(it.cur.lx, it.cur.ly, floor);
      if (it.kind === 'pl') {
        art.drawPlayer(ctx, it.pid, p.x, p.y, it.pdata, view.actor === it.pid, now);
      } else {
        art.drawMonster(ctx, it.id, p.x, p.y, it.stun > 0, now);
      }
    }
    ctx.restore();
  }

  function _drawFloats(ctx, now) {
    const wc = worldCenter();
    ctx.save();
    ctx.translate(-wc.x, -wc.y);
    ctx.font = 'italic 12px Georgia, serif';
    ctx.textAlign = 'center';
    S.floats = S.floats.filter((f) => now - f.t0 < 1900);
    for (const f of S.floats) {
      const t = (now - f.t0) / 1900;
      const p = iso(f.lx, f.ly, f.floor);
      ctx.globalAlpha = 1 - t;
      ctx.fillStyle = f.color;
      ctx.fillText(f.text, p.x, p.y - 40 - t * 26);
    }
    ctx.restore();
  }

  // ── HUD (DOM) ───────────────────────────────────────────────────────────
  function _renderHUD(frame) {
    document.getElementById('hud-round').textContent = `Ronda ${frame.r}`;
    const mine = S.live && S.live.myTurnActor(frame);
    document.getElementById('hud-phase').textContent =
      frame.ph === 'KING' ? 'La fase del Rey'
        : mine ? `Tu turno — ${mine}`
        : `Turno de ${frame.actor || '—'}`;

    const signCanvas = document.getElementById('hud-sign');
    const sctx = signCanvas.getContext('2d');
    sctx.clearRect(0, 0, signCanvas.width, signCanvas.height);
    art.drawYellowSign(sctx, signCanvas.width / 2, signCanvas.height / 2,
      signCanvas.width * 0.4, frame.T || 0, 0.95);

    const cards = document.getElementById('hud-players');
    cards.innerHTML = '';
    const claims = frame._seats?.claims || {};
    for (const [pid, p] of Object.entries(frame.P)) {
      const sMax = p.sanityMax != null ? p.sanityMax : 5;
      const s01 = Math.max(0, Math.min(1, (p.sanity + 5) / (sMax + 5)));
      const isMine = S.live && claims[pid] === S.clientId;
      const el = document.createElement('div');
      el.className = 'pcard' + (frame.actor === pid ? ' active' : '') + (p.atMinus5 ? ' broken' : '');
      el.innerHTML = `
        <div class="pcard-head">
          <span class="pcard-dot" style="background:${art.PAL.players[pid] || '#888'}"></span>
          <span class="pcard-name">${pid}${isMine ? ' ✦' : ''}</span>
          <span class="pcard-role">${p.role}</span>
        </div>
        <div class="sanity-track"><div class="sanity-fill${p.sanity <= 0 ? ' low' : ''}" style="width:${(s01 * 100).toFixed(0)}%"></div></div>
        <div class="pcard-row">
          <span class="mono">${p.sanity}/${sMax}</span>
          <span class="keys">${'🗝'.repeat(p.keys) || '—'}</span>
        </div>
        ${p.statuses.length ? `<div class="pcard-status">${p.statuses.join(' · ')}</div>` : ''}
        ${p.objects.length ? `<div class="pcard-obj">${p.objects.join(', ')}</div>` : ''}`;
      cards.appendChild(el);
    }

    const keysTotal = Object.values(frame.P).reduce((a, p) => a + p.keys, 0);
    document.getElementById('hud-keys').textContent =
      `Llaves ${keysTotal}/${(S.session && S.session.keysToWin) || 4}` +
      (frame.kd ? ` · ${frame.kd} destruidas` : '');
  }

  function _ticker(text) {
    if (!text) return;
    const el = document.getElementById('ticker');
    const line = document.createElement('div');
    line.textContent = text;
    el.prepend(line);
    while (el.children.length > 5) el.removeChild(el.lastChild);
  }

  function _showOutcome(outcome) {
    S.outcomeShown = true;
    const el = document.getElementById('overlay-gameover');
    document.getElementById('gameover-title').textContent = data.describeOutcome(outcome);
    document.getElementById('gameover-sub').textContent = outcome === 'WIN'
      ? '“No estamos locos todavía; solo hemos visto el lago.”'
      : '“Extraña es la noche donde surgen estrellas negras.”';
    // en live, ofrecer ver el replay de la partida recién guardada
    document.getElementById('btn-watch-replay').classList.toggle('hidden', !S.live);
    el.classList.remove('hidden');
    if (outcome === 'WIN' && S.view) {
      Object.keys(S.view.P).forEach((pid, i) => {
        const ap = S.anim.get('pl:' + pid);
        const slot = slotFor(S.umbral, i, true);
        if (ap && slot) ap.goTo(slot.lx, slot.ly, slot.floor, 1400);
      });
    }
  }

  function _setStatus(text) {
    document.getElementById('status-line').textContent = text;
  }

  // ── Barra de acciones (live) ────────────────────────────────────────────
  function _isLegalMove(rid) {
    return S.legal.some((a) => a.type === 'MOVE' && a.data && a.data.to === rid);
  }

  function _renderActionBar(actions) {
    const bar = document.getElementById('action-bar');
    bar.innerHTML = '';
    if (!actions || !actions.length) { bar.classList.add('hidden'); return; }
    bar.classList.remove('hidden');

    const title = document.createElement('span');
    title.className = 'act-actor';
    title.textContent = S.legalActor || '';
    bar.appendChild(title);

    const nonMove = actions.filter((a) => a.type !== 'MOVE');
    const moves = actions.filter((a) => a.type === 'MOVE');
    if (moves.length) {
      const hint = document.createElement('span');
      hint.className = 'act-hint';
      hint.textContent = `mover: toca una sala iluminada (${moves.length})`;
      bar.appendChild(hint);
    }
    // Motemey: mostrar las cartas pendientes si el server las expone
    const pending = S.view && S.view._pendingMotemey;
    for (const a of nonMove) {
      const btn = document.createElement('button');
      btn.className = 'act-btn';
      let label = _actionLabel(a);
      if (a.type === 'USE_MOTEMEY_BUY_CHOOSE' && pending) {
        const cards = Object.values(pending)[0] || [];
        const card = cards[a.data.chosen_index];
        if (card) label = `elegir: ${card}`;
      }
      btn.textContent = label;
      btn.onclick = () => _doAct(a);
      bar.appendChild(btn);
    }
  }

  function _actionLabel(a) {
    const d = a.data || {};
    const extra = d.object_id || d.item_name || d.target_player || d.room_id ||
      (d.room_a ? `${d.room_a}+${d.room_b}` : '') ||
      (d.mode ? (d.mode === 'SANITY_MAX' ? 'cordura máx −1' : `slot de objetos −1${d.discard_object_id ? ' (soltar ' + d.discard_object_id + ')' : ''}`) : '');
    const NAMES = {
      SEARCH: 'registrar', MEDITATE: 'meditar', END_TURN: 'terminar turno',
      SACRIFICE: 'sacrificar', ACCEPT_SACRIFICE: 'aceptar el colapso',
      ESCAPE_TRAPPED: 'liberarse', DISCARD_SANIDAD: 'descartar sanidad',
      SKIP_PEEK: 'no mirar',
    };
    const base = NAMES[a.type] || a.type.replace(/^USE_/, '').replace(/_/g, ' ').toLowerCase();
    return base + (extra ? ` · ${extra}` : '');
  }

  // ── Input ───────────────────────────────────────────────────────────────
  function _bindInput() {
    const cv = S.canvas;
    let dragging = false, lx = 0, ly = 0, moved = 0;

    cv.addEventListener('mousedown', (e) => { dragging = true; moved = 0; lx = e.clientX; ly = e.clientY; });
    window.addEventListener('mouseup', () => { dragging = false; });
    cv.addEventListener('mousemove', (e) => {
      if (dragging) {
        camera.x += e.clientX - lx; camera.y += e.clientY - ly;
        moved += Math.abs(e.clientX - lx) + Math.abs(e.clientY - ly);
        lx = e.clientX; ly = e.clientY;
      } else {
        S.hoverRoom = pickRoom(e.clientX, e.clientY, S.w, S.h);
        cv.style.cursor = S.hoverRoom && _isLegalMove(S.hoverRoom) ? 'pointer' : 'grab';
      }
    });
    cv.addEventListener('click', (e) => {
      if (moved > 6) return;
      const rid = pickRoom(e.clientX, e.clientY, S.w, S.h);
      if (!rid || !S.live) return;
      const mv = S.legal.find((a) => a.type === 'MOVE' && a.data && a.data.to === rid);
      if (mv) _doAct(mv);
    });
    cv.addEventListener('wheel', (e) => {
      e.preventDefault();
      const k = e.deltaY > 0 ? 0.9 : 1.11;
      camera.zoom = Math.max(0.35, Math.min(2.4, camera.zoom * k));
    }, { passive: false });

    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      if (e.key >= '0' && e.key <= '3') camera.focusFloor = +e.key;
      if (e.key === ' ') { e.preventDefault(); _togglePlay(); }
      if (e.key === 'ArrowRight') seek(S.frameIdx + 1);
      if (e.key === 'ArrowLeft') seek(S.frameIdx - 1);
    });
  }

  // ── UI DOM ──────────────────────────────────────────────────────────────
  function _togglePlay() {
    if (!S.session) return;
    if (S.frameIdx >= S.session.frames.length - 1) S.frameIdx = 0;
    S.playing = !S.playing;
    S.lastAdvance = 0;
    _updPlayBtn();
  }
  function _updPlayBtn() {
    document.getElementById('btn-play').textContent = S.playing ? '❚❚' : '▶';
  }
  function _updateTimeline() {
    if (!S.session) return;
    const range = document.getElementById('timeline');
    range.max = S.session.frames.length - 1;
    range.value = S.frameIdx;
    const f = S.session.frames[S.frameIdx];
    document.getElementById('timeline-label').textContent = `paso ${f.s} · ronda ${f.r}`;
  }

  function _bindUI() {
    document.getElementById('btn-play').onclick = _togglePlay;
    document.getElementById('timeline').oninput = (e) => { S.playing = false; _updPlayBtn(); seek(+e.target.value); };
    document.getElementById('speed').onchange = (e) => { S.speed = +e.target.value; };

    for (const b of document.querySelectorAll('[data-floor]')) {
      b.onclick = () => {
        camera.focusFloor = +b.dataset.floor;
        document.querySelectorAll('[data-floor]').forEach((x) => x.classList.toggle('on', x === b));
      };
    }

    const fileInput = document.getElementById('file-replay');
    if (fileInput) fileInput.onchange = (e) => e.target.files[0] && loadReplayFile(e.target.files[0]);
    window.addEventListener('dragover', (e) => e.preventDefault());
    window.addEventListener('drop', (e) => {
      e.preventDefault();
      if (e.dataTransfer.files[0]) loadReplayFile(e.dataTransfer.files[0]);
    });

    const on = (id, fn) => { const el = document.getElementById(id); if (el) el.onclick = fn; };
    on('btn-create', createGame);
    on('btn-connect', () => {
      const gid = document.getElementById('live-game').value.trim();
      if (!gid) { _setStatus('Falta el game_id'); return; }
      connectLive(_serverBase(), gid);
    });
    on('btn-claim', async () => {
      const seat = document.getElementById('claim-seat').value.trim().toUpperCase();
      if (!S.live || !seat) { _setStatus('Conéctate primero e indica el asiento (P1–P4).'); return; }
      try {
        const res = await S.live.claim([seat]);
        _setStatus(`Asientos tuyos: ${res.claimed.join(', ')}`);
        _syncTurn(S.live.lastFrame);
      } catch (e) { _setStatus(e.message); }
    });
    on('btn-save', saveCurrentGame);
    on('btn-games-refresh', refreshGamesList);
    on('btn-watch-replay', async () => {
      if (!S.live) return;
      const gid = S.live.gameId;
      document.getElementById('overlay-gameover').classList.add('hidden');
      // asegurar que quedó guardada (idempotente) y abrirla como replay
      try { await S.live.save(); } catch (e) { /* pudo autoguardarse ya */ }
      watchSavedGame(gid);
    });
    on('btn-close-gameover', () =>
      document.getElementById('overlay-gameover').classList.add('hidden'));
  }

  return { init, loadReplayObject, loadReplayText, connectLive, createGame, seek, refreshGamesList, state: S };
})();

document.addEventListener('DOMContentLoaded', HALI.app.init);
