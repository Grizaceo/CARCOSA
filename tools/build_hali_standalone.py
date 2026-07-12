"""
tools/build_hali_standalone.py — Empaqueta el motor HALI (web/hali/) en UN solo
archivo HTML autocontenido, reproducible en cualquier máquina sin depender de
nada externo (ni CDNs, ni hosting de terceros).

El archivo resultante:
  · funciona abierto directamente desde el disco (file://) o servido estático;
  · en modo replay no necesita nada más (puede embeber una partida de demo);
  · en modo live habla con el game_server local (uvicorn sim.game_server:app).

Uso:
    # build jugable completo, con la demo embebida
    python3 tools/build_hali_standalone.py \
        --replay web/hali/replays/goal_s4_win.json -o dist/hali_standalone.html

    # build solo-replay (p. ej. para compartir una partida concreta)
    python3 tools/build_hali_standalone.py --no-live \
        --replay runs/mi_partida_replay.json -o dist/mi_partida.html
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HALI = ROOT / "web" / "hali"
JS_ORDER = ["hali-core.js", "hali-art.js", "hali-cards.js", "hali-events.js", "hali-data.js", "hali-main.js"]


def build(out_path: str, replay_path: str | None, no_live: bool, title: str) -> Path:
    css = (HALI / "hali.css").read_text(encoding="utf-8")
    js = "\n\n".join((HALI / "js" / f).read_text(encoding="utf-8") for f in JS_ORDER)

    html = (HALI / "index.html").read_text(encoding="utf-8")
    body = html.split("<body>")[1].split("<script")[0]

    if "</script" in js:
        raise SystemExit("El JS contiene '</script' — inseguro para inline.")

    embed = ""
    if replay_path:
        replay_text = Path(replay_path).read_text(encoding="utf-8")
        json.loads(replay_text)  # validar
        if "</script" in replay_text:
            raise SystemExit("El replay contiene '</script' — inseguro para inline.")
        embed = f"<script>\nwindow.HALI_EMBEDDED_REPLAY = {replay_text};\n</script>\n"

    extra_css = ""
    if no_live:
        # ocultar todo lo que requiere red: solo replay embebido + carga de archivo
        body = re.sub(
            r'<details id="source-panel".*?</details>',
            '''  <details id="source-panel">
    <summary>Fuente</summary>
    <div class="sp-label">replay</div>
    <label class="file-label" for="file-replay">Cargar replay (.json / .jsonl)</label>
    <input type="file" id="file-replay" accept=".json,.jsonl">
    <label style="margin-top:8px; display:block">Build solo-replay: para jugar en vivo usa el build completo junto al game_server local.</label>
  </details>''',
            body, flags=re.S,
        )
        extra_css = "#live-tools, #action-bar { display: none !important; }\n"

    out = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{css}
{extra_css}</style>
</head>
<body>
{body}
{embed}<script>
{js}
</script>
</body>
</html>
"""
    dest = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    print(f"HALI standalone: {dest} ({dest.stat().st_size / 1024:.0f} KB)"
          f"{' · replay embebido' if replay_path else ''}{' · solo-replay' if no_live else ' · jugable'}")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="dist/hali_standalone.html")
    ap.add_argument("--replay", default=None, help="replay JSON destilado a embeber como demo")
    ap.add_argument("--no-live", action="store_true", help="build solo-replay (oculta el lobby live)")
    ap.add_argument("--title", default="HALI · CARCOSA en 2.5D")
    args = ap.parse_args()
    build(args.output, args.replay, args.no_live, args.title)


if __name__ == "__main__":
    main()
