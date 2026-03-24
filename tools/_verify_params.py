from sim.policies import GoalDirectedPlayerPolicy
from engine.config import Config
p = GoalDirectedPlayerPolicy(Config())
print("meditate_critical:", p.meditate_critical)
print("king_flee_sanity:", p.king_flee_sanity)
print("king_flee_round_threshold:", p.king_flee_round_threshold)
print("late_game_meditate_bonus:", p.late_game_meditate_bonus)
print("search_sanity_min:", p.search_sanity_min)
print("role_sanity_bias:", p._role_sanity_bias)
