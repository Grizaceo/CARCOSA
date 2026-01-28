"""
Sistema de objetos con efectos.

Define el catálogo de objetos y sus efectos cuando se usan.

SISTEMA CANÓNICO DE OBJETOS (2026-01-21):
=========================================

CATEGORÍAS:
-----------
1. OBJETO NORMAL: Consumible o permanente, NO soulbound
   - Ejemplos: Brújula, Vial, Contundente, Cuerda

2. TESORO: Objetos especiales del mazo de Motemey
   - Ejemplos: Llavero, Escaleras, Pergamino, Colgante

3. TESORO SOULBOUND: Ligados permanentemente al jugador
   - Corona: Activa Falso Rey, no ocupa slot
   - Anillo: Tesoro especial, no puede descartarse

REGLAS SOULBOUND:
-----------------
- NO se puede intercambiar, dropear ni transferir
- Efectos de descarte (d6=6 del Rey) NO eliminan objetos Soulbound
- No ocupan slots de objetos normales

NOTA: Las LLAVES son entidad separada (slot propio por rol de personaje)
"""

from engine.catalogs.objects import OBJECT_CATALOG
from engine.handlers.objects import get_object_use_handler, register_object_use
from engine.state import GameState, PlayerState
from engine.types import PlayerId


def is_soulbound(object_id: str) -> bool:
    """Retorna True si el objeto es soulbound (no puede descartarse)."""
    if object_id == "CHAMBERS_BOOK":
        object_id = "BOOK_CHAMBERS"
    obj_def = OBJECT_CATALOG.get(object_id)
    return obj_def.is_soulbound if obj_def else False


def can_discard(object_id: str) -> bool:
    """Retorna True si el objeto PUEDE ser descartado (no es soulbound)."""
    return not is_soulbound(object_id)



def use_object(s: GameState, pid: PlayerId, object_id: str, cfg, rng) -> bool:
    """
    Usa un objeto del inventario.
    Retorna True si se usó exitosamente.
    """
    p = s.players[pid]
    if object_id not in p.objects:
        return False

    obj_def = OBJECT_CATALOG.get(object_id)
    if obj_def is None:
        return False

    # Aplicar efecto segun tipo
    handler = get_object_use_handler(object_id)
    if handler is not None:
        handler(s, pid, cfg, rng)
    # Nota: TREASURE_RING tiene efecto pasivo, no se "usa"
    # ... mas objetos ...

    # Consumir si tiene usos limitados
    if obj_def.uses is not None:
        remaining = int(p.object_charges.get(object_id, obj_def.uses))
        remaining -= 1
        if remaining <= 0:
            if object_id in p.objects:
                p.objects.remove(object_id)
            if object_id in p.object_charges:
                del p.object_charges[object_id]
        else:
            p.object_charges[object_id] = remaining

    return True


def _use_compass(s: GameState, pid: PlayerId, cfg) -> None:
    """Brújula: Mueve al pasillo del piso actual. Acción gratuita."""
    from engine.board import floor_of, corridor_id
    p = s.players[pid]
    floor = floor_of(p.room)
    p.room = corridor_id(floor)


def _use_vial(s: GameState, pid: PlayerId, cfg) -> None:
    """Vial: Recupera 2 de cordura. Acción gratuita."""
    p = s.players[pid]
    p.sanity = min(p.sanity + 2, get_effective_sanity_max(p))


