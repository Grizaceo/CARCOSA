#!/usr/bin/env python3
"""
Patch GoalDirectedPlayerPolicy with improved sanity management.
Run from repo root: python tools/patch_policies.py
"""
from pathlib import Path

POLICIES_PATH = Path(__file__).parent.parent / "sim" / "policies.py"
src = POLICIES_PATH.read_text(encoding="utf-8")

patches_applied = 0

def apply_patch(label, old, new):
    global src, patches_applied
    if old in src:
        src = src.replace(old, new, 1)
        print(f"  OK: {label}")
        patches_applied += 1
    else:
        print(f"  SKIP (already applied or not found): {label}")


# ============================================================
# PATCH 1: dataclass fields + __post_init__
# ============================================================
apply_patch(
    "fields + __post_init__",
    '    meditate_critical: int = -3\n'
    '    # Diferencia m\u00ednima de cartas para cambiar a otro piso\n'
    '    move_for_better_delta: int = 2\n'
    '    # M\u00ednimo de cartas locales para preferir SEARCH\n'
    '    search_local_min_remaining: int = 1\n'
    '    # Margen de uso de VIAL vs umbral de meditar\n'
    '    vial_margin: int = 1\n'
    '    # Endgame: forzar umbral agresivamente\n'
    '    endgame_force_umbral: bool = True\n'
    '\n'
    '    def __post_init__(self) -> None:\n'
    '        params = _load_policy_params()\n'
    '        if not isinstance(params, dict):\n'
    '            return\n'
    '        self.meditate_critical = int(params.get("meditate_critical", self.meditate_critical))\n'
    '        self.move_for_better_delta = int(params.get("move_for_better_delta", self.move_for_better_delta))\n'
    '        self.search_local_min_remaining = int(params.get("search_local_min_remaining", self.search_local_min_remaining))\n'
    '        self.vial_margin = int(params.get("vial_margin", self.vial_margin))\n'
    '        self.endgame_force_umbral = bool(params.get("endgame_force_umbral", self.endgame_force_umbral))\n'
    '        # Sistema de memoria (se configura desde runner.py)\n'
    '        self._team_memory = None\n'
    '        self._bot_memories = None',

    '    meditate_critical: int = -2\n'
    '    # Diferencia m\u00ednima de cartas para cambiar a otro piso\n'
    '    move_for_better_delta: int = 2\n'
    '    # M\u00ednimo de cartas locales para preferir SEARCH\n'
    '    search_local_min_remaining: int = 1\n'
    '    # Margen de uso de VIAL vs umbral de meditar\n'
    '    vial_margin: int = 1\n'
    '    # Endgame: forzar umbral agresivamente\n'
    '    endgame_force_umbral: bool = True\n'
    '    # Huir del piso del Rey si sanidad <= este valor\n'
    '    king_flee_sanity: int = 2\n'
    '    # Ronda a partir de la cual el Rey hace da\u00f1o severo (4/ronda)\n'
    '    king_flee_round_threshold: int = 9\n'
    '    # Bonus adicional al umbral de meditar en late game\n'
    '    late_game_meditate_bonus: int = 2\n'
    '    # No buscar si cordura por debajo de este valor\n'
    '    search_sanity_min: int = -1\n'
    '\n'
    '    def __post_init__(self) -> None:\n'
    '        params = _load_policy_params()\n'
    '        if not isinstance(params, dict):\n'
    '            self._role_sanity_bias: Dict[str, int] = {}\n'
    '            self._team_memory = None\n'
    '            self._bot_memories = None\n'
    '            return\n'
    '        self.meditate_critical = int(params.get("meditate_critical", self.meditate_critical))\n'
    '        self.move_for_better_delta = int(params.get("move_for_better_delta", self.move_for_better_delta))\n'
    '        self.search_local_min_remaining = int(params.get("search_local_min_remaining", self.search_local_min_remaining))\n'
    '        self.vial_margin = int(params.get("vial_margin", self.vial_margin))\n'
    '        self.endgame_force_umbral = bool(params.get("endgame_force_umbral", self.endgame_force_umbral))\n'
    '        self.king_flee_sanity = int(params.get("king_flee_sanity", self.king_flee_sanity))\n'
    '        self.king_flee_round_threshold = int(params.get("king_flee_round_threshold", self.king_flee_round_threshold))\n'
    '        self.late_game_meditate_bonus = int(params.get("late_game_meditate_bonus", self.late_game_meditate_bonus))\n'
    '        self.search_sanity_min = int(params.get("search_sanity_min", self.search_sanity_min))\n'
    '        self._role_sanity_bias = dict(params.get("role_sanity_bias", {}))\n'
    '        # Sistema de memoria (se configura desde runner.py)\n'
    '        self._team_memory = None\n'
    '        self._bot_memories = None'
)

