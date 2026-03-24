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

var _active_actor: String = ""
var _game_over: bool = false
var _last_outcome: String = ""
# Datos del jugador pendiente de confirmación en hot-seat
var _pending_actor: String = ""
var _pending_actions: Array = []
# AcceptDialog creado en tiempo de ejecución para no modificar la escena
var _hotseat_dialog: AcceptDialog = null


# ── Ciclo de vida ─────────────────────────────────────────────────────────────

func _ready() -> void:
	game_panel.hide()
	result_panel.hide()
	error_label.hide()

	start_button.pressed.connect(_on_start_pressed)
	save_button.pressed.connect(_on_save_pressed)
	new_game_button.pressed.connect(_on_new_game_pressed)
	player_count_input.value_changed.connect(_on_player_count_changed)

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
	var player_names: Array = _get_player_names()
	if player_names.is_empty():
		player_names = ["J1", "J2", "J3", "J4"]
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
	GameClient.start_game(seed, player_names)


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
		_hotseat_dialog.dialog_text = "Turno de %s\n¿Listo para jugar?" % actor
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
