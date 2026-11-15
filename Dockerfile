FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

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

# Pin a matched PyTorch/CUDA stack compatible with comfy-kitchen (torch >= 2.7).
RUN python3 -m pip install --upgrade pip && \
    pip install torch==2.9.1 torchvision==0.24.1 torchaudio==2.9.1 --index-url https://download.pytorch.org/whl/cu128

# Clone ComfyUI
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git ${COMFYUI_DIR} && \
    pip install -r ${COMFYUI_DIR}/requirements.txt

# Install ComfyUI-Manager
RUN git clone --depth 1 https://github.com/ltdrdata/ComfyUI-Manager.git ${COMFYUI_DIR}/custom_nodes/ComfyUI-Manager && \
    if [ -f "${COMFYUI_DIR}/custom_nodes/ComfyUI-Manager/requirements.txt" ]; then \
        pip install -r ${COMFYUI_DIR}/custom_nodes/ComfyUI-Manager/requirements.txt; \
    fi

# Catch custom-op schema incompatibilities during image build, without requiring a GPU.
RUN python3 -c "import torch; import comfy_kitchen; assert tuple(int(v) for v in torch.__version__.split('+')[0].split('.')[:2]) >= (2, 7), torch.__version__; print('Comfy kitchen import OK; torch:', torch.__version__)"

# Copy entrypoint script
COPY start.sh /start.sh
RUN chmod +x /start.sh

WORKDIR ${COMFYUI_DIR}

EXPOSE 8188

ENTRYPOINT ["/start.sh"]