# ============================================================
# PATCH 2: meditate_threshold calculation
# ============================================================
apply_patch(
    "meditate_threshold logic",
    '        danger = _danger_score(state, pid)\n'
    '        meditate_threshold = self.meditate_critical\n'
    '        key_carrier = p.keys > 0\n'
    '        team_low, team_critical = _team_fragility(state)\n'
    '        if danger > 0:\n'
    '            meditate_threshold += 1\n'
    '        if danger >= 2:\n'
    '            meditate_threshold += 1\n'
    '        if team_critical >= 1:\n'
    '            meditate_threshold += 1\n'
    '        if key_carrier:\n'
    '            meditate_threshold += 1\n'
    '        \n'
    '        # === NUEVOS FACTORES DE RIESGO ===\n'
    '        \n'
    '        # Factor: Piso del Rey -> m\u00e1s riesgo si est\u00e1s en su piso\n'
    '        if floor_of(p.room) == state.king_floor:\n'
    '            if p.sanity <= 1:\n'
    '                meditate_threshold += 2  # Muy cr\u00edtico en piso del Rey con baja cordura\n'
    '            else:\n'
    '                meditate_threshold += 1\n'
    '        \n'
    '        # Factor: TALE en mano -> proteger valor similar a llaves\n'
    '        has_tale = any("TALE" in obj for obj in p.objects)\n'
    '        if has_tale:\n'
    '            meditate_threshold += 1\n'
    '        \n'
    '        # Factor: Ronda actual -> late game prioriza velocidad sobre seguridad\n'
    '        if state.round > 25:\n'
    '            meditate_threshold -= 1  # Menos conservador en late game\n'
    '        elif state.round > 35:\n'
    '            meditate_threshold -= 2  # Mucho menos conservador en muy late game\n'
    '        \n'
    '        # Factor: Capacidad de sacrificio restante -> si no puede sacrificar, meditar m\u00e1s urgente\n'
    '        can_sacrifice = p.object_slots_penalty < 2 and (p.sanity_max or 5) > -3\n'
    '        if not can_sacrifice and p.sanity <= 0:\n'
    '            meditate_threshold += 2  # Sin sacrificio disponible, urgente meditar\n'
    '        \n'
    '        meditate_threshold = min(meditate_threshold, 0)  # Cap menos restrictivo (-2 -> 0)',

    '        danger = _danger_score(state, pid)\n'
    '        role_id = getattr(p, "role_id", None)\n'
    '        role_bias = int((self._role_sanity_bias or {}).get(str(role_id) if role_id else "", 0))\n'
    '        late_game = state.round > self.king_flee_round_threshold\n'
    '        on_king_floor = floor_of(p.room) == state.king_floor\n'
    '        meditate_threshold = self.meditate_critical + role_bias\n'
    '        key_carrier = p.keys > 0\n'
    '        team_low, team_critical = _team_fragility(state)\n'
    '        if danger > 0:\n'
    '            meditate_threshold += 1\n'
    '        if danger >= 2:\n'
    '            meditate_threshold += 1\n'
    '        if team_critical >= 1:\n'
    '            meditate_threshold += 1\n'
    '        if key_carrier:\n'
    '            meditate_threshold += 1\n'
    '\n'
    '        # === FACTORES DE RIESGO ===\n'
    '\n'
    '        # Factor: Piso del Rey -> siempre cr\u00edtico\n'
    '        if on_king_floor:\n'
    '            meditate_threshold += 2\n'
    '\n'
    '        # Factor: Late game - el Rey hace 4 da\u00f1o/ronda desde round 10\n'
    '        if late_game:\n'
    '            meditate_threshold += self.late_game_meditate_bonus\n'
    '\n'
    '        # Factor: TALE en mano -> proteger valor similar a llaves\n'
    '        has_tale = any("TALE" in obj for obj in p.objects)\n'
    '        if has_tale:\n'
    '            meditate_threshold += 1\n'
    '\n'
    '        # Factor: Capacidad de sacrificio restante -> si no puede sacrificar, meditar m\u00e1s urgente\n'
    '        can_sacrifice = p.object_slots_penalty < 2 and (p.sanity_max or 5) > -3\n'
    '        if not can_sacrifice and p.sanity <= 0:\n'
    '            meditate_threshold += 2  # Sin sacrificio disponible, urgente meditar\n'
    '\n'
    '        meditate_threshold = min(meditate_threshold, 1)  # Cap: nunca exigir m\u00e1s que sanity<=1'
)

