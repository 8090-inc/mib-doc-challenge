# Submission (mkoker)

Solution repo: https://github.com/mkoker/mib-doc-solution

Dockerfile is at the repo root. The image takes exactly two args, input dir and
output path, runs fully offline on CPU, and comes in well under the limits (257 MB
image, ~14 MB of model weights, 1.7s per PDF measured on 4 vCPU).

To reproduce: docker build the repo, then run it per DOCKER_SUBMISSION.md, or use
scripts/run_docker_submission.py from the challenge repo.

The predictions.jsonl in this folder came from that image (tag submission-v3) run
over data/validation with the official runner.
