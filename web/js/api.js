/**
 * docs/playtest-html/js/api.js
 * 
 * Modulo cliente para comunicarse con CARCOSA Human Play Server (FastAPI).
 */

class CarcosaAPI {
    constructor(baseUrl = "http://127.0.0.1:8765") {
        this.baseUrl = baseUrl.replace(/\/$/, ""); // Quitar slash final si existe
        this.ws = null;
    }

    /**
     * Inicia una nueva partida con los jugadores dados.
     * @param {number} seed Semilla RNG
     * @param {string[]} players IDs de jugadores, ej. ["P1", "P2"]
     */
    async startGame(seed = 1, players = ["P1", "P2", "P3", "P4"]) {
        try {
            const response = await fetch(`${this.baseUrl}/start`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ seed, players })
            });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "Error al iniciar partida");
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
            const response = await fetch(`${this.baseUrl}/state/${gameId}`);
            if (!response.ok) throw new Error("No se pudo obtener el estado");
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
            const response = await fetch(`${this.baseUrl}/legal/${gameId}/${actor}`);
            if (!response.ok) throw new Error("No se pudieron obtener las acciones legales");
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
            const response = await fetch(`${this.baseUrl}/act`, {
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
                const err = await response.json();
                throw new Error(err.detail || "Error al ejecutar la acción");
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
            const response = await fetch(`${this.baseUrl}/save/${gameId}`, {
                method: "POST"
            });
            if (!response.ok) throw new Error("Error al guardar la partida");
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
            this.ws.close();
        }

        // Convertir http:// o https:// a ws:// o wss://
        let wsUrl = this.baseUrl.replace(/^http/, "ws");
        wsUrl = `${wsUrl}/ws/${gameId}/${playerId}`;

        console.log(`Conectando WebSocket a: ${wsUrl}`);
        this.ws = new WebSocket(wsUrl);

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (onMessageCallback) {
                    onMessageCallback(data);
                }
            } catch (e) {
                console.error("Error al procesar mensaje WebSocket:", e);
            }
        };

        this.ws.onerror = (error) => {
            console.error("WebSocket error:", error);
        };

        this.ws.onclose = () => {
            console.log("WebSocket cerrado");
        };
    }

    disconnectWS() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}
