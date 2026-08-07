/**
 * docs/playtest-html/js/main.js
 * 
 * Orquestador principal de la interfaz de juego CARCOSA con sintetizador Web Audio.
 */

/**
 * Motor de Síntesis de Sonido utilizando Web Audio API (cero dependencias externas).
 */
class CarcosaAudio {
    constructor() {
        this.ctx = null;
        this.isMuted = true; // Comienza silenciado para cumplir con autoplay
        this.ambienceOsc = null;
        this.ambienceGain = null;
    }

    init() {
        if (this.ctx) return;
        this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        this.playAmbience();
    }

    playAmbience() {
        if (this.isMuted || !this.ctx) return;
        
        try {
            this.ambienceOsc = this.ctx.createOscillator();
            this.ambienceGain = this.ctx.createGain();

            this.ambienceOsc.type = 'sawtooth';
            this.ambienceOsc.frequency.setValueAtTime(45, this.ctx.currentTime); // Hum grave
            
            const filter = this.ctx.createBiquadFilter();
            filter.type = 'lowpass';
            filter.frequency.setValueAtTime(100, this.ctx.currentTime); // Atenuar agudos

            this.ambienceGain.gain.setValueAtTime(0.08, this.ctx.currentTime);

            this.ambienceOsc.connect(filter);
            filter.connect(this.ambienceGain);
            this.ambienceGain.connect(this.ctx.destination);

            this.ambienceOsc.start();
        } catch (e) {
            console.error("Error al iniciar ambiente sonoro:", e);
        }
    }

    stopAmbience() {
        if (this.ambienceOsc) {
            try {
                this.ambienceOsc.stop();
            } catch(e){}
            this.ambienceOsc = null;
        }
    }

    toggleMute() {
        this.isMuted = !this.isMuted;
        if (this.isMuted) {
            this.stopAmbience();
        } else {
            this.init();
            if (this.ctx && this.ctx.state === 'suspended') {
                this.ctx.resume();
            }
            this.playAmbience();
        }
        return this.isMuted;
    }

