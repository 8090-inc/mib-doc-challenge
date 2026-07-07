# MIB Doc Challenge Submission

Thanks for submitting! Two required steps:

1. **Fill out the submission form:** <https://forms.gle/REPLACE-WITH-SUBMISSION-FORM>
   Your entry does not count until the form is submitted.
2. Complete this pull request. It should only add files under `submissions/<your-github-username>/`.

## Links

- Solution repository (public, contains a `Dockerfile`):
- Submission form: I filled it out on (date):

## Checklist

- [ ] I filled out the submission form linked above
- [ ] This PR only adds `submissions/<my-github-username>/predictions.jsonl`, `MEMO.md`, and `SUBMISSION.md`
- [ ] `predictions.jsonl` passes `scripts/validate_submission.py` against `data/validation_manifest.csv`
- [ ] My solution repository is public and includes a `Dockerfile`
- [ ] My Docker image runs offline (`--network none`) and accepts `<input_pdf_dir> <output_predictions_path>`
- [ ] My submitted runtime uses no LLMs, VLMs, cloud OCR, or network services
- [ ] Model artifacts fit the size limits in `DOCKER_SUBMISSION.md`
- [ ] No hardcoded validation answers and no manual per-case edits
- [ ] My memo describes my approach, failure modes, and what I would improve with another week
