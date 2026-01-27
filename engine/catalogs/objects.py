from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ObjectDefinition:
    object_id: str
    name: str
    uses: Optional[int]  # None = permanente, N = consumible N usos
    is_blunt: bool = False  # Objeto contundente (stun monstruos)
    is_treasure: bool = False  # Es tesoro (viene de Motemey)
    is_soulbound: bool = False  # Es soulbound (no puede descartarse)
    can_react: bool = False  # Puede usarse como reaccion (fuera del turno)


OBJECT_CATALOG = {
    # --- OBJETOS NORMALES ---
    # Brújula: +1 movimiento gratis, consumible, usable como reacción
    "COMPASS": ObjectDefinition("COMPASS", "Brújula", uses=1, is_blunt=False, can_react=True),
    # Vial: +2 cordura, consumible, usable como reacción
    "VIAL": ObjectDefinition("VIAL", "Vial", uses=1, is_blunt=False, can_react=True),
    # Contundente: STUN monstruo 2 turnos, consumible
    "BLUNT": ObjectDefinition("BLUNT", "Objeto Contundente", uses=1, is_blunt=True, can_react=False),
    # Cuerda: uso por definir
    "ROPE": ObjectDefinition("ROPE", "Cuerda", uses=1, is_blunt=False),
    # Escalera Portátil: subir/bajar 1 piso, consumible
    "PORTABLE_STAIRS": ObjectDefinition("PORTABLE_STAIRS", "Escalera Portátil", uses=1, is_blunt=False),
    
    # --- CUENTOS DE AMARILLO (4 objetos, mecánicamente iguales) ---
    "TALE_REPAIRER": ObjectDefinition("TALE_REPAIRER", "El Reparador de Reputaciones", uses=None, is_blunt=False),
    "TALE_MASK": ObjectDefinition("TALE_MASK", "La Máscara", uses=None, is_blunt=False),
    "TALE_DRAGON": ObjectDefinition("TALE_DRAGON", "En la Corte del Dragón", uses=None, is_blunt=False),
    "TALE_SIGN": ObjectDefinition("TALE_SIGN", "El Signo de Amarillo", uses=None, is_blunt=False),

    # --- LIBRO (Soulbound) ---
    "BOOK_CHAMBERS": ObjectDefinition("BOOK_CHAMBERS", "El Rey de Amarillo", uses=None, is_soulbound=True),
    
    # --- TESOROS (de Motemey) ---
    "TREASURE_RING": ObjectDefinition("TREASURE_RING", "Llavero", uses=None, is_blunt=False, is_treasure=True),
    "TREASURE_STAIRS": ObjectDefinition("TREASURE_STAIRS", "Escaleras Tesoro", uses=3, is_blunt=False, is_treasure=True),
    "TREASURE_SCROLL": ObjectDefinition("TREASURE_SCROLL", "Pergamino", uses=None, is_blunt=False, is_treasure=True),
    "TREASURE_PENDANT": ObjectDefinition("TREASURE_PENDANT", "Colgante", uses=None, is_blunt=False, is_treasure=True),
    
    # --- TESOROS SOULBOUND ---
    # Corona: soulbound desde inicio, activa Falso Rey
    "CROWN": ObjectDefinition("CROWN", "Corona", uses=None, is_blunt=False, is_treasure=True, is_soulbound=True),
    # Anillo: tesoro normal hasta activarse, luego soulbound
    # Al activar: todos a max cordura, portador -2/turno después
    "RING": ObjectDefinition("RING", "Anillo", uses=None, is_blunt=False, is_treasure=True, is_soulbound=False),
    # Libro de Chambers: soulbound desde inicio, vanisher del Rey
    # "CHAMBERS_BOOK": ObjectDefinition("CHAMBERS_BOOK", "Libro de Chambers", uses=None, is_blunt=False, is_treasure=True, is_soulbound=True),
    # REEMPLAZADO POR "BOOK_CHAMBERS" arriba para consistencia con nombres canónicos
}


__all__ = [
    "ObjectDefinition",
    "OBJECT_CATALOG",
]
