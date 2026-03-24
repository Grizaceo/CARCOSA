# scripts/Main.gd
# Controlador principal: maneja lobby → juego → resultado.
# Recibe señales de GameClient y coordina BoardView + ActionPanel.
extends Control

# ── Referencias de escena ─────────────────────────────────────────────────────
@onready var lobby_panel: Control = $LobbyPanel
@onready var game_panel: Control = $GamePanel
@onready var seed_input: SpinBox = $LobbyPanel/MarginContainer/VBox/SeedRow/SeedInput
@onready var start_button: Button = $LobbyPanel/MarginContainer/VBox/StartButton
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


# ── Ciclo de vida ─────────────────────────────────────────────────────────────

func _ready() -> void:
	game_panel.hide()
	result_panel.hide()
	error_label.hide()

	start_button.pressed.connect(_on_start_pressed)
	save_button.pressed.connect(_on_save_pressed)
	new_game_button.pressed.connect(_on_new_game_pressed)

	GameClient.state_updated.connect(_on_state_updated)
	GameClient.legal_actions_ready.connect(_on_legal_actions_ready)
	GameClient.game_saved.connect(_on_game_saved)
	GameClient.error_occurred.connect(_on_error)


# ── Botones de lobby ──────────────────────────────────────────────────────────

func _on_start_pressed() -> void:
	var seed: int = int(seed_input.value)
	start_button.disabled = true
	start_button.text = "Conectando..."
	error_label.hide()
	_game_over = false
	GameClient.game_id = ""
	GameClient.start_game(seed)


# ── Señales de GameClient ─────────────────────────────────────────────────────

func _on_state_updated(state: Dictionary) -> void:
	start_button.disabled = false
	start_button.text = "Nueva partida"
	_active_actor = state.get("active_actor", "")
	_game_over = state.get("game_over", false)

	# Primera actualización → pasar de lobby a juego
	if lobby_panel.visible:
		lobby_panel.hide()
		game_panel.show()

	board_view.update_state(state)
	status_label.text = _build_status(state)

	if _game_over:
		action_panel.clear_actions()
		GameClient.save_session()
	else:
		GameClient.fetch_legal_actions(_active_actor)


func _on_legal_actions_ready(actor: String, actions: Array) -> void:
	if actor == _active_actor and not _game_over:
		action_panel.show_actions(actor, actions)


func _on_save_pressed() -> void:
	GameClient.save_session()


func _on_game_saved(result: Dictionary) -> void:
	if _game_over:
		result_label.text = (
			"Partida terminada.\n"
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
