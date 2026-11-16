#!/usr/bin/env python3
"""
Vast.ai Automation Manager for FP AI Video Factory.
- Searches cheapest available GPU offer (>= 24GB VRAM, reliable internet)
- Launches instance with ghcr.io/bianobhz/fp-ai-video-factory:latest
- Waits for ComfyUI (/system_stats) to become reachable
- Destroys instance when production queue finishes
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Callable

VAST_API_BASE = "https://console.vast.ai/api/v0"
DEFAULT_IMAGE = "ghcr.io/bianobhz/fp-ai-video-factory:latest"


def _vast_request(method: str, path: str, api_key: str, payload: dict | None = None) -> dict:
    url = f"{VAST_API_BASE}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_cheapest_gpu(api_key: str, min_vram_gb: int = 24, max_dph: float = 0.60) -> dict:
    query = {
        "verified": {"eq": True},
        "rentable": {"eq": True},
        "gpu_ram": {"gte": min_vram_gb * 1024},
        "dph_total": {"lte": max_dph},
        "inet_down": {"gte": 200},
        "order": [["dph_total", "asc"]],
        "type": "on-demand",
        "limit": 10,
    }
    res = _vast_request("POST", "/bundles/", api_key, query)
    offers = res.get("offers", [])
    if not offers:
        raise RuntimeError(f"Nenhuma GPU >= {min_vram_gb}GB encontrada abaixo de ${max_dph}/h.")
    return offers[0]


def launch_instance(
    api_key: str,
    offer_id: int,
    rclone_conf_base64: str,
    image: str = DEFAULT_IMAGE,
    disk_gb: int = 60,
) -> int:
    payload = {
        "client_id": "me",
        "image": image,
        "disk": disk_gb,
        "runtype": "args",
        "env": {
            "RCLONE_CONF_BASE64": rclone_conf_base64,
            "-p 8188:8188": "1",
        },
    }
    res = _vast_request("PUT", f"/asks/{offer_id}/", api_key, payload)
    if not res.get("success") or not res.get("new_contract"):
        raise RuntimeError(f"Falha ao criar instância Vast.ai: {res}")
    return int(res["new_contract"])


def wait_for_comfyui(
    api_key: str,
    instance_id: int,
    log_fn: Callable[[str], None] = print,
    timeout_sec: int = 900,
) -> str:
    start = time.time()
    comfy_url = None
    while time.time() - start < timeout_sec:
        info = _vast_request("GET", f"/instances/{instance_id}/", api_key)
        inst = info.get("instances", info)
        status = inst.get("actual_status") or inst.get("cur_state")
        public_ip = inst.get("public_ipaddr")
        ports = inst.get("ports", {})
        mapped = ports.get("8188/tcp") if isinstance(ports, dict) else None
        host_port = mapped[0].get("HostPort") if isinstance(mapped, list) and mapped else None

        if public_ip and host_port:
            comfy_url = f"http://{public_ip}:{host_port}"
            try:
                with urllib.request.urlopen(f"{comfy_url}/system_stats", timeout=5) as resp:
                    if resp.status == 200:
                        log_fn(f"[vast] ComfyUI online em {comfy_url}!")
                        return comfy_url
            except Exception:
                pass

        log_fn(f"[vast] Aguardando instância {instance_id} (status={status})...")
        time.sleep(10)

    raise TimeoutError(f"Timeout aguardando ComfyUI na instância {instance_id}.")


def destroy_instance(api_key: str, instance_id: int, log_fn: Callable[[str], None] = print) -> None:
    log_fn(f"[vast] Destruindo instância {instance_id} para encerrar cobrança...")
    _vast_request("DELETE", f"/instances/{instance_id}/", api_key)
    log_fn(f"[vast] Instância {instance_id} destruída com sucesso.")
