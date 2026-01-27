from __future__ import annotations

from engine.inventory import get_inventory_limits
from engine.objects import is_soulbound
from engine.rules.sacrifice import available_sacrifice_options
from engine.state import GameState
from engine.systems.sanity import apply_sanity_loss
from engine.types import PlayerId

PENDING_SACRIFICE_FLAG = "PENDING_SACRIFICE_CHECK"


def apply_sacrifice_choice(state: GameState, pid: PlayerId, cfg, choice: dict | None) -> None:
    p = state.players[pid]
    opts = available_sacrifice_options(p)

    mode = (choice or {}).get("mode")
    if mode == "OBJECT_SLOT":
        if not opts["can_reduce_object_slots"]:
            raise ValueError("Sacrifice OBJECT_SLOT not available (no object slots to reduce).")

        p.object_slots_penalty = max(0, int(getattr(p, "object_slots_penalty", 0)) + 1)

        _, obj_slots = get_inventory_limits(p)
        while True:
            non_soul = [obj for obj in p.objects if not is_soulbound(obj)]
            if len(non_soul) <= obj_slots:
                break
            drop = (choice or {}).get("discard_object_id")
            if drop not in non_soul:
                drop = non_soul[-1]
            p.objects.remove(drop)
            state.discard_pile.append(drop)

    elif mode == "SANITY_MAX":
        if not opts["can_reduce_sanity"]:
            raise ValueError("Sacrifice SANITY_MAX not available (sanity_max already at -1).")
        p.sanity_max = max(-1, int(p.sanity_max) - 1)
        if p.sanity > p.sanity_max:
            p.sanity = p.sanity_max
    else:
        if opts["object_options"] and not opts["can_reduce_sanity"]:
            apply_sacrifice_choice(state, pid, cfg, {"mode": "OBJECT_SLOT"})
        elif opts["can_reduce_sanity"] and not opts["object_options"]:
            apply_sacrifice_choice(state, pid, cfg, {"mode": "SANITY_MAX"})
        else:
            raise ValueError("Sacrifice choice requires explicit mode when multiple options exist.")

    p.sanity = 0
    p.at_minus5 = False


def apply_minus5_transitions(state: GameState, cfg) -> None:
    for pid, p in state.players.items():
        if p.sanity <= cfg.S_LOSS:
            if not p.at_minus5:
                last_round = getattr(p, "last_minus5_round", -1)
                if last_round == state.round:
                    p.at_minus5 = True
                    p.last_minus5_round = state.round
                    continue
                if state.flags.get(PENDING_SACRIFICE_FLAG) != str(pid):
                    state.flags[PENDING_SACRIFICE_FLAG] = str(pid)
        else:
            if p.at_minus5:
                p.at_minus5 = False


def apply_minus5_consequences(state: GameState, pid: PlayerId, cfg) -> None:
    p = state.players[pid]
    state.keys_destroyed += p.keys
    p.keys = 0
    p.objects = []

    for other_pid, other in state.players.items():
        if other_pid != pid:
            apply_sanity_loss(state, other, 1, source="MINUS_5_TRANSITION", cfg=cfg)

    p.at_minus5 = True
    p.last_minus5_round = state.round
