# SentinelEHR
HIPAA compliance monitoring platform for Epic Clarity environments

SentinelEHR is a behavioral analytics platform that ingests access logs from Epic Clarity, applies detection rules and ML anomaly detection, and surfaces actionable alerts for compliance teams.

---

> **Status Banner**: This project is in design partner phase — not production-ready. It has no SOC 2 certification and no HIPAA certification at this time. Multi-tenant org isolation is verified by 17 end-to-end security tests. No deployment or accuracy claims are made for production environments.

---

## What it does
SentinelEHR connects to an Epic Clarity database via a read-only extractor running inside the hospital network. It extracts only behavioral metadata (no clinical content, no patient identifiers, no PHI). The platform then runs an automated detection pipeline on that metadata to identify privacy risks.

The core detection capabilities are 8 rules (R1-R8) and Isolation Forest anomaly detection. Each detected risk becomes an alert; alerts are grouped into investigation cases, each with a 72-hour OCR (Opportunity for Corrective Action) clock for compliance tracking.

The platform is multi-tenant SaaS: each hospital's data is isolated in a dedicated PostgreSQL schema.

---

## Architecture
| Component | Description |
|-----------|-------------|
| Backend API | FastAPI application, hosted on Render |
| Database | PostgreSQL on Neon |
| Frontend Dashboard | React/Vite application, hosted on Vercel |
| Clarity Extractor | Python script (pyodbc + requests) that runs inside the hospital network |

### Data Flow
```
Hospital Network
┌─────────────────────────────────────────┐
│ Epic Clarity (SQL Server)              │
│                                         │
│ clarity_extractor.py                    │
│  └── reads 4 tables → batches 5k rows  │
└────────────────┬────────────────────────┘
                 │ HTTPS (443)
                 ▼
┌─────────────────────────────────────────┐
│ SentinelEHR API (FastAPI on Render)     │
│  └── validates batches → stores in DB   │
│                                         │
│ PostgreSQL (Neon)                       │
│  └── multi-tenant schemas               │
│                                         │
│ Detection Pipeline                      │
│  └── baseline + rules + anomaly → cases │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Dashboard (React/Vite on Vercel)        │
└─────────────────────────────────────────┘
```

---

## Repository layout
```
SentinelEHR/
├── api.py                      # FastAPI backend (REST endpoints for ingestion/dashboard)
├── db.py                       # Database connection and schema definitions
├── case_logic.py               # Investigation case creation/management
├── alert_manager.py            # Alert lifecycle and prioritization
├── rules_engine.py             # Rule-based detection (R1-R8)
├── anomaly_detector.py         # Isolation Forest ML anomaly detection
├── baseline_calculator.py      # Employee behavioral baseline generation
├── auto_case_creator.py        # Automatically converts alerts to cases
├── breach_risk_scorer.py       # Risk scoring for alerts/cases
├── clarity_extractor.py        # Hospital-side Epic Clarity extractor
├── email_service.py            # Email notifications (alerts, OCR reminders)
├── seed_users.py               # Utility: seed initial users/organizations
├── setup_db.py                 # Utility: initialize PostgreSQL database
├── setup_cases.py              # Utility: populate test cases
├── step1_and_2.py              # Diagnostic utility
├── dashboard/                  # React/Vite frontend
│   ├── src/
│   │   ├── App.jsx             # Legacy frontend app
│   │   ├── AppV2.jsx           # Production frontend app (main entry)
│   │   └── main.jsx            # Vite bootstrap
│   └── package.json
├── mock_clarity_v2/            # Synthetic Epic Clarity data generator (local dev)
│   ├── generator.py
│   └── ingestion_pipeline_v2.py
├── DEPLOYMENT.md               # Full hospital IT deployment guide
├── QUICKSTART.md               # 10-minute extractor runbook
├── DEVLOG.md                   # Full development history
├── config.example.json         # Extractor config template
├── requirements.txt            # Python dependencies
└── render.yaml                 # Render deployment config
```

---

## Quick start (for developers)
### Requirements
- Python 3.11+
- Node.js 18+
- PostgreSQL database (local or Neon)

### Local development setup
```bash
# 1. Clone the repo
git clone https://github.com/your-org/sentinellehr.git
cd sentinellehr

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Set up PostgreSQL (local or Neon)
# Edit db.py to point to your database URL
python setup_db.py

# 4. Seed test data (optional)
python seed_users.py
python setup_cases.py

# 5. Start the backend API
python api.py

# 6. Start the frontend (new terminal)
cd dashboard
npm install
npm run dev

# 7. Open http://localhost:5173
```

For hospital-side extractor installation, see `QUICKSTART.md` and `DEPLOYMENT.md`.

---

## Detection pipeline
The detection pipeline runs automatically after each batch of audit events is ingested:

1. **Baseline calculation** (`baseline_calculator.py`)
   - Computes 30-day behavioral baselines per employee
2. **Rule-based detection** (`rules_engine.py`)
   - Applies 8 rules (R1-R8) to audit events
3. **Anomaly detection** (`anomaly_detector.py`)
   - Isolation Forest scores events for deviation from baselines
4. **Risk scoring** (`breach_risk_scorer.py`)
   - Combines rule severity and anomaly score into overall risk
5. **Case creation** (`auto_case_creator.py`)
   - Groups related alerts into investigation cases
   - Starts 72-hour OCR clock per case

---

## Database
The PostgreSQL database uses multi-tenant schemas (one schema per organization). Core tables:

| Table | Purpose |
|-------|---------|
| organizations | Org metadata (name, API key, settings) |
| users | User accounts (compliance officers, admins) |
| employees | Employee metadata (role, department, shift hours) |
| patients | Patient flags (VIP, sensitive) — no identifiers |
| patient_panels | Care panel relationships (employee ↔ patient) |
| audit_events | Ingested access log events (no PHI) |
| alerts | Detected privacy risks |
| cases | Investigation cases (groups of related alerts) |
| sync_state | Tracks last successful ingestion sync per table |
| ocr_actions | Tracks OCR activity and 72-hour clock status |

For full schema details, see `setup_db.py`.

---

## Security
- Passwords hashed using bcrypt
- JWT authentication with 8-hour expiry
- Account lockout after 10 failed login attempts
- Rate limiting on all critical API endpoints
- Separate API keys for extractor vs. dashboard users
- Extractor uses only read-only access to Epic Clarity
- No PHI transmitted or stored — only behavioral metadata
- Multi-tenant org isolation verified by automated tests

SOC 2 certification is on the 12-month roadmap.

---

## Documentation
- `DEPLOYMENT.md`: Full installation/operations guide for hospital IT teams
- `QUICKSTART.md`: 10-minute extractor runbook
- `DEVLOG.md`: Full development history (Phases 0-14)
- `mock_clarity_v2/README.md`: Synthetic Epic data generator for local testing

---

## Development status
### Done
- Detection engine (8 rules + Isolation Forest)
- Multi-tenant SaaS architecture with org isolation
- Frontend dashboard (alert queue, case investigation, OCR clock)
- Ingestion API with batch dedup and streaming extractor
- Admin panel (org/user management)
- Email alerting

### Not done (design partner phase)
- SOC 2 certification
- Real hospital deployments (design partners only)
- Public marketing site polish

---

## License and contact
- License: All rights reserved
- Contact: [placeholder support email]
