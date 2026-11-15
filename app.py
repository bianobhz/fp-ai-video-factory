#!/usr/bin/env python3
"""
FP AI Video Factory - Local Admin Dashboard Server.
Zero external dependencies (Python standard library only).
Run: python app.py
"""

from __future__ import annotations

import json
import mimetypes
import os
import random
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parent
WEB_DIR = REPO_ROOT / "web"
WORKFLOWS_DIR = REPO_ROOT / "workflows"
OUTPUTS_DIR = REPO_ROOT / "outputs"
FINAL_DIR = OUTPUTS_DIR / "final"
TMP_DIR = OUTPUTS_DIR / "tmp"

HOST = "127.0.0.1"
PORT = int(os.environ.get("FP_ADMIN_PORT", "8080"))


class JobManager:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.status = "idle"  # idle | running | done | error
        self.logs: list[str] = []
        self.last_video: str | None = None
        self.started_at: float | None = None
        self.error_message: str | None = None

    def append_log(self, line: str) -> None:
        with self.lock:
            self.logs.append(line.rstrip("\r\n"))
            if len(self.logs) > 500:
                self.logs = self.logs[-500:]

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "status": self.status,
                "logs": list(self.logs),
                "last_video": self.last_video,
                "started_at": self.started_at,
                "error_message": self.error_message,
            }


JOBS = JobManager()


def list_workflows() -> list[str]:
    if not WORKFLOWS_DIR.exists():
        return []
    return sorted(p.name for p in WORKFLOWS_DIR.glob("*.json") if p.is_file())


