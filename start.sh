#!/usr/bin/env bash
set -euo pipefail

COMFYUI_DIR="${COMFYUI_DIR:-/opt/ComfyUI}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
DRIVE_MODELS_PATH="${DRIVE_MODELS_PATH:-IA_Studio/models}"
RCLONE_CONFIG_DIR="${HOME}/.config/rclone"
RCLONE_CONFIG_FILE="${RCLONE_CONFIG_DIR}/rclone.conf"

echo "[FP AI Video Factory] Starting container initialization..."

# 1. Decode RCLONE_CONF_BASE64 securely (never echo secrets to logs)
if [ -n "${RCLONE_CONF_BASE64:-}" ]; then
    mkdir -p "${RCLONE_CONFIG_DIR}"
    printf '%s' "${RCLONE_CONF_BASE64}" | base64 -d > "${RCLONE_CONFIG_FILE}"
    chmod 600 "${RCLONE_CONFIG_FILE}"
    echo "[FP AI Video Factory] Rclone configuration loaded."
else
    echo "[FP AI Video Factory] WARNING: RCLONE_CONF_BASE64 is not set. Skipping Google Drive sync."
fi

# 2. Selective model download from Google Drive
# Format of MODELS_TO_DOWNLOAD (comma-separated relative paths under DRIVE_MODELS_PATH):
# Example: "checkpoints/model.safetensors,vae/ae.safetensors,loras/style.safetensors"
# Wan 2.2 T2V 14B is the primary workflow; always include its required files,
# even when an older Vast template still sets MODELS_TO_DOWNLOAD to Wan 2.1.
REQUIRED_MODELS=(
    "diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors"
    "diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors"
    "text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
    "vae/wan_2.1_vae.safetensors"
)
for required_model in "${REQUIRED_MODELS[@]}"; do
    case ",${MODELS_TO_DOWNLOAD:-}," in
        *",${required_model},"*) ;;
        *) MODELS_TO_DOWNLOAD="${MODELS_TO_DOWNLOAD:+${MODELS_TO_DOWNLOAD},}${required_model}" ;;
    esac
done

if [ -f "${RCLONE_CONFIG_FILE}" ] && [ -n "${MODELS_TO_DOWNLOAD:-}" ]; then
    echo "[FP AI Video Factory] Starting selective model download..."
    IFS=',' read -ra MODEL_LIST <<< "${MODELS_TO_DOWNLOAD}"
    for item in "${MODEL_LIST[@]}"; do
        # Trim whitespace
        rel_path="$(echo "${item}" | xargs)"
        if [ -z "${rel_path}" ]; then
            continue
        fi
        src="${RCLONE_REMOTE}:${DRIVE_MODELS_PATH}/${rel_path}"
        dest_dir="${COMFYUI_DIR}/models/$(dirname "${rel_path}")"
        mkdir -p "${dest_dir}"
        echo "[FP AI Video Factory] Downloading ${rel_path}..."
        rclone copy "${src}" "${dest_dir}" --progress --transfers 4 --checkers 8
    done
    echo "[FP AI Video Factory] Selective model download complete."
else
    echo "[FP AI Video Factory] No MODELS_TO_DOWNLOAD specified or rclone not configured. Skipping downloads."
fi

# 3. Start ComfyUI
echo "[FP AI Video Factory] Launching ComfyUI on 0.0.0.0:8188..."
cd "${COMFYUI_DIR}"
exec python3 main.py --listen 0.0.0.0 --port 8188 ${COMFYUI_ARGS:-}
