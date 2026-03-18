# SOP Runbook

## Inputs You Need

- API-exported workflow JSON
- reference input files or image URLs
- model download sources
- custom node repositories or registry names
- expected output format

## Required Checks Before Build

- run `scripts/verify-project-readiness.sh`
- confirm every required node is in `project-config/custom-nodes.txt`
- confirm every required model is in `project-config/model-manifest.txt` or explicitly marked as preloaded

## Required Checks Before Endpoint Creation

- confirm the temporary pod and endpoint use the same Network Volume
- confirm the actual mount path in the temporary pod
- confirm the volume contains the expected model files

## Required Checks After Endpoint Creation

- confirm startup logs show the detected models root
- confirm a known-good payload returns media in `output.images[]`
- confirm large outputs use S3 if base64 is too large
