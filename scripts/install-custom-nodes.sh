#!/usr/bin/env bash
set -euo pipefail

# Manifest format:
#   registry:<node-name>
#   git:<repo-url>
#   git:<repo-url>|<branch>

manifest_path="${1:-/project-config/custom-nodes.txt}"
comfyui_path="${COMFYUI_PATH:-/comfyui}"
custom_nodes_dir="${comfyui_path}/custom_nodes"
shared_dep_report="${SHARED_DEP_REPORT:-/tmp/custom-node-shared-deps.txt}"

shared_runtime_deps=(
  "transformers"
  "huggingface_hub"
  "accelerate"
  "diffusers"
  "opencv-python"
  "bitsandbytes"
)

if [[ ! -f "${manifest_path}" ]]; then
  echo "install-custom-nodes: manifest not found: ${manifest_path}"
  exit 1
fi

echo "install-custom-nodes: using manifest ${manifest_path}"

mkdir -p "${custom_nodes_dir}"
cd "${custom_nodes_dir}"
rm -f "${shared_dep_report}"

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

  inspect_shared_runtime_dependencies "${repo_name}" "${repo_url}"

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

inspect_shared_runtime_dependencies() {
  local repo_name="$1"
  local repo_url="$2"
  local dep
  local matched=()
  local search_files=()

  shopt -s nullglob
  for file in "${repo_name}"/requirements*.txt "${repo_name}"/install.py "${repo_name}"/README*; do
    if [[ -f "${file}" ]]; then
      search_files+=("${file}")
    fi
  done
  shopt -u nullglob

  if [[ ${#search_files[@]} -eq 0 ]]; then
    return 0
  fi

  for dep in "${shared_runtime_deps[@]}"; do
    if grep -qiF "${dep}" "${search_files[@]}"; then
      matched+=("${dep}")
    fi
  done

  if [[ ${#matched[@]} -gt 0 ]]; then
    {
      echo "repo=${repo_url}"
      echo "node_dir=${repo_name}"
      echo "shared_runtime_dependencies=$(IFS=,; echo "${matched[*]}")"
      echo "checked_files=$(IFS=,; echo "${search_files[*]}")"
      echo "---"
    } >> "${shared_dep_report}"
    echo "install-custom-nodes: shared runtime dependency warning for ${repo_url} -> ${matched[*]}"
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

if [[ -f "${shared_dep_report}" ]]; then
  echo "install-custom-nodes: shared runtime dependency report written to ${shared_dep_report}"
  echo "install-custom-nodes: review before promoting a production image tag"
fi

echo "install-custom-nodes: done"
