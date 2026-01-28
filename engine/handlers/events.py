from __future__ import annotations

from typing import Callable, Dict

from engine.board import floor_of
from engine.boxes import active_deck_for_room
from engine.config import Config
from engine.effects.event_utils import add_status, remove_all_statuses, get_player_by_turn_offset
from engine.inventory import add_object
from engine.rng import RNG
from engine.state import GameState
from engine.systems.rooms import enter_room_and_reveal
from engine.systems.sanity import apply_sanity_loss, heal_player
from engine.types import PlayerId, RoomId, CardId

EventHandler = Callable[..., None]

# Registry for event card handlers (resolved by event_id)
EVENT_HANDLERS: Dict[str, EventHandler] = {}


def register_event(event_id: str) -> Callable[[EventHandler], EventHandler]:
    def decorator(fn: EventHandler) -> EventHandler:
        EVENT_HANDLERS[event_id] = fn
        return fn

    return decorator


def get_event_handler(event_id: str) -> EventHandler | None:
    return EVENT_HANDLERS.get(event_id)


def resolve_event(state: GameState, pid: PlayerId, event_id: str, cfg: Config, rng: RNG, card_prefix: str = "EVENT") -> None:
    """
    Resuelve un evento por su ID.

    Convencion: Total = d6 + cordura_actual (clamp minimo 0)
    """
    p = state.players[pid]

    # Proteccion Amarillo: inmunidad a eventos "amarillo" por 1 ronda
    prot_flag = state.flags.get(f"PROTECCION_AMARILLO_{pid}", 0)
    amarillo_events = {
        "FURIA_AMARILLO",
        "GOLPE_AMARILLO",
        "REFLEJO_AMARILLO",
        "ESPEJO_AMARILLO",
        "DIVAN_AMARILLO",
    }
    if event_id in amarillo_events and prot_flag > state.round:
        deck = active_deck_for_room(state, p.room)
        if deck is not None:
            deck.put_bottom(CardId(f"{card_prefix}:{event_id}"))
        return

    d6 = rng.randint(1, 6)

    # High Roller: doble roll una vez por turno
    if getattr(p, "role_id", "") == "HIGH_ROLLER" and not p.double_roll_used_this_turn:
        d6_2 = rng.randint(1, 6)
        d6 += d6_2
        p.double_roll_used_this_turn = True

    total = max(0, d6 + p.sanity)

    handler = get_event_handler(event_id)
    if handler is not None:
        handler(state, pid, total, cfg, rng)

    # Evento vuelve al fondo del mazo
    deck = active_deck_for_room(state, p.room)
    if deck is not None:
        deck.put_bottom(CardId(f"{card_prefix}:{event_id}"))


