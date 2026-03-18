# SOP Simple

1. Collect the client workflow, sample inputs, model sources, and custom node sources.
2. Fill `templates/serverless-project/00_project-intake.md`.
3. Update `project-config/custom-nodes.txt` and `project-config/model-manifest.txt`.
4. Run `scripts/verify-project-readiness.sh`.
5. Build the image locally.
6. Mount the target volume in a temporary pod and run `scripts/download-models-to-volume.sh`.
7. Verify the volume with `scripts/verify-volume-models.sh`.
8. Create the endpoint and mount the same volume.
9. Test with at least one minimal payload and one representative payload.
10. Deliver the endpoint with request and output examples.
