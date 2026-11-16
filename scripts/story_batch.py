#!/usr/bin/env python3
"""Generate a multi-shot vertical story with ComfyUI, then render one MP4."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
from run_workflow import run_workflow  # noqa: E402


def patch_workflow(
    template: dict, *, prompt: str, negative: str, width: int, height: int,
    length: int, steps: int, cfg: float, seed: int,
) -> dict:
    workflow = json.loads(json.dumps(template))
    sampler = next(
        (node for node in workflow.values()
         if isinstance(node, dict) and node.get("class_type") == "KSampler"),
        None,
    )
    if sampler is None:
        raise RuntimeError("Workflow sem nó KSampler.")
    sampler_inputs = sampler.setdefault("inputs", {})
    sampler_inputs.update(seed=seed, steps=steps, cfg=cfg)
    for key, text in (("positive", prompt), ("negative", negative)):
        ref = sampler_inputs.get(key)
        if not isinstance(ref, list) or str(ref[0]) not in workflow:
            raise RuntimeError(f"Workflow sem referência CLIP para {key}.")
        workflow[str(ref[0])].setdefault("inputs", {})["text"] = text

    latent = next(
        (node for node in workflow.values()
         if isinstance(node, dict) and node.get("class_type") in
         ("EmptyHunyuanLatentVideo", "EmptyWanLatentVideo")),
        None,
    )
    if latent is None:
        raise RuntimeError("Workflow sem nó de vídeo latente compatível.")
    latent["inputs"].update(width=width, height=height, length=length)
    return workflow


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera tomadas em sequência e monta uma história vertical em MP4."
    )
    parser.add_argument("story", type=Path, help="JSON com prompts e duração da história.")
    parser.add_argument(
        "--workflow", type=Path,
        default=REPO_ROOT / "workflows" / "wan21_t2v_vertical_api.json",
    )
    parser.add_argument("--server", required=True, help="Endpoint público do ComfyUI na Vast.ai.")
    parser.add_argument("--output", type=Path, help="Destino do MP4 final.")
    parser.add_argument("--audio", type=Path, help="Trilha opcional com licença de publicação.")
    parser.add_argument("--nvenc", action="store_true", help="Codificar com NVENC local.")
    parser.add_argument("--crf", type=int, default=18)
    args = parser.parse_args()

    if not args.story.is_file() or not args.workflow.is_file():
        parser.error("Story JSON ou workflow não encontrado.")
    if args.audio and not args.audio.is_file():
        parser.error("Arquivo de áudio não encontrado.")

    story = json.loads(args.story.read_text(encoding="utf-8"))
    shots = story.get("shots", [])
    if not shots:
        parser.error("A história precisa ter ao menos uma tomada.")
    length = int(story.get("frames_per_scene", 81))
    fps = int(story.get("fps", 16))
    width = int(story.get("width", 480))
    height = int(story.get("height", 832))
    steps = int(story.get("steps", 30))
    cfg = float(story.get("cfg", 6))
    duration = float(story.get("duration_seconds", len(shots) * length / fps))
    negative = story.get("negative_prompt", "")

    run_id = uuid.uuid4().hex[:12]
    work_dir = REPO_ROOT / "outputs" / "raw" / f"story-{run_id}"
    frame_dir = work_dir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    final_dir = REPO_ROOT / "outputs" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    output = args.output or final_dir / f"{args.story.stem}-{run_id}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)

    template = json.loads(args.workflow.read_text(encoding="utf-8"))
    next_frame = 1
    for shot_index, shot in enumerate(shots, start=1):
        name = shot.get("name", f"cena-{shot_index:02d}")
        prompt = (shot.get("prompt") or "").strip()
        if not prompt:
            raise RuntimeError(f"Prompt vazio na tomada {name}.")
        patched = patch_workflow(
            template,
            prompt=prompt,
            negative=negative,
            width=width,
            height=height,
            length=length,
            steps=steps,
            cfg=cfg,
            seed=uuid.uuid4().int % (2**48 - 1) + 1,
        )
        workflow_path = work_dir / f"workflow-{shot_index:02d}.json"
        workflow_path.write_text(json.dumps(patched, ensure_ascii=False), encoding="utf-8")
        print(f"[story] Cena {shot_index}/{len(shots)}: {name}", flush=True)
        generated = run_workflow(
            args.server,
            workflow_path,
            work_dir / f"scene-{shot_index:02d}",
        )
        frames = sorted(p for p in generated if p.suffix.lower() == ".png")
        if not frames:
            raise RuntimeError(f"A tomada {name} não retornou frames.")
        for frame in frames:
            target = frame_dir / f"frame_{next_frame:05d}_.png"
            shutil.copy2(frame, target)
            next_frame += 1
        print(f"[story] {len(frames)} frames guardados para {name}.", flush=True)

    intermediate = work_dir / "story-intermediate.mp4"
    frame_limit = round(duration * fps)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-y", "-framerate", str(fps),
            "-i", str(frame_dir / "frame_%05d_.png"),
            "-frames:v", str(frame_limit), "-c:v", "libx264",
            "-pix_fmt", "yuv420p", str(intermediate),
        ],
        check=True,
    )

    command = [
        sys.executable, str(SCRIPT_DIR / "postprocess.py"), str(intermediate),
        "--output", str(output), "--crf", str(args.crf),
    ]
    subtitle_name = story.get("subtitles")
    if subtitle_name:
        subtitle_path = args.story.parent / subtitle_name
        if not subtitle_path.is_file():
            raise RuntimeError(f"Legenda não encontrada: {subtitle_path}")
        command.extend(["--subtitles", str(subtitle_path)])
    if args.audio:
        command.extend(["--audio", str(args.audio)])
    if args.nvenc:
        command.append("--nvenc")
    subprocess.run(command, check=True)
    print(f"[story] História pronta: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
