# Delivery Checklist

Before handing the endpoint to a client, verify all of the following.

- The repository README matches the final deployment method.
- `.runpod/hub.json` has real project title, description, GPU, disk, and env values.
- The client has at least one known-good request payload.
- The client knows to read results from `output.images[]`.
- Base64 outputs can be decoded with `scripts/extract-runpod-media.py`.
- If large video output is expected, S3 upload settings are documented.
- The exact volume preparation commands were tested on a temporary pod.
- The final endpoint was tested with at least one minimal payload and one representative payload.
- If shared runtime dependencies changed, a separate test image tag was validated before promoting the production tag.
- If shared runtime dependencies changed, at least two workflows were regression-tested before delivery.
- Rollback information exists: git tag, commit hash, or release reference.
