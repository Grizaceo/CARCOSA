from __future__ import annotations

from engine.actions import Action, ActionType
from engine.board import floor_of, is_corridor
from engine.boxes import active_deck_for_room
from engine.state import GameState
from engine.types import PlayerId, RoomId


def on_player_enters_room(state: GameState, pid: PlayerId, room: RoomId) -> None:
    """
    P1 - FASE 1.5.2: Hook cuando un jugador entra a una habitación.
    """
    if room not in state.rooms:
        return

    # FASE 1: Habilidad PSYCHIC - Scry 2
    # Ver/reordenar 2 cartas top.
    # Heurística: Monstruo al fondo (-2), Otros arriba (-1).
    p = state.players[pid]
    if getattr(p, "role_id", "") == "PSYCHIC":
        deck = active_deck_for_room(state, room)
        if deck and deck.remaining() >= 2:
            c1 = deck.cards[deck.top]
            c2 = deck.cards[deck.top + 1]

            # Score descending (High = Top)
            s1 = -2 if str(c1).startswith("MONSTER") else -1
            s2 = -2 if str(c2).startswith("MONSTER") else -1

            if s2 > s1:
                # c2 es mejor, poner c2 primero
                deck.cards[deck.top] = c2
                deck.cards[deck.top + 1] = c1

    room_state = state.rooms[room]

    # Si hay una carta especial boca abajo, revelarla
    if (room_state.special_card_id is not None and
        not room_state.special_revealed and
        not room_state.special_destroyed):
        room_state.special_revealed = True
        # Log o tracking de revelación
        state.flags[f"SPECIAL_REVEALED_{room}_{room_state.special_card_id}"] = state.round


def update_umbral_flags(state: GameState, cfg) -> None:
    for p in state.players.values():
        p.at_umbral = str(p.room) == str(cfg.UMBRAL_NODE)


def handle_hallway_peek_action(state: GameState, pid: PlayerId, action: Action) -> bool:
    if action.type == ActionType.PEEK_ROOM_DECK:
        target_room = RoomId(action.data["room_id"])
        if floor_of(target_room) != floor_of(state.players[pid].room) or is_corridor(target_room):
            raise ValueError("Invalid room for peek")
        deck = active_deck_for_room(state, target_room)
        if deck and deck.remaining() > 0:
            card = deck.cards[deck.top]
            state.action_log.append({"event": "PEEK_RESULT", "room": str(target_room), "card": str(card)})
        if state.flags.get("PENDING_HALLWAY_PEEK") == str(pid):
            del state.flags["PENDING_HALLWAY_PEEK"]
        return True

    if action.type == ActionType.SKIP_PEEK:
        if state.flags.get("PENDING_HALLWAY_PEEK") == str(pid):
            del state.flags["PENDING_HALLWAY_PEEK"]
        return True

    return False
