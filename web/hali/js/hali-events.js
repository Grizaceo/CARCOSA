/* ============================================================================
 * HALI · eventos — inferencia por diff de estados (técnica del frontend 2D)
 *
 * El engine solo escribe unos pocos eventos en action_log (PEEK_RESULT,
 * ESCAPE_ATTEMPT, KING_VANISHED); todo lo demás se infiere comparando dos
 * estados consecutivos: cartas reveladas (sube deck.top → la carta era
 * cards[prevTop]), especiales develadas, cordura, llaves, objetos, estados,
 * monstruos. Funciona igual para replays (full_state del jsonl) y live
 * (/state del server).
 * ==========================================================================*/
'use strict';

HALI.events = (() => {

  // ── Extractores a formato "rich" común ──────────────────────────────────
  function richFromFullState(fs) {
    const players = {};
    for (const [pid, p] of Object.entries(fs.players || {})) {
      players[pid] = {
        room: p.room, sanity: p.sanity, keys: p.keys || 0,
        objects: (p.objects || []).slice(),
        statuses: (p.statuses || []).map((s) => s.status_id),
      };
    }
    const rooms = {};
    for (const [rid, r] of Object.entries(fs.rooms || {})) {
      rooms[rid] = {
        specialId: r.special_card_id || null,
        specialRevealed: !!r.special_revealed,
        specialDestroyed: !!r.special_destroyed,
      };
    }
    // Mazos por BOX (identidad estable a través de la rotación "sushi"):
    // difear por habitación generaría revelaciones fantasma al rotar.
    const decks = {}, boxRoom = {};
    for (const [rid, boxId] of Object.entries(fs.box_at_room || {})) {
      const box = (fs.boxes || {})[boxId];
      if (!box || !box.deck) continue;
      decks[boxId] = { top: box.deck.top || 0, cards: box.deck.cards || [] };
      boxRoom[boxId] = rid;
    }
    return {
      players, rooms, decks, boxRoom,
      monsters: (fs.monsters || []).map((m) => ({ id: m.monster_id, room: m.room })),
      phase: fs.phase, round: fs.round, kingFloor: fs.king_floor,
      log: fs.action_log || [],
      gameOver: !!fs.game_over, outcome: fs.outcome,
    };
  }

  function richFromLiveState(state) {
    const players = {};
    for (const [pid, p] of Object.entries(state.players || {})) {
      players[pid] = {
        room: p.room, sanity: p.sanity, keys: p.keys || 0,
        objects: (p.objects || []).slice(),
        statuses: (p.statuses || []).slice(),
      };
    }
    const rooms = {}, decks = {}, boxRoom = {};
    for (const [rid, r] of Object.entries(state.rooms || {})) {
      rooms[rid] = {
        specialId: r.special_card_id || null,
        specialRevealed: !!r.special_revealed,
        specialDestroyed: !!r.special_destroyed,
      };
      // /state no expone boxes: clave por habitación. La rotación del fin de
      // ronda se neutraliza saltando la inferencia de cartas en fase KING.
      if (r.deck) {
        decks['room:' + rid] = { top: r.deck.top || 0, cards: r.deck.cards || [] };
        boxRoom['room:' + rid] = rid;
      }
    }
    return {
      players, rooms, decks, boxRoom,
      monsters: (state.monsters || []).map((m) => ({ id: m.monster_id || m.id, room: m.room })),
      phase: state.phase, round: state.round, kingFloor: state.king_floor,
      log: state.action_log || [],
      gameOver: !!state.game_over, outcome: state.outcome,
    };
  }

  // ── Inferencia ───────────────────────────────────────────────────────────
  function infer(prev, curr) {
    if (!prev || !curr) return [];
    const ev = [];

    // especiales develadas / destruidas
    for (const [rid, cr] of Object.entries(curr.rooms)) {
      const pr = prev.rooms[rid];
      if (!pr || !cr.specialId) continue;
      if (cr.specialRevealed && !pr.specialRevealed) {
        const who = Object.keys(curr.players).find((pid) => curr.players[pid].room === rid) || null;
        ev.push({ t: 'SPECIAL', room: rid, id: cr.specialId, p: who });
      }
      if (cr.specialDestroyed && !pr.specialDestroyed) {
        ev.push({ t: 'SPECIAL_DESTROYED', room: rid, id: cr.specialId });
      }
    }

    // cartas reveladas: deck.top avanzó → la carta revelada estaba en prevTop.
    // Se omite en la fase del Rey (la rotación de mazos no revela nada).
    if (prev.phase !== 'KING') {
      for (const [bid, cd] of Object.entries(curr.decks || {})) {
        const pd = (prev.decks || {})[bid];
        if (!pd) continue;
        const rid = (prev.boxRoom || {})[bid] || (curr.boxRoom || {})[bid];
        for (let k = pd.top; k < cd.top && k < pd.cards.length; k++) {
          const who = Object.keys(curr.players).find((pid) => curr.players[pid].room === rid)
            || Object.keys(prev.players).find((pid) => prev.players[pid].room === rid) || null;
          ev.push({ t: 'CARD', p: who, room: rid, card: String(pd.cards[k]) });
        }
      }
    }

    // eventos explícitos nuevos del action_log del engine
    const newLog = (curr.log || []).slice((prev.log || []).length);
    for (const entry of newLog) {
      if (!entry || !entry.event) continue;
      if (entry.event === 'PEEK_RESULT') ev.push({ t: 'PEEK', room: entry.room, card: entry.card });
      else if (entry.event === 'ESCAPE_ATTEMPT') ev.push({ t: 'ESCAPE', d6: entry.d6, sanity: entry.sanity, total: entry.total, ok: !!entry.success });
      else if (entry.event === 'KING_VANISHED') ev.push({ t: 'VANISH', turns: entry.turns });
    }

    // monstruos que aparecen o desaparecen
    const prevIds = new Set(prev.monsters.map((m) => m.id));
    const currIds = new Set(curr.monsters.map((m) => m.id));
    for (const m of curr.monsters) {
      if (!prevIds.has(m.id)) ev.push({ t: 'MONSTER', m: m.id, room: m.room });
    }
    for (const m of prev.monsters) {
      if (!currIds.has(m.id)) ev.push({ t: 'MONSTER_GONE', m: m.id });
    }

    // por jugador: objetos, llaves, estados, cordura
    for (const [pid, cp] of Object.entries(curr.players)) {
      const pp = prev.players[pid];
      if (!pp) continue;

      for (const obj of cp.objects.filter((o) => !pp.objects.includes(o))) {
        ev.push({ t: 'ITEM', p: pid, item: obj });
      }
      for (const obj of pp.objects.filter((o) => !cp.objects.includes(o))) {
        ev.push({ t: 'ITEM_LOST', p: pid, item: obj });
      }
      if (cp.keys > pp.keys) ev.push({ t: 'KEY', p: pid, d: cp.keys - pp.keys });
      if (cp.keys < pp.keys) ev.push({ t: 'KEY_LOST', p: pid, d: pp.keys - cp.keys });

      for (const st of cp.statuses.filter((s) => !pp.statuses.includes(s))) {
        ev.push({ t: 'STATUS', p: pid, st });
      }
      for (const st of pp.statuses.filter((s) => !cp.statuses.includes(s))) {
        ev.push({ t: 'STATUS_END', p: pid, st });
      }

      const ds = cp.sanity - pp.sanity;
      if (ds !== 0) ev.push({ t: 'SANITY', p: pid, d: ds });
    }

    // el Rey cambió de piso
    if (curr.kingFloor !== prev.kingFloor) {
      ev.push({ t: 'KINGMOVE', floor: curr.kingFloor });
    }

    if (curr.gameOver && !prev.gameOver) {
      ev.push({ t: 'GAMEOVER', outcome: curr.outcome });
    }

    return ev;
  }

  // ── Formato de línea de log (usa el catálogo HALI.cards) ────────────────
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const R = (rid) => esc(String(rid || '').replace('_', '·'));

  function format(ev) {
    const C = HALI.cards;
    switch (ev.t) {
      case 'CARD': {
        const e = C.lookup(ev.card);
        const head = `🔎 <b>${esc(ev.p || '?')}</b> revela en ${R(ev.room)}: <b>${esc(C.pretty(ev.card))}</b> ${C.icon(ev.card)}`;
        const body = e && e.desc ? `<div class="log-card ${C.kind(ev.card)}-k">${e.desc}</div>` : '';
        return { cls: 'lg-card', html: head + body };
      }
      case 'PEEK':
        return { cls: 'lg-info', html: `👁 Se atisba en ${R(ev.room)}: <b>${esc(C.pretty(ev.card))}</b> ${C.icon(ev.card)}` };
      case 'SPECIAL':
        return { cls: 'lg-special', html: `🗺 ${ev.p ? `<b>${esc(ev.p)}</b> devela` : 'Se devela'} la habitación especial <b>${esc(String(ev.id).replace(/_/g, ' '))}</b> en ${R(ev.room)}` };
      case 'SPECIAL_DESTROYED':
        return { cls: 'lg-bad', html: `💥 Un monstruo destruye <b>${esc(String(ev.id).replace(/_/g, ' '))}</b> en ${R(ev.room)}` };
      case 'MONSTER': {
        const e = C.lookup('MONSTER:' + ev.m) || C.lookup(ev.m);
        const body = e && e.desc ? `<div class="log-card monster-k">${e.desc}</div>` : '';
        return { cls: 'lg-bad', html: `👾 <b>${esc((e && e.name) || ev.m)}</b> aparece en ${R(ev.room)}` + body };
      }
      case 'MONSTER_GONE':
        return { cls: 'lg-info', html: `🕳 ${esc(ev.m)} abandona el tablero` };
      case 'ITEM': {
        const e = C.lookup(ev.item);
        return { cls: 'lg-good', html: `🎒 <b>${esc(ev.p)}</b> obtiene <b>${esc((e && e.name) || ev.item)}</b>` };
      }
      case 'ITEM_LOST':
        return { cls: 'lg-info', html: `🎒 <b>${esc(ev.p)}</b> pierde ${esc(C.pretty(ev.item))}` };
      case 'KEY':
        return { cls: 'lg-key', html: `🗝 <b>${esc(ev.p)}</b> encuentra ${ev.d > 1 ? ev.d + ' llaves' : 'una llave'}` };
      case 'KEY_LOST':
        return { cls: 'lg-bad', html: `🗝 <b>${esc(ev.p)}</b> pierde ${ev.d > 1 ? ev.d + ' llaves' : 'una llave'}` };
      case 'STATUS': {
        const e = C.lookup(ev.st);
        return { cls: 'lg-bad', html: `✨ <b>${esc(ev.p)}</b> adquiere el estado <b>${esc((e && e.name) || ev.st)}</b>` };
      }
      case 'STATUS_END':
        return { cls: 'lg-info', html: `✨ <b>${esc(ev.p)}</b> se libera de ${esc(ev.st)}` };
      case 'SANITY':
        return ev.d < 0
          ? { cls: 'lg-bad', html: `🕯 <b>${esc(ev.p)}</b> pierde ${-ev.d} de cordura` }
          : { cls: 'lg-good', html: `🕯 <b>${esc(ev.p)}</b> recupera +${ev.d} de cordura` };
      case 'ESCAPE':
        return { cls: 'lg-info', html: `🕸 Intento de escape: d6=${esc(ev.d6)} + cordura ${esc(ev.sanity)} = ${esc(ev.total)} → ${ev.ok ? '<b>éxito</b>' : 'fallo'}` };
      case 'VANISH':
        return { cls: 'lg-special', html: `👑 El Rey de Amarillo se desvanece por ${esc(ev.turns)} turnos` };
      case 'KINGMOVE':
        return { cls: 'lg-special', html: `👑 El Rey se desplaza al piso F${esc(ev.floor)}` };
      case 'GAMEOVER':
        return { cls: 'lg-special', html: `⛧ <b>${esc(HALI.data.describeOutcome(ev.outcome))}</b>` };
      default:
        return { cls: 'lg-info', html: esc(JSON.stringify(ev)) };
    }
  }

  return { richFromFullState, richFromLiveState, infer, format };
})();
