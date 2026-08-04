
# MIB Doc Challenge — Technical Memo

**Author:** pradeepbugga · **Solution repo:** https://github.com/pradeepbugga/mib-doc-challenge

## Approach

The goal of this challenge is to build a system that automates a legacy intake system, rapidly providing 
adjudication recommendations given a collection of visa information.  This project is inherently challenging due to 
a few factors:
- the data is messy (forms are provided with a variety of distortions and damages as one would expect in practice)
- the algorithms for extraction (especially OCR) are capped to a latency of 6 seconds per PDF, no network, and limiting hardware requirements
- the adjudication rules are only partially defined in the field manual
- information within a visa packet can be conflicting 

Our approach toward this ill-defined problem is to establish ground truths then steadily build upon those truths.
Practically, this means we first prioritize page quality (i.e. machine-readable text vs scan images that require OCR), even though
that may disagree with page priority in the field manual.  An applicant name in machine readable text will be trusted for our prediction pipeilne
more than an applicant name in a scan.

This also means that we prioritize independent fields over derived fields (fields that rely on other fields).  Applicant name, species,
home world, and declared purpose (along with registry status), are indpeendent fields because there are no records in the training dataset that lack 
explicit evidence for these.  On the other hand, risk flags and fee status are both very likely derived because there are 
a number of examples in the training dataset where these fields are not mentioned yet have non-null values.  (Note: this assumption
rests on training dataset having all relevant evidence in the packet).

We show the overall pipeline below:

         
```
predict.py → packet_pipeline → per-page: quality → OCR → classify → extract
           → corroboration → derivation → adjudication
```

In this strategy, we extract fields from machine-readable layer or OCR (repairing where needed),
normalize fields against controlled vocabulary, then corroborate fields as different forms may have different values.
Finally we perform any derivation (i.e. if registry_status = EMBARGO, risk_flag = planetary_embargo) then perform adjudication 
as per the field manual policy.

For OCR, we observe a variety of distortions, namely shear, rotation, scan line tear, and blur.  We developed low latency methods
to tackle these issues.  For shear and rotation, we first detected line segments then measured angles versus a horizontal and 
vertical line reference.  For tear, we identified the leftmost (or rightmost) line segment, then flattened them to a common x coordinate.
For blur, we found that the degree of blur was too much for deblurring CV algorithms.  One idea was to generate synthetic blurs
of prefix-value possibilites for controlled vocabulary fields (i.e. purpose) then pattern match.  Unfortunately, exactly matching degree of blur
proved more difficult than expected.  For all the repair scripts, we tested OCR before and after, only accepting a repair if it proved beneficial.
The downside of these fallbacks is that they really push against the latency constraints (6 s / PDF).  

After extraction, we regex to field specific patterns then normalize the OCR value to a controlled vocabulary.  Our thresholds are chosen 
such that fields that could be catastrophic (i.e. risk_flags) are more tolerant.  

Derivation and adjudication thereafter follow combining our established field values, the field manual, and maximization of training dataset accuracy.


## Results (training set, 1,000 packets)


| Section | Score |
| --- | --- |
| Field extraction | 41.81 / 50 |
| Classification | 65.17 / 80 |
| Calibration | 13.60 / 20 |
| Missing-case penalty | −0.00 / 10 (0 missing cases) |
| **Total** | **120.58 / 150** |

Mean confidence Brier 0.1599; 26 catastrophic false approvals.

Per-field accuracy:

| Field | Accuracy | Field | Accuracy |
| --- | --- | --- | --- |
| `species_code` | 94.0% | `arrival_date` | 83.6% |
| `declared_purpose` | 91.5% | `applicant_name` | 81.4% |
| `home_world` | 90.4% | `risk_flags` | 76.6% |
| `visa_class` | 87.6% | `fee_status` | 62.7% |
| `sponsor_id` | 85.8% | | |


## With another week

The biggest loss in our pipeline is fully predicted all risk flags and fee status values.
More thought is required to understand how to approach this. 