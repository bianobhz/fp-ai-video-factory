#!/usr/bin/env bash
set -euo pipefail

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
DRIVE_OUTPUTS_PATH="${DRIVE_OUTPUTS_PATH:-IA_Studio/outputs}"
LOCAL_OUTPUTS_DIR="${LOCAL_OUTPUTS_DIR:-./outputs/raw}"

mkdir -p "${LOCAL_OUTPUTS_DIR}"

echo "[FP AI Video Factory] Pulling outputs from ${RCLONE_REMOTE}:${DRIVE_OUTPUTS_PATH} -> ${LOCAL_OUTPUTS_DIR}"
rclone copy "${RCLONE_REMOTE}:${DRIVE_OUTPUTS_PATH}" "${LOCAL_OUTPUTS_DIR}" --progress --transfers 4 --checkers 8
echo "[FP AI Video Factory] Done."
