# Quick Start

## 1. Edit Project Config

Update these files first:

- `project-config/custom-nodes.txt`
- `project-config/model-manifest.txt`
- `project-inputs/workflow-api.json`
- `.runpod/hub.json`

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