def _use_blunt(s: GameState, pid: PlayerId, cfg) -> None:
    """
    CORRECCIÓN B: Objeto Contundente aturde monstruo en la habitación por 2 turnos.
    Actualizado para Canon 4.0:
    - Ice Servant: Muere.
    - Goblin: Drop loot.
    - Bogeyman: Free victim.
    """
    p = s.players[pid]
    for monster in s.monsters:
        if monster.room == p.room:
            mid = monster.monster_id
            
            # BABY_SPIDER: Stun = Die? 
            if "BABY_SPIDER" in mid:
                  s.monsters.remove(monster)
                  break

            # ICE_SERVANT: "si se stunea se retira del tablero"
            if "ICE_SERVANT" in mid or "REINA_HELADA" in mid:
                if "ICE_SERVANT" in mid:
                    s.monsters.remove(monster)
                    break
            
            # Rey de Amarillo es inmune al STUN
            if "YELLOW_KING" not in mid and "KING" not in mid:
                monster.stunned_remaining_rounds = max(monster.stunned_remaining_rounds, 2)
                
                # GOBLIN: Drop Loot
                if "DUENDE" in mid or "GOBLIN" in mid:
                    loot_objects = s.flags.get(f"GOBLIN_LOOT_OBJECTS_{mid}")
                    loot_keys = s.flags.get(f"GOBLIN_LOOT_KEYS_{mid}", 0)
                    
                    if loot_objects:
                        from engine.inventory import add_object
                        for obj_id in loot_objects:
                            if not add_object(s, pid, obj_id, discard_choice=None):
                                s.discard_pile.append(obj_id)
                        del s.flags[f"GOBLIN_LOOT_OBJECTS_{mid}"]

                    if loot_keys > 0:
                        from engine.inventory import can_add_key
                        for _ in range(int(loot_keys)):
                            if can_add_key(p):
                                p.keys += 1
                            else:
                                s.keys_destroyed += 1
                        del s.flags[f"GOBLIN_LOOT_KEYS_{mid}"]
                        
                    s.flags[f"GOBLIN_HAS_LOOT_{mid}"] = False
                    
                # BOGEYMAN: Release Victim
                if "VIEJO" in mid or "SACK" in mid:
                    for target_pid, target_p in s.players.items():
                        new_statuses = []
                        released = False
                        for st in target_p.statuses:
                            if st.status_id == "TRAPPED" and st.metadata.get("source_monster_id") == mid:
                                released = True
                            else:
                                new_statuses.append(st)
                        target_p.statuses = new_statuses
                        
                        if released:
                            s.flags[f"SACK_HAS_VICTIM_{mid}"] = False

            break


def _use_treasure_stairs(s: GameState, pid: PlayerId, cfg) -> None:
    """
    Escaleras (Tesoro): 3 usos. Coloca escalera temporal en habitación actual.
    Dura solo por el turno del jugador que la activa.
    """
    p = s.players[pid]
    # Registrar escalera temporal (válida solo este turno)
    s.flags[f"TEMP_STAIRS_{p.room}"] = {"round": s.round, "pid": str(pid)}

    # Decrementar usos (manejado automáticamente por el sistema en use_object)


@register_object_use("COMPASS")
def _handle_object_compass(s: GameState, pid: PlayerId, cfg, rng) -> None:
    _use_compass(s, pid, cfg)


@register_object_use("VIAL")
def _handle_object_vial(s: GameState, pid: PlayerId, cfg, rng) -> None:
    _use_vial(s, pid, cfg)


@register_object_use("BLUNT")
def _handle_object_blunt(s: GameState, pid: PlayerId, cfg, rng) -> None:
    _use_blunt(s, pid, cfg)


@register_object_use("TREASURE_STAIRS")
def _handle_object_treasure_stairs(s: GameState, pid: PlayerId, cfg, rng) -> None:
    _use_treasure_stairs(s, pid, cfg)


def has_treasure_ring(p: PlayerState) -> bool:
    """Verifica si el jugador tiene el tesoro Llavero (efecto pasivo)."""
    return "TREASURE_RING" in p.objects


def get_max_keys_capacity(p: PlayerState) -> int:
    """
    Retorna la capacidad máxima de llaves del jugador.
    Base: slots por rol
    +1 si tiene Llavero (TREASURE_RING)
    """
    from engine.roles import get_key_slots
    base_capacity = get_key_slots(getattr(p, "role_id", ""))
    if has_treasure_ring(p):
        base_capacity += 1
    return base_capacity


def get_effective_sanity_max(p: PlayerState) -> int:
    """
    Retorna la cordura máxima efectiva del jugador.
    Base: sanity_max del jugador (o 5 si no está definido)
    +1 si tiene Llavero (TREASURE_RING)
    """
    base_max = p.sanity_max if p.sanity_max is not None else 5
    if has_treasure_ring(p):
        base_max += 1
    return base_max
