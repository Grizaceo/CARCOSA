/* ============================================================================
 * HALI · cartas — catálogo de entidades (portado del frontend 2D web/js/main.js)
 * Nombres, iconos y efectos en español para eventos, objetos, estados,
 * monstruos y presagios. Fuente de verdad de reglas: el engine; esto es
 * solo texto de presentación.
 * ==========================================================================*/
'use strict';

HALI.cards = (() => {
  const DB = {
        // EVENTOS
        "FURIA_AMARILLO": {
            name: "La Furia de Amarillo",
            type: "event",
            icon: "🃏",
            desc: "Tira d6 + cordura. <br><strong>0:</strong> Duplica permanentemente el daño del Rey. <br><strong>1-4:</strong> El Rey se teletransporta al piso del jugador y daña a todos los presentes. <br><strong>5+:</strong> Aturde al Rey por 1 ronda."
        },
        "HAY_CADAVER": {
            name: "Hay un Cadáver",
            type: "event",
            icon: "🃏",
            desc: "Tira d6 + cordura. <br><strong>0-2:</strong> Pierdes tu próximo turno (omitido). <br><strong>3-4:</strong> Pierdes 1 de cordura. <br><strong>5+:</strong> Encuentras y obtienes un Objeto Contundente (BLUNT)."
        },
        "ESPEJO_AMARILLO": {
            name: "Espejo de Amarillo",
            type: "event",
            icon: "🃏",
            desc: "Invierte tu cordura actual (se multiplica por -1). Si tenías cordura positiva, sufres esa cantidad como daño mental directo. ¡Peligro de Locura Inminente!"
        },
        "COMIDA_SERVIDA": {
            name: "Una Comida Servida",
            type: "event",
            icon: "🃏",
            desc: "Tira d6 + cordura. <br><strong>0:</strong> Pierdes 3 de cordura. <br><strong>1-2:</strong> Sufres estado ENVENENADO (2 turnos). <br><strong>3-6:</strong> Recuperas 2 de cordura. <br><strong>7+:</strong> Atraes a otro jugador a tu habitación y ambos curan 2 de cordura."
        },
        "DIVAN_AMARILLO": {
            name: "Un Diván de Amarillo",
            type: "event",
            icon: "🃏",
            desc: "Tira d6 + cordura. <br><strong>0-3:</strong> Se eliminan todos tus estados alterados. <br><strong>4-7:</strong> Se eliminan tus estados y recuperas 1 de cordura. <br><strong>8+:</strong> Obtienes el estado SANIDAD (2 turnos)."
        },
        "CAMBIA_CARAS": {
            name: "Cambia Caras",
            type: "event",
            icon: "🃏",
            desc: "Tira d6 + cordura. <br><strong>0-3:</strong> Intercambias de posición en el mapa con el jugador a tu derecha en el orden de turnos. <br><strong>4+:</strong> Intercambias de posición con el jugador a tu izquierda."
        },
        "GOLPE_AMARILLO": {
            name: "Golpe de Amarillo",
            type: "event",
            icon: "🃏",
            desc: "La terrible mirada del Rey te sacude la mente. Sufres -2 de cordura de forma directa."
        },
        "REFLEJO_AMARILLO": {
            name: "Reflejo de Amarillo",
            type: "event",
            icon: "🃏",
            desc: "La terrible mirada del Rey te sacude la mente. Sufres -2 de cordura de forma directa."
        },
        "ASCENSOR": {
            name: "Ascensor",
            type: "event",
            icon: "🃏",
            desc: "Tira d6 + cordura. <br><strong>0:</strong> Pierdes todas tus acciones restantes del turno. <br><strong>1-3:</strong> Subes 1 piso (ej. F1 -> F2 -> F3 -> F1). <br><strong>4-6:</strong> Subes 2 pisos verticalmente."
        },
        "TRAMPILLA": {
            name: "Trampilla",
            type: "event",
            icon: "🃏",
            desc: "Tira d6 + cordura. <br><strong>0:</strong> Pierdes todas tus acciones restantes del turno. <br><strong>1-3:</strong> Bajas 2 pisos verticalmente. <br><strong>4-6:</strong> Bajas 1 piso verticalmente."
        },
        "EVENTO_MOTEMEY": {
            name: "Aparición de Motemey",
            type: "event",
            icon: "🃏",
            desc: "La tienda del comerciante ambulante Motemey se abre instantáneamente. Puedes comprar objetos del mazo pagando 2 de cordura, o vender tus objetos gratis para hacer espacio."
        },
        // OBJETOS
        "COMPASS": {
            name: "Brújula",
            type: "object",
            icon: "🧭",
            desc: "Objeto consumible (1 uso). Te otorga +1 de movimiento gratis. Se puede activar en tu turno o como reacción (fuera de turno) ante desplazamientos."
        },
        "VIAL": {
            name: "Vial de Sanación",
            type: "object",
            icon: "🧪",
            desc: "Objeto consumible (1 uso). Recuperas 2 puntos de cordura de forma inmediata. Se puede usar durante tu turno o como reacción ante una pérdida letal."
        },
        "BLUNT": {
            name: "Objeto Contundente",
            type: "object",
            icon: "🪵",
            desc: "Objeto defensivo (1 uso). Permite aturdir (STUN) a cualquier monstruo en tu habitación durante 2 turnos para poder huir o neutralizarlo."
        },
        "ROPE": {
            name: "Cuerda de Escalada",
            type: "object",
            icon: "🪢",
            desc: "Objeto consumible (1 uso). Útil para facilitar desplazamientos y resolver obstáculos verticales."
        },
        "PORTABLE_STAIRS": {
            name: "Escalera Portátil",
            type: "object",
            icon: "🪜",
            desc: "Objeto consumible (1 uso). Te permite subir o bajar 1 piso desde tu habitación actual directamente."
        },
        "TALE_REPAIRER": {
            name: "El Reparador de Reputaciones (Cuento)",
            type: "object",
            icon: "📖",
            desc: "Cuento de Amarillo permanente. Coleccionable clave requerido para desbloquear interacciones avanzadas."
        },
        "TALE_MASK": {
            name: "La Máscara (Cuento)",
            type: "object",
            icon: "📖",
            desc: "Cuento de Amarillo permanente. Coleccionable clave requerido para desbloquear interacciones avanzadas."
        },
        "TALE_DRAGON": {
            name: "En la Corte del Dragón (Cuento)",
            type: "object",
            icon: "📖",
            desc: "Cuento de Amarillo permanente. Coleccionable clave requerido para desbloquear interacciones avanzadas."
        },
        "TALE_SIGN": {
            name: "El Signo de Amarillo (Cuento)",
            type: "object",
            icon: "📖",
            desc: "Cuento de Amarillo permanente. Coleccionable clave requerido para desbloquear interacciones avanzadas."
        },
        "BOOK_CHAMBERS": {
            name: "El Libro de Chambers",
            type: "object",
            icon: "📘",
            desc: "Objeto permanente de Alma Vinculada (no se puede descartar). Te protege del Rey de Amarillo o te permite desvanecerlo bajo ciertas condiciones canónicas."
        },
        "KEY": {
            name: "Llave Física",
            type: "object",
            icon: "🔑",
            desc: "Llave necesaria para abrir las puertas del Umbral al final de la partida. ¡Llévala al nodo central para ganar! Tu capacidad de llaves depende de tu rol."
        },
        "CROWN": {
            name: "Corona del Rey de Amarillo",
            type: "object",
            icon: "👑",
            desc: "Objeto maldito de Alma Vinculada. Activa permanentemente la Corona en el portador y hace aparecer al Falso Rey en su piso actual de forma inmediata."
        },
        "TREASURE_RING": {
            name: "Llavero (Tesoro de Motemey)",
            type: "object",
            icon: "💍",
            desc: "Objeto Tesoro permanente de la tienda. Aumenta tu capacidad para cargar llaves físicas en +1."
        },
        "RING": {
            name: "Anillo de Amarillo (Tesoro)",
            type: "object",
            icon: "💍",
            desc: "Objeto Tesoro. Al activarse, cura a TODAS las almas perdidas al máximo de cordura, pero se vuelve de Alma Vinculada y resta 2 de cordura al portador al inicio de cada ronda."
        },
        "TREASURE_STAIRS": {
            name: "Escaleras Tesoro de Motemey",
            type: "object",
            icon: "🪜",
            desc: "Objeto Tesoro consumible (3 usos). Te permite moverte entre pisos de manera instantánea y gratuita sin gastar acciones."
        },
        "TREASURE_SCROLL": {
            name: "Pergamino Sagrado (Tesoro)",
            type: "object",
            icon: "📜",
            desc: "Objeto Tesoro especial permanente de la tienda con potentes efectos en la partida."
        },
        "TREASURE_PENDANT": {
            name: "Colgante Protector (Tesoro)",
            type: "object",
            icon: "📿",
            desc: "Objeto Tesoro especial permanente de la tienda que te otorga protección contra los horrores de Carcosa."
        },
        // ESTADOS
        "ENVENENADO": {
            name: "Envenenado",
            type: "state",
            icon: "✨",
            desc: "Estado alterado (2 turnos). Pierdes 1 punto de cordura al inicio de cada ronda debido al veneno activo en tu cuerpo."
        },
        "SANIDAD": {
            name: "Sanidad Potenciada",
            type: "state",
            icon: "✨",
            desc: "Estado beneficioso (2 turnos). Te hace inmune a cualquier pérdida de cordura temporal y te permite sanar con doble efectividad al meditar."
        },
        "MALDITO": {
            name: "Maldito",
            type: "state",
            icon: "✨",
            desc: "Estado alterado (5 turnos). Aumenta tu vulnerabilidad mental y hace que las tiradas de eventos tiendan a ser desastrosas."
        },
        "PARANOIA": {
            name: "Paranoia",
            type: "state",
            icon: "✨",
            desc: "Estado alterado (5 turnos). Desconfías del grupo. No puedes cooperar ni entrar en habitaciones que ya estén ocupadas por otras almas perdidas."
        },
        "TRAPPED": {
            name: "Atrapado",
            type: "state",
            icon: "✨",
            desc: "Estado alterado (3 turnos). Estás atrapado. Te impide realizar la acción de Desplazamiento (MOVE) libremente hasta que expire o te liberes."
        },
        "TRAPPED_SPIDER": {
            name: "Atrapado por Telaraña",
            type: "state",
            icon: "✨",
            desc: "Estado alterado (3 turnos). Quedas atrapado en los hilos de la Araña y no puedes desplazarte."
        },
        "STUN": {
            name: "Aturdido",
            type: "state",
            icon: "✨",
            desc: "Estado alterado (1 turno). Pierdes completamente la capacidad de realizar acciones durante este turno."
        },
        // MONSTRUOS
        "TUE_TUE": {
            name: "Tue Tue",
            type: "monster",
            icon: "👾",
            desc: "Monstruo acosador. Se desplaza de forma autónoma hacia el jugador con menor cordura actual. Al atacar inflige daño mental y aturde."
        },
        "REINA_HELADA": {
            name: "Reina Helada",
            type: "monster",
            icon: "👾",
            desc: "Monstruo territorial. Congela su habitación. Las almas perdidas que pasen por ella sufren daño mental inmediato y reducción de velocidad."
        },
        "DUENDE": {
            name: "Duende Travieso",
            type: "monster",
            icon: "👾",
            desc: "Monstruo escurridizo. Al entrar en su habitación, te roba un objeto al azar de tu inventario y huye a otra habitación contigua."
        },
        "VIEJO_DEL_SACO": {
            name: "El Viejo del Saco",
            type: "monster",
            icon: "👾",
            desc: "Monstruo hostil. Captura almas perdidas solitarias y las arrastra a habitaciones oscuras alejadas del grupo, infligiéndoles gran daño mental."
        },
        "ARAÑA": {
            name: "Araña Tejedora",
            type: "monster",
            icon: "👾",
            desc: "Monstruo inmovilizador. Teje telarañas en su habitación. Toda alma perdida que entre en su zona queda inmediatamente ATRAPADA (TRAPPED)."
        },
        "ICE_SERVANT": {
            name: "Sirviente de Hielo",
            type: "monster",
            icon: "❄️",
            desc: "Sirviente de la Reina Helada. Limita a 1 acción por turno a todas las almas en su piso. Se revela con la Reina Helada."
        },
        // PRESAGIOS
        "OMEN:ARAÑA": {
            name: "Presagio de la Araña",
            type: "omen",
            icon: "⚠️",
            desc: "Despierta el Presagio de la Araña. La Araña se activa en el mapa y la Tensión general del juego sube en +1."
        },
        "OMEN:DUENDE": {
            name: "Presagio del Duende",
            type: "omen",
            icon: "⚠️",
            desc: "Despierta el Presagio del Duende. El Duende se activa y la Tensión general sube en +1."
        },
        "OMEN:REINA_HELADA": {
            name: "Presagio de la Reina Helada",
            type: "omen",
            icon: "⚠️",
            desc: "Despierta el Presagio de la Reina Helada. La Reina Helada se activa en el mapa y la Tensión general sube en +1."
        },
        "OMEN:TUE_TUE": {
            name: "Presagio del Tue Tue",
            type: "omen",
            icon: "⚠️",
            desc: "Despierta el Presagio del Tue Tue. El Tue Tue se activa para iniciar su cacería y la Tensión general sube en +1."
        },
        "TUE_TUE_REV_1": {
            name: "Tue-Tue (1ª Revelación)",
            type: "event",
            icon: "🐦",
            desc: "1ª revelación: -1 cordura (-2 con Vanidad). El Tue-Tue observa desde las sombras."
        },
        "TUE_TUE_REV_2": {
            name: "Tue-Tue (2ª Revelación)",
            type: "event",
            icon: "🐦",
            desc: "2ª revelación: -2 cordura (-3 con Vanidad). El canto del Tue-Tue se intensifica."
        },
        "TUE_TUE_REV_3": {
            name: "Tue-Tue (3ª+ Revelación)",
            type: "event",
            icon: "💀",
            desc: "3ª+ revelación: Fija cordura en -5 (ignora Vanidad/protección). STUN a todos en el piso. Efecto persistente: 1 acción/turno en piso Reina Helada."
        }
    };

  const PREFIX_RE = /^(EVENTS|EVENT|STATE|OBJECT|MONSTER):/;

  /** Busca una carta por su id crudo del engine (con o sin prefijo). */
  function lookup(cardId) {
    if (!cardId) return null;
    const raw = String(cardId);
    if (raw.startsWith('OMEN:')) return DB[raw] || null;   // presagios van con prefijo
    const clean = raw.replace(PREFIX_RE, '');
    return DB[clean] || DB[raw] || null;
  }

  /** Nombre legible aunque no esté en el catálogo. */
  function pretty(cardId) {
    const e = lookup(cardId);
    if (e) return e.name;
    return String(cardId || '').replace(PREFIX_RE, '').replace('OMEN:', 'Presagio: ').replace(/_/g, ' ');
  }

  /** Icono por catálogo o por prefijo. */
  function icon(cardId) {
    const e = lookup(cardId);
    if (e && e.icon) return e.icon;
    const raw = String(cardId || '');
    if (raw.startsWith('MONSTER:')) return '👾';
    if (raw.startsWith('OMEN:')) return '⚠️';
    if (raw.startsWith('OBJECT:')) return '🎒';
    if (raw.startsWith('STATE:')) return '✨';
    if (raw === 'KEY') return '🔑';
    return '🃏';
  }

  /** Tipo (event/object/state/monster/omen) para colorear la carta. */
  function kind(cardId) {
    const e = lookup(cardId);
    if (e && e.type) return e.type;
    const raw = String(cardId || '');
    if (raw.startsWith('MONSTER:')) return 'monster';
    if (raw.startsWith('OMEN:')) return 'omen';
    if (raw.startsWith('OBJECT:')) return 'object';
    if (raw.startsWith('STATE:')) return 'state';
    if (raw === 'KEY') return 'object';
    return 'event';
  }

  /** Nombres de rol en español (espejo de engine/catalogs/roles.py). */
  const ROLE_ES = {
    HEALER: 'Sanador', TANK: 'Tanque', HIGH_ROLLER: 'Apostador',
    SCOUT: 'Explorador', BRAWLER: 'Luchador', PSYCHIC: 'Psíquico', DEFAULT: '—',
  };

  /**
   * Límites de inventario (espejo de engine/systems/inventory.get_inventory_limits):
   * llaves = base por rol (+1 con TREASURE_RING); objetos = base por rol − penalización.
   */
  function inventoryLimits(role, objects, penalty) {
    let keyCap = role === 'HIGH_ROLLER' ? 2 : 1;
    if ((objects || []).includes('TREASURE_RING')) keyCap += 1;
    const base = role === 'TANK' ? 3 : role === 'SCOUT' ? 1 : 2;
    return { keyCap, objSlots: Math.max(0, base - (penalty || 0)) };
  }

  return { DB, lookup, pretty, icon, kind, ROLE_ES, inventoryLimits };
})();
