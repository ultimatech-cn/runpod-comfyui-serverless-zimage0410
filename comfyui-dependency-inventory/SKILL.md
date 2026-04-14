---
name: comfyui-dependency-inventory
description: Generate RunPod dependency draft files from ComfyUI workflows. Use this skill when the user wants to turn a PNG, workflow JSON, or API JSON into model-manifest.txt, custom-nodes.txt, and 02_dependencies.md for serverless delivery.
---

# ComfyUI Dependency Inventory

## Overview

This skill handles the dependency-inventory step of a RunPod ComfyUI delivery workflow.

Default flow:
1. Read `PNG`, workflow JSON, or API JSON
2. Normalize the workflow into one structure
3. Extract models, custom nodes, and deployment hints
4. Resolve custom node repositories
5. Search Hugging Face and Civitai for model candidates when links are missing
6. Write `project-config/model-manifest.txt`, `project-config/custom-nodes.txt`, and `templates/serverless-project/02_dependencies.md`

## When To Use

Use this skill when the user asks to:

- generate a RunPod dependency inventory from a ComfyUI workflow
- convert a ComfyUI workflow into `model-manifest.txt` and `custom-nodes.txt`
- prepare the dependency checklist after local workflow validation

Do not use this skill as the first choice when the goal is:

- a customer-facing workflow document
- HTML workflow documentation
- a general workflow explanation without RunPod output files

In those cases, prefer `comfyui-doc-generator`.

## Workflow

### Step 1. Prepare Input

Accepted inputs:

- `workflow.png`
- `workflow.json`
- `workflow-api.json`

If `project_root` is not provided:

- first try the current project root
- if that does not look like the RunPod template, fall back to `d:\01_Projects\Runpod\templates\active\runpod-comfyui-serverless-template0318`

The target template should contain:

- `project-config/model-manifest.txt`
- `project-config/custom-nodes.txt`
- `templates/serverless-project/02_dependencies.md`

### Step 2. Run The Generator

Use the unified entrypoint:

```bash
python scripts/generate_inventory.py --input_path <workflow-file> --project_root <project-root>
```

Common options:

```bash
python scripts/generate_inventory.py --input_path <workflow-file> --search_models false
python scripts/generate_inventory.py --input_path <workflow-file> --write_outputs false
python scripts/generate_inventory.py --input_path <workflow-file> --inventory_out <inventory-json>
```

Safety note:

- `write_outputs` now defaults to `false`
- when writing outputs, pass `--project_root` explicitly
- for multi-workflow projects, generate separate inventory JSON files first, then merge after review

### Step 3. Review Output Quality

Check these first:

- whether all model filenames were detected
- whether custom node repository matches look trustworthy
- whether suggested download links still need human verification

If model links come from fuzzy search, do not treat them as final truth. Keep them as draft output for review.

### Step 4. Finalize For Delivery

Report back to the user with:

- total detected models
- total detected custom nodes
- high-confidence items
- items that need manual review
- unresolved items that still need manual completion

## Resources

### scripts/

- `normalize_workflow.py`
- `extract_dependencies.py`
- `resolve_custom_nodes.py`
- `search_model_candidates.py`
- `write_runpod_outputs.py`
- `generate_inventory.py`

### references/

- `model_path_mapping.md`
- `search_ranking.md`
- `custom_node_resolution.md`
