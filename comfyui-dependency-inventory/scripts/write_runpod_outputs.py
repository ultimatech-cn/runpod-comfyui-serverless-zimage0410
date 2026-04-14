#!/usr/bin/env python3
"""
Write RunPod template draft files from extracted dependency inventory.
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


def _family_from_filename(filename: str) -> str:
    lower = filename.lower()
    if "flux" in lower:
        return "FLUX"
    if "sdxl" in lower or "_xl" in lower or "-xl" in lower:
        return "SDXL"
    if "pony" in lower:
        return "Pony"
    if "sd15" in lower or "1.5" in lower or "v15" in lower:
        return "SD15"
    if "wan" in lower:
        return "WAN"
    return "TODO-family"


def _relative_path_for_model(model_type: str, filename: str) -> str:
    family = _family_from_filename(filename)
    mapping = {
        "checkpoint": f"checkpoints/{family}",
        "lora": f"loras/{family}",
        "vae": "vae",
        "controlnet": "controlnet",
        "clip_vision": "clip_vision",
        "upscale_model": "upscale_models",
        "unet": "unet",
        "clip": "clip",
    }
    return mapping.get(model_type, "misc/TODO-family")


def _action_for_url(url: str, filename: str) -> str:
    lower = (url or filename).lower()
    if lower.endswith(".zip"):
        return "unzip"
    if lower.endswith(".tar") or lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "untar"
    return "file"


def _is_manifest_usable_url(url: str) -> bool:
    lower = (url or "").lower()
    return (
        lower.startswith("https://huggingface.co/")
        and "/resolve/" in lower
    ) or lower.startswith("https://civitai.com/api/download/")


def _escape_cell(value: Any) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text.replace("|", "\\|")


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def _recommended_candidate(model: Dict[str, Any]) -> Dict[str, Any]:
    candidates = model.get("candidate_urls", [])
    return candidates[0] if candidates else {}


def build_model_manifest(models: List[Dict[str, Any]]) -> str:
    lines = [
        "# Auto-generated draft. Review URLs and paths before delivery.",
        "# Format:",
        "# relative_path|filename|url|action",
    ]
    for model in models:
        candidate = _recommended_candidate(model)
        raw_url = model.get("explicit_url") or candidate.get("url") or ""
        url = raw_url if _is_manifest_usable_url(raw_url) else "TODO-url"
        relative_path = _relative_path_for_model(model["model_type"], model["filename"])
        action = _action_for_url(url, model["filename"])
        lines.append(f"{relative_path}|{model['filename']}|{url}|{action}")
    return "\n".join(lines) + "\n"


def build_custom_nodes_manifest(custom_nodes: List[Dict[str, Any]]) -> str:
    lines = [
        "# Auto-generated draft. Review unresolved items before delivery.",
        "# Supported formats:",
        "#   registry:<node-name>",
        "#   git:<repo-url>",
        "#   git:<repo-url>|<branch>",
    ]
    seen_specs = set()
    seen_todos = set()
    for node in custom_nodes:
        install_spec = node.get("install_spec", "")
        version_hint = node.get("version_hint", "")
        if install_spec:
            line = install_spec
            if version_hint:
                line = f"{line}|{version_hint}"
            if line not in seen_specs:
                seen_specs.add(line)
                lines.append(line)
        else:
            todo = f"# TODO unresolved custom node: {node['node_name']}"
            if todo not in seen_todos:
                seen_todos.add(todo)
                lines.append(todo)
    return "\n".join(lines) + "\n"


def build_dependencies_markdown(inventory: Dict[str, Any]) -> str:
    lines = ["# 02 依赖清单", "", "## 模型清单", "", "| 模型文件名 | 类型 | 下载链接 | 目标路径 | 是否必须 | 备注 |", "| --- | --- | --- | --- | --- | --- |"]
    for model in inventory["models"]:
        candidate = _recommended_candidate(model)
        url = model.get("explicit_url") or candidate.get("url") or ""
        notes = []
        if candidate:
            notes.append(f"推荐来源: {candidate.get('provider', '')}")
            notes.append(f"置信度: {candidate.get('confidence', '')}")
        if model.get("verification_required"):
            notes.append("需人工核对")
        if model.get("source_nodes"):
            notes.append("来源节点: " + ", ".join(model["source_nodes"]))
        lines.append(
            "| {filename} | {model_type} | {url} | {relative_path} | {required} | {notes} |".format(
                filename=_escape_cell(model["filename"]),
                model_type=_escape_cell(model["model_type"]),
                url=_escape_cell(url),
                relative_path=_escape_cell(_relative_path_for_model(model["model_type"], model["filename"])),
                required=_yes_no(model.get("required", True)),
                notes=_escape_cell("; ".join(note for note in notes if note)),
            )
        )

    lines.extend(["", "## 自定义节点清单", "", "| 节点名称 | 仓库地址 | 版本要求 | 安装方式 | 额外依赖 | 是否必须 |", "| --- | --- | --- | --- | --- | --- |"])
    for node in inventory["custom_nodes"]:
        notes = []
        if node.get("confidence"):
            notes.append(node["confidence"])
        if node.get("verification_required"):
            notes.append("需人工核对")
        version_hint = node.get("version_hint") or ("待确认" if node.get("verification_required") else "")
        extra_dependencies = node.get("extra_dependencies") or ""
        if notes:
            extra_dependencies = "; ".join([extra_dependencies] + notes).strip("; ")
        lines.append(
            "| {name} | {repo} | {version} | {install_spec} | {extra} | {required} |".format(
                name=_escape_cell(node["node_name"]),
                repo=_escape_cell(node.get("repo_url", "")),
                version=_escape_cell(version_hint),
                install_spec=_escape_cell(node.get("install_spec", "")),
                extra=_escape_cell(extra_dependencies),
                required=_yes_no(node.get("required", True)),
            )
        )

    lines.extend(["", "## Python 依赖", "", "| 包名 | 版本 | 用途 | 是否已在 requirements 中 |", "| --- | --- | --- | --- |"])
    python_dependencies = inventory.get("python_dependencies", [])
    if python_dependencies:
        for item in python_dependencies:
            lines.append(
                "| {name} | {version} | {usage} | {present} |".format(
                    name=_escape_cell(item.get("name", "")),
                    version=_escape_cell(item.get("version", "")),
                    usage=_escape_cell(item.get("usage", "")),
                    present=_yes_no(bool(item.get("present"))),
                )
            )
    else:
        lines.append("| | | | |")

    lines.extend(["", "## 系统依赖", "", "| 依赖 | 用途 | 是否需要写入 Dockerfile |", "| --- | --- | --- |"])
    system_dependencies = inventory.get("system_dependencies", [])
    if system_dependencies:
        for item in system_dependencies:
            lines.append(
                "| {dependency} | {usage} | {needs_dockerfile} |".format(
                    dependency=_escape_cell(item.get("dependency", "")),
                    usage=_escape_cell(item.get("usage", "")),
                    needs_dockerfile=_yes_no(bool(item.get("needs_dockerfile"))),
                )
            )
    else:
        lines.append("| | | |")

    lines.extend(["", "## 环境变量", "", "| 变量名 | 说明 | 是否必填 | 默认值 | 备注 |", "| --- | --- | --- | --- | --- |"])
    environment_variables = inventory.get("environment_variables", [])
    if environment_variables:
        for item in environment_variables:
            lines.append(
                "| {name} | {description} | {required} | {default} | {note} |".format(
                    name=_escape_cell(item.get("name", "")),
                    description=_escape_cell(item.get("description", "")),
                    required=_yes_no(bool(item.get("required"))),
                    default=_escape_cell(item.get("default", "")),
                    note=_escape_cell(item.get("note", "")),
                )
            )
    else:
        lines.append("| | | | | |")

    lines.extend(["", "## 外部服务", "", "| 服务 | 用途 | 是否必须 | 备注 |", "| --- | --- | --- | --- |"])
    external_services = inventory.get("external_services", [])
    if external_services:
        for item in external_services:
            lines.append(
                "| {service} | {usage} | {required} | {note} |".format(
                    service=_escape_cell(item.get("service", "")),
                    usage=_escape_cell(item.get("usage", "")),
                    required=_yes_no(bool(item.get("required"))),
                    note=_escape_cell(item.get("note", "")),
                )
            )
    else:
        lines.append("| | | | |")

    lines.extend(["", "## 依赖总结", ""])
    summary_items = [
        f"- 已识别模型: {len(inventory.get('models', []))}",
        f"- 已识别自定义节点: {len(inventory.get('custom_nodes', []))}",
    ]
    unresolved_nodes = [item["node_name"] for item in inventory.get("custom_nodes", []) if not item.get("install_spec")]
    unresolved_models = [item["filename"] for item in inventory.get("models", []) if not _recommended_candidate(item) and not item.get("explicit_url")]
    if unresolved_models:
        summary_items.append("- 待补模型链接: " + ", ".join(unresolved_models))
    if unresolved_nodes:
        summary_items.append("- 待补节点仓库: " + ", ".join(unresolved_nodes))
    if inventory.get("unresolved_model_refs"):
        summary_items.append(f"- 未识别模型引用: {len(inventory['unresolved_model_refs'])} 项")
    lines.extend(summary_items)
    lines.append("")
    return "\n".join(lines)


def write_outputs(project_root: str | Path, inventory: Dict[str, Any]) -> Dict[str, str]:
    root = Path(project_root)
    model_manifest_path = root / "project-config" / "model-manifest.txt"
    custom_nodes_path = root / "project-config" / "custom-nodes.txt"
    dependencies_md_path = root / "templates" / "serverless-project" / "02_dependencies.md"

    model_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    custom_nodes_path.parent.mkdir(parents=True, exist_ok=True)
    dependencies_md_path.parent.mkdir(parents=True, exist_ok=True)

    model_manifest_path.write_text(build_model_manifest(inventory["models"]), encoding="utf-8")
    custom_nodes_path.write_text(build_custom_nodes_manifest(inventory["custom_nodes"]), encoding="utf-8")
    dependencies_md_path.write_text(build_dependencies_markdown(inventory), encoding="utf-8")

    return {
        "model_manifest": str(model_manifest_path),
        "custom_nodes": str(custom_nodes_path),
        "dependencies_md": str(dependencies_md_path),
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python write_runpod_outputs.py <inventory.json> <project-root>")
        return 1
    inventory = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    outputs = write_outputs(sys.argv[2], inventory)
    print(json.dumps(outputs, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
