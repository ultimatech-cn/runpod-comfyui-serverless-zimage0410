# Manual Checklist

Do not skip these checks.

## Workflow Audit

- Confirm the workflow is API-exported JSON, not UI-only JSON.
- Confirm every model filename referenced by the workflow is present in `project-config/model-manifest.txt` or already exists in the customer volume.
- Confirm every custom node used by the workflow has a source listed in `project-config/custom-nodes.txt`.
- Confirm the workflow contains a real media output node.
- Confirm no input path still uses Windows separators when Linux execution is expected.

## Build Audit

- Confirm every script copied by `Dockerfile` exists in the repository and is not excluded by `.dockerignore`.
- Confirm custom node repositories still exist and the selected branch is valid.
- Run `scripts/preflight-custom-node-deps.sh` before editing Docker-related files or promoting a new image tag.
- For every new custom node repo, inspect `requirements.txt`, `install.py`, and README install notes.
- Identify shared runtime dependencies before build, especially:
  - `transformers`
  - `huggingface_hub`
  - `accelerate`
  - `diffusers`
  - `opencv-python`
  - `bitsandbytes`
- Confirm whether a shared dependency upgrade is required before using a production tag.
- Confirm the image can build before any volume or endpoint debugging starts.

## Volume Audit

- Confirm where the Network Volume is mounted in the temporary pod.
- Confirm the endpoint will mount the same volume, even if the path differs.
- Confirm the expected model root actually contains files.
- Confirm the expected core directories exist when relevant: `checkpoints`, `clip`, `unet`, `vae`, `loras`.
- Confirm download failure logs are empty or absent for a successful run.

## Runtime Audit

- Confirm the endpoint logs show the detected model root you expected.
- Confirm missing node errors are not being mistaken for missing model errors.
- Confirm history outputs contain real media artifacts.
- Confirm the response shape matches the client contract.
- If shared runtime dependencies were upgraded, confirm at least two representative workflows still run correctly.