# ============================================================
# PATCH 3: King floor flee before panic meditate
# ============================================================
apply_patch(
    "king floor flee logic",
    '        # 1) Panico extremo: meditar si existe\n'
    '        if p.sanity <= self.cfg.PLAYER_SANITY_PANIC:\n'
    '            a = _pick_first(acts, ActionType.MEDITATE)\n'
    '            if a:\n'
    '                return finalize(a)\n'
    '\n'
    '        # 2) Supervivencia inmediata si hay peligro alto\n'
    '        if danger > 0 and p.sanity <= meditate_threshold:\n'
    '            a = _pick_first(acts, ActionType.MEDITATE)\n'
    '            if a:\n'
    '                return finalize(a)',

    '        # 0.7) Huir del piso del Rey cuando el da\u00f1o es severo o la cordura est\u00e1 baja\n'
    '        if on_king_floor and p.sanity <= self.king_flee_sanity:\n'
    '            exits = [\n'
    '                a for a in acts\n'
    '                if a.type == ActionType.MOVE\n'
    '                and floor_of(RoomId(a.data.get("to", str(p.room)))) != state.king_floor\n'
    '            ]\n'
    '            if exits:\n'
    '                safest = min(exits, key=lambda a: _danger_score_room(state, RoomId(a.data.get("to"))))\n'
    '                return finalize(safest)\n'
    '\n'
    '        # 0.8) En late game forzar salida del piso del Rey sin importar la cordura\n'
    '        if late_game and on_king_floor:\n'
    '            exits = [\n'
    '                a for a in acts\n'
    '                if a.type == ActionType.MOVE\n'
    '                and floor_of(RoomId(a.data.get("to", str(p.room)))) != state.king_floor\n'
    '            ]\n'
    '            if exits:\n'
    '                safest = min(exits, key=lambda a: _danger_score_room(state, RoomId(a.data.get("to"))))\n'
    '                return finalize(safest)\n'
    '\n'
    '        # 1) Panico extremo: meditar si existe\n'
    '        if p.sanity <= self.cfg.PLAYER_SANITY_PANIC:\n'
    '            a = _pick_first(acts, ActionType.MEDITATE)\n'
    '            if a:\n'
    '                return finalize(a)\n'
    '\n'
    '        # 2) Supervivencia inmediata si hay peligro alto\n'
    '        if danger > 0 and p.sanity <= meditate_threshold:\n'
    '            a = _pick_first(acts, ActionType.MEDITATE)\n'
    '            if a:\n'
    '                return finalize(a)'
)

