#!/usr/bin/env python3
"""
Studio API helpers for FP AI Video Factory v2:
- Workflow inspection/patching for KSampler & KSamplerAdvanced (Wan 2.2 14B)
- PT-BR Neural TTS preview & synthesis (edge-tts)
- AI Copilot (Gemini / OpenAI via stdlib urllib)
- Offline Production Queue + Multi-scene Dialogue Builder (FFmpeg)
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent
WORKFLOWS_DIR = REPO_ROOT / "workflows"
OUTPUTS_DIR = REPO_ROOT / "outputs"
RAW_DIR = OUTPUTS_DIR / "raw"
FINAL_DIR = OUTPUTS_DIR / "final"
TMP_DIR = OUTPUTS_DIR / "tmp"
QUEUE_FILE = TMP_DIR / "queue.json"


def extract_workflow_meta(wf: dict) -> dict:
    meta = {
        "positive_prompt": "",
        "negative_prompt": "",
        "width": 720,
        "height": 1280,
        "length": 81,
        "steps": 20,
        "cfg": 3.5,
        "sampler_type": "KSampler",
    }
    for node in wf.values():
        if not isinstance(node, dict):
            continue
        ctype = node.get("class_type")
        if ctype in ("KSampler", "KSamplerAdvanced"):
            meta["sampler_type"] = ctype
            inp = node.get("inputs", {})
            if "steps" in inp:
                meta["steps"] = inp.get("steps", meta["steps"])
            if "cfg" in inp:
                meta["cfg"] = inp.get("cfg", meta["cfg"])
            pos_ref = inp.get("positive")
            neg_ref = inp.get("negative")
            if isinstance(pos_ref, list) and str(pos_ref[0]) in wf and not meta["positive_prompt"]:
                meta["positive_prompt"] = wf[str(pos_ref[0])].get("inputs", {}).get("text", "")
            if isinstance(neg_ref, list) and str(neg_ref[0]) in wf and not meta["negative_prompt"]:
                meta["negative_prompt"] = wf[str(neg_ref[0])].get("inputs", {}).get("text", "")
        elif ctype in ("EmptyHunyuanLatentVideo", "EmptyWanLatentVideo"):
            inp = node.get("inputs", {})
            meta["width"] = inp.get("width", meta["width"])
            meta["height"] = inp.get("height", meta["height"])
            meta["length"] = inp.get("length", meta["length"])
    return meta


def patch_workflow_nodes(data: dict, params: dict) -> dict:
    pos_prompt = (params.get("positive_prompt") or "").strip()
    neg_prompt = (params.get("negative_prompt") or "").strip()
    seed = params.get("seed")
    steps = params.get("steps")
    cfg = params.get("cfg")
    width = params.get("width")
    height = params.get("height")
    length = params.get("length")
    prefix = (params.get("filename_prefix") or "").strip()

    chosen_seed = int(seed) if (seed is not None and str(seed).strip() != "") else random.randint(1, 2**48 - 1)
    samplers = [
        node for node in data.values()
        if isinstance(node, dict) and node.get("class_type") in ("KSampler", "KSamplerAdvanced")
    ]
    for node in samplers:
        ctype = node.get("class_type")
        inp = node.setdefault("inputs", {})
        if ctype == "KSampler":
            inp["seed"] = chosen_seed
        else:
            if inp.get("add_noise") == "enable":
                inp["noise_seed"] = chosen_seed
        if steps is not None and str(steps).strip() != "":
            inp["steps"] = int(steps)
        if cfg is not None and str(cfg).strip() != "":
            inp["cfg"] = float(cfg)

        pos_ref = inp.get("positive")
        neg_ref = inp.get("negative")
        if pos_prompt and isinstance(pos_ref, list) and str(pos_ref[0]) in data:
            data[str(pos_ref[0])].setdefault("inputs", {})["text"] = pos_prompt
        if neg_prompt and isinstance(neg_ref, list) and str(neg_ref[0]) in data:
            data[str(neg_ref[0])].setdefault("inputs", {})["text"] = neg_prompt

    for node in data.values():
        if not isinstance(node, dict):
            continue
        ctype = node.get("class_type")
        if ctype in ("EmptyHunyuanLatentVideo", "EmptyWanLatentVideo"):
            inp = node.setdefault("inputs", {})
            if width is not None and str(width).strip() != "":
                inp["width"] = int(width)
            if height is not None and str(height).strip() != "":
                inp["height"] = int(height)
            if length is not None and str(length).strip() != "":
                inp["length"] = int(length)
        elif ctype == "SaveImage" and prefix:
            node.setdefault("inputs", {})["filename_prefix"] = prefix
    return data


def synthesize_tts(text: str, voice: str, dest_path: Path, rate: str = "+0%") -> Path:
    import edge_tts

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    async def _run() -> None:
        comm = edge_tts.Communicate(text.strip(), voice=voice, rate=rate)
        await comm.save(str(dest_path))

    asyncio.run(_run())
    return dest_path


def call_ai_copilot(user_goal: str, api_key: str, provider: str = "gemini") -> dict:
    system_prompt = (
        "You are an AI Video Director for FP AI Video Factory (vertical 9:16 hyper-realistic videos using Wan 2.2 T2V 14B). "
        "Given the user's request in Portuguese, return ONLY a valid JSON object (no markdown fences) with:\n"
        '{\n'
        '  "title": "short_slug_title",\n'
        '  "scenes": [\n'
        '    {\n'
        '      "speaker": "Nome do personagem",\n'
        '      "voice": "pt-BR-FranciscaNeural or pt-BR-AntonioNeural",\n'
        '      "speech_ptbr": "Fala natural em português do Brasil (máx 18 palavras para caber em ~5s)",\n'
        '      "visual_prompt_en": "Candid 35mm film close-up medium shot... hyper-realistic, natural skin pores, shallow depth of field, handheld camera"\n'
        '    }\n'
        '  ]\n'
        '}\n'
        "Generate 2 to 4 scenes depending on the requested duration (each scene is ~5 seconds)."
    )

    if provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_goal},
            ],
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        raw_text = data["choices"][0]["message"]["content"]
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={urllib.parse.quote(api_key)}"
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\nPedido do usuário: {user_goal}"}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


def load_queue() -> list[dict]:
    if not QUEUE_FILE.is_file():
        return []
    try:
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_queue(items: list[dict]) -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def _comfy_post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _comfy_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=180) as resp, open(dest, "wb") as f:
        while chunk := resp.read(1024 * 1024):
            f.write(chunk)


def _ffprobe_duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        text=True,
    ).strip()
    return float(out)


def build_dialogue_project(project: dict, server_url: str, log_fn: Callable[[str], None]) -> Path:
    base_url = server_url.rstrip("/")
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", project.get("title") or f"projeto_{int(time.time())}").strip("_")
    proj_dir = RAW_DIR / f"studio_{slug}_{int(time.time())}"
    proj_dir.mkdir(parents=True, exist_ok=True)

    wf_name = project.get("workflow") or "wan22_t2v_14b_vertical_api.json"
    wf_path = WORKFLOWS_DIR / wf_name
    if not wf_path.is_file():
        raise FileNotFoundError(f"Workflow não encontrado: {wf_name}")
    base_wf = json.loads(wf_path.read_text(encoding="utf-8"))

    scenes = project.get("scenes") or []
    if not scenes:
        raise ValueError("Projeto sem cenas.")

    scene_mp4s: list[Path] = []
    for idx, scene in enumerate(scenes, start=1):
        speech = (scene.get("speech_ptbr") or "").strip()
        voice = scene.get("voice") or "pt-BR-FranciscaNeural"
        prompt = (scene.get("visual_prompt_en") or "").strip()

        audio_path = proj_dir / f"scene_{idx:02d}.mp3"
        if speech:
            log_fn(f"[studio] Gerando áudio PT-BR cena {idx}/{len(scenes)} ({voice})...")
            synthesize_tts(speech, voice, audio_path)

        wf = json.loads(json.dumps(base_wf))
        patch_workflow_nodes(
            wf,
            {
                "positive_prompt": prompt,
                "width": project.get("width", 720),
                "height": project.get("height", 1280),
                "length": project.get("length", 81),
                "filename_prefix": f"fp_studio/{slug}_s{idx:02d}",
            },
        )
        client_id = str(uuid.uuid4())
        log_fn(f"[studio] Enviando cena {idx}/{len(scenes)} para ComfyUI ({base_url})...")
        res = _comfy_post(f"{base_url}/prompt", {"prompt": wf, "client_id": client_id})
        prompt_id = res["prompt_id"]

        while True:
            hist = _comfy_get(f"{base_url}/history/{prompt_id}")
            if prompt_id in hist:
                entry = hist[prompt_id]
                if entry.get("status", {}).get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI erro cena {idx}: {entry.get('status')}")
                outputs = entry.get("outputs", {})
                break
            time.sleep(4.0)

        frames_dir = proj_dir / f"frames_{idx:02d}"
        frames_dir.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []
        for _nid, node_out in outputs.items():
            for media_key in ("gifs", "videos", "images"):
                for f_idx, item in enumerate(node_out.get(media_key, [])):
                    q = urllib.parse.urlencode(
                        {"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")}
                    )
                    ext = Path(item["filename"]).suffix or ".png"
                    dest = frames_dir / f"f_{f_idx:05d}{ext}"
                    _download(f"{base_url}/view?{q}", dest)
                    downloaded.append(dest)

        if not downloaded:
            raise RuntimeError(f"Nenhum frame retornado para cena {idx}.")

        raw_scene_mp4 = proj_dir / f"raw_scene_{idx:02d}.mp4"
        if downloaded[0].suffix.lower() in (".mp4", ".webm", ".gif"):
            raw_scene_mp4 = downloaded[0]
        else:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error", "-framerate", "16",
                    "-i", str(frames_dir / f"f_%05d{downloaded[0].suffix}"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
                    str(raw_scene_mp4),
                ],
                check=True,
            )

        final_scene_mp4 = proj_dir / f"final_scene_{idx:02d}.mp4"
        if audio_path.is_file():
            aud_dur = _ffprobe_duration(audio_path)
            vid_dur = _ffprobe_duration(raw_scene_mp4)
            target_dur = max(aud_dur + 0.25, vid_dur)
            speed = target_dur / vid_dur if vid_dur > 0 else 1.0
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error",
                    "-i", str(raw_scene_mp4), "-i", str(audio_path),
                    "-filter_complex",
                    f"[0:v]setpts={speed:.4f}*PTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30[v]",
                    "-map", "[v]", "-map", "1:a",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                    "-c:a", "aac", "-b:a", "192k", "-shortest",
                    str(final_scene_mp4),
                ],
                check=True,
            )
        else:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error", "-i", str(raw_scene_mp4),
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                    str(final_scene_mp4),
                ],
                check=True,
            )
        scene_mp4s.append(final_scene_mp4)

    concat_list = proj_dir / "concat.txt"
    concat_list.write_text("\n".join(f"file '{p.as_posix()}'" for p in scene_mp4s), encoding="utf-8")

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    out_final = FINAL_DIR / f"{slug}-{int(time.time())}.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
            "-i", str(concat_list), "-c", "copy", str(out_final),
        ],
        check=True,
    )
    log_fn(f"[studio] Vídeo final montado: {out_final.name}")
    return out_final
