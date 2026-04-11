# 00 Project Intake

- Project name: runpod-comfyui-serverless-zimage0410
- Client: TBD
- Goal: Deploy the `Z-IMAGE TURBO-ENHANCE BY SHUBZ` workflow as a RunPod ComfyUI serverless endpoint.
- Primary workflow type: Text-to-image generation
- Expected inputs: RunPod `input.workflow` payload; no required input images in the current workflow
- Expected outputs: Generated images returned in `output.images[]`
- Deployment target: RunPod serverless endpoint
- GPU preference: TBD
- Volume strategy: Install custom nodes in the image and place workflow models on the shared Network Volume
- S3 required: Not required initially; enable only if response payloads become too large for base64 delivery
- Known risks: Workflow-exported model names differ from some upstream source filenames; `Detail Daemon` introduces at least `matplotlib`; local Docker daemon is not currently running
- Delivery deadline: TBD