# ============================================================
# PATCH 4: Guard SEARCH with search_sanity_min
# ============================================================
apply_patch(
    "search sanity guard",
    '            if search_allowed and _room_remaining(state, p.room) > 0 and (danger == 0 or p.sanity > meditate_threshold):\n'
    '                a = _pick_first(acts, ActionType.SEARCH)\n'
    '                if a:\n'
    '                    return finalize(a)',

    '            if search_allowed and _room_remaining(state, p.room) > 0 and (danger == 0 or p.sanity > meditate_threshold) and p.sanity >= self.search_sanity_min:\n'
    '                a = _pick_first(acts, ActionType.SEARCH)\n'
    '                if a:\n'
    '                    return finalize(a)'
)

# ============================================================
# PATCH 5: Per-player room assignment
# ============================================================
# Replace `goal = _best_room_global(state)` in the key-progress block
OLD5 = (
    '            if key_special:\n'
    '                return finalize(key_special)\n'
    '\n'
    '            goal = _best_room_global(state)\n'
    '            current_rem = _room_remaining(state, p.room)\n'
    '            same_floor_goal = goal is not None and floor_of(goal) == floor_of(p.room)\n'
    '            search_allowed = (current_rem >= self.search_local_min_remaining) or same_floor_goal\n'
    '\n'
    '            if goal is not None and floor_of(goal) != floor_of(p.room):'
)
NEW5 = (
    '            if key_special:\n'
    '                return finalize(key_special)\n'
    '\n'
    '            goal = self._best_room_for_player(state, pid)\n'
    '            current_rem = _room_remaining(state, p.room)\n'
    '            same_floor_goal = goal is not None and floor_of(goal) == floor_of(p.room)\n'
    '            search_allowed = (current_rem >= self.search_local_min_remaining) or same_floor_goal\n'
    '\n'
    '            if goal is not None and floor_of(goal) != floor_of(p.room):'
)
apply_patch("per-player room assignment", OLD5, NEW5)

# ============================================================
# Write patched file
# ============================================================
POLICIES_PATH.write_text(src, encoding="utf-8")
print(f"\n{patches_applied} patch(es) applied. File saved.")

"""
Patch GoalDirectedPlayerPolicy with improved sanity management:
- Lower meditate_critical to -2 (loads from JSON already)
- Add new fields (king_flee, late_game_meditate_bonus, search_sanity_min)
- Update __post_init__ to load them
- Update choose() with king-flee priority and late-game conservatism
- Replace _best_room_global with per-player assignment in choose()
"""
import re
from pathlib import Path

POLICIES_PATH = Path(__file__).parent.parent / "sim" / "policies.py"

src = POLICIES_PATH.read_text(encoding="utf-8")

# ============================================================
# PATCH 1: Update dataclass fields and __post_init__
# ============================================================
OLD_FIELDS = '''    cfg: Config = Config()
    # Umbral base de "meditar por seguridad" (m\u00e1s estricto que <=1)
    meditate_critical: int = -3
    # Diferencia m\u00ednima de cartas para cambiar a otro piso
    move_for_better_delta: int = 2
    # M\u00ednimo de cartas locales para preferir SEARCH
    search_local_min_remaining: int = 1
    # Margen de uso de VIAL vs umbral de meditar
    vial_margin: int = 1
    # Endgame: forzar umbral agresivamente
    endgame_force_umbral: bool = True

    def __post_init__(self) -> None:
        params = _load_policy_params()
        if not isinstance(params, dict):
            return
        self.meditate_critical = int(params.get("meditate_critical", self.meditate_critical))
        self.move_for_better_delta = int(params.get("move_for_better_delta", self.move_for_better_delta))
        self.search_local_min_remaining = int(params.get("search_local_min_remaining", self.search_local_min_remaining))
        self.vial_margin = int(params.get("vial_margin", self.vial_margin))
        self.endgame_force_umbral = bool(params.get("endgame_force_umbral", self.endgame_force_umbral))
        # Sistema de memoria (se configura desde runner.py)
        self._team_memory = None
        self._bot_memories = None'''

