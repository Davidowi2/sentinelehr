---

<div align="center">

# 🛡️ SentinelEHR

### Automated EHR Privacy Monitoring for Community Health Centers

*Behavioral analytics and machine learning for HIPAA compliance — 
built for Epic-based Federally Qualified Health Centers*

! `https://img.shields.io/badge/Python-3.11+-blue`
! `https://img.shields.io/badge/FastAPI-0.100+-green`
! `https://img.shields.io/badge/React-18-61DAFB`
! `https://img.shields.io/badge/PostgreSQL-15-blue`
! `https://img.shields.io/badge/Status-Prototype-orange`

</div>

---

## The Problem

Community health centers using Epic EHR generate 
thousands of patient record access events every day. 
A nurse checking records outside her patient panel. 
A billing clerk exporting hundreds of files before 
resigning. A terminated employee whose account was 
never deactivated.

These violations happen continuously. The average 
HIPAA breach goes undetected for over 200 days.

Current practice at most FQHCs: a compliance officer 
manually samples audit logs once a month. That is 
checking 10 pages of a 10,000-page book.

---

## The Solution

SentinelEHR automates the entire privacy surveillance 
pipeline — from raw Epic Clarity audit logs to a 
ranked, explainable alert dashboard.

It learns what normal access looks like for every 
employee. When behavior deviates — wrong patients, 
wrong hours, bulk exports, VIP record access — it 
scores the deviation and surfaces the most anomalous 
activity for human review.

A compliance officer opens one dashboard each morning 
and sees exactly who to investigate, why, and how 
urgently. No PHI ever leaves Epic.

---

## Performance (90-Day Simulation)

| Metric | Result |
|--------|--------|
| Audit events processed | 405,168 |
| Employees monitored | 80 |
| Active security signals | 833 active security signals (Critical: 184, High: 321, Medium: 328) |
| False positive reduction (ML) | 400 low-confidence alerts suppressed through ML scoring |
| Injected threat actors detected | all four detected with mean scores 0.51-0.83 |
| Threat types caught | Bulk Export, VIP Snooping, Off-Hours, Cross-Department |

---

## Detection Capabilities

**7 behavioral rules:**

| Rule | Description |
|------|-------------|
| R1 Panel Violation | Access to patients outside assigned care panel |
| R2 Volume Spike | Daily access count exceeds 2σ above personal baseline |
| R3 Off-Hours Access | Significant access outside normal shift hours |
| R4 VIP Access | Any access to sensitive records without care relationship |
| R5 Cross-Department | Access to patients across unrelated clinic locations |
| R6 Bulk Export/Print | Unusual volume of data export events |
| R7 Break-Glass Abuse | Emergency override used beyond baseline frequency |

**Multi-layer detection:**
- Rules fire independently but require 2+ triggers before alerting (Rule of 3)
- Isolation Forest ML layer scores all behavioral patterns
- Alerts ranked by combined severity + anomaly score
- Human-readable explanations — no PHI, no black boxes

---

## Architecture
Epic Clarity DB (SQL) 
│ 
▼ 
ingestion_pipeline.py    ← polls Clarity, normalizes, loads SQLite 
│ 
▼ 
baseline_calculator.py   ← builds behavioral profiles per employee 
│ 
▼ 
rules_engine.py          ← applies 7 detection rules, generates alerts 
│ 
▼ 
anomaly_detector.py      ← Isolation Forest scoring, alert re-ranking 
│ 
▼ 
alert_manager.py         ← lifecycle management, priority ranking 
│ 
▼ 
api.py (FastAPI)         ← REST API serving the dashboard 
│ 
▼ 
dashboard/ (React)       ← compliance officer interface 

**Database:** SQLite (zero-config, single-file deployment)  
**Upgrade path:** PostgreSQL for multi-site deployments  
**PHI policy:** Zero patient identifiers stored or displayed  

---

## Quick Start

**Requirements:** Python 3.11+, Node.js 18+

```bash 
# 1. Install Python dependencies 
pip install pandas numpy scikit-learn fastapi uvicorn 

# 2. Generate synthetic data (development only) 
python mock_clarity_generator.py 

# 3. Run the full pipeline 
python ingestion_pipeline.py 
python baseline_calculator.py 
python rules_engine.py 
python anomaly_detector.py 
python alert_manager.py 

# 4. Start the API 
python api.py 

# 5. Start the dashboard (new terminal) 
cd dashboard 
npm install 
npm run dev 

# 6. Open http://localhost:5173 
```

---

## Connecting to Real Epic Clarity

In production, replace the mock CSV with a direct 
Clarity database connection:

1. Obtain a read-only SQL connection string from 
    your Epic IT team (SQL Server or Oracle) 
2. Update `ingestion_pipeline.py` — replace the 
    CSV reader with a SQLAlchemy connection to 
    `CLARITY_AUDIT` and related tables 
3. Map your organization's specific table/column 
    names (minor variations exist between Epic installs) 
4. Schedule `ingestion_pipeline.py` to run nightly 
    via cron or Windows Task Scheduler 
5. Sign a Business Associate Agreement 

Implementation time for an experienced IT team: 
approximately one day.

---

## Project Structure
SentinelEHR/ 
├── mock_clarity_generator.py   # synthetic Epic data 
├── ingestion_pipeline.py       # ETL + SQLite loader 
├── baseline_calculator.py      # behavioral profiling 
├── rules_engine.py             # 7-rule detection 
├── anomaly_detector.py         # Isolation Forest ML 
├── alert_manager.py            # lifecycle + ranking 
├── api.py                      # FastAPI backend 
├── diagnostic_queries.py       # verification utilities 
└── dashboard/                  # React frontend 
├── src/ 
│   ├── App.jsx 
│   ├── main.jsx 
│   └── index.css 
└── package.json 

---

## Security Notice

This prototype runs without authentication and uses 
HTTP. It is designed for deployment on an internal 
hospital network only.

**Before any production deployment:**
- Add token-based authentication to `api.py` 
- Restrict CORS from `*` to your internal domain 
- Deploy behind HTTPS 
- Replace SQLite with PostgreSQL for scale 
- Complete a formal BAA with your legal team 

Never expose port 8000 to the public internet.

---

## Built For

This system was designed specifically for **Federally 
Qualified Health Centers** responding to HIPAA audit 
control requirements under §164.312(b).

It addresses the core need described in RFP 
**2026-02-001** (CommUnityCare, Austin TX): 
automated, real-time privacy monitoring for Epic EHR 
with proactive anomaly detection and compliance 
reporting.

---

## Roadmap

- [ ] Real Epic Clarity ODBC connector 
- [ ] Email/SMS alerting for Critical events 
- [ ] PDF report export for OCR audits  
- [ ] Multi-tenant support (multiple health centers) 
- [ ] Login and role-based access control 
- [ ] PostgreSQL migration for large deployments 
- [ ] Near-real-time syslog/CEF ingestion 
- [ ] FHIR R4 supplementary data integration 

---

## License

MIT License — free to use, modify, and deploy.

---

*SentinelEHR is a research prototype. It has not been 
validated in a clinical environment. All data in this 
repository is entirely synthetic.*
