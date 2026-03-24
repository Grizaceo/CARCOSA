# scripts/Main.gd
# Controlador principal: maneja lobby → juego → resultado.
# Sprint 3: hot-seat multi-jugador con AcceptDialog + configuración de nombres.
# Sprint 5: campo de URL de servidor configurable (LAN / VPS).
extends Control

# ── Referencias de escena ─────────────────────────────────────────────────────
@onready var lobby_panel: Control = $LobbyPanel
@onready var game_panel: Control = $GamePanel
@onready var seed_input: SpinBox = $LobbyPanel/MarginContainer/VBox/SeedRow/SeedInput
@onready var player_count_input: SpinBox = $LobbyPanel/MarginContainer/VBox/PlayerCountRow/PlayerCountInput
@onready var player_names_container: VBoxContainer = $LobbyPanel/MarginContainer/VBox/PlayerNamesContainer
@onready var start_button: Button = $LobbyPanel/MarginContainer/VBox/StartButton
# Sprint 5: campo de URL del servidor (LAN / VPS)
@onready var server_url_input: LineEdit = $LobbyPanel/MarginContainer/VBox/ServerRow/ServerInput
@onready var status_label: Label = $GamePanel/StatusLabel
@onready var board_view = $GamePanel/HSplit/BoardView
@onready var action_panel = $GamePanel/HSplit/ActionPanel
@onready var save_button: Button = $GamePanel/SaveButton
@onready var result_panel: Control = $ResultPanel
@onready var result_label: Label = $ResultPanel/VBox/ResultLabel
@onready var new_game_button: Button = $ResultPanel/VBox/NewGameButton
@onready var error_label: Label = $ErrorLabel
@onready var event_log_text: RichTextLabel = $GamePanel/EventLogPanel/Margin/VBox/EventLogScroll/EventLogText
@onready var random_seed_btn: Button = $LobbyPanel/MarginContainer/VBox/SeedRow/RandomSeedBtn

var _active_actor: String = ""
var _game_over: bool = false
var _last_outcome: String = ""
# Datos del jugador pendiente de confirmación en hot-seat
var _pending_actor: String = ""
var _pending_actions: Array = []
# AcceptDialog creado en tiempo de ejecución para no modificar la escena
var _hotseat_dialog: AcceptDialog = null
# Mapeo de PID canónico (P1, P2...) → nombre de display del lobby
var _player_display_names: Dictionary = {}
# Historial de eventos
var _prev_state: Dictionary = {}
var _prev_state_hash: String = ""
var _event_log_entries: Array = []
const MAX_LOG_ENTRIES := 80


# ── Ciclo de vida ─────────────────────────────────────────────────────────────

func _ready() -> void:
	game_panel.hide()
	result_panel.hide()
	error_label.hide()

	start_button.pressed.connect(_on_start_pressed)
	save_button.pressed.connect(_on_save_pressed)
	new_game_button.pressed.connect(_on_new_game_pressed)
	player_count_input.value_changed.connect(_on_player_count_changed)
	random_seed_btn.pressed.connect(_on_random_seed_pressed)

	# AcceptDialog para confirmación hot-seat (creado dinámicamente)
	_hotseat_dialog = AcceptDialog.new()
	_hotseat_dialog.title = "Hot-Seat"
	_hotseat_dialog.get_ok_button().text = "¡Listo!"
	_hotseat_dialog.confirmed.connect(_on_hotseat_confirmed)
	add_child(_hotseat_dialog)

	# Construir inputs de nombres con el valor inicial del SpinBox
	_rebuild_player_inputs(int(player_count_input.value))

	GameClient.state_updated.connect(_on_state_updated)
	GameClient.legal_actions_ready.connect(_on_legal_actions_ready)
	GameClient.game_saved.connect(_on_game_saved)
	GameClient.error_occurred.connect(_on_error)


# ── Configuración de jugadores en lobby ───────────────────────────────────────

func _on_player_count_changed(value: float) -> void:
	_rebuild_player_inputs(int(value))


func _rebuild_player_inputs(count: int) -> void:
	# Eliminar filas anteriores
	var old_children := player_names_container.get_children()
	for child in old_children:
		player_names_container.remove_child(child)
		child.queue_free()
	# Crear una fila por jugador
	for i: int in count:
		var row := HBoxContainer.new()
		var lbl := Label.new()
		lbl.text = "J%d:" % (i + 1)
		lbl.custom_minimum_size = Vector2(28, 0)
		lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		var edit := LineEdit.new()
		edit.text = "J%d" % (i + 1)
		edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		edit.name = "NameInput%d" % i
		row.add_child(lbl)
		row.add_child(edit)
		player_names_container.add_child(row)