NEW_FIELDS = '''    cfg: Config = Config()
    # Umbral base de "meditar por seguridad"
    meditate_critical: int = -2
    # Diferencia m\u00ednima de cartas para cambiar a otro piso
    move_for_better_delta: int = 2
    # M\u00ednimo de cartas locales para preferir SEARCH
    search_local_min_remaining: int = 1
    # Margen de uso de VIAL vs umbral de meditar
    vial_margin: int = 1
    # Endgame: forzar umbral agresivamente
    endgame_force_umbral: bool = True
    # Huir del piso del Rey si sanidad <= este valor
    king_flee_sanity: int = 2
    # Ronda a partir de la cual el Rey hace da\u00f1o severo (4/ronda)
    king_flee_round_threshold: int = 9
    # Bonus adicional al umbral de meditar en late game
    late_game_meditate_bonus: int = 2
    # No buscar si cordura por debajo de este valor
    search_sanity_min: int = -1

    def __post_init__(self) -> None:
        params = _load_policy_params()
        if not isinstance(params, dict):
            self._role_sanity_bias: Dict[str, int] = {}
            self._team_memory = None
            self._bot_memories = None
            return
        self.meditate_critical = int(params.get("meditate_critical", self.meditate_critical))
        self.move_for_better_delta = int(params.get("move_for_better_delta", self.move_for_better_delta))
        self.search_local_min_remaining = int(params.get("search_local_min_remaining", self.search_local_min_remaining))
        self.vial_margin = int(params.get("vial_margin", self.vial_margin))
        self.endgame_force_umbral = bool(params.get("endgame_force_umbral", self.endgame_force_umbral))
        self.king_flee_sanity = int(params.get("king_flee_sanity", self.king_flee_sanity))
        self.king_flee_round_threshold = int(params.get("king_flee_round_threshold", self.king_flee_round_threshold))
        self.late_game_meditate_bonus = int(params.get("late_game_meditate_bonus", self.late_game_meditate_bonus))
        self.search_sanity_min = int(params.get("search_sanity_min", self.search_sanity_min))
        self._role_sanity_bias = dict(params.get("role_sanity_bias", {}))
        # Sistema de memoria (se configura desde runner.py)
        self._team_memory = None
        self._bot_memories = None'''

assert OLD_FIELDS in src, "PATCH 1: Could not find target string"
src = src.replace(OLD_FIELDS, NEW_FIELDS, 1)
print("PATCH 1 applied: fields + __post_init__")

# ============================================================
# PATCH 2: Update meditate_threshold calculation in choose()
# ============================================================
OLD_THRESHOLD = '''        danger = _danger_score(state, pid)
        meditate_threshold = self.meditate_critical
        key_carrier = p.keys > 0
        team_low, team_critical = _team_fragility(state)
        if danger > 0:
            meditate_threshold += 1
        if danger >= 2:
            meditate_threshold += 1
        if team_critical >= 1:
            meditate_threshold += 1
        if key_carrier:
            meditate_threshold += 1
        
        # === NUEVOS FACTORES DE RIESGO ===
        
        # Factor: Piso del Rey -> m\u00e1s riesgo si est\u00e1s en su piso
        if floor_of(p.room) == state.king_floor:
            if p.sanity <= 1:
                meditate_threshold += 2  # Muy cr\u00edtico en piso del Rey con baja cordura
            else:
                meditate_threshold += 1
        
        # Factor: TALE en mano -> proteger valor similar a llaves
        has_tale = any("TALE" in obj for obj in p.objects)
        if has_tale:
            meditate_threshold += 1
        
        # Factor: Ronda actual -> late game prioriza velocidad sobre seguridad
        if state.round > 25:
            meditate_threshold -= 1  # Menos conservador en late game
        elif state.round > 35:
            meditate_threshold -= 2  # Mucho menos conservador en muy late game
        
        # Factor: Capacidad de sacrificio restante -> si no puede sacrificar, meditar m\u00e1s urgente
        can_sacrifice = p.object_slots_penalty < 2 and (p.sanity_max or 5) > -3
        if not can_sacrifice and p.sanity <= 0:
            meditate_threshold += 2  # Sin sacrificio disponible, urgente meditar
        
        meditate_threshold = min(meditate_threshold, 0)  # Cap menos restrictivo (-2 -> 0)'''

