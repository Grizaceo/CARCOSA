import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from train.carcosa_env import CarcosaEnv
from sim.policies import GoalDirectedPlayerPolicy
from sim.memory import create_team_memory, create_bot_memories
from engine.actions import ActionType

def test():
    env = CarcosaEnv(render_mode="human")
    policy = GoalDirectedPlayerPolicy()
    
    team_memory = create_team_memory()
    bot_memories = create_bot_memories(["P1", "P2", "P3", "P4"])
    policy.set_memory(team_memory, bot_memories)
    
    obs, info = env.reset(seed=10043) # Seed that wins in benchmark
    team_memory.sync_from_state(env.state)
    
    done = False
    step_count = 0
    while not done and step_count < 500:
        state = env.state
        actor = str(state.turn_order[state.turn_pos])
        phase = state.phase
        
        if phase == "KING":
            action_id = env.ACTION_TYPES.index(ActionType.KING_ENDROUND)
        else:
            action = policy.choose(state, env.rng)
            action_id = env.ACTION_TYPES.index(action.type)
            print(f"Step {step_count} | Actor: {actor} | Action: {action.type.value} | Data: {action.data}")
            
        obs, reward, done, truncated, info = env.step(action_id)
        step_count += 1
        
        # Sync memory
        if env.ACTION_TYPES[action_id] == ActionType.KING_ENDROUND:
            team_memory.sync_from_state(env.state)
        
        # Simple card capture (just to see if it works)
        for key, entry in env.shared_info_memory.items():
            from sim.memory import CardMemory
            card_mem = CardMemory(
                card_id=entry["card_id"],
                box_id=entry["box_id"],
                position_in_deck=entry["position"],
                priority=entry["priority"],
                source_player=entry["source_player"],
                seen_step=entry["seen_step"],
                seen_round=entry["seen_round"],
                confidence=entry["confidence"],
                observation_type=entry["observation_type"],
                current_room=team_memory.room_for_box.get(entry["box_id"])
            )
            team_memory.share_card(card_mem, from_player=entry["source_player"])

    print(f"Final outcome: {info.get('outcome')}")

if __name__ == "__main__":
    test()
