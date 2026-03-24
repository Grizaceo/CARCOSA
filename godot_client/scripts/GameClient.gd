# scripts/GameClient.gd
# Autoload singleton — gestiona toda comunicación HTTP/WebSocket con el servidor CARCOSA.
# Se accede desde cualquier nodo como: GameClient.start_game(seed)
#
# Arrancar el servidor antes de usar:
#   uvicorn sim.game_server:app --host 0.0.0.0 --port 8765 --reload
extends Node

# Sprint 5: BASE_URL es variable para que el lobby pueda cambiarla (LAN / VPS)
var base_url: String = "http://127.0.0.1:8765"

var game_id: String = ""
var current_state: Dictionary = {}
# IDs de los jugadores en esta máquina (hot-seat).
# Actualizado al llamar start_game().
var local_player_ids: Array = []

# Sprint 5: WebSocket para push de actualizaciones de estado
var _ws: WebSocketPeer = null
var _ws_url: String = ""
var _ws_connected: bool = false
# Evita doble-save cuando el broadcast WS llega justo después de la respuesta HTTP de /act
var _save_pending: bool = false

signal state_updated(state: Dictionary)
signal legal_actions_ready(actor: String, actions: Array)
signal game_saved(result: Dictionary)
signal error_occurred(message: String)


# ── Ciclo de vida ─────────────────────────────────────────────────────────────

func _process(_delta: float) -> void:
	if _ws == null:
		return
	_ws.poll()
	var ws_state := _ws.get_ready_state()
	match ws_state:
		WebSocketPeer.STATE_OPEN:
			if not _ws_connected:
				_ws_connected = true
			while _ws.get_available_packet_count() > 0:
				var packet := _ws.get_packet()
				_on_ws_message(packet.get_string_from_utf8())
		WebSocketPeer.STATE_CLOSED:
			if _ws_connected:
				_ws_connected = false
				# Reconectar automáticamente si la partida sigue activa
				if not game_id.is_empty() and not current_state.get("game_over", false):
					_connect_ws()


# ── API pública ───────────────────────────────────────────────────────────────

func start_game(seed: int, player_ids: Array = []) -> void:
	local_player_ids = player_ids.duplicate() if not player_ids.is_empty() else ["P1", "P2", "P3", "P4"]
	_save_pending = false
	_post("/start", {"seed": seed, "players": local_player_ids}, _on_start_response)


func fetch_state() -> void:
	if game_id.is_empty():
		return
	_get("/state/" + game_id, _on_state_response)


func fetch_legal_actions(actor: String) -> void:
	if game_id.is_empty():
		return
	_get(
		"/legal/" + game_id + "/" + actor,
		func(data: Dictionary) -> void: _on_legal_response(actor, data)
	)


func send_action(actor: String, action_type: String, action_data: Dictionary = {}) -> void:
	if game_id.is_empty():
		return
	_post(
		"/act",
		{
			"game_id": game_id,
			"actor": actor,
			"action_type": action_type,
			"action_data": action_data,
		},
		_on_act_response,
	)


func save_session() -> void:
	if game_id.is_empty() or _save_pending:
		return
	_save_pending = true
	_post("/save/" + game_id, {}, _on_save_response)


# ── Sprint 5: WebSocket ───────────────────────────────────────────────────────

func _connect_ws() -> void:
	"""Abre conexión WebSocket al servidor. Llamado tras recibir el game_id."""
	if game_id.is_empty():
		return
	# Derivar URL WS desde base_url: http(s):// → ws(s)://
	var ws_base := base_url.replace("https://", "wss://").replace("http://", "ws://")
	# Usar el primer jugador local como player_id para la suscripción
	var pid := local_player_ids[0] if not local_player_ids.is_empty() else "P1"
	_ws_url = ws_base + "/ws/" + game_id + "/" + pid
	_ws = WebSocketPeer.new()
	_ws_connected = false
	var err := _ws.connect_to_url(_ws_url)
	if err != OK:
		push_warning("GameClient: no se pudo conectar WebSocket (%d): %s" % [err, _ws_url])
		_ws = null


func _disconnect_ws() -> void:
	if _ws != null:
		_ws.close()
		_ws = null
		_ws_connected = false


func _on_ws_message(text: String) -> void:
	var json := JSON.new()
	if json.parse(text) != OK:
		return
	var msg: Dictionary = json.data
	if msg.get("type") == "state_update":
		var new_state: Dictionary = msg.get("state", {})
		if new_state.is_empty():
			return
		current_state = new_state
		state_updated.emit(current_state)
		# Si la partida no terminó, solicitar legales si es nuestro turno
		if not current_state.get("game_over", false):
			var active: String = current_state.get("active_actor", "")
			if active in local_player_ids:
				fetch_legal_actions(active)


# ── Callbacks de respuesta HTTP ───────────────────────────────────────────────

func _on_start_response(data: Dictionary) -> void:
	game_id = data.get("game_id", "")
	current_state = data.get("state", {})
	state_updated.emit(current_state)
	# Sprint 5: conectar WS tras obtener el game_id
	_connect_ws()


func _on_state_response(data: Dictionary) -> void:
	current_state = data.get("state", {})
	state_updated.emit(current_state)


func _on_legal_response(actor: String, data: Dictionary) -> void:
	var actions: Array = data.get("actions", [])
	legal_actions_ready.emit(actor, actions)


func _on_act_response(data: Dictionary) -> void:
	# Sprint 5: el WS ya hará el push de estado al jugador que actuó y a los demás.
	# Igualmente actualizamos desde la respuesta HTTP para robustez ante WS caído.
	current_state = data.get("state", {})
	state_updated.emit(current_state)


func _on_save_response(data: Dictionary) -> void:
	_save_pending = false
	_disconnect_ws()
	game_saved.emit(data)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

func _post(path: String, body: Dictionary, callback: Callable) -> void:
	var http := HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(
		func(result: int, code: int, _headers: PackedStringArray, response_body: PackedByteArray) -> void:
			http.queue_free()
			_handle_response(result, code, response_body, callback)
	)
	var json_body := JSON.stringify(body)
	var headers := PackedStringArray(["Content-Type: application/json"])
	var err := http.request(base_url + path, headers, HTTPClient.METHOD_POST, json_body)
	if err != OK:
		http.queue_free()
		error_occurred.emit("POST request failed (err %d): %s" % [err, path])


func _get(path: String, callback: Callable) -> void:
	var http := HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(
		func(result: int, code: int, _headers: PackedStringArray, response_body: PackedByteArray) -> void:
			http.queue_free()
			_handle_response(result, code, response_body, callback)
	)
	var err := http.request(base_url + path)
	if err != OK:
		http.queue_free()
		error_occurred.emit("GET request failed (err %d): %s" % [err, path])


func _handle_response(
	result: int,
	code: int,
	body: PackedByteArray,
	callback: Callable,
) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		error_occurred.emit("Error de red (result=%d). ¿Está corriendo el servidor?" % result)
		return
	if code < 200 or code >= 300:
		var detail := body.get_string_from_utf8()
		error_occurred.emit("HTTP %d: %s" % [code, detail])
		return
	var json := JSON.new()
	var parse_err := json.parse(body.get_string_from_utf8())
	if parse_err != OK:
		error_occurred.emit("Error parseando JSON de respuesta")
		return
	callback.call(json.data)
