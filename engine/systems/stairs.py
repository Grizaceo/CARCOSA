from __future__ import annotations

from engine.board import FLOORS, room_from_d4
from engine.rng import RNG
from engine.state import GameState


def roll_stairs(state: GameState, rng: RNG) -> None:
    for floor in range(1, FLOORS + 1):
        roll = rng.randint(1, 4)
        state.stairs[floor] = room_from_d4(floor, roll)