def _event_golpe_amarillo(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """Golpe de Amarillo (ex Reflejo): Pierdes 2 de cordura."""
    p = s.players[pid]
    apply_sanity_loss(s, p, 2, source="GOLPE_AMARILLO")


def _event_espejo_amarillo(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """Espejo de Amarillo: invierte la cordura (cordura x -1)."""
    p = s.players[pid]
    p.sanity = -p.sanity


def _event_hay_cadaver(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Hay un cadaver: segun Total.
    0-2: Pierdes turno siguiente
    3-4: -1 cordura
    5+: Obtienes objeto contundente
    """
    p = s.players[pid]

    if total <= 2:
        s.flags[f"SKIP_TURN_{pid}"] = True
    elif total <= 4:
        apply_sanity_loss(s, p, 1, source="HAY_CADAVER")
    else:
        if not add_object(s, pid, "BLUNT", discard_choice=None):
            s.discard_pile.append("BLUNT")


def _event_comida_servida(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Una comida servida: segun Total.
    0: -3 cordura
    1-2: Estado Envenenado (Canon: Sangrado -> Envenenado)
    3-6: +2 cordura
    7+: Trae otro jugador a tu habitacion, ambos +2 cordura
    """
    p = s.players[pid]

    if total == 0:
        apply_sanity_loss(s, p, 3, source="COMIDA_SERVIDA")
    elif total <= 2:
        add_status(p, "ENVENENADO", duration=2)
    elif total <= 6:
        heal_player(p, 2)
    else:
        other_pids = [pid2 for pid2 in s.players if pid2 != pid]
        if other_pids:
            target_pid = rng.choice(other_pids)
            target_player = s.players[target_pid]
            from_room = target_player.room
            target_player.room = p.room
            enter_room_and_reveal(s, target_pid, p.room, from_room=from_room, cfg=cfg, rng=rng)

            heal_player(p, 2)
            target = s.players[target_pid]
            heal_player(target, 2)


def _event_divan_amarillo(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Un divan de Amarillo: segun Total.
    0-3: Quita todos los estados
    4-7: Quita estados + 1 cordura
    8+: Obtiene estado Sanidad
    """
    p = s.players[pid]

    if total <= 3:
        remove_all_statuses(p)
    elif total <= 7:
        remove_all_statuses(p)
        heal_player(p, 1)
    else:
        add_status(p, "SANIDAD", duration=2)


def _event_cambia_caras(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Cambia caras: segun Total.
    0-3: Swap con jugador a la derecha (orden turno +1, ej 1->2)
    4+: Swap con jugador a la izquierda (orden turno -1, ej 1->4)
    """
    if len(s.turn_order) < 2:
        return

    offset = 1 if total <= 3 else -1
    target_pid = get_player_by_turn_offset(s, pid, offset)
    p = s.players[pid]
    target = s.players[target_pid]
    from_room_p = p.room
    from_room_t = target.room
    p.room, target.room = target.room, p.room
    enter_room_and_reveal(s, pid, p.room, from_room=from_room_p, cfg=cfg, rng=rng)
    enter_room_and_reveal(s, target_pid, target.room, from_room=from_room_t, cfg=cfg, rng=rng)


def _event_furia_amarillo(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    La furia de Amarillo: segun Total.
    0: Dobla efecto del Rey PERMANENTEMENTE
    1-4: Rey se mueve al piso del jugador activo (+ dano llegada)
    5+: Aturde al Rey 1 ronda
    """
    p = s.players[pid]

    if total == 0:
        s.flags["KING_DAMAGE_DOUBLE_PERMANENT"] = True
    elif total <= 4:
        player_floor = floor_of(p.room)
        s.king_floor = player_floor

        dmg = cfg.HOUSE_LOSS_PER_ROUND
        if s.flags.get("KING_DAMAGE_DOUBLE_PERMANENT"):
            dmg *= 2
        elif s.flags.get("KING_DAMAGE_DOUBLE_UNTIL", 0) > s.round:
            dmg *= 2

        for pl in s.players.values():
            if floor_of(pl.room) == player_floor:
                apply_sanity_loss(s, pl, dmg, source="KING_ARRIVAL")
    else:
        s.king_vanished_turns = 1


def _event_ascensor(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Ascensor:
    0: Fin turno
    1-3: Subir 1 piso (F1->F2->F3->F1)
    4-6: Subir 2 pisos (F1->F3->F2->F1)
    """
    p = s.players[pid]
    from_room = p.room
    current_floor = floor_of(p.room)
    suffix = str(p.room).split("_")[1]

    if total == 0:
        s.remaining_actions[pid] = 0
    elif total <= 3:
        new_floor = (current_floor % 3) + 1
        new_rid = RoomId(f"F{new_floor}_{suffix}")
        p.room = new_rid
        enter_room_and_reveal(s, pid, new_rid, from_room=from_room, cfg=cfg, rng=rng)
    else:
        new_floor = ((current_floor + 1) % 3) + 1
        new_rid = RoomId(f"F{new_floor}_{suffix}")
        p.room = new_rid
        enter_room_and_reveal(s, pid, new_rid, from_room=from_room, cfg=cfg, rng=rng)


def _event_trampilla(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Trampilla:
    0: Fin turno
    1-3: Baja 2 pisos (= Subir 1)
    4-6: Baja 1 piso (= Subir 2)
    """
    p = s.players[pid]
    from_room = p.room
    current_floor = floor_of(p.room)
    suffix = str(p.room).split("_")[1]

    if total == 0:
        s.remaining_actions[pid] = 0
    elif total <= 3:
        new_floor = (current_floor % 3) + 1
        new_rid = RoomId(f"F{new_floor}_{suffix}")
        p.room = new_rid
        enter_room_and_reveal(s, pid, new_rid, from_room=from_room, cfg=cfg, rng=rng)
    else:
        vals = {1: 3, 2: 1, 3: 2}
        new_floor = vals[current_floor]
        new_rid = RoomId(f"F{new_floor}_{suffix}")
        p.room = new_rid
        enter_room_and_reveal(s, pid, new_rid, from_room=from_room, cfg=cfg, rng=rng)


def _event_motemey_trigger(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Evento Motemey: Abre tienda inmediatamente.
    Funciona igual que la habitacion: Compra (2 san) o Venta (gratis).
    """
    s.motemey_event_active = True


register_event("REFLEJO_AMARILLO")(_event_golpe_amarillo)
register_event("GOLPE_AMARILLO")(_event_golpe_amarillo)
register_event("ESPEJO_AMARILLO")(_event_espejo_amarillo)
register_event("HAY_CADAVER")(_event_hay_cadaver)
register_event("COMIDA_SERVIDA")(_event_comida_servida)
register_event("DIVAN_AMARILLO")(_event_divan_amarillo)
register_event("CAMBIA_CARAS")(_event_cambia_caras)
register_event("FURIA_AMARILLO")(_event_furia_amarillo)
register_event("ASCENSOR")(_event_ascensor)
register_event("TRAMPILLA")(_event_trampilla)
register_event("EVENTO_MOTEMEY")(_event_motemey_trigger)
