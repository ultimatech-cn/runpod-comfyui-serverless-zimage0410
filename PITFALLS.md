# Common Pitfalls

## Volume Mount Path Changes Between Environments

Temporary pods and serverless endpoints may mount the same Network Volume at different paths.

Common examples:

- temporary pod: `/workspace`
- endpoint: `/runpod-volume`

Do not assume one mount path. Verify it in the live container.

## Customer-Preloaded Models May Not Be Under `/runpod-volume/models`

Some customer images keep ComfyUI under paths such as:

- `/workspace/ComfyUI/models`
- `/workspace/runpod-slim/ComfyUI/models`
- `/workspace/models`

This template detects common locations, but you still need to verify the actual files on disk.

## Custom Node Failure Is Not the Same as Missing Model Failure

Typical symptoms differ:

- missing node: `Cannot execute because node ... does not exist`
- missing model: ComfyUI loads the workflow but fails during node execution or model lookup

Check node installation and model presence separately.

## BOM and Encoding Problems Break Manifests

`custom-nodes.txt` and `model-manifest.txt` must be plain UTF-8 text without BOM.

If a build fails on the first line of a manifest, check encoding before changing logic.

## Docker Build Context Omissions

If Docker cannot find a script during `COPY`, the file is missing from the build context or excluded by `.dockerignore`.

Do not debug runtime logic until the image contents are confirmed.

## History With No Outputs

If the handler reports `No outputs found in history`, verify all of the following:

- the workflow has a real output node
- the output node writes images or video, not only temp artifacts
- the workflow actually finished, instead of failing silently upstream

## Base64 Video Responses Can Be Too Large

Large video outputs may exceed practical memory limits for base64 responses.

Use S3-compatible upload configuration for large outputs.

## Windows Paths in Workflow JSON

API-exported workflows can still contain backslashes or Windows paths. Normalize them before deployment.

## Do Not Assume the Download Script Alone Is Proof

A successful download script run does not guarantee the endpoint can see the same files.

Always verify:

- the mounted path
- the model count
- key model filenames
- endpoint startup logs
