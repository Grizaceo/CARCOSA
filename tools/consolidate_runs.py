"""
Consolidación multi-seed de runs del simulador Carcosa.

Uso:
    python tools/consolidate_runs.py <runs_dir> [--out <output_dir>]

Genera:
    consolidado_summary.json  — datos crudos consolidados
    consolidado_report.md     — reporte legible en markdown
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from datetime import datetime


# ---------------------------------------------------------------------------
# Lectura de datos
# ---------------------------------------------------------------------------

def load_summaries(runs_dir: Path) -> list[dict]:
    """Lee todos los *_summary.json del directorio, excluyendo outputs propios."""
    summaries = []
    for path in sorted(runs_dir.glob("*_summary.json")):
        if path.name.startswith("consolidado"):
            continue
        with open(path, encoding="utf-8") as f:
            summaries.append(json.load(f))
    return summaries


def sample_jsonl(jsonl_path: Path) -> dict:
    """Lee step 0, último step y todos los KING_ENDROUND records de un JSONL.
    Eficiente: itera una sola vez sin cargar todo en memoria."""
    result = {"first": None, "last": None, "king_endround": []}
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if result["first"] is None:
                result["first"] = rec
            if rec.get("action_type") == "KING_ENDROUND":
                result["king_endround"].append({
                    "round": rec.get("round"),
                    "T_post": rec.get("T_post"),
                    "floor": rec.get("action_data", {}).get("floor"),
                })
            result["last"] = rec
    return result


def _extract_seed_num(stem: str) -> int | None:
    """Extrae el número de seed del nombre de archivo. Ej: 'seed3' → 3, 'run_GOAL_seed2_...' → 2."""
    m = re.search(r'seed(\d+)', stem)
    return int(m.group(1)) if m else None


def load_all_jsonl(runs_dir: Path) -> list[dict]:
    """Carga muestras de todos los JSONL del directorio."""
    samples = []
    for path in sorted(runs_dir.glob("*.jsonl")):
        if "_summary" in path.name:
            continue
        s = sample_jsonl(path)
        s["path"] = str(path)
        s["seed_name"] = path.stem
        s["seed_num"] = _extract_seed_num(path.stem)
        samples.append(s)
    return samples


# ---------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------

def _safe_stat(values: list[float]) -> dict:
    if not values:
        return {"mean": None, "std": None, "min": None, "max": None}
    return {
        "mean": round(mean(values), 2),
        "std": round(stdev(values), 2) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def classify_defeat(s: dict) -> str:
    """Clasifica la causa de derrota de un summary a partir del outcome string."""
    outcome = s.get("outcome") or ""
    if outcome == "WIN":
        return "WIN"
    if not s.get("game_over"):
        return "INCOMPLETE"
    # Priorizar el string del outcome
    outcome_upper = outcome.upper()
    if "MINUS5" in outcome_upper or "SANITY" in outcome_upper:
        return "LOSE_SANITY"
    if "KEYS_DESTROYED" in outcome_upper:
        return "LOSE_KEYS"
    if "TIMEOUT" in outcome_upper:
        return "LOSE_TIMEOUT"
    return outcome or "UNKNOWN"


def analyze_outcomes(summaries: list[dict]) -> dict:
    n = len(summaries)
    outcome_counts: dict[str, int] = defaultdict(int)
    defeat_causes: dict[str, int] = defaultdict(int)

    for s in summaries:
        raw = s.get("outcome") or ("INCOMPLETE" if not s.get("game_over") else "UNKNOWN")
        outcome_counts[raw] += 1
        defeat_causes[classify_defeat(s)] += 1

    wins = outcome_counts.get("WIN", 0)
    return {
        "n": n,
        "win_rate": round(wins / n, 3) if n else 0,
        "wins": wins,
        "outcome_counts": dict(outcome_counts),
        "defeat_causes": dict(defeat_causes),
    }


def analyze_duration(summaries: list[dict]) -> dict:
    rounds = [s["round"] for s in summaries if s.get("round")]
    steps = [s["steps"] for s in summaries if s.get("steps")]
    return {
        "rounds": _safe_stat(rounds),
        "steps": _safe_stat(steps),
    }


def analyze_keys(summaries: list[dict]) -> dict:
    keys_end = [s.get("keys_in_hand", 0) or 0 for s in summaries]
    keys_dest = [s.get("keys_destroyed_total", 0) or 0 for s in summaries]
    return {
        "keys_in_hand_end": _safe_stat(keys_end),
        "keys_destroyed": _safe_stat(keys_dest),
    }


def analyze_sacrifice(summaries: list[dict]) -> dict:
    total_sac = sum(s.get("sacrifice", {}).get("sacrifice", 0) for s in summaries)
    total_acc = sum(s.get("sacrifice", {}).get("accept", 0) for s in summaries)
    total_opp = sum(s.get("sacrifice", {}).get("opportunities", 0) for s in summaries)
    sac_with_keys = sum(s.get("sacrifice", {}).get("sacrifice_with_keys", 0) for s in summaries)
    acc_with_keys = sum(s.get("sacrifice", {}).get("accept_with_keys", 0) for s in summaries)

    # Aggregate sacrifice modes
    modes: dict[str, int] = defaultdict(int)
    for s in summaries:
        for mode, cnt in (s.get("sacrifice", {}).get("sacrifice_mode", {}) or {}).items():
            modes[mode] += cnt

    return {
        "opportunities": total_opp,
        "sacrifice": total_sac,
        "accept": total_acc,
        "sac_rate": round(total_sac / (total_sac + total_acc), 3) if (total_sac + total_acc) else None,
        "sac_with_keys": sac_with_keys,
        "acc_with_keys": acc_with_keys,
        "sacrifice_modes": dict(modes),
    }


def analyze_actions(summaries: list[dict]) -> dict:
    special: dict[str, int] = defaultdict(int)
    objects: dict[str, int] = defaultdict(int)
    for s in summaries:
        for k, v in (s.get("special_actions") or {}).items():
            special[k] += v
        for k, v in (s.get("object_actions") or {}).items():
            objects[k] += v
    return {
        "special_actions": dict(special),
        "object_actions": dict(objects),
    }


def analyze_statuses(summaries: list[dict]) -> dict:
    gained: dict[str, int] = defaultdict(int)
    cleared: dict[str, int] = defaultdict(int)
    for s in summaries:
        for k, v in (s.get("status_gained") or {}).items():
            gained[k] += v
        for k, v in (s.get("status_cleared") or {}).items():
            cleared[k] += v
    return {"gained": dict(gained), "cleared": dict(cleared)}


def analyze_roles(summaries: list[dict], jsonl_samples: list[dict]) -> dict:
    """Correlaciona roles asignados (del step 0 de cada JSONL) con outcomes."""
    # Mapa seed_num → roles (extraído del step 0 del JSONL)
    seed_roles: dict[int, dict] = {}
    for sample in jsonl_samples:
        first = sample.get("first") or {}
        roles = first.get("roles_assigned")
        seed_num = sample.get("seed_num")
        if roles and seed_num is not None:
            seed_roles[seed_num] = roles

    # Mapa seed_num → summary
    seed_summaries: dict[int, dict] = {}
    for s in summaries:
        seed = s.get("seed")
        if seed is not None:
            seed_summaries[int(seed)] = s

    # Contar por rol individual
    role_stats: dict[str, dict] = defaultdict(lambda: {"games": 0, "wins": 0, "rounds": []})
    combo_stats: dict[str, dict] = defaultdict(lambda: {"games": 0, "wins": 0, "rounds": []})

    for seed_num, roles in seed_roles.items():
        s = seed_summaries.get(seed_num)
        if s is None:
            continue
        won = s.get("outcome") == "WIN"
        rnd = s.get("round") or 0
        combo = "+".join(sorted(set(roles.values())))

        combo_stats[combo]["games"] += 1
        combo_stats[combo]["rounds"].append(rnd)
        if won:
            combo_stats[combo]["wins"] += 1

        for role in set(roles.values()):
            role_stats[role]["games"] += 1
            role_stats[role]["rounds"].append(rnd)
            if won:
                role_stats[role]["wins"] += 1

    # Calcular win rates
    def _finalize(d: dict) -> dict:
        result = {}
        for k, v in d.items():
            g = v["games"]
            w = v["wins"]
            result[k] = {
                "games": g,
                "wins": w,
                "win_rate": round(w / g, 3) if g else None,
                "avg_rounds": round(mean(v["rounds"]), 1) if v["rounds"] else None,
            }
        return result

    return {
        "by_role": _finalize(role_stats),
        "by_combo": _finalize(combo_stats),
    }


def analyze_tension(jsonl_samples: list[dict]) -> dict:
    """Agrupa T_post por ronda a partir de KING_ENDROUND records."""
    by_round: dict[int, list[float]] = defaultdict(list)
    for sample in jsonl_samples:
        for rec in sample.get("king_endround", []):
            rnd = rec.get("round")
            t = rec.get("T_post")
            if rnd is not None and t is not None:
                by_round[rnd].append(t)

    result = {}
    for rnd in sorted(by_round):
        vals = by_round[rnd]
        result[rnd] = round(mean(vals), 3)
    return result


def build_per_seed_table(summaries: list[dict], jsonl_samples: list[dict]) -> list[dict]:
    """Una fila por seed con métricas clave."""
    # mapa seed_num → jsonl sample para sacar T_final
    sample_by_seed: dict[int, dict] = {}
    for s in jsonl_samples:
        num = s.get("seed_num")
        if num is not None:
            sample_by_seed[num] = s

    rows = []
    for s in summaries:
        seed = s.get("seed")
        sample = sample_by_seed.get(int(seed) if seed is not None else -1, {})
        last = sample.get("last") or {}

        sac = s.get("sacrifice", {}) or {}
        special_total = sum((s.get("special_actions") or {}).values())

        rows.append({
            "seed": seed,
            "outcome": s.get("outcome") or ("INCOMPLETE" if not s.get("game_over") else "UNKNOWN"),
            "defeat_cause": classify_defeat(s),
            "rounds": s.get("round"),
            "steps": s.get("steps"),
            "keys_end": s.get("keys_in_hand", 0),
            "keys_destroyed": s.get("keys_destroyed_total", 0),
            "sacrifice_count": sac.get("sacrifice", 0),
            "accept_count": sac.get("accept", 0),
            "special_actions_total": special_total,
            "T_final": last.get("T_post"),
        })
    return rows


# ---------------------------------------------------------------------------
# Render markdown
# ---------------------------------------------------------------------------

def _pct(n: int, total: int) -> str:
    return f"{n} ({100*n//total if total else 0}%)"


def _stat_str(d: dict) -> str:
    if d.get("mean") is None:
        return "—"
    s = f"{d['mean']}"
    if d.get("std"):
        s += f" ± {d['std']}"
    s += f"  [min {d['min']} – max {d['max']}]"
    return s


def render_markdown(data: dict) -> str:
    lines = []
    a = lines.append

    # Header
    a(f"# Reporte consolidado — {data['meta']['runs_dir']}")
    a(f"Generado: {data['meta']['generated_at']}  |  Seeds: {data['outcomes']['n']}  |  Política: {data['meta'].get('policy', '—')}")
    a("")

    # A. Overview
    a("## A. Overview")
    oc = data["outcomes"]
    n = oc["n"]
    a(f"- **Win rate**: {oc['win_rate']*100:.1f}%  ({oc['wins']}/{n})")
    a("")
    a("**Distribución de outcomes:**")
    a("")
    a("| Outcome | Count | % |")
    a("|---|:---:|:---:|")
    for outcome, cnt in sorted(oc["outcome_counts"].items(), key=lambda x: -x[1]):
        a(f"| `{outcome}` | {cnt} | {100*cnt//n}% |")
    a("")
    dur = data["duration"]
    a(f"**Duración** — Rondas: {_stat_str(dur['rounds'])}  |  Steps: {_stat_str(dur['steps'])}")
    a("")

    # B. Balance
    a("## B. Balance del juego")
    a("")
    dc = oc["defeat_causes"]
    a("**Causas de derrota:**")
    a("")
    a("| Causa | Count |")
    a("|---|:---:|")
    for cause, cnt in sorted(dc.items(), key=lambda x: -x[1]):
        a(f"| {cause} | {cnt} |")
    a("")

    keys = data["keys"]
    a("**Economía de llaves:**")
    a(f"- Keys en mano al final: {_stat_str(keys['keys_in_hand_end'])}")
    a(f"- Keys destruidas por run: {_stat_str(keys['keys_destroyed'])}")
    a("")

    sac = data["sacrifice"]
    a("**Sacrificios:**")
    a(f"- Oportunidades: {sac['opportunities']}  |  Sacrificios: {sac['sacrifice']}  |  Acepta: {sac['accept']}")
    if sac["sac_rate"] is not None:
        a(f"- Tasa de sacrificio: {sac['sac_rate']*100:.1f}%")
    a(f"- Sac con llaves: {sac['sac_with_keys']}  |  Acepta con llaves: {sac['acc_with_keys']}")
    if sac["sacrifice_modes"]:
        modes_str = "  ".join(f"`{k}`: {v}" for k, v in sorted(sac["sacrifice_modes"].items(), key=lambda x: -x[1]))
        a(f"- Modos: {modes_str}")
    a("")

    tension = data["tension_by_round"]
    if tension:
        a("**Tensión T promedio por ronda** (KING_ENDROUND):")
        a("")
        a("| Ronda | T_avg |")
        a("|:---:|:---:|")
        for rnd, t in sorted(tension.items()):
            bar = "█" * int(t * 20)
            a(f"| {rnd} | {t:.3f} {bar} |")
        a("")

    # C. Bots
    a("## C. Comportamiento de los bots")
    a("")
    actions = data["actions"]
    if actions["special_actions"]:
        a("**Acciones especiales (total acumulado):**")
        a("")
        a("| Acción | Count |")
        a("|---|:---:|")
        for k, v in sorted(actions["special_actions"].items(), key=lambda x: -x[1]):
            a(f"| `{k}` | {v} |")
        a("")
    if actions["object_actions"]:
        a("**Objetos usados:**")
        a("")
        a("| Objeto | Count |")
        a("|---|:---:|")
        for k, v in sorted(actions["object_actions"].items(), key=lambda x: -x[1]):
            a(f"| `{k}` | {v} |")
        a("")

    statuses = data["statuses"]
    if statuses["gained"]:
        a("**Statuses ganados:**  " + "  ".join(f"`{k}`: {v}" for k, v in sorted(statuses["gained"].items(), key=lambda x: -x[1])))
        a("")

    # D. Roles
    a("## D. Análisis de roles")
    a("")
    roles = data["roles"]
    if roles["by_role"]:
        a("**Por rol individual:**")
        a("")
        a("| Rol | Partidas | Wins | Win rate | Rondas avg |")
        a("|---|:---:|:---:|:---:|:---:|")
        for role, r in sorted(roles["by_role"].items(), key=lambda x: -(x[1]["win_rate"] or 0)):
            wr = f"{r['win_rate']*100:.0f}%" if r["win_rate"] is not None else "—"
            a(f"| {role} | {r['games']} | {r['wins']} | {wr} | {r['avg_rounds'] or '—'} |")
        a("")
    if roles["by_combo"]:
        a("**Por combinación de roles:**")
        a("")
        a("| Combo | Partidas | Wins | Win rate |")
        a("|---|:---:|:---:|:---:|")
        for combo, r in sorted(roles["by_combo"].items(), key=lambda x: -(x[1]["win_rate"] or 0)):
            wr = f"{r['win_rate']*100:.0f}%" if r["win_rate"] is not None else "—"
            a(f"| {combo} | {r['games']} | {r['wins']} | {wr} |")
        a("")

    # E. Tabla por seed
    a("## E. Tabla por seed")
    a("")
    a("| Seed | Outcome | Causa | Rondas | Steps | Keys_end | Keys_dest | Sac | Acc | Special | T_final |")
    a("|:---:|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for row in data["per_seed"]:
        t_final = f"{row['T_final']:.3f}" if row["T_final"] is not None else "—"
        a(f"| {row['seed']} | `{row['outcome']}` | {row['defeat_cause']} | {row['rounds']} | {row['steps']} | {row['keys_end']} | {row['keys_destroyed']} | {row['sacrifice_count']} | {row['accept_count']} | {row['special_actions_total']} | {t_final} |")
    a("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Consolida múltiples runs de Carcosa en un reporte.")
    ap.add_argument("runs_dir", type=Path, help="Directorio con seed*.jsonl y seed*_summary.json")
    ap.add_argument("--out", type=Path, default=None, help="Directorio de output (default: mismo que runs_dir)")
    args = ap.parse_args()

    runs_dir = args.runs_dir.resolve()
    out_dir = (args.out or runs_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Cargando summaries de {runs_dir}...")
    summaries = load_summaries(runs_dir)
    if not summaries:
        print("ERROR: No se encontraron *_summary.json en el directorio.")
        return

    print(f"  {len(summaries)} summaries encontrados.")

    print("Cargando muestras de JSONL...")
    jsonl_samples = load_all_jsonl(runs_dir)
    print(f"  {len(jsonl_samples)} archivos JSONL procesados.")

    # Detectar política del primer summary
    policy = summaries[0].get("policy") if summaries else "—"

    data = {
        "meta": {
            "runs_dir": str(runs_dir),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "policy": policy,
            "n_summaries": len(summaries),
            "n_jsonl": len(jsonl_samples),
        },
        "outcomes": analyze_outcomes(summaries),
        "duration": analyze_duration(summaries),
        "keys": analyze_keys(summaries),
        "sacrifice": analyze_sacrifice(summaries),
        "actions": analyze_actions(summaries),
        "statuses": analyze_statuses(summaries),
        "roles": analyze_roles(summaries, jsonl_samples),
        "tension_by_round": analyze_tension(jsonl_samples),
        "per_seed": build_per_seed_table(summaries, jsonl_samples),
    }

    # Guardar JSON crudo
    json_path = out_dir / "consolidado_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Guardado: {json_path}")

    # Guardar reporte markdown
    md_path = out_dir / "consolidado_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(data))
    print(f"Guardado: {md_path}")

    # Print resumen rápido en consola
    oc = data["outcomes"]
    print(f"\n=== RESUMEN ===")
    print(f"Seeds: {oc['n']}  |  Win rate: {oc['win_rate']*100:.1f}%  |  Política: {policy}")
    for cause, cnt in sorted(oc["defeat_causes"].items(), key=lambda x: -x[1]):
        print(f"  {cause}: {cnt}")


if __name__ == "__main__":
    main()
