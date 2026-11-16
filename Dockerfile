FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    COMFYUI_DIR=/opt/ComfyUI

# System dependencies: Python, Git, FFmpeg, Rclone, curl, unzip
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    git \
    ffmpeg \
    curl \
    unzip \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install rclone
RUN curl -fsSL https://rclone.org/install.sh | bash

# Upgrade pip and install PyTorch (CUDA 12.4)
RUN python3 -m pip install --upgrade pip && \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Clone ComfyUI
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git ${COMFYUI_DIR} && \
    pip install -r ${COMFYUI_DIR}/requirements.txt

# Install ComfyUI-Manager, VideoHelperSuite and LatentSyncWrapper (Lip-Sync)
RUN git clone --depth 1 https://github.com/ltdrdata/ComfyUI-Manager.git ${COMFYUI_DIR}/custom_nodes/ComfyUI-Manager && \
    if [ -f "${COMFYUI_DIR}/custom_nodes/ComfyUI-Manager/requirements.txt" ]; then \
        pip install -r ${COMFYUI_DIR}/custom_nodes/ComfyUI-Manager/requirements.txt; \
    fi && \
    git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git ${COMFYUI_DIR}/custom_nodes/ComfyUI-VideoHelperSuite && \
    pip install -r ${COMFYUI_DIR}/custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt && \
    git clone --depth 1 https://github.com/ShmuelRonen/ComfyUI-LatentSyncWrapper.git ${COMFYUI_DIR}/custom_nodes/ComfyUI-LatentSyncWrapper && \
    pip install -r ${COMFYUI_DIR}/custom_nodes/ComfyUI-LatentSyncWrapper/requirements.txt

# Copy entrypoint script
COPY start.sh /start.sh
RUN chmod +x /start.sh

WORKDIR ${COMFYUI_DIR}

EXPOSE 8188

ENTRYPOINT ["/start.sh"]