NEW_THRESHOLD = '''        danger = _danger_score(state, pid)
        role_id = getattr(p, "role_id", None)
        role_bias = int((self._role_sanity_bias or {}).get(str(role_id) if role_id else "", 0))
        late_game = state.round > self.king_flee_round_threshold
        on_king_floor = floor_of(p.room) == state.king_floor
        meditate_threshold = self.meditate_critical + role_bias
        key_carrier = p.keys > 0
        team_low, team_critical = _team_fragility(state)
        if danger > 0:
            meditate_threshold += 1
        if danger >= 2:
            meditate_threshold += 1
        if team_critical >= 1:
            meditate_threshold += 1
        if key_carrier:
            meditate_threshold += 1

        # === FACTORES DE RIESGO ===

        # Factor: Piso del Rey -> siempre cr\u00edtico
        if on_king_floor:
            meditate_threshold += 2

        # Factor: Late game - el Rey hace 4 da\u00f1o/ronda desde round 10
        if late_game:
            meditate_threshold += self.late_game_meditate_bonus

        # Factor: TALE en mano -> proteger valor similar a llaves
        has_tale = any("TALE" in obj for obj in p.objects)
        if has_tale:
            meditate_threshold += 1

        # Factor: Capacidad de sacrificio restante -> si no puede sacrificar, meditar m\u00e1s urgente
        can_sacrifice = p.object_slots_penalty < 2 and (p.sanity_max or 5) > -3
        if not can_sacrifice and p.sanity <= 0:
            meditate_threshold += 2  # Sin sacrificio disponible, urgente meditar

        meditate_threshold = min(meditate_threshold, 1)  # Cap: nunca exigir m\u00e1s que sanity<=1'''

assert OLD_THRESHOLD in src, "PATCH 2: Could not find target string"
src = src.replace(OLD_THRESHOLD, NEW_THRESHOLD, 1)
print("PATCH 2 applied: meditate_threshold logic")

# ============================================================
# PATCH 3: Add king-floor flee BEFORE panic meditate (step 0.7)
# ============================================================
OLD_PANIC = '''        # 1) Panico extremo: meditar si existe
        if p.sanity <= self.cfg.PLAYER_SANITY_PANIC:
            a = _pick_first(acts, ActionType.MEDITATE)
            if a:
                return finalize(a)

        # 2) Supervivencia inmediata si hay peligro alto
        if danger > 0 and p.sanity <= meditate_threshold:
            a = _pick_first(acts, ActionType.MEDITATE)
            if a:
                return finalize(a)'''

