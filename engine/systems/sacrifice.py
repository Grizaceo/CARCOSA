from __future__ import annotations

from engine.inventory import get_inventory_limits
from engine.objects import is_soulbound
from engine.rules.sacrifice import available_sacrifice_options
from engine.state import GameState
from engine.systems.sanity import apply_sanity_loss
from engine.types import PlayerId

PENDING_SACRIFICE_FLAG = "PENDING_SACRIFICE_CHECK"
PENDING_SACRIFICE_DAMAGE_FLAG = "PENDING_SACRIFICE_DAMAGE"


def _pending_queue(state: GameState) -> list[str]:
    raw = state.flags.get(PENDING_SACRIFICE_FLAG)
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    return [str(raw)]


def _pending_damage_map(state: GameState) -> dict[str, dict]:
    raw = state.flags.get(PENDING_SACRIFICE_DAMAGE_FLAG)
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def pending_sacrifice_pid(state: GameState) -> str | None:
    queue = _pending_queue(state)
    return queue[0] if queue else None


def is_pending_sacrifice(state: GameState, pid: PlayerId) -> bool:
    return str(pid) in _pending_queue(state)


def has_pending_sacrifice_damage(state: GameState, pid: PlayerId) -> bool:
    return str(pid) in _pending_damage_map(state)


def set_pending_sacrifice_damage(state: GameState, pid: PlayerId, amount: int, source: str | None) -> None:
    pending = _pending_damage_map(state)
    pid_str = str(pid)
    if pid_str in pending:
        return
    pending[pid_str] = {"amount": int(amount), "source": source or "UNKNOWN"}
    state.flags[PENDING_SACRIFICE_DAMAGE_FLAG] = pending


def pop_pending_sacrifice_damage(state: GameState, pid: PlayerId) -> dict | None:
    pending = _pending_damage_map(state)
    pid_str = str(pid)
    info = pending.pop(pid_str, None)
    if pending:
        state.flags[PENDING_SACRIFICE_DAMAGE_FLAG] = pending
    else:
        state.flags.pop(PENDING_SACRIFICE_DAMAGE_FLAG, None)
    return info

def queue_pending_sacrifice(state: GameState, pid: PlayerId) -> None:
    queue = _pending_queue(state)
    pid_str = str(pid)
    if pid_str in queue:
        return
    queue.append(pid_str)
    state.flags[PENDING_SACRIFICE_FLAG] = queue


def pop_pending_sacrifice(state: GameState) -> str | None:
    queue = _pending_queue(state)
    if not queue:
        state.flags.pop(PENDING_SACRIFICE_FLAG, None)
        return None
    pid_str = queue.pop(0)
    if queue:
        state.flags[PENDING_SACRIFICE_FLAG] = queue
    else:
        state.flags.pop(PENDING_SACRIFICE_FLAG, None)
    return pid_str


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
            if drop in p.object_charges:
                del p.object_charges[drop]
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
    if state.flags.get(PENDING_SACRIFICE_FLAG) is not None:
        pending = _pending_queue(state)
        filtered: list[str] = []
        for pid_str in pending:
            pid = PlayerId(pid_str)
            p = state.players.get(pid)
            if p is None:
                continue
            if p.at_minus5:
                continue
            if p.sanity <= cfg.S_LOSS or has_pending_sacrifice_damage(state, pid):
                filtered.append(pid_str)
        if filtered:
            state.flags[PENDING_SACRIFICE_FLAG] = filtered
        else:
            state.flags.pop(PENDING_SACRIFICE_FLAG, None)
    for pid, p in state.players.items():
        if p.sanity <= cfg.S_LOSS:
            if not p.at_minus5:
                last_round = getattr(p, "last_minus5_round", -1)
                if last_round == state.round:
                    p.at_minus5 = True
                    p.last_minus5_round = state.round
                    continue
                queue_pending_sacrifice(state, pid)
        else:
            if p.at_minus5:
                p.at_minus5 = False


def apply_minus5_consequences(state: GameState, pid: PlayerId, cfg) -> None:
    p = state.players[pid]
    state.keys_destroyed += p.keys
    p.keys = 0
    p.objects = []
    p.object_charges = {}

    for other_pid, other in state.players.items():
        if other_pid != pid:
            apply_sanity_loss(state, other, 1, source="MINUS_5_TRANSITION", cfg=cfg)

    p.at_minus5 = True
    p.last_minus5_round = state.round