    playHover() {
        if (this.isMuted || !this.ctx) return;
        this.init();
        
        try {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            
            osc.type = 'sine';
            osc.frequency.setValueAtTime(800, this.ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(100, this.ctx.currentTime + 0.05);
            
            gain.gain.setValueAtTime(0.02, this.ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.05);
            
            osc.connect(gain);
            gain.connect(this.ctx.destination);
            osc.start();
            osc.stop(this.ctx.currentTime + 0.06);
        } catch(e){}
    }

    playClick() {
        if (this.isMuted || !this.ctx) return;
        this.init();
        
        try {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(1200, this.ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(300, this.ctx.currentTime + 0.08);
            
            gain.gain.setValueAtTime(0.04, this.ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.08);
            
            osc.connect(gain);
            gain.connect(this.ctx.destination);
            osc.start();
            osc.stop(this.ctx.currentTime + 0.09);
        } catch(e){}
    }

    playRoll() {
        if (this.isMuted || !this.ctx) return;
        this.init();
        
        try {
            // Ruido blanco simulado para rodaje físico de dados
            const bufferSize = this.ctx.sampleRate * 0.5;
            const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
            const data = buffer.getChannelData(0);
            for (let i = 0; i < bufferSize; i++) {
                data[i] = Math.random() * 2 - 1;
            }
            
            const noise = this.ctx.createBufferSource();
            noise.buffer = buffer;
            
            const filter = this.ctx.createBiquadFilter();
            filter.type = 'bandpass';
            filter.frequency.setValueAtTime(150, this.ctx.currentTime);
            filter.frequency.exponentialRampToValueAtTime(350, this.ctx.currentTime + 0.4);
            
            const gain = this.ctx.createGain();
            gain.gain.setValueAtTime(0.12, this.ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.5);
            
            noise.connect(filter);
            filter.connect(gain);
            gain.connect(this.ctx.destination);
            
            noise.start();
            
            setTimeout(() => {
                this.playClick();
            }, 450);
        } catch(e){}
    }

    playKey() {
        if (this.isMuted || !this.ctx) return;
        this.init();
        
        try {
            const notes = [523.25, 587.33, 659.25, 783.99, 880.00]; // Arpegio C5 pentatónico
            notes.forEach((freq, idx) => {
                const time = this.ctx.currentTime + idx * 0.08;
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();
                
                osc.type = 'sine';
                osc.frequency.setValueAtTime(freq, time);
                
                gain.gain.setValueAtTime(0.06, time);
                gain.gain.exponentialRampToValueAtTime(0.001, time + 0.35);
                
                osc.connect(gain);
                gain.connect(this.ctx.destination);
                osc.start(time);
                osc.stop(time + 0.4);
            });
        } catch(e){}
    }

    playMonster() {
        if (this.isMuted || !this.ctx) return;
        this.init();

        try {
            const freqs = [110.00, 116.54, 155.56, 220.00]; // Acorde disonante
            freqs.forEach((freq) => {
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();

                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(freq, this.ctx.currentTime);

                gain.gain.setValueAtTime(0.04, this.ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 1.2);

                const filter = this.ctx.createBiquadFilter();
                filter.type = 'lowpass';
                filter.frequency.setValueAtTime(250, this.ctx.currentTime);

                osc.connect(filter);
                filter.connect(gain);
                gain.connect(this.ctx.destination);

                osc.start();
                osc.stop(this.ctx.currentTime + 1.3);
            });
        } catch(e){}
    }

    // P3-3: Game Over variants
    playVictory() {
        if (this.isMuted || !this.ctx) return;
        this.init();

        try {
            // Arpegio mayor ascendente (C5 E5 G5 C6) — sensación de escape
            const notes = [523.25, 659.25, 783.99, 1046.50];
            notes.forEach((freq, idx) => {
                const time = this.ctx.currentTime + idx * 0.12;
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();

                osc.type = 'triangle';
                osc.frequency.setValueAtTime(freq, time);

                gain.gain.setValueAtTime(0.07, time);
                gain.gain.exponentialRampToValueAtTime(0.001, time + 0.5);

                osc.connect(gain);
                gain.connect(this.ctx.destination);

                osc.start(time);
                osc.stop(time + 0.55);
            });
        } catch(e){}
    }

    playDefeat() {
        if (this.isMuted || !this.ctx) return;
        this.init();

        try {
            // Cluster descendente grave — colapso del Rey
            const freqs = [220.00, 196.00, 174.61, 155.56]; // A3 G3 F3 Eb3
            freqs.forEach((freq, idx) => {
                const time = this.ctx.currentTime + idx * 0.18;
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();

                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(freq, time);

                gain.gain.setValueAtTime(0.06, time);
                gain.gain.exponentialRampToValueAtTime(0.001, time + 1.0);

                const filter = this.ctx.createBiquadFilter();
                filter.type = 'lowpass';
                filter.frequency.setValueAtTime(400, time);

                osc.connect(filter);
                filter.connect(gain);
                gain.connect(this.ctx.destination);

                osc.start(time);
                osc.stop(time + 1.1);
            });
        } catch(e){}
    }

    // P3-3: Sacrificio — pulso grave con caída de pitch
    playSacrifice() {
        if (this.isMuted || !this.ctx) return;
        this.init();

        try {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();

            osc.type = 'sine';
            osc.frequency.setValueAtTime(180, this.ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(45, this.ctx.currentTime + 0.6);

            gain.gain.setValueAtTime(0.10, this.ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.7);

            const filter = this.ctx.createBiquadFilter();
            filter.type = 'lowpass';
            filter.frequency.setValueAtTime(300, this.ctx.currentTime);

            osc.connect(filter);
            filter.connect(gain);
            gain.connect(this.ctx.destination);

            osc.start();
            osc.stop(this.ctx.currentTime + 0.75);
        } catch(e){}
    }
}

document.addEventListener("DOMContentLoaded", () => {

    // Lobby state
    const audio = new CarcosaAudio();
    let currentGameId = null;
    let isHost = false;
    let isJoining = false;

    let api = null;
    let renderer = null;
    let activeActor = null;
    let currentGameState = null;
    let isHotseatMode = true; // Por defecto hotseat (todos los humanos se controlan en esta pantalla)
    let humanPlayers = ["P1"]; // Jugadores controlados localmente
    let renderedLogCount = 0; // Contador de logs renderizados en pantalla
    let currentLegalActions = []; // Acciones legales del jugador activo actual
    let hoveredRoomId = null; // ID de la habitación que el ratón está sobrevolando actualmente
    let previousGameState = null; // Estado anterior para detectar cambios
    let gameOverShown = false; // Evita mostrar/registrar el Game Over más de una vez
    let lastSeenStep = -1; // Descarta estados que llegan fuera de orden (HTTP vs WS)
    let actionInFlight = false; // Evita enviar dos acciones con estado stale (doble click)
    let fxEnabled = true; // Suprime animaciones/audio durante replay masivo de bitácora

    function escapeHTML(str) {
        if (!str) return "";
        return str.toString()
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Definición de los 7 roles canónicos (engine/config.py ROLE_POOL)
    const ROLE_DB = {
        "SCOUT": {
            name: "Explorador",
            icon: "🧭",
            color: "#FF4A6B",
            desc: "<strong>Movimiento gratis (1/turno):</strong> una acción MOVE adicional sin consumir acciones. Se tracks vía <code>free_move_used_this_turn</code>. Si llevas Brújula (COMPASS), se sinergiza con peek/pasillos.",
            ability: "free_move"
        },
        "HIGH_ROLLER": {
            name: "Azaroso",
            icon: "🎲",
            color: "#4B96FF",
            desc: "<strong>Double roll (1/turno):</strong> cuando tiras dados por cualquier motivo, puedes repetir UN dado del pool. Tracked vía <code>double_roll_used_this_turn</code>. Ideal para eventos de d6 + cordura con umbrales altos.",
            ability: "double_roll"
        },
        "TANK": {
            name: "Protector",
            icon: "🛡️",
            color: "#3CE39A",
            desc: "<strong>Escudo (stack):</strong> absorbe 1 golpe de cordura al recibir daño. Se muestra como <code>shield</code> en stats. <strong>Bloqueo meditación:</strong> en tu room, otros no pueden usar acciones de Capilla/Monasterio (engine lo enforces automáticamente).",
            ability: "shield"
        },
        "BRAWLER": {
            name: "Luchador",
            icon: "👊",
            color: "#F6C844",
            desc: "<strong>Contundente gratis:</strong> USE_BLUNT envía <code>cost_override=0</code> al server. Cada uso de BLUNT stunea al monstruo 2 turnos. No consume acciones si es la única que usas ese turno (verificar engine).",
            ability: "blunt_free"
        },
        "HEALER": {
            name: "Curandero",
            icon: "🩹",
            color: "#06B6D4",
            desc: "<strong>Curar grupo:</strong> USE_HEALER_HEAL (-1 cordura propia) → +2 cordura a OTRO jugador + estado aleatorio (SANIDAD o ILUMINADO, 2 turnos). Requiere sanity ≥ 1 y al menos 1 objetivo válido en el room o adyacente.",
            ability: "heal_group"
        },
        "PSYCHIC": {
            name: "Psíquico",
            icon: "🔮",
            color: "#C084FC",
            desc: "<strong>Peek hallway:</strong> PEEK_ROOM_DECK sobre habitaciones ADYACENTES (no solo la actual). Revela la carta superior de cada deck adyacente sin consumirla. Útil para evitar monstruos oplanificados.",
            ability: "peek_hallway"
        }
        // El pool canónico del engine (engine/catalogs/roles.py) tiene exactamente estos 6 roles.
    };

    // Nombres legibles para display
    const SPECIAL_ROOM_LABELS = {
        "TABERNA": "🍻 Taberna (FREE)",
        "MOTEMEY": "⚖️ Motemey (FREE)",
        "ARMERIA": "⚔️ Armería (FREE)",
        "PUERTAS_AMARILLO": "🚪 Puertas Amarillas (PAID)",
        "CAMARA_LETAL": "💀 Cámara Letal (PAID)",
        "SALON_BELLEZA": "🪞 Salón Belleza (PAID)",
        "MONASTERIO_LOCURA": "⛪ Monasterio Locura (PAID)"
    };

    // P3-2: Preview REAL del setup, calculado por el servidor con el engine (no aproximación JS).
    let validatorRequestId = 0;
    async function updateSpecialRoomsValidator(seed) {
        if (!specialRoomsValidator || !validatorContent) return;
        const reqId = ++validatorRequestId;

        validatorContent.innerHTML = `<div style="color: var(--text-muted); text-align: center; padding: 8px;">Consultando setup real al servidor...</div>`;
        specialRoomsValidator.classList.remove("hidden");

        let preview;
        try {
            const drawMode = document.getElementById("roleDrawMode").value;
            const previewApi = api || new CarcosaAPI(serverUrlInput.value.trim());
            preview = await previewApi.getSetupPreview(seed, drawMode);
        } catch (e) {
            if (reqId !== validatorRequestId) return;
            validatorContent.innerHTML = `<div style="color: var(--text-muted); text-align: center; padding: 8px;">Preview no disponible (servidor sin conexión). Se calculará al crear la partida.</div>`;
            return;
        }
        if (reqId !== validatorRequestId) return; // llegó tarde, hay una consulta más nueva

        const specials = preview.special_rooms || [];
        const floorsCovered = new Set(specials.map(s => s.room.split("_")[0])).size;
        const allInRooms = specials.every(s => s.room.includes("_R"));
        const uniqueTypes = new Set(specials.map(s => s.special_id)).size;
        const validTotal = specials.length === 3;
        const validFloors = floorsCovered === 3;
        const validUniqueTypes = uniqueTypes === specials.length;

        let html = `<div style="margin-bottom: 12px;">`;
        specials.forEach(s => {
            const label = SPECIAL_ROOM_LABELS[s.special_id] || s.special_id;
            html += `<div class="validator-row info">
                <span>${escapeHTML(s.room.split("_")[0])}: ${label}</span>
                <span>→ ${escapeHTML(s.room)}</span>
            </div>`;
        });
        html += `</div>`;

        if (preview.roles && preview.draw_mode !== "FIXED") {
            html += `<div style="margin-bottom: 8px; font-size: 0.75rem; color: var(--text-muted);">Roles sorteados (seed ${preview.seed}): ` +
                Object.entries(preview.roles).map(([pid, rid]) => `${pid}=${ROLE_DB[rid]?.icon || ""}${ROLE_DB[rid]?.name || rid}`).join(" · ") +
                `</div>`;
        }

        html += `<div style="border-top: 1px solid var(--border-color); padding-top: 8px;">`;
        html += `<div class="validator-row ${validTotal ? 'valid' : 'warning'}"><span>Total habitaciones especiales: ${specials.length}/3</span><span>${validTotal ? '✓' : '✗'}</span></div>`;
        html += `<div class="validator-row ${validFloors ? 'valid' : 'warning'}"><span>1 por piso (F1,F2,F3): ${floorsCovered}/3</span><span>${validFloors ? '✓' : '✗'}</span></div>`;
        html += `<div class="validator-row ${allInRooms ? 'valid' : 'warning'}"><span>Nunca en pasillos</span><span>${allInRooms ? '✓' : '✗'}</span></div>`;
        html += `<div class="validator-row ${validUniqueTypes ? 'valid' : 'warning'}"><span>Tipos únicos</span><span>${validUniqueTypes ? '✓' : '✗'}</span></div>`;
        html += `</div>`;

        const allValid = validTotal && validFloors && allInRooms && validUniqueTypes;
        html += `<div style="margin-top: 8px; padding: 8px; background: ${allValid ? 'rgba(60, 227, 154, 0.1)' : 'rgba(255, 74, 107, 0.1)'}; border-radius: 4px; text-align: center; font-weight: 600; color: ${allValid ? 'var(--color-success)' : 'var(--color-danger)'};">
            ${allValid ? '✅ Setup real del engine — invariantes canónicos válidos' : '⚠️ INVARIANTES VIOLADOS - Revisar seed'}
        </div>`;

        validatorContent.innerHTML = html;
    }

    // Base de datos de todas las entidades del juego con sus descripciones mecánicas oficiales
    const ENTITY_DB = {
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
    
    // Inicializar canvas renderer
    renderer = new CarcosaRenderer("boardCanvas");

    // Interacción táctil/click directa en el tablero de Canvas para moverse
    const canvas = document.getElementById("boardCanvas");
    
    canvas.addEventListener("click", (e) => {
        if (!currentGameState || !currentLegalActions || currentLegalActions.length === 0) return;
        
        // Calcular coordenadas relativas al Canvas escalado
        const rect = canvas.getBoundingClientRect();
        const clickX = ((e.clientX - rect.left) / rect.width) * canvas.width;
        const clickY = ((e.clientY - rect.top) / rect.height) * canvas.height;
        
        // Ver si hizo click dentro de alguna habitación
        let clickedRoomId = null;
        for (let roomId in renderer.layout) {
            const layout = renderer.layout[roomId];
            if (clickX >= layout.x && clickX <= layout.x + layout.w &&
                clickY >= layout.y && clickY <= layout.y + layout.h) {
                clickedRoomId = roomId;
                break;
            }
        }
        
        if (clickedRoomId && !actionInFlight) {
            // Buscar si hay una acción legal de movimiento ("MOVE") hacia esa habitación
            const moveAction = currentLegalActions.find(act => act.type === "MOVE" && act.data && act.data.to === clickedRoomId);
            if (moveAction) {
                audio.playClick();
                executePlayerAction(moveAction);
            }
        }
    });
    
    canvas.addEventListener("mousemove", (e) => {
        if (!currentGameState) {
            canvas.style.cursor = "default";
            hoveredRoomId = null;
            return;
        }
        
        const rect = canvas.getBoundingClientRect();
        const mouseX = ((e.clientX - rect.left) / rect.width) * canvas.width;
        const mouseY = ((e.clientY - rect.top) / rect.height) * canvas.height;
        
        let currentHover = null;
        for (let roomId in renderer.layout) {
            const layout = renderer.layout[roomId];
            if (mouseX >= layout.x && mouseX <= layout.x + layout.w &&
                mouseY >= layout.y && mouseY <= layout.y + layout.h) {
                currentHover = roomId;
                break;
            }
        }
        
        if (currentHover !== hoveredRoomId) {
            hoveredRoomId = currentHover;
            if (hoveredRoomId && currentLegalActions && currentLegalActions.length > 0) {
                const isValid = currentLegalActions.some(act => act.type === "MOVE" && act.data && act.data.to === hoveredRoomId);
                if (isValid) {
                    audio.playHover();
                    canvas.style.cursor = "pointer";
                    return;
                }
            }
        } else if (hoveredRoomId && currentLegalActions && currentLegalActions.length > 0) {
            const isValid = currentLegalActions.some(act => act.type === "MOVE" && act.data && act.data.to === hoveredRoomId);
            if (isValid) {
                canvas.style.cursor = "pointer";
                return;
            }
        }
        canvas.style.cursor = "default";
    });

    canvas.addEventListener("mouseleave", () => {
        hoveredRoomId = null;
    });


    // Elementos DOM
    const lobbyView = document.getElementById("lobbyView");
    const gameView = document.getElementById("gameView");
    const startForm = document.getElementById("startForm");
    const btnStart = document.getElementById("btnStart");
    const serverUrlInput = document.getElementById("serverUrl");
    const seedInput = document.getElementById("seed");

    // Lobby sync elements
    const connectionStatusBar = document.getElementById("connectionStatusBar");
    const activeGameInfoBar = document.getElementById("activeGameInfoBar");
    const activeGameIdEl = document.getElementById("activeGameId");
    const activeGameRoleEl = document.getElementById("activeGameRole");
    const btnLeaveGame = document.getElementById("btnLeaveGame");
    const lobbyConnectionStatus = document.getElementById("lobbyConnectionStatus");
    const lobbyActiveGameInfo = document.getElementById("lobbyActiveGameInfo");
    const lobbyActiveGameIdEl = document.getElementById("lobbyActiveGameId");
    const lobbyActiveGameRoleEl = document.getElementById("lobbyActiveGameRole");
    const btnLeaveGameLobby = document.getElementById("btnLeaveGameLobby");
    const joinExistingGame = document.getElementById("joinExistingGame");
    const joinGameIdInput = document.getElementById("joinGameId");
    const joinSeedInput = document.getElementById("joinSeed");
    const btnJoinGame = document.getElementById("btnJoinGame");
    const shareUrlCode = document.getElementById("shareUrl");
    const btnCopyShareUrl = document.getElementById("btnCopyShareUrl");
    const btnShowCreateForm = document.getElementById("btnShowCreateForm");
    const lobbyActiveGame = document.getElementById("lobbyActiveGameInfo");

    // P3-2: Special Rooms Validator
    const specialRoomsValidator = document.getElementById("specialRoomsValidator");
    const validatorContent = document.getElementById("validatorContent");

    const roundPill = document.getElementById("roundPill");
    const phasePill = document.getElementById("phasePill");
    const kingPill = document.getElementById("kingPill");
    const activeActorSpan = document.getElementById("activeActorSpan");
    
    const playersStatusList = document.getElementById("playersStatusList");
    const actionsGrid = document.getElementById("actionsGrid");
    const logContent = document.getElementById("logContent");
    
    const gameOverOverlay = document.getElementById("gameOverOverlay");
    const gameOverBox = document.getElementById("gameOverBox");
    const gameOverTitle = document.getElementById("gameOverTitle");
    const gameOverDetails = document.getElementById("gameOverDetails");
    const btnNewGame = document.getElementById("btnNewGame");
    const tueTuePill = document.getElementById("tueTuePill");
    const falseKingPill = document.getElementById("falseKingPill");
    const kingVanishedPill = document.getElementById("kingVanishedPill");

    // P3-1: Deck counters
    const deckCountersBar = document.getElementById("deckCountersBar");
    const motemeyDeckPill = document.getElementById("motemeyDeckPill");
    const globalDeckPill = document.getElementById("globalDeckPill");

    // Elementos DOM para Audio y Grimorio
    const btnAudioToggle = document.getElementById("btnAudioToggle");
    const audioText = document.getElementById("audioText");
    const btnGrimorioToggle = document.getElementById("btnGrimorioToggle");
    const grimorioDrawer = document.getElementById("grimorioDrawer");
    const btnCloseGrimorio = document.getElementById("btnCloseGrimorio");
    const grimorioOverlay = document.getElementById("grimorioOverlay");
    const grimorioSearch = document.getElementById("grimorioSearch");
    const grimorioContent = document.getElementById("grimorioContent");
    const filterButtons = document.querySelectorAll(".grimorio-filters .filter-btn");

    // Configuración Audio Toggle (Inicia silenciado por políticas de autoplay)
    btnAudioToggle.classList.add("muted");
    btnAudioToggle.setAttribute("aria-pressed", "false");
    btnAudioToggle.addEventListener("click", () => {
        const isMuted = audio.toggleMute();
        if (isMuted) {
            btnAudioToggle.classList.add("muted");
            btnAudioToggle.setAttribute("aria-pressed", "false");
            audioText.textContent = "MUDO";
        } else {
            btnAudioToggle.classList.remove("muted");
            btnAudioToggle.setAttribute("aria-pressed", "true");
            audioText.textContent = "ACTIVO";
            audio.playClick();
        }
    });

    // Grimorio Interactivo
    function openGrimorio() {
        audio.playClick();
        grimorioDrawer.classList.remove("hidden");
        grimorioOverlay.classList.remove("hidden");
        btnGrimorioToggle.setAttribute("aria-expanded", "true");
        renderGrimorio();
    }

    function closeGrimorio() {
        audio.playClick();
        grimorioDrawer.classList.add("hidden");
        grimorioOverlay.classList.add("hidden");
        btnGrimorioToggle.setAttribute("aria-expanded", "false");
    }

    btnGrimorioToggle.addEventListener("click", openGrimorio);
    btnCloseGrimorio.addEventListener("click", closeGrimorio);
    grimorioOverlay.addEventListener("click", closeGrimorio);
    grimorioSearch.addEventListener("input", renderGrimorio);

    filterButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            filterButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            audio.playHover();
            renderGrimorio();
        });
    });

    // Configuración de asientos (4 asientos fijos P1..P4).
    // Control por asiento: "local" (YO, este navegador), "remote" (AMIGO, otro navegador), "bot".
    const SEAT_CONTROLS = [
        { value: "local", label: "🙋 YO", cls: "human" },
        { value: "remote", label: "🧑‍🤝‍🧑 AMIGO", cls: "remote" },
        { value: "bot", label: "🤖 BOT", cls: "bot" },
    ];
    const DEFAULT_SEAT_CONTROLS = { P1: "local", P2: "remote", P3: "bot", P4: "bot" };

    function generateRoleConfig() {
        const container = document.getElementById("roleConfigContainer");
        const drawMode = document.getElementById("roleDrawMode").value;
        container.innerHTML = "";

        const roleIds = Object.keys(ROLE_DB);

        for (let i = 0; i < 4; i++) {
            const pid = `P${i + 1}`;
            const item = document.createElement("div");
            item.className = "player-config-item";
            item.dataset.pid = pid;

            const name = document.createElement("span");
            name.className = "player-name";
            name.style.color = renderer.playerColors[pid] || "#fff";
            name.textContent = pid;
            item.appendChild(name);

            // Selector de rol: solo tiene sentido en modo FIXED (el server lo respeta ahí).
            if (drawMode === "FIXED") {
                const select = document.createElement("select");
                select.className = "form-control role-select";
                select.id = `roleSelect${pid}`;
                select.style.cssText = "width: auto; display: inline-block; margin: 0 8px;";
                roleIds.forEach(rid => {
                    const opt = document.createElement("option");
                    opt.value = rid;
                    opt.textContent = `${ROLE_DB[rid].icon} ${ROLE_DB[rid].name}`;
                    select.appendChild(opt);
                });
                select.value = roleIds[i % roleIds.length];
                item.appendChild(select);
            } else {
                const hint = document.createElement("span");
                hint.style.cssText = "font-size: 0.75rem; color: var(--text-muted); margin: 0 8px;";
                hint.textContent = "🎲 rol aleatorio";
                item.appendChild(hint);
            }

            // Botón de control del asiento (cicla YO → AMIGO → BOT)
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "player-type-toggle";
            btn.id = `type${pid}`;
            const initial = DEFAULT_SEAT_CONTROLS[pid];
            setSeatControl(btn, initial);
            btn.addEventListener("click", () => {
                const idx = SEAT_CONTROLS.findIndex(c => c.value === btn.dataset.control);
                const next = SEAT_CONTROLS[(idx + 1) % SEAT_CONTROLS.length];
                setSeatControl(btn, next.value);
            });
            item.appendChild(btn);

            const legend = document.createElement("span");
            legend.className = "role-desc";
            legend.style.cssText = "font-size: 0.7rem; color: var(--text-muted); margin-left: 8px;";
            legend.textContent = "YO = este navegador · AMIGO = se une con el link · BOT = IA";
            item.appendChild(legend);

            container.appendChild(item);
        }
    }

    function setSeatControl(btn, value) {
        const ctrl = SEAT_CONTROLS.find(c => c.value === value) || SEAT_CONTROLS[2];
        btn.dataset.control = ctrl.value;
        btn.textContent = ctrl.label;
        btn.classList.remove("human", "remote", "bot");
        btn.classList.add(ctrl.cls);
    }

    function renderGrimorio() {
        const query = grimorioSearch.value.toLowerCase().trim();
        const activeFilter = document.querySelector(".grimorio-filters .filter-btn.active").dataset.filter;

        grimorioContent.innerHTML = "";

        if (activeFilter === "role") {
            // P3-5: Show roles from ROLE_DB
            for (let roleId in ROLE_DB) {
                const role = ROLE_DB[roleId];
                const matchesQuery = role.name.toLowerCase().includes(query) || role.desc.toLowerCase().includes(query);

                if (matchesQuery) {
                    const card = document.createElement("div");
                    card.className = "grimorio-item-card grimorio-item-role";
                    card.style.borderLeftColor = role.color;

                    const header = document.createElement("div");
                    header.className = "grimorio-item-header";

                    const title = document.createElement("div");
                    title.className = "grimorio-item-title";
                    title.innerHTML = `${role.icon} ${role.name}`;

                    const badge = document.createElement("span");
                    badge.className = "grimorio-item-type-badge badge-role";
                    badge.textContent = "Rol";

                    header.appendChild(title);
                    header.appendChild(badge);
                    card.appendChild(header);

                    const desc = document.createElement("div");
                    desc.className = "grimorio-item-desc";
                    desc.innerHTML = `<strong>Habilidad: </strong>${role.ability}<br><strong>Efecto:</strong> ${role.desc}`;
                    card.appendChild(desc);

                    grimorioContent.appendChild(card);
                }
            }
        } else {
            // Existing ENTITY_DB logic
            for (let key in ENTITY_DB) {
                const item = ENTITY_DB[key];
                const matchesQuery = item.name.toLowerCase().includes(query) || item.desc.toLowerCase().includes(query);
                const matchesFilter = activeFilter === "all" || item.type === activeFilter;

                if (matchesQuery && matchesFilter) {
                    const card = document.createElement("div");
                    card.className = "grimorio-item-card";

                    const header = document.createElement("div");
                    header.className = "grimorio-item-header";

                    const title = document.createElement("div");
                    title.className = "grimorio-item-title";
                    title.innerHTML = `${item.icon} ${item.name}`;

                    const badge = document.createElement("span");
                    badge.className = `grimorio-item-type-badge badge-${item.type}`;

                    let typeText = item.type;
                    if (item.type === "object") typeText = "Objeto";
                    else if (item.type === "monster") typeText = "Monstruo";
                    else if (item.type === "state") typeText = "Estado";
                    else if (item.type === "event") typeText = "Evento";
                    else if (item.type === "omen") typeText = "Presagio";

                    badge.textContent = typeText;

                    header.appendChild(title);
                    header.appendChild(badge);
                    card.appendChild(header);

                    const desc = document.createElement("div");
                    desc.className = "grimorio-item-desc";
                    desc.innerHTML = item.desc;
                    card.appendChild(desc);

                    grimorioContent.appendChild(card);
                }
            }
        }

        if (grimorioContent.innerHTML === "") {
            const empty = document.createElement("div");
            empty.style.color = "var(--text-muted)";
            empty.style.textAlign = "center";
            empty.style.padding = "20px";
            empty.textContent = "No se encontraron registros del Caos.";
            grimorioContent.appendChild(empty);
        }
    }


    // Botón Nueva Partida en pantalla de Game Over
    btnNewGame.addEventListener("click", () => {
        gameOverOverlay.classList.add("hidden");
        gameView.classList.add("hidden");
        lobbyView.classList.remove("hidden");
        btnStart.disabled = false;
        btnStart.textContent = "Crear Nueva Partida";
        if (api) {
            api.disconnectWS();
        }
        currentGameId = null;
        currentGameState = null;
        // P3-1: Hide deck counters bar
        if (deckCountersBar) deckCountersBar.classList.add("hidden");
    });

    // LOBBY SYNC LOGIC
    // ==========================================================================

    // Initialize lobby from URL params and localStorage
    function initLobby() {
        const params = new URLSearchParams(window.location.search);
        const urlGameId = params.get("game");
        const urlSeed = params.get("seed");

        // Si la página se sirve desde el propio game server, usar ese origen por defecto.
        if (window.location.protocol.startsWith("http")) {
            serverUrlInput.value = window.location.origin;
        }

        // Check for saved game in localStorage
        const savedGameId = localStorage.getItem("carcosa_game_id");
        
        if (urlGameId && savedGameId === urlGameId) {
            // F5 de un invitado que entró por link: reconectar con sus asientos
            tryRejoin(savedGameId);
        } else if (urlGameId) {
            // Join mode: pre-fill game_id
            joinGameIdInput.value = urlGameId;
            if (urlSeed) joinSeedInput.value = urlSeed;
            showJoinSection();
        } else if (savedGameId) {
            // Rejoin automático tras F5/cierre: recuperar partida y asientos de este navegador
            tryRejoin(savedGameId);
        }

        // Update share URL if we have a game_id
        if (currentGameId) {
            updateShareUrl();
        }

        generateRoleConfig();
        // P3-2: Initial validator
        const initialSeed = parseInt(seedInput.value) || 1;
        updateSpecialRoomsValidator(initialSeed);
    }

    /**
     * Rejoin tras F5/cierre del navegador. La fuente de verdad de "mis asientos" son los
     * claims del servidor para este client_id; carcosa_my_seats es el respaldo para
     * re-reclamarlos (en modo "add", que NO suelta otros asientos) si hiciera falta.
     */
    async function tryRejoin(gameId) {
        api = new CarcosaAPI(serverUrlInput.value.trim());
        let stateData;
        try {
            stateData = await api.getState(gameId);
        } catch (e) {
            // La partida ya no existe: limpiar y quedarse en el lobby
            localStorage.removeItem("carcosa_game_id");
            localStorage.removeItem("carcosa_my_seats");
            api = null;
            return;
        }

        const state = stateData.state;
        const claims = (state.seats && state.seats.claims) || {};
        let mySeats = Object.keys(claims).filter(pid => claims[pid] === api.clientId);

        if (mySeats.length === 0) {
            // Reintentar con los asientos que teníamos guardados
            let savedSeats = [];
            try { savedSeats = JSON.parse(localStorage.getItem("carcosa_my_seats") || "[]"); } catch (e) {}
            const humans = (state.seats && state.seats.humans) || [];
            savedSeats = savedSeats.filter(s => humans.includes(s));
            if (savedSeats.length > 0) {
                try {
                    const res = await api.claimSeats(gameId, savedSeats, "add");
                    mySeats = res.claimed || savedSeats;
                } catch (e) { /* asientos tomados por otro: caer al flujo de unirse */ }
            }
        }

        if (mySeats.length === 0 || state.game_over) {
            joinGameIdInput.value = gameId;
            showJoinSection();
            return;
        }

        humanPlayers = mySeats;
        currentGameId = gameId;
        localStorage.setItem("carcosa_my_seats", JSON.stringify(mySeats));
        showActiveGame(gameId, mySeats.includes("P1"));
        enterGameView(state);
        addLog("SISTEMA", `🔄 Reconectado a la partida <strong>#${gameId}</strong> como ${mySeats.join(", ")}`, "game-event");
    }

    function showJoinSection() {
        startForm.classList.add("hidden");
        joinExistingGame.classList.remove("hidden");
        btnShowCreateForm.style.display = "block";
        isJoining = true;
    }

    function showCreateForm() {
        startForm.classList.remove("hidden");
        joinExistingGame.classList.add("hidden");
        btnShowCreateForm.style.display = "none";
        isJoining = false;
    }

    function showActiveGame(gameId, host = false) {
        currentGameId = gameId;
        isHost = host;
        
        // Update header connection status
        connectionStatusBar.classList.add("connected");
        connectionStatusBar.classList.remove("disconnected");
        connectionStatusBar.querySelector(".text").textContent = `Conectado a #${gameId} ${host ? "(Host)" : "(Invitado)"}`;
        activeGameInfoBar.classList.remove("hidden");
        activeGameIdEl.textContent = gameId;
        activeGameRoleEl.textContent = host ? "Host" : "Invitado";
        activeGameRoleEl.className = "role-label " + (host ? "host" : "guest");

        // Update lobby connection status
        lobbyConnectionStatus.classList.add("connected");
        lobbyConnectionStatus.classList.remove("disconnected");
        lobbyConnectionStatus.querySelector(".text").textContent = `Conectado a partida #${gameId}`;
        lobbyActiveGameInfo.classList.remove("hidden");
        lobbyActiveGameIdEl.textContent = gameId;
        lobbyActiveGameRoleEl.textContent = host ? "Host" : "Invitado";
        lobbyActiveGameRoleEl.className = "role-badge " + (host ? "host" : "guest");

        // Hide create form, show join section if not host
        if (!host) {
            showJoinSection();
            joinGameIdInput.value = gameId;
        } else {
            showCreateForm();
        }
        
        updateShareUrl();
    }

    function updateShareUrl() {
        if (currentGameId) {
            // La seed real viene del estado del servidor (el invitado no la ingresó)
            const seed = currentGameState?.seed ?? (seedInput.value || joinSeedInput.value || "1");
            const url = `${window.location.origin}${window.location.pathname}?game=${currentGameId}&seed=${seed}`;
            shareUrlCode.textContent = url;
        }
    }

    async function createGame() {
        const seed = parseInt(seedInput.value) || 1;
        const drawMode = document.getElementById("roleDrawMode").value;

        // Leer configuración de asientos desde la UI (4 asientos fijos)
        humanPlayers = [];        // asientos controlados por ESTE navegador
        const allHumanSeats = []; // asientos humanos (locales + amigo remoto)
        const playersConfig = []; // [{pid, roleId?, control}]

        for (let i = 1; i <= 4; i++) {
            const pid = `P${i}`;
            const btn = document.getElementById(`type${pid}`);
            const control = btn ? btn.dataset.control : "bot";
            const roleSelect = document.getElementById(`roleSelect${pid}`);
            const cfg = { pid, control };
            if (roleSelect) cfg.roleId = roleSelect.value;
            playersConfig.push(cfg);
            if (control === "local") {
                humanPlayers.push(pid);
                allHumanSeats.push(pid);
            } else if (control === "remote") {
                allHumanSeats.push(pid);
            }
        }

        if (allHumanSeats.length === 0) {
            alert("Debes elegir al menos un asiento humano (YO o AMIGO).");
            return;
        }
        if (humanPlayers.length === 0) {
            alert("Debes controlar al menos un asiento (YO) desde este navegador.");
            return;
        }

        const serverUrl = serverUrlInput.value.trim();
        api = new CarcosaAPI(serverUrl);
        btnStart.disabled = true;
        btnStart.textContent = "Creando...";

        // Disparar audio hum de tensión ambiente
        audio.init();
        audio.playAmbience();

        try {
            // Llamar API para iniciar juego con asientos + roles
            const data = await api.startGame(seed, allHumanSeats, playersConfig, drawMode);
            currentGameId = data.game_id;
            isHost = true;

            // Guardar en localStorage
            localStorage.setItem("carcosa_game_id", currentGameId);
            localStorage.setItem("carcosa_my_seats", JSON.stringify(humanPlayers));

            showActiveGame(currentGameId, true);
            enterGameView(data.state, seed);

            const remoteSeats = allHumanSeats.filter(s => !humanPlayers.includes(s));
            addLog("SISTEMA", `Nueva partida creada. ID: <strong>${currentGameId}</strong>. Semilla: ${seed}`, "game-event");
            addLog("SISTEMA", `Tus asientos: ${humanPlayers.join(", ")}${remoteSeats.length ? ` · Asientos del amigo: ${remoteSeats.join(", ")} (comparte el link de la partida)` : ""}`, "game-event");

        } catch (error) {
            alert(`No se pudo conectar con el servidor de CARCOSA en ${serverUrl}. Asegúrate de que el servidor FastAPI esté corriendo en ese puerto.\n\nError: ${error.message}`);
            btnStart.disabled = false;
            btnStart.textContent = "Crear Nueva Partida";
        }
    }

    // Fallback de polling cuando el WS muere definitivamente (server caído/redeploy largo).
    let pollTimer = null;
    function startPollingFallback() {
        if (pollTimer || !currentGameId) return;
        addLog("SISTEMA", "⚠️ Conexión en tiempo real perdida. Consultando estado cada 5s...", "game-event");
        connectionStatusBar.classList.remove("connected");
        connectionStatusBar.classList.add("disconnected");
        connectionStatusBar.querySelector(".text").textContent = "Reconectando (polling)...";
        pollTimer = setInterval(async () => {
            if (!api || !currentGameId) { stopPollingFallback(); return; }
            try {
                const data = await api.getState(currentGameId);
                updateState(data.state);
                // Reintentar el WS: si vuelve, ws_connected detendrá el polling
                api.reconnectAttempts = 0;
                api.connectWS(currentGameId, humanPlayers[0] || "P1", wsHandler);
                stopPollingFallback();
            } catch (e) { /* servidor aún caído, seguir intentando */ }
        }, 5000);
    }
    function stopPollingFallback() {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    function wsHandler(wsData) {
        if (wsData.type === "state_update") {
            updateState(wsData.state);
        } else if (wsData.type === "ws_connected") {
            stopPollingFallback();
            connectionStatusBar.classList.add("connected");
            connectionStatusBar.classList.remove("disconnected");
            if (currentGameId) connectionStatusBar.querySelector(".text").textContent = `Conectado a #${currentGameId}`;
        } else if (wsData.type === "ws_dead") {
            startPollingFallback();
        } else if (wsData.type === "error" && wsData.code === "game_not_found") {
            addLog("SISTEMA", `❌ La partida ya no existe en el servidor (${escapeHTML(wsData.detail || "")}).`, "game-event");
            alert("La partida ya no existe en el servidor (expiró o el servidor se reinició sin ella).");
            leaveGame();
        }
    }

    // Entra a la vista de juego, conecta WS y pinta el estado inicial.
    function enterGameView(state, seed) {
        renderedLogCount = 0;
        gameOverShown = false;
        previousGameState = null;
        lastSeenStep = -1;
        logContent.innerHTML = "";
        lobbyView.classList.add("hidden");
        gameView.classList.remove("hidden");
        audio.init();
        audio.playAmbience();
        updateState(state);
        api.connectWS(currentGameId, humanPlayers[0] || "P1", wsHandler);
    }

    async function joinGame() {
        const gameId = joinGameIdInput.value.trim().toLowerCase();
        if (!gameId) return alert("Ingresa un Game ID válido");
        if (gameId.length !== 8) return alert("El Game ID debe tener 8 caracteres");

        const serverUrl = serverUrlInput.value.trim();
        api = new CarcosaAPI(serverUrl);
        btnJoinGame.disabled = true;
        btnJoinGame.textContent = "Uniendo...";

        try {
            // Validar que la partida existe y ver asientos disponibles
            const stateData = await api.getState(gameId);
            const seats = stateData.state.seats || { humans: [], claims: {} };
            const claims = seats.claims || {};
            const myId = api.clientId;

            if ((seats.humans || []).length === 0) {
                alert("Esta partida no tiene asientos humanos.");
                btnJoinGame.disabled = false;
                btnJoinGame.textContent = "Unirse";
                return;
            }

            // Selector de asiento(s) para el invitado (los ocupados se pueden forzar)
            showSeatPickerModal(gameId, stateData.state, seats.humans, claims, myId);

        } catch (error) {
            alert(`No se pudo unir a la partida: ${error.message}`);
            btnJoinGame.disabled = false;
            btnJoinGame.textContent = "Unirse";
        }
    }

    // Modal para que el invitado elija qué asiento(s) controlar.
    // Los asientos ocupados por otro navegador se pueden FORZAR (rescate: amigo que
    // perdió su localStorage, cambió de dispositivo, o nunca llegó).
    function showSeatPickerModal(gameId, state, humanSeats, claims, myClientId) {
        const modal = document.createElement("div");
        modal.className = "card-reveal-overlay";
        modal.style.zIndex = "var(--z-modal, 1000)";
        const seatButtons = humanSeats.map(pid => {
            const p = state.players[pid] || {};
            const role = ROLE_DB[p.role_id] || {};
            const owner = claims[pid];
            let tag = "";
            if (owner === myClientId) tag = " ✅ (ya era tuyo)";
            else if (owner) tag = " 🔒 (ocupado — click para forzar)";
            return `<button class="action-btn seat-choice" data-seat="${escapeHTML(pid)}" data-taken="${owner && owner !== myClientId ? "1" : ""}" style="text-align: left; justify-content: flex-start;">
                ${role.icon || "🎭"} <strong>${escapeHTML(pid)}</strong> — ${escapeHTML(role.name || p.role_id || "?")}${tag}
            </button>`;
        }).join("");

        modal.innerHTML = `
            <div class="card-reveal-box type-event" style="max-width: 420px;">
                <div class="card-reveal-header">
                    <span class="card-reveal-icon">🎭</span>
                    <span class="card-reveal-type">UNIRSE A PARTIDA</span>
                </div>
                <h2 class="card-reveal-title">Elige tu asiento</h2>
                <div class="card-reveal-divider"></div>
                <p class="card-reveal-desc">Partida <strong>#${escapeHTML(gameId)}</strong>. Elige qué alma controlarás desde este navegador.</p>
                <div style="display: flex; flex-direction: column; gap: 8px; margin: 16px 0;">
                    ${seatButtons}
                </div>
                <p class="card-reveal-footer">Click en un asiento para reclamarlo</p>
            </div>
        `;
        document.body.appendChild(modal);

        modal.querySelectorAll(".seat-choice").forEach(btn => {
            btn.addEventListener("click", async (e) => {
                e.stopPropagation();
                const seat = btn.dataset.seat;
                const taken = btn.dataset.taken === "1";
                if (taken && !confirm(`${seat} está controlado por otro navegador. ¿Quitárselo? (úsalo solo si ese jugador perdió su sesión)`)) {
                    return;
                }
                try {
                    await api.claimSeats(gameId, [seat], "add", taken);
                    document.body.removeChild(modal);
                    await completeJoin(gameId, [seat]);
                } catch (err) {
                    alert(`No se pudo reclamar ${seat}: ${err.message}`);
                }
            });
        });

        modal.onclick = (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
                btnJoinGame.disabled = false;
                btnJoinGame.textContent = "Unirse";
            }
        };
    }

    async function completeJoin(gameId, seats) {
        humanPlayers = seats;
        currentGameId = gameId;
        isHost = false;

        localStorage.setItem("carcosa_game_id", currentGameId);
        localStorage.setItem("carcosa_my_seats", JSON.stringify(seats));

        showActiveGame(currentGameId, false);

        const stateData = await api.getState(gameId);
        enterGameView(stateData.state);

        addLog("SISTEMA", `Unido a partida <strong>#${currentGameId}</strong> como ${seats.join(", ")}`, "game-event");
    }

    function leaveGame() {
        // Liberar los asientos en el servidor para que otro navegador pueda tomarlos
        if (api && currentGameId) {
            api.claimSeats(currentGameId, [], "release").catch(() => {});
        }
        stopPollingFallback();

        // Limpiar estado
        currentGameId = null;
        isHost = false;
        isJoining = false;
        localStorage.removeItem("carcosa_game_id");
        localStorage.removeItem("carcosa_my_seats");

        // Reactivar botones del lobby (createGame/joinGame los dejan deshabilitados)
        btnStart.disabled = false;
        btnStart.textContent = "👁️ Crear Nueva Partida";
        btnJoinGame.disabled = false;
        btnJoinGame.textContent = "Unirse";

        // Desconectar WebSocket
        if (api) {
            api.disconnectWS();
            api = null;
        }
        
        // Reset UI
        connectionStatusBar.classList.remove("connected");
        connectionStatusBar.classList.add("disconnected");
        connectionStatusBar.querySelector(".text").textContent = "Desconectado";
        activeGameInfoBar.classList.add("hidden");
        
        lobbyConnectionStatus.classList.remove("connected");
        lobbyConnectionStatus.classList.add("disconnected");
        lobbyConnectionStatus.querySelector(".text").textContent = "Sin partida activa";
        lobbyActiveGameInfo.classList.add("hidden");
        
        // Mostrar formulario crear
        showCreateForm();
        shareUrlCode.textContent = "";
        
        // Volver al lobby si estábamos en juego
        if (!gameView.classList.contains("hidden")) {
            gameView.classList.add("hidden");
            lobbyView.classList.remove("hidden");
        }
    }

    // Event listeners for lobby sync
    btnStart.addEventListener("click", async (e) => {
        e.preventDefault();
        await createGame();
    });

    btnJoinGame.addEventListener("click", async () => {
        await joinGame();
    });

    btnLeaveGame.addEventListener("click", leaveGame);
    btnLeaveGameLobby.addEventListener("click", leaveGame);

    btnShowCreateForm.addEventListener("click", showCreateForm);

    document.getElementById("roleDrawMode").addEventListener("change", generateRoleConfig);

    // P3-2: Update special rooms validator when seed changes
    seedInput.addEventListener("input", () => {
        const seed = parseInt(seedInput.value) || 1;
        updateSpecialRoomsValidator(seed);
    });
    document.getElementById("roleDrawMode").addEventListener("change", () => {
        const seed = parseInt(seedInput.value) || 1;
        updateSpecialRoomsValidator(seed);
    });

    btnCopyShareUrl.addEventListener("click", () => {
        const url = shareUrlCode.textContent;
        if (url) {
            navigator.clipboard.writeText(url).then(() => {
                btnCopyShareUrl.textContent = "✓";
                setTimeout(() => btnCopyShareUrl.textContent = "📋", 2000);
            });
        }
    });

    // Initialize lobby on load
    initLobby();

    /**
     * Actualiza el estado local y redibuja la interfaz.
     */
    function updateState(state) {
        // Descartar estados fuera de orden: /act (HTTP) y los broadcasts (WS) viajan por
        // canales distintos; procesar un estado viejo produce diffs invertidos y logs espurios.
        if (typeof state.step === "number") {
            if (state.step < lastSeenStep) return;
            lastSeenStep = state.step;
        }

        // Detectar eventos inferidos comparando con estado anterior
        if (previousGameState) {
            inferEventsFromStateDiff(previousGameState, state);
        }
        previousGameState = JSON.parse(JSON.stringify(state)); // Deep clone para próxima comparación

        currentGameState = state;
        activeActor = state.active_actor;
        
        // Redibujar Canvas se realiza a través de renderLoop automáticamente
        
        // Actualizar Cabecera de metadatos
        roundPill.textContent = `RONDA ${state.round}`;
        phasePill.textContent = `FASE: ${state.phase}`;
        kingPill.textContent = `REY EN PISO ${state.king_floor}`;
        activeActorSpan.textContent = activeActor;
        
        // [LIVE-ACT] Cerebro del bot: activaciones PPO en vivo
        renderBotBrain(state);
        
        // P0-5: Tue-Tue counter
        const tueRevelations = state.tue_tue_revelations || 0;
        if (tueRevelations > 0) {
            tueTuePill.textContent = `TUE-TUE: ${tueRevelations}/3`;
            tueTuePill.style.display = "inline-block";
        } else {
            tueTuePill.style.display = "none";
        }
        
        // P2-4: Falso Rey pill
        if (state.false_king_floor) {
            falseKingPill.textContent = `FALSO REY: PISO ${state.false_king_floor}`;
            falseKingPill.style.display = "inline-block";
        } else {
            falseKingPill.style.display = "none";
        }
        
        // P2-3: Rey desvanecido pill
        if (state.king_vanished_turns > 0) {
            kingVanishedPill.textContent = `REY DESVANECIDO: ${state.king_vanished_turns}`;
            kingVanishedPill.style.display = "inline-block";
        } else {
            kingVanishedPill.style.display = "none";
        }

        // P3-1: Deck counters bar (show when game is active)
        if (deckCountersBar) {
            deckCountersBar.classList.remove("hidden");
            // Motemey deck: cards.length - top (server sends motemey_deck with cards + top)
            let motemeyRemaining = 13; // fallback initial
            if (state.motemey_deck && state.motemey_deck.cards) {
                motemeyRemaining = state.motemey_deck.cards.length - (state.motemey_deck.top || 0);
            }
            motemeyDeckPill.textContent = `MOTEMEY: ${motemeyRemaining}`;
            // Global deck: sum of all room decks (cards.length - top)
            let globalRemaining = 0;
            if (state.rooms) {
                for (const roomId in state.rooms) {
                    const room = state.rooms[roomId];
                    if (room.deck && room.deck.cards) {
                        globalRemaining += room.deck.cards.length - (room.deck.top || 0);
                    }
                }
            }
            if (globalRemaining === 0) globalRemaining = 108; // fallback initial
            globalDeckPill.textContent = `GLOBAL: ${globalRemaining}`;
        }

        // P2-2: Anillo activo indicator (en holder stats, ver renderPlayersList)
        
        // Limpiar marcador de turno en barra de título
        document.title = `CARCOSA - Turno de ${activeActor}`;
        
        // Renderizar Jugadores en la barra lateral
        renderPlayersList(state);
        
        // Procesar logs autoritativos del servidor.
        // Al unirse a mitad de partida hay decenas de entradas históricas: suprimir
        // animaciones/overlays/audio salvo para las últimas entradas.
        if (state.action_log) {
            const pending = state.action_log.length - renderedLogCount;
            for (let i = renderedLogCount; i < state.action_log.length; i++) {
                fxEnabled = !(pending > 8 && i < state.action_log.length - 3);
                processServerLog(state.action_log[i]);
            }
            fxEnabled = true;
            renderedLogCount = state.action_log.length;
        }
        
        // Renderizar Acciones legales si le toca a un humano local
        renderActions(state);
        
        // Verificar fin del juego
        if (state.game_over) {
            showGameOver(state);
        }
    }

    /**
     * Procesa un log enviado por el servidor y lo renderiza de forma amigable.
     */
    function processServerLog(log) {
        console.log("[PROCESS_LOG] processServerLog called", log);
        if (log.event) {
            if (log.event === "CARD_REVEALED") {
                let entity = null;
                if (log.card.startsWith("OMEN:")) {
                    entity = ENTITY_DB[log.card];
                } else {
                    const cleanKey = log.card.replace("EVENTS:", "").replace("EVENT:", "").replace("STATE:", "").replace("OBJECT:", "").replace("MONSTER:", "");
                    entity = ENTITY_DB[cleanKey];
                }

                if (entity) {
                    addLog("SISTEMA", `🔎 ${escapeHTML(log.player)} entra a ${escapeHTML(log.room)} y revela: <strong>${escapeHTML(entity.name)}</strong> ${entity.icon}<div class="card-detail-box ${entity.type}-type"><strong>Efecto:</strong> ${entity.desc}</div>`, "game-event");
                } else {
                    const cardName = log.card.replace("EVENTS:", "").replace("EVENT:", "").replace("STATE:", "").replace("OBJECT:", "").replace("MONSTER:", "").replace("OMEN:", "");
                    const prettyCard = cardName.replace(/_/g, " ");
                    let icon = "🃏";
                    if (log.card.startsWith("MONSTER:")) icon = "👾";
                    else if (log.card.startsWith("OMEN:")) icon = "⚠️";
                    else if (log.card.startsWith("OBJECT:")) icon = "🎒";
                    else if (log.card.startsWith("STATE:")) icon = "✨";
                    else if (log.card === "KEY") icon = "🔑";
                    addLog("SISTEMA", `🔎 ${escapeHTML(log.player)} entra a ${escapeHTML(log.room)} y revela: <strong>${escapeHTML(prettyCard)}</strong> ${icon}`, "game-event");
                }

                // Disparar popup visual y auditivo de revelación de carta
                triggerCardRevealAnimation(log.card);
            } else if (log.event === "DICE_ROLL") {
                const rollsStr = log.rolls.join(" + ");
                const rollsSum = log.rolls.reduce((a, b) => a + b, 0);
                const sanityStr = log.sanity > 0 ? ` + cordura (${log.sanity})` : log.sanity < 0 ? ` - cordura (${Math.abs(log.sanity)})` : '';
                const result = log.sanity !== 0 ? ` = Total: <strong>${log.total}</strong>` : ` = Resultado: <strong>${log.total}</strong>`;
                addLog("SISTEMA", `🎲 <strong>${escapeHTML(log.player)}</strong> tira dados [${escapeHTML(log.purpose)}]: dados (${rollsStr}) = ${rollsSum}${sanityStr}${result}`, "game-event");

                // Disparar popup animado neón de dados y efectos de rodado
                triggerDiceRollAnimation(log.rolls, log.purpose, log.sanity, log.total);

            } else if (log.event === "SPECIAL_ROOM_REVEALED") {
                const roomName = log.special_id.replace(/_/g, " ");
                let icon = "🏨";
                if (log.special_id === "TABERNA") icon = "🍻";
                else if (log.special_id === "MOTEMEY") icon = "⚖️";
                else if (log.special_id === "ARMERIA") icon = "⚔️";
                else if (log.special_id === "PUERTAS_AMARILLO") icon = "🚪";
                else if (log.special_id === "CAMARA_LETAL") icon = "💀";
                else if (log.special_id === "SALON_BELLEZA") icon = "🪞";
                else if (log.special_id === "MONASTERIO_LOCURA") icon = "⛪";
                addLog("SISTEMA", `🗺️ ¡Se devela una habitación especial! <strong>${escapeHTML(roomName)}</strong> ${icon} ha sido revelada en <strong>${escapeHTML(log.room)}</strong> por ${escapeHTML(log.player)}`, "game-event");
            } else if (log.event === "TUE_TUE_REVEALED") {
                // P0-5: Tue-Tue revelación acumulativa
                const rev = log.revelation_count || 1;
                const cardKey = rev === 1 ? "TUE_TUE_REV_1" : rev === 2 ? "TUE_TUE_REV_2" : "TUE_TUE_REV_3";
                const entity = ENTITY_DB[cardKey];
                if (entity) {
                    addLog("SISTEMA", `🐦 ${escapeHTML(log.player)} revela: <strong>${escapeHTML(entity.name)}</strong> ${entity.icon}<div class="card-detail-box event-type"><strong>Efecto:</strong> ${entity.desc}</div>`, "game-event");
                    triggerCardRevealAnimation(cardKey);
                }
                if (rev >= 3) {
                    addLog("SISTEMA", `☠️ ¡3ª+ revelación del Tue-Tue! Cordura fijada en -5. STUN a todos en el piso. Efecto persistente: 1 acción/turno en piso Reina Helada.`, "game-event");
                }
            } else if (log.event === "ESCAPE_ATTEMPT") {
                addLog("SISTEMA", `🕸️ Intento de escape: d6=${log.d6} + cordura=${log.sanity} = ${log.total} (${log.success ? "Éxito" : "Fallo"})`, "game-event");
            } else if (log.event === "KING_VANISHED") {
                addLog("SISTEMA", `👑 El Rey de Amarillo se ha desvanecido por ${log.turns} turnos.`, "game-event");
            } else if (log.event === "PEEK_RESULT") {
                addLog("SISTEMA", `👁️ Mirador en ${escapeHTML(log.room)} revela la carta: ${escapeHTML(log.card)}`, "game-event");
            } else if (log.event === "SANITY_LOSS") {
                addLog("SISTEMA", `💔 ${escapeHTML(log.player)} sufre -${log.amount} de cordura [Fuente: ${escapeHTML(log.source)}]`, "game-event");
            } else if (log.event === "SANITY_LOSS_PENDING_SACRIFICE") {
                addLog("SISTEMA", `⚠️ ¡LOCURA INMINENTE! ${escapeHTML(log.player)} va a sufrir -${log.amount} de cordura [Fuente: ${escapeHTML(log.source)}] y debe sacrificar para resistir`, "game-event");
                // P3-3: audio cue de sacrificio pendiente
                if (fxEnabled) audio.playSacrifice();
            } else if (log.event === "SANITY_GAIN") {
                addLog("SISTEMA", `💚 <strong>${escapeHTML(log.player)}</strong> recupera +${log.amount} de cordura [Fuente: ${escapeHTML(log.source)}]`, "game-event");
            } else if (log.event === "ITEM_GRANTED") {
                const entity = ENTITY_DB[log.item];
                if (entity) {
                    addLog("SISTEMA", `🎒 ${escapeHTML(log.player)} obtiene objeto: <strong>${escapeHTML(entity.name)}</strong>${log.discarded ? ` (descartando ${escapeHTML(log.discarded)})` : ''}<div class="card-detail-box object-type"><strong>Efecto:</strong> ${entity.desc}</div>`, "game-event");
                } else {
                    addLog("SISTEMA", `🎒 ${escapeHTML(log.player)} obtiene objeto: ${escapeHTML(log.item)}${log.discarded ? ` (descartando ${escapeHTML(log.discarded)})` : ''}`, "game-event");
                }
            } else if (log.event === "KEY_GRANTED") {
                addLog("SISTEMA", `🔑 ${escapeHTML(log.player)} encuentra una Llave física`, "game-event");
                if (fxEnabled) audio.playKey();

            } else if (log.event === "STATUS_ADDED") {
                const entity = ENTITY_DB[log.status];
                if (entity) {
                    addLog("SISTEMA", `✨ ${escapeHTML(log.player)} adquiere estado: <strong>${escapeHTML(entity.name)}</strong> (${log.duration} turnos)<div class="card-detail-box state-type"><strong>Efecto:</strong> ${entity.desc}</div>`, "game-event");
                } else {
                    addLog("SISTEMA", `✨ ${escapeHTML(log.player)} adquiere estado: ${escapeHTML(log.status)} (${log.duration} turnos)`, "game-event");
                }
            } else if (log.event === "MONSTER_SPAWNED") {
                const entity = ENTITY_DB[log.monster];
                if (entity) {
                    addLog("SISTEMA", `👾 ¡Monstruo invocado! <strong>${escapeHTML(entity.name)}</strong> aparece en ${escapeHTML(log.room)}<div class="card-detail-box monster-type"><strong>Comportamiento:</strong> ${entity.desc}</div>`, "game-event");
                } else {
                    addLog("SISTEMA", `👾 ¡Monstruo invocado! ${escapeHTML(log.monster)} aparece en ${escapeHTML(log.room)}`, "game-event");
                }
                if (fxEnabled) audio.playMonster();

            // P2-2: Anillo activado
            } else if (log.event === "RING_ACTIVATED") {
                const holder = log.player || log.actor;
                addLog("SISTEMA", `💍 <strong>${escapeHTML(holder)}</strong> activa el Anillo de Amarillo: cura a TODOS al máximo, pero -2 cordura/turno al portador.`, "game-event");
                if (fxEnabled) audio.playKey();

            // P2-3: Libro Chambers - cuento unido / vanish
            } else if (log.event === "TALE_ATTACHED") {
                addLog("SISTEMA", `📖 <strong>${escapeHTML(log.player)}</strong> une Cuento ${escapeHTML(log.tale_id?.replace("TALE_", "") || "?")} al Libro Chambers. Rey desvanecido +1 turno (total: ${log.vanish_turns || 1}).`, "game-event");
                if (fxEnabled) audio.playKey();

            // P2-4: Falso Rey aparece
            } else if (log.event === "FALSE_KING_APPEARED") {
                const floor = log.floor || "?";
                const holder = log.player || log.actor;
                addLog("SISTEMA", `👑 ¡FALSO REY aparece en Piso ${floor}! (Corona activada por ${escapeHTML(holder)}). Presencia daño en su piso.`, "game-event");
                if (fxEnabled) audio.playMonster();


            }
        } else if (log.type) {
            let desc = "";
            switch (log.type) {
                case "MOVE":
                    desc = `Se desplaza a ${log.data.to}`;
                    break;
                case "SEARCH":
                    desc = `Busca en la habitación`;
                    break;
                case "MEDITATE":
                    desc = `Medita (Recupera cordura)`;
                    break;
                case "DISCARD_SANIDAD":
                    desc = `Consume carta de SANIDAD para curarse`;
                    break;
                case "END_TURN":
                    desc = `Finaliza su turno`;
                    break;
                case "KING_ENDROUND":
                    // P2-5: King Phase Breakdown completo
                    const floor = currentGameState ? currentGameState.king_floor : "?";
                    const d6 = log.d6 || "?";
                    const d4 = log.d4 || "?";
                    const presDamage = currentGameState ? (currentGameState.round <= 3 ? 1 : currentGameState.round <= 6 ? 2 : currentGameState.round <= 9 ? 3 : 4) : "?";
                    
                    // Logs secuenciales del turno del Rey
                    addLog("REY", `🏠 Casa: -1 cordura a todos (HOUSE_LOSS)`);
                    addLog("REY", `🎲 Ruleta d4=${d4}: Rey se manifiesta en Piso ${floor}`);
                    if (presDamage > 0) addLog("REY", `👑 Presencia (Ronda ${currentGameState?.round || "?"}): -${presDamage} cordura en Piso ${floor}`);
                    
                    // Efecto d6
                    switch(parseInt(d6)) {
                        case 1: addLog("REY", `⚡ d6=1: Rotación intra-piso (R1→R4→R3→R2)`); break;
                        case 2: addLog("REY", `☠️ d6=2: -1 cordura a todos (exc. Falso Rey)`); break;
                        case 3: addLog("REY", `⏱️ d6=3: Acción reducida en Piso ${floor} next round`); break;
                        case 4: addLog("REY", `🚪 d6=4: Expulsión del Piso ${floor} (exc. Falso Rey)`); break;
                        case 5: addLog("REY", `🧲 d6=5: Atracción al Piso ${floor} (exc. Falso Rey)`); break;
                        case 6: addLog("REY", `🤲 d6=6: Robo objeto no soulbound a todos`); break;
                        default: addLog("REY", `❓ d6=${d6}: Efecto desconocido`);
                    }
                    
                    // Monster phase + status EOR + stair reroll + victory check
                    addLog("REY", `👾 Fase de Monstruos resuelta`);
                    addLog("REY", `🎴 Escaleras reroll + rotación cajas`);
                    addLog("REY", `✅ Victory check`);
                    
                    desc = `Fin de ronda completa (ver logs arriba)`;
                    break;
                case "SACRIFICE":
                    desc = `Realiza un Sacrificio: ${escapeHTML(JSON.stringify(log.data))}`;
                    break;
                case "ACCEPT_SACRIFICE":
                    desc = `Acepta consecuencias de locura (-5 Cordura)`;
                    break;
                default:
                    desc = `Realiza acción: ${escapeHTML(log.type)}`;
            }
            addLog(log.actor, desc);
        }
    }

    /**
     * Renderiza la lista de jugadores en la barra lateral con sus atributos y estatus.
     */
    function renderPlayersList(state) {
        playersStatusList.innerHTML = "";
        
        // Roles traducidos con iconos
        // Roles con iconos desde ROLE_DB (7 roles canónicos)
        const roleTranslations = {};
        Object.keys(ROLE_DB).forEach(rid => {
            roleTranslations[rid] = `${ROLE_DB[rid].name} ${ROLE_DB[rid].icon}`;
        });

        // Estados traducidos con iconos y clases de estilo
        const statusDetails = {
            "SANIDAD": { label: "✨ Sanidad", class: "status-SANIDAD" },
            "ENVENENADO": { label: "🤢 Envenenado", class: "status-ENVENENADO" },
            "MALDITO": { label: "💀 Maldito", class: "status-MALDITO" },
            "PARANOIA": { label: "👁️ Paranoico", class: "status-PARANOIA" },
            "TRAPPED": { label: "🕸️ Atrapado", class: "status-TRAPPED" },
            "TRAPPED_SPIDER": { label: "🕸️ Telaraña", class: "status-TRAPPED" },
            "STUN": { label: "⚡ Aturdido", class: "status-STUN" },
            "VANIDAD": { label: "💅 Vanidad", class: "status-VANIDAD" },
            "ILUMINADO": { label: "✨ Iluminado", class: "status-ILUMINADO" }
        };

        const seatHumans = (state.seats && state.seats.humans) || [];

        for (let pid in state.players) {
            const p = state.players[pid];
            const isActive = (activeActor === pid);
            const isLocal = humanPlayers.includes(pid);
            const isHumanSeat = seatHumans.includes(pid);
            
            const card = document.createElement("div");
            card.className = `player-status-card ${isActive ? 'active-turn' : ''}`;
            
            // Header del jugador
            const header = document.createElement("div");
            header.className = "player-status-header";
            
            const nameDiv = document.createElement("div");
            nameDiv.className = "player-status-name";
            
            const dot = document.createElement("span");
            dot.className = "token-dot";
            dot.style.backgroundColor = renderer.playerColors[pid];
            
            const nameText = document.createTextNode(`${pid} `);
            
            const roleSpan = document.createElement("span");
            roleSpan.className = "role";
            const roleName = roleTranslations[p.role_id] || p.role_id;
            const seatTag = isLocal ? " (TÚ)" : isHumanSeat ? " (AMIGO)" : " (BOT)";
            roleSpan.textContent = ` ${roleName}${seatTag}`;
            
            nameDiv.appendChild(dot);
            nameDiv.appendChild(nameText);
            nameDiv.appendChild(roleSpan);
            
            const actionsDiv = document.createElement("div");
            actionsDiv.className = "player-status-actions";
            actionsDiv.textContent = "Acciones: ";
            const actSpan = document.createElement("span");
            actSpan.textContent = p.remaining_actions;
            actionsDiv.appendChild(actSpan);
            
            header.appendChild(nameDiv);
            header.appendChild(actionsDiv);
            card.appendChild(header);
            
            // Barra de Cordura interactiva
            // Cálculo del porcentaje de cordura: rango de -5 a max.
            const totalSanityRange = p.sanity_max - (-5);
            const currentSanityProgress = p.sanity - (-5);
            const sanityPct = Math.max(0, Math.min(100, (currentSanityProgress / totalSanityRange) * 100));
            
            let sanityClass = "sanity-high";
            if (p.sanity < 0) {
                sanityClass = "sanity-low";
            } else if (p.sanity <= 2) {
                sanityClass = "sanity-medium";
            }
            
            const sanityBarContainer = document.createElement("div");
            sanityBarContainer.className = "sanity-bar-container";
            sanityBarContainer.title = `Progreso de Cordura: ${p.sanity}/${p.sanity_max}`;
            
            const sanityBarFill = document.createElement("div");
            sanityBarFill.className = `sanity-bar-fill ${sanityClass}`;
            sanityBarFill.style.transform = `scaleX(${sanityPct / 100})`;
            
            sanityBarContainer.appendChild(sanityBarFill);
            
            // Estadísticas (Cordura, Llaves, Sala)
            const stats = document.createElement("div");
            stats.className = "player-stats-grid";
            
            const sanityStat = document.createElement("div");
            sanityStat.className = "stat-item sanity";
            sanityStat.textContent = `🧠 ${p.sanity}/${p.sanity_max}`;
            
            const keysStat = document.createElement("div");
            keysStat.className = "stat-item keys";
            // Capacidad real calculada por el engine (incluye bonus de TREASURE_RING)
            const keyCap = p.keys_capacity ?? 1;
            keysStat.textContent = `🔑 ${p.keys}/${keyCap}`;
            keysStat.title = `Capacidad de llaves: ${keyCap} (${p.role_id})`;
            
            const roomStat = document.createElement("div");
            roomStat.className = "stat-item room";
            roomStat.textContent = `📍 ${p.room}`;
            roomStat.title = p.room;
            
            stats.appendChild(sanityStat);
            stats.appendChild(keysStat);
            stats.appendChild(roomStat);
            
            card.appendChild(stats);
            
            // Indicadores específicos de rol
            const roleIndicators = document.createElement("div");
            roleIndicators.className = "role-indicators";
            roleIndicators.style.fontSize = "0.7rem";
            roleIndicators.style.color = "var(--text-muted)";
            roleIndicators.style.marginTop = "4px";
            
            const indicators = [];
            const role = ROLE_DB[p.role_id];
            if (role) {
                switch (role.ability) {
                    case "free_move":
                        if (!p.free_move_used_this_turn) indicators.push(`${role.icon} Movimiento gratis disponible`);
                        else indicators.push(`${role.icon} Movimiento gratis usado`);
                        break;
                    case "double_roll":
                        if (!p.double_roll_used_this_turn) indicators.push(`${role.icon} Double roll disponible`);
                        else indicators.push(`${role.icon} Double roll usado`);
                        break;
                    case "shield":
                        if (p.shield > 0) indicators.push(`🛡️ Escudo: ${p.shield}`);
                        break;
                    case "blunt_free":
                        indicators.push(`${role.icon} Contundente GRATIS`);
                        break;
                    case "heal_group":
                        indicators.push(`${role.icon} Curar grupo (-1 propia)`);
                        break;
                    case "peek_hallway":
                        indicators.push(`${role.icon} Peek hallway`);
                        break;
                    case "deck_manipulation":
                        indicators.push(`${role.icon} Manipulación mazos`);
                        break;
                }
            }
            
            if (indicators.length > 0) {
                roleIndicators.textContent = indicators.join(" • ");
                card.appendChild(roleIndicators);
            }
            
            card.appendChild(sanityBarContainer);
            
            // Inventario de Objetos - P2-1: separar soulbound + charges + slots penalty
            const soulboundItems = p.soulbound_items || [];
            const objectCharges = p.object_charges || {};
            const slotsPenalty = p.object_slots_penalty || 0;
            
            // Slots reales calculados por el engine (ya descuentan la penalidad de sacrificio)
            const availableSlots = p.object_slots ?? 3;
            const baseSlotCount = availableSlots + slotsPenalty;
            
            // Objetos normales (no soulbound)
            const normalObjects = (p.objects || []).filter(obj => {
                const clean = obj.replace("OBJECT:", "");
                return !soulboundItems.includes(clean) && !["BOOK_CHAMBERS", "CROWN", "RING", "CHAMBERS_BOOK"].includes(clean);
            });
            
            // Objetos soulbound
            const sbObjects = (p.objects || []).filter(obj => {
                const clean = obj.replace("OBJECT:", "");
                return soulboundItems.includes(clean) || ["BOOK_CHAMBERS", "CROWN", "RING", "CHAMBERS_BOOK"].includes(clean);
            });
            
            if (normalObjects.length > 0 || sbObjects.length > 0) {
                const inv = document.createElement("div");
                inv.className = "player-inventory";
                inv.style.marginTop = "4px";
                
                // Objetos normales
                if (normalObjects.length > 0) {
                    const label = document.createElement("div");
                    label.style.fontSize = "0.65rem";
                    label.style.color = "var(--text-muted)";
                    label.style.marginBottom = "2px";
                    label.textContent = `Objetos (${normalObjects.length}/${availableSlots})`;
                    inv.appendChild(label);
                    
                    normalObjects.forEach(obj => {
                        const objPill = document.createElement("span");
                        objPill.className = "inventory-pill";
                        const cleanObj = obj.replace("OBJECT:", "").replace(/_/g, " ");
                        // Mostrar charges si tiene
                        const charge = objectCharges[cleanObj.toUpperCase().replace(/ /g, "_")] || objectCharges[obj];
                        const chargeText = (charge !== undefined && charge > 0) ? ` (${charge})` : "";
                        objPill.textContent = cleanObj + chargeText;
                        objPill.title = `Slot: ${normalObjects.indexOf(obj)+1}/${availableSlots}`;
                        inv.appendChild(objPill);
                    });
                    
                    // Slots vacíos
                    const emptySlots = availableSlots - normalObjects.length;
                    for (let i = 0; i < emptySlots; i++) {
                        const emptyPill = document.createElement("span");
                        emptyPill.className = "inventory-pill";
                        emptyPill.style.opacity = "0.3";
                        emptyPill.style.background = "var(--bg-input)";
                        emptyPill.textContent = "—";
                        inv.appendChild(emptyPill);
                    }
                }
                
                // Soulbound items
                if (sbObjects.length > 0) {
                    const sbLabel = document.createElement("div");
                    sbLabel.style.fontSize = "0.65rem";
                    sbLabel.style.color = "#C084FC";
                    sbLabel.style.marginTop = "6px";
                    sbLabel.style.marginBottom = "2px";
                    sbLabel.textContent = `🔒 Soulbound (${sbObjects.length})`;
                    inv.appendChild(sbLabel);
                    
                    sbObjects.forEach(obj => {
                        const objPill = document.createElement("span");
                        objPill.className = "inventory-pill";
                        objPill.style.borderColor = "#C084FC";
                        objPill.style.background = "rgba(192, 132, 252, 0.1)";
                        const cleanObj = obj.replace("OBJECT:", "").replace(/_/g, " ");
                        const charge = objectCharges[cleanObj.toUpperCase().replace(/ /g, "_")] || objectCharges[obj];
                        const chargeText = (charge !== undefined && charge > 0) ? ` (${charge})` : "";
                        objPill.textContent = "🔒 " + cleanObj + chargeText;
                        inv.appendChild(objPill);
                    });
                }
                
                card.appendChild(inv);
            } else if (slotsPenalty > 0) {
                // Mostrar penalty incluso sin objetos
                const inv = document.createElement("div");
                inv.className = "player-inventory";
                inv.style.marginTop = "4px";
                const label = document.createElement("div");
                label.style.fontSize = "0.65rem";
                label.style.color = "var(--color-danger)";
                label.textContent = `Slots reducidos: -${slotsPenalty} (${availableSlots}/${baseSlotCount})`;
                inv.appendChild(label);
                card.appendChild(inv);
            }
            
            // Estados activos
            if (p.statuses && p.statuses.length > 0) {
                const statusesDiv = document.createElement("div");
                statusesDiv.className = "player-inventory";
                statusesDiv.style.marginTop = "6px";
                p.statuses.forEach(status => {
                    const statusBadge = document.createElement("span");
                    const detail = statusDetails[status] || { label: status, class: "" };
                    statusBadge.className = `status-badge ${detail.class}`;
                    statusBadge.textContent = detail.label;
                    statusesDiv.appendChild(statusBadge);
                });
                card.appendChild(statusesDiv);
            }

            playersStatusList.appendChild(card);
        }
    }

    /**
     * Pide las acciones legales del actor activo y las renderiza en pantalla.
     *
     * IMPORTANTE: esta función es async y puede ser invocada varias veces seguidas
     * (respuesta HTTP de /act + broadcasts WS). El token de generación garantiza
     * que solo la invocación más reciente pinte botones — sin él, cada invocación
     * en vuelo agregaba su propio set de botones y las opciones salían duplicadas.
     */
    let renderActionsToken = 0;
    async function renderActions(state) {
        const token = ++renderActionsToken;
        actionsGrid.innerHTML = "";

        // Si el juego terminó, no mostramos acciones
        if (state.game_over) {
            currentLegalActions = [];
            return;
        }

        // Solo mostramos acciones si el actor activo es un asiento controlado por ESTE navegador.
        // El turno del Rey lo resuelve el servidor automáticamente.
        const isLocal = humanPlayers.includes(activeActor);
        if (!isLocal) {
            currentLegalActions = [];
            const waitMsg = document.createElement("div");
            waitMsg.style.color = "var(--text-muted)";
            waitMsg.style.textAlign = "center";
            waitMsg.style.padding = "20px";
            waitMsg.style.fontSize = "0.9rem";
            waitMsg.style.fontStyle = "italic";
            if (activeActor === "KING") {
                waitMsg.textContent = "👑 El Rey de Amarillo actúa...";
            } else if (state.seats && (state.seats.humans || []).includes(activeActor)) {
                waitMsg.textContent = `⌛ Esperando a ${activeActor} (otro jugador)...`;
            } else {
                waitMsg.textContent = `🤖 ${activeActor} (bot) pensando turno...`;
            }
            actionsGrid.appendChild(waitMsg);

            // Rescate: si el turno es de un asiento humano SIN reclamar (amigo que nunca
            // se unió o que salió), permitir tomar el control desde este navegador.
            // Los asientos reclamados por otro navegador activo no se ofrecen aquí;
            // para esos casos existe el force-claim del seat picker (Unirse).
            const seatUnclaimed = !((state.seats && state.seats.claims) || {})[activeActor];
            if (activeActor !== "KING" && seatUnclaimed && state.seats && (state.seats.humans || []).includes(activeActor)) {
                const takeBtn = document.createElement("button");
                takeBtn.className = "action-btn";
                takeBtn.style.marginTop = "8px";
                takeBtn.textContent = `🎮 Tomar control de ${activeActor}`;
                takeBtn.title = "Reclama este asiento para este navegador (útil si el otro jugador no está).";
                takeBtn.addEventListener("click", async () => {
                    if (!confirm(`¿Tomar control de ${activeActor} en este navegador?`)) return;
                    try {
                        await api.claimSeats(currentGameId, [activeActor], "add", true);
                        if (!humanPlayers.includes(activeActor)) humanPlayers.push(activeActor);
                        localStorage.setItem("carcosa_my_seats", JSON.stringify(humanPlayers));
                        addLog("SISTEMA", `🎮 Ahora controlas a ${activeActor} desde este navegador.`, "game-event");
                        renderActions(currentGameState);
                    } catch (e) {
                        alert(`No se pudo tomar control: ${e.message}`);
                    }
                });
                actionsGrid.appendChild(takeBtn);
            }
            return;
        }

        let raw;
        try {
            const data = await api.getLegalActions(currentGameId, activeActor);
            raw = data.actions || [];
        } catch (error) {
            console.error("Error al obtener acciones legales:", error);
            return;
        }

        // Si mientras esperábamos llegó un estado más nuevo, abortar: otra invocación pintará.
        if (token !== renderActionsToken) return;

        // /legal es la ÚNICA fuente de verdad — sin filtrado local.
        currentLegalActions = raw;
        actionsGrid.innerHTML = "";

        // Banner de contexto: sacrificio pendiente / movimiento bloqueado / acciones restantes
        const pendingSac = state.flags && state.flags.PENDING_SACRIFICE_CHECK;
        const pendingList = Array.isArray(pendingSac) ? pendingSac : (pendingSac ? [pendingSac] : []);
        if (pendingList.includes(activeActor)) {
            const banner = document.createElement("div");
            banner.style.cssText = "color: var(--color-danger); text-align: center; padding: 8px; font-weight: 700; border: 1px solid var(--color-danger); border-radius: 6px; margin-bottom: 8px;";
            banner.textContent = `💀 ¡LOCURA INMINENTE! ${activeActor} debe elegir: sacrificar o aceptar caer a -5.`;
            actionsGrid.appendChild(banner);
            audio.playSacrifice();
        }
        if ((state.movement_blocked_players || []).includes(activeActor)) {
            const mb = document.createElement("div");
            mb.style.cssText = "color: #7dd3fc; text-align: center; padding: 4px; font-size: 0.8rem;";
            mb.textContent = "🧊 Movimiento bloqueado este turno (Reina Helada)";
            actionsGrid.appendChild(mb);
        }

        if (!raw || raw.length === 0) {
            const noActions = document.createElement("div");
            noActions.style.color = "var(--color-danger)";
            noActions.style.textAlign = "center";
            noActions.textContent = "No hay acciones legales disponibles.";
            actionsGrid.appendChild(noActions);
            return;
        }

        // Agrupar/deduplicar acciones para no inundar la UI:
        // - USE_MOTEMEY_BUY (legacy) se oculta si existe USE_MOTEMEY_BUY_START (mismo efecto → botón duplicado)
        // - Las decenas de combinaciones USE_TABERNA_ROOMS se colapsan en UN botón que abre modal
        const hasBuyStart = raw.some(a => a.type === "USE_MOTEMEY_BUY_START");
        const tabernaActions = raw.filter(a => a.type === "USE_TABERNA_ROOMS");
        const actions = raw.filter(a =>
            a.type !== "USE_TABERNA_ROOMS" &&
            !(a.type === "USE_MOTEMEY_BUY" && hasBuyStart)
        );
        if (tabernaActions.length > 0) {
            actions.push({ type: "USE_TABERNA_ROOMS", data: {}, _tabernaGroup: tabernaActions });
        }

        actions.forEach(action => {
                const btn = document.createElement("button");
                btn.className = "action-btn";
                
                // Formatear texto descriptivo e icono del botón según el tipo de acción
                let actionText = "";
                let actionCost = "";
                let isEndTurn = false;

                switch (action.type) {
                    case "MOVE":
                        actionText = `🚶 Moverse a ${action.data.to}`;
                        actionCost = "1 Ac.";
                        break;
                    case "SEARCH":
                        actionText = "🔍 Buscar en la Habitación";
                        actionCost = "1 Ac.";
                        break;
                    case "MEDITATE":
                        actionText = "🧘 Meditar (Recuperar Cordura)";
                        actionCost = "1 Ac.";
                        break;
                    case "DISCARD_SANIDAD":
                        actionText = "✨ Consumir Carta SANIDAD (Quitar Estados)";
                        actionCost = "Gratis";
                        break;
                    case "END_TURN":
                        actionText = "⏹️ Finalizar Turno";
                        actionCost = "-";
                        isEndTurn = true;
                        btn.classList.add("action-end-turn");
                        break;
                    case "KING_ENDROUND":
                        actionText = "👑 Resolver Turno del Rey";
                        actionCost = "-";
                        btn.style.borderColor = "var(--color-yellow)";
                        btn.style.color = "var(--color-yellow)";
                        break;
                    case "SACRIFICE":
                        // El servidor ya envía las opciones correctas según available_sacrifice_options
                        // Cada action SACRIFICE es una opción distinta
                        let sacrificeLabel = "";
                        if (action.data.mode === "SANITY_MAX") {
                            sacrificeLabel = "1 Cordura Máxima";
                        } else if (action.data.mode === "OBJECT_SLOT") {
                            if (action.data.discard_object_id) {
                                sacrificeLabel = `Descartar: ${action.data.discard_object_id}`;
                            } else {
                                sacrificeLabel = "Reducir slot de objeto (elegir al confirmar)";
                            }
                        } else {
                            sacrificeLabel = action.data.mode || "Opción desconocida";
                        }
                        actionText = `💀 Sacrificar: ${sacrificeLabel}`;
                        actionCost = "Inter.";
                        btn.style.borderColor = "var(--color-danger)";
                        // Marcar botón para posible confirmación extra
                        btn.dataset.sacrificeMode = action.data.mode;
                        btn.dataset.discardObject = action.data.discard_object_id || "";
                        break;
                    case "ACCEPT_SACRIFICE":
                        actionText = "Acceptar Sanity Loss (-5 Cordura)";
                        actionCost = "Inter.";
                        btn.style.borderColor = "var(--color-danger)";
                        break;
                    case "ESCAPE_TRAPPED":
                        actionText = "🕸️ Intentar Escapar (Lanzar d6)";
                        actionCost = "1 Ac.";
                        break;
                    case "USE_MOTEMEY_SELL":
                        actionText = `💰 Vender ${action.data.item_name} en Motemey`;
                        actionCost = "Gratis";
                        break;
                    case "USE_MOTEMEY_BUY_START":
                        actionText = "🛒 Comprar en Motemey (Ofrece 2 Cartas)";
                        actionCost = "2 Cord.";
                        btn.title = "Paga 2 cordura → muestra 2 cartas del mazo Motemey (13 cartas: 3 Brújula, 3 Vial, 2 Contundente, 4 Tesoros, 1 Llave, 1 Cuento) · Elige 1, otra al fondo";
                        btn.dataset.showMotemeyModal = "true";
                        break;
                    case "USE_MOTEMEY_BUY_CHOOSE":
                        actionText = `🃏 Motemey: Elegir Opción ${action.data.chosen_index + 1}`;
                        actionCost = "-";
                        btn.title = `Elige carta ${action.data.chosen_index + 1} de las 2 mostradas`;
                        break;
                    case "USE_YELLOW_DOORS":
                        actionText = `🚪 Transportar a ${action.data.target_player}`;
                        actionCost = "1 Ac. (Target -1 Cordura)";
                        btn.title = "Teletransporta target a tu room · Target sufre -1 cordura · Reveal room";
                        break;
                    case "USE_TABERNA_ROOMS":
                        actionText = `🍻 Taberna: Intercambiar 2 habitaciones (elegir)`;
                        actionCost = "FREE (-1 Cordura)";
                        btn.title = "FREE · Solo habitaciones (no pasillos) · 2 distintas · 1 uso/turno · -1 Cordura al actor · Intercambia mazos (peek mutuo)";
                        break;
                    case "USE_ARMORY_DROP":
                        const dropText = action.data.item_name === "KEY" ? "Llave" : action.data.item_name;
                        actionText = `⬇️ Armería: Dejar ${dropText}`;
                        actionCost = "FREE";
                        btn.title = "Storage máx 2 items (llaves + objetos combinados) · No soulbound · FREE";
                        break;
                    case "USE_ARMORY_TAKE":
                        actionText = "⬆️ Armería: Tomar Ítem Guardado";
                        actionCost = "FREE";
                        btn.title = "Recupera item del storage (máx 2 items total) · FREE";
                        break;
                    case "USE_SALON_BELLEZA":
                        actionText = "💅 Salón Belleza: Adquirir Vanidad";
                        actionCost = "1 Ac.";
                        const salonUses = currentGameState?.salon_belleza_uses || 0;
                        btn.title = `Usos globales: ${salonUses} · Cada 2 usos = VANIDAD (+1 daño cordura permanente) · PAID`;
                        break;
                    case "USE_CAPILLA":
                        actionText = "⛪ Capilla: Meditar (d6+2 Cordura, 1/6 PARANOIA)";
                        actionCost = "1 Ac.";
                        btn.title = "Cura d6+2 cordura · 16.6% chance PARANOIA (5 turnos, no compartir room) · PAID";
                        break;
                    case "USE_CAMARA_LETAL_RITUAL":
                        actionText = "🔴 Ritual Cámara Letal (7ª Llave)";
                        actionCost = "1 Ac. (2 jugadores)";
                        btn.style.borderColor = "var(--color-danger)";
                        btn.title = "Requiere 2 jugadores en la habitación. d6: 1-2=[7,0] | 3-6=[4,3] cordura. Otorga 7ª llave.";
                        action._confirm = "camara_letal";
                        break;
                    case "USE_ATTACH_TALE":
                        actionText = `📖 Unir Cuento ${action.data.tale_id.replace("TALE_", "")}`;
                        actionCost = "Gratis";
                        break;
                    case "USE_HEALER_HEAL":
                        actionText = "🩹 Curar Grupo (Sacrificar 1 Cordura)";
                        actionCost = "Gratis";
                        break;
                    case "USE_BLUNT":
                        actionText = "🔨 Atacar Monstruo con Objeto Contundente";
                        actionCost = "Gratis";
                        break;
                    case "USE_PORTABLE_STAIRS":
                        actionText = `🪜 Escalera: Moverse ${action.data.direction === "UP" ? "Piso Arriba" : "Piso Abajo"}`;
                        actionCost = "Gratis";
                        break;
                    case "USE_OBJECT":
                        actionText = `🎒 Usar Objeto: ${action.data.object_id}`;
                        actionCost = "Gratis";
                        break;
                    case "PEEK_ROOM_DECK":
                        actionText = `👁️ Mirador: Mirar carta de ${action.data.room_id}`;
                        actionCost = "1 Ac.";
                        break;
                    case "SKIP_PEEK":
                        actionText = "⏩ Mirador: Saltar Acción";
                        actionCost = "Gratis";
                        break;
                    default:
                        actionText = `⚙️ Acción: ${action.type}`;
                        actionCost = "-";
                }

                btn.textContent = actionText + " ";
                if (actionCost) {
                    const costSpan = document.createElement("span");
                    costSpan.className = "action-cost";
                    costSpan.textContent = actionCost;
                    btn.appendChild(costSpan);
                }
                
                // Evento click ÚNICO para enviar acción (o abrir modal de confirmación/selección).
                // La data del action se envía EXACTAMENTE como la entregó /legal — el engine
                // valida con igualdad estricta y agregar campos extra la vuelve ilegal.
                btn.addEventListener("click", () => {
                    audio.playClick();

                    if (action._tabernaGroup) {
                        showTabernaModal(action._tabernaGroup);
                        return;
                    }
                    if (action._confirm === "camara_letal") {
                        showCamaraLetalModal(action);
                        return;
                    }

                    executePlayerAction(action);
                });

                // Micro-retroalimentación auditiva al sobrevolar
                btn.addEventListener("mouseenter", () => {
                    audio.playHover();
                });

                actionsGrid.appendChild(btn);

            });
    }

    /**
     * Envía la acción seleccionada al servidor FastAPI.
     */
    async function executePlayerAction(action) {
        if (actionInFlight) return; // evitar doble envío con estado stale (doble click / canvas)
        actionInFlight = true;
        const actingActor = activeActor;
        try {
            // Deshabilitar botones de acción temporalmente
            const buttons = actionsGrid.querySelectorAll("button");
            buttons.forEach(b => b.disabled = true);

            // Llamar API act
            const result = await api.act(currentGameId, actingActor, action.type, action.data);

            // Actualizar estado devuelto
            updateState(result.state);

            // P1-7: Mostrar modal Motemey BUY_START después de ejecutar
            if (action.type === "USE_MOTEMEY_BUY_START" &&
                result.state?.pending_motemey_choice?.[actingActor]) {
                setTimeout(() => {
                    showMotemeyBuyModal(action);
                }, 100);
            }

        } catch (error) {
            alert(`Error al ejecutar acción: ${error.message}`);
            renderActions(currentGameState);
        } finally {
            actionInFlight = false;
        }
    }

    /**
     * Muestra la superposición de Game Over con los resultados de la partida.
     */
    function showGameOver(state) {
        if (gameOverShown) return;
        gameOverShown = true;
        gameOverOverlay.classList.remove("hidden");

        // Quitar clases previas
        gameOverBox.classList.remove("outcome-WIN", "outcome-LOSE");

        // P3-3: Audio cue contextual para Game Over
        if (state.outcome === "WIN") {
            audio.playVictory();
        } else {
            audio.playDefeat();
        }

        if (state.outcome === "WIN") {
            gameOverBox.classList.add("outcome-WIN");
            gameOverTitle.textContent = "🏆 ¡VICTORIA CANÓNICA!";
            const totalKeys = Object.values(state.players).reduce((sum, p) => sum + (p.keys || 0), 0);
            gameOverDetails.innerHTML = `
                Felicidades, el grupo ha logrado escapar de la influencia del Rey de Amarillo.<br><br>
                <strong>Detalles:</strong><br>
                - Rondas jugadas: ${state.round}<br>
                - Llaves reunidas: ${totalKeys}/${state.keys_to_win || 4}<br>
                - Semilla RNG: ${state.seed ?? seedInput.value}
            `;
            addLog("SISTEMA", "¡Juego Terminado! El grupo de almas perdidas HA GANADO la partida.", "game-event");
        } else {
            gameOverBox.classList.add("outcome-LOSE");
            gameOverTitle.textContent = "👁️ HASTA EL FIN DE CARCOSA...";
            
            let causeDetails = "";
            let causeLog = "";
            
            if (state.outcome && state.outcome.startsWith("LOSE_ALL_MINUS5")) {
                // Formato: "LOSE_ALL_MINUS5 (SOURCE -> PID)"
                const sourceMatch = state.outcome.match(/LOSE_ALL_MINUS5\s*\((.+)\)/);
                const source = sourceMatch ? sourceMatch[1] : "desconocido";
                causeDetails = `Todas las almas cayeron a -5 cordura.<br><strong>Golpe final:</strong> ${escapeHTML(source)}`;
                causeLog = `¡Derrota! Todas las almas en -5 cordura. Fuente: ${source}`;
            } else if (state.outcome === "LOSE_KEYS_DESTROYED") {
                const keysTotal = state.keys_total || 6;
                const keysDestroyed = state.keys_destroyed || 0;
                const keysAvailable = keysTotal - keysDestroyed;
                causeDetails = `Llaves destruidas superaron el umbral.<br><strong>Llaves en juego:</strong> ${keysAvailable} / ${keysTotal} (umbral: 3)<br><strong>Llaves destruidas:</strong> ${keysDestroyed}`;
                causeLog = `¡Derrota! Llaves destruidas: ${keysDestroyed}, restantes en juego: ${keysAvailable} ≤ 3`;
            } else {
                causeDetails = `El Rey de Amarillo ha reclamado a las almas perdidas o destruido sus llaves.<br><br><strong>Causa:</strong> ${escapeHTML(state.outcome || "desconocida")}`;
                causeLog = `¡Derrota! ${state.outcome || "Causa desconocida"}`;
            }
            
            gameOverDetails.innerHTML = `
                ${causeDetails}<br><br>
                <strong>Detalles:</strong><br>
                - Rondas jugadas: ${state.round}<br>
                - Semilla RNG: ${state.seed ?? seedInput.value}
            `;
            addLog("SISTEMA", causeLog, "game-event");
        }

        // Registro de partida: el servidor auto-guarda al terminar (state.saved_to).
        if (state.saved_to) {
            addLog("SISTEMA", `📼 Registro de partida guardado automáticamente en: ${escapeHTML(state.saved_to)}`, "game-event");
        } else if (api && currentGameId && isHost) {
            // Respaldo (server antiguo o WS sin saved_to): solo el host pide guardar; /save es idempotente.
            api.saveGame(currentGameId).then(res => {
                addLog("SISTEMA", `📼 Registro de partida guardado en: ${escapeHTML(res.saved_to)}`, "game-event");
            }).catch(err => {
                console.error("Error al guardar partida:", err);
            });
        }
    }

    /**
     * Añade un mensaje al Event Log de la interfaz.
     */
    function addLog(actor, message, customClass = "") {
        const entry = document.createElement("div");
        entry.className = `log-entry actor-${actor} ${customClass}`;
        
        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        
        const timeSpan = document.createElement("span");
        timeSpan.className = "time";
        timeSpan.textContent = `[${timestamp}]`;
        
        const actorSpan = document.createElement("span");
        actorSpan.className = "actor";
        actorSpan.textContent = `${actor}: `;
        
        const msgSpan = document.createElement("span");
        msgSpan.className = "msg-text";
        msgSpan.innerHTML = message;
        
        entry.appendChild(timeSpan);
        if (actor !== "SISTEMA") {
            entry.appendChild(actorSpan);
        }
        entry.appendChild(msgSpan);
        
        logContent.appendChild(entry);
        
        // Auto-scroll al final
        logContent.scrollTop = logContent.scrollHeight;
    }

    // Ventanas flotantes de animación de tirada de dados holográfica
    function triggerDiceRollAnimation(rolls, purpose, sanity, total) {
        if (!fxEnabled) return;
        audio.playRoll();

        const overlay = document.getElementById("diceRollerOverlay");
        const titleEl = document.getElementById("diceRollPurpose");
        const resultValue = document.getElementById("diceRollResultValue");
        const subDetails = document.getElementById("diceRollSubDetails");
        const die1 = document.getElementById("die1");
        const die2 = document.getElementById("die2");

        // Configurar metadatos del lanzamiento
        titleEl.textContent = `TIRADA: ${purpose.replace(/_/g, " ")}`;
        resultValue.textContent = "-";
        subDetails.textContent = "Modulando el Caos...";
        
        // Empezar animación de rodaje neón
        die1.classList.add("rolling");
        die2.classList.add("rolling");
        die1.textContent = "?";
        die2.textContent = "?";
        
        overlay.classList.remove("hidden");

        // Resolver giro físico simulado tras 1.2 segundos
        setTimeout(() => {
            die1.classList.remove("rolling");
            die2.classList.remove("rolling");
            
            const d1Val = rolls[0] || 1;
            const d2Val = rolls[1] || 1;
            
            die1.textContent = d1Val;
            if (rolls.length === 1) {
                die2.style.display = "none";
            } else {
                die2.style.display = "flex";
                die2.textContent = d2Val;
            }

            resultValue.textContent = total;
            const rollsSum = rolls.reduce((a, b) => a + b, 0);
            const sanityText = sanity > 0 ? ` + cordura (${sanity})` : sanity < 0 ? ` - cordura (${Math.abs(sanity)})` : '';
            subDetails.textContent = `Dados (${rolls.join(" + ")}) = ${rollsSum}${sanityText}`;
        }, 1200);

        // Permitir click para omitir
        overlay.onclick = () => {
            overlay.classList.add("hidden");
        };

        // Auto ocultar después de 3.2 segundos
        setTimeout(() => {
            overlay.classList.add("hidden");
        }, 3200);
    }

    // Modal flotante de develación de cartas del mazo
    function triggerCardRevealAnimation(cardKey) {
        if (!fxEnabled) return;
        let entity = null;
        let cardTitle = cardKey.replace(/_/g, " ");
        let cardIcon = "🃏";
        let cardType = "EVENTO";
        let cardDesc = "El destino se devela ante tus ojos en Carcosa.";
        let classType = "type-event";

        if (cardKey.startsWith("OMEN:")) {
            entity = ENTITY_DB[cardKey];
        } else {
            const cleanKey = cardKey.replace("EVENTS:", "").replace("EVENT:", "").replace("STATE:", "").replace("OBJECT:", "").replace("MONSTER:", "");
            entity = ENTITY_DB[cleanKey];
        }

        if (entity) {
            cardTitle = entity.name;
            cardIcon = entity.icon;
            cardType = entity.type;
            cardDesc = entity.desc;
            classType = `type-${entity.type}`;
        } else {
            if (cardKey.startsWith("MONSTER:")) {
                cardType = "MONSTRUO";
                cardIcon = "👾";
                classType = "type-monster";
            } else if (cardKey.startsWith("OMEN:")) {
                cardType = "PRESAGIO";
                cardIcon = "⚠️";
                classType = "type-omen";
            } else if (cardKey.startsWith("OBJECT:")) {
                cardType = "OBJETO";
                cardIcon = "🎒";
                classType = "type-object";
            } else if (cardKey.startsWith("STATE:")) {
                cardType = "ESTADO";
                cardIcon = "✨";
                classType = "type-state";
            } else if (cardKey === "KEY") {
                cardType = "LLAVE FÍSICA";
                cardIcon = "🔑";
                classType = "type-object";
            }
        }

        // Determinar sonido contextual
        if (cardType === "MONSTRUO" || cardType === "PRESAGIO" || cardType === "monster" || cardType === "omen") {
            audio.playMonster();
        } else {
            audio.playClick();
        }

        const overlay = document.getElementById("cardRevealOverlay");
        const box = document.getElementById("cardRevealBox");
        const iconEl = document.getElementById("cardRevealIcon");
        const typeEl = document.getElementById("cardRevealType");
        const titleEl = document.getElementById("cardRevealTitle");
        const descEl = document.getElementById("cardRevealDesc");

        box.className = `card-reveal-box ${classType}`;
        iconEl.textContent = cardIcon;
        typeEl.textContent = cardType.toUpperCase();
        titleEl.textContent = cardTitle;
        descEl.innerHTML = cardDesc;

        overlay.classList.remove("hidden");

        const autoCloseTimeout = setTimeout(() => {
            overlay.classList.add("hidden");
        }, 4000);

        overlay.onclick = () => {
            clearTimeout(autoCloseTimeout);
            overlay.classList.add("hidden");
        };
    }

    // Modal para Taberna: elegir la combinación exacta de 2 habitaciones a intercambiar.
    // Recibe la lista de acciones legales USE_TABERNA_ROOMS del servidor y ejecuta una tal cual.
    function showTabernaModal(tabernaActions) {
        if (!tabernaActions || tabernaActions.length === 0) return;

        const roomsA = [...new Set(tabernaActions.map(a => a.data.room_a))].sort();

        const modal = document.createElement("div");
        modal.className = "card-reveal-overlay";
        modal.style.zIndex = "var(--z-modal)";
        modal.innerHTML = `
            <div class="card-reveal-box type-event" style="max-width: 420px;">
                <div class="card-reveal-header">
                    <span class="card-reveal-icon">🍻</span>
                    <span class="card-reveal-type">TABERNA</span>
                </div>
                <h2 class="card-reveal-title">Intercambiar Mazos de 2 Habitaciones</h2>
                <div class="card-reveal-divider"></div>
                <p class="card-reveal-desc">FREE · -1 Cordura · 1 uso/turno · Solo habitaciones (no pasillos). Ambas ven la carta superior del nuevo mazo (peek mutuo).</p>
                <div style="display: flex; gap: 8px; justify-content: center; margin: 16px 0; align-items: center;">
                    <select id="tabernaRoomA" class="form-control" style="width: auto;"></select>
                    <span style="font-size: 1.2rem;">⟷</span>
                    <select id="tabernaRoomB" class="form-control" style="width: auto;"></select>
                </div>
                <div style="display: flex; gap: 12px; justify-content: center;">
                    <button id="btnTabernaConfirm" class="btn btn-primary" style="flex: 1;">Confirmar (-1 Cordura)</button>
                    <button id="btnTabernaCancel" class="btn btn-secondary" style="flex: 1;">Cancelar</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        const selA = modal.querySelector("#tabernaRoomA");
        const selB = modal.querySelector("#tabernaRoomB");

        function fillA() {
            selA.innerHTML = roomsA.map(r => `<option value="${escapeHTML(r)}">${escapeHTML(r)}</option>`).join("");
        }
        function fillB() {
            const a = selA.value;
            const options = tabernaActions.filter(x => x.data.room_a === a).map(x => x.data.room_b);
            selB.innerHTML = options.map(r => `<option value="${escapeHTML(r)}">${escapeHTML(r)}</option>`).join("");
        }
        fillA();
        fillB();
        selA.addEventListener("change", fillB);

        modal.querySelector("#btnTabernaConfirm").addEventListener("click", () => {
            const chosen = tabernaActions.find(x => x.data.room_a === selA.value && x.data.room_b === selB.value);
            document.body.removeChild(modal);
            if (chosen) executePlayerAction(chosen);
        });
        modal.querySelector("#btnTabernaCancel").addEventListener("click", () => {
            document.body.removeChild(modal);
        });
        modal.onclick = (e) => {
            if (e.target === modal) document.body.removeChild(modal);
        };
    }

    // Modal para Cámara Letal - confirmación con detalles d6
    function showCamaraLetalModal(cameraAction) {
        const modal = document.createElement("div");
        modal.className = "card-reveal-overlay";
        modal.style.zIndex = "var(--z-modal)";
        modal.innerHTML = `
            <div class="card-reveal-box type-event" style="max-width: 450px;">
                <div class="card-reveal-header">
                    <span class="card-reveal-icon">🔴</span>
                    <span class="card-reveal-type">CÁMARA LETAL</span>
                </div>
                <h2 class="card-reveal-title">Ritual de la 7ª Llave</h2>
                <div class="card-reveal-divider"></div>
                <p class="card-reveal-desc">
                    <strong>Requisitos:</strong> 2 jugadores en la habitación, ritual no completado.<br>
                    <strong>Costos por d6:</strong>
                    <ul style="margin: 8px 0; padding-left: 20px;">
                        <li>1-2: [7, 0] cordura (un jugador -7, otro 0)</li>
                        <li>3-6: [4, 3] cordura (un jugador -4, otro -3)</li>
                    </ul>
                    <strong>Efecto:</strong> Otorga la 7ª Llave física al pool (incrementa llaves disponibles).
                    <br><br>Solo se puede realizar una vez por partida.
                </p>
                <div style="display: flex; gap: 12px; justify-content: center; margin-top: 16px;">
                    <button id="btnCamaraConfirm" class="btn btn-primary" style="flex: 1;">Confirmar Ritual</button>
                    <button id="btnCamaraCancel" class="btn btn-secondary" style="flex: 1;">Cancelar</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        modal.querySelector("#btnCamaraConfirm").addEventListener("click", () => {
            document.body.removeChild(modal);
            executePlayerAction(cameraAction);
        });
        
        modal.querySelector("#btnCamaraCancel").addEventListener("click", () => {
            document.body.removeChild(modal);
            renderActions(currentGameState);
        });
        
        modal.onclick = (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
                renderActions(currentGameState);
            }
        };
    }

    // Modal para Motemey BUY_START - muestra 2 cartas para elegir
    function showMotemeyBuyModal(buyAction) {
        // This is handled by the BUY_START action which sets pending_motemey_choice
        // The BUY_CHOOSE actions are already rendered as buttons
        // We just need to show a visual modal with the 2 cards
        const pending = currentGameState?.pending_motemey_choice?.[activeActor];
        if (!pending || pending.length < 2) {
            // Sin elección pendiente en el estado: los botones BUY_CHOOSE de /legal
            // siguen disponibles en el panel de acciones. NUNCA re-ejecutar BUY_START
            // (cobraría 2 de cordura otra vez).
            return;
        }
        
        const [card1, card2] = pending;
        
        const getEntity = (cardKey) => {
            if (cardKey.startsWith("OMEN:")) return ENTITY_DB[cardKey];
            const clean = cardKey.replace("EVENTS:", "").replace("EVENT:", "").replace("STATE:", "").replace("OBJECT:", "").replace("MONSTER:", "");
            return ENTITY_DB[clean];
        };
        
        const e1 = getEntity(card1);
        const e2 = getEntity(card2);
        
        const modal = document.createElement("div");
        modal.className = "card-reveal-overlay";
        modal.style.zIndex = "var(--z-modal)";
        modal.innerHTML = `
            <div class="card-reveal-box type-object" style="max-width: 500px;">
                <div class="card-reveal-header">
                    <span class="card-reveal-icon">⚖️</span>
                    <span class="card-reveal-type">MOTEMEY - COMPRA</span>
                </div>
                <h2 class="card-reveal-title">Elige tu Objeto (2 cordura pagados)</h2>
                <div class="card-reveal-divider"></div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 16px 0;">
                    <div class="motemey-choice" data-index="0" style="border: 2px solid var(--border-color); border-radius: 8px; padding: 12px; cursor: pointer; transition: all 0.2s;">
                        <div style="font-size: 2rem; text-align: center;">${e1?.icon || "🃏"}</div>
                        <div style="font-weight: 600; text-align: center; margin: 8px 0;">${e1?.name || card1}</div>
                        <div style="font-size: 0.8rem; color: var(--text-muted); text-align: center;">${e1?.desc?.substring(0, 100) || ""}...</div>
                    </div>
                    <div class="motemey-choice" data-index="1" style="border: 2px solid var(--border-color); border-radius: 8px; padding: 12px; cursor: pointer; transition: all 0.2s;">
                        <div style="font-size: 2rem; text-align: center;">${e2?.icon || "🃏"}</div>
                        <div style="font-weight: 600; text-align: center; margin: 8px 0;">${e2?.name || card2}</div>
                        <div style="font-size: 0.8rem; color: var(--text-muted); text-align: center;">${e2?.desc?.substring(0, 100) || ""}...</div>
                    </div>
                </div>
                <p class="card-reveal-footer">Click en una carta para elegir · La otra vuelve al fondo del mazo</p>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Hover effects
        modal.querySelectorAll(".motemey-choice").forEach(choice => {
            choice.addEventListener("mouseenter", () => {
                choice.style.borderColor = "var(--color-accent)";
                choice.style.boxShadow = "0 0 15px var(--color-accent-glow)";
            });
            choice.addEventListener("mouseleave", () => {
                choice.style.borderColor = "var(--border-color)";
                choice.style.boxShadow = "none";
            });
            choice.addEventListener("click", () => {
                const chosenIndex = parseInt(choice.dataset.index);
                document.body.removeChild(modal);
                // Dispatch BUY_CHOOSE with chosen_index
                const chooseAction = {
                    actor: activeActor,
                    type: "USE_MOTEMEY_BUY_CHOOSE",
                    data: { chosen_index: chosenIndex }
                };
                executePlayerAction(chooseAction);
            });
        });
        
        modal.onclick = (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
                renderActions(currentGameState);
            }
        };
    }


    // Loop de animación continuo a 60fps para efectos visuales fluidos
    function renderLoop() {
        if (currentGameState) {
            renderer.draw(currentGameState, currentLegalActions, hoveredRoomId);
        }
        requestAnimationFrame(renderLoop);
    }
    requestAnimationFrame(renderLoop);

    /**
     * Infer events by comparing previous and current game state.
     * This supplements the server's action_log with inferred events.
     */
    function inferEventsFromStateDiff(prevState, currState) {
        console.log("[INFER] inferEventsFromStateDiff called", { 
            prevState: !!prevState, 
            currState: !!currState,
            prevRooms: prevState ? Object.keys(prevState.rooms || {}) : [],
            currRooms: currState ? Object.keys(currState.rooms || {}) : []
        });
        if (!prevState || !currState) return;

        // 1. Detect room changes for players (room swaps, special room reveals)
        for (let pid in currState.players) {
            const prevPlayer = prevState.players[pid];
            const currPlayer = currState.players[pid];
            if (!prevPlayer || !currPlayer) continue;

            // Room changed - check for special room reveal or room swap
            if (prevPlayer.room !== currPlayer.room) {
                const prevRoom = prevState.rooms[prevPlayer.room];
                const currRoom = currState.rooms[currPlayer.room];
                
                // Check for special room reveal
                if (currRoom && currRoom.special_card_id && currRoom.special_revealed && 
                    !(prevRoom && prevRoom.special_card_id && prevRoom.special_revealed)) {
                    // Special room was revealed
                    processServerLog({
                        event: "SPECIAL_ROOM_REVEALED",
                        player: pid,
                        room: currPlayer.room,
                        special_id: currRoom.special_card_id
                    });
                }
            }

            // Sanity loss detection
            if (prevPlayer.sanity > currPlayer.sanity) {
                const amount = prevPlayer.sanity - currPlayer.sanity;
                processServerLog({
                    event: "SANITY_LOSS",
                    player: pid,
                    amount: amount,
                    source: "UNKNOWN"
                });
            }

            // Sanity gain detection
            if (prevPlayer.sanity < currPlayer.sanity) {
                const amount = currPlayer.sanity - prevPlayer.sanity;
                processServerLog({
                    event: "SANITY_GAIN",
                    player: pid,
                    amount: amount,
                    source: "MEDITATE"
                });
            }

            // Key gained
            if (prevPlayer.keys < currPlayer.keys) {
                processServerLog({
                    event: "KEY_GRANTED",
                    player: pid
                });
            }

            // Object gained
            if (prevPlayer.objects && currPlayer.objects) {
                const newObjects = currPlayer.objects.filter(o => !prevPlayer.objects.includes(o));
                for (const obj of newObjects) {
                    processServerLog({
                        event: "ITEM_GRANTED",
                        player: pid,
                        item: obj
                    });
                }
            }

            // Status gained
            if (prevPlayer.statuses && currPlayer.statuses) {
                const newStatuses = currPlayer.statuses.filter(s => !prevPlayer.statuses.includes(s));
                for (const status of newStatuses) {
                    processServerLog({
                        event: "STATUS_ADDED",
                        player: pid,
                        status: status,
                        duration: 2 // default
                    });
                }
            }
        }

        // 2. Detect card reveals by comparing room states
        for (let roomId in currState.rooms) {
            const prevRoom = prevState.rooms[roomId];
            const currRoom = currState.rooms[roomId];
            if (!prevRoom || !currRoom) continue;

            // Special room revealed
            if (currRoom.special_card_id && currRoom.special_revealed && 
                !(prevRoom && prevRoom.special_revealed)) {
                // Check if this wasn't already processed
                const alreadyLogged = prevState.action_log.some(log => 
                    log.event === "SPECIAL_ROOM_REVEALED" && log.room === roomId
                );
                if (!alreadyLogged) {
                    processServerLog({
                        event: "SPECIAL_ROOM_REVEALED",
                        player: "UNKNOWN",
                        room: roomId,
                        special_id: currRoom.special_card_id
                    });
                }
            }

            // Card revealed from deck (search action)
            // Detect if a card was drawn from the deck
            if (currRoom.deck && prevRoom.deck) {
                const prevTop = prevRoom.deck.top;
                const currTop = currRoom.deck.top;
                console.log("[INFER] Checking card draw", { roomId, prevTop, currTop, cards: currRoom.deck.cards });
                if (currTop > prevTop) {
                    // A card was drawn - reveal it
                    // The drawn card was at the OLD top index (prevTop), not currTop - 1
                    const drawnIndex = prevTop;
                    console.log("[INFER] Card drawn detected", { roomId, prevTop, currTop, drawnIndex });
                    if (currRoom.deck.cards && drawnIndex < currRoom.deck.cards.length) {
                        const card = currRoom.deck.cards[drawnIndex];
                        // Try to find which player drew it
                        let drawingPlayer = "UNKNOWN";
                        for (let pid in currState.players) {
                            if (currState.players[pid].room === roomId) {
                                drawingPlayer = pid;
                                break;
                            }
                        }
                        console.log("[INFER] Emitting CARD_REVEALED", { drawingPlayer, roomId, card: currRoom.deck.cards[drawnIndex] });
                        processServerLog({
                            event: "CARD_REVEALED",
                            player: drawingPlayer,
                            room: roomId,
                            card: card
                        });
                    }
                }
            }
        }

        // 3. Detect monster spawns
        for (let monster of currState.monsters || []) {
            const wasPresent = (prevState.monsters || []).some(m => m.id === monster.id || m.monster_id === monster.id);
            if (!wasPresent) {
                processServerLog({
                    event: "MONSTER_SPAWNED",
                    player: "UNKNOWN",
                    monster: monster.monster_id || monster.id,
                    room: monster.room
                });
            }
        }

        // 4. Detect King phase changes
        if (prevState.phase === "KING" && currState.phase === "PLAYER") {
            if (currState.round > prevState.round) {
                processServerLog({
                    event: "KING_ENDROUND",
                    d6: currState.last_king_d6 || "?",
                    floor: currState.king_floor
                });
            }
        }
    }


    /**
     * [LIVE-ACT] Renderiza el "cerebro" del bot PPO: activaciones de la capa
     * oculta (64 Tanh) y logits de acción (27). Se alimenta de
     * state.last_activations que el server inyecta tras cada paso de bot.
     */
    function renderBotBrain(state) {
        const panel = document.getElementById("botBrainPanel");
        if (!panel) return;
        // Cachear nombres de acciones (27) la primera vez que llegan
        if (state && Array.isArray(state.action_names) && state.action_names.length) {
            window.CARCOSA_ACTION_NAMES = state.action_names;
        }
        const act = state && state.last_activations;
        if (!act || !act.policy_hidden || !act.logits) {
            panel.classList.add("hidden");
            return;
        }
        panel.classList.remove("hidden");

        // Actor + métricas
        document.getElementById("botBrainActor").textContent = act.actor || "—";
        document.getElementById("botBrainValue").textContent = (act.value !== undefined) ? act.value.toFixed(2) : "—";
        const actionNames = window.CARCOSA_ACTION_NAMES || [];
        const aName = (act.action_idx !== undefined && actionNames[act.action_idx]) ? actionNames[act.action_idx] : `#${act.action_idx}`;
        document.getElementById("botBrainAction").textContent = aName;

        // Barras de capa oculta (64)
        renderBars(document.getElementById("botBrainHidden"), act.policy_hidden, 1.0);
        // Barras de logits (27)
        renderBars(document.getElementById("botBrainLogits"), act.logits, Math.max(...act.logits.map(Math.abs), 1e-6));
    }

    function renderBars(container, values, scale) {
        if (!container) return;
        container.innerHTML = "";
        for (let i = 0; i < values.length; i++) {
            const v = values[i];
            const bar = document.createElement("div");
            bar.className = "bot-brain-bar";
            const mag = Math.min(1, Math.abs(v) / scale);
            bar.style.height = Math.max(1, Math.round(mag * 52)) + "px";
            if (v > 0.02) bar.classList.add("pos");
            else if (v < -0.02) bar.classList.add("neg");
            else bar.classList.add("zero");
            bar.title = `n${i}: ${v.toFixed(3)}`;
            container.appendChild(bar);
        }
    }

    // Toggle detalle
    const bbToggle = document.getElementById("botBrainToggle");
    if (bbToggle) {
        bbToggle.addEventListener("click", () => {
            const detail = document.getElementById("botBrainDetail");
            const hidden = detail.classList.toggle("hidden");
            bbToggle.textContent = hidden ? "▸ mostrar detalle" : "▾ ocultar detalle";
        });
    }

});
