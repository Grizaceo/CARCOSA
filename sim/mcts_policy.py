from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from engine.state import GameState
from engine.actions import Action, ActionType
from engine.config import Config
from engine.rng import RNG
from engine.legality import get_legal_actions

from sim.policies import PlayerPolicy, GoalDirectedPlayerPolicy, HeuristicKingPolicy
from sim.mcts import mcts_search

@dataclass
class MCTSPlayerPolicy(PlayerPolicy):
    """
    Política basada en Monte Carlo Tree Search.
    
    Params:
        rollouts: Número de iteraciones MCTS por turno.
        depth: Profundidad máxima del rollout.
        determinize: (Placeholder) Si True, determiniza el estado oculto antes de buscar.
    """
    cfg: Config = Config()
    rollouts: int = 100
    depth: int = 50
    determinize: bool = False # P0: Ignored (Cheats by looking at full state)

    def __post_init__(self):
        # Override with Config if defaults (hacky, but dataclass init order matters)
        # Ideally we trust `rollouts` passed in, but if caller didn't pass it, we use cfg.
        # But `runner.py` passes `rollouts=getattr(cfg...` manually.
        # Let's just ensure we respect cfg if available.
        if self.rollouts == 100 and hasattr(self.cfg, "MCTS_ROLLOUTS"):
             self.rollouts = self.cfg.MCTS_ROLLOUTS
        if self.depth == 50 and hasattr(self.cfg, "MCTS_DEPTH"):
             self.depth = self.cfg.MCTS_DEPTH

        # Default policies for Rollout and Opponent modeling
        # We use GoalDirected for teammates and Heuristic for King.
        self._default_player_policy = GoalDirectedPlayerPolicy(self.cfg)
        self._king_policy = HeuristicKingPolicy(self.cfg)

    def _rollout_policy(self, state: GameState, rng: RNG) -> Action:
        """
        Policy used during the Simulation phase (Play out).
        Delegates to existing heuristics.
        """
        active = state.turn_order[state.turn_pos] if state.phase == "PLAYER" else "KING"
        
        if active == "KING":
            act = self._king_policy.choose(state, rng)
            if act is None:
                act = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
            return act
        else:
            # Player
            act = self._default_player_policy.choose(state, rng)
            if act is None:
                 act = Action(actor=str(active), type=ActionType.END_TURN, data={})
            return act

    def _opponent_policy(self, state: GameState, rng: RNG) -> Action:
        """
        Policy used during Tree Expansion for NON-controlled actors.
        """
        return self._rollout_policy(state, rng)

    def choose(self, state: GameState, rng: RNG) -> Action:
        actor = state.turn_order[state.turn_pos] if state.phase == "PLAYER" else "KING"
        
        # Only invoke MCTS if it is a Player turn (sanity check)
        if actor == "KING":
             return Action(actor=actor, type=ActionType.END_TURN, data={})

        # MCTS Search
        # Note: We pass player_id=str(actor) so MCTS knows who it is optimizing for.
        best_action = mcts_search(
            root_state=state,
            cfg=self.cfg,
            rng=rng,
            player_id=str(actor),
            rollout_policy_fn=self._rollout_policy,
            opponent_policy_fn=self._opponent_policy,
            num_rollouts=self.rollouts,
            max_depth=self.depth
        )
        
        if best_action:
            return best_action
            
        # Fallback
        return Action(actor=str(actor), type=ActionType.END_TURN, data={})
