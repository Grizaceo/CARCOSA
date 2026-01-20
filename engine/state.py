from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import copy

from engine.types import PlayerId, RoomId, CardId
from engine.boxes import sync_room_decks_from_boxes


@dataclass
class StatusInstance:
    status_id: str
    remaining_rounds: int
    stacks: int = 1


@dataclass
class PlayerState:
    player_id: PlayerId
    sanity: int
    room: RoomId

    sanity_max: Optional[int] = None
    keys: int = 0
    objects: List[str] = field(default_factory=list)
    soulbound_items: List[str] = field(default_factory=list)
    statuses: List[StatusInstance] = field(default_factory=list)

    at_umbral: bool = False

    # CORRECCIÓN: este flag ahora significa "actualmente está en -5 y ya se aplicaron efectos de entrar a -5"
    at_minus5: bool = False

    def __post_init__(self) -> None:
        if self.sanity_max is None:
            self.sanity_max = self.sanity


@dataclass
class MonsterState:
    monster_id: str
    room: RoomId


@dataclass
class DeckState:
    cards: List[CardId]
    top: int = 0

    def remaining(self) -> int:
        return max(0, len(self.cards) - self.top)


@dataclass
class RoomState:
    room_id: RoomId
    deck: DeckState
    revealed: int = 0

    # P1: Sistema de habitaciones especiales
    special_card_id: Optional[str] = None  # ID de la habitación especial ("CAMARA_LETAL", "PEEK", etc.)
    special_revealed: bool = False          # Si la carta especial ha sido revelada
    special_destroyed: bool = False         # Si fue destruida por monstruo
    special_activation_count: int = 0       # Contador de activaciones (para Salón de Belleza, etc.)


@dataclass
class BoxState:
    box_id: str
    deck: DeckState


def ensure_canonical_rooms(state: "GameState") -> None:
    from engine.board import canonical_room_ids, corridor_id, FLOORS

    for rid in canonical_room_ids():
        if rid not in state.rooms:
            state.rooms[rid] = RoomState(room_id=rid, deck=DeckState(cards=[]))
    for floor in range(1, FLOORS + 1):
        rid = corridor_id(floor)
        if rid not in state.rooms:
            state.rooms[rid] = RoomState(room_id=rid, deck=DeckState(cards=[]))


