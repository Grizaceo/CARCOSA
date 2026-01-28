from __future__ import annotations

import contextlib
import io
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple

from engine.config import Config
from sim.runner import run_episode
from sim import policies


@dataclass
class BatchResult:
    version_dir: str
    winrate: float
    wins: int
    total: int
    outcome_counts: Dict[str, int]
    action_rate_win: Dict[str, float]
    action_rate_loss: Dict[str, float]
    action_counts_win: Dict[str, int]
    action_counts_loss: Dict[str, int]
    object_counts_win: Dict[str, int]
    object_counts_loss: Dict[str, int]
    steps_avg_win: float
    steps_med_win: float
    steps_avg_loss: float
    steps_med_loss: float
    rounds_avg_win: float
    rounds_med_win: float
    rounds_avg_loss: float
    rounds_med_loss: float
    keys_in_hand_win: float
    keys_in_hand_loss: float
    keys_destroyed_win: float
    keys_destroyed_loss: float
    final_avg_win: Dict[str, float]
    final_avg_loss: Dict[str, float]


def _git(cmd, default="unknown"):
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except Exception:
        return default


def _load_params(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f) or {}


def _save_params(path: Path, params: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2)


def run_batch(seeds, max_steps: int, base_dir: Path) -> str:
    commit = _git(["git", "rev-parse", "--short", "HEAD"])
    branch = _git(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_dir = base_dir / f"runs_v{commit}_{branch}_{ts}"
    version_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "commit": commit,
        "branch": branch,
        "timestamp": ts,
        "seeds": list(seeds),
        "max_steps": max_steps,
        "version_dir": str(version_dir),
        "policy": "GOAL",
    }
    with open(version_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    cfg = Config()

    completed = 0
    for seed in seeds:
        out_file = version_dir / f"seed{seed}.jsonl"
        if out_file.exists():
            completed += 1
            continue
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            state = run_episode(max_steps=max_steps, seed=seed, out_path=str(out_file), cfg=cfg, policy_name="GOAL")
        completed += 1
        if completed % 50 == 0:
            print(f"[{completed}/{len(seeds)}] seed {seed} -> {state.outcome} (round {state.round})")

    return str(version_dir)


def analyze_batch(version_dir: str) -> BatchResult:
    vpath = Path(version_dir)
    summary_files = sorted(vpath.glob("*summary.json"))
    runs = []
    for sf in summary_files:
        with open(sf, "r", encoding="utf-8") as f:
            s = json.load(f)
        seed = s.get("seed")
        runs.append((seed, s, sf))

    total = len(runs)
    win_runs = [(seed, s, sf) for seed, s, sf in runs if s.get("outcome") == "WIN"]
    lose_runs = [(seed, s, sf) for seed, s, sf in runs if s.get("outcome") != "WIN"]

    outcome_counts: Dict[str, int] = {}
    for _, s, _ in runs:
        outcome_counts[s.get("outcome")] = outcome_counts.get(s.get("outcome"), 0) + 1

    def analyze_group(group):
        action_counts: Dict[str, int] = {}
        object_counts: Dict[str, int] = {}
        total_steps = 0
        keys_in_hand_sum = 0
        keys_destroyed_sum = 0
        steps_list = []
        rounds_list = []
        final_sum: Dict[str, float] = {}

        for seed, s, sf in group:
            jsonl = sf.with_name(f"seed{seed}.jsonl")
            total_steps += s.get("steps") or 0
            keys_in_hand_sum += s.get("keys_in_hand") or 0
            keys_destroyed_sum += s.get("keys_destroyed_total") or 0
            steps_list.append(s.get("steps") or 0)
            rounds_list.append(s.get("round") or 0)
            last = None
            with open(jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    atype = rec.get("action_type")
                    if atype:
                        action_counts[atype] = action_counts.get(atype, 0) + 1
                        if atype == "USE_OBJECT":
                            obj_id = rec.get("action_data", {}).get("object_id")
                            if obj_id:
                                object_counts[obj_id] = object_counts.get(obj_id, 0) + 1
                    last = rec
            if last is not None:
                sp = last.get("summary_post", {})
                for k in ("keys_in_hand", "keys_destroyed", "monsters", "min_sanity", "mean_sanity", "umbral_frac"):
                    if sp.get(k) is not None:
                        final_sum[k] = final_sum.get(k, 0.0) + float(sp.get(k))

        action_rate = {}
        if total_steps > 0:
            for k, v in action_counts.items():
                action_rate[k] = (v / total_steps) * 100

        avg_keys_in_hand = (keys_in_hand_sum / len(group)) if group else 0.0
        avg_keys_destroyed = (keys_destroyed_sum / len(group)) if group else 0.0

        def _avg(vals):
            return (sum(vals) / len(vals)) if vals else 0.0

        def _med(vals):
            if not vals:
                return 0.0
            vals = sorted(vals)
            mid = len(vals) // 2
            if len(vals) % 2 == 1:
                return float(vals[mid])
            return (vals[mid - 1] + vals[mid]) / 2.0

        steps_avg = _avg(steps_list)
        steps_med = _med(steps_list)
        rounds_avg = _avg(rounds_list)
        rounds_med = _med(rounds_list)

        final_avg = {}
        if group:
            for k, v in final_sum.items():
                final_avg[k] = v / len(group)

        return (
            action_rate,
            action_counts,
            object_counts,
            avg_keys_in_hand,
            avg_keys_destroyed,
            steps_avg,
            steps_med,
            rounds_avg,
            rounds_med,
            final_avg,
        )

    (
        win_action_rate,
        win_action_counts,
        win_object_counts,
        win_keys_in_hand,
        win_keys_destroyed,
        win_steps_avg,
        win_steps_med,
        win_rounds_avg,
        win_rounds_med,
        win_final_avg,
    ) = analyze_group(win_runs)
    (
        lose_action_rate,
        lose_action_counts,
        lose_object_counts,
        lose_keys_in_hand,
        lose_keys_destroyed,
        lose_steps_avg,
        lose_steps_med,
        lose_rounds_avg,
        lose_rounds_med,
        lose_final_avg,
    ) = analyze_group(lose_runs)

    return BatchResult(
        version_dir=version_dir,
        winrate=(len(win_runs) / total) if total else 0.0,
        wins=len(win_runs),
        total=total,
        outcome_counts=outcome_counts,
        action_rate_win=win_action_rate,
        action_rate_loss=lose_action_rate,
        action_counts_win=win_action_counts,
        action_counts_loss=lose_action_counts,
        object_counts_win=win_object_counts,
        object_counts_loss=lose_object_counts,
        steps_avg_win=win_steps_avg,
        steps_med_win=win_steps_med,
        steps_avg_loss=lose_steps_avg,
        steps_med_loss=lose_steps_med,
        rounds_avg_win=win_rounds_avg,
        rounds_med_win=win_rounds_med,
        rounds_avg_loss=lose_rounds_avg,
        rounds_med_loss=lose_rounds_med,
        keys_in_hand_win=win_keys_in_hand,
        keys_in_hand_loss=lose_keys_in_hand,
        keys_destroyed_win=win_keys_destroyed,
        keys_destroyed_loss=lose_keys_destroyed,
        final_avg_win=win_final_avg,
        final_avg_loss=lose_final_avg,
    )


def _print_batch_analysis(result: BatchResult) -> None:
    print(f"Winrate: {result.winrate:.1%} ({result.wins}/{result.total})")
    print(f"Outcome breakdown: {result.outcome_counts}")

    print(f"\n[WIN] steps avg/med: ({result.steps_avg_win:.2f}, {result.steps_med_win:.2f})")
    print(f"[WIN] rounds avg/med: ({result.rounds_avg_win:.2f}, {result.rounds_med_win:.2f})")
    print(f"[WIN] keys_in_hand avg: {result.keys_in_hand_win:.2f}")
    print(f"[WIN] keys_destroyed avg: {result.keys_destroyed_win:.2f}")

    print(f"[LOSS] steps avg/med: ({result.steps_avg_loss:.2f}, {result.steps_med_loss:.2f})")
    print(f"[LOSS] rounds avg/med: ({result.rounds_avg_loss:.2f}, {result.rounds_med_loss:.2f})")
    print(f"[LOSS] keys_in_hand avg: {result.keys_in_hand_loss:.2f}")
    print(f"[LOSS] keys_destroyed avg: {result.keys_destroyed_loss:.2f}")

    all_action_types = set(result.action_rate_win) | set(result.action_rate_loss)
    rate_deltas = []
    for at in all_action_types:
        w = result.action_rate_win.get(at, 0.0)
        l = result.action_rate_loss.get(at, 0.0)
        rate_deltas.append((w - l, at, w, l))
    rate_deltas.sort(reverse=True)

    print("\nTop + action rate (per 100 steps) in wins vs losses:")
    for delta, at, w, l in rate_deltas[:10]:
        print(f"  {at:24s} +{delta:6.2f} (win {w:.2f} / loss {l:.2f})")

    print("\nTop - action rate (per 100 steps) in wins vs losses:")
    for delta, at, w, l in rate_deltas[-10:]:
        print(f"  {at:24s} {delta:6.2f} (win {w:.2f} / loss {l:.2f})")

    print("\nObject uses in wins (count):", dict(result.object_counts_win))
    print("Object uses in losses (count):", dict(result.object_counts_loss))

    if result.final_avg_win:
        print("\n[WIN] final state averages:")
        for k, v in result.final_avg_win.items():
            print(f"  {k}: {v:.2f}")

    if result.final_avg_loss:
        print("\n[LOSS] final state averages:")
        for k, v in result.final_avg_loss.items():
            print(f"  {k}: {v:.2f}")


def tune_params(params: Dict[str, Any], result: BatchResult) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    # Defaults
    params = params.copy()
    params.setdefault("meditate_critical", -3)
    params.setdefault("move_for_better_delta", 2)
    params.setdefault("search_local_min_remaining", 1)
    params.setdefault("vial_margin", 1)
    params.setdefault("endgame_force_umbral", True)

    win_rate = result.winrate

    win_meditate = result.action_rate_win.get("MEDITATE", 0.0)
    loss_meditate = result.action_rate_loss.get("MEDITATE", 0.0)
    win_move = result.action_rate_win.get("MOVE", 0.0)
    loss_move = result.action_rate_loss.get("MOVE", 0.0)
    win_search = result.action_rate_win.get("SEARCH", 0.0)
    loss_search = result.action_rate_loss.get("SEARCH", 0.0)

    changes: Dict[str, Any] = {}

    # Heuristic adjustments
    if win_rate < 0.25:
        # Meditate tuning
        if (loss_meditate - win_meditate) > 2.0:
            new_val = max(-4, int(params["meditate_critical"]) - 1)
            if new_val != params["meditate_critical"]:
                params["meditate_critical"] = new_val
                changes["meditate_critical"] = new_val
        elif (win_meditate - loss_meditate) > 1.0:
            new_val = min(-2, int(params["meditate_critical"]) + 1)
            if new_val != params["meditate_critical"]:
                params["meditate_critical"] = new_val
                changes["meditate_critical"] = new_val

        # SEARCH vs MOVE
        if (loss_search - win_search) > 1.0:
            new_val = min(2, int(params["search_local_min_remaining"]) + 1)
            if new_val != params["search_local_min_remaining"]:
                params["search_local_min_remaining"] = new_val
                changes["search_local_min_remaining"] = new_val
        elif (win_search - loss_search) > 1.0:
            new_val = max(1, int(params["search_local_min_remaining"]) - 1)
            if new_val != params["search_local_min_remaining"]:
                params["search_local_min_remaining"] = new_val
                changes["search_local_min_remaining"] = new_val

        # Move aggressiveness between floors
        if (win_move - loss_move) > 3.0:
            new_val = max(1, int(params["move_for_better_delta"]) - 1)
            if new_val != params["move_for_better_delta"]:
                params["move_for_better_delta"] = new_val
                changes["move_for_better_delta"] = new_val
        elif (loss_move - win_move) > 2.0:
            new_val = min(3, int(params["move_for_better_delta"]) + 1)
            if new_val != params["move_for_better_delta"]:
                params["move_for_better_delta"] = new_val
                changes["move_for_better_delta"] = new_val

        # Vial margin if losses meditate much more
        if (loss_meditate - win_meditate) > 2.0:
            new_val = min(2, int(params["vial_margin"]) + 1)
            if new_val != params["vial_margin"]:
                params["vial_margin"] = new_val
                changes["vial_margin"] = new_val

    return params, changes


def main():
    end_time = datetime(2026, 1, 28, 8, 0, 0)
    base_dir = Path("runs")
    params_path = Path("sim") / "policy_params.json"
    params = _load_params(params_path)

    log_path = Path("runs") / f"tuning_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    batch_idx = 0
    best_winrate = 0.0
    best_version = None
    best_params = None

    while datetime.now() < end_time:
        batch_idx += 1
        print(f"\n=== Batch {batch_idx} ===")
        version_dir = run_batch(range(1, 1001), 2000, base_dir)
        result = analyze_batch(version_dir)

        if result.winrate > best_winrate:
            best_winrate = result.winrate
            best_version = result.version_dir
            best_params = params.copy()

        _print_batch_analysis(result)

        params, changes = tune_params(params, result)
        if changes:
            _save_params(params_path, params)
            policies.refresh_policy_params()
            print(f"Policy changes: {changes}")
        else:
            print("No policy changes this batch.")

        # Log batch result
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "batch": batch_idx,
                "version_dir": result.version_dir,
                "winrate": result.winrate,
                "wins": result.wins,
                "total": result.total,
                "outcome_counts": result.outcome_counts,
                "params": params,
                "changes": changes,
            }) + "\n")

        # Check time before starting next batch
        if datetime.now() >= end_time:
            break

    print("\n=== Tuning finished ===")
    print(f"Best winrate: {best_winrate:.1%}")
    if best_version:
        print(f"Best run directory: {best_version}")
    if best_params:
        print(f"Best params: {best_params}")
    print(f"Log: {log_path}")


if __name__ == "__main__":
    main()
