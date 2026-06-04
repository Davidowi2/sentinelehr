# SentinelEHR — Development Log

## What This Project Is

SentinelEHR is a HIPAA compliance monitoring platform for healthcare organizations. It connects to Epic Clarity (the EHR database) and monitors employee access behavior for potential privacy violations — snooping on VIP patients, accessing records outside a care panel, off-hours access, sensitive record access (HIV, behavioral health), and more.

The system runs detection pipelines that score each access event, generates alerts ranked by severity, groups alerts into investigation cases, and provides a compliance dashboard for reviewing and documenting findings. It also tracks HIPAA breach reporting obligations with a 72-hour OCR notification countdown.

---

## Architecture

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python), hosted on Render |
| Database | PostgreSQL via Neon (serverless) |
| Frontend | React (Vite), hosted on Vercel |
| Auth | JWT access tokens + httpOnly refresh token cookies |
| Detection | Rules engine + Isolation Forest (scikit-learn) |
| Data source | Epic Clarity via `clarity_extractor.py` (runs inside hospital network) |

---

## File Reference

| File | Purpose |
|---|---|
| `api.py` | All FastAPI endpoints — auth, alerts, cases, admin, ingestion, OCR |
| `rules_engine.py` | Detects behavioral anomalies using 8 rules (R1–R8, R_SENSITIVE) |
| `anomaly_detector.py` | Isolation Forest ML scoring for each employee-day |
| `alert_manager.py` | Adjusts severity based on ML score, applies R8 override |
| `baseline_calculator.py` | Computes per-employee behavioral baselines from 90-day history |
| `auto_case_creator.py` | Automatically creates investigation cases from Critical alerts |
| `case_logic.py` | Case management helpers — create, update, note, flag overdue |
| `clarity_extractor.py` | Hospital-side script — extracts behavioral metadata from Epic Clarity and sends to API |
| `db.py` | psycopg2 connection helper |
| `email_service.py` | SendGrid integration for critical alert notifications |
| `dashboard/src/AppV2.jsx` | Main React frontend — all views and UI logic |

---

## Detection Pipeline (runs in order)

```
1. baseline_calculator.py   — recalculate behavioral baselines from fresh data
2. rules_engine.py          — apply 8 rules, generate alerts with severity
3. anomaly_detector.py      — ML scoring, update anomaly_scores table
4. alert_manager.py         — adjust severity based on ML score, R8 override
5. auto_case_creator.py     — auto-case Critical alerts not yet in a case
```

Triggered automatically after a successful `audit_events` ingest (`POST /ingest/data` with `is_last_batch: true`) and manually via `POST /admin/run-detection/{org_id}`.

---

## User Roles

| Role | Access |
|---|---|
| `compliance_officer` | Alerts, Cases, Investigate, Settings, Export, Dismiss alerts, OCR assessment |
| `it_director` | System status, Sync state, Flag cases for re-review |
| `admin` | Everything — plus org management, user creation, detection trigger |

---

## Session Log

### Phase 0 — Initial Build
- React frontend (AppV2.jsx), FastAPI backend, PostgreSQL on Neon
- Login, JWT auth, alerts table, cases table, overview dashboard
- Chart.js visualization, CSV export, case report generation

### Phase 1 — Detection Engine
- Rules engine (R1–R8, R_SENSITIVE) with severity scoring
- Anomaly detector (Isolation Forest, 10 features)
- Baseline calculator (personal + role-group baselines)
- Alert manager (ML-adjusted severity, R8 Critical override)
- Auto case creator

### Phase 2 — Multi-Org Foundation
- `organization_id` added to all core tables: `alerts`, `cases`, `employees`, `anomaly_scores`, `audit_events`, `patient_panels`, `user_baselines`
- All detection scripts updated to scope reads/writes by `org_id`
- `TRUNCATE` replaced with org-scoped `DELETE` in all scripts
- All scripts require `org_id` as CLI argument

### Phase 3 — Org Management + Ingestion API
- `organizations` table with `api_key`, `epic_connection_verified`, `last_sync_at`
- `sync_state` table tracking per-org per-table sync status
- `POST /admin/organizations` — create org, generates API key (shown once)
- `GET /admin/organizations` — list orgs with masked API key preview
- `POST /admin/organizations/{id}/rotate-key` — rotate API key
- `GET /ingest/sync-state` — API key auth, returns sync status
- `POST /ingest/data` — API key auth, batched ingestion for `audit_events`, `employees`, `patient_panels`
- Unique constraints added: `(audit_id, organization_id)`, `(emp_id, organization_id)` on employees, `(emp_id, pat_id, organization_id)` on patient_panels
- After last `audit_events` batch: auto-triggers full detection pipeline in background thread

### Phase 4 — Clarity Extractor
- `clarity_extractor.py` — standalone script for hospital IT deployment
- Connects to Epic Clarity via ODBC (read-only), extracts behavioral metadata only
- No PHI transmitted — only IDs, timestamps, boolean flags
- Sends data in 5,000-record batches to `/ingest/data`
- `--dry-run` and `--full-sync` flags
- `config.example.json` — template config (actual `config.json` gitignored)
- `config.json` and `sentinelehr_extractor.log` added to `.gitignore`

