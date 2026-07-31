# Solution Repository

Public repository:

https://github.com/NiketKakkar03/mib-doc-solution

Suggested reviewer entry points:

- `Dockerfile`: defines the offline submission image
- `run.sh`: evaluator-compatible container entrypoint
- `solution.py`: main OCR, extraction, adjudication, and JSONL writer
- `MEMO.md`: technical approach, failure modes, and improvement plan
- `reports/training-evaluation.json`: local public training-set evaluation
- `tests/test_solution.py`: targeted regression coverage
