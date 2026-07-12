/* ============================================================================
 * HALI · datos — adaptadores hacia el simulador CARCOSA
 *
 * Fuentes, todas normalizadas al mismo formato de frame:
 *  · Replay destilado: JSON de tools/distill_replay.py
 *  · Replay crudo:     .jsonl del runner/server (se destila aquí, en JS)
 *  · Live:             API del game_server (/start /claim /state /legal /act
 *                      /save /games + WS). El server es la ÚNICA fuente de
 *                      reglas: este cliente jamás decide legalidad.
 *
 * Frame normalizado:
 *  { s, r, ph, actor, a:{t,d}, T, k, fk, kd, P:{pid:{room,sanity,sanityMax,
 *    keys,role,statuses,objects}}, M:[[id,room,stun]], D:{rid:n},
 *    SP:{rid:[id,revealed,destroyed]}, done, outcome }
 * ==========================================================================*/
'use strict';

HALI.data = (() => {

  // ── Replay destilado ────────────────────────────────────────────────────
  function loadReplay(json) {
    if (!json || !Array.isArray(json.frames) || json.frames.length === 0) {
      throw new Error('Replay inválido: sin frames');
    }
    return {
      mode: 'replay',
      meta: json.meta || {},
      stairs: json.stairs || {},
      umbral: json.umbral || 'F2_P',
      keysToWin: json.keysToWin || 4,
      frames: json.frames,
    };
  }

  // ── Destilador JS: jsonl crudo (con full_state) → replay ───────────────
  // Réplica exacta de tools/distill_replay.py para cerrar el ciclo
  // jugar → guardar → reproducir sin salir del navegador.
  function _deckRemaining(room, fs, rid) {
    const boxId = fs.box_at_room ? fs.box_at_room[rid] : null;
    let deck = (boxId && fs.boxes && fs.boxes[boxId]) ? fs.boxes[boxId].deck : null;
    if (!deck) deck = room.deck;
    if (!deck) return 0;
    return Math.max(0, (deck.cards || []).length - (deck.top || 0));
  }

  function _frameFromRecord(rec) {
    const fs = rec.full_state;
    const P = {};
    for (const [pid, p] of Object.entries(fs.players || {})) {
      P[pid] = {
        room: p.room,
        sanity: p.sanity,
        sanityMax: p.sanity_max,
        keys: p.keys || 0,
        role: p.role_id || 'DEFAULT',
        statuses: (p.statuses || []).map((s) => s.status_id),
        objects: p.objects || [],
        atMinus5: !!p.at_minus5,
        ra: (fs.remaining_actions || {})[pid],
      };
    }
    const D = {}, SP = {};
    for (const [rid, room] of Object.entries(fs.rooms || {})) {
      D[rid] = _deckRemaining(room, fs, rid);
      if (room.special_card_id) {
        SP[rid] = [room.special_card_id, !!room.special_revealed, !!room.special_destroyed];
      }
    }
    return {
      s: rec.step, r: rec.round, ph: rec.phase, actor: rec.actor,
      a: { t: rec.action_type, d: rec.action_data || {} },
      T: +((rec.T_pre != null ? rec.T_pre : 0).toFixed ? rec.T_pre.toFixed(4) : rec.T_pre) || 0,
      k: fs.king_floor || 1,
      fk: fs.false_king_floor != null ? fs.false_king_floor : null,
      kd: fs.keys_destroyed || 0,
      P,
      M: (fs.monsters || []).map((m) => [m.monster_id, m.room, m.stunned_remaining_rounds | 0]),
      D, SP,
      ev: rec.sanity_loss_events || [],
      done: !!rec.done,
      outcome: rec.outcome,
    };
  }

  function distillJsonl(text) {
    const frames = [];
    let firstFs = null, last = null, prevRich = null;
    for (const line of text.split('\n')) {
      const t = line.trim();
      if (!t) continue;
      let rec;
      try { rec = JSON.parse(t); } catch (e) { continue; }
      if (!rec.full_state) continue;
      if (!firstFs) firstFs = rec.full_state;
      const frame = _frameFromRecord(rec);
      // eventos causados por la acción anterior (diff de estados consecutivos)
      const rich = HALI.events.richFromFullState(rec.full_state);
      frame.E = prevRich ? HALI.events.infer(prevRich, rich) : [];
      // atribución de reveals sin dueño: el actor de la acción anterior
      const causer = frames.length ? frames[frames.length - 1].actor : null;
      if (causer && causer !== 'KING') {
        for (const ev of frame.E) if (ev.t === 'CARD' && ev.p == null) ev.p = causer;
      }
      prevRich = rich;
      frames.push(frame);
      last = rec;
    }
    if (!firstFs) throw new Error('jsonl sin registros con full_state');
    return {
      v: 1,
      meta: {
        source: 'jsonl', seed: firstFs.seed,
        policy: last ? last.policy : null,
        outcome: last ? last.outcome : null,
        rounds: last ? last.round : null,
        steps: frames.length,
        roles: firstFs.roles_assigned || {},
      },
      stairs: Object.fromEntries(Object.entries(firstFs.stairs || {}).map(([k, v]) => [String(k), v])),
      umbral: 'F2_P',
      keysToWin: 4,
      frames,
    };
  }

  // ── Live: /state → frame ────────────────────────────────────────────────
  function adaptLiveState(state, stepIdx) {
    const players = {};
    for (const [pid, p] of Object.entries(state.players || {})) {
      players[pid] = {
        room: p.room,
        sanity: p.sanity,
        sanityMax: p.sanity_max,
        keys: p.keys,
        role: p.role_id || 'DEFAULT',
        statuses: p.statuses || [],
        objects: p.objects || [],
        atMinus5: !!p.at_minus5,
        ra: p.remaining_actions,
      };
    }
    const D = {}, SP = {};
    for (const [rid, room] of Object.entries(state.rooms || {})) {
      const deck = room.deck;
      D[rid] = deck ? Math.max(0, (deck.cards || []).length - (deck.top || 0)) : 0;
      if (room.special_card_id) {
        SP[rid] = [room.special_card_id, !!room.special_revealed, !!room.special_destroyed];
      }
    }
    // La API live no expone la tensión del engine: aproximación monótona
    const sanities = Object.values(players).map((p) => p.sanity);
    const minS = sanities.length ? Math.min(...sanities) : 5;
    const T = Math.max(0, Math.min(1, 0.08 * (state.round || 1) + 0.07 * Math.max(0, -minS)));

    return {
      s: stepIdx != null ? stepIdx : (state.step || 0),
      r: state.round,
      ph: state.phase,
      actor: state.active_actor,
      a: null,
      T,
      k: state.king_floor,
      fk: state.false_king_floor,
      kd: state.keys_destroyed || 0,
      P: players,
      M: (state.monsters || []).map((m) => [m.monster_id || m.id, m.room, 0]),
      D, SP,
      done: !!state.game_over,
      outcome: state.outcome,
      _seats: state.seats || null,
      _stairs: state.stairs || null,
      _savedTo: state.saved_to || null,
      _pendingMotemey: state.pending_motemey_choice || null,
    };
  }

  // ── Cliente live ────────────────────────────────────────────────────────
  class LiveClient {
    constructor(baseUrl, gameId, { clientId = null, onFrame = null, onError = null } = {}) {
      this.base = baseUrl.replace(/\/+$/, '');
      this.gameId = gameId;
      this.clientId = clientId;
      this.onFrame = onFrame;
      this.onError = onError || ((e) => console.warn('[HALI live]', e));
      this.ws = null;
      this._pollTimer = null;
      this.stairs = null;
      this.lastFrame = null;
    }

    // ── estáticos: lobby ──
    static async startGame(base, payload) {
      const res = await fetch(base.replace(/\/+$/, '') + '/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `POST /start → ${res.status}`);
      return data;
    }

    static async listGames(base, limit = 25) {
      const res = await fetch(base.replace(/\/+$/, '') + `/games?limit=${limit}`);
      if (!res.ok) throw new Error(`GET /games → ${res.status}`);
      return (await res.json()).games || [];
    }

    static async downloadReplayJsonl(base, gameId) {
      const res = await fetch(base.replace(/\/+$/, '') + `/games/${gameId}/download`);
      if (!res.ok) throw new Error(`GET /games/${gameId}/download → ${res.status}`);
      return await res.text();
    }

    // ── sesión ──
    async fetchState() {
      const res = await fetch(`${this.base}/state/${this.gameId}`);
      if (!res.ok) throw new Error(`GET /state → ${res.status}`);
      const data = await res.json();
      return this._emit(data.state);
    }

    _emit(state) {
      const frame = adaptLiveState(state);
      if (frame._stairs) this.stairs = frame._stairs;
      this.lastFrame = frame;
      if (this.onFrame) this.onFrame(frame, state);
      return frame;
    }

    /** Asientos de este cliente según los claims del server. */
    mySeats(frame) {
      const claims = (frame || this.lastFrame || {})._seats?.claims || {};
      return Object.keys(claims).filter((s) => claims[s] === this.clientId);
    }

    /** Si el actor activo es un asiento mío, lo devuelve; si no, null. */
    myTurnActor(frame) {
      const f = frame || this.lastFrame;
      if (!f || f.done) return null;
      const claims = f._seats?.claims || {};
      return claims[f.actor] === this.clientId ? f.actor : null;
    }

    async claim(seats, mode = 'add', takeover = false) {
      const res = await fetch(`${this.base}/claim`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_id: this.gameId, client_id: this.clientId, seats, mode, takeover }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `POST /claim → ${res.status}`);
      return data;
    }

    async fetchLegal(actor) {
      const res = await fetch(`${this.base}/legal/${this.gameId}/${actor}`);
      if (!res.ok) throw new Error(`GET /legal → ${res.status}`);
      return (await res.json()).actions || [];
    }

    /**
     * Envía una acción EXACTAMENTE como vino de /legal — el frontend jamás
     * inventa ni filtra campos de action.data (la igualdad estricta de step()
     * declara ilegal cualquier alteración).
     */
    async act(actor, action) {
      const res = await fetch(`${this.base}/act`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          game_id: this.gameId,
          actor,
          action_type: action.type,
          action_data: action.data || {},
          client_id: this.clientId,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `POST /act → ${res.status}`);
      this._emit(data.state);
      return data;
    }

    /** Guarda la partida en el server (idempotente; también parciales). */
    async save() {
      const res = await fetch(`${this.base}/save/${this.gameId}`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `POST /save → ${res.status}`);
      return data;
    }

    connect() {
      const wsUrl = this.base.replace(/^http/, 'ws') + `/ws/${this.gameId}/observer`;
      try {
        this.ws = new WebSocket(wsUrl);
        this.ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg.type === 'state_update' && msg.state) this._emit(msg.state);
          } catch (e) { /* ping u otros */ }
        };
        this.ws.onclose = () => this._startPolling();
        this.ws.onerror = () => { try { this.ws.close(); } catch (e) {} };
      } catch (e) {
        this._startPolling();
      }
    }

    _startPolling() {
      if (this._pollTimer) return;
      this._pollTimer = setInterval(() => this.fetchState().catch(this.onError), 3000);
    }

    close() {
      if (this.ws) try { this.ws.close(); } catch (e) {}
      if (this._pollTimer) clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  }

  // ── Narración de acciones (ticker) ──────────────────────────────────────
  const ROOM_LABEL = (rid) => String(rid || '').replace('_', '·');
  function describeAction(frame) {
    if (!frame || !frame.a) return '';
    const { actor } = frame;
    const t = frame.a.t;
    const d = frame.a.d || {};
    switch (t) {
      case 'MOVE': return `${actor} avanza a ${ROOM_LABEL(d.to)}`;
      case 'SEARCH': return `${actor} registra la habitación`;
      case 'MEDITATE': return `${actor} medita entre susurros`;
      case 'END_TURN': return `${actor} cede su turno`;
      case 'KING_ENDROUND': return `El Rey cierra la ronda ${frame.r}${d.d6 ? ` (d6=${d.d6})` : ''}`;
      case 'SACRIFICE': return `${actor} SACRIFICA parte de sí (${d.mode === 'SANITY_MAX' ? 'cordura máxima' : 'espacio de objetos'})`;
      case 'ACCEPT_SACRIFICE': return `${actor} acepta las consecuencias del colapso`;
      case 'ESCAPE_TRAPPED': return `${actor} forcejea contra la telaraña`;
      case 'USE_OBJECT': return `${actor} usa ${d.object_id || 'un objeto'}`;
      case 'USE_BLUNT': return `${actor} golpea con el contundente`;
      case 'USE_MOTEMEY_BUY_START': return `${actor} negocia con Motemey`;
      case 'USE_MOTEMEY_BUY_CHOOSE': return `${actor} elige su compra`;
      case 'USE_MOTEMEY_SELL': return `${actor} vende ${d.item_name || 'algo'} a Motemey`;
      case 'USE_TABERNA_ROOMS': return `${actor} espía ${ROOM_LABEL(d.room_a)} y ${ROOM_LABEL(d.room_b)}`;
      case 'USE_YELLOW_DOORS': return `${actor} cruza las Puertas Amarillas hacia ${d.target_player}`;
      case 'USE_CAPILLA': return `${actor} reza en el Monasterio de la Locura`;
      case 'USE_SALON_BELLEZA': return `${actor} se contempla en el Salón de Belleza`;
      case 'USE_CAMARA_LETAL_RITUAL': return `${actor} oficia el ritual de la Cámara Letal`;
      case 'USE_ARMORY_TAKE': return `${actor} toma algo de la Armería`;
      case 'USE_ARMORY_DROP': return `${actor} deposita ${d.item_name || 'algo'} en la Armería`;
      case 'USE_HEALER_HEAL': return `${actor} ofrece su cordura a los demás`;
      case 'USE_ATTACH_TALE': return `${actor} une un cuento al Libro de Chambers`;
      case 'PEEK_ROOM_DECK': return `${actor} atisba ${ROOM_LABEL(d.room_id)}`;
      case 'SKIP_PEEK': return `${actor} aparta la mirada`;
      case 'DISCARD_SANIDAD': return `${actor} renuncia a la Sanidad`;
      default: return `${actor} · ${t}`;
    }
  }

  function describeOutcome(outcome) {
    if (!outcome) return '';
    if (outcome === 'WIN') return 'HAN ESCAPADO DE CARCOSA';
    if (String(outcome).startsWith('LOSE')) return 'CARCOSA LOS RECLAMA';
    return String(outcome);
  }

  return { loadReplay, distillJsonl, adaptLiveState, LiveClient, describeAction, describeOutcome };
})();
