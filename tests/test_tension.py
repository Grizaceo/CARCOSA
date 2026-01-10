from engine.config import Config
from engine.state import GameState, PlayerState, MonsterState, StatusInstance
from engine.types import PlayerId, RoomId
from engine.tension import tension_T


def _base_state():
    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=RoomId("F1_R1")),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=3, room=RoomId("F1_R2")),
    }
    return GameState(round=0, players=players, monsters=[], flags={}, seed=1)


def test_tension_bounds():
    cfg = Config()
    s = _base_state()
    T = tension_T(s, cfg)
    assert 0.0 <= T <= 1.0


def test_tension_increases_when_sanity_drops():
    cfg = Config()
    s1 = _base_state()
    T1 = tension_T(s1, cfg)

    s2 = _base_state()
    s2.players[PlayerId("P1")].sanity = -4
    T2 = tension_T(s2, cfg)

    assert T2 > T1


def test_tension_increases_with_monsters_and_keys():
    cfg = Config()
    s = _base_state()
    T0 = tension_T(s, cfg)

    s.monsters.append(MonsterState(monster_id="M1", room=RoomId("F1_R1")))
    s.players[PlayerId("P1")].keys = 2
    T1 = tension_T(s, cfg)

    assert T1 > T0


def test_tension_increases_with_debuffs():
    cfg = Config()
    s = _base_state()
    T0 = tension_T(s, cfg)

    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="STUN", remaining_rounds=2))
    T1 = tension_T(s, cfg)

    assert T1 > T0
