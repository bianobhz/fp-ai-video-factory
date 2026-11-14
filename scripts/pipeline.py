#!/usr/bin/env python3
"""End-to-end ComfyUI -> frames -> vertical delivery pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
from run_workflow import run_workflow  # noqa: E402


def build_video_from_frames(frames: list[Path], output: Path, fps: int) -> None:
    if not frames:
        raise RuntimeError("ComfyUI completed without returning frame images.")

    # SaveImage names frames with a sortable, zero-padded sequence suffix.
    frames = sorted(frames, key=lambda path: path.name)
    expected = [frames[0].parent / f"frame_{index:05d}_.png" for index in range(1, len(frames) + 1)]
    if frames != expected:
        raise RuntimeError(
            "Unexpected frame filenames. Expected ComfyUI SaveImage names "
            "frame_00001_.png, frame_00002_.png, ..."
        )

    cmd = [
        "ffmpeg", "-hide_banner", "-y", "-framerate", str(fps),
        "-i", str(frames[0].parent / "frame_%05d_.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
    ]
    print("[pipeline] Encoding generated frames into an intermediate video...")
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a ComfyUI video on Vast.ai and render a vertical social-media master."
    )
    parser.add_argument(
        "--workflow", type=Path,
        default=REPO_ROOT / "workflows" / "wan21_t2v_vertical_api.json",
        help="ComfyUI API-format workflow JSON.",
    )
    parser.add_argument("--server", default="http://127.0.0.1:8188", help="ComfyUI/Vast.ai endpoint.")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "outputs")
    parser.add_argument("--audio", type=Path, help="Optional music/audio file.")
    parser.add_argument("--subtitles", type=Path, help="Optional SRT subtitles.")
    parser.add_argument("--fps", type=int, default=16, help="Frame rate emitted by the Wan workflow.")
    parser.add_argument("--nvenc", action="store_true", help="Use h264_nvenc in postprocess.py.")
    parser.add_argument("--crf", type=int, default=18)
    args = parser.parse_args()

    if not args.workflow.is_file():
        parser.error(f"Workflow not found: {args.workflow}")
    if args.fps < 1:
        parser.error("--fps must be positive")
    if args.audio and not args.audio.is_file():
        parser.error(f"Audio file not found: {args.audio}")
    if args.subtitles and not args.subtitles.is_file():
        parser.error(f"Subtitle file not found: {args.subtitles}")

    run_id = uuid.uuid4().hex[:12]
    raw_dir = args.output_dir / "raw" / run_id
    final_path = args.output_dir / "final" / f"fp-video-{run_id}.mp4"
    raw_dir.mkdir(parents=True, exist_ok=True)
    final_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[pipeline] Submitting to {args.server}")
    generated = run_workflow(args.server, args.workflow, raw_dir)
    frames = [path for path in generated if path.suffix.lower() == ".png"]
    intermediate = raw_dir / "wan-intermediate.mp4"
    build_video_from_frames(frames, intermediate, args.fps)

    command = [
        sys.executable, str(SCRIPT_DIR / "postprocess.py"), str(intermediate),
        "--output", str(final_path), "--crf", str(args.crf),
    ]
    if args.audio:
        command.extend(["--audio", str(args.audio)])
    if args.subtitles:
        command.extend(["--subtitles", str(args.subtitles)])
    if args.nvenc:
        command.append("--nvenc")

    print("[pipeline] Applying 9:16, 1080x1920, 30fps post-processing...")
    subprocess.run(command, check=True)
    print(f"[pipeline] Finished: {final_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
