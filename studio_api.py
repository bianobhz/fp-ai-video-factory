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
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
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


def list_uploads() -> list[dict]:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(UPLOADS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        kind = "image" if ext in (".jpg", ".jpeg", ".png", ".webp") else "audio" if ext in (".mp3", ".wav", ".m4a", ".aac") else "video"
        items.append({
            "name": p.name,
            "url": f"/uploads/{p.name}",
            "kind": kind,
            "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
        })
    return items


def auto_cut_silence(filename: str, log_fn: Callable[[str], None]) -> Path:
    src = (UPLOADS_DIR / filename).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {filename}")
    log_fn(f"[editor] Detectando silêncios em {filename}...")
    proc = subprocess.run(
        ["ffmpeg", "-i", str(src), "-af", "silencedetect=noise=-32dB:d=0.45", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", proc.stderr)]
    dur = _ffprobe_duration(src)

    keep_segments: list[tuple[float, float]] = []
    cursor = 0.0
    for i, s in enumerate(starts):
        if s > cursor + 0.15:
            keep_segments.append((cursor, s))
        cursor = ends[i] if i < len(ends) else dur
    if dur > cursor + 0.15:
        keep_segments.append((cursor, dur))

    out = UPLOADS_DIR / f"cut_{src.stem}_{int(time.time())}.mp4"
    if not keep_segments or len(keep_segments) == 1 and keep_segments[0][1] - keep_segments[0][0] >= dur - 0.2:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-c", "copy", str(out)], check=True)
        return out

    tmp_parts = []
    for idx, (a, b) in enumerate(keep_segments):
        part = TMP_DIR / f"cutpart_{idx}_{int(time.time())}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(src),
             "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", str(part)],
            check=True,
        )
        tmp_parts.append(part)

    clist = TMP_DIR / f"cutlist_{int(time.time())}.txt"
    clist.write_text("\n".join(f"file '{p.as_posix()}'" for p in tmp_parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(clist), "-c", "copy", str(out)], check=True)
    log_fn(f"[editor] Microcortes concluídos: {out.name} ({len(keep_segments)} trechos mantidos)")
    return out


def render_local_project(project: dict, log_fn: Callable[[str], None]) -> Path:
    fmt = project.get("format", "9:16")
    w, h = (1080, 1920) if fmt == "9:16" else (1920, 1080) if fmt == "16:9" else (1080, 1080)
    scenes = project.get("scenes") or []
    if not scenes:
        raise ValueError("Nenhuma cena na Timeline para exportar.")

    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", project.get("title") or f"local_{int(time.time())}").strip("_")
    work_dir = TMP_DIR / f"render_{slug}_{int(time.time())}"
    work_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []

    for idx, sc in enumerate(scenes, start=1):
        dur = float(sc.get("durationSec") or 3.0)
        media_url = (sc.get("mediaUrl") or "").strip()
        speech = (sc.get("speechPtBr") or "").strip()
        voice = sc.get("voice") or "pt-BR-FranciscaNeural"
        out_clip = work_dir / f"clip_{idx:02d}.mp4"

        src_file: Path | None = None
        if media_url.startswith("/uploads/"):
            src_file = UPLOADS_DIR / media_url.split("/uploads/", 1)[1]
        elif media_url.startswith("/media/"):
            src_file = FINAL_DIR / media_url.split("/media/", 1)[1]

        if not src_file or not src_file.is_file():
            raise FileNotFoundError(f"Cena {idx} ({sc.get('title')}) sem mídia local anexada. Anexe uma foto ou vídeo.")

        audio_in: Path | None = None
        if speech:
            audio_in = work_dir / f"tts_{idx:02d}.mp3"
            synthesize_tts(speech, voice, audio_in)
            dur = max(dur, _ffprobe_duration(audio_in) + 0.2)

        ext = src_file.suffix.lower()
        is_image = ext in (".jpg", ".jpeg", ".png", ".webp")
        frames = int(dur * 30)

        if is_image:
            log_fn(f"[render] Cena {idx}/{len(scenes)}: foto -> vídeo com zoom suave ({dur:.1f}s)...")
            vf = (
                f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},"
                f"zoompan=z='min(zoom+0.0012,1.15)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps=30,format=yuv420p"
            )
            cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", f"{dur:.2f}", "-i", str(src_file)]
            if audio_in:
                cmd += ["-i", str(audio_in), "-vf", vf, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"]
            else:
                cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-vf", vf, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"]
            cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "18", str(out_clip)]
            subprocess.run(cmd, check=True)
        else:
            log_fn(f"[render] Cena {idx}/{len(scenes)}: ajustando vídeo local...")
            vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30,format=yuv420p"
            cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src_file)]
            if audio_in:
                cmd += ["-i", str(audio_in), "-vf", vf, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"]
            else:
                cmd += ["-vf", vf, "-c:a", "aac"]
            cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "18", str(out_clip)]
            subprocess.run(cmd, check=True)

        clips.append(out_clip)

    concat_txt = work_dir / "concat.txt"
    concat_txt.write_text("\n".join(f"file '{c.as_posix()}'" for c in clips), encoding="utf-8")
    merged = work_dir / "merged.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(merged)], check=True)

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    final_out = FINAL_DIR / f"{slug}-local-{int(time.time())}.mp4"
    music_url = (project.get("musicUrl") or "").strip()
    music_vol = float(project.get("musicVolume") or 0.25)

    if music_url.startswith("/uploads/"):
        music_file = UPLOADS_DIR / music_url.split("/uploads/", 1)[1]
        if music_file.is_file():
            log_fn(f"[render] Mixando trilha sonora ({music_file.name})...")
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error", "-i", str(merged), "-stream_loop", "-1", "-i", str(music_file),
                    "-filter_complex", f"[0:a]volume=1.0[a0];[1:a]volume={music_vol:.2f}[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                    "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    str(final_out),
                ],
                check=True,
            )
            log_fn(f"[render] Vídeo local exportado: {final_out.name}")
            return final_out

    merged.replace(final_out)
    log_fn(f"[render] Vídeo local exportado: {final_out.name}")
    return final_out