@dataclass
class GameState:
    round: int
    players: Dict[PlayerId, PlayerState]

    monsters: List[MonsterState] = field(default_factory=list)
    rooms: Dict[RoomId, RoomState] = field(default_factory=dict)
    boxes: Dict[str, BoxState] = field(default_factory=dict)
    box_at_room: Dict[RoomId, str] = field(default_factory=dict)

    # Rey
    king_floor: int = 1
    king_vanish_ends: int = 0
    false_king_floor: Optional[int] = None  # P0.4b: Falso Rey en piso (None = no existe)
    false_king_round_appeared: Optional[int] = None  # Ronda en que CROWN activó Falso Rey

    # Escaleras
    stairs: Dict[int, RoomId] = field(default_factory=dict)

    # Máquina de estados
    phase: str = "PLAYER"  # "PLAYER" | "KING"
    turn_order: List[PlayerId] = field(default_factory=list)
    starter_pos: int = 0
    turn_pos: int = 0
    remaining_actions: Dict[PlayerId, int] = field(default_factory=dict)
    limited_action_floor_next: Optional[int] = None

    # Flags globales
    flags: Dict[str, Any] = field(default_factory=dict)

    # Cola y logs
    event_queue: List[Dict[str, Any]] = field(default_factory=list)
    
    # B2: MOTEMEY deck y estado
    motemey_deck: DeckState = field(default_factory=lambda: DeckState(cards=[]))
    motemey_event_active: bool = False  # Supuesto: hay evento MOTEMEY activo
    
    # B5: Peek flag (una vez por turno)
    peek_used_this_turn: Dict[PlayerId, bool] = field(default_factory=dict)
    
    # B6: Armory storage (por room_id, lista de items, capacidad 2)
    armory_storage: Dict[RoomId, List[str]] = field(default_factory=dict)
    action_log: List[Dict[str, Any]] = field(default_factory=list)

    # RNG seed y fin de juego
    seed: int = 0
    game_over: bool = False
    outcome: Optional[str] = None  # "WIN" | "LOSE" | None

    # CORRECCIÓN: llaves destruidas (para "llaves en juego" = KEYS_TOTAL - keys_destroyed)
    keys_destroyed: int = 0

    def __post_init__(self) -> None:
        ensure_canonical_rooms(self)

        if not self.turn_order:
            self.turn_order = sorted(self.players.keys(), key=lambda x: str(x))

        if self.turn_pos < 0 or self.turn_pos >= max(1, len(self.turn_order)):
            self.turn_pos = 0

        if self.starter_pos < 0 or self.starter_pos >= max(1, len(self.turn_order)):
            self.starter_pos = 0

        if not self.remaining_actions:
            for pid in self.turn_order:
                self.remaining_actions[pid] = 2

        if not self.stairs:
            for f in (1, 2, 3):
                self.stairs[f] = RoomId(f"F{f}_R1")

        if not self.boxes or not self.box_at_room:
            self._init_boxes()
        sync_room_decks_from_boxes(self)

    def _init_boxes(self) -> None:
        from engine.board import canonical_room_ids

        for rid in canonical_room_ids():
            box_id = str(rid)
            if box_id not in self.boxes:
                if rid in self.rooms:
                    deck = self.rooms[rid].deck
                else:
                    deck = DeckState(cards=[])
                self.boxes[box_id] = BoxState(box_id=box_id, deck=deck)
            if rid not in self.box_at_room:
                self.box_at_room[rid] = box_id

    def clone(self) -> "GameState":
        return copy.deepcopy(self)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "GameState":
        players: Dict[PlayerId, PlayerState] = {}
        for pid, pdata in d["players"].items():
            statuses = [StatusInstance(**s) for s in pdata.get("statuses", [])]
            players[PlayerId(pid)] = PlayerState(
                player_id=PlayerId(pdata["player_id"]),
                sanity=pdata["sanity"],
                room=RoomId(pdata["room"]),
                sanity_max=pdata.get("sanity_max", None),
                keys=pdata.get("keys", 0),
                objects=pdata.get("objects", []),
                soulbound_items=pdata.get("soulbound_items", []),
                statuses=statuses,
                at_umbral=pdata.get("at_umbral", False),
                at_minus5=pdata.get("at_minus5", False),
            )

        monsters = [MonsterState(monster_id=m["monster_id"], room=RoomId(m["room"])) for m in d.get("monsters", [])]

        rooms: Dict[RoomId, RoomState] = {}
        for rid, rdata in d.get("rooms", {}).items():
            deck = DeckState(
                cards=[CardId(x) for x in rdata["deck"]["cards"]],
                top=rdata["deck"].get("top", 0),
            )
            rooms[RoomId(rid)] = RoomState(
                room_id=RoomId(rdata["room_id"]),
                deck=deck,
                revealed=rdata.get("revealed", 0),
            )

        boxes: Dict[str, BoxState] = {}
        for bid, bdata in d.get("boxes", {}).items():
            deck = DeckState(
                cards=[CardId(x) for x in bdata["deck"]["cards"]],
                top=bdata["deck"].get("top", 0),
            )
            boxes[str(bid)] = BoxState(box_id=str(bid), deck=deck)

        box_at_room = {RoomId(k): str(v) for k, v in d.get("box_at_room", {}).items()}

        turn_order = [PlayerId(x) for x in d.get("turn_order", list(players.keys()))]
        remaining_actions = {PlayerId(k): int(v) for k, v in d.get("remaining_actions", {}).items()}

        stairs = {int(k): RoomId(v) for k, v in d.get("stairs", {}).items()}

        return GameState(
            round=int(d["round"]),
            players=players,
            monsters=monsters,
            rooms=rooms,
            boxes=boxes,
            box_at_room=box_at_room,
            king_floor=int(d.get("king_floor", 1)),
            king_vanish_ends=int(d.get("king_vanish_ends", 0)),
            false_king_floor=int(d["false_king_floor"]) if d.get("false_king_floor") else None,
            false_king_round_appeared=int(d["false_king_round_appeared"]) if d.get("false_king_round_appeared") else None,
            stairs=stairs,
            phase=d.get("phase", "PLAYER"),
            turn_order=turn_order,
            starter_pos=int(d.get("starter_pos", 0)),
            turn_pos=int(d.get("turn_pos", 0)),
            remaining_actions=remaining_actions,
            limited_action_floor_next=d.get("limited_action_floor_next", None),
            flags=d.get("flags", {}),
            event_queue=d.get("event_queue", []),
            action_log=d.get("action_log", []),
            seed=int(d.get("seed", 0)),
            game_over=bool(d.get("game_over", False)),
            outcome=d.get("outcome", None),
            keys_destroyed=int(d.get("keys_destroyed", 0)),
        )
