# AGENTS.md

This file defines project-specific collaboration rules for `runpod-comfyui-serverless-template0318`.

## Scope

This repository is the main template for new RunPod ComfyUI Serverless projects.

Use it as a clean starting point. Do not turn it into a client-specific project unless explicitly requested.

## Intent

The template should stay:

- reusable
- minimal
- deployment-proven
- easy to copy into a new client project

## What Can Change Freely Per New Project

These files are expected to change for each client:

- `project-config/custom-nodes.txt`
- `project-config/model-manifest.txt`
- `project-inputs/workflow-api.json`
- `project-inputs/test-payload-minimal.json`
- `project-inputs/test-payload-with-image.json`
- `.runpod/hub.json`

## What Should Usually Stay Stable

Only change these when there is a real deployment reason:

- `handler.py`
- `src/start.sh`
- `scripts/download-models-to-volume.sh`
- `scripts/install-custom-nodes.sh`
- `Dockerfile`

If one of these changes, the reason should be concrete and reproducible.

## Required Checks Before Calling A Project Ready

Do not skip these:

1. `workflow-api.json` is a real API export, not a placeholder.
2. Every model referenced by the workflow is present in `model-manifest.txt` or already confirmed on the customer volume.
3. Every custom node used by the workflow is present in `custom-nodes.txt`.
4. The temporary pod and the final endpoint use the same Network Volume.
5. Volume contents are verified before endpoint creation.
6. At least one minimal payload and one representative payload are tested.

## Script Rules

- `scripts/verify-project-readiness.sh` should fail on placeholder content or missing critical references.
- `scripts/download-models-to-volume.sh` should prefer correctness over silent success.
- New scripts should only be added if they reduce repeated manual work across multiple projects.

## Documentation Rules

Keep docs compact and operational.

Primary docs:

- `README.md`
- `QUICK_START.md`
- `SOP_SIMPLE.md`
- `SOP_RUNBOOK.md`
- `PITFALLS.md`
- `MANUAL_CHECKLIST.md`
- `DELIVERY_CHECKLIST.md`

Do not add overlapping docs unless they replace an existing one.

## Non-Goals

- This repository is not a customer delivery project.
- This repository is not a general ComfyUI knowledge base.
- This repository should not accumulate one-off hacks for a single workflow.
