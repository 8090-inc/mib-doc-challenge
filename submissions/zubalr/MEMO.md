# MIB Doc Challenge: Technical Memo

## Result

Two figures are reported, because they answer different questions.

| Measurement | Total |
| --- | ---: |
| Full public training set, final Docker image | 133.93 / 150 |
| Repeated out-of-fold estimate, 10 fold assignments | **128.53 / 150, SE 0.16** |

| Section | Out of fold | Training set |
| --- | ---: | ---: |
| Extraction | 44.15 / 50 | 44.16 / 50 |
| Classification | 67.88 / 80 | 72.69 / 80 |
| Calibration | 16.50 / 20 | 17.07 / 20 |
| Mean confidence Brier | 0.0874 | 0.0732 |

The training-set figure is the shipped Docker image scored on all 1,000 labeled
packets with the official evaluator. It is fully reproducible, and it is
in-sample: the model was fitted on those rows.

The out-of-fold figure is the estimate to use for unseen packets. Every held-out
prediction comes from a model that did not train on that packet, averaged over
ten independent fold assignments. The gap between the two figures is in-sample
optimism, so the larger number should not be read as an expected score.

Extraction is nearly identical under both, as expected: it does not depend on
the model.

## Scoring behavior

The evaluator informed three implementation choices.

First, every input packet must produce a record. A missing record forfeits its
extraction and classification denominator, so processing failures return a
schema-valid fallback instead of dropping the case.

Second, blank fields have no scoring advantage over incorrect fields.
Unresolved fields therefore receive conservative printable defaults. Those
defaults are kept separate from policy evidence, so a guessed field cannot
justify an approval.

Third, adjudication uses the published payoff matrix directly. For class
probabilities `a`, `d`, and `r`, the expected raw scores are:

```text
APPROVED:      8a - 4d + r
DENIED:        8d + r
NEEDS_REVIEW:  2a + 2d + 8r
```

The selected action is the expected-value maximum. Reported confidence is the
probability assigned to that action.

## Evidence extraction

PDF processing starts with PyMuPDF span extraction. Every observation records
its page type, source type, visibility, extraction method, and trust rank.
Resolution follows the source precedence in the field manual.

Pages without a reliable text layer are rendered and processed locally with
Tesseract. Multiple page segmentation modes are merged because sparse forms,
single-line notes, and dense blocks require different OCR layouts. Field
parsers then apply structural validation before a value can enter the evidence
set.

Most categorical fields have small, fixed vocabularies. OCR output is matched
with weighted edit distance that gives lower cost to common glyph confusions
such as `0/O`, `1/I`, and `5/S`. Values outside a safe threshold remain
unmatched instead of being forced onto a known token.

## Adversarial content

Hidden content is classified from PDF structure rather than keywords alone.
The parser checks text rendering mode, opacity, foreground and background
colors, and position relative to the visible crop.

The pipeline also distinguishes visible evidence from visible instructions.
Barcode payloads and prompt-like directives do not become field evidence or
policy commands. Their presence may be recorded as a document-quality feature,
but their contents are quarantined.

This separation is preserved during OCR. Rendering a page does not make hidden
white or transparent text visible, and visible instructional payloads remain
excluded by source and content rules.

## Adjudication

High-confidence policy evidence is handled deterministically. Examples include
an explicit adjudicator finding, a disqualifying risk flag, and a transit-class
rule. Missing or unreadable evidence is represented explicitly rather than
treated as a clean result.

Cases without a decisive rule use a calibrated histogram gradient-boosting
classifier. Its inputs describe extracted evidence, coverage, page structure,
OCR quality, document damage, temporal margins, and the deterministic path
prior. It does not receive a case ID, filename, or hidden answer content.

The fitted classifier is blended with the deterministic path distribution.
This retains the stability of the policy prior while allowing the model to
separate cases that share a coarse path. If the model artifact cannot be
loaded, the deterministic policy remains a functional fallback.

Training excludes cases settled by an explicit adjudicator note because those
cases never reach model inference. Model selection uses the challenge
classification and calibration objective on held-out predictions.

## Generalization checks

The validation corpus contains 5,000 unlabeled packets. Schema validation
confirmed one output per input with no missing cases.

Closed-vocabulary coverage remained stable between the labeled and unlabeled
corpora for species, home world, visa class, declared purpose, fee status, and
risk flags. Applicant-name combinations changed substantially, while component
token coverage remained stable. This supports token-level matching without
assuming that complete names repeat.

Confidence and fallback distributions were also compared between corpora.
The unlabeled set contains more damaged packets, which increases conservative
fallbacks without changing the evidence hierarchy.

## Limitations

Some packet fields are absent, contradictory, or unreadable. The pipeline
reports defaults for schema completeness but does not promote those defaults to
evidence. This is especially important for risk flags and fee status, where
absence of a readable page is not evidence of a clean record.

The learned adjudicator is intentionally small and regularized. It improves
probability estimates within unresolved policy paths, but it cannot recover
evidence that is not present in the packet.

## Reproducibility

The runtime is fully offline and uses pinned dependencies. The Docker image
contains PyMuPDF, Tesseract, NumPy, and scikit-learn. No LLM, VLM, cloud OCR
service, network request, or API key is used.

`tools/check_env.py` verifies that the training and runtime scikit-learn
versions match. `tools/verify_image.py` verifies that the built image contains
the current source and policy artifacts. The test suite covers visibility
classification, OCR parsing, vocabulary matching, schema validation, and
end-to-end output generation.
