#!/usr/bin/env bash
set -euo pipefail

# Manifest format:
#   registry:<node-name>
#   git:<repo-url>
#   git:<repo-url>|<branch>

manifest_path="${1:-/project-config/custom-nodes.txt}"
comfyui_path="${COMFYUI_PATH:-/comfyui}"
custom_nodes_dir="${comfyui_path}/custom_nodes"

if [[ ! -f "${manifest_path}" ]]; then
  echo "install-custom-nodes: manifest not found: ${manifest_path}"
  exit 1
fi

echo "install-custom-nodes: using manifest ${manifest_path}"

mkdir -p "${custom_nodes_dir}"
cd "${custom_nodes_dir}"

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "${value}"
}

install_git_repo() {
  local repo_url="$1"
  local branch="${2:-}"
  local repo_name
  repo_name="$(basename "${repo_url}")"
  repo_name="${repo_name%.git}"

  rm -rf "${repo_name}"

  local clone_cmd=(git clone --depth 1)
  if [[ -n "${branch}" ]]; then
    clone_cmd+=(--branch "${branch}")
  fi
  clone_cmd+=("${repo_url}" "${repo_name}")

  local attempt
  for attempt in 1 2 3; do
    echo "install-custom-nodes: clone attempt ${attempt} for ${repo_url}"
    if "${clone_cmd[@]}"; then
      break
    fi
    rm -rf "${repo_name}"
    sleep 2
  done

  if [[ ! -d "${repo_name}" ]]; then
    echo "install-custom-nodes: shallow clone failed for ${repo_url}, retrying without --depth 1"
    if [[ -n "${branch}" ]]; then
      git clone --branch "${branch}" "${repo_url}" "${repo_name}"
    else
      git clone "${repo_url}" "${repo_name}"
    fi
  fi

  if [[ -f "${repo_name}/requirements.txt" ]]; then
    python3 -m pip install --no-cache-dir -r "${repo_name}/requirements.txt" || true
  fi

  if [[ -f "${repo_name}/install.py" ]]; then
    (cd "${repo_name}" && python3 install.py) || true
  fi

  if [[ -f "${repo_name}/install.sh" ]]; then
    (cd "${repo_name}" && bash install.sh) || true
  fi
}

while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
  line="$(trim "${raw_line}")"
  line="${line#$'\ufeff'}"

  if [[ -z "${line}" || "${line}" == \#* ]]; then
    continue
  fi

  if [[ "${line}" == registry:* ]]; then
    node_name="$(trim "${line#registry:}")"
    if [[ -n "${node_name}" ]]; then
      echo "install-custom-nodes: installing registry node ${node_name}"
      comfy-node-install "${node_name}"
    fi
    continue
  fi

  if [[ "${line}" == git:* ]]; then
    git_spec="${line#git:}"
    IFS='|' read -r repo_url branch <<< "${git_spec}"
    repo_url="$(trim "${repo_url}")"
    branch="$(trim "${branch:-}")"
    if [[ -n "${repo_url}" ]]; then
      echo "install-custom-nodes: cloning ${repo_url}"
      install_git_repo "${repo_url}" "${branch}"
    fi
    continue
  fi

  echo "install-custom-nodes: unsupported line format: ${line}" >&2
  exit 1
done < "${manifest_path}"

echo "install-custom-nodes: done"