func _get_player_names() -> Array:
	var names: Array = []
	var i := 0
	for row in player_names_container.get_children():
		var edit := row.get_node_or_null("NameInput%d" % i) as LineEdit
		var n: String = edit.text.strip_edges() if edit else ""
		names.append(n if not n.is_empty() else "J%d" % (i + 1))
		i += 1
	return names


# ── Botones de lobby ──────────────────────────────────────────────────────────

func _on_start_pressed() -> void:
	var seed: int = int(seed_input.value)
	var display_names: Array = _get_player_names()
	var count: int = display_names.size()
	# Los PIDs canónicos del engine siempre son P1, P2, P3, P4.
	# Los nombres del lobby son solo para display en el diálogo hot-seat.
	var canonical_ids: Array = []
	_player_display_names = {}
	for i: int in count:
		var pid := "P%d" % (i + 1)
		canonical_ids.append(pid)
		_player_display_names[pid] = display_names[i] if i < display_names.size() else pid
	# Sprint 5: aplicar URL de servidor desde el campo del lobby
	var url := server_url_input.text.strip_edges()
	if not url.is_empty():
		GameClient.base_url = url
	start_button.disabled = true
	start_button.text = "Conectando..."
	error_label.hide()
	_game_over = false
	_last_outcome = ""
	_pending_actor = ""
	_pending_actions = []
	GameClient.game_id = ""
	_prev_state = {}
	_prev_state_hash = ""
	_event_log_entries.clear()
	if is_instance_valid(event_log_text):
		event_log_text.text = "[color=#444]— iniciando partida —[/color]"
	GameClient.start_game(seed, canonical_ids)


# ── Señales de GameClient ─────────────────────────────────────────────────────

func _on_state_updated(state: Dictionary) -> void:
	start_button.disabled = false
	start_button.text = "Nueva partida"
	_active_actor = state.get("active_actor", "")
	_game_over = state.get("game_over", false)
	_last_outcome = state.get("outcome", "")

	# Primera actualización → pasar de lobby a juego
	if lobby_panel.visible:
		lobby_panel.hide()
		game_panel.show()

	board_view.update_state(state)
	status_label.text = _build_status(state)

	# Historial: comparar hash del estado y registrar diferencias
	var state_hash := JSON.stringify(state)
	if state_hash != _prev_state_hash:
		if not _prev_state.is_empty():
			_generate_log_events(_prev_state, state)
		_prev_state = state.duplicate(true)
		_prev_state_hash = state_hash

	if _game_over:
		action_panel.clear_actions()
		# Auto-save al terminar la partida
		GameClient.save_session()
	else:
		GameClient.fetch_legal_actions(_active_actor)


func _on_legal_actions_ready(actor: String, actions: Array) -> void:
	if actor != _active_actor or _game_over:
		return

	if actor in GameClient.local_player_ids:
		# Hot-seat: guardar datos y pedir confirmación antes de revelar acciones
		_pending_actor = actor
		_pending_actions = actions
		action_panel.show_waiting(actor)
		var display_name: String = _player_display_names.get(actor, actor)
		_hotseat_dialog.dialog_text = "Turno de %s\n¿Listo para jugar?" % display_name
		_hotseat_dialog.popup_centered()
	else:
		# Modo observador: actor remoto o bot — no mostrar acciones
		action_panel.show_waiting(actor)


func _on_hotseat_confirmed() -> void:
	if not _pending_actor.is_empty() and not _game_over:
		action_panel.show_actions(_pending_actor, _pending_actions)
		_pending_actor = ""
		_pending_actions = []


func _on_save_pressed() -> void:
	GameClient.save_session()


func _on_game_saved(result: Dictionary) -> void:
	if _game_over:
		var outcome_str: String = _last_outcome if not _last_outcome.is_empty() else "?"
		result_label.text = (
			"RESULTADO: %s\n\n" % outcome_str
			+ "Guardada en: %s\n" % result.get("saved_to", "?")
			+ "Pasos registrados: %d" % result.get("steps", 0)
		)
		result_panel.show()


