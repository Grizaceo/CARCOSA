from __future__ import annotations

from engine.config import Config
from engine.effects.states_canonical import has_status
from engine.rules.sanity import sanity_cap
from engine.state import GameState, PlayerState


def heal_player(player: PlayerState, amount: int) -> None:
    player.sanity = min(player.sanity + amount, sanity_cap(player))


def apply_sanity_loss(state: GameState, player: PlayerState, amount: int, cfg: Config | None = None, source: str = "GENERIC") -> None:
    """
    Centralized sanity loss.
    - Applies 'VANIDAD' effect: +1 loss if player has VANIDAD.
    """
    if amount <= 0:
        return

    if has_status(player, "VANIDAD"):
        amount += 1

    player.sanity -= amount

    # Tracking de golpe de gracia
    limit = -5
    if cfg:
        limit = getattr(cfg, "S_LOSS", -5)
    elif hasattr(state, "config"):
        limit = getattr(state.config, "S_LOSS", -5)

    if player.sanity <= limit and amount > 0:
        actual_source = source or "UNKNOWN"
        state.last_sanity_loss_event = f"{actual_source} -> {player.player_id}"