def list_final_videos() -> list[dict]:
    if not FINAL_DIR.exists():
        return []
    videos = []
    for p in sorted(FINAL_DIR.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = p.stat()
        videos.append(
            {
                "name": p.name,
                "url": f"/media/{p.name}",
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "mtime": int(stat.st_mtime),
            }
        )
    return videos


def patch_workflow(workflow_path: Path, params: dict) -> Path:
    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pos_prompt = (params.get("positive_prompt") or "").strip()
    neg_prompt = (params.get("negative_prompt") or "").strip()
    seed = params.get("seed")
    steps = params.get("steps")
    cfg = params.get("cfg")
    width = params.get("width")
    height = params.get("height")
    length = params.get("length")

    # Patch KSampler and linked positive/negative CLIPTextEncode nodes if present
    ksampler_node = None
    for node in data.values():
        if isinstance(node, dict) and node.get("class_type") == "KSampler":
            ksampler_node = node
            break

    if ksampler_node:
        inputs = ksampler_node.setdefault("inputs", {})
        if seed is not None and str(seed).strip() != "":
            inputs["seed"] = int(seed)
        else:
            inputs["seed"] = random.randint(1, 2**48 - 1)
        if steps is not None:
            inputs["steps"] = int(steps)
        if cfg is not None:
            inputs["cfg"] = float(cfg)

        pos_ref = inputs.get("positive")
        neg_ref = inputs.get("negative")
        if pos_prompt and isinstance(pos_ref, list) and str(pos_ref[0]) in data:
            data[str(pos_ref[0])].setdefault("inputs", {})["text"] = pos_prompt
        if neg_prompt and isinstance(neg_ref, list) and str(neg_ref[0]) in data:
            data[str(neg_ref[0])].setdefault("inputs", {})["text"] = neg_prompt

    for node in data.values():
        if isinstance(node, dict) and node.get("class_type") in (
            "EmptyHunyuanLatentVideo",
            "EmptyWanLatentVideo",
        ):
            inputs = node.setdefault("inputs", {})
            if width is not None:
                inputs["width"] = int(width)
            if height is not None:
                inputs["height"] = int(height)
            if length is not None:
                inputs["length"] = int(length)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    patched_path = TMP_DIR / f"workflow_{int(time.time())}.json"
    with open(patched_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return patched_path


def run_pipeline_thread(params: dict) -> None:
    try:
        server = (params.get("server") or "http://127.0.0.1:8188").strip()
        workflow_name = params.get("workflow") or "wan21_t2v_vertical_api.json"
        workflow_path = WORKFLOWS_DIR / workflow_name
        if not workflow_path.is_file():
            raise FileNotFoundError(f"Workflow não encontrado: {workflow_name}")

        patched_workflow = patch_workflow(workflow_path, params)
        JOBS.append_log(f"[admin] Workflow preparado: {patched_workflow.name}")

        cmd = [
            sys.executable,
            "-u",
            str(REPO_ROOT / "scripts" / "pipeline.py"),
            "--workflow",
            str(patched_workflow),
            "--server",
            server,
            "--fps",
            str(int(params.get("fps") or 16)),
            "--crf",
            str(int(params.get("crf") or 18)),
        ]
        if params.get("nvenc"):
            cmd.append("--nvenc")
        audio_path = (params.get("audio_path") or "").strip()
        if audio_path:
            cmd.extend(["--audio", audio_path])
        subtitles_path = (params.get("subtitles_path") or "").strip()
        if subtitles_path:
            cmd.extend(["--subtitles", subtitles_path])

        JOBS.append_log(f"[admin] Executando: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        last_finished = None
        for line in proc.stdout:
            JOBS.append_log(line)
            if "[pipeline] Finished:" in line:
                last_finished = Path(line.split("[pipeline] Finished:", 1)[1].strip()).name

        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"pipeline.py encerrou com código {rc}")

        with JOBS.lock:
            JOBS.status = "done"
            if last_finished:
                JOBS.last_video = f"/media/{last_finished}"
            else:
                videos = list_final_videos()
                JOBS.last_video = videos[0]["url"] if videos else None
        JOBS.append_log("[admin] Concluído com sucesso!")
    except Exception as exc:
        with JOBS.lock:
            JOBS.status = "error"
            JOBS.error_message = str(exc)
        JOBS.append_log(f"[admin] ERRO: {exc}")


def run_pull_drive_thread() -> None:
    try:
        raw_dir = OUTPUTS_DIR / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            "rclone",
            "copy",
            "gdrive:IA_Studio/outputs",
            str(raw_dir),
            "--progress",
            "--transfers",
            "4",
            "--checkers",
            "8",
        ]
        JOBS.append_log(f"[admin] Sincronizando Drive: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            JOBS.append_log(line)
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"rclone encerrou com código {rc}")
        with JOBS.lock:
            JOBS.status = "done"
        JOBS.append_log("[admin] Sync do Drive concluído.")
    except Exception as exc:
        with JOBS.lock:
            JOBS.status = "error"
            JOBS.error_message = str(exc)
        JOBS.append_log(f"[admin] ERRO no Drive: {exc}")


class AdminHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            index_file = WEB_DIR / "index.html"
            if not index_file.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "web/index.html not found")
                return
            data = index_file.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/status":
            snap = JOBS.snapshot()
            snap["workflows"] = list_workflows()
            snap["videos"] = list_final_videos()
            self.send_json(snap)
            return

        if path.startswith("/api/workflow/"):
            name = unquote(path[len("/api/workflow/"):])
            wf_path = (WORKFLOWS_DIR / name).resolve()
            if wf_path.parent != WORKFLOWS_DIR.resolve() or not wf_path.is_file():
                self.send_json({"error": "Workflow not found"}, status=404)
                return
            with open(wf_path, "r", encoding="utf-8") as f:
                wf = json.load(f)
            meta = {"positive_prompt": "", "negative_prompt": "", "width": 480, "height": 832, "length": 33, "steps": 30, "cfg": 6}
            for node in wf.values():
                if isinstance(node, dict) and node.get("class_type") == "KSampler":
                    inp = node.get("inputs", {})
                    meta["steps"] = inp.get("steps", 30)
                    meta["cfg"] = inp.get("cfg", 6)
                    pos_ref = inp.get("positive")
                    neg_ref = inp.get("negative")
                    if isinstance(pos_ref, list) and str(pos_ref[0]) in wf:
                        meta["positive_prompt"] = wf[str(pos_ref[0])].get("inputs", {}).get("text", "")
                    if isinstance(neg_ref, list) and str(neg_ref[0]) in wf:
                        meta["negative_prompt"] = wf[str(neg_ref[0])].get("inputs", {}).get("text", "")
                if isinstance(node, dict) and node.get("class_type") in ("EmptyHunyuanLatentVideo", "EmptyWanLatentVideo"):
                    inp = node.get("inputs", {})
                    meta["width"] = inp.get("width", 480)
                    meta["height"] = inp.get("height", 832)
                    meta["length"] = inp.get("length", 33)
            self.send_json(meta)
            return

        if path.startswith("/media/"):
            filename = unquote(path[len("/media/"):])
            file_path = (FINAL_DIR / filename).resolve()
            if file_path.parent != FINAL_DIR.resolve() or not file_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Video not found")
                return
            mime, _ = mimetypes.guess_type(str(file_path))
            size = file_path.stat().st_size
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime or "video/mp4")
            self.send_header("Content-Length", str(size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with open(file_path, "rb") as f:
                while chunk := f.read(1024 * 512):
                    self.wfile.write(chunk)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/test-connection":
            body = self.read_json()
            server = (body.get("server") or "").strip().rstrip("/")
            if not server:
                self.send_json({"ok": False, "error": "Informe a URL do servidor ComfyUI."}, status=400)
                return
            try:
                req = urllib.request.Request(f"{server}/system_stats", method="GET")
                with urllib.request.urlopen(req, timeout=8) as resp:
                    stats = json.loads(resp.read().decode("utf-8"))
                devices = stats.get("devices", [])
                gpu_name = devices[0].get("name", "GPU detectada") if devices else "ComfyUI Online"
                vram_total = devices[0].get("vram_total", 0) if devices else 0
                vram_gb = round(vram_total / (1024**3), 1) if vram_total else None
                self.send_json({"ok": True, "gpu": gpu_name, "vram_gb": vram_gb})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=200)
            return

        if path == "/api/run":
            with JOBS.lock:
                if JOBS.status == "running":
                    self.send_json({"ok": False, "error": "Já existe um job em execução."}, status=409)
                    return
                JOBS.status = "running"
                JOBS.logs = ["[admin] Iniciando pipeline..."]
                JOBS.error_message = None
                JOBS.started_at = time.time()

            params = self.read_json()
            t = threading.Thread(target=run_pipeline_thread, args=(params,), daemon=True)
            t.start()
            self.send_json({"ok": True})
            return

        if path == "/api/pull-drive":
            with JOBS.lock:
                if JOBS.status == "running":
                    self.send_json({"ok": False, "error": "Já existe um job em execução."}, status=409)
                    return
                JOBS.status = "running"
                JOBS.logs = ["[admin] Iniciando sync do Google Drive..."]
                JOBS.error_message = None
                JOBS.started_at = time.time()

            t = threading.Thread(target=run_pull_drive_thread, daemon=True)
            t.start()
            self.send_json({"ok": True})
            return

        self.send_json({"error": "Endpoint desconhecido"}, status=404)


def main() -> int:
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), AdminHandler)
    url = f"http://{HOST}:{PORT}"
    print(f"[FP AI Video Factory] Painel Administrativo rodando em {url}")
    print("Pressione Ctrl+C para encerrar.")
    if os.environ.get("FP_NO_BROWSER") != "1":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[FP AI Video Factory] Encerrando painel.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
