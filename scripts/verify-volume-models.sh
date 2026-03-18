#!/usr/bin/env bash
set -euo pipefail

root_path="${1:-/runpod-volume}"

if [[ ! -d "$root_path" ]]; then
  echo "verify-volume-models: root path not found: $root_path" >&2
  exit 1
fi

find_models_dir() {
  local root="$1"
  local candidate=""
  for candidate in \
    "$root/models" \
    "$root/storage/models" \
    "$root/ComfyUI/models" \
    "$root/storage/ComfyUI/models" \
    "$root/runpod-slim/ComfyUI/models"
  do
    if [[ -d "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done

  candidate="$(find "$root" -maxdepth 5 -type d \( -name models -o -name Models \) | head -n 1)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  return 1
}

models_root="$(find_models_dir "$root_path" || true)"
if [[ -z "$models_root" ]]; then
  echo "verify-volume-models: could not locate a models directory under $root_path" >&2
  exit 1
fi

echo "verify-volume-models: models root: $models_root"

for subdir in checkpoints clip unet vae loras controlnet; do
  if [[ -d "$models_root/$subdir" ]]; then
    echo "verify-volume-models: found directory $subdir"
  else
    echo "verify-volume-models: missing directory $subdir"
  fi
done

count="$(find "$models_root" -type f \( -name '*.safetensors' -o -name '*.ckpt' -o -name '*.pt' -o -name '*.pth' \) | wc -l | tr -d ' ')"
echo "verify-volume-models: model file count: $count"

echo "verify-volume-models: sample files:"
find "$models_root" -type f \( -name '*.safetensors' -o -name '*.ckpt' -o -name '*.pt' -o -name '*.pth' \) | sort | head -20
