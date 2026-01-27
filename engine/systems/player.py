from __future__ import annotations

from engine.actions import Action
from engine.config import Config
from engine.rng import RNG
from engine.state import GameState


def apply_player_action(state: GameState, action: Action, rng: RNG, cfg: Config) -> GameState:
    from engine import transition
    return transition._apply_player_action(state, action, rng, cfg)