### Phase 5 — Security Hardening
- bcrypt DoS protection: password length capped at 128 chars before hash
- All `str(e)` in HTTP error responses replaced with generic messages + server-side `print()`
- subprocess `.stderr` leak removed from admin detection endpoint
- Rate limiting added to: `/auth/refresh`, `/users/change-password`, `/users/update-email`, `/users`, `/export/alerts`, `/export/case`, `/admin/run-detection`, `/admin/organizations`, `/admin/organizations/rotate-key`, `/ingest/data`
- Case status whitelist: `VALID_STATUSES = {'Open', 'Under Investigation', 'Pending HR', 'Resolved', 'Closed', 'Overdue'}`
- Pagination bounds: `GET /cases` limit 1–200, offset ≥ 0; `GET /digest` days 1–365
- `GET /users` column name fix (`user_id` → `id`, `active` → `is_active`)
- Ingest record cap: 50,000 records max per request, type-checked as list

### Phase 6 — Bug Fixes
- `R_SENSITIVE` severity: `"CRITICAL"` → `"Critical"` (was causing priority rank 5 = Suppressed instead of 1 = Critical)
- `flag_overdue_cases`: `'overdue'` → `'Overdue'` throughout, unconditional `conn.commit()`
- `alert_manager.py`: full org scoping on all SQL, transaction safety added
- Constraint migration ordering: `organization_id` column added before unique constraints referencing it
- `patient_panels` added to org_id migration loop (was missing)

### Phase 7 — IT Director + Admin Dashboard
- `GET /system/status` — returns org info, alert stats, sync state, user list (it_director + admin)
- `POST /admin/users/create` — admin creates users for any org
- `System` nav tab (it_director + admin), `Admin` nav tab (admin only)
- `SystemView` component: org info, detection summary, data sync status table, user list
- `AdminView` component: organization management, user creation form
- IT director redirects to System tab on login (skips Overview, Alerts, Cases, Investigate)

### Phase 8 — Clinical Workflow (Cases + Alerts)
**New database tables:**
- `case_notes` — threaded notes per case with `note_type` (`investigation`, `flag`, `resolution`, `system`), author role/email, timestamps
- `alert_dismissals` — audit trail for dismissed alerts with reason code
- `case_notifications` — in-app notification rows per recipient role
- `ocr_assessments` — HIPAA breach assessment with 72-hour OCR clock

**New columns on `cases`:** `it_director_flagged`, `ocr_clock_started`

**New API endpoints:**
- `POST /alerts/{id}/dismiss` — dismiss with reason, sets status = 'dismissed'
- `POST /cases/{id}/notes` — add threaded note; IT director notes trigger compliance_officer notification
- `GET /cases/{id}/notes` — fetch note thread ordered oldest → newest
- `POST /cases/{id}/flag` — IT director flags case for re-review, notifies compliance_officer
- `GET /notifications` — unread/read notifications scoped to token role + org
- `POST /notifications/read` — mark all as read
- `GET /cases/{id}/ocr-status` — OCR fields + live hours_remaining countdown
- `POST /cases/{id}/ocr-assess` — start 72hr clock (breach) or document no-breach
- `PATCH /cases/{id}/ocr-notified` — record OCR notification, inserts system note

**Frontend — alert drawer:**
- Dismiss button (compliance_officer + admin only)
- Reason dropdown + optional detail input
- Dismissed alerts: 45% opacity + grey DISMISSED badge in table
- Status filter: added 'dismissed' option

**Frontend — case drawer (complete redesign):**
- Threaded notes section replacing single textarea
- Role-colored note cards (blue = compliance, orange = IT director, grey = system)
- Add Note button appends inline without reload
- IT director: Flag for Re-Review button only (no status/outcome controls)
- Compliance officer/admin: status + outcome + Save + OCR panel
- IT director flagged banner (orange) shown at top of case
- OCR status panel with 4 states: not assessed / clock running (countdown) / notified (green) / no breach
- Amber `OCR` badge on case rows; pulses when clock is running

**Frontend — header:**
- Notification bell with red unread count badge
- Clicking marks all read and navigates to Cases

---

## Environment Variables

```
DATABASE_URL          — Neon PostgreSQL connection string
JWT_SECRET            — JWT signing secret
JWT_EXPIRE_HOURS      — Token expiry (default 8)
SENDGRID_API_KEY      — SendGrid for critical alert emails
SENDGRID_FROM_EMAIL   — From address
ALERT_EMAIL_TO        — Recipient for alert emails
ADMIN_USERNAME        — Fallback admin username
ADMIN_PASSWORD        — Fallback admin password
```

---

## Database Tables

| Table | Purpose |
|---|---|
| `users` | Auth — email, password_hash, role, org_id, lockout tracking |
| `organizations` | Multi-tenant orgs — API key, Epic connection fields, sync timestamp |
| `audit_events` | Raw EHR access log events |
| `employees` | Employee reference — role, dept, shift hours, float status |
| `patient_panels` | Provider-patient care relationships |
| `patients` | Patient flags — is_vip, is_sensitive |
| `alerts` | Detection results — severity, rules triggered, anomaly score, status |
| `cases` | Investigation cases — status, priority, outcome, OCR clock |
| `anomaly_scores` | ML scores per employee-day |
| `user_baselines` | Behavioral baselines per employee |
| `case_notes` | Threaded investigation notes |
| `alert_dismissals` | Dismissed alert audit trail |
| `case_notifications` | In-app notifications |
| `ocr_assessments` | HIPAA breach assessments |
| `sync_state` | Per-org per-table ingestion tracking |
| `refresh_tokens` | JWT refresh token store |
| `case_audit_log` | Case action history |
| `settings` | Alert severity thresholds |

---

*Last updated: June 2026*
