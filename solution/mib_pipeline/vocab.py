"""Closed vocabularies for the MIB intake domain.

Categorical vocabularies come from the public FIELD_MANUAL.md plus the public
training labels (data/train_labels.csv). They are domain lexicons learned from
public training data - allowed by the challenge rules and disclosed in MEMO.md.
Nothing here is keyed to a case id.
"""

SPECIES = [
    "ALPHA_DRACONIAN",
    "ANDROMEDAN",
    "AQUARIAN_MANTIS",
    "ARCTURIAN",
    "CENTAURI_SYNTH",
    "JOVIAN_GASFORM",
    "KAIJU_MICRO",
    "LUNA_SECURID",
    "ORION_GRAYS",
    "SIRIUS_AVIAN",
    "TRIANGULAN",
    "VENUSIAN_MYCELIAL",
]

HOME_WORLDS = [
    "Barnard-c",
    "Eris Relay",
    "Europa Station",
    "Gliese-581g",
    "Kepler-186f",
    "Luyten-b",
    "Mars Dome-7",
    "Proxima-b",
    "Sirius Outpost",
    "Titan Freeport",
    "TRAPPIST-1e",
    "Wolf-1061c",
    "Zeta Reticuli",
]

VISA_CLASSES = ["XW-1", "XW-2", "DIP-1", "MED-3", "TRANSIT-7"]

PURPOSES = [
    "archive audit",
    "cultural exchange",
    "diplomatic",
    "field repair",
    "medical consult",
    "reactor maintenance",
    "research",
    "translation",
    "transit",
    "xenobotany",
]

FEE_STATUSES = ["paid", "waived", "unpaid", "unknown"]

DISQUALIFYING_FLAGS = [
    "memory_tampering",
    "planetary_embargo",
    "active_warrant",
    "biohazard_red",
]

REVIEW_FLAGS = [
    "identity_conflict",
    "sponsor_mismatch",
    "illegible_biometrics",
    "rescinded_denial",
]

RISK_FLAGS = DISQUALIFYING_FLAGS + REVIEW_FLAGS

# Sponsors listed as revoked in FIELD_MANUAL.md.
REVOKED_SPONSORS_MANUAL = {"SPN-0007", "SPN-0139", "SPN-4040"}

# Additional revoked sponsors mined from training labels (the manual says
# "Other revoked sponsors may appear in examples"). Each appears 13-20x in
# train with a dominant DENIED outcome; regular sponsors appear 1-2x.
# In-document revocation evidence, when present, takes precedence over this
# fallback list at runtime.
REVOKED_SPONSORS_MINED = {"SPN-7331", "SPN-2718", "SPN-9090"}

REVOKED_SPONSORS = REVOKED_SPONSORS_MANUAL | REVOKED_SPONSORS_MINED

# Home worlds under blanket embargo in training data. TRAPPIST-1e and
# Eris Relay always carry the planetary_embargo risk flag (72/72 embargo
# cases denied). Wolf-1061c is embargoed for everything except DIP-1.
EMBARGOED_WORLDS_ALWAYS = {"TRAPPIST-1e", "Eris Relay"}
EMBARGOED_WORLDS_NON_DIP = {"Wolf-1061c"}

ADJUDICATIONS = ["APPROVED", "DENIED", "NEEDS_REVIEW"]

# Applications are stale if arrival is more than this many days before the
# packet receipt date (FIELD_MANUAL.md date rules). DIP-1 with a valid
# diplomatic note is exempt.
STALE_DAYS = 180
