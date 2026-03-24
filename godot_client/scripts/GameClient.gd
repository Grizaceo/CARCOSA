# scripts/GameClient.gd
# Autoload singleton — gestiona toda comunicación HTTP con el servidor CARCOSA.
# Se accede desde cualquier nodo como: GameClient.start_game(seed)
#
# Arrancar el servidor antes de usar:
#   uvicorn sim.game_server:app --host 127.0.0.1 --port 8765 --reload
extends Node

const BASE_URL: String = "http://127.0.0.1:8765"

var game_id: String = ""
var current_state: Dictionary = {}

signal state_updated(state: Dictionary)
signal legal_actions_ready(actor: String, actions: Array)
signal game_saved(result: Dictionary)
signal error_occurred(message: String)


# ── API pública ───────────────────────────────────────────────────────────────

func start_game(seed: int) -> void:
	_post("/start", {"seed": seed}, _on_start_response)


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
	if game_id.is_empty():
		return
	_post("/save/" + game_id, {}, _on_save_response)


# ── Callbacks de respuesta ────────────────────────────────────────────────────

func _on_start_response(data: Dictionary) -> void:
	game_id = data.get("game_id", "")
	current_state = data.get("state", {})
	state_updated.emit(current_state)


func _on_state_response(data: Dictionary) -> void:
	current_state = data.get("state", {})
	state_updated.emit(current_state)


func _on_legal_response(actor: String, data: Dictionary) -> void:
	var actions: Array = data.get("actions", [])
	legal_actions_ready.emit(actor, actions)


func _on_act_response(data: Dictionary) -> void:
	current_state = data.get("state", {})
	state_updated.emit(current_state)


func _on_save_response(data: Dictionary) -> void:
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
	var err := http.request(BASE_URL + path, headers, HTTPClient.METHOD_POST, json_body)
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
	var err := http.request(BASE_URL + path)
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
