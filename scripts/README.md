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

## `verify-volume-models.sh`

Read-only checks for volume mount points and visible model files.

```bash
bash scripts/verify-volume-models.sh /runpod-volume
bash scripts/verify-volume-models.sh /workspace
```

## `extract-runpod-media.py`

Extract images or videos from handler responses that contain base64 or URL-based media entries.
