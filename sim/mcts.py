from __future__ import annotations
from typing import List, Optional, Dict, Any, Callable
import math
import time

from engine.state import GameState
from engine.actions import Action, ActionType
from engine.config import Config
from engine.rng import RNG
from engine.transition import step
from engine.legality import get_legal_actions
from sim.metrics import calculate_reward

class MCTSNode:
    def __init__(
        self, 
        state: GameState, 
        parent: Optional[MCTSNode] = None, 
        action: Optional[Action] = None
    ):
        self.state = state
        self.parent = parent
        self.action = action  # The action that led to this state
        self.children: List[MCTSNode] = []
        self.visits: int = 0
        self.value: float = 0.0
        self.untried_actions: Optional[List[Action]] = None

    def is_fully_expanded(self) -> bool:
        return self.untried_actions is not None and len(self.untried_actions) == 0

    def best_child(self, exploration_weight: float = 1.41) -> MCTSNode:
        # UCB1 Selection
        best_score = -float('inf')
        best_nodes = []
        
        for c in self.children:
            if c.visits == 0:
                return c # Should not happen if expanded correctly
                
            exploitation = c.value / c.visits
            exploration = exploration_weight * math.sqrt(math.log(self.visits) / c.visits)
            score = exploitation + exploration
            
            if score > best_score:
                best_score = score
                best_nodes = [c]
            elif score == best_score:
                best_nodes.append(c)
        
        # Tie-break deterministically or randomly? 
        # Using the first one for stability, or we could pass an RNG.
        return best_nodes[0]

def _run_rollout(
    start_state: GameState, 
    cfg: Config, 
    rng: RNG, 
    rollout_policy_fn: Callable[[GameState, RNG], Action],
    max_depth: int
) -> float:
    """
    Simulates a game trajectory from start_state using the given policy.
    Returns the accumulated reward (canonical RL reward).
    """
    state = start_state
    total_reward = 0.0
    depth = 0
    
    while not state.game_over and depth < max_depth:
        action = rollout_policy_fn(state, rng)
        # Fail-safe
        if action is None:
            # End turn if no action returned (should not happen with valid policies)
            action = Action(actor=state.turn_order[state.turn_pos] if state.phase=="PLAYER" else "KING", type=ActionType.END_TURN, data={})

        next_state = step(state, action, rng, cfg)
        
        # Accumulate reward
        r = calculate_reward(state, next_state, cfg)
        total_reward += r
        
        state = next_state
        depth += 1
    
    return total_reward

def mcts_search(
    root_state: GameState,
    cfg: Config,
    rng: RNG,
    player_id: str,
    rollout_policy_fn: Callable[[GameState, RNG], Action],
    opponent_policy_fn: Callable[[GameState, RNG], Action],
    num_rollouts: int = 100,
    max_depth: int = 50,
    exploration_weight: float = 1.41
) -> Action:
    """
    Performs MCTS Search.
    
    Args:
        root_state: Current game state.
        cfg: Game config.
        rng: RNG for simulations.
        player_id: The ID of the player running MCTS (optimizing for this player).
        rollout_policy_fn: Policy used for rollouts (simulation phase).
        opponent_policy_fn: Policy used for opponents/environment in the tree (expansion phase).
                            This allows us to model King/Other Players as fixed policies rather than searching their trees.
        num_rollouts: Number of iterations.
        max_depth: Max depth for rollout.
    """
    
    # Root Node
    root = MCTSNode(root_state)
    
    # Get Legal Actions for Root
    # Root is always "My Turn" (checked by caller)
    actor = root_state.turn_order[root_state.turn_pos] if root_state.phase == "PLAYER" else "KING"
    # assert str(actor) == player_id, f"MCTS called for {player_id} but it is {actor}'s turn"
    
    root.untried_actions = get_legal_actions(root_state, actor)
    
    if not root.untried_actions:
        return Action(actor=actor, type=ActionType.END_TURN, data={})

    for i in range(num_rollouts):
        node = root
        state = root_state
        
        # 1. Selection
        while node.is_fully_expanded() and not node.children == []:
            node = node.best_child(exploration_weight)
            state = node.state
            if state.game_over:
                break
        
        # 2. Expansion
        if not state.game_over and node.untried_actions:
            # Pop an untried action
            action = node.untried_actions.pop()
            
            # Step
            # Use a forked RNG for the step from the tree node? 
            # In MCTS-lite (P0), we assume one sample is enough or we use deterministic transition if possible.
            # But the game is stochastic. 
            # Ideally, a node represents (State). The edge is (Action). 
            # The result of Action is (Next State). In stochastic games, Action -> [Next States].
            # For P0, we will just sample ONE transition per expansion.
            # This makes it "Open Loop" effectively if we don't aggregate same-param states.
            # We are building a tree of STATES.
            next_state = step(state, action, rng.fork(f"mcts_{i}_{node.visits}"), cfg)
            
            child_node = MCTSNode(next_state, parent=node, action=action)
            
            # Prepare untried_actions for the child
            if not next_state.game_over:
                next_actor = next_state.turn_order[next_state.turn_pos] if next_state.phase == "PLAYER" else "KING"
                
                if str(next_actor) == player_id:
                    # It's our turn again: Expand ALL options
                    child_node.untried_actions = get_legal_actions(next_state, next_actor)
                else:
                    # It's opponent/teammate turn: Model them with Fixed Policy
                    # We treat their move as a deterministic (or single-sample) transition
                    # effectively "Branching Factor = 1" for their turn in the tree.
                    op_action = opponent_policy_fn(next_state, rng.fork(f"op_{i}"))
                    if op_action:
                        child_node.untried_actions = [op_action]
                    else:
                        child_node.untried_actions = [] 
            else:
                child_node.untried_actions = []

            node.children.append(child_node)
            node = child_node
            state = next_state

        # 3. Simulation (Rollout)
        # Run until depth or terminal
        rollout_reward = _run_rollout(state, cfg, rng.fork(f"rollout_{i}"), rollout_policy_fn, max_depth)
        
        # Add the reward we already got reaching this node?
        # Usually rewards are additive. `_run_rollout` returns sum of future rewards.
        # But we also have rewards on the PATH to this node.
        # However, classic MCTS assesses the value of the 'leaf'.
        # If we collect intermediate rewards, we propagate them.
        # `calculate_reward` is (State -> Next State).
        # We need to backtrack and add rewards from the edges in the tree too!
        
        # Better approach: 
        # Value of a node = Reward to get there? No.
        # Value of a node = Average Future Reward from this state.
        # So `rollout_reward` is exactly that.
        
        # 4. Backpropagation
        while node is not None:
            node.visits += 1
            node.value += rollout_reward
            
            # Update rollout_reward with the reward *leading* to this node?
            # Standard: V(s) = r + V(s')
            # Here `rollout_reward` is the sum of rewards from `node.state` onwards.
            # When we go up to parent, we need to add the reward of (parent -> node).
            
            if node.parent:
                edge_reward = calculate_reward(node.parent.state, node.state, cfg)
                rollout_reward += edge_reward
            
            node = node.parent

    # Select best action (most visited)
    # Root's children are (State) nodes derived from (Action).
    if not root.children:
        return None # Should be handled by fallback

    best_child = max(root.children, key=lambda c: c.visits)
    return best_child.action
