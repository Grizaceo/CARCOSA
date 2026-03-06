from engine.actions import ActionType
from engine.board import corridor_id, room_id
from engine.config import Config
from engine.rng import RNG
from engine.state_factory import make_game_state
from engine.types import PlayerId
from sim.policies import GoalDirectedPlayerPolicy


def test_goal_policy_prioritizes_best_hallway_peek_card():
    rooms = {
        str(room_id(1, 1)): {"cards": ["EVENT:SAFE"]},
        str(room_id(1, 2)): {"cards": ["KEY"]},
        str(room_id(1, 3)): {"cards": ["MONSTER:SPIDER"]},
        str(corridor_id(1)): {},
    }
    players = {"P1": {"room": str(corridor_id(1)), "sanity": 5}}

    state = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        turn_order=["P1"],
        remaining_actions={"P1": 1},
    )
    state.flags["PENDING_HALLWAY_PEEK"] = "P1"
    state.players[PlayerId("P1")].room = corridor_id(1)

    policy = GoalDirectedPlayerPolicy(Config())
    action = policy.choose(state, RNG(7))

    assert action.type == ActionType.PEEK_ROOM_DECK
    assert action.data.get("room_id") == str(room_id(1, 2))
