# SentinelEHR Extractor — Quickstart
Install and run the SentinelEHR ingestion extractor in under 10 minutes on a Windows machine inside the hospital network.

For the full guide, see DEPLOYMENT.md.

---

## Prerequisites checklist
- Windows 10/11 or Windows Server 2019+
- Python 3.11+ installed
- ODBC Driver 17 for SQL Server installed
- API key from your SentinelEHR admin (looks like `hKY1Hw5j_kxupr5YPZcVhxF4tSLldldlr0Ahi33qRNJDDJIEmtzymZ4-dv5eVvSM`)
- Read-only SQL Server login `sentinelehr_readonly` with SELECT on CLARITY_EMP, PAT_ENC, PATIENT, ACCESS_LOG

---

## Phase 1: Install dependencies (2 minutes)
### Install Python
- Download: https://www.python.org/downloads/
- **Check "Add Python to PATH"** during installation

### Install ODBC Driver 17
- Download: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
- Run as Administrator, accept defaults

### Install Python packages
```powershell
pip install pyodbc requests
```

### Verify
```powershell
python --version
Get-OdbcDriver | Where-Object Name -like "*SQL Server*"
pip show pyodbc requests
```

---

## Phase 2: Place files (30 seconds)
- Put `clarity_extractor.py` and `config.example.json` in `C:\SentinelEHR\`
```powershell
cd C:\SentinelEHR\
Copy-Item config.example.json config.json
```

---

## Phase 3: Edit config (1 minute)
Open `C:\SentinelEHR\config.json` in Notepad and replace placeholders:
```json
{
  "api_key": "YOUR_API_KEY_HERE",
  "api_url": "https://sentinelehr.onrender.com",
  "clarity_server": "YOUR_CLARITY_HOSTNAME",
  "clarity_database": "Clarity",
  "clarity_username": "sentinelehr_readonly",
  "clarity_password": "YOUR_SQL_PASSWORD",
  "shift_start": "07:00",
  "shift_end": "19:00"
}
```

Save the file.

---

## Phase 4: Dry run (2 minutes)
```powershell
cd C:\SentinelEHR\
python clarity_extractor.py --dry-run
```

**Expected**: Log lines showing row counts and "Total: 38 batches would be sent".

If you see errors, jump to Common errors below.

---

## Phase 5: Live run (5-10 minutes first time, faster after)
```powershell
cd C:\SentinelEHR\
python clarity_extractor.py
```

Wait for streaming to complete. Check the SentinelEHR dashboard — alerts appear within 5 minutes.

---

## Phase 6: Schedule daily (1 minute)
1. Open Task Scheduler (`taskschd.msc`)
2. Create Basic Task
   - Name: `SentinelEHR Daily Sync`
   - Trigger: Daily at 2:00 AM
   - Action: Start a program
     - Program/script: `python`
     - Arguments: `clarity_extractor.py`
     - Start in: `C:\SentinelEHR\`
   - Finish, then in Properties check "Run whether user is logged on or not"

Done. The extractor runs every night at 2 AM.

---

## Common errors (cheat sheet)
| Error Message | Fix |
|---------------|-----|
| `Data source name not found` | Install ODBC Driver 17 |
| `Login failed for user` | Check password with your DBA |
| `multi-part identifier could not be bound` | See DEPLOYMENT.md Section 5.3 for custom schema mapping |
| `Connection timeout` | Check firewall / hostname with your DBA |
| `HTTP 401 Invalid API key` | Get correct key from your SentinelEHR admin |

---

## Done!
Extractor is now running. Check the dashboard tomorrow morning to confirm the scheduled task worked.

---

## Need help?
- Full guide: DEPLOYMENT.md
- SentinelEHR support: [placeholder]
