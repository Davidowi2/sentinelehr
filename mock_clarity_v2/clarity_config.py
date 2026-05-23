from datetime import datetime

# ── SIMULATION SETTINGS ──────────────────────────────────────
SEED = 42
NUM_DAYS = 90
START_DATE = datetime(2026, 1, 1)
NUM_EMPLOYEES = 80
NUM_PATIENTS = 5000

# ── EPIC ACTION CODES (ZC_ACS_ACTION) ────────────────────────
# These are the real action names Epic uses internally.
# CONFIRMED: _C suffix convention. Names reconstructed from
# Epic's public Audit Trail Viewer documentation.
ACTION_CODES = {
    1: {"NAME": "In Chart", "ABBR": "IC"},
    2: {"NAME": "Chart Review", "ABBR": "CR"},
    3: {"NAME": "Open Chart", "ABBR": "OC"},
    4: {"NAME": "Print Chart", "ABBR": "PC"},
    5: {"NAME": "Export Data", "ABBR": "ED"},
    6: {"NAME": "Break Glass", "ABBR": "BG"},
    7: {"NAME": "Search", "ABBR": "SR"},  # search hit - NOT an open
    8: {"NAME": "Edit Note", "ABBR": "EN"},
    9: {"NAME": "Sign Order", "ABBR": "SO"},
    10: {"NAME": "View Result", "ABBR": "VR"},
    11: {"NAME": "Chart Close", "ABBR": "CC"},
}

# Action 7 (Search) means patient appeared in search results.
# The user did NOT open the record.
# Our rules engine MUST exclude Action 7 from access counts.
SEARCH_ACTION_C = 7
OPEN_ACTION_C = 3

# ── ROLE DEFINITIONS ─────────────────────────────────────────
ROLES = {
    "Physician": {
        "count": 15,
        "panel_size": (150, 300),
        "shift_start": 7,
        "shift_end": 18,
        "off_hours_prob": 0.08,
        "action_weights": {
            1: 0.25, 2: 0.20, 3: 0.20, 4: 0.05, 5: 0.03, 6: 0.03, 
            7: 0.10, 8: 0.05, 9: 0.04, 10: 0.04, 11: 0.01
        }
    },
    "Nurse": {
        "count": 20,
        "panel_size": (80, 200),
        "shift_start": 7,
        "shift_end": 19,
        "off_hours_prob": 0.10,
        "action_weights": {
            1: 0.30, 2: 0.15, 3: 0.20, 4: 0.08, 5: 0.03, 6: 0.03, 
            7: 0.08, 8: 0.05, 9: 0.03, 10: 0.04, 11: 0.01
        }
    },
    "Float_Nurse": {
        "count": 8,
        "panel_size": (20, 60),
        "shift_start": 6,
        "shift_end": 22,
        "off_hours_prob": 0.15,
        "action_weights": {
            1: 0.30, 2: 0.15, 3: 0.20, 4: 0.07, 5: 0.03, 6: 0.02, 
            7: 0.10, 8: 0.05, 9: 0.03, 10: 0.04, 11: 0.01
        }
    },
    "MA": {
        "count": 15,
        "panel_size": (40, 120),
        "shift_start": 8,
        "shift_end": 17,
        "off_hours_prob": 0.05,
        "action_weights": {
            1: 0.35, 2: 0.10, 3: 0.25, 4: 0.10, 5: 0.02, 6: 0.01, 
            7: 0.08, 8: 0.04, 9: 0.02, 10: 0.02, 11: 0.01
        }
    },
    "Scheduler": {
        "count": 10,
        "panel_size": (10, 40),
        "shift_start": 8,
        "shift_end": 17,
        "off_hours_prob": 0.03,
        "action_weights": {
            1: 0.40, 2: 0.05, 3: 0.30, 4: 0.05, 5: 0.01, 6: 0.005, 
            7: 0.12, 8: 0.02, 9: 0.01, 10: 0.01, 11: 0.005
        }
    },
    "Billing": {
        "count": 12,
        "panel_size": (5, 20),
        "shift_start": 8,
        "shift_end": 17,
        "off_hours_prob": 0.02,
        "action_weights": {
            1: 0.35, 2: 0.05, 3: 0.20, 4: 0.15, 5: 0.10, 6: 0.005, 
            7: 0.10, 8: 0.02, 9: 0.005, 10: 0.01, 11: 0.005
        }
    }
}
