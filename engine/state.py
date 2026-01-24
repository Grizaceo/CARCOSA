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
    # CORRECCIÓN B: Metadata para estados complejos
    # Para TRAPPED_SPIDER: almacena monster_id fuente del trap
    metadata: Dict[str, Any] = field(default_factory=dict)


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
    
    # FASE 1: Sistema de roles
    role_id: str = "DEFAULT"  # Rol del personaje (HEALER, TANK, etc.)
    double_roll_used_this_turn: bool = False  # Para High Roller
    free_move_used_this_turn: bool = False  # Para Scout

    def __post_init__(self) -> None:
        if self.sanity_max is None:
            self.sanity_max = self.sanity


@dataclass
class MonsterState:
    monster_id: str
    room: RoomId
    # CORRECCIÓN B: STUN para monstruos
    # Contundente: 2 turnos, Liberación de trap: 1 turno
    # Rey de Amarillo: inmune (no puede ser stuneado)
    stunned_remaining_rounds: int = 0


@dataclass
class DeckState:
    cards: List[CardId]
    top: int = 0

    def remaining(self) -> int:
        return max(0, len(self.cards) - self.top)

    def draw_top(self) -> Optional[CardId]:
        """
        Extrae (peek) la carta del top sin removerla físicamente del array.
        Avanza el puntero top.
        Retorna None si no quedan cartas.
        """
        if self.remaining() <= 0:
            return None
        card = self.cards[self.top]
        self.top += 1
        return card

    def put_bottom(self, card: CardId) -> None:
        """
        Inserta una carta al fondo del mazo (después de todas las cartas físicas).
        No duplica - asume que la carta ya fue extraída/consumida del mazo.

        Implementa compactación automática: si top >= len(cards) / 2, compacta el mazo
        removiendo cartas consumidas y reiniciando top a 0.
        """
        self.cards.append(card)

        # Compactación automática para evitar crecimiento indefinido
        # Umbral: cuando top alcanza la mitad del array
        if self.top >= len(self.cards) // 2 and self.top > 0:
            # Remover cartas consumidas (antes de top)
            self.cards = self.cards[self.top:]
            self.top = 0


