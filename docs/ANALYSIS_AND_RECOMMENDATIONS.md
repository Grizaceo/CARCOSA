# Análisis y Recomendaciones del Repositorio CARCOSA

Este documento detalla el análisis realizado sobre la estructura del código y su apego al canon del juego físico (según `docs/Carcosa_Libro_Tecnico_CANON.md` y `docs/Carcosa_Canon_Actualizado_PnP_v0_4.pdf`).

## 1. Análisis de Estructura del Código

### Estado Actual
El repositorio se encuentra en una fase de transición desde una estructura monolítica o "legacy" hacia una arquitectura modular basada en sistemas y manejadores (`handlers`).

- **Legacy (`engine/compat/legacy.py`)**: Contiene gran parte de la lógica central, actuando como un puente para mantener compatibilidad. Esto genera deuda técnica y dificulta la navegación.
- **Sistemas (`engine/systems/`)**: Se han extraído sistemas específicos (`sanity`, `monsters`, `rooms`), lo cual es positivo.
- **Manejadores (`engine/handlers/`)**: Implementan lógica específica de cartas, eventos y habitaciones especiales usando decoradores.

### Recomendaciones Estructurales

1.  **Migración Completa de Legacy**:
    - Priorizar la eliminación de `engine/compat/legacy.py`. La lógica remanente debe moverse a `engine/systems/` (ej. `turn.py`, `king.py`) o `engine/handlers/`.
    - `engine/transition.py` debería orquestar llamadas a sistemas puros, no delegar a funciones legacy.

2.  **Centralización de Configuración y Datos**:
    - Listas como `SPECIAL_ROOMS_POOL` y la composición del mazo canónico se encuentran actualmente en `engine/setup.py`.
    - **Recomendación**: Mover estas definiciones a `engine/data/constants.py` o `engine/config.py` para separar claramente los datos de la lógica de inicialización.

3.  **Tipado Estricto**:
    - Se observó falta de tipado estricto en funciones críticas como `resolve_card_minimal` en `engine/handlers/cards.py`, donde el argumento `card` no tiene tipo definido (puede ser `str` o `CardId`).
    - **Recomendación**: Asegurar el uso de tipos definidos en `engine/types.py` en todo el código nuevo y refactorizado.

---

## 2. Análisis de Apego al Canon (Fidelity Check)

Se comparó la implementación actual con las reglas descritas en el Canon.

### Discrepancias Detectadas (Prioridad Alta)

#### 1. Tue-Tue (El Pájaro de la Locura)
- **Canon**:
  - 3ª Revelación+: Fija la cordura en -5 **Y** "Jugadores en ese piso quedan **STUN hasta fin de ronda**".
- **Código (`engine/handlers/monsters.py`)**:
  - Aplica correctamente `p.sanity = -5`.
  - **Falta**: No aplica el estado `STUN` a los jugadores en el piso.

#### 2. Reina Helada
- **Canon**: "Al ser revelada, se coloca en el **pasillo del piso** donde fue revelada."
- **Código (`engine/handlers/monsters.py` & `engine/systems/monsters.py`)**:
  - La lógica de `spawn_monster_from_card` coloca al monstruo inicialmente en la habitación del jugador (`p.room`), lo que dispara `on_monster_enters_room`.
  - Luego, el handler `_post_spawn_reina_helada` la mueve al pasillo.
  - **Problema**: Si el jugador está en una habitación especial, la entrada (aunque breve) de la Reina Helada **destruye la habitación especial** antes de moverse al pasillo. Esto viola la intención de que spawnee directamente en el pasillo.

#### 3. Monasterio de la Locura / Capilla / Estado "Iluminado"
- **Canon**:
  - Pool incluye "Monasterio a la Locura".
  - Tabla de estados menciona "**Iluminado** | Capilla".
- **Código (`engine/handlers/special_rooms.py`)**:
  - Implementa `USE_CAPILLA` (mapeado desde `MONASTERIO_LOCURA`).
  - Efecto actual: Cura `d6 + 2` de cordura. Si `d6=1`, aplica `PARANOIA`.
  - **Falta**: No existe implementación del estado `ILUMINADO`. Si "Iluminado" debe otorgar inmunidad o efectos pasivos, esa lógica está ausente.

### Implementaciones Correctas Verificadas

- **Llaves**: Se respetan como entidad separada (`p.keys`) y no ocupan slots de objetos.
- **Trapped**: Duración de 3 turnos implementada correctamente en `engine/handlers/monsters.py`.
- **Estados Canónicos**: `MALDITO`, `ENVENENADO`, `SANIDAD` tienen sus efectos implementados en `engine/handlers/statuses.py`.
- **Paranoia**: Implementada restricción de movimiento en `engine/legality.py`.

---

## 3. Plan de Acción Sugerido

1.  **Corrección de Bugs de Canon**:
    - Modificar `_spawn_tue_tue` para aplicar STUN en la 3ª revelación.
    - Ajustar `spawn_monster_from_card` para permitir un spawn location override, evitando que la Reina Helada pase por la habitación del jugador.
    - Implementar el estado `ILUMINADO` y sus efectos (requiere definición exacta del canon).

2.  **Refactorización**:
    - Continuar la extracción de lógica desde `legacy.py`.

3.  **Tests**:
    - Agregar tests específicos para:
      - 3ª revelación de Tue-Tue (verificar STUN).
      - Spawn de Reina Helada en habitación especial (verificar NO destrucción).
