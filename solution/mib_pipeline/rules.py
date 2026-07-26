"""Adjudication rule engine: deterministic cascade + expected-value decision layer.

The cascade encodes FIELD_MANUAL.md policy plus rules mined from the public
training labels (each mined rule has support >= 20 and 100% purity on train,
and belongs to a rule family named in the dataset spec: embargo list, sponsor
standing, fee rules, expiration windows, diplomatic exceptions).

Rung order is load-bearing and verified by a regression test
(973/1000 on true train fields, zero false approvals):
  1. visible adjudicator stamp/note override (evidence precedence #1)
  2. disqualifying risk flag        -> DENIED
  3. fee unknown                    -> NEEDS_REVIEW
  4. fee unpaid (no visible waiver) -> DENIED
  5. TRANSIT-7                      -> DENIED
  6. embargoed home world           -> DENIED (Wolf-1061c exempts DIP-1)
  7. revoked sponsor (non-DIP-1)    -> DENIED
  8. stale arrival (non-DIP-1)      -> DENIED   [MUST precede review flags]
  9. any review-only risk flag      -> NEEDS_REVIEW
 10. otherwise                      -> APPROVED
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from . import vocab


@dataclass
class CaseBelief:
    """The adjudicator's view of a case: field beliefs + document signals.

    Values are the adjudicator's *beliefs* (may be None when evidence is
    missing/untrusted), deliberately decoupled from the extraction output
    guesses that go in the submission row.
    """

    visa_class: Optional[str] = None
    fee_status: Optional[str] = None          # None = no trusted evidence
    risk_flags: frozenset = frozenset()
    sponsor_id: Optional[str] = None
    sponsor_seen: bool = False                # any trusted sponsor evidence
    sponsor_revoked_in_doc: Optional[bool] = None  # registry says revoked?
    home_world: Optional[str] = None
    arrival_date: Optional[date] = None
    receipt_date: Optional[date] = None       # packet receipt / inspection date
    arrival_hidden_only: bool = False          # arrival only in untrusted text
    # Document-level override evidence (precedence #1):
    note_approves: bool = False                # signed adjudicator approval
    note_denies: bool = False                  # adjudicator denial, not rescinded
    denial_rescinded: bool = False
    has_hardship_waiver: bool = False
    has_diplomatic_note: bool = False
    # Quality signals:
    field_confidences: dict = field(default_factory=dict)  # field -> [0,1]
    damage_score: float = 0.0                  # 0 clean .. 1 destroyed
    trap_detected: bool = False
    pages_missing_evidence: int = 0


@dataclass
class Decision:
    adjudication: str
    p_approved: float
    p_denied: float
    p_review: float
    confidence: float     # calibrated P(adjudication correct)
    reason: str
    forced: bool          # True when a hard cascade rung fired


def _flag_conf(belief: CaseBelief, flag: str) -> float:
    return belief.field_confidences.get("flag:" + flag, 1.0)


def cascade(belief: CaseBelief):
    """Deterministic policy outcome given trusted evidence.

    Returns (adjudication, reason) or (None, reason) when no rung fires
    cleanly (the probabilistic layer then decides).
    """
    flags = set(belief.risk_flags)

    # 1. Adjudicator note override (highest precedence evidence).
    if belief.note_approves and not belief.note_denies:
        return "APPROVED", "adjudicator_note_approves"
    if belief.note_denies and not belief.denial_rescinded:
        return "DENIED", "adjudicator_note_denies"

    # 2. Disqualifying flags.
    disq = flags & set(vocab.DISQUALIFYING_FLAGS)
    if disq:
        return "DENIED", "disqualifying_flag:" + "|".join(sorted(disq))

    # 3-4. Fees. An explicitly unreadable/unknown fee needs review; a packet
    # simply missing its receipt page is not a fee problem (verified on train:
    # truth fee-unknown receipts literally print "unknown").
    if belief.fee_status == "unknown":
        return "NEEDS_REVIEW", "fee_unknown"
    if belief.fee_status == "unpaid" and not belief.has_hardship_waiver:
        return "DENIED", "fee_unpaid"

    # 5. Transit visas: work authorization denied.
    if belief.visa_class == "TRANSIT-7":
        return "DENIED", "transit_visa"

    # 6. Embargoed home worlds.
    if belief.home_world in vocab.EMBARGOED_WORLDS_ALWAYS:
        return "DENIED", "embargoed_world"
    if (belief.home_world in vocab.EMBARGOED_WORLDS_NON_DIP
            and belief.visa_class != "DIP-1"):
        return "DENIED", "embargoed_world_non_dip"

    # 7. Sponsor standing (DIP-1 needs no sponsor).
    if belief.visa_class != "DIP-1":
        revoked = (
            belief.sponsor_revoked_in_doc is True
            or (belief.sponsor_id in vocab.REVOKED_SPONSORS
                and belief.sponsor_revoked_in_doc is not False)
        )
        if revoked:
            return "DENIED", "revoked_sponsor"

    # 8. Staleness (before review flags: stale packets deny even with
    # review-only flags present - verified on train).
    if belief.arrival_date is not None and belief.visa_class != "DIP-1":
        receipt = belief.receipt_date
        if receipt is not None:
            if (receipt - belief.arrival_date) > timedelta(days=vocab.STALE_DAYS):
                return "DENIED", "stale_arrival"
    if belief.arrival_date is None:
        # Missing or hidden-only arrival date -> review (manual date rule).
        return "NEEDS_REVIEW", "arrival_missing_or_hidden"

    # 9. Review-only flags.
    rev = flags & set(vocab.REVIEW_FLAGS)
    if rev:
        return "NEEDS_REVIEW", "review_flag:" + "|".join(sorted(rev))

    # 10. Clean.
    return "APPROVED", "clean"


def ev_utility(pred: str, p_a: float, p_d: float, p_r: float) -> float:
    """Per-case expected final points (x N) for a prediction, including the
    calibration cost of the Brier-optimal confidence for that prediction."""
    if pred == "APPROVED":
        raw = 8.0 * p_a - 4.0 * p_d + 1.0 * p_r
        p_correct = p_a
    elif pred == "DENIED":
        raw = 8.0 * p_d + 1.0 * p_r
        p_correct = p_d
    else:
        raw = 8.0 * p_r + 2.0 * (p_a + p_d)
        p_correct = p_r
    return 10.0 * raw - 40.0 * p_correct * (1.0 - p_correct)


def ev_decide(p_a: float, p_d: float, p_r: float):
    """Pick the adjudication maximizing expected score."""
    best = max(("APPROVED", "DENIED", "NEEDS_REVIEW"),
               key=lambda pred: ev_utility(pred, p_a, p_d, p_r))
    p_correct = {"APPROVED": p_a, "DENIED": p_d, "NEEDS_REVIEW": p_r}[best]
    return best, p_correct
