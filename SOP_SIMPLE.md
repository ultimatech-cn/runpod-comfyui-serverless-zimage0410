# SOP Simple

1. Collect the client workflow, sample inputs, model sources, and custom node sources.
2. Fill `templates/serverless-project/00_project-intake.md`.
3. Extract a draft dependency list, then manually verify node repos and real model sources.
4. Mirror unstable LoRA files to your own Hugging Face repo when needed.
5. Update `project-config/custom-nodes.txt` and `project-config/model-manifest.txt`.
6. Run `scripts/verify-project-readiness.sh`.
7. Build the image locally.
8. Mount the target volume in a temporary pod and run `scripts/download-models-to-volume.sh`.
9. Verify the volume with `scripts/verify-volume-models.sh`.
10. Create the endpoint and mount the same volume.
11. Test with at least one minimal payload and one representative payload.
12. Deliver the endpoint with request and output examples.
