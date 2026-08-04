# Technical Memo — MIB Doc Challenge

## Approach

This submission is a deterministic, CPU-only, offline PDF pipeline. It keeps
the tried-and-true V5 plus fold-local PR44 semantic owner, serializes all
PDFium document/page/text/render/bitmap-copy/close operations behind one
process-global reentrant lock, and adds an identity-free policy-score model
that may change confidence only. The finalizer asserts that extraction and
adjudication fields remain unchanged.

The evidence boundary is deliberate:

1. rendered pixels and Tesseract remain the primary extraction surface;
2. bounded secondary OCR may recover or challenge a weak rendered proposal;
3. native/selectable PDF text, page layout, PDF-object structure, visible
   key-like text, and OCR may propose, localize, corroborate, conflict, or
   veto; and
4. no extracted string or structural observation is accepted verbatim as
   truth or directly transcribed into a final answer.

There is no answer-key harvesting/parser/transcriber, case/hash/path/output
lookup, public-label table, competitor-prediction route, LLM, VLM, cloud OCR,
runtime network dependency, or manual per-case override. Case IDs are used
only for input/output integrity and concurrent-call matching, never as model
features.

## Evaluation Evidence

The grouped nested result is the primary generalization evidence. The
all-1,000 result is a descriptive deployment fit, not holdout evidence. The
850/150 release slice is disclosed as reused sensitivity evidence.

| Protocol | Track A | Comparator | Delta | CFA | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| Grouped nested 5x4 | `133.62002305740833` | `133.32418873300010` | `+0.29583432440823` | `1` | Primary evidence; all five outer-fold deltas are positive |
| All-1,000 deployment fit | `133.88708608605802` | `133.32418873300010` | `+0.56289735305792` | `1` | Descriptive full-public fit after selection |
| Exact-image 1,000 replay B | `133.88713553473560` | `133.32418873300010` | `+0.56294680173550` | `1` | Independent runtime replay; confidence-only variation disclosed below |
| Reused 850/150 sensitivity | `130.07338821722735` | `130.02208598566455` | `+0.05130223156280` | `0` | Previously opened/reused slice, not untouched holdout |

Replay B completed 1,000/1,000 rows with exit 0, no timeout/OOM, zero field
changes, and zero adjudication changes. Nineteen confidence floats differed
from the immutable semantic reference, changing the score by only
`+0.00004944867758`. The internal exact-output parity subgate therefore
remains `STOP_SHIP`, even though execution, validity, decisions, and score
passed; this submission does not claim byte-deterministic confidence. Replay
B prediction SHA-256 is
`b8b665749e3d715df37b7d7e4dd02b6e9bcbe37a4009a04577e0b51d426ea97e`;
its receipt SHA-256 is
`41c1837cd927f36377a538e488c237fcdfa892fdff177eeed97f92630834549a`.

## Runtime and Publication Evidence

### Generated truth-free 5,000 lifecycle

The exact image completed 5,000/5,000 strict rows through the official
wrapper in `5680.879672278` seconds, exit 0, no crash/timeout/OOM, kernel peak
`3202224128` bytes/21 PIDs, and zero observed swap. Output SHA-256 is
`b52e62e715e1caeb10d7b2290510cbb0c983a241403095aefd865df1ea0f7265`;
independent receipt SHA-256 is
`9f2f51959cd6e171149f14de56e7963dd517b3b326ea847ad82a6f8d3ab68171`.
This is synthetic lifecycle evidence only, not score or validation evidence.

### Real validation 5,000

The one authorized real-validation run passed the frozen label-free terminal
verifier:

- wrapper/container exit: `0`; timeout/crash/OOM-kill observed: `false`;
- coverage: `5,000/5,000` strict rows and unique expected IDs;
- missing/extra IDs: `0/0`;
- runtime: `18082.435871` seconds (`3.6164871742` seconds/PDF);
- prediction bytes: `1637452`;
- prediction SHA-256:
  `233cfea5a21462653e25b1744b4afdc194b8ec8efa0b3ccedbcb207e0ff79c70`;
- terminal receipt SHA-256:
  `e0f8676d875db040abeec5b1a884ac9e117e40e42b097c616bc9d1310596c7fc`.

Resource telemetry was stopped at the operator's request while the run was
live. Its observed segment was clean—kernel peak `4006785024` bytes, 23 PIDs,
zero swap/OOM/OOM-kill—but it ended about 2 hours 44 minutes before terminal.
Accordingly, full-lifecycle resource-sampling continuity and continuous
zero-swap are **not** claimed. Output identity, schema, coverage, official
validator, Docker exit, and terminal binding independently passed.

Private validation truth was not opened or used for tuning, and no validation
score is claimed.

## Exact Production Provenance

- runtime-bearing private `main` at publication:
  `2f1d3af600c78556baad5fee5f0b8c2eb2669302`;
- frozen runtime source:
  `5c70e9edb1cfd736f87f9bdab4ecf6acc45cb738`;
- frozen runtime tree:
  `ebe6ffb25e73373f3d3e6e3c339fff1a6e19cf9e`;
- official image:
  `sha256:c8d238794c6ab7c1e3963fe7f588bf17df5428d39956d9352852322ffce16f0d`
  (`589402203` bytes);
- policy model SHA-256:
  `6d1c15254429409ffa9812ffc957764628b3dfebfa2a1ceccb1df61b271c7460`.

The runtime source was committed at `2026-08-03 19:07:13 PDT`, the exact
image was created at `19:08:04 PDT`, and the real container started at
`19:57:57 PDT`, all before the August 3 Pacific-time deadline. The JSONL was
atomically published at its actual time, `2026-08-04 00:59:18 PDT`; no
timestamp was altered. Later private commits may add only release evidence
and documentation without changing the frozen runtime.

## Public Packaging

This pull request changes exactly `MEMO.md`, `SUBMISSION.md`, and the immutable
`predictions.jsonl`. The JSONL was copied byte-for-byte from the terminal
artifact; it was not regenerated, reordered, reformatted, or manually edited.
