"""Expected-value adjudication over rule-path-conditional probabilities.

The rules engine (adjudicate.py) routes every packet down one of ~25 named
paths (its `reason` string).  Each path is a bucket of cases with an empirical
outcome mix, and the scorer pays a fixed amount per (truth, prediction) pair:

    EV[APPROVED]     = 8a - 4d + 1r
    EV[DENIED]       = 0a + 8d + 1r
    EV[NEEDS_REVIEW] = 2a + 2d + 8r

for class probabilities (a, d, r).  So once each path's outcome distribution
is measured -- by running THIS pipeline over the labeled training corpus, so
extraction error is priced into the probabilities -- the score-optimal action
per path is pure arithmetic, and the calibration-optimal confidence is the
probability of the chosen action (Brier is a proper scoring rule).

This replaces two things the rules engine did by hand: the choice of decision
per path (previously fixed at authoring time; deliberately conservative), and
the per-rule confidence constants (previously hand-tuned).  The rules engine
still does all evidence evaluation; nothing here reads the document.

Distributions are Dirichlet-smoothed toward the global outcome prior
(strength K), so a path that fired a handful of times cannot claim certainty.
Safety stays one-way and rule-anchored:

  * a signed adjudicator finding is emitted verbatim with Laplace-smoothed
    note accuracy as confidence -- the overlay never touches it;
  * a rule-level DENIED may soften to NEEDS_REVIEW but never flip to
    APPROVED, and a rule-level APPROVED may demote to NEEDS_REVIEW but never
    flip to DENIED -- EV chooses freely only where the rules chose review.

The artifact (ev_weights.json beside this file) is fitted by tools/evtrain.py
from the public training labels with out-of-fold validation; the runtime only
loads the pinned artifact and no learning happens at scoring time.  If the
artifact is missing the overlay is a no-op and the rule decision stands.
"""
import json
import os
import re

import vocab

_ARTIFACT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "ev_weights.json")

CLASSES = ("APPROVED", "DENIED", "NEEDS_REVIEW")

# PAYOFF[action][truth], transcribed from the official scorer -- including the
# off-diagonal cells (missed review = 1, conservative review = 2) that decide
# which buckets should hedge.
PAYOFF = {
    "APPROVED": {"APPROVED": 8.0, "DENIED": -4.0, "NEEDS_REVIEW": 1.0},
    "DENIED": {"APPROVED": 0.0, "DENIED": 8.0, "NEEDS_REVIEW": 1.0},
    "NEEDS_REVIEW": {"APPROVED": 2.0, "DENIED": 2.0, "NEEDS_REVIEW": 8.0},
}

# Paths emitted verbatim: the human adjudicator already ruled on the packet.
_NOTE_KEYS = ("adjudicator_note",)


def rule_key(reason):
    return reason.split(":", 1)[0]


def _ev(probs):
    return {a: sum(PAYOFF[a][t] * probs[t] for t in CLASSES) for a in CLASSES}


# ---------------------------------------------------------------------------
# Identity-free structural features for the within-path review resolver.
# Nothing here derives from names, sponsor digits, case ids, or file paths --
# only evidence quality, page composition, enum values and rule state.
# ---------------------------------------------------------------------------

_AUX_KEYS = (
    "positive_clean_flags", "uncertain_flags", "illegible_page",
    "damaged_key", "has_fee_page", "fee_page_read", "sponsor_id_trusted",
    "sponsor_corroborated", "home_world_trusted", "registry_clear",
    "registry_embargo", "note_sample", "note_rescinded", "waiver_confirmed",
    "flags_candidate_present", "flags_source_ocr", "sponsor_revoked_signal",
    "has_b13_page", "has_registry_page", "has_i8090_page",
)
_FIELD_KEYS = ("applicant_name", "species_code", "home_world", "visa_class",
               "sponsor_id", "arrival_date", "declared_purpose",
               "fee_status", "risk_flags")


def _days_from_ref(arrival, ref):
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", (arrival or "").strip())
    if not m or ref is None:
        return 0.0
    try:
        import datetime as _dt
        d = _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return float((ref - d).days)
    except ValueError:
        return 0.0


# Rule paths the featurizer one-hots (fixed order; unknown paths get the
# trailing bucket so future rules cannot shift indices).
RULE_KEYS = (
    "revoked_sponsor", "transit_visa", "unpaid_no_waiver", "stale_arrival",
    "revoked_dip_illegible", "embargo_world", "fee_unknown",
    "missing_arrival", "review_flag", "uncertain_flags", "damaged_field",
    "attested_clean", "illegible_page", "name_conflict", "sponsor_conflict",
    "unsupported_waiver", "med3_no_biometric", "insufficient_evidence",
    "fee_unverified", "consensus_clean", "unverified_clean", "clean",
    "extract_failed", "disqualifying_flag", "note_disqualifier",
)


