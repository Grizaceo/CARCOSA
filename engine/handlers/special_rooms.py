from __future__ import annotations

from typing import Callable, Dict

from engine.actions import Action, ActionType
from engine.config import Config
from engine.inventory import add_object
from engine.objects import get_max_keys_capacity, is_soulbound
from engine.rng import RNG
from engine.state import GameState
from engine.systems.decks import reveal_one
from engine.systems.rooms import enter_room_and_reveal
from engine.systems.sanity import apply_sanity_loss, heal_player
from engine.types import PlayerId, RoomId
from engine.rules.keys import get_base_keys_total, get_effective_keys_total

SpecialRoomHandler = Callable[[GameState, PlayerId, Action, RNG, Config], None]


SPECIAL_ROOM_ACTIONS: Dict[ActionType, SpecialRoomHandler] = {}


def register_special_room_action(action_type: ActionType) -> Callable[[SpecialRoomHandler], SpecialRoomHandler]:
    def decorator(fn: SpecialRoomHandler) -> SpecialRoomHandler:
        SPECIAL_ROOM_ACTIONS[action_type] = fn
        return fn
    return decorator


def handle_special_room_action(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> bool:
    handler = SPECIAL_ROOM_ACTIONS.get(action.type)
    if handler is None:
        return False
    handler(state, pid, action, rng, cfg)
    return True


# Compat layer for legacy imports
SPECIAL_ROOM_HANDLERS = SPECIAL_ROOM_ACTIONS


def register_special_room(action_type: ActionType) -> Callable[[SpecialRoomHandler], SpecialRoomHandler]:
    return register_special_room_action(action_type)


def get_special_room_handler(action_type: ActionType) -> SpecialRoomHandler | None:
    return SPECIAL_ROOM_ACTIONS.get(action_type)


@register_special_room_action(ActionType.USE_MOTEMEY_BUY)
def _motemey_buy(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> None:
    p = state.players[pid]
    if p.sanity < 2:
        state.motemey_event_active = False
        return
    apply_sanity_loss(state, p, 2, source="MOTEMEY_BUY", cfg=cfg)
    deck = state.motemey_deck
    if deck.remaining() >= 2:
        card1 = deck.cards[deck.top]
        card2 = deck.cards[deck.top + 1]
        deck.top += 2

        chosen_idx = int(action.data.get("chosen_index", 0))
        chosen = card1 if chosen_idx == 0 else card2
        rejected = card2 if chosen_idx == 0 else card1

        chosen_str = str(chosen)
        if chosen_str == "KEY":
            keys_in_hand = sum(pl.keys for pl in state.players.values())
            keys_in_game = max(0, get_base_keys_total(cfg) - state.keys_destroyed)
            if keys_in_hand < keys_in_game and p.keys < get_max_keys_capacity(p):
                p.keys += 1
            else:
                deck.put_bottom(chosen)
        else:
            if not add_object(state, pid, chosen_str, discard_choice=action.data.get("discard_choice")):
                deck.put_bottom(chosen)

        deck.put_bottom(rejected)
    state.motemey_event_active = False


@register_special_room_action(ActionType.USE_MOTEMEY_BUY_START)
def _motemey_buy_start(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> None:
    p = state.players[pid]
    apply_sanity_loss(state, p, 2, source="MOTEMEY_BUY", cfg=cfg)
    deck = state.motemey_deck

    if deck.remaining() >= 2:
        card1 = deck.draw_top()
        card2 = deck.draw_top()
        if state.pending_motemey_choice is None:
            state.pending_motemey_choice = {}
        state.pending_motemey_choice[str(pid)] = [card1, card2]


@register_special_room_action(ActionType.USE_MOTEMEY_BUY_CHOOSE)
def _motemey_buy_choose(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> None:
    p = state.players[pid]
    if state.pending_motemey_choice and str(pid) in state.pending_motemey_choice:
        cards = state.pending_motemey_choice[str(pid)]
        chosen_idx = int(action.data.get("chosen_index", 0))

        if 0 <= chosen_idx < len(cards):
            chosen = cards[chosen_idx]
            rejected = cards[1 - chosen_idx]

            chosen_str = str(chosen)
            if chosen_str == "KEY":
                keys_in_hand = sum(pl.keys for pl in state.players.values())
                keys_in_game = max(0, get_base_keys_total(cfg) - state.keys_destroyed)
                if keys_in_hand >= keys_in_game:
                    state.motemey_deck.put_bottom(chosen)
                else:
                    role_limit = get_max_keys_capacity(p)
                    if p.keys < role_limit:
                        p.keys += 1
                    else:
                        state.motemey_deck.put_bottom(chosen)
            else:
                if not add_object(state, pid, chosen_str, discard_choice=action.data.get("discard_choice")):
                    pass

            state.motemey_deck.put_bottom(rejected)

            del state.pending_motemey_choice[str(pid)]
            if len(state.pending_motemey_choice) == 0:
                state.pending_motemey_choice = None
            state.motemey_event_active = False


@register_special_room_action(ActionType.USE_MOTEMEY_SELL)
def _motemey_sell(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> None:
    p = state.players[pid]
    item_name = action.data.get("item_name", "")
    if item_name in p.objects and not is_soulbound(item_name):
        p.objects.remove(item_name)
        if str(item_name).startswith("TREASURE"):
            heal_player(p, 3)
        else:
            heal_player(p, 1)
        state.motemey_event_active = False


@register_special_room_action(ActionType.USE_YELLOW_DOORS)
def _yellow_doors(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> None:
    target_id = PlayerId(action.data.get("target_player", ""))
    if target_id in state.players:
        target = state.players[target_id]
        p = state.players[pid]
        from_room = p.room
        p.room = target.room
        apply_sanity_loss(state, target, 1, source="YELLOW_DOORS", cfg=cfg)
        enter_room_and_reveal(state, pid, p.room, from_room=from_room, cfg=cfg, rng=rng)


@register_special_room_action(ActionType.USE_TABERNA_ROOMS)
def _taberna_rooms(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> None:
    p = state.players[pid]
    apply_sanity_loss(state, p, 1, source="TABERNA", cfg=cfg)
    state.taberna_used_this_turn[pid] = True

    room_a = RoomId(action.data.get("room_a", ""))
    room_b = RoomId(action.data.get("room_b", ""))

    deck_a = state.boxes[state.box_at_room.get(room_a)].deck if room_a in state.box_at_room else None
    deck_b = state.boxes[state.box_at_room.get(room_b)].deck if room_b in state.box_at_room else None

    card_a = deck_a.cards[deck_a.top] if deck_a and deck_a.remaining() > 0 else None
    card_b = deck_b.cards[deck_b.top] if deck_b and deck_b.remaining() > 0 else None

    state.last_peek = [{"room": str(room_a), "card": str(card_a)}, {"room": str(room_b), "card": str(card_b)}]


@register_special_room_action(ActionType.USE_ARMORY_DROP)
def _armory_drop(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> None:
    p = state.players[pid]
    item_name = action.data.get("item_name", "")
    item_type = action.data.get("item_type", "object")
    armory_room = p.room

    if armory_room not in state.armory_storage:
        state.armory_storage[armory_room] = []

    if len(state.armory_storage[armory_room]) < 2:
        if item_type == "key" and p.keys > 0:
            p.keys -= 1
            state.armory_storage[armory_room].append({"type": "key", "value": 1})
        elif item_type == "object" and item_name in p.objects and not is_soulbound(item_name):
            p.objects.remove(item_name)
            state.armory_storage[armory_room].append(item_name)


@register_special_room_action(ActionType.USE_ARMORY_TAKE)
def _armory_take(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> None:
    p = state.players[pid]
    armory_room = p.room
    if armory_room in state.armory_storage and len(state.armory_storage[armory_room]) > 0:
        item = state.armory_storage[armory_room].pop()
        if isinstance(item, dict):
            item_name = item.get("value", "")
            if item.get("type") == "key":
                p.keys += item.get("value", 1)
            else:
                if not add_object(state, pid, item_name, discard_choice=action.data.get("discard_choice")):
                    state.armory_storage[armory_room].append(item)
        else:
            if not add_object(state, pid, item, discard_choice=action.data.get("discard_choice")):
                state.armory_storage[armory_room].append(item)


@register_special_room_action(ActionType.USE_CAPILLA)
def _capilla(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> None:
    p = state.players[pid]
    d6 = rng.randint(1, 6)
    heal_amount = d6 + 2
    heal_player(p, heal_amount)
    if d6 == 1:
        from engine.effects.event_utils import add_status
        add_status(p, "PARANOIA")


@register_special_room_action(ActionType.USE_SALON_BELLEZA)
def _salon_belleza(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> None:
    p = state.players[pid]
    state.salon_belleza_uses += 1
    state.flags[f"PROTECCION_AMARILLO_{pid}"] = state.round + 1
    if state.salon_belleza_uses >= 3:
        from engine.effects.event_utils import add_status
        add_status(p, "VANIDAD")


@register_special_room_action(ActionType.USE_CAMARA_LETAL_RITUAL)
def _camara_letal(state: GameState, pid: PlayerId, action: Action, rng: RNG, cfg: Config) -> None:
    if state.flags.get("CAMARA_LETAL_RITUAL_COMPLETED", False):
        return

    p = state.players[pid]
    players_in_room = [p_id for p_id, player in state.players.items() if player.room == p.room]
    if len(players_in_room) != 2:
        return

    d6 = rng.randint(1, 6)
    key_recipient = pid

    costs = [0, 0]
    if d6 in (1, 2):
        costs = [7, 0]
    elif d6 in (3, 4):
        costs = [4, 3]
    elif d6 in (5, 6):
        costs = [4, 3]

    other_pids = [pid2 for pid2 in players_in_room if pid2 != pid]
    if other_pids:
        other_pid = other_pids[0]
        targets = [pid, other_pid]

        for i, target_pid in enumerate(targets):
            dmg = costs[i]
            tp = state.players[target_pid]
            apply_sanity_loss(state, tp, dmg, source="CAMARA_LETAL", cfg=cfg)

        state.flags["CAMARA_LETAL_RITUAL_COMPLETED"] = True

        recipient = state.players[key_recipient]
        keys_in_hand = sum(pl.keys for pl in state.players.values())
        if keys_in_hand < get_effective_keys_total(state, cfg) - state.keys_destroyed:
            recipient.keys += 1

        state.flags["CAMARA_LETAL_D6"] = d6
