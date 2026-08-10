import os
import sys
import numpy as np
import argparse
from pathlib import Path
import pickle
from tqdm import tqdm

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from train.carcosa_env import CarcosaEnv
from sim.policies import GoalDirectedPlayerPolicy
from sim.memory import create_team_memory, create_bot_memories, CardMemory
from engine.actions import ActionType


def collect_data(
    num_episodes=1000, max_steps=1000, output_path="train/expert_data.pkl"
):
    env = CarcosaEnv()
    policy = GoalDirectedPlayerPolicy()

    obs_data = []
    action_data = []

    wins = 0

    print(f"Collecting data from {num_episodes} episodes WITH MEMORY...")

    for ep in tqdm(range(num_episodes)):
        # Important: the policy itself doesn't need to be recreated, but its memory DOES.
        team_memory = create_team_memory()
        bot_memories = create_bot_memories(["P1", "P2", "P3", "P4"])
        policy.set_memory(team_memory, bot_memories)

        obs, info = env.reset(seed=ep + 10000)
        team_memory.sync_from_state(env.state)

        done = False
        truncated = False

        ep_obs = []
        ep_actions = []

        step_count = 0
        while not (done or truncated) and step_count < max_steps:
            state = env.state
            actor = str(state.turn_order[state.turn_pos])
            phase = state.phase

            # Use GOAL policy
            rng = env.rng
            action = policy.choose(state, rng)

            # Map action to ID
            try:
                action_id = env.ACTION_TYPES.index(action.type)
            except ValueError:
                action_id = env.ACTION_TYPES.index(ActionType.END_TURN)

            # Store observation BEFORE action ONLY if it's a player turn
            if phase != "KING":
                ep_obs.append(obs)
                ep_actions.append(action_id)

            # Step in environment
            obs, reward, done, truncated, info = env.step(action_id)
            step_count += 1

            # --- MEMORY UPDATES (Mirroring sim/runner.py) ---
            next_state = env.state
            last_action_type = env.ACTION_TYPES[action_id]

            if last_action_type == ActionType.KING_ENDROUND:
                team_memory.sync_from_state(next_state)
                team_memory.age_all_memories(bot_memories)
                team_memory.optimize_assignments(bot_memories)

            # Capture observations (PEEK/SEARCH)
            # Reusing the logic from sim/runner._capture_observed_cards but simplified
            if actor in next_state.players:
                if last_action_type == ActionType.SEARCH:
                    _ = next_state.players[actor].room
                elif last_action_type == ActionType.PEEK_ROOM_DECK:
                    # In env, we don't easily have the specific action object with data here
                    # but we can check what was peeked from env.shared_info_memory
                    pass

                # Simplified: Just sync whatever the environment discovered in shared_info_memory
                for key, entry in env.shared_info_memory.items():
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
                        current_room=team_memory.room_for_box.get(entry["box_id"]),
                    )
                    team_memory.share_card(card_mem, from_player=entry["source_player"])
                team_memory.optimize_assignments(bot_memories)

        # Data selection: Win, Keys, or Good Survival
        is_good = False
        if info.get("outcome") == "WIN":
            wins += 1
            is_good = True
        elif info.get("keys_in_hand", 0) >= 1:
            is_good = True
        elif step_count >= 250:
            is_good = True

        if is_good:
            obs_data.extend(ep_obs)
            action_data.extend(ep_actions)

    print("\nCollection finished.")
    print(f"Wins: {wins}/{num_episodes} ({wins / num_episodes:.1%})")
    print(f"Total samples collected: {len(obs_data)}")

    # Load existing data if appending is possible
    if os.path.exists(output_path):
        try:
            with open(output_path, "rb") as f:
                existing_data = pickle.load(f)
                obs_data = list(existing_data.get("observations", [])) + obs_data
                action_data = list(existing_data.get("actions", [])) + action_data
                print(f"Appended to existing data. New total: {len(obs_data)}")
        except Exception as e:
            print(f"Could not append to existing data: {e}. Saving new file.")

    data = {
        "observations": np.array(obs_data, dtype=np.float32),
        "actions": np.array(action_data, dtype=np.int64),
    }

    with open(output_path, "wb") as f:
        pickle.dump(data, f)

    print(f"Saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=1000)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--output", type=str, default="train/expert_data.pkl")
    args = parser.parse_args()

    collect_data(
        num_episodes=args.episodes, max_steps=args.max_steps, output_path=args.output
    )