NEW_PANIC = '''        # 0.7) Huir del piso del Rey cuando el da\u00f1o es severo o la cordura es baja
        if on_king_floor and p.sanity <= self.king_flee_sanity:
            # Buscar movimiento que salga del piso del Rey
            exits = [
                a for a in acts
                if a.type == ActionType.MOVE
                and floor_of(RoomId(a.data.get("to", str(p.room)))) != state.king_floor
            ]
            if exits:
                safest = min(exits, key=lambda a: _danger_score_room(state, RoomId(a.data.get("to"))))
                return finalize(safest)

        # 0.8) En late game forzar salida del piso del Rey sin importar la cordura
        if late_game and on_king_floor:
            exits = [
                a for a in acts
                if a.type == ActionType.MOVE
                and floor_of(RoomId(a.data.get("to", str(p.room)))) != state.king_floor
            ]
            if exits:
                safest = min(exits, key=lambda a: _danger_score_room(state, RoomId(a.data.get("to"))))
                return finalize(safest)

        # 1) Panico extremo: meditar si existe
        if p.sanity <= self.cfg.PLAYER_SANITY_PANIC:
            a = _pick_first(acts, ActionType.MEDITATE)
            if a:
                return finalize(a)

        # 2) Supervivencia inmediata si hay peligro alto
        if danger > 0 and p.sanity <= meditate_threshold:
            a = _pick_first(acts, ActionType.MEDITATE)
            if a:
                return finalize(a)'''

assert OLD_PANIC in src, "PATCH 3: Could not find target string"
src = src.replace(OLD_PANIC, NEW_PANIC, 1)
print("PATCH 3 applied: king floor flee logic")

# ============================================================
# PATCH 4: Guard SEARCH with search_sanity_min threshold
# ============================================================
# Find the SEARCH guarded by sanity in step 3 (key progress phase)
OLD_SEARCH_GUARD = '''            if search_allowed and _room_remaining(state, p.room) > 0 and (danger == 0 or p.sanity > meditate_threshold):
                a = _pick_first(acts, ActionType.SEARCH)
                if a:
                    return finalize(a)'''

NEW_SEARCH_GUARD = '''            if search_allowed and _room_remaining(state, p.room) > 0 and (danger == 0 or p.sanity > meditate_threshold) and p.sanity >= self.search_sanity_min:
                a = _pick_first(acts, ActionType.SEARCH)
                if a:
                    return finalize(a)'''

assert OLD_SEARCH_GUARD in src, "PATCH 4: Could not find target string"
src = src.replace(OLD_SEARCH_GUARD, NEW_SEARCH_GUARD, 1)
print("PATCH 4 applied: search sanity guard")

# ============================================================
# PATCH 5: Use _best_room_for_player() instead of _best_room_global()
#          in the exploration goal computation (step 3 main goal line)
# ============================================================
# Replace the "goal = _best_room_global(state)" in the key progress section (step 3)
# There are multiple calls; we only want to replace the one in the key-progress block
# We identify it by its surrounding context
OLD_GOAL_LINE = '''        # 3) Progreso de llaves: specials de progreso primero
        if need_keys and p.sanity > meditate_threshold and not carrier_caution:
            key_special = _choose_special_action(
                acts,
                state,
                pid,
                rng,
                self.cfg,
                avoid_armory=avoid_armory,
                armory_streak=armory_streak,
                avoid_salon=True,
                key_progress_only=True,
                risk_averse=False,
            )
            if key_special:
                return finalize(key_special)

            goal = _best_room_global(state)'''

NEW_GOAL_LINE = '''        # 3) Progreso de llaves: specials de progreso primero
        if need_keys and p.sanity > meditate_threshold and not carrier_caution:
            key_special = _choose_special_action(
                acts,
                state,
                pid,
                rng,
                self.cfg,
                avoid_armory=avoid_armory,
                armory_streak=armory_streak,
                avoid_salon=True,
                key_progress_only=True,
                risk_averse=False,
            )
            if key_special:
                return finalize(key_special)

            goal = self._best_room_for_player(state, pid)'''

assert OLD_GOAL_LINE in src, "PATCH 5: Could not find target string"
src = src.replace(OLD_GOAL_LINE, NEW_GOAL_LINE, 1)
print("PATCH 5 applied: per-player room assignment in key progress")

# ============================================================
# Write patched file
# ============================================================
POLICIES_PATH.write_text(src, encoding="utf-8")
print("\nAll patches applied successfully!")
