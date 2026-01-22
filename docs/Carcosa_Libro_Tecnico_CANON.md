# Carcosa Libro Tecnico - Canon (Resumen Operativo)

## Manifestacion del Rey (ruleta)
- La manifestacion del Rey se resuelve con ruleta d4=1..4.
- La funcion ruleta actual es correcta; no se asigna piso directo por d4.

## Presencia del Rey
- La presencia golpea solo al llegar.
- Orden canonico: ruleta -> Rey aparece en PAS del nuevo piso -> aplicar presencia en el piso nuevo.

---

## Pool de Habitaciones Especiales (Canónico)

Setup: Se eligen 3 habitaciones del pool, 1 por piso, ubicación por d4→R1..R4.

| Habitación | Gasta Acción | Notas |
|------------|--------------|-------|
| **Taberna** | ❌ No | Recuperación de cordura |
| **Motemey** | ❌ No | Compra: -2 cordura, ofrece 2 cartas, elige 1 |
| **Armería** | ❌ No | Adquisición de equipo |
| **Puertas de Amarillo** | ✅ Sí | Transporte entre pisos |
| **Cámara Letal** | ✅ Sí | 1 acción por jugador participante |
| **Salón de Belleza** | ✅ Sí | Aplica estado Vanidad |
| **Monasterio a la Locura** | ✅ Sí | Mecánica especial |

### Reglas de Habitaciones Especiales
- Se revelan boca abajo; solo se revelan al entrar por primera vez.
- Si un monstruo entra, la habitación se destruye.
- Motemey: carta no elegida vuelve al fondo del mazo.

---

## Sistema de Objetos e Inventario

### Llaves (Entidad Separada)
- **Las llaves NO son objetos ni tesoros.**
- Cada rol de personaje tiene su propia capacidad de llaves (slot independiente).
- La capacidad de llaves es independiente de la capacidad de objetos.

### Tipos de Objetos
| Tipo | Soulbound | Ejemplos |
|------|-----------|----------|
| **Objeto Normal** | No | Brújula, Vial, Contundente |
| **Tesoro** | No | Llavero, Escaleras, Pergamino, Colgante |
| **Tesoro Soulbound** | Sí | Corona, Anillo |

### Reglas Soulbound
- **Soulbound** = ligado permanentemente al jugador.
- No se puede intercambiar, dropear ni transferir.
- Efectos de descarte (p.ej. d6=6 del Rey) no eliminan objetos Soulbound.

### Corona (SOULbound)
- La Corona es SOULbound: ligada permanentemente al jugador.
- No ocupa slots de objetos.
- No se puede intercambiar, dropear ni transferir.

---

## Estados Canónicos

### Estados con Carta Propia (en mazo de eventos)
| Estado | Efecto |
|--------|--------|
| **Maldito** | Efecto negativo persistente |
| **Sanidad** | Modificador de cordura |
| **Envenenado** | Daño periódico |
| **Paranoia** | Restricción de acciones |

### Estados por Efectos (no tienen carta propia)
| Estado | Origen |
|--------|--------|
| **Vanidad** | Salón de Belleza |
| **Iluminado** | Capilla |
| **Stun** | Contundente, liberación de trap, Reina Helada |
| **Trapped** | Araña, Viejo del Saco |
| **Acción Reducida** | Reina Helada (rondas posteriores) |

---

## STUN y TRAPPED (Canónico)

### TRAPPED (Araña/Viejo del Saco)
- Duración: **3 turnos**.
- En cada turno puede intentar liberarse: `d6 + cordura_actual >= 3`.
- **Si falla el escape, NO puede actuar ese turno** (remaining_actions = 0).
- Al liberarse, el monstruo fuente queda stuneado por **1 turno**.

### STUN por Contundente
- Monstruos quedan stuneados por **2 turnos**.
- **El Rey de Amarillo NO puede ser stuneado.**

---

## Monstruos Especiales

### Reina Helada
- **Revelación**: Está barajada al azar en los mazos de habitación.
- Al ser revelada, se coloca en el **pasillo del piso** donde fue revelada.
- **Efecto inmediato (solo ronda de revelación)**:
  - Jugadores en ese piso quedan **STUN hasta fin de ronda**.
- **Efecto persistente (rondas siguientes)**:
  - Jugadores en el piso de la Reina Helada solo pueden realizar **1 acción**.
- **Puede ser stuneada** con objetos contundentes.
