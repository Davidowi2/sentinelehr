# SentinelEHR Ingestion Pipeline Deployment Guide

For Hospital IT Teams

---

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Required SQL Server Permissions](#required-sql-server-permissions)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [First Run (Dry Run)](#first-run-dry-run)
7. [Live Run and Scheduling](#live-run-and-scheduling)
8. [Troubleshooting](#troubleshooting)
9. [Uninstallation](#uninstallation)
10. [Support and Contact](#support-and-contact)

---

## 1. Overview

### What is SentinelEHR
SentinelEHR is a behavioral analytics platform for Epic Clarity environments that detects anomalous access patterns to sensitive patient records.

### What the extractor does
The extractor is a Python script that runs inside your hospital's network. It connects to your Epic Clarity SQL Server database, extracts behavioral access metadata, batches it securely, and sends it to the SentinelEHR API over HTTPS. It performs incremental syncs after the first full sync, only sending new audit events since the last successful run.

### Extractor data sources
The extractor queries only these four tables:
| Table | Purpose |
|-------|---------|
| `CLARITY_EMP` | Employee roster and role metadata |
| `PAT_ENC` | Patient-provider encounter relationships (to determine care panels) |
| `PATIENT` | Patient sensitivity flags (VIP, sensitive record status) |
| `ACCESS_LOG` | Raw audit events of who accessed which patient record, when, and from where |

### What the extractor does NOT touch
No clinical content:
- Patient names
- MRNs
- Diagnoses
- Progress notes
- Lab results
- Medications
- Financial data

### Architecture diagram

```
┌───────────────────────────────────┐
│  Hospital Network                 │
│  ┌─────────────────────────────┐ │
│  │  Windows Machine            │ │
│  │  ┌───────────────────────┐  │ │
│  │  │  clarity_extractor.py │  │ │
│  │  └───────────┬───────────┘  │ │
│  │              │              │ │
│  └──────────────┼──────────────┘ │
│                 │              │
│  ┌──────────────▼──────────────┐ │
│  │  Epic Clarity (SQL Server)  │ │
│  └─────────────────────────────┘ │
└──────────────────┬────────────────┘
                   │
                   │ HTTPS (443)
                   │
┌──────────────────▼────────────────┐
│  SentinelEHR API                  │
│  (sentinelehr.onrender.com)       │
└──────────────────┬────────────────┘
                   │
┌──────────────────▼────────────────┐
│  SentinelEHR Backend              │
└──────────────────┬────────────────┘
                   │
┌──────────────────▼────────────────┐
│  SentinelEHR Dashboard            │
└───────────────────────────────────┘
```

---

## 2. Prerequisites

| Requirement | Details |
|-------------|---------|
| Operating System | Windows 10, Windows 11, Windows Server 2019, or later |
| Python | 3.11+ (download at https://www.python.org/downloads/) |
| ODBC Driver | Microsoft ODBC Driver 17 for SQL Server (download at https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) |
| Network Access | - To Epic Clarity SQL Server (port 1433, or custom port) <br> - Outbound HTTPS (port 443) to `https://sentinelehr.onrender.com` |
| SQL Server Login | Read‑only login to Clarity database (see Section 3) |
| API Key | SentinelEHR org API key (provided by your SentinelEHR admin) |

---

## 3. Required SQL Server Permissions

Create a SQL Server login `sentinelehr_readonly` with these permissions:

| Setting | Value |
|---------|-------|
| Authentication | SQL Server authentication (not Windows) |
| Default database | Clarity (or your Epic database name) |
| Server role | `public` |
| Database user mapping | Map to Clarity database |
| Database role | `db_datareader` |
| Explicit grants | `SELECT` on `CLARITY_EMP`, `PAT_ENC`, `PATIENT`, `ACCESS_LOG`, `ZC_ACS_ACTION` (if exists) |

### Example T-SQL Script

```sql
-- Create login (replace YOUR_PASSWORD_HERE with a strong password)
USE [master];
GO
CREATE LOGIN [sentinelehr_readonly] 
WITH PASSWORD = 'YOUR_PASSWORD_HERE';
GO

-- Create database user in Clarity
USE [Clarity];
GO
CREATE USER [sentinelehr_readonly] FOR LOGIN [sentinelehr_readonly];
GO

-- Add to db_datareader role
USE [Clarity];
GO
ALTER ROLE [db_datareader] ADD MEMBER [sentinelehr_readonly];
GO

-- Explicit grants (optional but recommended for extra safety)
USE [Clarity];
GO
GRANT SELECT ON [dbo].[CLARITY_EMP] TO [sentinelehr_readonly];
GRANT SELECT ON [dbo].[PAT_ENC] TO [sentinelehr_readonly];
GRANT SELECT ON [dbo].[PATIENT] TO [sentinelehr_readonly];
GRANT SELECT ON [dbo].[ACCESS_LOG] TO [sentinelehr_readonly];
GO
```

> **Note:** This account cannot write to Epic. It only has read access to the four tables listed. For extra peace of mind, your DBA can manually run the extractor's queries first to audit what is being accessed.

---

## 4. Installation

### 4.1 Install Python 3.11+
1. Download Python from https://www.python.org/downloads/
2. Run the installer
3. **Check "Add Python to PATH" at the beginning of the install wizard**
4. Complete the installation with default options
5. Verify the install in PowerShell:
```powershell
python --version
```
Expected output: `Python 3.11.x` or later

### 4.2 Install ODBC Driver 17 for SQL Server
1. Download the `.msi` installer for your architecture from:
   https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
2. Run the installer **as Administrator**
3. Accept all defaults
4. Verify the driver is installed:
```powershell
Get-OdbcDriver | Where-Object Name -like "*SQL Server*"
```
Or open `odbcad32.exe` from the Run dialog (`Win+R`) and check the **Drivers** tab for "ODBC Driver 17 for SQL Server".

### 4.3 Install Python dependencies
Open PowerShell as the user who will run the extractor:
```powershell
pip install pyodbc requests
```
**Known good versions from self‑pilot test:**
- `pyodbc 5.3.0`
- `requests 2.33.0`
Pandas is optional and not required.

Verify installation:
```powershell
pip show pyodbc
pip show requests
```

### 4.4 Get the extractor files
1. Place `clarity_extractor.py` and `config.example.json` into a dedicated folder, e.g., `C:\SentinelEHR\`
2. Copy the example config to the live config:
```powershell
cd C:\SentinelEHR\
Copy-Item config.example.json config.json
```

---

## 5. Configuration

### 5.1 Get your API key
Contact your SentinelEHR admin. They will provide a 64‑character API key that looks like this:
```
hKY1Hw5j_kxupr5YPZcVhxF4tSLldldlr0Ahi33qRNJDDJIEmtzymZ4-dv5eVvSM
```
**Save this securely. It will not be shown again.**

### 5.2 Edit `config.json`
Open `C:\SentinelEHR\config.json` in Notepad or your preferred editor, and fill in these fields:

```json
{
  "api_key": "YOUR_64_CHARACTER_API_KEY_HERE",
  "api_url": "https://sentinelehr.onrender.com",
  "clarity_server": "CLARITY-SQL-01",
  "clarity_database": "Clarity",
  "clarity_username": "sentinelehr_readonly",
  "clarity_password": "YOUR_SQL_PASSWORD_HERE",
  "shift_start": "07:00",
  "shift_end": "19:00"
}
```

| Field | Description |
|-------|-------------|
| `api_key` | Paste the API key from your SentinelEHR admin |
| `api_url` | **Do not change** unless instructed by SentinelEHR support |
| `clarity_server` | Hostname or IP address of your Epic Clarity SQL Server (ask your DBA) |
| `clarity_database` | Usually `Clarity`; confirm with your DBA if different |
| `clarity_username` | `sentinelehr_readonly` (the SQL login created in Section 3) |
| `clarity_password` | Password you set for the `sentinelehr_readonly` SQL login |
| `shift_start`, `shift_end` | Typical workday hours in 24‑hour format (used for anomaly detection baselines) |

> **Security note:** `config.json` contains credentials. Do not commit it to source control. Do not email it. Do not share it via chat. Store it with NTFS permissions restricted to the service account that runs the extractor.

### 5.3 (Optional) Custom schema mapping
If your Epic Clarity database uses non‑standard column names (common for customized deployments), you can override the defaults in `config.json` using the `schema_mapping` section:
1. See the standard mapping:
```powershell
python clarity_extractor.py --print-schema-example
```
2. Override only the table/column names that differ in your environment; leave the rest as defaults
3. Verify the merged mapping:
```powershell
python clarity_extractor.py --print-schema
```

---

## 6. First Run (Dry Run)

### 6.1 Open PowerShell in the extractor folder
```powershell
cd C:\SentinelEHR\
```

### 6.2 Run the dry‑run
```powershell
python clarity_extractor.py --dry-run
```
This connects to Clarity, extracts the data, and logs what it would send—but **does not POST anything to the API**.

#### Expected successful output example
```
2026-06-17 02:00:00 [INFO] ============================================================
2026-06-17 02:00:00 [INFO] SentinelEHR Clarity Extractor starting
2026-06-17 02:00:00 [INFO] Mode: DRY RUN
2026-06-17 02:00:00 [INFO] Sync type: FULL
2026-06-17 02:00:00 [INFO] ============================================================
2026-06-17 02:00:01 [INFO] Connected to Clarity: CLARITY-SQL-01/Clarity
2026-06-17 02:00:01 [INFO] Extracting employee reference data...
2026-06-17 02:00:01 [INFO] Extracted 80 employee records
2026-06-17 02:00:01 [INFO] Sending 80 records to employees in 1 batches
2026-06-17 02:00:01 [INFO] [DRY RUN] Would send 80 records to employees (batch 1)
2026-06-17 02:00:01 [INFO] Extracting patient panel relationships...
2026-06-17 02:00:02 [INFO] Extracted 8640 panel relationships
2026-06-17 02:00:02 [INFO] Sending 8640 records to patient_panels in 2 batches
2026-06-17 02:00:02 [INFO] [DRY RUN] Would send 5000 records to patient_panels (batch 1)
2026-06-17 02:00:02 [INFO] [DRY RUN] Would send 3640 records to patient_panels (batch 2)
2026-06-17 02:00:02 [INFO] Loading VIP and sensitive patient flags...
2026-06-17 02:00:03 [INFO] Loaded 107 VIP patients, 83 sensitive patients
2026-06-17 02:00:03 [INFO] Loading panel relationships for in-panel derivation...
2026-06-17 02:00:04 [INFO] Loaded 8640 panel relationships
2026-06-17 02:00:04 [INFO] Streaming [ACCESS_LOG] in chunks...
2026-06-17 02:00:14 [INFO]   Chunk at offset 0: 50000 records (total so far: 50000)
2026-06-17 02:00:24 [INFO]   Chunk at offset 50000: 50000 records (total so far: 100000)
2026-06-17 02:00:34 [INFO]   Chunk at offset 100000: 50000 records (total so far: 150000)
2026-06-17 02:00:40 [INFO]   Chunk at offset 150000: 20839 records (total so far: 170839)
2026-06-17 02:00:40 [INFO] Streaming complete. Total audit events extracted: 170,839
Total: 38 batches would be sent (1 employees + 2 patient_panels + 35 audit_events)
```

If you see errors, skip to Section 8: Troubleshooting.

### 6.3 Verify the log file
The extractor writes to `sentinelehr_extractor.log` in the current working directory. Open it and check for any `ERROR` or `WARNING` lines. The log file contains only row counts and metadata—**no PHI or patient data**—so it's safe to share with SentinelEHR support if needed.

---

## 7. Live Run and Scheduling

### 7.1 Live run
To perform a real sync (send data to the API):
```powershell
cd C:\SentinelEHR\
python clarity_extractor.py
```
The first full sync may take 10–60 minutes depending on your 90‑day audit event volume.

### 7.2 Schedule daily runs (Windows Task Scheduler)
1. Open **Task Scheduler** (`taskschd.msc`)
2. Click **Create Basic Task** on the right
3. **Name**: "SentinelEHR Daily Sync"
4. **Trigger**: Daily, at 2:00 AM (or off‑peak hours for your hospital)
5. **Action**: Start a program
   - **Program/script**: `python`
   - **Arguments**: `clarity_extractor.py`
   - **Start in**: `C:\SentinelEHR\`
6. On the final screen, check **"Open the Properties dialog for this task when I click Finish"**, then click **Finish**
7. In Properties:
   - Check **"Run whether user is logged on or not"**
   - Check **"Do not store password. The task will only have access to local computer resources."** if your service account has network access to Clarity
   - Otherwise, check **"Run with highest privileges"** if needed for network access

### 7.3 Verify the schedule
- The next morning, check the SentinelEHR dashboard's **System** tab—**Last Sync** should show today's date
- Check `sentinelehr_extractor.log` for the new run

---

## 8. Troubleshooting

| Error Message | Likely Cause | Fix |
|---------------|--------------|-----|
| `Data source name not found and no default driver specified` | Microsoft ODBC Driver 17 for SQL Server not installed | Reinstall the driver (Section 4.2) |
| `Login failed for user 'sentinelehr_readonly'` | Wrong password, SQL auth not enabled on server, or login doesn't exist | Verify password with DBA; ensure SQL Server has mixed‑mode authentication enabled; confirm login was created |
| `(pyodbc.ProgrammingError) The multi-part identifier "USER_ID" could not be bound` | Your Clarity database uses non‑standard column names | Configure `schema_mapping` in `config.json` (Section 5.3) |
| `Connection timeout expired` | Network can't reach Clarity server, or wrong hostname/port | Verify hostname/IP with DBA; check firewall rules allow outbound port 1433 from extractor host to Clarity server |
| `HTTP 401 "Invalid API key"` | Wrong `api_key` in `config.json` | Get correct key from your SentinelEHR admin |
| `HTTP 404 from /ingest/data` | Wrong `api_url` | Should be `https://sentinelehr.onrender.com` |
| `HTTP 429 "Rate limit exceeded"` | Too many API requests per minute (unlikely with default settings) | Contact SentinelEHR support |
| `[DUPLICATE] Batch ... already processed` | Network retry after a blip; batch already inserted | Normal behavior—no action needed; the `batch_id` dedup worked correctly |
| Log file not found | Ran from a directory the user can't write to | Always run from `C:\SentinelEHR\` |

---

## 9. Uninstallation

To completely remove the extractor:
1. Delete the extractor folder (e.g., `C:\SentinelEHR\`)
2. Delete the "SentinelEHR Daily Sync" task from Task Scheduler
3. Ask your DBA to drop the `sentinelehr_readonly` SQL login:
```sql
USE [master];
GO
DROP LOGIN [sentinelehr_readonly];
GO
USE [Clarity];
GO
DROP USER [sentinelehr_readonly];
GO
```
4. Inform your SentinelEHR admin to disable your org

The extractor leaves no other artifacts: no registry entries, no services, no files outside its own folder.

---

## 10. Support and Contact

| Issue | Contact |
|-------|---------|
| SentinelEHR API/account issues | [SentinelEHR Support Placeholder] |
| Epic Clarity database issues | Your hospital's Epic team / DBA |
| Network/firewall issues | Your hospital's IT network team |
| Data extraction questions | [Architecture Documentation Placeholder] |
| HIPAA/compliance questions | [Security Documentation Placeholder] |
