#!/usr/bin/env python3
"""
Unified entrypoint for generating RunPod dependency inventory drafts from ComfyUI workflows.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict

from extract_dependencies import extract_dependencies
from normalize_workflow import normalize_input
from resolve_custom_nodes import resolve_custom_nodes
from search_model_candidates import attach_model_candidates
from write_runpod_outputs import write_outputs


if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer") and not isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except (ValueError, AttributeError):
        pass


FALLBACK_PROJECT_ROOT = Path(
    r"d:\01_Projects\Runpod\templates\active\runpod-comfyui-serverless-template0318"
)


def _bool_arg(value: str) -> bool:
    lowered = value.lower().strip()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _looks_like_project_root(path: Path) -> bool:
    return (
        (path / "project-config" / "model-manifest.txt").exists()
        and (path / "project-config" / "custom-nodes.txt").exists()
        and (path / "templates" / "serverless-project").exists()
    )


def _is_direct_download_url(url: str) -> bool:
    lower = (url or "").lower()
    return (lower.startswith("https://huggingface.co/") and "/resolve/" in lower) or lower.startswith("https://civitai.com/api/download/")


def discover_project_root(cli_value: str = "") -> tuple[Path, str]:
    if cli_value:
        return Path(cli_value).resolve(), "cli"
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if _looks_like_project_root(candidate):
            return candidate, "cwd"
    if _looks_like_project_root(FALLBACK_PROJECT_ROOT):
        return FALLBACK_PROJECT_ROOT, "fallback"
    return cwd, "cwd"


def summarize(inventory: Dict[str, Any]) -> Dict[str, Any]:
    high_conf_models = []
    review_models = []
    for model in inventory["models"]:
        candidates = model.get("candidate_urls") or []
        candidate = candidates[0] if candidates else None
        if model.get("explicit_url"):
            high_conf_models.append(model["filename"])
        elif candidate and candidate.get("confidence") == "high" and _is_direct_download_url(candidate.get("url", "")):
            high_conf_models.append(model["filename"])
        else:
            review_models.append(model["filename"])

    high_conf_nodes = []
    review_nodes = []
    for node in inventory["custom_nodes"]:
        if node.get("confidence") == "high" and not node.get("verification_required"):
            high_conf_nodes.append(node["node_name"])
        else:
            review_nodes.append(node["node_name"])

    return {
        "models_detected": len(inventory["models"]),
        "custom_nodes_detected": len(inventory["custom_nodes"]),
        "high_confidence_models": high_conf_models,
        "review_models": review_models,
        "high_confidence_custom_nodes": high_conf_nodes,
        "review_custom_nodes": review_nodes,
        "unresolved_model_refs": inventory.get("unresolved_model_refs", []),
    }


def build_inventory(input_path: str, search_models: bool = True, enable_online_node_lookup: bool = True) -> Dict[str, Any]:
    normalized = normalize_input(input_path)
    inventory = extract_dependencies(normalized)
    inventory["custom_nodes"] = resolve_custom_nodes(
        inventory["custom_nodes"],
        enable_online=enable_online_node_lookup,
    )
    if search_models:
        inventory["models"] = attach_model_candidates(
            inventory["models"],
            reference_links=inventory.get("reference_links", []),
        )
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate RunPod dependency drafts from a ComfyUI workflow.")
    parser.add_argument("--input_path", required=True, help="Path to workflow PNG/JSON/API JSON")
    parser.add_argument("--project_root", default="", help="RunPod template project root")
    parser.add_argument("--search_models", type=_bool_arg, default=True, help="Whether to search Hugging Face/Civitai candidates")
    parser.add_argument("--write_outputs", type=_bool_arg, default=False, help="Whether to write output files into project_root")
    parser.add_argument("--enable_online_node_lookup", type=_bool_arg, default=True, help="Whether to query registry.comfy.org when local mapping misses")
    parser.add_argument("--print_json", type=_bool_arg, default=False, help="Print full inventory JSON")
    parser.add_argument("--inventory_out", default="", help="Optional path to write the full inventory JSON")
    args = parser.parse_args()

    project_root, project_root_source = discover_project_root(args.project_root)
    inventory = build_inventory(
        input_path=args.input_path,
        search_models=args.search_models,
        enable_online_node_lookup=args.enable_online_node_lookup,
    )

    outputs = {}
    if args.write_outputs:
        if project_root_source == "fallback" and not args.project_root:
            raise SystemExit(
                "Refusing to write outputs into the fallback template path. "
                "Pass --project_root explicitly."
            )
        outputs = write_outputs(project_root, inventory)

    if args.inventory_out:
        inventory_out_path = Path(args.inventory_out).resolve()
        inventory_out_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_out_path.write_text(
            json.dumps(inventory, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    summary = summarize(inventory)
    print(
        json.dumps(
            {
                "project_root": str(project_root),
                "project_root_source": project_root_source,
                "outputs": outputs,
                "inventory_out": str(Path(args.inventory_out).resolve()) if args.inventory_out else "",
                "summary": summary,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if args.print_json:
        print(json.dumps(inventory, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
