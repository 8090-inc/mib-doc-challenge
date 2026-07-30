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


class EVModel:
    def __init__(self, artifact):
        self.tables = artifact["tables"]        # rule_key -> {class: p}
        self.prior = artifact["prior"]          # global {class: p}
        self.note_conf = float(artifact.get("note_conf", 0.99))
        self.conf_lo = float(artifact.get("conf_lo", 0.03))
        self.conf_hi = float(artifact.get("conf_hi", 0.99))

    def probs_for(self, reason):
        return self.tables.get(rule_key(reason), self.prior)

    def decide(self, rule_adj, rule_conf, rule_reason):
        rk = rule_key(rule_reason)
        if rk in _NOTE_KEYS:
            return rule_adj, round(self.note_conf, 3), rule_reason
        probs = self.probs_for(rule_reason)
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


def apply(rule_adj, rule_conf, rule_reason):
    """EV overlay entry point; identity function when no artifact shipped."""
    m = load()
    if m is None:
        return rule_adj, rule_conf, rule_reason
    return m.decide(rule_adj, rule_conf, rule_reason)
