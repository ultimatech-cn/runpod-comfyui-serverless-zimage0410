#!/usr/bin/env python3
"""
Extract models, custom nodes, and deployment hints from normalized ComfyUI workflows.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
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


MODEL_EXTENSIONS = (
    ".safetensors",
    ".ckpt",
    ".pt",
    ".pth",
    ".bin",
    ".onnx",
    ".engine",
    ".gguf",
    ".zip",
    ".tar",
    ".tar.gz",
)

KNOWN_HUB_MODEL_IDS: Dict[str, Dict[str, str]] = {
    "Qwen3-VL-4B-Instruct": {
        "provider": "huggingface",
        "repo_id": "Qwen/Qwen3-VL-4B-Instruct",
        "repo_url": "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct",
    }
}

BUILTIN_NODES = {
    "CheckpointLoader",
    "CheckpointLoaderSimple",
    "unCLIPCheckpointLoader",
    "LoraLoader",
    "LoraLoaderModelOnly",
    "VAELoader",
    "CLIPLoader",
    "DualCLIPLoader",
    "ControlNetLoader",
    "ControlNetLoaderAdvanced",
    "UpscaleModelLoader",
    "CLIPVisionLoader",
    "UNETLoader",
    "UNETLoaderFLUX",
    "KSampler",
    "KSamplerAdvanced",
    "SamplerCustom",
    "SamplerCustomAdvanced",
    "KSamplerSelect",
    "BasicScheduler",
    "BasicGuider",
    "CFGNorm",
    "DisableNoise",
    "EmptyLatentImage",
    "FlipSigmas",
    "LatentUpscale",
    "LatentUpscaleBy",
    "LatentComposite",
    "VAEEncode",
    "VAEDecode",
    "VAEEncodeTiled",
    "VAEDecodeTiled",
    "LoadImage",
    "SaveImage",
    "PreviewImage",
    "ImageScale",
    "ImageScaleBy",
    "ImageUpscaleWithModel",
    "ImageBatch",
    "ImagePadForOutpaint",
    "FluxGuidance",
    "RandomNoise",
    "InjectNoise",
    "CLIPTextEncode",
    "CLIPTextEncodeFlux",
    "CLIPTextEncodeSDXL",
    "CLIPTextEncodeSDXLRefiner",
    "TextEncodeQwenImageEditPlus",
    "ConditioningCombine",
    "ConditioningConcat",
    "ConditioningSetArea",
    "ConditioningSetMask",
    "Note",
    "Reroute",
    "PrimitiveNode",
    "Group",
    "ModelSamplingSD3",
    "ModelSamplingAuraFlow",
    "PrimitiveString",
    "FluxKontextImageScale",
}

MODEL_FIELD_HINTS = {
    "checkpoint": {"ckpt_name", "checkpoint", "checkpoint_name", "model_name", "base_model"},
    "lora": {"lora_name", "lora", "lora_model"},
    "vae": {"vae_name", "vae"},
    "controlnet": {"control_net_name", "controlnet_name", "controlnet", "control_net"},
    "clip_vision": {"clip_name", "clip_vision", "clipvision_name", "vision_model"},
    "upscale_model": {"model_name", "upscale_model", "upscaler_name"},
    "clip": {"clip_name1", "clip_name2", "clip_name"},
    "unet": {"unet_name", "unet_model"},
    "other": {"ipadapter_file", "model_file", "weights_file"},
}

RULES = [
    {"contains": ("CheckpointLoader",), "model_type": "checkpoint", "fields": ("ckpt_name", "checkpoint", "model"), "widget_index": 0},
    {"contains": ("LoraLoader",), "model_type": "lora", "fields": ("lora_name", "lora"), "widget_index": 0},
    {"contains": ("VAELoader",), "model_type": "vae", "fields": ("vae_name", "vae"), "widget_index": 0},
    {"contains": ("ControlNetLoader",), "model_type": "controlnet", "fields": ("control_net_name", "controlnet", "controlnet_name"), "widget_index": 0},
    {"contains": ("CLIPVisionLoader",), "model_type": "clip_vision", "fields": ("clip_name", "clip_vision", "clipvision_name"), "widget_index": 0},
    {"contains": ("UpscaleModelLoader",), "model_type": "upscale_model", "fields": ("model_name", "upscale_model"), "widget_index": 0},
    {"contains": ("UNETLoader",), "model_type": "unet", "fields": ("unet_name", "model_name"), "widget_index": 0},
    {"contains": ("CLIPLoader", "DualCLIPLoader"), "model_type": "clip", "fields": ("clip_name", "clip_name1", "clip_name2"), "widget_index": 0},
    {"contains": ("Qwen3_VQA",), "model_type": "other", "fields": ("model",), "allow_named_id": True},
]


def safe_print(message: str, file=None) -> None:
    target = file or sys.stdout
    try:
        print(message, file=target)
    except (UnicodeEncodeError, ValueError, OSError):
        fallback = str(message).encode("ascii", errors="replace").decode("ascii")
        print(fallback, file=target)


def _normalize_str(value: Any) -> str:
    return str(value).strip()


def _looks_like_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _looks_like_model_name(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or len(text) < 3:
        return False
    lower = text.lower()
    if _looks_like_url(lower):
        return True
    if any(lower.endswith(ext) for ext in MODEL_EXTENSIONS):
        return True
    basename = os.path.basename(text)
    return any(basename.lower().endswith(ext) for ext in MODEL_EXTENSIONS)


def _looks_like_named_model_id(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or len(text) < 6:
        return False
    if " " in text or text.startswith("$"):
        return False
    if _looks_like_url(text.lower()):
        return False
    if any(char in text for char in ("\\", ":")):
        return False
    has_letter = any(char.isalpha() for char in text)
    has_digit = any(char.isdigit() for char in text)
    has_separator = any(char in text for char in ("-", "_", "/"))
    return has_letter and has_digit and has_separator


def _looks_like_model_reference(value: Any, allow_named_id: bool = False) -> bool:
    if _looks_like_model_name(value):
        return True
    if allow_named_id and _looks_like_named_model_id(value):
        return True
    return False


def _source_type_for_value(value: Any, allow_named_id: bool = False) -> str:
    if _looks_like_url(str(value).lower()):
        return "url"
    if _looks_like_model_name(value):
        return "file"
    if allow_named_id and _looks_like_named_model_id(value):
        hub_info = KNOWN_HUB_MODEL_IDS.get(str(value).strip(), {})
        if hub_info.get("provider") == "huggingface":
            return "huggingface_repo"
        return "hub_model_id"
    return "unknown"


def _basename(value: str) -> str:
    clean = value.replace("\\", "/")
    return clean.split("/")[-1]


def _infer_model_type_from_field(field_name: str) -> Optional[str]:
    field = field_name.lower()
    for model_type, hints in MODEL_FIELD_HINTS.items():
        if field in hints:
            return model_type
        if any(token in field for token in hints):
            return model_type
    return None


def _extract_rule_matches(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    node_type = node["node_type"]
    matches: List[Dict[str, Any]] = []
    for rule in RULES:
        if any(token in node_type for token in rule["contains"]):
            allow_named_id = bool(rule.get("allow_named_id"))
            fields = node.get("input_values", {})
            for field_name in rule["fields"]:
                value = fields.get(field_name)
                if _looks_like_model_reference(value, allow_named_id=allow_named_id):
                    matches.append(
                        {
                            "model_type": rule["model_type"],
                            "field_name": field_name,
                            "value": _normalize_str(value),
                            "source": "input_value",
                            "source_type": _source_type_for_value(value, allow_named_id=allow_named_id),
                        }
                    )
            widget_index = rule.get("widget_index")
            widgets = node.get("widgets_values", [])
            if isinstance(widget_index, int) and len(widgets) > widget_index:
                widget_value = widgets[widget_index]
                if _looks_like_model_reference(widget_value, allow_named_id=allow_named_id):
                    matches.append(
                        {
                            "model_type": rule["model_type"],
                            "field_name": f"widget[{widget_index}]",
                            "value": _normalize_str(widget_value),
                            "source": "widget_value",
                            "source_type": _source_type_for_value(widget_value, allow_named_id=allow_named_id),
                        }
                    )
    return matches


def _extract_generic_model_matches(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for field_name, value in node.get("input_values", {}).items():
        if not isinstance(value, str):
            continue
        model_type = _infer_model_type_from_field(field_name)
        if model_type and _looks_like_model_name(value):
            matches.append({"model_type": model_type, "field_name": field_name, "value": _normalize_str(value), "source": "generic_field"})
    return matches


def _collect_string_values(node: Dict[str, Any]) -> List[tuple[str, str]]:
    values: List[tuple[str, str]] = []
    for field_name, value in node.get("input_values", {}).items():
        if isinstance(value, str) and value.strip():
            values.append((field_name, value.strip()))
    for index, value in enumerate(node.get("widgets_values", [])):
        if isinstance(value, str) and value.strip():
            values.append((f"widget[{index}]", value.strip()))
    return values


def _extract_property_model_urls(node: Dict[str, Any]) -> Dict[str, str]:
    raw_node = node.get("raw_node", {})
    if not isinstance(raw_node, dict):
        return {}
    properties = raw_node.get("properties", {})
    if not isinstance(properties, dict):
        return {}
    models = properties.get("models", [])
    if not isinstance(models, list):
        return {}
    mapping: Dict[str, str] = {}
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "")
        url = item.get("url", "")
        if name and url:
            mapping[str(name)] = str(url)
    return mapping


MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
RAW_URL_PATTERN = re.compile(r"https?://[^\s)]+")


def _extract_note_links(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    if node.get("node_type") not in {"Note", "MarkdownNote"}:
        return []

    parts = [value for _, value in _collect_string_values(node)]
    text = "\n".join(parts)
    if not text:
        return []

    links: List[Dict[str, Any]] = []
    seen_urls = set()

    for label, url in MARKDOWN_LINK_PATTERN.findall(text):
        if url in seen_urls:
            continue
        seen_urls.add(url)
        links.append(
            {
                "label": label.strip(),
                "url": url.strip(),
                "source_node_id": node.get("id"),
                "source_node_type": node.get("node_type"),
            }
        )

    for url in RAW_URL_PATTERN.findall(text):
        if url in seen_urls:
            continue
        seen_urls.add(url)
        links.append(
            {
                "label": "",
                "url": url.strip(),
                "source_node_id": node.get("id"),
                "source_node_type": node.get("node_type"),
            }
        )

    return links


def _infer_service(field_name: str, value: str) -> Optional[Dict[str, Any]]:
    lower_field = field_name.lower()
    lower_value = value.lower()
    if "s3://" in lower_value or " bucket" in f" {lower_field}" or lower_field.startswith("s3"):
        return {"service": "S3", "usage": "模型或结果对象存储", "required": True, "note": value}
    if ("api_key" in lower_field or "token" in lower_field or "base_url" in lower_field) and not value.startswith("$"):
        return {"service": "第三方 API", "usage": f"字段 {field_name}", "required": True, "note": value}
    return None


def _infer_env_var(field_name: str, value: str) -> Optional[Dict[str, Any]]:
    if value.startswith("${") and value.endswith("}"):
        name = value[2:-1]
        return {"name": name, "description": f"来自字段 {field_name}", "required": True, "default": "", "note": "工作流中显式引用"}
    if value.startswith("$") and len(value) > 1 and " " not in value:
        return {"name": value[1:], "description": f"来自字段 {field_name}", "required": True, "default": "", "note": "工作流中显式引用"}
    lower_field = field_name.lower()
    if any(token in lower_field for token in ("api_key", "token", "secret")):
        return {
            "name": re.sub(r"[^A-Z0-9_]", "_", field_name.upper()),
            "description": f"建议从字段 {field_name} 提取为环境变量",
            "required": True,
            "default": "",
            "note": "值需要人工确认",
        }
    return None


def _video_hint(node_type: str) -> Optional[Dict[str, Any]]:
    lower = node_type.lower()
    if "video" in lower or lower.startswith("vhs_") or "vfi" in lower:
        return {"dependency": "ffmpeg", "usage": "视频读写或帧处理", "needs_dockerfile": True}
    return None


def _dedupe_by(items: List[Dict[str, Any]], key_fields: tuple[str, ...]) -> List[Dict[str, Any]]:
    seen = set()
    unique: List[Dict[str, Any]] = []
    for item in items:
        key = tuple(item.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def extract_dependencies(normalized: Dict[str, Any]) -> Dict[str, Any]:
    model_map: Dict[tuple[str, str], Dict[str, Any]] = {}
    custom_nodes: List[Dict[str, Any]] = []
    services: List[Dict[str, Any]] = []
    env_vars: List[Dict[str, Any]] = []
    system_dependencies: List[Dict[str, Any]] = []
    unresolved_model_refs: List[Dict[str, Any]] = []
    reference_links: List[Dict[str, Any]] = []

    for node in normalized.get("nodes", []):
        node_type = node["node_type"]
        reference_links.extend(_extract_note_links(node))

        if node_type not in BUILTIN_NODES:
            custom_nodes.append({"node_name": node_type, "title": node.get("title") or node_type, "required": True, "source_node_ids": [node.get("id")]})

        video_dep = _video_hint(node_type)
        if video_dep:
            system_dependencies.append(video_dep)

        model_refs = _extract_rule_matches(node)
        generic_refs = _extract_generic_model_matches(node)
        if not model_refs and generic_refs:
            model_refs = generic_refs

        property_model_urls = _extract_property_model_urls(node)

        for match in model_refs:
            raw_value = match["value"]
            explicit_url = raw_value if _looks_like_url(raw_value.lower()) else ""
            filename = _basename(raw_value)
            if not filename:
                unresolved_model_refs.append({"node_type": node_type, "value": raw_value})
                continue
            key = (match["model_type"], filename)
            record = model_map.setdefault(
                key,
                {
                    "filename": filename,
                    "model_type": match["model_type"],
                    "source_type": match.get("source_type", "file"),
                    "source_nodes": [],
                    "field_names": [],
                    "required": True,
                    "explicit_url": explicit_url or property_model_urls.get(filename, ""),
                    "candidate_urls": [],
                    "verification_required": not bool(explicit_url or property_model_urls.get(filename, "")),
                    "preload_recommended": False,
                    "hub_repo_id": "",
                    "hub_repo_url": "",
                    "notes": [],
                },
            )
            record["source_nodes"].append(node_type)
            record["field_names"].append(match["field_name"])
            if match.get("source_type") and record.get("source_type") == "file":
                record["source_type"] = match["source_type"]
            resolved_explicit_url = explicit_url or property_model_urls.get(filename, "")
            if resolved_explicit_url and not record["explicit_url"]:
                record["explicit_url"] = resolved_explicit_url
                record["verification_required"] = False
            hub_info = KNOWN_HUB_MODEL_IDS.get(filename, {})
            if record.get("source_type") in {"huggingface_repo", "hub_model_id"}:
                record["preload_recommended"] = True
                if hub_info:
                    record["hub_repo_id"] = hub_info.get("repo_id", "")
                    record["hub_repo_url"] = hub_info.get("repo_url", "")
                    note = "非单文件模型，建议预下载到 Volume，避免运行时自动拉取失败或重复下载"
                    if note not in record["notes"]:
                        record["notes"].append(note)

        for field_name, value in _collect_string_values(node):
            service = _infer_service(field_name, value)
            if service:
                services.append(service)
            env_var = _infer_env_var(field_name, value)
            if env_var:
                env_vars.append(env_var)

    models = []
    for record in model_map.values():
        record["source_nodes"] = sorted(set(record["source_nodes"]))
        record["field_names"] = sorted(set(record["field_names"]))
        models.append(record)

    return {
        "source_format": normalized.get("source_format"),
        "models": sorted(models, key=lambda item: (item["model_type"], item["filename"].lower())),
        "custom_nodes": _dedupe_by(custom_nodes, ("node_name",)),
        "python_dependencies": [],
        "system_dependencies": _dedupe_by(system_dependencies, ("dependency",)),
        "environment_variables": _dedupe_by(env_vars, ("name",)),
        "external_services": _dedupe_by(services, ("service", "note")),
        "unresolved_model_refs": unresolved_model_refs,
        "reference_links": _dedupe_by(reference_links, ("url",)),
    }


def main() -> int:
    if len(sys.argv) != 2:
        safe_print("Usage: python extract_dependencies.py <normalized-workflow.json>")
        return 1
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    result = extract_dependencies(payload)
    safe_print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
