#!/usr/bin/env bash
set -euo pipefail

manifest_path="${1:-project-config/custom-nodes.txt}"
workspace_dir="${2:-/tmp/runpod-custom-node-preflight}"

shared_runtime_deps=(
  "transformers"
  "huggingface_hub"
  "accelerate"
  "diffusers"
  "opencv-python"
  "bitsandbytes"
)

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "${value}"
}

if [[ ! -f "${manifest_path}" ]]; then
  echo "preflight-custom-node-deps: manifest not found: ${manifest_path}" >&2
  exit 1
fi

mkdir -p "${workspace_dir}"
report_path="${workspace_dir}/shared-runtime-deps-report.txt"
rm -f "${report_path}"

echo "preflight-custom-node-deps: manifest=${manifest_path}"
echo "preflight-custom-node-deps: workspace=${workspace_dir}"

inspect_repo() {
  local repo_url="$1"
  local branch="${2:-}"
  local repo_name
  repo_name="$(basename "${repo_url}")"
  repo_name="${repo_name%.git}"
  local repo_dir="${workspace_dir}/${repo_name}"

  rm -rf "${repo_dir}"

  local clone_cmd=(git clone --depth 1)
  if [[ -n "${branch}" ]]; then
    clone_cmd+=(--branch "${branch}")
  fi
  clone_cmd+=("${repo_url}" "${repo_dir}")

  echo "preflight-custom-node-deps: cloning ${repo_url}"
  if ! "${clone_cmd[@]}" >/dev/null 2>&1; then
    rm -rf "${repo_dir}"
    if [[ -n "${branch}" ]]; then
      git clone --branch "${branch}" "${repo_url}" "${repo_dir}" >/dev/null 2>&1
    else
      git clone "${repo_url}" "${repo_dir}" >/dev/null 2>&1
    fi
  fi

  local files=()
  local dep
  local matched=()

  shopt -s nullglob
  for file in "${repo_dir}"/requirements*.txt "${repo_dir}"/install.py "${repo_dir}"/README*; do
    if [[ -f "${file}" ]]; then
      files+=("${file}")
    fi
  done
  shopt -u nullglob

  if [[ ${#files[@]} -eq 0 ]]; then
    {
      echo "repo=${repo_url}"
      echo "status=no_install_metadata_found"
      echo "---"
    } >> "${report_path}"
    return 0
  fi

  for dep in "${shared_runtime_deps[@]}"; do
    if grep -qiF "${dep}" "${files[@]}"; then
      matched+=("${dep}")
    fi
  done

  {
    echo "repo=${repo_url}"
    if [[ ${#matched[@]} -gt 0 ]]; then
      echo "status=shared_runtime_dependency_detected"
      echo "shared_runtime_dependencies=$(IFS=,; echo "${matched[*]}")"
    else
      echo "status=no_shared_runtime_dependency_detected"
    fi
    echo "checked_files=$(IFS=,; echo "${files[*]}")"
    echo "---"
  } >> "${report_path}"
}

while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
  line="$(trim "${raw_line}")"
  line="${line#$'\ufeff'}"

  if [[ -z "${line}" || "${line}" == \#* ]]; then
    continue
  fi

  if [[ "${line}" == registry:* ]]; then
    {
      echo "repo=${line}"
      echo "status=registry_node_manual_review_required"
      echo "---"
    } >> "${report_path}"
    continue
  fi

  if [[ "${line}" == git:* ]]; then
    git_spec="${line#git:}"
    IFS='|' read -r repo_url branch <<< "${git_spec}"
    repo_url="$(trim "${repo_url}")"
    branch="$(trim "${branch:-}")"
    if [[ -n "${repo_url}" ]]; then
      inspect_repo "${repo_url}" "${branch}"
    fi
    continue
  fi

  echo "preflight-custom-node-deps: unsupported line format: ${line}" >&2
  exit 1
done < "${manifest_path}"

echo "preflight-custom-node-deps: report written to ${report_path}"
cat "${report_path}"
