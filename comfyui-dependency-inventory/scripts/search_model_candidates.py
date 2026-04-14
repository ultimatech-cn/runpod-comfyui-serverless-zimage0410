#!/usr/bin/env python3
"""
Search Hugging Face and Civitai for model download candidates.
"""

from __future__ import annotations

import difflib
import io
import json
import os
import sys
from functools import lru_cache
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer") and not isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except (ValueError, AttributeError):
        pass


HF_SEARCH_URL = "https://huggingface.co/api/models?search={query}&limit=6"
HF_MODEL_URL = "https://huggingface.co/api/models/{repo_id}"
CIVITAI_SEARCH_URL = "https://civitai.com/api/v1/models?query={query}&limit=6"

MODEL_TYPE_KEYWORDS = {
    "checkpoint": ("checkpoint", "base model", "sdxl", "flux"),
    "lora": ("lora",),
    "vae": ("vae",),
    "controlnet": ("controlnet", "control net"),
    "clip_vision": ("clip vision", "vision"),
    "upscale_model": ("upscale", "upscaler"),
    "clip": ("clip",),
    "unet": ("unet",),
}

LOCAL_HUB_MODEL_MAP = {
    "Qwen3-VL-4B-Instruct": {
        "provider": "Hugging Face Repo",
        "repo_id": "Qwen/Qwen3-VL-4B-Instruct",
        "url": "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct",
        "score": 96,
    }
}


def _fetch_json(url: str, timeout: int = 10) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "codex-skill/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _stem(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".tar.gz"):
        return os.path.basename(filename)[:-7]
    return os.path.splitext(os.path.basename(filename))[0]


def _score_candidate(requested_name: str, model_type: str, candidate_name: str, label: str) -> int:
    requested_base = os.path.basename(requested_name).lower()
    candidate_base = os.path.basename(candidate_name).lower()
    requested_stem = _stem(requested_name).lower()
    candidate_stem = _stem(candidate_name).lower()

    score = 0
    if requested_base == candidate_base:
        score += 100
    elif requested_stem == candidate_stem:
        score += 92
    elif requested_stem in candidate_stem or candidate_stem in requested_stem:
        score += 78
    else:
        ratio = difflib.SequenceMatcher(None, requested_stem, candidate_stem).ratio()
        score += int(ratio * 70)

    keywords = MODEL_TYPE_KEYWORDS.get(model_type, ())
    label_lower = label.lower()
    if any(keyword in label_lower for keyword in keywords):
        score += 8
    if requested_stem.replace("-", " ") in label_lower:
        score += 6
    return score


def _confidence_from_score(score: int) -> str:
    if score >= 95:
        return "high"
    if score >= 75:
        return "medium"
    return "low"


def _build_candidate(provider: str, filename: str, label: str, url: str, score: int) -> Dict[str, Any]:
    return {
        "provider": provider,
        "filename": filename,
        "label": label,
        "url": url,
        "score": score,
        "confidence": _confidence_from_score(score),
        "verification_required": True,
    }


