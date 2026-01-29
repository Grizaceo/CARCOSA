from __future__ import annotations

from engine.config import Config
from engine.effects.states_canonical import has_status
from engine.rules.sanity import sanity_cap
from engine.state import GameState, PlayerState


def heal_player(player: PlayerState, amount: int) -> None:
    player.sanity = min(player.sanity + amount, sanity_cap(player))


def apply_sanity_loss(
    state: GameState,
    player: PlayerState,
    amount: int,
    cfg: Config | None = None,
    source: str = "GENERIC",
    allow_sacrifice: bool = True,
    apply_vanidad: bool = True,
) -> None:
    """
    Centralized sanity loss.
    - Applies 'VANIDAD' effect: +1 loss if player has VANIDAD.
    """
    if amount <= 0:
        return

    if apply_vanidad and has_status(player, "VANIDAD"):
        amount += 1

    prev_sanity = player.sanity

    # Tracking de golpe de gracia
    limit = -5
    if cfg:
        limit = getattr(cfg, "S_LOSS", -5)
    elif hasattr(state, "config"):
        limit = getattr(state.config, "S_LOSS", -5)

    if allow_sacrifice and prev_sanity > limit:
        from engine.systems.sacrifice import (
            is_pending_sacrifice,
            queue_pending_sacrifice,
            set_pending_sacrifice_damage,
        )
        if is_pending_sacrifice(state, player.player_id):
            return
        projected = prev_sanity - amount
        if projected <= limit and not player.at_minus5:
            from engine.rules.sacrifice import available_sacrifice_options

            opts = available_sacrifice_options(player)
            can_sacrifice = bool(opts.get("can_reduce_object_slots")) or bool(opts.get("can_reduce_sanity"))
            if can_sacrifice:
                set_pending_sacrifice_damage(state, player.player_id, amount, source)
                queue_pending_sacrifice(state, player.player_id)
                return

            # Sin opciones de sacrificio: aplicar daño y consecuencias inmediatas
            player.sanity = projected
            actual_source = source or "UNKNOWN"
            state.last_sanity_loss_event = f"{actual_source} -> {player.player_id}"
            if hasattr(state, "last_sanity_loss_events"):
                state.last_sanity_loss_events.append(f"{actual_source} -> {player.player_id}")
            from engine.systems.sacrifice import apply_minus5_consequences
            eff_cfg = cfg or getattr(state, "config", None)
            apply_minus5_consequences(state, player.player_id, eff_cfg)
            return

    player.sanity -= amount

    crossed = prev_sanity > limit and player.sanity <= limit
    if crossed and amount > 0:
        actual_source = source or "UNKNOWN"
        state.last_sanity_loss_event = f"{actual_source} -> {player.player_id}"
        if hasattr(state, "last_sanity_loss_events"):
            state.last_sanity_loss_events.append(f"{actual_source} -> {player.player_id}")
        if allow_sacrifice and not player.at_minus5:
            from engine.systems.sacrifice import queue_pending_sacrifice
            queue_pending_sacrifice(state, player.player_id)
