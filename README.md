# RunPod ComfyUI Serverless Template

This is the current main template for new RunPod ComfyUI Serverless projects.

The goal is not to be clever. The goal is to stay reusable, stable, and easy to copy into a new delivery project.

## Start Here

Read these in order:

1. `QUICK_START.md`
2. `SOP_RUNBOOK.md`
3. `PITFALLS.md`
4. `MANUAL_CHECKLIST.md`
5. `scripts/README.md`
6. `AGENTS.md`

## What You Change Per Project

- `project-config/custom-nodes.txt`
- `project-config/model-manifest.txt`
- `project-inputs/workflow-api.json`
- `project-inputs/test-payload-minimal.json`
- `project-inputs/test-payload-with-image.json`
- `.runpod/hub.json`

## What Should Usually Stay Stable

- `handler.py`
- `src/start.sh`
- `Dockerfile`
- `scripts/download-models-to-volume.sh`
- `scripts/install-custom-nodes.sh`

Change these only when there is a real deployment issue to solve.

## Repository Layout

```text
runpod-comfyui-serverless-template0318/
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
  SOP_SIMPLE.md
  SOP_RUNBOOK.md
  PITFALLS.md
  MANUAL_CHECKLIST.md
  DELIVERY_CHECKLIST.md
  AGENTS.md
```

## Recommended Operating Model

- Treat the delivery process as semi-automated, not fully automatic.
- Use workflow extraction to produce drafts, then do manual verification before delivery.
- Install custom nodes into the image.
- Put models on a Network Volume.
- Prefer your own Hugging Face mirror for LoRA files when third-party links are unstable or permission-gated.
- Treat model verification as a required step, not an optional check.
- Keep workflow-specific logic in the workflow JSON before touching `handler.py`.

## Model Truth Policy

- Do not assume workflow-exported model names are final truth.
- Keep `workflow_ref` and `resolved source` as separate concepts.
- For delivery, prioritize:
  1. manually verified source
  2. your own Hugging Face mirror
  3. workflow-exported name only as a reference key

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