def call_ai_agent(messages: list[dict], project_state: dict, api_key: str) -> dict:
    """Conversational AI Agent with full Studio v3 tool-calling (Local CapCut + Vast.ai Cloud)."""
    uploads = list_uploads()
    system_msg = {
        "role": "system",
        "content": (
            "Você é o Agente Diretor e Editor do FP AI Video Factory Studio v3. "
            "Você conversa em português do Brasil com o operador e TEM CONTROLE TOTAL da interface (Editor Local estilo CapCut + Estúdio IA Vast.ai). "
            f"Arquivos locais anexados em outputs/uploads/: {json.dumps(uploads, ensure_ascii=False)}\n"
            f"Estado atual do projeto:\n{json.dumps(project_state, ensure_ascii=False)}\n\n"
            "Use as ferramentas para criar cenas IA, montar Reels com fotos/vídeos locais anexados, colocar música de fundo, "
            "fazer microcortes de silêncio, editar cenas, exportar localmente via FFmpeg ou abrir a produção na Vast.ai."
        ),
    }
    tools = [
        {
            "type": "function",
            "function": {
                "name": "replace_scenes",
                "description": "Cria um novo roteiro substituindo todas as cenas do projeto.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "scenes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "speaker": {"type": "string"},
                                    "voice": {"type": "string", "enum": ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural", "pt-BR-ThalitaNeural"]},
                                    "speech_ptbr": {"type": "string"},
                                    "visual_prompt_en": {"type": "string"},
                                    "durationSec": {"type": "number"},
                                },
                                "required": ["speaker", "voice", "speech_ptbr", "visual_prompt_en"],
                            },
                        },
                    },
                    "required": ["title", "scenes"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_scene",
                "description": "Edita propriedades de uma cena existente pelo número (1, 2, 3...) ou id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scene_index": {"type": "integer", "description": "Número da cena começando em 1"},
                        "speechPtBr": {"type": "string"},
                        "visualPromptEn": {"type": "string"},
                        "voice": {"type": "string"},
                        "durationSec": {"type": "number"},
                        "lipSyncEnabled": {"type": "boolean"},
                    },
                    "required": ["scene_index"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "set_project_settings",
                "description": "Altera configurações globais do projeto (título, formato, legendas).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "format": {"type": "string", "enum": ["9:16", "16:9", "1:1"]},
                        "subtitlesEnabled": {"type": "boolean"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "save_to_queue",
                "description": "Salva o projeto atual na fila de produção offline.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "open_produce_modal",
                "description": "Abre o Modal de Autorização da Vast.ai mostrando a GPU mais barata e o preço para o usuário autorizar.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "add_local_media_scenes",
                "description": "Monta cenas na Timeline usando fotos ou vídeos já anexados em outputs/uploads/ (ex: Reels de fotos).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "filenames": {"type": "array", "items": {"type": "string"}},
                        "durationSec": {"type": "number", "description": "Duração de cada foto/cena em segundos (ex: 2.5)"},
                        "replace": {"type": "boolean", "description": "Se true, substitui a timeline atual"},
                    },
                    "required": ["filenames"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "set_music",
                "description": "Define uma música de fundo anexada em outputs/uploads/ na faixa Música da Timeline.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "volume": {"type": "number", "description": "Volume de 0.0 a 1.0 (ex: 0.25)"},
                    },
                    "required": ["filename"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "auto_cut_video",
                "description": "Executa microcortes automáticos via FFmpeg removendo silêncios de um vídeo narrado anexado.",
                "parameters": {
                    "type": "object",
                    "properties": {"filename": {"type": "string"}},
                    "required": ["filename"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "render_local_video",
                "description": "Exporta/renderiza o projeto atual localmente usando FFmpeg (custo zero de nuvem).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]
    payload = {
        "model": "gpt-4o-mini",
        "messages": [system_msg, *messages],
        "tools": tools,
        "tool_choice": "auto",
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    msg = data["choices"][0]["message"]
    actions = []
    for tc in msg.get("tool_calls") or []:
        fn = tc["function"]["name"]
        args = json.loads(tc["function"].get("arguments") or "{}")
        actions.append({"name": fn, "args": args})

    reply = msg.get("content") or ("Ação executada na interface!" if actions else "Pronto!")
    return {"reply": reply, "actions": actions}


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
