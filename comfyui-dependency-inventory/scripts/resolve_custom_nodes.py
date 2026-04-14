#!/usr/bin/env python3
"""
Resolve ComfyUI custom node repositories for RunPod deployment drafts.
"""

from __future__ import annotations

import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer") and not isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except (ValueError, AttributeError):
        pass


LOCAL_NODE_MAP: Dict[str, Dict[str, Any]] = {
    "VHS_VideoCombine": {"repo_url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"},
    "VHS_LoadVideo": {"repo_url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"},
    "VHS_LoadVideoPath": {"repo_url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"},
    "VHS_LoadImages": {"repo_url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"},
    "VHS_SelectLatest": {"repo_url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"},
    "Any Switch (rgthree)": {"repo_url": "https://github.com/rgthree/rgthree-comfy"},
    "Power Prompt (rgthree)": {"repo_url": "https://github.com/rgthree/rgthree-comfy"},
    "easy cleanGpuUsed": {"repo_url": "https://github.com/yolain/ComfyUI-Easy-Use"},
    "easy fullLoader": {"repo_url": "https://github.com/yolain/ComfyUI-Easy-Use"},
    "easy kSampler": {"repo_url": "https://github.com/yolain/ComfyUI-Easy-Use"},
    "easy showAnything": {"repo_url": "https://github.com/yolain/ComfyUI-Easy-Use"},
    "SetNode": {"repo_url": "https://github.com/WASasquatch/was-node-suite-comfyui"},
    "GetNode": {"repo_url": "https://github.com/WASasquatch/was-node-suite-comfyui"},
    "ColorMatch": {"repo_url": "https://github.com/kijai/ComfyUI-KJNodes"},
    "CRTFirstLastFrameSelector": {"repo_url": "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes"},
    "Fast Groups Bypasser (rgthree)": {"repo_url": "https://github.com/rgthree/rgthree-comfy"},
    "Label (rgthree)": {"repo_url": "https://github.com/rgthree/rgthree-comfy"},
    "PathchSageAttentionKJ": {"repo_url": "https://github.com/kijai/ComfyUI-KJNodes"},
    "GetImageSizeKJ": {"repo_url": "https://github.com/kijai/ComfyUI-KJNodes"},
    "DownloadAndLoadGIMMVFIModel": {"repo_url": "https://github.com/kijai/ComfyUI-GIMM-VFI"},
    "GIMMVFI_interpolate": {"repo_url": "https://github.com/kijai/ComfyUI-GIMM-VFI"},
    "Resolution": {"repo_url": "https://github.com/pythongosssss/ComfyUI-Custom-Scripts"},
    "MarkdownNote": {"repo_url": "https://github.com/pythongosssss/ComfyUI-Custom-Scripts"},
    "ImageResize+": {"repo_url": "https://github.com/pythongosssss/ComfyUI-Custom-Scripts"},
    "IPAdapter": {"repo_url": "https://github.com/cubiq/ComfyUI_IPAdapter_plus"},
    "IPAdapterUnifiedLoader": {"repo_url": "https://github.com/cubiq/ComfyUI_IPAdapter_plus"},
    "IPAdapterModelLoader": {"repo_url": "https://github.com/cubiq/ComfyUI_IPAdapter_plus"},
    "WanImageToVideo": {"repo_url": "https://github.com/Wan-Video/ComfyUI-Wan-Node"},
    "WanVideoToVideo": {"repo_url": "https://github.com/Wan-Video/ComfyUI-Wan-Node"},
    "TTP_Image_Assy": {"repo_url": "https://github.com/TTPlanetPig/Comfyui_TTP_Toolset"},
    "RH_Captioner": {"repo_url": "https://github.com/receyuki/comfyui-prompt-reader-node"},
    "FaceDetailer": {"repo_url": "https://github.com/ltdrdata/ComfyUI-Impact-Pack"},
    "UltralyticsDetectorProvider": {"repo_url": "https://github.com/ltdrdata/ComfyUI-Impact-Pack"},
    "AIO_Preprocessor": {"repo_url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "DWPreprocessor": {"repo_url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "LineArtPreprocessor": {"repo_url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "DepthAnythingPreprocessor": {"repo_url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "Manager": {"repo_url": "https://github.com/ltdrdata/ComfyUI-Manager", "registry_name": "comfyui-manager"},
    "Florence2Run": {"repo_url": "https://github.com/kijai/ComfyUI-Florence2"},
    "DownloadAndLoadFlorence2Model": {"repo_url": "https://github.com/kijai/ComfyUI-Florence2"},
    "KSamplerAdvancedProgress": {"repo_url": "https://github.com/ltdrdata/ComfyUI-Inspire-Pack"},
    "Efficient Loader": {"repo_url": "https://github.com/jags111/efficiency-nodes-comfyui"},
    "BNK_CLIPTextEncodeAdvanced": {"repo_url": "https://github.com/BlenderNeko/ComfyUI_ADV_CLIP_emb"},
    "GroundingDinoSAMSegment": {"repo_url": "https://github.com/storyicon/comfyui_segment_anything"},
    "ADE_AnimateDiffLoaderWithContext": {"repo_url": "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved"},
    "RIFE VFI": {"repo_url": "https://github.com/Fannovel16/ComfyUI-Frame-Interpolation"},
    "UltimateSDUpscale": {"repo_url": "https://github.com/ssitu/ComfyUI_UltimateSDUpscale"},
    "Qwen3_VQA": {"repo_url": "https://github.com/IuvenisSapiens/ComfyUI_Qwen3-VL-Instruct"},
    "LayerUtility: ImageScaleByAspectRatio V2": {"repo_url": "https://github.com/chflame163/ComfyUI_LayerStyle"},
    "LayerUtility: PurgeVRAM V2": {"repo_url": "https://github.com/chflame163/ComfyUI_LayerStyle"},
    "FluxForwardODESampler": {"repo_url": "https://github.com/logtd/ComfyUI-Fluxtapoz"},
    "FluxDeGuidance": {"repo_url": "https://github.com/logtd/ComfyUI-Fluxtapoz"},
    "FluxReverseODESampler": {"repo_url": "https://github.com/logtd/ComfyUI-Fluxtapoz"},
    "GetImageSize+": {"repo_url": "https://github.com/cubiq/ComfyUI_essentials"},
    "InFluxModelSamplingPred": {"repo_url": "https://github.com/logtd/ComfyUI-Fluxtapoz"},
    "JoinStrings": {"repo_url": "https://github.com/kijai/ComfyUI-KJNodes"},
    "OutFluxModelSamplingPred": {"repo_url": "https://github.com/logtd/ComfyUI-Fluxtapoz"},
    "PainterFluxImageEdit": {"repo_url": "https://github.com/princepainter/Comfyui-PainterFluxImageEdit"},
    "SaveImageAndMetadata_": {"repo_url": "https://github.com/shadowcz007/comfyui-mixlab-nodes"},
    "UpscaleImageByUsingModel": {"repo_url": "https://github.com/TheBill2001/comfyui-upscale-by-model"},
}

LOCAL_TITLE_MAP: Dict[str, Dict[str, Any]] = {
    "Qwen3 VQA": {"repo_url": "https://github.com/IuvenisSapiens/ComfyUI_Qwen3-VL-Instruct"},
    "LayerUtility: Purge VRAM V2": {"repo_url": "https://github.com/chflame163/ComfyUI_LayerStyle"},
    "Painter Flux Image Edit": {"repo_url": "https://github.com/princepainter/Comfyui-PainterFluxImageEdit"},
    "Save Image Output ❤️Mixlab": {"repo_url": "https://github.com/shadowcz007/comfyui-mixlab-nodes"},
}

PATTERN_RULES = [
    (r"^VHS_", "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite", "high"),
    (r"\(rgthree\)$", "https://github.com/rgthree/rgthree-comfy", "high"),
    (r"^easy\s|^easy[A-Z]", "https://github.com/yolain/ComfyUI-Easy-Use", "high"),
    (r"^IPAdapter", "https://github.com/cubiq/ComfyUI_IPAdapter_plus", "medium"),
    (r"^CR\s|^CR[A-Z]", "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes", "medium"),
    (r"KJ$", "https://github.com/kijai/ComfyUI-KJNodes", "medium"),
    (r"^TTP_", "https://github.com/TTPlanetPig/Comfyui_TTP_Toolset", "medium"),
    (r"^Wan[A-Z]", "https://github.com/Wan-Video/ComfyUI-Wan-Node", "medium"),
    (r"^ADE_", "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved", "medium"),
    (r"^BNK_", "https://github.com/BlenderNeko/ComfyUI_ADV_CLIP_emb", "medium"),
    (r"Preprocessor$", "https://github.com/Fannovel16/comfyui_controlnet_aux", "medium"),
    (r"^LayerUtility:", "https://github.com/chflame163/ComfyUI_LayerStyle", "high"),
    (r"Mixlab", "https://github.com/shadowcz007/comfyui-mixlab-nodes", "high"),
    (r"^Qwen3_", "https://github.com/IuvenisSapiens/ComfyUI_Qwen3-VL-Instruct", "high"),
    (r"^PainterFlux", "https://github.com/princepainter/Comfyui-PainterFluxImageEdit", "high"),
]

REGISTRY_SEARCH_URL = "https://registry.comfy.org/api/nodes?search={query}"


def _fetch_json(url: str, timeout: int = 6) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "codex-skill/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _build_install_spec(repo_url: str, registry_name: str = "") -> str:
    if registry_name:
        return f"registry:{registry_name}"
    return f"git:{repo_url}" if repo_url else ""


def _registry_lookup(node_name: str) -> Optional[Dict[str, Any]]:
    url = REGISTRY_SEARCH_URL.format(query=urllib.parse.quote(node_name))
    try:
        payload = _fetch_json(url)
    except Exception:
        return None
    nodes = payload.get("nodes", []) if isinstance(payload, dict) else []
    for item in nodes:
        if not isinstance(item, dict):
            continue
        node_types = item.get("node_types", [])
        if node_name in node_types:
            repository = item.get("repository")
            repo_url = repository.get("url", "") if isinstance(repository, dict) else ""
            return {
                "repo_url": repo_url,
                "registry_name": item.get("name", ""),
                "confidence": "medium",
                "resolution_source": "registry",
                "verification_required": True,
                "version_hint": "",
                "extra_dependencies": "",
            }
    return None


def resolve_node(node_name: str, title: str = "", enable_online: bool = True) -> Dict[str, Any]:
    if node_name in LOCAL_NODE_MAP:
        item = LOCAL_NODE_MAP[node_name]
        repo_url = item.get("repo_url", "")
        registry_name = item.get("registry_name", "")
        return {
            "node_name": node_name,
            "repo_url": repo_url,
            "install_spec": _build_install_spec(repo_url, registry_name),
            "version_hint": "",
            "extra_dependencies": "",
            "confidence": "high",
            "verification_required": False,
            "resolution_source": "local_map",
        }

    if title and title in LOCAL_TITLE_MAP:
        item = LOCAL_TITLE_MAP[title]
        repo_url = item.get("repo_url", "")
        registry_name = item.get("registry_name", "")
        return {
            "node_name": node_name,
            "repo_url": repo_url,
            "install_spec": _build_install_spec(repo_url, registry_name),
            "version_hint": "",
            "extra_dependencies": "",
            "confidence": "high",
            "verification_required": False,
            "resolution_source": "title_map",
        }

    for pattern, repo_url, confidence in PATTERN_RULES:
        if re.search(pattern, node_name):
            return {
                "node_name": node_name,
                "repo_url": repo_url,
                "install_spec": f"git:{repo_url}",
                "version_hint": "",
                "extra_dependencies": "",
                "confidence": confidence,
                "verification_required": True,
                "resolution_source": "pattern",
            }

    if enable_online:
        found = _registry_lookup(node_name)
        if found:
            found["node_name"] = node_name
            found["install_spec"] = _build_install_spec(found.get("repo_url", ""), found.get("registry_name", ""))
            return found

    return {
        "node_name": node_name,
        "repo_url": "",
        "install_spec": "",
        "version_hint": "",
        "extra_dependencies": "",
        "confidence": "none",
        "verification_required": True,
        "resolution_source": "unresolved",
    }


def resolve_custom_nodes(custom_nodes: List[Dict[str, Any]], enable_online: bool = True) -> List[Dict[str, Any]]:
    resolved = []
    for item in custom_nodes:
        node_name = item["node_name"]
        resolved.append({**item, **resolve_node(node_name, title=item.get("title", ""), enable_online=enable_online)})
    return sorted(resolved, key=lambda entry: entry["node_name"].lower())


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python resolve_custom_nodes.py <custom-nodes.json>")
        return 1
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    result = resolve_custom_nodes(payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
