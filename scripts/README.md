# Scripts

## `download-models-to-volume.sh`

Download models from `project-config/model-manifest.txt` into a mounted Network Volume.

Examples:

```bash
bash scripts/download-models-to-volume.sh /runpod-volume project-config/model-manifest.txt /tmp/download-models-failed.txt
bash scripts/download-models-to-volume.sh /workspace project-config/model-manifest.txt /tmp/
```

## `verify-project-readiness.sh`

Read-only checks for workflow, custom nodes, and model manifest files.

```bash
bash scripts/verify-project-readiness.sh project-inputs/workflow-api.json project-config/custom-nodes.txt project-config/model-manifest.txt
```

## `preflight-custom-node-deps.sh`

Run this before editing `Dockerfile` or promoting a new image tag.

It clones the custom-node repos listed in `project-config/custom-nodes.txt` and scans:

- `requirements*.txt`
- `install.py`
- `README*`

for shared runtime dependencies.

```bash
bash scripts/preflight-custom-node-deps.sh project-config/custom-nodes.txt
```

## `verify-volume-models.sh`

Read-only checks for volume mount points and visible model files.

```bash
bash scripts/verify-volume-models.sh /runpod-volume
bash scripts/verify-volume-models.sh /workspace
```

## `install-custom-nodes.sh`

Install custom node repos from `project-config/custom-nodes.txt`.

This script now also scans each repo for shared runtime dependencies such as:

- `transformers`
- `huggingface_hub`
- `accelerate`
- `diffusers`
- `opencv-python`
- `bitsandbytes`

If found, it writes a warning report to:

- `/tmp/custom-node-shared-deps.txt`

Review that report before promoting a production image tag.

## `extract-runpod-media.py`

Extract images or videos from handler responses that contain base64 or URL-based media entries.
