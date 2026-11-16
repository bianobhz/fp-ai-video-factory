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
from urllib.parse import parse_qs, unquote, urlparse

import studio_api

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

    studio_api.patch_workflow_nodes(data, params)

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


def run_queue_thread(server_url: str) -> None:
    try:
        queue = studio_api.load_queue()
        if not queue:
            raise ValueError("A fila de produção está vazia.")
        last_name = None
        for idx, proj in enumerate(list(queue), start=1):
            JOBS.append_log(f"[fila] Processando item {idx}/{len(queue)}: {proj.get('title', 'sem_titulo')}")
            out_path = studio_api.build_dialogue_project(proj, server_url, JOBS.append_log)
            last_name = out_path.name
            remaining = [item for item in studio_api.load_queue() if item.get("id") != proj.get("id")]
            studio_api.save_queue(remaining)

        with JOBS.lock:
            JOBS.status = "done"
            if last_name:
                JOBS.last_video = f"/media/{last_name}"
        JOBS.append_log("[fila] Todos os projetos da fila foram concluídos!")
    except Exception as exc:
        with JOBS.lock:
            JOBS.status = "error"
            JOBS.error_message = str(exc)
        JOBS.append_log(f"[fila] ERRO: {exc}")


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
            self.send_json(studio_api.extract_workflow_meta(wf))
            return

        if path == "/api/queue":
            self.send_json({"items": studio_api.load_queue()})
            return

        if path == "/api/comfy-queue":
            qs = parse_qs(parsed.query)
            server = (qs.get("server", [""])[0] or "").strip().rstrip("/")
            if not server:
                self.send_json({"ok": False, "running": 0, "pending": 0})
                return
            try:
                with urllib.request.urlopen(f"{server}/queue", timeout=5) as resp:
                    qdata = json.loads(resp.read().decode("utf-8"))
                self.send_json({
                    "ok": True,
                    "running": len(qdata.get("queue_running", [])),
                    "pending": len(qdata.get("queue_pending", [])),
                })
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "running": 0, "pending": 0})
            return

        if path.startswith("/tmp-media/"):
            filename = unquote(path[len("/tmp-media/"):])
            file_path = (TMP_DIR / filename).resolve()
            if file_path.parent != TMP_DIR.resolve() or not file_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Temp media not found")
                return
            mime, _ = mimetypes.guess_type(str(file_path))
            data = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime or "audio/mpeg")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
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

        if path == "/api/tts-preview":
            body = self.read_json()
            text = (body.get("text") or "").strip()
            voice = body.get("voice") or "pt-BR-FranciscaNeural"
            if not text:
                self.send_json({"ok": False, "error": "Texto vazio."}, status=400)
                return
            try:
                fname = f"tts_{int(time.time() * 1000)}.mp3"
                studio_api.synthesize_tts(text, voice, TMP_DIR / fname)
                self.send_json({"ok": True, "url": f"/tmp-media/{fname}"})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return

        if path == "/api/ai-copilot":
            body = self.read_json()
            goal = (body.get("goal") or "").strip()
            provider = body.get("provider") or "gemini"
            api_key = (body.get("api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
            if not goal:
                self.send_json({"ok": False, "error": "Descreva o vídeo que você quer criar."}, status=400)
                return
            if not api_key:
                self.send_json({"ok": False, "error": "Informe sua chave da API (Gemini ou OpenAI)."}, status=400)
                return
            try:
                plan = studio_api.call_ai_copilot(goal, api_key, provider)
                self.send_json({"ok": True, "plan": plan})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return

        if path == "/api/queue":
            body = self.read_json()
            items = studio_api.load_queue()
            body["id"] = f"q_{int(time.time() * 1000)}"
            items.append(body)
            studio_api.save_queue(items)
            self.send_json({"ok": True, "items": items})
            return

        if path == "/api/queue/delete":
            body = self.read_json()
            target_id = body.get("id")
            items = [i for i in studio_api.load_queue() if i.get("id") != target_id]
            studio_api.save_queue(items)
            self.send_json({"ok": True, "items": items})
            return

        if path == "/api/queue/run":
            body = self.read_json()
            server = (body.get("server") or "http://127.0.0.1:8188").strip()
            with JOBS.lock:
                if JOBS.status == "running":
                    self.send_json({"ok": False, "error": "Já existe um job em execução."}, status=409)
                    return
                JOBS.status = "running"
                JOBS.logs = ["[fila] Iniciando processamento da fila na Vast.ai..."]
                JOBS.error_message = None
                JOBS.started_at = time.time()
            t = threading.Thread(target=run_queue_thread, args=(server,), daemon=True)
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