def _local_hub_candidates(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    if model.get("source_type") not in {"huggingface_repo", "hub_model_id"}:
        return []
    filename = model.get("filename", "")
    known = LOCAL_HUB_MODEL_MAP.get(filename)
    if known:
        return [
            {
                "provider": known["provider"],
                "filename": filename,
                "label": known["repo_id"],
                "url": known["url"],
                "score": known["score"],
                "confidence": "high",
                "verification_required": True,
            }
        ]
    repo_id = model.get("hub_repo_id", "")
    repo_url = model.get("hub_repo_url", "")
    if repo_id and repo_url:
        return [
            {
                "provider": "Hub Repo",
                "filename": filename,
                "label": repo_id,
                "url": repo_url,
                "score": 90,
                "confidence": "high",
                "verification_required": True,
            }
        ]
    return []


def _is_direct_download_url(url: str) -> bool:
    lower = (url or "").lower()
    return (lower.startswith("https://huggingface.co/") and "/resolve/" in lower) or lower.startswith("https://civitai.com/api/download/")


def _candidate_priority(candidate: Dict[str, Any]) -> tuple[int, int]:
    provider = candidate.get("provider", "")
    direct = 1 if _is_direct_download_url(candidate.get("url", "")) else 0
    note_bonus = 1 if provider.startswith("Note Link") else 0
    explicit_bonus = 2 if provider == "explicit" else 0
    return (explicit_bonus + direct + note_bonus, candidate.get("score", 0))


def _normalize_huggingface_url(url: str) -> str:
    return url.replace("/blob/", "/resolve/")


def _candidate_filename_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    return urllib.parse.unquote(os.path.basename(path))


@lru_cache(maxsize=128)
def _fetch_civitai_model_version(version_id: str) -> Dict[str, Any]:
    return _fetch_json(f"https://civitai.com/api/v1/model-versions/{version_id}")


def _search_note_links(model_name: str, model_type: str, reference_links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    requested_name = os.path.basename(model_name)

    for link in reference_links:
        url = link.get("url", "")
        label = link.get("label", "") or url
        lower_url = url.lower()

        if "huggingface.co" in lower_url:
            normalized_url = _normalize_huggingface_url(url)
            candidate_name = _candidate_filename_from_url(normalized_url) or label
            score = _score_candidate(requested_name, model_type, candidate_name, label)
            if score >= 40:
                candidates.append(_build_candidate("Note Link (HF)", candidate_name, label, normalized_url, score))
            continue

        if "civitai.com" in lower_url:
            parsed = urllib.parse.urlparse(url)
            version_id = urllib.parse.parse_qs(parsed.query).get("modelVersionId", [""])[0]
            if version_id:
                try:
                    payload = _fetch_civitai_model_version(version_id)
                except Exception:
                    payload = {}
                files = payload.get("files", []) if isinstance(payload, dict) else []
                for file_item in files:
                    file_name = file_item.get("name", "")
                    download_url = file_item.get("downloadUrl", "") or file_item.get("url", "")
                    if not file_name or not download_url:
                        continue
                    score = _score_candidate(requested_name, model_type, file_name, label)
                    if os.path.basename(file_name).lower() == os.path.basename(requested_name).lower() or _stem(file_name).lower() == _stem(requested_name).lower():
                        candidates.append(_build_candidate("Note Link (Civitai)", file_name, label, download_url, score))
            else:
                candidate_name = _candidate_filename_from_url(url) or label
                score = _score_candidate(requested_name, model_type, candidate_name, label)
                if score >= 55:
                    candidates.append(_build_candidate("Note Link (Civitai page)", candidate_name, label, url, score))

    return candidates


def search_huggingface(model_name: str, model_type: str) -> List[Dict[str, Any]]:
    query = urllib.parse.quote(_stem(model_name))
    try:
        repos = _fetch_json(HF_SEARCH_URL.format(query=query))
    except Exception:
        return []

    candidates: List[Dict[str, Any]] = []
    for repo in repos[:3]:
        if not isinstance(repo, dict) or "id" not in repo:
            continue
        repo_id = repo["id"]
        label = repo_id
        try:
            details = _fetch_json(HF_MODEL_URL.format(repo_id=urllib.parse.quote(repo_id, safe="")))
        except Exception:
            details = {}
        siblings = details.get("siblings", []) if isinstance(details, dict) else []
        if siblings:
            for sibling in siblings:
                file_name = sibling.get("rfilename", "")
                if not file_name:
                    continue
                score = _score_candidate(model_name, model_type, file_name, label)
                if score < 40:
                    continue
                candidates.append(
                    _build_candidate(
                        "Hugging Face",
                        file_name,
                        label,
                        f"https://huggingface.co/{repo_id}/resolve/main/{file_name}",
                        score,
                    )
                )
        else:
            score = _score_candidate(model_name, model_type, model_name, label)
            candidates.append(_build_candidate("Hugging Face", model_name, label, f"https://huggingface.co/{repo_id}", score))
    return candidates


def search_civitai(model_name: str, model_type: str) -> List[Dict[str, Any]]:
    query = urllib.parse.quote(_stem(model_name))
    try:
        payload = _fetch_json(CIVITAI_SEARCH_URL.format(query=query))
    except Exception:
        return []

    items = payload.get("items", []) if isinstance(payload, dict) else []
    candidates: List[Dict[str, Any]] = []
    for item in items[:4]:
        if not isinstance(item, dict):
            continue
        model_label = item.get("name", "")
        versions = item.get("modelVersions", []) or []
        for version in versions[:2]:
            version_name = version.get("name", "")
            files = version.get("files", []) or []
            for file_item in files:
                file_name = file_item.get("name", "")
                download_url = file_item.get("downloadUrl", "") or file_item.get("url", "")
                if not file_name or not download_url:
                    continue
                label = f"{model_label} / {version_name}".strip(" /")
                score = _score_candidate(model_name, model_type, file_name, label)
                if score < 40:
                    continue
                candidates.append(_build_candidate("Civitai", file_name, label, download_url, score))
    return candidates


def attach_model_candidates(models: List[Dict[str, Any]], reference_links: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    reference_links = reference_links or []
    for model in models:
        item = dict(model)
        if item.get("explicit_url"):
            item["candidate_urls"] = [
                {
                    "provider": "explicit",
                    "filename": item["filename"],
                    "label": "workflow explicit url",
                    "url": item["explicit_url"],
                    "score": 100,
                    "confidence": "high",
                    "verification_required": False,
                }
            ]
            item["verification_required"] = False
            enriched.append(item)
            continue

        all_candidates = _local_hub_candidates(item)
        all_candidates.extend(_search_note_links(item["filename"], item["model_type"], reference_links))
        all_candidates.extend(search_huggingface(item["filename"], item["model_type"]))
        all_candidates.extend(search_civitai(item["filename"], item["model_type"]))
        direct_candidates = [candidate for candidate in all_candidates if _is_direct_download_url(candidate.get("url", ""))]
        if direct_candidates:
            all_candidates = direct_candidates
        all_candidates.sort(key=_candidate_priority, reverse=True)

        unique: List[Dict[str, Any]] = []
        seen_urls = set()
        for candidate in all_candidates:
            url = candidate["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            unique.append(candidate)
            if len(unique) == 3:
                break

        item["candidate_urls"] = unique
        item["verification_required"] = True
        enriched.append(item)
    return enriched


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python search_model_candidates.py <models.json>")
        return 1
    models = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(attach_model_candidates(models), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
