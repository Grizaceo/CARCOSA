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
                body: JSON.stringify({ seed, players: humanPlayers, players_config: playersConfig, draw_mode: drawMode })
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
                    action_data: actionData
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
        if (this.ws) {
            this.ws.explicitlyClosed = true;
            this.ws.close();
        }

        // Convertir http:// o https:// a ws:// o wss:// de forma segura
        let wsUrl = this.baseUrl.replace(/^http/, "ws");
        wsUrl = `${wsUrl}/ws/${gameId}/${playerId}`;

        console.log(`Conectando WebSocket a: ${wsUrl}`);
        const socket = new WebSocket(wsUrl);
        this.ws = socket;

        socket.onopen = () => {
            console.log("WebSocket conectado exitosamente.");
            this.reconnectAttempts = 0; // Resetear intentos en conexión exitosa
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
            console.log("WebSocket cerrado", event);
            if (!socket.explicitlyClosed) {
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    const backoffTime = Math.pow(2, this.reconnectAttempts) * 1000;
                    console.log(`Intentando reconectar WebSocket en ${backoffTime}ms (Intento ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
                    setTimeout(() => {
                        this.connectWS(gameId, playerId, onMessageCallback);
                    }, backoffTime);
                } else {
                    console.error("No se pudo reconectar al WebSocket de CARCOSA tras varios intentos.");
                }
            }
        };
    }

    disconnectWS() {
        if (this.ws) {
            this.ws.explicitlyClosed = true;
            this.ws.close();
            this.ws = null;
        }
    }
}
