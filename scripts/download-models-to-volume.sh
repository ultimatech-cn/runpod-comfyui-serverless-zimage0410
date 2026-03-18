#!/usr/bin/env bash
set -euo pipefail

# Manifest format:
#   relative_path|filename|url|action
# Actions:
#   file | unzip | untar

volume_root="${1:-/runpod-volume}"
manifest_path="${2:-project-config/model-manifest.txt}"
fail_log_path="${3:-/tmp/download-models-failed.txt}"

if [[ ! -f "${manifest_path}" ]]; then
  echo "download-models-to-volume: manifest not found: ${manifest_path}" >&2
  exit 1
fi

if [[ ! -d "${volume_root}" ]]; then
  echo "download-models-to-volume: volume root not found: ${volume_root}" >&2
  echo "download-models-to-volume: mount your Network Volume first" >&2
  exit 1
fi

if [[ -d "${fail_log_path}" ]]; then
  fail_log_path="${fail_log_path%/}/download-models-failed.txt"
fi

mkdir -p "$(dirname "${fail_log_path}")"

if [[ -d "${volume_root}/storage" ]]; then
  models_root="${volume_root}/storage/models"
  echo "download-models-to-volume: detected storage mount, using ${models_root}"
else
  models_root="${volume_root}/models"
  echo "download-models-to-volume: using standard models path ${models_root}"
fi

mkdir -p "${models_root}"
echo "download-models-to-volume: using manifest ${manifest_path}"
echo "download-models-to-volume: failure log ${fail_log_path}"

failures=()
downloaded_count=0
skipped_count=0

auth_header=()
if [[ -n "${HF_TOKEN:-}" ]]; then
  auth_header=(-H "Authorization: Bearer ${HF_TOKEN}")
fi

download_file() {
  local url="$1"
  local output_path="$2"

  # Prefer curl for Hugging Face links because some CAS bridge redirects
  # are more reliable with curl -L in container environments.
  if [[ "${url}" == *huggingface.co* ]]; then
    if command -v curl >/dev/null 2>&1; then
      if [[ -n "${HF_TOKEN:-}" ]]; then
        curl -fL "${auth_header[@]}" "${url}" -o "${output_path}"
      else
        curl -fL "${url}" -o "${output_path}"
      fi
      return
    fi

    if command -v wget >/dev/null 2>&1; then
      if [[ -n "${HF_TOKEN:-}" ]]; then
        wget --header="Authorization: Bearer ${HF_TOKEN}" -O "${output_path}" "${url}"
      else
        wget -O "${output_path}" "${url}"
      fi
      return
    fi

    echo "download-models-to-volume: neither curl nor wget is available" >&2
    return 127
  fi

  if command -v wget >/dev/null 2>&1; then
    wget -O "${output_path}" "${url}"
    return
  fi

  if command -v curl >/dev/null 2>&1; then
    curl -fL "${url}" -o "${output_path}"
    return
  fi

  echo "download-models-to-volume: neither curl nor wget is available" >&2
  return 127
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "${value}"
}

while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
  line="$(trim "${raw_line}")"

  if [[ -z "${line}" || "${line}" == \#* ]]; then
    continue
  fi

  IFS='|' read -r relative_path filename url action <<< "${line}"
  relative_path="$(trim "${relative_path:-}")"
  filename="$(trim "${filename:-}")"
  url="$(trim "${url:-}")"
  action="$(trim "${action:-file}")"

  if [[ -z "${relative_path}" || -z "${filename}" || -z "${url}" ]]; then
    echo "download-models-to-volume: invalid line: ${line}" >&2
    exit 1
  fi

  target_dir="${models_root}/${relative_path}"
  mkdir -p "${target_dir}"

  case "${action}" in
    ""|file)
      target_file="${target_dir}/${filename}"
      if [[ -f "${target_file}" ]]; then
        echo "download-models-to-volume: skip existing file ${target_file}"
        skipped_count=$((skipped_count + 1))
        continue
      fi
      echo "download-models-to-volume: downloading ${filename} -> ${target_dir}"
      if ! download_file "${url}" "${target_file}"; then
        echo "download-models-to-volume: failed ${filename} from ${url}" >&2
        rm -f "${target_file}"
        failures+=("${relative_path}|${filename}|${url}|file")
        continue
      fi
      downloaded_count=$((downloaded_count + 1))
      ;;
    unzip)
      archive_path="${target_dir}/${filename}"
      marker_path="${target_dir}/.unzipped-${filename//[^A-Za-z0-9._-]/_}"
      if [[ -f "${marker_path}" ]]; then
        echo "download-models-to-volume: skip existing archive extraction ${target_dir}"
        skipped_count=$((skipped_count + 1))
        continue
      fi
      echo "download-models-to-volume: downloading archive ${filename} -> ${target_dir}"
      if ! download_file "${url}" "${archive_path}"; then
        echo "download-models-to-volume: failed ${filename} from ${url}" >&2
        rm -f "${archive_path}"
        failures+=("${relative_path}|${filename}|${url}|unzip")
        continue
      fi
      if ! unzip -o "${archive_path}" -d "${target_dir}"; then
        echo "download-models-to-volume: unzip failed for ${archive_path}" >&2
        rm -f "${archive_path}"
        failures+=("${relative_path}|${filename}|${url}|unzip")
        continue
      fi
      rm -f "${archive_path}"
      touch "${marker_path}"
      downloaded_count=$((downloaded_count + 1))
      ;;
    untar)
      archive_path="${target_dir}/${filename}"
      marker_path="${target_dir}/.untarred-${filename//[^A-Za-z0-9._-]/_}"
      if [[ -f "${marker_path}" ]]; then
        echo "download-models-to-volume: skip existing archive extraction ${target_dir}"
        skipped_count=$((skipped_count + 1))
        continue
      fi
      echo "download-models-to-volume: downloading archive ${filename} -> ${target_dir}"
      if ! download_file "${url}" "${archive_path}"; then
        echo "download-models-to-volume: failed ${filename} from ${url}" >&2
        rm -f "${archive_path}"
        failures+=("${relative_path}|${filename}|${url}|untar")
        continue
      fi
      if ! tar -xf "${archive_path}" -C "${target_dir}"; then
        echo "download-models-to-volume: untar failed for ${archive_path}" >&2
        rm -f "${archive_path}"
        failures+=("${relative_path}|${filename}|${url}|untar")
        continue
      fi
      rm -f "${archive_path}"
      touch "${marker_path}"
      downloaded_count=$((downloaded_count + 1))
      ;;
    *)
      echo "download-models-to-volume: unsupported action '${action}' in line: ${line}" >&2
      exit 1
      ;;
  esac
done < "${manifest_path}"

rm -f "${fail_log_path}"

if [[ ${#failures[@]} -gt 0 ]]; then
  printf '%s\n' "${failures[@]}" > "${fail_log_path}"
  echo "download-models-to-volume: completed with failures" >&2
  echo "download-models-to-volume: downloaded ${downloaded_count}, skipped ${skipped_count}, failed ${#failures[@]}" >&2
  echo "download-models-to-volume: review ${fail_log_path}" >&2
  exit 1
fi

echo "download-models-to-volume: done"
echo "download-models-to-volume: downloaded ${downloaded_count}, skipped ${skipped_count}, failed 0"
