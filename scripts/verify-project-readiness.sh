#!/usr/bin/env bash
set -euo pipefail

workflow_path="${1:-project-inputs/workflow-api.json}"
custom_nodes_path="${2:-project-config/custom-nodes.txt}"
manifest_path="${3:-project-config/model-manifest.txt}"

failures=0
warnings=0

fail() {
  echo "verify-project-readiness: ERROR: $1" >&2
  failures=$((failures + 1))
}

warn() {
  echo "verify-project-readiness: WARNING: $1" >&2
  warnings=$((warnings + 1))
}

if [[ ! -f "$workflow_path" ]]; then
  fail "workflow not found: $workflow_path"
fi
if [[ ! -f "$custom_nodes_path" ]]; then
  fail "custom nodes manifest not found: $custom_nodes_path"
fi
if [[ ! -f "$manifest_path" ]]; then
  fail "model manifest not found: $manifest_path"
fi

check_bom() {
  local path="$1"
  if LC_ALL=C head -c 3 "$path" | grep -q $'\xEF\xBB\xBF'; then
    fail "UTF-8 BOM detected in $path"
  fi
}

check_bom "$custom_nodes_path"
check_bom "$manifest_path"

if [[ -f "$custom_nodes_path" ]]; then
  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    line="${raw_line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" != registry:* && "$line" != git:* ]]; then
      fail "invalid custom node line: $line"
      continue
    fi
    if [[ "$line" == git:* ]]; then
      repo_part="${line#git:}"
      repo_url="${repo_part%%|*}"
      if [[ ! "$repo_url" =~ ^https://github\.com/[^/]+/[^/]+ ]]; then
        warn "custom node git entry is not a standard GitHub URL: $line"
      fi
    fi
  done < "$custom_nodes_path"
fi

manifest_models=()
if [[ -f "$manifest_path" ]]; then
  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    line="${raw_line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    IFS='|' read -r relative_path filename url action <<< "$line"
    if [[ -z "${relative_path:-}" || -z "${filename:-}" || -z "${url:-}" ]]; then
      fail "invalid manifest line: $line"
      continue
    fi
    case "${action:-file}" in
      file|unzip|untar) ;;
      *) fail "unsupported manifest action '${action}' in line: $line" ;;
    esac
    manifest_models+=("$filename")
  done < "$manifest_path"
fi

if [[ -f "$workflow_path" ]]; then
  if grep -q '\\' "$workflow_path"; then
    warn "workflow contains backslashes; review Windows-style paths"
  fi

  mapfile -t workflow_refs < <(grep -oE '[^"/\\]+\.(safetensors|ckpt|pt|pth|onnx|bin)' "$workflow_path" | sort -u || true)
  for ref in "${workflow_refs[@]}"; do
    found=0
    for manifest_model in "${manifest_models[@]}"; do
      if [[ "$ref" == "$manifest_model" ]]; then
        found=1
        break
      fi
    done
    if [[ $found -eq 0 ]]; then
      warn "workflow references model not found in manifest: $ref"
    fi
  done

  if ! grep -q 'SaveImage\|VHS_VideoCombine\|SaveAnimatedWEBP\|SaveWEBM\|SaveVideo' "$workflow_path"; then
    warn "workflow does not appear to contain a known output node"
  fi
fi

if [[ $failures -gt 0 ]]; then
  echo "verify-project-readiness: failed with $failures error(s) and $warnings warning(s)" >&2
  exit 1
fi

echo "verify-project-readiness: passed with $warnings warning(s)"
