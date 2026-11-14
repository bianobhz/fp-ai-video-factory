#!/usr/bin/env python3
"""
Orchestrator script for FP AI Video Factory.
Submits a ComfyUI API-format workflow JSON to a running ComfyUI instance (e.g., Vast.ai),
waits for completion, and downloads the generated output files locally.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as f:
        while chunk := resp.read(1024 * 1024):
            f.write(chunk)


def run_workflow(server_url: str, workflow_path: Path, output_dir: Path, poll_interval: float = 3.0) -> list[Path]:
    base_url = server_url.rstrip("/")
    client_id = str(uuid.uuid4())

    with open(workflow_path, "r", encoding="utf-8") as f:
        prompt = json.load(f)

    print(f"[orchestrator] Submitting workflow '{workflow_path.name}' to {base_url}...")
    res = post_json(f"{base_url}/prompt", {"prompt": prompt, "client_id": client_id})
    prompt_id = res["prompt_id"]
    print(f"[orchestrator] Queued prompt_id={prompt_id}. Waiting for completion...")

    while True:
        history = get_json(f"{base_url}/history/{prompt_id}")
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI execution failed: {status}")
            outputs = entry.get("outputs", {})
            break
        time.sleep(poll_interval)

    saved_files: list[Path] = []
    for _node_id, node_out in outputs.items():
        for media_key in ("gifs", "videos", "images"):
            for item in node_out.get(media_key, []):
                filename = item["filename"]
                subfolder = item.get("subfolder", "")
                media_type = item.get("type", "output")
                query = urllib.parse.urlencode(
                    {"filename": filename, "subfolder": subfolder, "type": media_type}
                )
                file_url = f"{base_url}/view?{query}"
                dest = output_dir / filename
                print(f"[orchestrator] Downloading {filename} -> {dest}")
                download_file(file_url, dest)
                saved_files.append(dest)

    print(f"[orchestrator] Done. Downloaded {len(saved_files)} file(s).")
    return saved_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a ComfyUI API workflow and download outputs.")
    parser.add_argument("workflow", type=Path, help="Path to ComfyUI API-format workflow JSON")
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:8188",
        help="ComfyUI server URL (default: http://127.0.0.1:8188)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("outputs/raw"),
        help="Directory to save downloaded outputs (default: outputs/raw)",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=3.0,
        help="Polling interval in seconds (default: 3.0)",
    )

    args = parser.parse_args()
    if not args.workflow.exists():
        print(f"Error: workflow file not found: {args.workflow}", file=sys.stderr)
        return 1

    try:
        run_workflow(args.server, args.workflow, args.output_dir, args.poll)
    except urllib.error.URLError as exc:
        print(f"Connection error to {args.server}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
