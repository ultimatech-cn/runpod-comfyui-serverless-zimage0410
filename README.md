# RunPod ComfyUI Serverless Template

A reusable template for deploying ComfyUI workflows on RunPod Serverless.

This repository is intentionally generic. It keeps the runtime core that usually works across projects and pushes project-specific changes into a small set of configuration files.

## What Stays Stable

- `handler.py`: RunPod handler contract and ComfyUI execution loop
- `src/start.sh`: startup orchestration and model path detection
- `Dockerfile`: image build entrypoint for custom nodes and runtime tools
- `scripts/download-models-to-volume.sh`: model download helper for temporary pods

## What You Change Per Project

- `project-config/custom-nodes.txt`
- `project-config/model-manifest.txt`
- `project-inputs/workflow-api.json`
- `project-inputs/test-payload-minimal.json`
- `project-inputs/test-payload-with-image.json`
- `.runpod/hub.json`

## Repository Layout

```text
runpod-comfyui-serverless-template/
  .runpod/
  project-config/
  project-inputs/
  scripts/
  src/
  templates/serverless-project/
  tests/
  Dockerfile
  docker-compose.yml
  handler.py
  README.md
  QUICK_START.md
  PITFALLS.md
  MANUAL_CHECKLIST.md
  DELIVERY_CHECKLIST.md
```

## Recommended Operating Model

- Install custom nodes into the image
- Put models on a Network Volume
- Keep workflow-specific logic in the workflow JSON before touching `handler.py`
- Treat volume verification as a required manual step, not an optional check

## First Read

- `QUICK_START.md`
- `PITFALLS.md`
- `MANUAL_CHECKLIST.md`
- `scripts/README.md`

## Request Contract

Use RunPod input shaped like:

```json
{
  "input": {
    "workflow": {},
    "images": []
  }
}
```

`images` is optional.

## Response Contract

Read generated media from `output.images[]`.

Each item contains:

- `filename`
- `type`
- `data`

For base64 responses, `data` may already include a data URI prefix.