def featurize(fields, aux, cands, rule_reason, ref):
    """Fixed-order numeric vector; see FEATURE_NAMES for the layout."""
    f = []
    rk = rule_key(rule_reason)
    for k in RULE_KEYS:
        f.append(1.0 if rk == k else 0.0)
    f.append(0.0 if rk in RULE_KEYS else 1.0)
    visa = fields.get("visa_class", "")
    for v in vocab.VISA_CLASSES:
        f.append(1.0 if visa == v else 0.0)
    f.append(1.0 if not visa else 0.0)
    fee = fields.get("fee_status", "")
    for v in vocab.FEE_STATUSES:
        f.append(1.0 if fee == v else 0.0)
    f.append(1.0 if not fee else 0.0)
    rf = fields.get("risk_flags", "")
    flags = set(rf.split("|")) if rf and rf != "none" else set()
    for fl in vocab.RISK_FLAGS:
        f.append(1.0 if fl in flags else 0.0)
    f.append(float(len(flags)))
    f.append(1.0 if rf == "none" else 0.0)
    for key in _AUX_KEYS:
        f.append(1.0 if aux.get(key) else 0.0)
    f.append(float(aux.get("n_ocr_pages") or 0))
    f.append(float(aux.get("n_unknown_pages") or 0))
    f.append(float(aux.get("n_pages") or 0))
    forms = {ft for lst in cands.values() for (_v, ft, _o) in lst}
    for ft in ("I8090", "B13", "FEE", "SPONSOR", "REGISTRY", "NOTE"):
        f.append(1.0 if ft in forms else 0.0)
    for key in _FIELD_KEYS:
        f.append(1.0 if fields.get(key) else 0.0)
        f.append(float(min(len(cands.get(key, [])), 6)))
    days = _days_from_ref(fields.get("arrival_date", ""), ref)
    f.append(days / 365.0)
    f.append(1.0 if days > 180 else 0.0)
    f.append(1.0 if not fields.get("arrival_date") else 0.0)
    return f


FEATURE_NAMES = (
    [f"path_{k}" for k in RULE_KEYS] + ["path_other"]
    + [f"visa_{v}" for v in vocab.VISA_CLASSES] + ["visa_unknown"]
    + [f"fee_{v}" for v in vocab.FEE_STATUSES] + ["fee_unresolved"]
    + [f"flag_{fl}" for fl in vocab.RISK_FLAGS] + ["n_flags", "flags_none"]
    + list(_AUX_KEYS)
    + ["n_ocr_pages", "n_unknown_pages", "n_pages"]
    + [f"page_{ft}" for ft in ("I8090", "B13", "FEE", "SPONSOR",
                               "REGISTRY", "NOTE")]
    + [x for key in _FIELD_KEYS for x in (f"has_{key}", f"pool_{key}")]
    + ["days_from_ref", "stale", "arrival_missing"]
)


def forest_proba(forest, x):
    """Average class distribution over exported decision trees.

    Trees are trained with scikit-learn offline and exported to plain JSON
    arrays; this walker (with the float32 feature cast matching sklearn's
    internal representation) is the only runtime dependency.
    """
    import numpy as np
    xv = np.asarray(x, dtype=np.float32)
    acc = [0.0, 0.0, 0.0]
    trees = forest["trees"]
    for t in trees:
        i = 0
        feat, thr = t["feature"], t["threshold"]
        left, right, val = t["left"], t["right"], t["value"]
        while feat[i] >= 0:
            i = left[i] if xv[feat[i]] <= thr[i] else right[i]
        v = val[i]
        s = sum(v) or 1.0
        for j in range(3):
            acc[j] += v[j] / s
    n = float(len(trees)) or 1.0
    # forest class order is (APPROVED, DENIED, NEEDS_REVIEW), asserted at
    # export time by the trainer.
    return {c: acc[j] / n for j, c in enumerate(CLASSES)}


class EVModel:
    def __init__(self, artifact):
        self.tables = artifact["tables"]        # rule_key -> {class: p}
        self.prior = artifact["prior"]          # global {class: p}
        self.note_conf = float(artifact.get("note_conf", 0.99))
        self.conf_lo = float(artifact.get("conf_lo", 0.03))
        self.conf_hi = float(artifact.get("conf_hi", 0.99))
        self.forest = artifact.get("forest")    # optional review resolver

    def probs_for(self, reason):
        return self.tables.get(rule_key(reason), self.prior)

    def decide(self, rule_adj, rule_conf, rule_reason,
               fields=None, aux=None, cands=None, ref=None):
        rk = rule_key(rule_reason)
        if rk in _NOTE_KEYS:
            return rule_adj, round(self.note_conf, 3), rule_reason
        probs = self.probs_for(rule_reason)
        # Within-path separation for the review-family paths: a small
        # exported forest over identity-free structural features, blended
        # with the path table.  Only ever consulted on the paths it was
        # fitted for; falls back to the table alone when inputs are absent.
        if (self.forest and rk in self.forest.get("paths", ())
                and fields is not None):
            try:
                pf = forest_proba(
                    self.forest,
                    featurize(fields, aux or {}, cands or {},
                              rule_reason, ref))
                w = float(self.forest.get("blend", 0.65))
                probs = {c: w * pf[c] + (1.0 - w) * probs[c] for c in CLASSES}
            except Exception:
                pass
        ev = _ev(probs)
        allowed = {"APPROVED": ("APPROVED", "NEEDS_REVIEW"),
                   "DENIED": ("DENIED", "NEEDS_REVIEW"),
                   "NEEDS_REVIEW": CLASSES}[rule_adj]
        # deterministic argmax; prefer the rule's own choice on exact ties.
        choice = rule_adj
        best = ev[rule_adj] if rule_adj in allowed else float("-inf")
        for a in allowed:
            if ev[a] > best + 1e-12:
                best, choice = ev[a], a
        conf = min(self.conf_hi, max(self.conf_lo, probs[choice]))
        return choice, round(conf, 3), f"ev:{rk}"


_model = None
_loaded = False


def load():
    global _model, _loaded
    if not _loaded:
        _loaded = True
        try:
            with open(_ARTIFACT) as fh:
                _model = EVModel(json.load(fh))
        except (OSError, ValueError, KeyError):
            _model = None
    return _model


def apply(rule_adj, rule_conf, rule_reason,
          fields=None, aux=None, cands=None, ref=None):
    """EV overlay entry point; identity function when no artifact shipped."""
    m = load()
    if m is None:
        return rule_adj, rule_conf, rule_reason
    return m.decide(rule_adj, rule_conf, rule_reason, fields, aux, cands, ref)
