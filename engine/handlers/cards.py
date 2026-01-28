from __future__ import annotations

from typing import Optional

from engine.boxes import active_deck_for_room
from engine.config import Config
from engine.inventory import add_object
from engine.objects import OBJECT_CATALOG, get_max_keys_capacity
from engine.rng import RNG
from engine.state import GameState, StatusInstance
from engine.systems.monsters import spawn_monster_from_card, handle_omen_reveal
from engine.systems.sanity import apply_sanity_loss
from engine.types import PlayerId, RoomId
from engine.handlers.events import resolve_event
from engine.effects.event_utils import add_status
from engine.board import floor_of


def resolve_card_minimal(state: GameState, pid: PlayerId, card, cfg: Config, rng: Optional[RNG] = None):
    """
    Resolver efectos minimos de cartas.
    - KEY -> jugador gana una llave (si no excede limite)
    - MONSTER:<id> -> monstruo entra en el tablero
    - STATE:<id> -> status al jugador
    - CROWN -> activa bandera de corona y crea Falso Rey en piso del jugador
    """
    s_str = str(card)
    p = state.players[pid]

    def _grant_object(obj_id: str) -> None:
        if not add_object(state, pid, obj_id, discard_choice=None):
            state.discard_pile.append(obj_id)

    if s_str == "KEY":
        keys_in_hand = sum(pl.keys for pl in state.players.values())
        keys_in_game = max(0, int(getattr(cfg, "KEYS_TOTAL", 6)) - state.keys_destroyed)

        if keys_in_hand >= keys_in_game:
            deck = active_deck_for_room(state, p.room)
            if deck is not None:
                deck.put_bottom(card)
            return

        role_capacity = get_max_keys_capacity(p)

        if p.keys < role_capacity:
            p.keys += 1
        else:
            deck = active_deck_for_room(state, p.room)
            if deck is not None:
                deck.put_bottom(card)
        return

    if s_str.startswith("OBJECT:"):
        obj_id = s_str.split(":", 1)[1]
        if obj_id == "CROWN":
            s_str = "CROWN"
        elif obj_id in OBJECT_CATALOG:
            _grant_object(obj_id)
            return

    if s_str in OBJECT_CATALOG and s_str != "CROWN":
        _grant_object(s_str)
        return

    if s_str.startswith("MONSTER:"):
        mid = s_str.split(":", 1)[1]
        spawn_monster_from_card(state, pid, mid, cfg, rng)
        return

    if s_str.startswith("STATE:"):
        sid = s_str.split(":", 1)[1]
        duration = 3 if sid in ("TRAPPED", "TRAPPED_SPIDER") else 2
        p.statuses.append(StatusInstance(status_id=sid, remaining_rounds=duration))
        return

    if s_str == "CROWN":
        if not state.flags.get("CROWN_YELLOW"):
            state.flags["CROWN_YELLOW"] = True
            state.flags["CROWN_HOLDER"] = str(pid)
            if "CROWN" not in p.soulbound_items:
                p.soulbound_items.append("CROWN")
            state.false_king_floor = floor_of(p.room)
            state.false_king_round_appeared = state.round
        return

    if s_str.startswith("OMEN:"):
        omen_id = s_str.split(":", 1)[1]
        handle_omen_reveal(state, pid, omen_id, rng, cfg)
        state.discard_pile.append(f"OMEN:{omen_id}")
        return

    if s_str.startswith("EVENT:") or s_str.startswith("EVENTS:"):
        prefix = s_str.split(":", 1)[0]
        event_id = s_str.split(":", 1)[1]
        resolve_event(state, pid, event_id, cfg, rng, card_prefix=prefix)
        return
