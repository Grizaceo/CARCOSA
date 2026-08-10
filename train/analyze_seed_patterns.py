"""
Análisis de patrones de setup en las seeds nunca-ganadas de CARCOSA.
=====================================================================

Vía (1) del cierre 2026-08-05: ¿hay estructura COMÚN en las 226/300 seeds
que NINGÚN modelo ha ganado? Si el setup (distribución de keys, habitaciones
especiales, topología) discrimina ganable vs perdible, el problema es
modificable ajustando el setup — no el bot.

Tesis:
  - Si un clasificador simple (árbol profundidad<=3) separa WIN de LOSE con
    AUC alta usando SOLO features del setup (que se conocen ANTES de jugar),
    entonces el setup condena/regala seeds → vía (5) rediseño tiene fundamento.
  - Si el AUC es ~0.5, el setup NO explica la ganabilidad → el problema es
    estrategia/política, no setup.

Además cruza el tipo de derrota (SANITY vs KEYS) con la estructura de keys
para detectar seeds "condenadas por diseño" (keys enterradas al fondo de los
decks, keys inalcanzables por topología, etc.)

Uso:
    python3 train/analyze_seed_patterns.py [--out reports/seed_patterns_<ts>.json]

Dependencias: solo stdlib + numpy + (sklearn opcional para el árbol).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.config import Config
from sim.runner import make_smoke_state

# ---------------------------------------------------------------------------
# Seeds ganadas por algo CONFIABLE (post action_masks fix) + gap documentado
# ---------------------------------------------------------------------------
REPORTS_CONFIABLES = [
    "reports/20260804_223607_committee_fix_300/benchmark_summary.json",
    "reports/20260805_171500_committee_v6_300/benchmark_summary.json",
    "reports/20260805_172656_committee_v6_300/benchmark_summary.json",
    "reports/20260805_174243_existence_correct_masks/benchmark_summary.json",
]
GAP_DOCUMENTADO = {70, 112, 298}  # best_evolved raw net, no reproducibles en committee


def load_confiable_wins(repo_root: Path) -> set[int]:
    wins: set[int] = set()
    for f in REPORTS_CONFIABLES:
        p = repo_root / f
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        for policy, s in d.get("summary", {}).items():
            wins.update(int(w) for w in (s.get("win_seeds") or []))
    return wins


# ---------------------------------------------------------------------------
# Features del setup (todo determinista por seed, ~6000 seeds/s)
# ---------------------------------------------------------------------------
def setup_features(state) -> dict:
    """Extrae features del setup que se conocen ANTES de jugar."""
    feats: dict = {}
    cfg = Config()

    # --- Habitaciones especiales ---
    sel = state.flags.get("SPECIAL_ROOMS_SELECTED", [])
    loc = state.flags.get("SPECIAL_ROOM_LOCATIONS", {})
    feats["special_free_count"] = sum(1 for t in sel if t in {"TABERNA", "MOTEMEY", "ARMERIA"})
    feats["special_paid_count"] = sum(1 for t in sel if t not in {"TABERNA", "MOTEMEY", "ARMERIA"})
    feats["special_monasterio"] = 1 if "MONASTERIO_LOCURA" in sel else 0
    feats["special_motemey"] = 1 if "MOTEMEY" in sel else 0
    feats["special_taberna"] = 1 if "TABERNA" in sel else 0
    feats["special_armeria"] = 1 if "ARMERIA" in sel else 0
    feats["special_puertas"] = 1 if "PUERTAS_AMARILLO" in sel else 0
    feats["special_camara"] = 1 if "CAMARA_LETAL" in sel else 0
    feats["special_salon"] = 1 if "SALON_BELLEZA" in sel else 0
    # posición media de las especiales en la cadena R1..R4 (1=pegada al pasillo)
    pos_list = []
    for t, floors in loc.items():
        for f, r in floors.items():
            pos_list.append(r)
    feats["special_mean_pos"] = float(np.mean(pos_list)) if pos_list else 0.0
    feats["special_on_R1_count"] = sum(1 for p in pos_list if p == 1)
    feats["special_on_R4_count"] = sum(1 for p in pos_list if p == 4)

    # --- Keys en decks de habitaciones ---
    key_positions: dict[int, list[int]] = {1: [], 2: [], 3: []}  # floor -> indices en deck
    key_rooms: dict[int, list[int]] = {1: [], 2: [], 3: []}  # floor -> R index
    for rid, room in state.rooms.items():
        if "_P" in str(rid):
            continue
        floor = int(str(rid).split("_")[0][1])
        rnum = int(str(rid).split("_")[1][1])
        for i, c in enumerate(room.deck.cards):
            if c == "KEY":
                key_positions[floor].append(i)
                key_rooms[floor].append(rnum)

    for f in (1, 2, 3):
        kp = key_positions[f]
        kr = key_rooms[f]
        feats[f"keys_floor{f}"] = len(kp)
        feats[f"key_min_idx_floor{f}"] = min(kp) if kp else None
        feats[f"key_mean_idx_floor{f}"] = float(np.mean(kp)) if kp else None
        feats[f"key_min_room_floor{f}"] = min(kr) if kr else None
        feats[f"key_mean_room_floor{f}"] = float(np.mean(kr)) if kr else None

    all_idx = [i for f in (1, 2, 3) for i in key_positions[f]]
    all_rooms = [r for f in (1, 2, 3) for r in key_rooms[f]]
    feats["keys_total_in_rooms"] = len(all_idx)
    feats["key_min_idx_global"] = min(all_idx) if all_idx else None
    feats["key_mean_idx_global"] = float(np.mean(all_idx)) if all_idx else None
    feats["key_min_room_global"] = min(all_rooms) if all_rooms else None

    # keys "cercanas" (R1-R2, accesibles desde pasillo en 1-2 pasos) vs lejanas (R3-R4)
    feats["keys_near_rooms"] = sum(1 for r in all_rooms if r <= 2)
    feats["keys_far_rooms"] = sum(1 for r in all_rooms if r > 2)
    # keys en el mismo piso del Umbral (F2)
    feats["keys_floor2_ratio"] = len(key_positions[2]) / max(1, len(all_idx))

    # --- Key de Motemey ---
    m_keys = [i for i, c in enumerate(state.motemey_deck.cards) if c == "KEY"]
    feats["motemey_key_idx"] = m_keys[0] if m_keys else None  # None si no hay key (bug)

    # --- Deck global: primera key por piso (índice más temprano jugable) ---
    first_keys = [min(kp) for kp in key_positions.values() if kp]
    feats["earliest_key_any_floor"] = min(first_keys) if first_keys else None
    feats["all_floors_have_early_key"] = (
        1 if all(min(kp) <= 4 for kp in key_positions.values() if kp) else 0
    )

    # --- Métricas compuestas ---
    # "profundidad media de key" normalizada (0-1): qué tan enterradas están
    feats["key_burial"] = float(np.mean([i / 8.0 for i in all_idx])) if all_idx else 0.0
    # ¿algún piso sin ninguna key en el deck? (debería ser raro: 6 keys en 12 rooms)
    feats["any_floor_without_key"] = 1 if any(len(v) == 0 for v in key_positions.values()) else 0
    # ¿hay key en la posición 0 de algún piso? (win express si el bot SEARCHa)
    feats["any_key_at_idx0"] = 1 if any(0 in v for v in key_positions.values()) else 0

    return feats


def features_for_seed(seed: int, cfg: Config | None = None) -> dict:
    state = make_smoke_state(seed=seed, cfg=cfg or Config())
    return setup_features(state)


# ---------------------------------------------------------------------------
# Clasificación y reporte
# ---------------------------------------------------------------------------
def _num(rows: list[dict], key: str) -> np.ndarray:
    return np.array([r[key] for r in rows if r[key] is not None], dtype=float)


def _mann_whitney_u(a: np.ndarray, b: np.ndarray) -> float:
    """p-value aproximado de Mann-Whitney U (normal)."""
    if len(a) < 3 or len(b) < 3:
        return 1.0
    a, b = np.sort(a), np.sort(b)
    n1, n2 = len(a), len(b)
    # U = suma de rangos de a
    ranks = np.concatenate([a, b])
    order = np.argsort(np.argsort(ranks))  # ranks 0-based con ties promediados no exacto
    ra = np.sum(order[:n1]) + n1
    u = ra - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2
    sigma = np.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if sigma == 0:
        return 1.0
    z = (u - mu) / sigma
    # p-value two-sided
    p = 2 * (1 - _normal_cdf(abs(z)))
    return float(p)


def _normal_cdf(x: float) -> float:
    return 0.5 * (1 + _erf(x / np.sqrt(2)))


def _erf(x: float) -> float:
    # Abramowitz-Stegun
    sign = 1 if x >= 0 else -1
    x = abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return sign * y


def build_dataset(seeds: range, win_set: set[int]) -> tuple[list[dict], np.ndarray]:
    rows = []
    y = []
    for s in seeds:
        f = features_for_seed(s)
        f["seed"] = s
        f["win"] = 1 if s in win_set else 0
        rows.append(f)
        y.append(f["win"])
    return rows, np.array(y)


def report(rows: list[dict], y: np.ndarray, out_path: Path) -> None:
    n_win = int(y.sum())
    n_lose = len(y) - n_win
    win_rows = [r for r in rows if r["win"] == 1]
    lose_rows = [r for r in rows if r["win"] == 0]

    lines = []
    lines.append("=" * 78)
    lines.append("ANÁLISIS DE PATRONES DE SETUP — seeds nunca-ganadas")
    lines.append(f"Seeds: {len(rows)} | WIN (confiable+gap): {n_win} | LOSE (nunca ganada): {n_lose}")
    lines.append("=" * 78)

    # Features continuas: media WIN vs LOSE + p-value MWU
    numeric_keys = [k for k in rows[0] if isinstance(rows[0][k], (int, float)) and k not in ("seed", "win")]
    lines.append("")
    lines.append("FEATURES CONTINUAS — media WIN vs LOSE (Mann-Whitney U)")
    lines.append(f"{'feature':<28}{'WIN':>10}{'LOSE':>10}{'p-value':>10}  sig")
    results = []
    for k in sorted(numeric_keys):
        a = _num(win_rows, k)
        b = _num(lose_rows, k)
        if len(a) == 0 or len(b) == 0:
            continue
        p = _mann_whitney_u(a, b)
        sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else ""))
        results.append((k, a.mean(), b.mean(), p, sig))
        lines.append(f"{k:<28}{a.mean():>10.3f}{b.mean():>10.3f}{p:>10.4f}  {sig}")
    lines.append("")

    # Correlación con win (point-biserial aproximado por MWU ya hecho; ordenar por p)
    results.sort(key=lambda t: t[3])
    top = [r for r in results if r[4]]
    lines.append(f"FEATURES CON DIFERENCIA SIGNIFICATIVA (p<0.05): {len(top)}")
    for k, mw, ml, p, sig in top[:12]:
        lines.append(f"  {k:<30} WIN={mw:.3f} LOSE={ml:.3f}  p={p:.4f} {sig}")

    # --- Análisis de árbol simple (si sklearn disponible) ---
    lines.append("")
    lines.append("CLASIFICADOR SETUP->GANABLE (árbol de decisión, prof.<=3)")
    try:
        from sklearn.tree import DecisionTreeClassifier, export_text
        from sklearn.model_selection import cross_val_score
        from sklearn.ensemble import RandomForestClassifier

        X = np.array([[r[k] if r[k] is not None else -1 for k in sorted(numeric_keys)] for r in rows])
        feat_names = sorted(numeric_keys)
        clf = DecisionTreeClassifier(max_depth=3, min_samples_leaf=10, random_state=0)
        aucs = cross_val_score(clf, X, y, cv=5, scoring="roc_auc")
        clf.fit(X, y)
        lines.append(f"  AUC CV (5-fold): {aucs.mean():.3f} ± {aucs.std():.3f}")
        lines.append("  AUC = 0.5 => el setup NO discrimina; AUC > 0.65 => estructura real")
        lines.append("  Árbol:")
        tree_txt = export_text(clf, feature_names=feat_names, max_depth=3)
        for tl in tree_txt.splitlines():
            lines.append("    " + tl)
        # Importancia
        rf = RandomForestClassifier(n_estimators=200, random_state=0, max_depth=4)
        rf.fit(X, y)
        imp = sorted(zip(feat_names, rf.feature_importances_), key=lambda t: -t[1])[:8]
        lines.append("  Top-8 importancia (RandomForest):")
        for fn, im in imp:
            lines.append(f"    {fn:<30} {im:.3f}")
    except ImportError:
        lines.append("  sklearn no disponible — solo estadística no paramétrica")

    # --- Distribución de outcomes GOAL por categoría ---
    lines.append("")
    lines.append("OUTCOMES GOAL por categoría (benchmark v6 confiable)")
    try:
        d = json.loads((Path(__file__).parent.parent / REPORTS_CONFIABLES[2]).read_text())
        outcomes = {}
        for sid, r in d["detail"]["GOAL"].items():
            o = r["outcome"]
            if "LOSE_ALL_MINUS5" in o:
                outcomes[int(sid)] = "SANITY"
            elif "LOSE_KEYS" in o:
                outcomes[int(sid)] = "KEYS"
            elif "WIN" in o:
                outcomes[int(sid)] = "WIN"
            else:
                outcomes[int(sid)] = "OTHER"
        # Cruce con categoría
        from collections import Counter
        cat_of = {r["seed"]: ("WIN" if r["win"] else "LOSE") for r in rows}
        cross = Counter()
        for sid, oc in outcomes.items():
            if sid in cat_of:
                cross[(cat_of[sid], oc)] += 1
        lines.append(f"{'categoría':<12}{'SANITY':>10}{'KEYS':>10}{'WIN':>10}")
        for cat in ("WIN", "LOSE"):
            lines.append(f"{cat:<12}{cross[(cat,'SANITY')]:>10}{cross[(cat,'KEYS')]:>10}{cross[(cat,'WIN')]:>10}")
    except Exception as e:
        lines.append(f"  (no se pudo leer outcomes: {e})")

    text = "\n".join(lines)
    print(text)

    # Guardar JSON con datos crudos para análisis posteriores
    out = {
        "meta": {
            "n_seeds": len(rows),
            "n_win": n_win,
            "n_lose": n_lose,
            "reports_confiables": REPORTS_CONFIABLES,
            "gap_documentado": sorted(GAP_DOCUMENTADO),
        },
        "per_seed": rows,
        "report_text": text,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1, default=str))
    print(f"\n[guardado] {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--seeds", type=int, default=300)
    args = ap.parse_args()

    repo = Path(__file__).parent.parent
    win_set = load_confiable_wins(repo) | GAP_DOCUMENTADO
    print(f"Union confiable: {len(win_set)} seeds | nunca ganadas: {300 - len(win_set)}")

    rows, y = build_dataset(range(args.seeds), win_set)

    out_path = Path(args.out) if args.out else repo / "reports" / f"seed_patterns_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report(rows, y, out_path)


if __name__ == "__main__":
    main()
