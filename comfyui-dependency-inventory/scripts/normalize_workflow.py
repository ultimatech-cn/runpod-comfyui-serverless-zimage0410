#!/usr/bin/env python3
"""
Normalize ComfyUI workflow inputs (PNG, workflow JSON, API JSON)
into a consistent intermediate structure.
"""

from __future__ import annotations

import io
import json
import sys
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


PNG_KEYS = ("workflow", "Workflow", "prompt")


def safe_print(message: str, file=None) -> None:
    target = file or sys.stdout
    try:
        print(message, file=target)
    except (UnicodeEncodeError, ValueError, OSError):
        fallback = str(message).encode("ascii", errors="replace").decode("ascii")
        print(fallback, file=target)


def _try_parse_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, bytes):
        for encoding in ("utf-8", "utf-8-sig", "latin1"):
            try:
                value = value.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
    if not isinstance(value, str):
        return value
    candidates = [value]
    try:
        candidates.append(value.encode("latin1").decode("utf-8"))
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return value


def extract_from_png(png_path: Path) -> Any:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError(
            "PNG workflow extraction requires Pillow. Install it before using PNG input."
        ) from exc

    image = Image.open(png_path)
    for key in PNG_KEYS:
        if key in image.info:
            parsed = _try_parse_json(image.info[key])
            if isinstance(parsed, (dict, list)):
                return parsed
    raise ValueError("PNG metadata does not contain recognizable ComfyUI workflow data.")


def load_input(input_path: str | Path) -> Any:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if path.suffix.lower() == ".png":
        return extract_from_png(path)
    if path.suffix.lower() != ".json":
        raise ValueError(f"Unsupported file type: {path.suffix}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _looks_like_api_prompt(data: Any) -> bool:
    if not isinstance(data, dict) or not data:
        return False
    matched = 0
    for value in data.values():
        if isinstance(value, dict) and ("class_type" in value or "inputs" in value):
            matched += 1
    return matched > 0


def detect_format(data: Any) -> tuple[str, Any]:
    if isinstance(data, dict):
        if isinstance(data.get("nodes"), list):
            return "workflow_json", data
        if isinstance(data.get("workflow"), dict) and isinstance(data["workflow"].get("nodes"), list):
            return "workflow_json", data["workflow"]
        if isinstance(data.get("prompt"), dict):
            prompt = data["prompt"]
            if isinstance(prompt.get("nodes"), list):
                return "workflow_json", prompt
            if _looks_like_api_prompt(prompt):
                return "api_json", prompt
        if _looks_like_api_prompt(data):
            return "api_json", data
    raise ValueError("Unsupported ComfyUI input. Expected PNG metadata, workflow JSON, or API JSON.")


def _normalize_widget_values(values: Any) -> List[Any]:
    if isinstance(values, list):
        return values
    if isinstance(values, dict):
        return list(values.values())
    return []


def _extract_ui_input_refs(inputs: Any) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    if not isinstance(inputs, list):
        return refs
    for item in inputs:
        if not isinstance(item, dict):
            continue
        link = item.get("link")
        if link is not None:
            refs.append({"name": item.get("name"), "link": link})
    return refs


def _extract_ui_output_refs(outputs: Any) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    if not isinstance(outputs, list):
        return refs
    for item in outputs:
        if not isinstance(item, dict):
            continue
        links = item.get("links") or []
        if links:
            refs.append({"name": item.get("name"), "links": links})
    return refs


def normalize_workflow_json(data: Dict[str, Any]) -> Dict[str, Any]:
    nodes = []
    for node in data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        nodes.append(
            {
                "id": str(node.get("id", "")),
                "node_type": node.get("type", "Unknown"),
                "title": node.get("title") or node.get("type", "Unknown"),
                "widgets_values": _normalize_widget_values(node.get("widgets_values")),
                "raw_inputs": node.get("inputs", []),
                "raw_outputs": node.get("outputs", []),
                "input_refs": _extract_ui_input_refs(node.get("inputs", [])),
                "output_refs": _extract_ui_output_refs(node.get("outputs", [])),
                "input_values": {},
                "source": "workflow_json",
                "raw_node": node,
            }
        )
    return {"source_format": "workflow_json", "node_count": len(nodes), "nodes": nodes}


def _extract_api_refs(inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    for key, value in inputs.items():
        if isinstance(value, list) and value:
            refs.append({"name": key, "node_id": str(value[0]), "slot": value[1] if len(value) > 1 else None})
    return refs


def _extract_api_values(inputs: Dict[str, Any]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    for key, value in inputs.items():
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, (int, float)) or (isinstance(first, str) and first.isdigit()):
                continue
        values[key] = value
    return values


def normalize_api_json(data: Dict[str, Any]) -> Dict[str, Any]:
    nodes = []
    for node_id, node in data.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {}) if isinstance(node.get("inputs"), dict) else {}
        meta = node.get("_meta", {}) if isinstance(node.get("_meta"), dict) else {}
        nodes.append(
            {
                "id": str(node_id),
                "node_type": node.get("class_type", "Unknown"),
                "title": meta.get("title") or node.get("class_type", "Unknown"),
                "widgets_values": [],
                "raw_inputs": inputs,
                "raw_outputs": [],
                "input_refs": _extract_api_refs(inputs),
                "output_refs": [],
                "input_values": _extract_api_values(inputs),
                "source": "api_json",
                "raw_node": node,
            }
        )
    return {"source_format": "api_json", "node_count": len(nodes), "nodes": nodes}


def normalize_input(input_path: str | Path) -> Dict[str, Any]:
    raw = load_input(input_path)
    detected, payload = detect_format(raw)
    if detected == "workflow_json":
        return normalize_workflow_json(payload)
    if detected == "api_json":
        return normalize_api_json(payload)
    raise AssertionError(f"Unhandled format: {detected}")


def main() -> int:
    if len(sys.argv) != 2:
        safe_print("Usage: python normalize_workflow.py <workflow.png|workflow.json|workflow-api.json>")
        return 1
    normalized = normalize_input(sys.argv[1])
    safe_print(json.dumps(normalized, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
