"""
Sistema de Memoria de Cartas para Bots — CARCOSA

Implementa memoria individual (2 slots/bot) y memoria de equipo compartida.
La priorización es COLABORATIVA: el equipo decide quién recuerda qué carta
para maximizar el tracking colectivo.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.state import GameState
    from engine.types import PlayerId, RoomId


# Prioridades de cartas (menor = más importante)
PRIORITY_KEY = 1
PRIORITY_MONSTER = 2
PRIORITY_TRAP = 2
PRIORITY_TREASURE = 3
PRIORITY_EVENT = 4
PRIORITY_OMEN = 4
PRIORITY_OTHER = 5

# Decay: cartas se olvidan después de N rondas
MEMORY_DECAY_ROUNDS = 5


def card_priority(card_id: str) -> int:
    """Determina prioridad de una carta por su ID/tipo."""
    card_upper = card_id.upper()
    if "KEY" in card_upper or "LLAVE" in card_upper:
        return PRIORITY_KEY
    if "MONSTER" in card_upper or any(m in card_upper for m in [
        "ARAÑA", "SPIDER", "REINA", "QUEEN", "BRUJO", "SORCERER",
        "SIRVIENTE", "SERVANT", "TUE_TUE"
    ]):
        return PRIORITY_MONSTER
    if "TRAP" in card_upper or "TRAMPA" in card_upper:
        return PRIORITY_TRAP
    if "TREASURE" in card_upper or "TESORO" in card_upper:
        return PRIORITY_TREASURE
    if "EVENT" in card_upper or "EVENTO" in card_upper:
        return PRIORITY_EVENT
    if "OMEN" in card_upper or "PRESAGIO" in card_upper:
        return PRIORITY_OMEN
    return PRIORITY_OTHER


@dataclass
class CardMemory:
    """Memoria de una carta específica."""
    card_id: str
    box_id: str  # Box donde está (estable entre rotaciones)
    position_in_deck: int  # Posición en el mazo (0=siguiente a salir)
    priority: int  # 1=KEY, 2=MONSTER, etc.
    rounds_since_seen: int = 0  # Envejece cada ronda
    
    # Calculado dinámicamente
    current_room: Optional[str] = None  # Se actualiza con box_at_room
    
    def age(self) -> None:
        """Incrementa edad de la memoria."""
        self.rounds_since_seen += 1
    
    def is_expired(self) -> bool:
        """True si la memoria expiró."""
        return self.rounds_since_seen > MEMORY_DECAY_ROUNDS
    
    def __hash__(self):
        return hash((self.card_id, self.box_id, self.position_in_deck))
    
    def __eq__(self, other):
        if not isinstance(other, CardMemory):
            return False
        return (self.card_id == other.card_id and 
                self.box_id == other.box_id and
                self.position_in_deck == other.position_in_deck)


@dataclass
class BotMemory:
    """Memoria individual de un bot."""
    player_id: str
    max_slots: int = 2
    remembered_cards: List[CardMemory] = field(default_factory=list)
    
    def can_add(self, card: CardMemory) -> bool:
        """True si puede agregar esta carta."""
        if len(self.remembered_cards) < self.max_slots:
            return True
        # Puede reemplazar si hay una de menor prioridad (número mayor)
        worst = max(self.remembered_cards, key=lambda c: c.priority)
        return card.priority < worst.priority
    
    def add_memory(self, card: CardMemory) -> Optional[CardMemory]:
        """
        Agrega carta a la memoria. Si está llena, reemplaza la menos prioritaria.
        Returns: carta reemplazada (si hubo) o None
        """
        # Evitar duplicados
        if any(c.card_id == card.card_id and c.box_id == card.box_id for c in self.remembered_cards):
            return None
        
        if len(self.remembered_cards) < self.max_slots:
            self.remembered_cards.append(card)
            return None
        
        # Reemplazar la menos prioritaria
        worst_idx = max(range(len(self.remembered_cards)), 
                       key=lambda i: self.remembered_cards[i].priority)
        replaced = self.remembered_cards[worst_idx]
        
        if card.priority < replaced.priority:
            self.remembered_cards[worst_idx] = card
            return replaced
        return None
    
    def remove_memory(self, card_id: str) -> None:
        """Remueve carta de la memoria."""
        self.remembered_cards = [c for c in self.remembered_cards if c.card_id != card_id]
    
    def age_memories(self) -> List[CardMemory]:
        """
        Envejece todas las memorias y remueve las expiradas.
        Returns: lista de cartas olvidadas
        """
        forgotten = []
        for card in self.remembered_cards:
            card.age()
            if card.is_expired():
                forgotten.append(card)
        
        self.remembered_cards = [c for c in self.remembered_cards if not c.is_expired()]
        return forgotten
    
    def get_slots_available(self) -> int:
        """Slots disponibles."""
        return self.max_slots - len(self.remembered_cards)
    
    def get_priority_targets(self, priority_filter: Optional[int] = None) -> List[CardMemory]:
        """
        Obtiene cartas recordadas filtradas por prioridad.
        Si priority_filter es None, retorna todas ordenadas por prioridad.
        """
        cards = self.remembered_cards
        if priority_filter is not None:
            cards = [c for c in cards if c.priority == priority_filter]
        return sorted(cards, key=lambda c: c.priority)


@dataclass
class TeamMemory:
    """Memoria compartida del equipo de bots."""
    
    # Tracking de posición de boxes (sincronizado del state)
    box_at_room: Dict[str, str] = field(default_factory=dict)  # room_id → box_id
    room_for_box: Dict[str, str] = field(default_factory=dict)  # box_id → room_id (inverso)
    
    # Pool de todas las cartas conocidas por el equipo
    known_cards: List[CardMemory] = field(default_factory=list)
    
    # Asignación: qué bot recuerda qué carta
    assignments: Dict[str, Set[str]] = field(default_factory=dict)  # player_id → {card_ids}
    
    # Cartas ya sacadas (para no buscarlas)
    removed_cards: Set[str] = field(default_factory=set)
    
    def sync_from_state(self, state: "GameState") -> None:
        """Sincroniza posiciones de boxes desde el estado del juego."""
        self.box_at_room = {str(k): str(v) for k, v in state.box_at_room.items()}
        # Crear inverso
        self.room_for_box = {v: k for k, v in self.box_at_room.items()}
        
        # Actualizar current_room de todas las cartas conocidas
        for card in self.known_cards:
            card.current_room = self.room_for_box.get(card.box_id)
    
    def share_card(self, card: CardMemory, from_player: str) -> None:
        """
        Un bot comparte una carta que vio con el equipo.
        La carta se agrega al pool conocido.
        """
        # Evitar duplicados
        existing = next((c for c in self.known_cards 
                        if c.card_id == card.card_id and c.box_id == card.box_id), None)
        if existing:
            # Actualizar posición si cambió
            existing.position_in_deck = card.position_in_deck
            existing.rounds_since_seen = 0  # Reset age si se vio de nuevo
            return
        
        self.known_cards.append(card)
    
    def mark_card_removed(self, card_id: str) -> None:
        """Marca una carta como sacada (ya no está en ningún mazo)."""
        self.removed_cards.add(card_id)
        self.known_cards = [c for c in self.known_cards if c.card_id not in self.removed_cards]
    
    def optimize_assignments(self, bots: Dict[str, "BotMemory"]) -> None:
        """
        Distribuye las cartas conocidas entre los bots de forma óptima.
        
        Estrategia:
        1. Ordenar cartas por prioridad (KEY primero)
        2. Asignar a bots con slots disponibles
        3. Si todos llenos, reemplazar cartas menos prioritarias
        """
        if not bots:
            return
        
        # Limpiar asignaciones actuales
        self.assignments = {pid: set() for pid in bots.keys()}
        for bot in bots.values():
            bot.remembered_cards.clear()
        
        # Ordenar cartas por prioridad (menor = más importante)
        sorted_cards = sorted(self.known_cards, key=lambda c: (c.priority, c.rounds_since_seen))
        
        # Distribuir entre bots (round-robin por prioridad)
        bot_list = list(bots.values())
        bot_idx = 0
        
        for card in sorted_cards:
            # Buscar un bot que pueda recordar esta carta
            attempts = 0
            while attempts < len(bot_list):
                target_bot = bot_list[bot_idx]
                if target_bot.can_add(card):
                    replaced = target_bot.add_memory(card)
                    self.assignments[target_bot.player_id].add(card.card_id)
                    if replaced:
                        self.assignments[target_bot.player_id].discard(replaced.card_id)
                    break
                
                bot_idx = (bot_idx + 1) % len(bot_list)
                attempts += 1
            
            # Avanzar al siguiente bot para distribuir equitativamente
            bot_idx = (bot_idx + 1) % len(bot_list)
    
    def age_all_memories(self, bots: Dict[str, "BotMemory"]) -> None:
        """Envejece todas las memorias y limpia las expiradas."""
        # Envejecer cartas conocidas
        for card in self.known_cards:
            card.age()
        self.known_cards = [c for c in self.known_cards if not c.is_expired()]
        
        # Envejecer memorias individuales
        for bot in bots.values():
            forgotten = bot.age_memories()
            for card in forgotten:
                self.assignments.get(bot.player_id, set()).discard(card.card_id)
    
    def get_best_targets(self, priority_filter: Optional[int] = None) -> List[str]:
        """
        Obtiene las habitaciones donde hay cartas de interés.
        
        Returns: Lista de room_ids ordenados por prioridad de carta
        """
        cards = self.known_cards
        if priority_filter is not None:
            cards = [c for c in cards if c.priority == priority_filter]
        
        # Filtrar cartas con posición conocida
        cards = [c for c in cards if c.current_room is not None]
        
        # Ordenar por prioridad y retornar rooms únicos
        sorted_cards = sorted(cards, key=lambda c: (c.priority, c.rounds_since_seen))
        seen_rooms: Set[str] = set()
        result = []
        for card in sorted_cards:
            if card.current_room and card.current_room not in seen_rooms:
                seen_rooms.add(card.current_room)
                result.append(card.current_room)
        
        return result
    
    def get_key_rooms(self) -> List[str]:
        """Obtiene habitaciones con llaves conocidas."""
        return self.get_best_targets(PRIORITY_KEY)
    
    def get_threat_rooms(self) -> List[str]:
        """Obtiene habitaciones con amenazas conocidas (monstruos/trampas)."""
        return self.get_best_targets(PRIORITY_MONSTER)
    
    def get_card_info(self, room_id: str) -> List[CardMemory]:
        """Obtiene información de cartas conocidas en una habitación."""
        return [c for c in self.known_cards if c.current_room == room_id]


def create_team_memory() -> TeamMemory:
    """Factory para crear memoria de equipo."""
    return TeamMemory()


def create_bot_memories(player_ids: List[str]) -> Dict[str, BotMemory]:
    """Factory para crear memorias individuales para todos los bots."""
    return {pid: BotMemory(player_id=pid) for pid in player_ids}


__all__ = [
    "CardMemory",
    "BotMemory", 
    "TeamMemory",
    "card_priority",
    "create_team_memory",
    "create_bot_memories",
    "PRIORITY_KEY",
    "PRIORITY_MONSTER",
    "PRIORITY_TRAP",
    "PRIORITY_TREASURE",
    "PRIORITY_EVENT",
    "PRIORITY_OMEN",
]
