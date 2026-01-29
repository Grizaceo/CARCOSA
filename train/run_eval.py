import json
import sys
from pathlib import Path

# Allow importing package modules when executed as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from train.evaluate import Config, NeuralNetworkPlayerPolicy, evaluate_policy, print_results


def main():
    model_path = Path("models_bc/bc_mlp_all_best.pt")
    if not model_path.exists():
        print(f"Modelo no encontrado: {model_path}")
        return

    cfg = Config()
    policy = NeuralNetworkPlayerPolicy(str(model_path), cfg=cfg, device="cpu", temperature=1.0)
    results = evaluate_policy(policy, f"NN:{model_path.stem}", episodes=20, cfg=cfg)
    print_results(results)

    out_path = Path("runs/eval_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)

    print(f"Resultados guardados en: {out_path}")


if __name__ == "__main__":
    main()