@dataclass
class RoomState:
    room_id: RoomId
    deck: DeckState
    revealed: int = 0

    # P1: Sistema de habitaciones especiales
    special_card_id: Optional[str] = None  # ID de la habitación especial ("CAMARA_LETAL", "TABERNA", etc.)
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

    # CORRECCIÓN D: Sistema de elección de 2 pasos para Motemey
    # Almacena {player_id: [card1, card2]} cuando jugador inicia compra
    # None cuando no hay elección pendiente
    pending_motemey_choice: Optional[Dict[str, List[CardId]]] = None
    
    # B5: Taberna flag (una vez por turno)
    taberna_used_this_turn: Dict[PlayerId, bool] = field(default_factory=dict)
    
    # B5: PEEK flag (una vez por turno)
    peek_used_this_turn: Dict[PlayerId, bool] = field(default_factory=dict)
    
    # CANON Fix #C: Last peek data for UI/Serialization
    # List of {"room": str, "card": str}
    last_peek: Optional[List[Dict[str, str]]] = None
    
    # Reina Helada: jugadores con movimiento bloqueado (turno de entrada)
    # Se limpia al inicio del siguiente turno
    movement_blocked_players: List[PlayerId] = field(default_factory=list)
    
    # B6: Armory storage (por room_id, lista de items, capacidad 2)
    armory_storage: Dict[RoomId, List[str]] = field(default_factory=dict)
    action_log: List[Dict[str, Any]] = field(default_factory=list)

    # RNG seed y fin de juego
    seed: int = 0
    game_over: bool = False
    outcome: Optional[str] = None  # "WIN" | "LOSE" | None

    # CORRECCIÓN: llaves destruidas (para "llaves en juego" = KEYS_TOTAL - keys_destroyed)
    keys_destroyed: int = 0
    
    # FASE 2: Pozo de descarte común (objetos, estados expirados, etc.)
    discard_pile: List[str] = field(default_factory=list)
    
    # FASE 4: Libro de Chambers y Vanish del Rey
    chambers_book_holder: Optional[PlayerId] = None  # Quién tiene el Libro
    chambers_tales_attached: int = 0  # Cuentos unidos (0-4)
    king_vanished_turns: int = 0  # Turnos restantes de vanish del Rey
    
    # Estado de Habitaciones Especiales
    salon_belleza_uses: int = 0  # Contador de activaciones del Salón (3er uso -> Vanidad)
    tue_tue_revelations: int = 0  # Contador de revelaciones de Tue-Tue
    
    # Anillo activado (para efecto de -2 cordura/turno)
    ring_activated_by: Optional[PlayerId] = None

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
                base_actions = 2
                # Scout tiene +1 acción adicional
                player = self.players.get(pid)
                if player and getattr(player, "role_id", "") == "SCOUT":
                    base_actions = 3
                self.remaining_actions[pid] = base_actions

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
                # P1: Campos de habitaciones especiales
                special_card_id=rdata.get("special_card_id", None),
                special_revealed=rdata.get("special_revealed", False),
                special_destroyed=rdata.get("special_destroyed", False),
                special_activation_count=rdata.get("special_activation_count", 0),
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

        # B2: MOTEMEY deck
        motemey_deck_data = d.get("motemey_deck")
        if motemey_deck_data:
            motemey_deck = DeckState(
                cards=[CardId(x) for x in motemey_deck_data.get("cards", [])],
                top=motemey_deck_data.get("top", 0),
            )
        else:
            motemey_deck = DeckState(cards=[])

        # CORRECCIÓN D: Motemey pending choice
        pending_motemey_choice_data = d.get("pending_motemey_choice")
        pending_motemey_choice = None
        if pending_motemey_choice_data:
            pending_motemey_choice = {
                pid: [CardId(c) for c in cards]
                for pid, cards in pending_motemey_choice_data.items()
            }

        # B5: Taberna used this turn
        taberna_used_this_turn_data = d.get("taberna_used_this_turn", {})
        taberna_used_this_turn = {PlayerId(k): bool(v) for k, v in taberna_used_this_turn_data.items()}

        # B5: PEEK used this turn
        peek_used_this_turn_data = d.get("peek_used_this_turn", {})
        peek_used_this_turn = {PlayerId(k): bool(v) for k, v in peek_used_this_turn_data.items()}

        # B6: Armory storage
        armory_storage = {RoomId(k): list(v) for k, v in d.get("armory_storage", {}).items()}

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
            # B2: MOTEMEY
            motemey_deck=motemey_deck,
            motemey_event_active=bool(d.get("motemey_event_active", False)),
            pending_motemey_choice=pending_motemey_choice,
            # B5: TABERNA
            taberna_used_this_turn=taberna_used_this_turn,
            # B5: PEEK
            peek_used_this_turn=peek_used_this_turn,
            last_peek=d.get("last_peek"),
            # B6: ARMORY
            armory_storage=armory_storage,
            # Reina Helada: movimiento bloqueado
            movement_blocked_players=[PlayerId(x) for x in d.get("movement_blocked_players", [])],
            
            # FASE 3: Habitaciones Especiales
            salon_belleza_uses=int(d.get("salon_belleza_uses", 0)),
            tue_tue_revelations=int(d.get("tue_tue_revelations", 0)),
            
            # FASE 4: Libro Chambers y Vanish
            chambers_book_holder=PlayerId(d["chambers_book_holder"]) if d.get("chambers_book_holder") else None,
            chambers_tales_attached=int(d.get("chambers_tales_attached", 0)),
            king_vanished_turns=int(d.get("king_vanished_turns", 0)),
            
            # Anillo
            ring_activated_by=PlayerId(d["ring_activated_by"]) if d.get("ring_activated_by") else None,
        )
