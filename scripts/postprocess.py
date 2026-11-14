#!/usr/bin/env python3
"""
Post-production script for FP AI Video Factory.
Converts raw ComfyUI video outputs into 9:16 (1080x1920) vertical shorts
with optional background audio and burned-in SRT subtitles.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_ffmpeg(
    input_video: Path,
    output_video: Path,
    audio_file: Path | None = None,
    subtitles_file: Path | None = None,
    use_nvenc: bool = False,
    crf: int = 18,
) -> None:
    vf_filters = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
        "fps=30",
    ]

    if subtitles_file is not None:
        escaped_subs = str(subtitles_file).replace("\\", "/").replace(":", "\\:")
        vf_filters.append(
            f"subtitles='{escaped_subs}':force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=60'"
        )

    cmd = ["ffmpeg", "-y", "-i", str(input_video)]

    if audio_file is not None:
        cmd.extend(["-i", str(audio_file)])

    cmd.extend(["-vf", ",".join(vf_filters)])

    if use_nvenc:
        cmd.extend(["-c:v", "h264_nvenc", "-preset", "p5", "-cq", str(crf)])
    else:
        cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", str(crf)])

    cmd.extend(["-pix_fmt", "yuv420p"])

    if audio_file is not None:
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"])
    else:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

    cmd.append(str(output_video))

    print(f"[postprocess] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print(f"[postprocess] Saved: {output_video}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render 9:16 vertical short from raw AI video.")
    parser.add_argument("input", type=Path, help="Path to raw input video")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Path to final output video")
    parser.add_argument("-a", "--audio", type=Path, default=None, help="Optional audio/music file")
    parser.add_argument("-s", "--subtitles", type=Path, default=None, help="Optional .srt subtitles file")
    parser.add_argument("--nvenc", action="store_true", help="Use NVIDIA h264_nvenc (GTX 1050 Ti)")
    parser.add_argument("--crf", type=int, default=18, help="Quality factor (lower = better, default 18)")

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        input_video=args.input,
        output_video=args.output,
        audio_file=args.audio,
        subtitles_file=args.subtitles,
        use_nvenc=args.nvenc,
        crf=args.crf,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
