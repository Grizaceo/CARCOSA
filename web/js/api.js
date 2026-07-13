/**
 * docs/playtest-html/js/api.js
 * 
 * Modulo cliente para comunicarse con CARCOSA Human Play Server (FastAPI).
 */

class CarcosaAPI {
    constructor(baseUrl = "http://127.0.0.1:8765") {
        this.baseUrl = baseUrl.replace(/\/$/, ""); // Quitar slash final si existe
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.clientId = CarcosaAPI.getClientId();
    }

    /**
     * Identificador estable de este navegador (para reclamar asientos).
     */
    static getClientId() {
        let cid = null;
        try {
            cid = localStorage.getItem("carcosa_client_id");
            if (!cid) {
                cid = "c-" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
                localStorage.setItem("carcosa_client_id", cid);
            }
        } catch (e) {
            cid = "c-" + Math.random().toString(36).slice(2, 10);
        }
        return cid;
    }

    /**
     * Helper para realizar peticiones HTTP con un timeout específico.
     */
    async _fetchWithTimeout(resource, options = {}) {
        const { timeout = 8000 } = options;
        
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), timeout);
        
        try {
            const response = await fetch(resource, {
                ...options,
                signal: controller.signal
            });
            clearTimeout(id);
            return response;
        } catch (error) {
            clearTimeout(id);
            if (error.name === 'AbortError') {
                throw new Error("La petición al servidor de Carcosa excedió el tiempo límite (Timeout).");
            }
            throw error;
        }
    }

    /**
     * Inicia una nueva partida con los jugadores dados.
     * @param {number} seed Semilla RNG
     * @param {string[]} humanPlayers IDs de jugadores humanos locales, ej. ["P1", "P2"]
     * @param {object[]} playersConfig Configuración completa: [{pid, roleId, isHuman}]
     * @param {string} drawMode Modo de asignación: RANDOM_UNIQUE | FIXED | RANDOM_WITH_REPLACEMENT
     */
    async startGame(seed = 1, humanPlayers = ["P1"], playersConfig = [], drawMode = "RANDOM_UNIQUE") {
        try {
            const response = await this._fetchWithTimeout(`${this.baseUrl}/start`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ seed, players: humanPlayers, players_config: playersConfig, draw_mode: drawMode, client_id: this.clientId })
            });
            if (!response.ok) {
                let errMsg = "Error al iniciar partida";
                try {
                    const err = await response.json();
                    errMsg = err.detail || errMsg;
                } catch (e) {}
                throw new Error(errMsg);
            }
            return await response.json();
        } catch (error) {
            console.error("API error (startGame):", error);
            throw error;
        }
    }

    /**
     * Obtiene el estado actual de una partida.
     */
    async getState(gameId) {
        try {
            const response = await this._fetchWithTimeout(`${this.baseUrl}/state/${gameId}`);
            if (!response.ok) {
                let errMsg = "No se pudo obtener el estado";
                try {
                    const err = await response.json();
                    errMsg = err.detail || errMsg;
                } catch (e) {}
                throw new Error(errMsg);
            }
            return await response.json();
        } catch (error) {
            console.error("API error (getState):", error);
            throw error;
        }
    }

    /**
     * Obtiene las acciones legales de un actor en una partida.
     */
    async getLegalActions(gameId, actor) {
        try {
            const response = await this._fetchWithTimeout(`${this.baseUrl}/legal/${gameId}/${actor}`);
            if (!response.ok) {
                let errMsg = "No se pudieron obtener las acciones legales";
                try {
                    const err = await response.json();
                    errMsg = err.detail || errMsg;
                } catch (e) {}
                throw new Error(errMsg);
            }
            return await response.json();
        } catch (error) {
            console.error("API error (getLegalActions):", error);
            throw error;
        }
    }

    /**
     * Ejecuta una acción.
     * @param {string} gameId
     * @param {string} actor Actor ejecutando, ej. "P1"
     * @param {string} actionType Tipo de acción, ej. "MOVE"
     * @param {object} actionData Datos de la acción
     */
    async act(gameId, actor, actionType, actionData = {}) {
        try {
            const response = await this._fetchWithTimeout(`${this.baseUrl}/act`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    game_id: gameId,
                    actor,
                    action_type: actionType,
                    action_data: actionData,
                    client_id: this.clientId
                })
            });
            if (!response.ok) {
                let errMsg = "Error al ejecutar la acción";
                try {
                    const err = await response.json();
                    errMsg = err.detail || errMsg;
                } catch (e) {}
                throw new Error(errMsg);
            }
            return await response.json();
        } catch (error) {
            console.error("API error (act):", error);
            throw error;
        }
    }

    /**
     * Reclama asiento(s) humano(s) para este navegador.
     * mode: "add" (default) | "replace" | "release". takeover fuerza quitar el asiento a otro cliente.
     */
    async claimSeats(gameId, seats, mode = "add", takeover = false) {
        const response = await this._fetchWithTimeout(`${this.baseUrl}/claim`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ game_id: gameId, client_id: this.clientId, seats, mode, takeover })
        });
        if (!response.ok) {
            let errMsg = "No se pudo reclamar el asiento";
            try {
                const err = await response.json();
                errMsg = err.detail || errMsg;
            } catch (e) {}
            throw new Error(errMsg);
        }
        return await response.json();
    }

    /**
     * Preview real del setup (habitaciones especiales + roles) para una semilla.
     */
    async getSetupPreview(seed, drawMode = "") {
        const response = await this._fetchWithTimeout(`${this.baseUrl}/setup_preview/${seed}?draw_mode=${encodeURIComponent(drawMode)}`);
        if (!response.ok) throw new Error("No se pudo obtener preview de setup");
        return await response.json();
    }

    /**
     * Lista de partidas guardadas (registro de playtests).
     */
    async listGames(limit = 20) {
        const response = await this._fetchWithTimeout(`${this.baseUrl}/games?limit=${limit}`);
        if (!response.ok) throw new Error("No se pudo listar partidas");
        return await response.json();
    }

    /**
     * Guarda la partida como JSONL para entrenamiento de bots.
     */
    async saveGame(gameId) {
        try {
            const response = await this._fetchWithTimeout(`${this.baseUrl}/save/${gameId}`, {
                method: "POST"
            });
            if (!response.ok) {
                let errMsg = "Error al guardar la partida";
                try {
                    const err = await response.json();
                    errMsg = err.detail || errMsg;
                } catch (e) {}
                throw new Error(errMsg);
            }
            return await response.json();
        } catch (error) {
            console.error("API error (saveGame):", error);
            throw error;
        }
    }

    /**
     * Conecta un WebSocket para recibir actualizaciones en tiempo real.
     * @param {string} gameId
     * @param {string} playerId ID del jugador que conecta
     * @param {function} onMessageCallback Callback para recibir actualizaciones de estado
     */
    connectWS(gameId, playerId, onMessageCallback) {
        this.disconnectWS(); // cierra socket previo Y cancela reconexiones pendientes
        this._wsGameId = gameId;

        // Convertir http:// o https:// a ws:// o wss:// de forma segura
        let wsUrl = this.baseUrl.replace(/^http/, "ws");
        wsUrl = `${wsUrl}/ws/${gameId}/${playerId}`;

        console.log(`Conectando WebSocket a: ${wsUrl}`);
        const socket = new WebSocket(wsUrl);
        this.ws = socket;

        socket.onopen = () => {
            console.log("WebSocket conectado exitosamente.");
            this.reconnectAttempts = 0; // Resetear intentos en conexión exitosa
            if (onMessageCallback) onMessageCallback({ type: "ws_connected" });
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (onMessageCallback) {
                    onMessageCallback(data);
                }
            } catch (e) {
                console.error("Error al procesar mensaje WebSocket:", e);
            }
        };

        socket.onerror = (error) => {
            console.error("WebSocket error:", error);
        };

        socket.onclose = (event) => {
            // Ignorar cierres de sockets viejos (ya reemplazados) o cierres explícitos
            if (socket.explicitlyClosed || this.ws !== socket || this._wsGameId !== gameId) return;
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                const backoffTime = Math.pow(2, this.reconnectAttempts) * 1000;
                console.log(`Reconectando WebSocket en ${backoffTime}ms (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
                this._reconnectTimer = setTimeout(() => {
                    this._reconnectTimer = null;
                    if (this._wsGameId === gameId) {
                        this.connectWS(gameId, playerId, onMessageCallback);
                    }
                }, backoffTime);
            } else {
                console.error("No se pudo reconectar al WebSocket de CARCOSA tras varios intentos.");
                // Avisar a la UI para que active el fallback de polling
                if (onMessageCallback) onMessageCallback({ type: "ws_dead" });
            }
        };
    }

    disconnectWS() {
        if (this._reconnectTimer) {
            clearTimeout(this._reconnectTimer);
            this._reconnectTimer = null;
        }
        this._wsGameId = null;
        if (this.ws) {
            this.ws.explicitlyClosed = true;
            try { this.ws.close(); } catch (e) {}
            this.ws = null;
        }
    }
}
