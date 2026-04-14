# Quick Start

## 1. Edit Project Config

Update these files first:

- `project-config/custom-nodes.txt`
- `project-config/model-manifest.txt`
- `project-inputs/workflow-api.json`
- `.runpod/hub.json`

Before you lock the model manifest:

- separate `workflow_ref` from the final verified source
- manually verify custom-node repos at repo level, not only by node count
- mirror unstable LoRA files to your own Hugging Face repo when needed
- run `bash scripts/preflight-custom-node-deps.sh project-config/custom-nodes.txt` before changing Docker-related files

## 2. Run the Readiness Check

```bash
bash scripts/verify-project-readiness.sh \
  project-inputs/workflow-api.json \
  project-config/custom-nodes.txt \
  project-config/model-manifest.txt
```

Fix every reported issue before building.

## 3. Build Locally

```powershell
docker build --platform linux/amd64 -t runpod-comfyui-serverless-template:local .
```

## 4. Start the Local Stack

```powershell
docker-compose up
```

Endpoints:

- Worker API: <http://localhost:8000/docs>
- ComfyUI: <http://localhost:8188>

## 5. Download Models to the Mounted Volume

Use verified links here. Do not blindly trust workflow-exported model names.

If your temporary pod mounts the Network Volume at `/runpod-volume`:

```bash
bash scripts/download-models-to-volume.sh /runpod-volume project-config/model-manifest.txt /tmp/download-models-failed.txt
```

If your temporary pod exposes the same volume at `/workspace`:

```bash
bash scripts/download-models-to-volume.sh /workspace project-config/model-manifest.txt /tmp/download-models-failed.txt
```

The third argument may also be a directory such as `/tmp/`.

## 6. Verify the Volume Before Creating the Endpoint

```bash
bash scripts/verify-volume-models.sh /runpod-volume
bash scripts/verify-volume-models.sh /workspace
```

Use the path that exists in the temporary pod.

## 6a. RunPod Manual Steps

Temporary pod:

```bash
git clone https://github.com/ultimatech-cn/runpod-comfyui-serverless-zimage0410.git
cd runpod-comfyui-serverless-zimage0410
ls -la /runpod-volume
ls -la /workspace
```

If the mounted volume path is `/runpod-volume`:

```bash
bash scripts/download-models-to-volume.sh /runpod-volume project-config/model-manifest.txt /tmp/download-models-failed.txt
bash scripts/verify-volume-models.sh /runpod-volume
```

If the mounted volume path is `/workspace`:

```bash
bash scripts/download-models-to-volume.sh /workspace project-config/model-manifest.txt /tmp/download-models-failed.txt
bash scripts/verify-volume-models.sh /workspace
```

Endpoint from Docker image:

- Container image: `docker.io/ultimatech/runpod-comfyui-serverless-zimage0410:latest`
- Use the same Network Volume as the temporary pod.
- If the effective models root is not auto-detected, set `RUNPOD_MODELS_PATH` to `/runpod-volume/models`, `/runpod-volume/storage/models`, `/workspace/models`, or the verified path from the temporary pod.

Test payload:

- Use `project-inputs/runpod-test-input.json` or `project-inputs/test-payload-minimal.json`.
- This workflow does not require `input.images`.

## 7. Test the Handler Contract

Minimal payload:

```json
{
  "input": {
    "workflow": {}
  }
}
```

Real payloads should usually include a full API-exported workflow and optional `images`.

## 8. Delivery Reality

This template assumes a semi-automated workflow:

- extraction tools generate drafts
- humans verify repo grouping and model truth
- final delivery uses stable mirrored links when required
