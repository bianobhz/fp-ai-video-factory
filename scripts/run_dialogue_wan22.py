#!/usr/bin/env python3
"""
Gera os 3 clipes (5s cada, 720x1280, 81 frames) do diálogo usando Wan 2.2 T2V 14B.
Uso:
  python scripts/run_dialogue_wan22.py --server http://SEU_IP_VAST:8188
"""

import argparse
import copy
import json
import random
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / "workflows" / "wan22_t2v_14b_vertical_api.json"
OUT_DIR = REPO_ROOT / "outputs" / "raw" / "dialogo_teste"

SCENES = [
    {
        "name": "cena1_mulher",
        "prompt": (
            "Candid 35mm film close-up medium shot of a Brazilian woman in her late 20s "
            "sitting in a cozy modern coffee shop, looking directly at someone across the table "
            "and speaking excitedly with natural mouth movement and expressive eyes, "
            "realistic skin pores, natural window daylight, shallow depth of field, handheld camera"
        ),
    },
    {
        "name": "cena2_homem",
        "prompt": (
            "Candid 35mm film close-up medium shot of a Brazilian man in his early 30s "
            "sitting in a cozy modern coffee shop, leaning slightly forward, listening attentively "
            "and speaking back with natural mouth movement and curious expression, "
            "realistic skin texture, warm ambient cafe lighting, shallow depth of field, handheld camera"
        ),
    },
    {
        "name": "cena3_mulher_final",
        "prompt": (
            "Candid 35mm film close-up medium shot of the same Brazilian woman in her late 20s "
            "smiling warmly and speaking with confidence in a cozy modern coffee shop, "
            "natural mouth movement, realistic skin pores and hair strands, "
            "natural window daylight, shallow depth of field, handheld camera"
        ),
    },
]


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=180) as resp, open(dest, "wb") as f:
        while chunk := resp.read(1024 * 1024):
            f.write(chunk)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8188", help="URL do ComfyUI na Vast.ai")
    args = parser.parse_args()

    base_url = args.server.rstrip("/")
    base_wf = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for scene in SCENES:
        wf = copy.deepcopy(base_wf)
        wf["7"]["inputs"]["text"] = scene["prompt"]
        wf["10"]["inputs"]["noise_seed"] = random.randint(1, 2**50)
        wf["13"]["inputs"]["filename_prefix"] = f"fp_factory/{scene['name']}"

        client_id = str(uuid.uuid4())
        print(f"[dialogo] Enviando {scene['name']} para {base_url}...")
        res = post_json(f"{base_url}/prompt", {"prompt": wf, "client_id": client_id})
        prompt_id = res["prompt_id"]

        while True:
            history = get_json(f"{base_url}/history/{prompt_id}")
            if prompt_id in history:
                entry = history[prompt_id]
                if entry.get("status", {}).get("status_str") == "error":
                    raise RuntimeError(f"Erro no ComfyUI ({scene['name']}): {entry.get('status')}")
                outputs = entry.get("outputs", {})
                break
            time.sleep(4.0)

        for _nid, node_out in outputs.items():
            for media_key in ("gifs", "videos", "images"):
                for item in node_out.get(media_key, []):
                    q = urllib.parse.urlencode({
                        "filename": item["filename"],
                        "subfolder": item.get("subfolder", ""),
                        "type": item.get("type", "output"),
                    })
                    dest = OUT_DIR / f"{scene['name']}_{item['filename']}"
                    download_file(f"{base_url}/view?{q}", dest)
                    print(f"[dialogo] Salvo: {dest}")

    print("[dialogo] Concluido! Voce ja pode pausar/matar a instancia Vast.ai.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
