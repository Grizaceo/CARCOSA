/**
 * docs/playtest-html/js/renderer.js
 * 
 * Renderizador de Canvas 2D para el tablero de CARCOSA.
 */

class CarcosaRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext("2d");
        
        // Colores de jugadores
        this.playerColors = {
            "P1": "#FF4A6B", // Rojo neón
            "P2": "#4B96FF", // Azul neón
            "P3": "#3CE39A", // Verde neón
            "P4": "#F6C844"  // Amarillo neón
        };

        this.specialRoomColors = {
            "TABERNA": "#10B981",          // Verde esmeralda
            "MOTEMEY": "#3B82F6",          // Azul
            "ARMERIA": "#F59E0B",          // Ámbar
            "PUERTAS_AMARILLO": "#8B5CF6", // Violeta
            "CAMARA_LETAL": "#EF4444",     // Rojo fuerte
            "SALON_BELLEZA": "#EC4899",    // Rosa
            "MONASTERIO_LOCURA": "#6B7280" // Gris
        };

        // Layout de habitaciones por piso
        // Centrado en X = 400. Cada piso ocupa 240px de alto.
        this.layout = {};
        this.setupLayout();

        // Sistema de Partículas Atmosféricas (Niebla de Carcosa)
        this.particles = [];
        this.initParticles();
    }

    initParticles() {
        this.particles = [];
        const numParticles = 45;
        for (let i = 0; i < numParticles; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                radius: Math.random() * 2 + 0.8,
                speedX: Math.random() * 0.4 - 0.2,
                speedY: -(Math.random() * 0.4 + 0.15), // Ascender lentamente
                alpha: Math.random() * 0.35 + 0.08,
                oscSpeed: Math.random() * 0.015 + 0.005,
                oscRange: Math.random() * 6 + 2,
                angle: Math.random() * Math.PI * 2
            });
        }
    }

    updateAndDrawParticles() {
        this.ctx.save();
        this.particles.forEach(p => {
            // Actualizar posiciones
            p.y += p.speedY;
            p.angle += p.oscSpeed;
            const currentX = p.x + Math.sin(p.angle) * p.oscRange;

            // Rebotar en bordes
            if (p.y < -10) {
                p.y = this.canvas.height + 10;
                p.x = Math.random() * this.canvas.width;
            }
            if (p.x < -10 || p.x > this.canvas.width + 10) {
                p.x = Math.random() * this.canvas.width;
            }

            // Dibujar mota de polvo de Carcosa
            this.ctx.fillStyle = `rgba(246, 200, 68, ${p.alpha})`; // Brillo amarillo-ámbar
            this.ctx.shadowBlur = 4;
            this.ctx.shadowColor = "rgba(246, 200, 68, 0.3)";
            this.ctx.beginPath();
            this.ctx.arc(currentX, p.y, p.radius, 0, Math.PI * 2);
            this.ctx.fill();
        });
        this.ctx.restore();
    }


    setupLayout() {
        const floorHeight = 245;
        const width = 800;

        for (let floor = 1; floor <= 3; floor++) {
            // Piso 3 arriba, Piso 1 abajo
            const floorY = (3 - floor) * floorHeight + 30;
            
            this.layout[`F${floor}_P`] = {
                x: 200,
                y: floorY + 95,
                w: 400,
                h: 40,
                type: "corridor",
                label: `PASILLO PISO ${floor}`
            };

            // R1: Top-Left
            this.layout[`F${floor}_R1`] = {
                x: 180,
                y: floorY + 25,
                w: 160,
                h: 50,
                type: "room",
                num: 1
            };

            // R2: Top-Right
            this.layout[`F${floor}_R2`] = {
                x: 460,
                y: floorY + 25,
                w: 160,
                h: 50,
                type: "room",
                num: 2
            };

            // R3: Bottom-Left
            this.layout[`F${floor}_R3`] = {
                x: 180,
                y: floorY + 155,
                w: 160,
                h: 50,
                type: "room",
                num: 3
            };

            // R4: Bottom-Right
            this.layout[`F${floor}_R4`] = {
                x: 460,
                y: floorY + 155,
                w: 160,
                h: 50,
                type: "room",
                num: 4
            };
        }
    }

    /**
     * Dibuja el tablero completo basado en el estado del juego.
     */
    draw(state, legalActions = [], hoveredRoomId = null) {
        if (!state) return;
        
        // Limpiar lienzo
        this.ctx.fillStyle = "#06040A";
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Dibujar niebla de Carcosa (Partículas flotantes de neón)
        this.updateAndDrawParticles();

        // 1. Dibujar conexiones verticales de escaleras
        this.drawStairsConnections(state);


        // 2. Dibujar pisos y habitaciones
        for (let roomKey in this.layout) {
            this.drawRoom(roomKey, state, legalActions, hoveredRoomId);
        }

        // 3. Dibujar monstruos
        this.drawMonsters(state);

        // 4. Dibujar jugadores
        this.drawPlayers(state);

        // 5. Dibujar presencia del Rey de Amarillo
        this.drawKingPresence(state);

        // 6. Dibujar indicador ICE_SERVANT / Reina Helada persistente
        this.drawIceServantPresence(state);
    }

    /**
     * Dibuja las conexiones verticales entre las escaleras activas de cada piso.
     */
    drawStairsConnections(state) {
        if (!state.stairs) return;

        this.ctx.save();
        this.ctx.strokeStyle = "rgba(246, 200, 68, 0.35)";
        this.ctx.lineWidth = 3;
        this.ctx.setLineDash([6, 8]);
        this.ctx.lineDashOffset = -Date.now() / 40; // Efecto de flujo de energía vertical en tiempo real

        let stairPoints = [];
        for (let floor = 1; floor <= 3; floor++) {
            const roomId = state.stairs[floor];
            const roomLayout = this.layout[roomId];
            if (roomLayout) {
                // Centro de la habitación
                stairPoints.push({
                    x: roomLayout.x + roomLayout.w / 2,
                    y: roomLayout.y + roomLayout.h / 2
                });
            }
        }

        // Dibujar línea de F1 a F2 a F3
        if (stairPoints.length >= 2) {
            this.ctx.beginPath();
            this.ctx.moveTo(stairPoints[0].x, stairPoints[0].y);
            for (let i = 1; i < stairPoints.length; i++) {
                this.ctx.lineTo(stairPoints[i].x, stairPoints[i].y);
            }
            this.ctx.stroke();
        }
        this.ctx.restore();
    }

    /**
     * Dibuja una habitación individual, sus conexiones a pasillo y relaciones R1-R2 / R3-R4.
     */
    drawRoom(roomId, state, legalActions = [], hoveredRoomId = null) {
        const item = this.layout[roomId];
        const roomState = state.rooms ? state.rooms[roomId] : null;
        const isStairs = state.stairs && Object.values(state.stairs).includes(roomId);
        
        // Verificar si es un destino de movimiento legal y si está bajo el ratón
        const isMoveTarget = legalActions.some(act => act.type === "MOVE" && act.data && act.data.to === roomId);
        const isHovered = (hoveredRoomId === roomId);

        this.ctx.save();

        // Determinar color de fondo con respuesta táctil translúcida
        let bgColor = "rgba(23, 20, 42, 0.4)";
        if (isHovered && isMoveTarget) {
            bgColor = "rgba(60, 227, 154, 0.2)"; // Iluminar verde al sobrevolar caminos válidos
        } else if (isHovered) {
            bgColor = "rgba(138, 75, 243, 0.08)"; // Iluminar violeta al sobrevolar cuartos normales
        }

        let borderGlow = isMoveTarget ? "rgba(60, 227, 154, 0.4)" : "rgba(138, 75, 243, 0.15)";
        let strokeColor = isMoveTarget ? "#3CE39A" : "rgba(138, 75, 243, 0.25)";
        
        if (isMoveTarget) {
            // Efecto de respiración neón verde mediante pulsación armónica senoidal
            const alphaPulse = 0.6 + Math.sin(Date.now() / 150) * 0.25;
            const blurPulse = 6 + Math.sin(Date.now() / 150) * 3;
            borderGlow = `rgba(60, 227, 154, ${alphaPulse * 0.6})`;
            strokeColor = `rgba(60, 227, 154, ${alphaPulse})`;
            this.ctx.shadowBlur = blurPulse;
        }
        
        let roomNameLabel = roomId;

        if (item.type === "corridor") {
            bgColor = "rgba(30, 20, 50, 0.6)";
            strokeColor = "rgba(138, 75, 243, 0.4)";
            roomNameLabel = item.label;
            
            // Si el Rey está en este piso, pintar el pasillo con un borde sutil amarillo
            const floor = parseInt(roomId.split("_")[0][1]);
            if (state.king_floor === floor) {
                borderGlow = "rgba(246, 200, 68, 0.2)";
                strokeColor = "rgba(246, 200, 68, 0.6)";
            }
        } else if (roomState) {
            roomNameLabel = `R${item.num}`;
            // Si es habitación especial y está revelada
            if (roomState.special_card_id && roomState.special_revealed) {
                const sType = roomState.special_card_id;
                bgColor = this.specialRoomColors[sType] ? `${this.specialRoomColors[sType]}22` : "rgba(138, 75, 243, 0.1)";
                strokeColor = this.specialRoomColors[sType] || "rgba(138, 75, 243, 0.5)";
                
                let sIcon = "🏨";
                if (sType === "TABERNA") sIcon = "🍻";
                else if (sType === "MOTEMEY") sIcon = "⚖️";
                else if (sType === "ARMERIA") sIcon = "⚔️";
                else if (sType === "PUERTAS_AMARILLO") sIcon = "🚪";
                else if (sType === "CAMARA_LETAL") sIcon = "💀";
                else if (sType === "SALON_BELLEZA") sIcon = "🪞";
                else if (sType === "MONASTERIO_LOCURA") sIcon = "⛪";

                roomNameLabel = `${sIcon} ${sType.replace("_", " ")}`;
                
                if (roomState.special_destroyed) {
                    bgColor = "rgba(255, 74, 107, 0.1)";
                    strokeColor = "rgba(255, 74, 107, 0.4)";
                    roomNameLabel = `💥 ${sType.replace("_", " ")} [DESTRUIDA]`;
                }
            } else if (roomState.special_card_id && !roomState.special_revealed) {

                // Habitación especial boca abajo
                bgColor = "rgba(50, 40, 20, 0.4)";
                strokeColor = "rgba(246, 200, 68, 0.4)";
                roomNameLabel = "ESPECIAL (OCULTA)";
            }
        }

        // Dibujar sombras de glow
        this.ctx.shadowBlur = 8;
        this.ctx.shadowColor = strokeColor;

        // Dibujar caja contenedora
        this.ctx.fillStyle = bgColor;
        this.ctx.strokeStyle = strokeColor;
        this.ctx.lineWidth = 2;
        
        // Trazar bordes redondeados con compatibilidad para navegadores antiguos
        const radius = 6;
        if (this.ctx.roundRect) {
            this.ctx.beginPath();
            this.ctx.roundRect(item.x, item.y, item.w, item.h, radius);
        } else {
            const x = item.x;
            const y = item.y;
            const w = item.w;
            const h = item.h;
            const r = radius;
            this.ctx.beginPath();
            this.ctx.moveTo(x + r, y);
            this.ctx.lineTo(x + w - r, y);
            this.ctx.quadraticCurveTo(x + w, y, x + w, y + r);
            this.ctx.lineTo(x + w, y + h - r);
            this.ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
            this.ctx.lineTo(x + r, y + h);
            this.ctx.quadraticCurveTo(x, y + h, x, y + h - r);
            this.ctx.lineTo(x, y + r);
            this.ctx.quadraticCurveTo(x, y, x + r, y);
            this.ctx.closePath();
        }
        this.ctx.fill();
        this.ctx.stroke();

        this.ctx.shadowBlur = 0; // Reset shadow

        // Dibujar conexiones directas canónicas entre R1<->R2 y R3<->R4
        if (item.type === "room") {
            const floor = roomId.split("_")[0];
            this.ctx.strokeStyle = "rgba(138, 75, 243, 0.15)";
            this.ctx.lineWidth = 1;
            
            // Conexión a pasillo
            const corridor = this.layout[`${floor}_P`];
            this.ctx.beginPath();
            this.ctx.moveTo(item.x + item.w / 2, item.y + item.h / 2);
            this.ctx.lineTo(corridor.x + corridor.w / 2, corridor.y + corridor.h / 2);
            this.ctx.stroke();

            // Dibujar puerta a habitación adyacente
            if (item.num === 1) {
                const r2 = this.layout[`${floor}_R2`];
                this.ctx.strokeStyle = "rgba(138, 75, 243, 0.35)";
                this.ctx.lineWidth = 2;
                this.ctx.setLineDash([2, 4]);
                this.ctx.beginPath();
                this.ctx.moveTo(item.x + item.w, item.y + item.h / 2);
                this.ctx.lineTo(r2.x, r2.y + r2.h / 2);
                this.ctx.stroke();
                this.ctx.setLineDash([]);
            } else if (item.num === 3) {
                const r4 = this.layout[`${floor}_R4`];
                this.ctx.strokeStyle = "rgba(138, 75, 243, 0.35)";
                this.ctx.lineWidth = 2;
                this.ctx.setLineDash([2, 4]);
                this.ctx.beginPath();
                this.ctx.moveTo(item.x + item.w, item.y + item.h / 2);
                this.ctx.lineTo(r4.x, r4.y + r4.h / 2);
                this.ctx.stroke();
                this.ctx.setLineDash([]);
            }
        }

        // Dibujar etiqueta de la habitación
        this.ctx.fillStyle = (roomState && roomState.special_card_id && !roomState.special_revealed) ? "#F6C844" : "#F3F1FA";
        this.ctx.font = item.type === "corridor" ? "bold 10px 'Space Grotesk'" : "bold 11px 'Outfit'";
        this.ctx.textAlign = "center";
        this.ctx.textBaseline = "middle";
        
        let labelY = item.y + (item.type === "corridor" ? item.h / 2 : 16);
        this.ctx.fillText(roomNameLabel, item.x + item.w / 2, labelY);

        // Si es habitación normal, mostrar cartas restantes en el mazo
        if (item.type === "room" && roomState && roomState.deck) {
            const cardsRemaining = roomState.deck.cards.length - roomState.deck.top;
            this.ctx.fillStyle = "rgba(158, 154, 168, 0.7)";
            this.ctx.font = "9px 'Space Grotesk'";
            this.ctx.fillText(`${cardsRemaining} cartas`, item.x + item.w / 2, item.y + 36);
        }

        // Dibujar icono de escaleras fijas
        if (isStairs) {
            this.ctx.fillStyle = "#F6C844";
            this.ctx.font = "bold 9px 'Space Grotesk'";
            this.ctx.textAlign = "right";
            this.ctx.fillText(" Escaleras", item.x + item.w - 8, item.y + 12);
            
            // Pequeño símbolo de escalera
            this.ctx.strokeStyle = "#F6C844";
            this.ctx.lineWidth = 1;
            this.ctx.beginPath();
            this.ctx.moveTo(item.x + item.w - 70, item.y + 8);
            this.ctx.lineTo(item.x + item.w - 70, item.y + 16);
            this.ctx.moveTo(item.x + item.w - 64, item.y + 8);
            this.ctx.lineTo(item.x + item.w - 64, item.y + 16);
            // Peldaños
            this.ctx.moveTo(item.x + item.w - 70, item.y + 10);
            this.ctx.lineTo(item.x + item.w - 64, item.y + 10);
            this.ctx.moveTo(item.x + item.w - 70, item.y + 13);
            this.ctx.lineTo(item.x + item.w - 64, item.y + 13);
            this.ctx.stroke();
        }

        // Armería almacenamiento (si aplica)
        if (roomState && roomState.special_card_id === "ARMERIA" && roomState.special_revealed) {
            const armoryItems = state.armory_storage && state.armory_storage[roomId] ? state.armory_storage[roomId] : [];
            if (armoryItems.length > 0) {
                this.ctx.fillStyle = "#F59E0B";
                this.ctx.font = "8px 'Space Grotesk'";
                this.ctx.textAlign = "left";
                this.ctx.fillText(`Eq: ${armoryItems.join(", ")}`, item.x + 8, item.y + 12);
            }
        }

        this.ctx.restore();
    }

    /**
     * Dibuja a los jugadores en sus respectivas habitaciones.
     */
    drawPlayers(state) {
        if (!state.players) return;

        // Agrupar jugadores por habitación para evitar solapamiento
        const playersByRoom = {};
        for (let pid in state.players) {
            const player = state.players[pid];
            if (!playersByRoom[player.room]) {
                playersByRoom[player.room] = [];
            }
            playersByRoom[player.room].push({ id: pid, ...player });
        }

        for (let roomKey in playersByRoom) {
            const players = playersByRoom[roomKey];
            const roomLayout = this.layout[roomKey];
            if (!roomLayout) continue;

            // Distribuir jugadores en la habitación
            const count = players.length;
            const startX = roomLayout.x + 25;
            const stepX = (roomLayout.w - 50) / Math.max(1, count - 1);

            players.forEach((player, index) => {
                // Calcular X, Y para cada jugador
                let px = count === 1 ? roomLayout.x + roomLayout.w / 2 : startX + index * stepX;
                // Si es pasillo, ponerlos distribuidos en la mitad del pasillo
                let py = roomLayout.y + roomLayout.h - (roomLayout.type === "corridor" ? 14 : 12);

                this.ctx.save();
                
                // Círculo de jugador
                this.ctx.fillStyle = this.playerColors[player.id] || "#FFFFFF";
                this.ctx.shadowBlur = 10;
                this.ctx.shadowColor = this.ctx.fillStyle;

                this.ctx.beginPath();
                this.ctx.arc(px, py, 9, 0, Math.PI * 2);
                this.ctx.fill();

                // Borde de turno activo animado (Respiración / Pulsación Neón)
                const activeActor = state.active_actor;
                if (activeActor === player.id) {
                    const pulse = 12 + Math.sin(Date.now() / 150) * 1.8;
                    this.ctx.strokeStyle = "#FFFFFF";
                    this.ctx.lineWidth = 2.5;
                    this.ctx.shadowBlur = 12;
                    this.ctx.shadowColor = "#FFFFFF";
                    this.ctx.beginPath();
                    this.ctx.arc(px, py, pulse, 0, Math.PI * 2);
                    this.ctx.stroke();
                }

                // Letra ID del jugador
                this.ctx.shadowBlur = 0;
                this.ctx.fillStyle = "#0B0914";
                this.ctx.font = "bold 9px 'Space Grotesk'";
                this.ctx.textAlign = "center";
                this.ctx.textBaseline = "middle";
                this.ctx.fillText(player.id, px, py);

                // Si tiene llaves, dibujar indicador arriba
                let keyY = py - 18;
                if (player.keys > 0) {
                    this.ctx.fillStyle = "#F6C844";
                    this.ctx.font = "bold 8px sans-serif";
                    this.ctx.fillText("🔑".repeat(player.keys), px, keyY);
                    keyY -= 14;
                }
                
                // Movement blocked indicator (Reina Helada efecto inmediato)
                const isMovementBlocked = state.movement_blocked_players && state.movement_blocked_players.includes(player.id);
                if (isMovementBlocked) {
                    this.ctx.fillStyle = "#06B6D4";
                    this.ctx.font = "12px sans-serif";
                    this.ctx.fillText("🧊", px, keyY);
                    keyY -= 16;
                }

                // Efectos de aura para estados alterados activos
                if (player.statuses && player.statuses.length > 0) {
                    player.statuses.forEach((status, sIdx) => {
                        this.ctx.save();
                        this.ctx.shadowBlur = 8;
                        this.ctx.lineWidth = 1.5;

                        // Desfase orbital para rotar suavemente
                        const angleOffset = (Date.now() / 600) + (sIdx * Math.PI / 2);
                        const radiusOffset = 13 + (sIdx * 3);

                        if (status === "ENVENENADO") {
                            this.ctx.strokeStyle = "#3CE39A";
                            this.ctx.shadowColor = "#3CE39A";
                            this.ctx.setLineDash([2, 4]);
                            this.ctx.beginPath();
                            this.ctx.arc(px, py, radiusOffset, angleOffset, angleOffset + Math.PI * 1.5);
                            this.ctx.stroke();
                        } else if (status === "MALDITO") {
                            this.ctx.strokeStyle = "#C084FC";
                            this.ctx.shadowColor = "#C084FC";
                            this.ctx.beginPath();
                            const ox = px + Math.cos(angleOffset) * radiusOffset;
                            const oy = py + Math.sin(angleOffset) * radiusOffset;
                            this.ctx.fillStyle = "#C084FC";
                            this.ctx.arc(ox, oy, 2, 0, Math.PI * 2);
                            this.ctx.fill();
                        } else if (status === "PARANOIA") {
                            this.ctx.strokeStyle = "#FF4A6B";
                            this.ctx.shadowColor = "#FF4A6B";
                            this.ctx.setLineDash([4, 4]);
                            this.ctx.beginPath();
                            this.ctx.arc(px, py, radiusOffset, -angleOffset, -angleOffset + Math.PI);
                            this.ctx.stroke();
                        } else if (status === "STUN") {
                            this.ctx.strokeStyle = "#F6C844";
                            this.ctx.shadowColor = "#F6C844";
                            const ox = px + Math.cos(angleOffset) * (radiusOffset - 2);
                            const oy = py + Math.sin(angleOffset) * (radiusOffset - 2);
                            this.ctx.font = "bold 6px sans-serif";
                            this.ctx.fillStyle = "#F6C844";
                            this.ctx.fillText("⚡", ox, oy);
                        } else if (status === "SANIDAD") {
                            this.ctx.strokeStyle = "#06B6D4";
                            this.ctx.shadowColor = "#06B6D4";
                            this.ctx.beginPath();
                            this.ctx.arc(px, py, radiusOffset, 0, Math.PI * 2);
                            this.ctx.stroke();
                        }
                        this.ctx.restore();
                    });
                }

                this.ctx.restore();
            });
        }

    }

    /**
     * Dibuja los monstruos en sus habitaciones.
     */
    drawMonsters(state) {
        if (!state.monsters || state.monsters.length === 0) return;

        // Agrupar monstruos por habitación
        const monstersByRoom = {};
        state.monsters.forEach(m => {
            if (!monstersByRoom[m.room]) {
                monstersByRoom[m.room] = [];
            }
            monstersByRoom[m.room].push(m);
        });

        for (let roomKey in monstersByRoom) {
            const list = monstersByRoom[roomKey];
            const roomLayout = this.layout[roomKey];
            if (!roomLayout) continue;

            list.forEach((m, idx) => {
                // Posicionar monstruos al lado derecho inferior/superior
                let mx = roomLayout.x + roomLayout.w - 15 - (idx * 16);
                let my = roomLayout.y + roomLayout.h - 12;

                const mId = m.id || m.monster_id || "";

                this.ctx.save();
                this.ctx.fillStyle = this.playerColors[mId] || "#D037A5";
                
                // Dibujar triángulo/rombo para monstruos
                this.ctx.beginPath();
                this.ctx.moveTo(mx, my - 6);
                this.ctx.lineTo(mx + 6, my + 4);
                this.ctx.lineTo(mx - 6, my + 4);
                this.ctx.closePath();
                this.ctx.fill();

                // Llavero/indicador de ID corta
                this.ctx.fillStyle = "#FFFFFF";
                this.ctx.font = "7px sans-serif";
                this.ctx.textAlign = "center";
                this.ctx.textBaseline = "middle";
                
                // Letra del monstruo
                let letter = "M";
                if (mId.includes("ARAÑA") || mId.includes("SPIDER")) letter = "A";
                else if (mId.includes("REINA")) letter = "R";
                else if (mId.includes("DUENDE")) letter = "D";
                else if (mId.includes("VIEJO")) letter = "V";
                else if (mId.includes("ICE_SERVANT")) letter = "I";
                
                this.ctx.fillText(letter, mx, my + 1);
                
                // ICE_SERVANT: indicador especial ❄️
                if (mId.includes("ICE_SERVANT")) {
                    this.ctx.fillStyle = "#06B6D4";
                    this.ctx.font = "10px sans-serif";
                    this.ctx.fillText("❄️", mx, my - 18);
                }

                // Si está stuneado
                if (m.stunned_remaining_rounds && m.stunned_remaining_rounds > 0) {
                    this.ctx.fillStyle = "#FF4A6B";
                    this.ctx.font = "bold 6px 'Space Grotesk'";
                    this.ctx.fillText("⚡", mx, my - 12);
                }

                this.ctx.restore();
            });
        }
    }

    /**
     * Dibuja al Rey de Amarillo (corona/estrella) en su piso activo.
     */
    drawKingPresence(state) {
        if (state.king_floor === undefined) return;
        
        // El Rey está en el pasillo del piso king_floor
        const corridorId = `F${state.king_floor}_P`;
        const corridor = this.layout[corridorId];
        
        if (corridor) {
            this.ctx.save();
            
            // X, Y en el extremo izquierdo del pasillo
            let kx = corridor.x + 30;
            let ky = corridor.y + corridor.h / 2;

            // Corona del rey (dibujada en amarillo neón con sombra de glow)
            this.ctx.fillStyle = "#F6C844";
            this.ctx.shadowBlur = 15;
            this.ctx.shadowColor = "#F6C844";

            this.ctx.beginPath();
            this.ctx.arc(kx, ky, 9, 0, Math.PI * 2);
            this.ctx.fill();

            // Símbolo de Corona / K en negro
            this.ctx.shadowBlur = 0;
            this.ctx.fillStyle = "#0B0914";
            this.ctx.font = "bold 9px 'Outfit'";
            this.ctx.textAlign = "center";
            this.ctx.textBaseline = "middle";
            this.ctx.fillText("👑", kx, ky);

            // Texto "EL REY DE AMARILLO"
            this.ctx.fillStyle = "#F6C844";
            this.ctx.font = "bold 8px 'Space Grotesk'";
            this.ctx.textAlign = "left";
            this.ctx.fillText("PRESENCIA", kx + 14, ky + 1);

            this.ctx.restore();
        }
    }

    /**
     * Dibuja indicador de ICE_SERVANT / Reina Helada persistente en el pasillo del piso afectado.
     */
    drawIceServantPresence(state) {
        // Buscar piso con ICE_SERVANT
        let iceFloor = null;
        if (state.monsters) {
            for (const m of state.monsters) {
                if (m.monster_id && m.monster_id.includes("ICE_SERVANT")) {
                    iceFloor = m.room.startsWith("F1_") ? 1 : m.room.startsWith("F2_") ? 2 : 3;
                    break;
                }
            }
        }
        // También Reina Helada persistente: jugadores en piso del rey tienen 1 acción
        // (se indica visualmente igual que ICE_SERVANT)
        let reinaFloor = null;
        if (state.king_floor && state.monsters) {
            for (const m of state.monsters) {
                if (m.monster_id && m.monster_id.includes("REINA_HELADA")) {
                    reinaFloor = state.king_floor; // La reina está en el piso del rey
                    break;
                }
            }
        }
        
        const floorsToMark = new Set();
        if (iceFloor) floorsToMark.add(iceFloor);
        if (reinaFloor) floorsToMark.add(reinaFloor);
        
        floorsToMark.forEach(floor => {
            const corridorId = `F${floor}_P`;
            const corridor = this.layout[corridorId];
            if (!corridor) return;
            
            this.ctx.save();
            // X, Y en el extremo derecho del pasillo (opuesto al Rey)
            let ix = corridor.x + corridor.w - 30;
            let iy = corridor.y + corridor.h / 2;
            
            // Icono de hielo
            this.ctx.fillStyle = "#06B6D4";
            this.ctx.shadowBlur = 15;
            this.ctx.shadowColor = "#06B6D4";
            
            this.ctx.beginPath();
            this.ctx.arc(ix, iy, 9, 0, Math.PI * 2);
            this.ctx.fill();
            
            this.ctx.shadowBlur = 0;
            this.ctx.fillStyle = "#0B0914";
            this.ctx.font = "bold 9px 'Outfit'";
            this.ctx.textAlign = "center";
            this.ctx.textBaseline = "middle";
            this.ctx.fillText("❄️", ix, iy);
            
            this.ctx.fillStyle = "#06B6D4";
            this.ctx.font = "bold 8px 'Space Grotesk'";
            this.ctx.textAlign = "right";
            this.ctx.fillText("1 ACCIÓN", ix - 14, iy + 1);
            
            this.ctx.restore();
        });
    }
}