func _on_new_game_pressed() -> void:
	result_panel.hide()
	game_panel.hide()
	lobby_panel.show()
	start_button.disabled = false
	start_button.text = "Nueva partida"
	_pending_actor = ""
	_pending_actions = []


func _on_error(message: String) -> void:
	start_button.disabled = false
	start_button.text = "Nueva partida"
	error_label.text = "⚠ " + message
	error_label.show()


# ── Helpers privados ──────────────────────────────────────────────────────────

func _build_status(state: Dictionary) -> String:
	if state.get("game_over", false):
		return "PARTIDA TERMINADA — %s" % state.get("outcome", "?")
	return "Ronda %d  |  Fase: %s  |  Turno: %s" % [
		state.get("round", 0),
		state.get("phase", "?"),
		state.get("active_actor", "?"),
	]


func _on_random_seed_pressed() -> void:
	seed_input.value = (randi() % 999998) + 1


func _add_log_entry(text: String, color: String = "888888") -> void:
	_event_log_entries.append("[color=#%s]%s[/color]" % [color, text])
	if _event_log_entries.size() > MAX_LOG_ENTRIES:
		_event_log_entries.remove_at(0)
	if is_instance_valid(event_log_text):
		event_log_text.text = "\n".join(_event_log_entries)
	await get_tree().process_frame
	if is_instance_valid(event_log_text):
		var scroll := event_log_text.get_parent() as ScrollContainer
		if is_instance_valid(scroll):
			scroll.scroll_vertical = 999999


func _generate_log_events(prev: Dictionary, curr: Dictionary) -> void:
	var prev_round: int = prev.get("round", 0)
	var curr_round: int = curr.get("round", 0)
	var prev_phase: String = prev.get("phase", "")
	var curr_phase: String = curr.get("phase", "")

	if curr_round != prev_round:
		_add_log_entry("══ Ronda %d ══" % curr_round, "fff176")
	elif curr_phase != prev_phase:
		_add_log_entry("Fase: %s → %s" % [prev_phase, curr_phase], "ce93d8")

	var prev_players: Dictionary = prev.get("players", {})
	var curr_players: Dictionary = curr.get("players", {})
	for pid: String in curr_players:
		var pp: Dictionary = prev_players.get(pid, {})
		var cp: Dictionary = curr_players[pid]
		var prev_san: int = pp.get("sanity", cp.get("sanity", 0))
		var curr_san: int = cp.get("sanity", 0)
		var prev_keys: int = pp.get("keys", cp.get("keys", 0))
		var curr_keys: int = cp.get("keys", 0)
		var prev_room: String = str(pp.get("room", cp.get("room", "")))
		var curr_room: String = str(cp.get("room", ""))
		var prev_objs: Array = pp.get("objects", [])
		var curr_objs: Array = cp.get("objects", [])

		if curr_san <= 0 and prev_san > 0:
			_add_log_entry("✗ %s eliminado" % pid, "ef5350")
		elif curr_san < prev_san:
			_add_log_entry("  %s -%d cord (%d/%d)" % [pid, prev_san - curr_san, curr_san, cp.get("sanity_max", 10)], "ef9a9a")
		elif curr_san > prev_san:
			_add_log_entry("  %s +%d cord" % [pid, curr_san - prev_san], "a5d6a7")

		if curr_keys > prev_keys:
			_add_log_entry("  K+ %s obtiene llave" % pid, "ffcc80")
		elif curr_keys < prev_keys:
			_add_log_entry("  K- %s usa llave" % pid, "ffb74d")

		if curr_room != prev_room and not prev_room.is_empty():
			_add_log_entry("  %s → %s" % [pid, curr_room], "64b5f6")

		for obj: String in curr_objs:
			if obj not in prev_objs:
				_add_log_entry("  %s + %s" % [pid, obj], "80cbc4")
		for obj: String in prev_objs:
			if obj not in curr_objs:
				_add_log_entry("  %s - %s" % [pid, obj], "b0bec5")

	var prev_king: int = prev.get("king_floor", 1)
	var curr_king: int = curr.get("king_floor", 1)
	if curr_king != prev_king:
		_add_log_entry("★ Rey → piso %d" % curr_king, "ce93d8")

	if curr.get("game_over", false) and not prev.get("game_over", false):
		var outcome: String = curr.get("outcome", "?")
		var won: bool = "WIN" in outcome.to_upper()
		_add_log_entry("★ FIN: %s" % outcome, "69f0ae" if won else "ef5350")
