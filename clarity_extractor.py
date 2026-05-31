#!/usr/bin/env python3
"""
SentinelEHR Clarity Extractor
==============================
This script runs inside your network and extracts behavioral access metadata
from your Epic Clarity database. It sends ONLY the following to SentinelEHR:

    - Who accessed which record type (employee ID, patient ID)
    - When the access occurred (timestamp)
    - What department they were in (department ID)
    - Whether the patient was in the employee's care panel (boolean)
    - Whether the patient is flagged as VIP (boolean)
    - Whether the patient has sensitive record flags (boolean)

No patient names, no clinical notes, no diagnoses, no medications, no financial
data, and no other PHI is extracted or transmitted.

Requirements:
    pip install pyodbc requests python-dotenv pandas

Configuration:
    Create a config.json file in the same directory as this script.
    See config.example.json for the required format.

Usage:
    python clarity_extractor.py
    python clarity_extractor.py --dry-run    (extract but do not send)
    python clarity_extractor.py --full-sync  (ignore last sync, send everything)

Schedule:
    Run nightly via Windows Task Scheduler or cron.
    Recommended: 2:00 AM daily during low-activity period.
"""

import os
import sys
import json
import argparse
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ─── LOGGING SETUP ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('sentinelehr_extractor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

# ─── CONFIGURATION ──────────────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / 'config.json'
BATCH_SIZE = 5000  # Records per API batch — reduce if network is slow


def load_config():
    """Load and validate configuration from config.json."""
    if not CONFIG_FILE.exists():
        log.error(f'Config file not found: {CONFIG_FILE}')
        log.error('Create config.json from config.example.json and fill in your values.')
        sys.exit(1)

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    required = ['api_key', 'api_url', 'clarity_server', 'clarity_database',
                'clarity_username', 'clarity_password']
    missing = [k for k in required if not config.get(k)]
    if missing:
        log.error(f'Missing required config keys: {missing}')
        sys.exit(1)

    return config


# ─── API COMMUNICATION ──────────────────────────────────────────────────────
def get_sync_state(config):
    """Get last sync timestamps from SentinelEHR API."""
    try:
        response = requests.get(
            f"{config['api_url']}/ingest/sync-state",
            headers={'X-API-Key': config['api_key']},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        state = {}
        for s in data.get('sync_state', []):
            state[s['table_name']] = s['last_sync_at']
        log.info(f"Sync state retrieved for org: {data.get('organization_name')}")
        return state
    except requests.RequestException as e:
        log.error(f'Failed to get sync state: {e}')
        sys.exit(1)


def send_batch(config, table, records, is_last_batch, batch_num, dry_run=False):
    """Send a batch of records to SentinelEHR API."""
    if dry_run:
        log.info(f'[DRY RUN] Would send {len(records)} records to {table} (batch {batch_num})')
        return True

    try:
        response = requests.post(
            f"{config['api_url']}/ingest/data",
            headers={
                'X-API-Key': config['api_key'],
                'Content-Type': 'application/json'
            },
            json={
                'table': table,
                'records': records,
                'batch_id': f'{table}_{batch_num}',
                'is_last_batch': is_last_batch
            },
            timeout=120
        )
        response.raise_for_status()
        result = response.json()
        log.info(f'Batch {batch_num}: inserted={result["inserted"]}, skipped={result["skipped"]}')
        return True
    except requests.RequestException as e:
        log.error(f'Failed to send batch {batch_num} to {table}: {e}')
        return False


# ─── CLARITY CONNECTION ─────────────────────────────────────────────────────
def get_clarity_connection(config):
    """Connect to Epic Clarity database via ODBC."""
    try:
        import pyodbc
    except ImportError:
        log.error('pyodbc not installed. Run: pip install pyodbc')
        log.error('Also install Microsoft ODBC Driver 17 for SQL Server from Microsoft.')
        sys.exit(1)

    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={config['clarity_server']};"
        f"DATABASE={config['clarity_database']};"
        f"UID={config['clarity_username']};"
        f"PWD={config['clarity_password']};"
        f"TrustServerCertificate=yes;"
    )

    try:
        conn = pyodbc.connect(conn_str, readonly=True)
        log.info(f"Connected to Clarity: {config['clarity_server']}/{config['clarity_database']}")
        return conn
    except Exception as e:
        log.error(f'Failed to connect to Clarity: {e}')
        sys.exit(1)


# ─── DATA EXTRACTION ────────────────────────────────────────────────────────
def extract_employees(clarity_conn, config):
    """
    Extract employee reference data from CLARITY_EMP.
    Columns extracted: USER_ID, role, department, shift times, float status.
    No personally identifiable employee information is extracted.
    """
    log.info('Extracting employee reference data...')
    cursor = clarity_conn.cursor()

    query = """
        SELECT
            e.USER_ID                       AS emp_id,
            COALESCE(e.USER_TYPE, 'Unknown') AS role,
            COALESCE(e.PRIMARY_DEP_ID, 0)   AS dept_id,
            COALESCE(e.DEFAULT_LOGIN_DEP_ID, 0) AS login_dept_id,
            '08:00'                         AS normal_start,
            '17:00'                         AS normal_end,
            CASE WHEN e.USER_TYPE = 'float' THEN 1 ELSE 0 END AS is_float
        FROM CLARITY_EMP e
        WHERE e.USER_ID IS NOT NULL
    """

    # Allow config override for custom shift hours
    if config.get('shift_start'):
        query = query.replace("'08:00'", f"'{config['shift_start']}'")
    if config.get('shift_end'):
        query = query.replace("'17:00'", f"'{config['shift_end']}'")

    cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()

    records = []
    for row in rows:
        record = dict(zip(columns, row))
        record['is_float'] = bool(record.get('is_float', 0))
        records.append(record)

    log.info(f'Extracted {len(records)} employee records')
    return records


def extract_patient_panels(clarity_conn):
    """
    Extract care panel relationships from PAT_ENC.
    Only extracts provider-patient encounter relationships.
    No clinical content, diagnoses, or notes are extracted.
    """
    log.info('Extracting patient panel relationships...')
    cursor = clarity_conn.cursor()

    query = """
        SELECT DISTINCT
            pe.PROV_ID  AS emp_id,
            pe.PAT_ID   AS pat_id
        FROM PAT_ENC pe
        WHERE pe.PROV_ID IS NOT NULL
          AND pe.PAT_ID IS NOT NULL
    """

    cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    records = [dict(zip(columns, row)) for row in rows]

    log.info(f'Extracted {len(records)} panel relationships')
    return records


def extract_audit_events(clarity_conn, last_sync_at, full_sync=False):
    """
    Extract access log events from ACCESS_LOG.

    What IS extracted (behavioral metadata only):
        - Employee ID (who)
        - Patient ID (which record was accessed — ID only, no content)
        - Action type code (view, print, export)
        - Access timestamp
        - Department ID
        - VIP flag (boolean)
        - Sensitive record flag (boolean)

    What is NOT extracted:
        - Patient names
        - Clinical notes or diagnoses
        - Medications or lab results
        - Financial information
        - Any PHI content fields
    """
    log.info('Extracting audit events...')
    cursor = clarity_conn.cursor()

    if full_sync or not last_sync_at:
        since = datetime.now() - timedelta(days=90)
        log.info('Full sync — extracting last 90 days')
    else:
        since = datetime.fromisoformat(str(last_sync_at))
        log.info(f'Delta sync — extracting records since {since}')

    # Build VIP and sensitive patient sets for derivation
    log.info('Loading VIP and sensitive patient flags...')
    cursor.execute("""
        SELECT PAT_ID,
               COALESCE(IS_VIP, 0)       AS is_vip,
               COALESCE(IS_SENSITIVE, 0) AS is_sensitive
        FROM PATIENT
        WHERE PAT_ID IS NOT NULL
    """)
    patient_rows = cursor.fetchall()
    vip_set = {row[0] for row in patient_rows if row[1]}
    sensitive_set = {row[0] for row in patient_rows if row[2]}
    log.info(f'Loaded {len(vip_set)} VIP patients, {len(sensitive_set)} sensitive patients')

    # Load panel relationships for in_panel derivation
    log.info('Loading panel relationships for in-panel derivation...')
    cursor.execute("""
        SELECT DISTINCT PROV_ID, PAT_ID FROM PAT_ENC
        WHERE PROV_ID IS NOT NULL AND PAT_ID IS NOT NULL
    """)
    panel_set = {(row[0], row[1]) for row in cursor.fetchall()}
    log.info(f'Loaded {len(panel_set)} panel relationships')

    # Load known employees
    cursor.execute("SELECT USER_ID FROM CLARITY_EMP WHERE USER_ID IS NOT NULL")
    known_emp_set = {row[0] for row in cursor.fetchall()}

    # Main access log query — behavioral metadata only
    query = """
        SELECT
            al.ACCESS_LOG_ID  AS audit_id,
            al.USER_ID        AS emp_id,
            al.PAT_ID         AS pat_id,
            al.ACTION_C       AS action_c,
            al.ACCESS_INSTANT AS action_datetime,
            al.DEP_ID         AS dept_id
        FROM ACCESS_LOG al
        WHERE al.ACCESS_INSTANT >= ?
          AND al.USER_ID IS NOT NULL
          AND al.PAT_ID IS NOT NULL
        ORDER BY al.ACCESS_INSTANT ASC
    """

    cursor.execute(query, (since,))
    columns = [col[0] for col in cursor.description]

    records = []
    row_count = 0

    for row in cursor:
        record = dict(zip(columns, row))

        emp_id = record.get('emp_id')
        pat_id = record.get('pat_id')

        # Derive boolean flags
        record['in_panel'] = (emp_id, pat_id) in panel_set
        record['is_vip_access'] = pat_id in vip_set
        record['is_sensitive_access'] = pat_id in sensitive_set
        record['is_known_user'] = emp_id in known_emp_set

        # Convert datetime to ISO string for JSON serialization
        if record.get('action_datetime'):
            record['action_datetime'] = record['action_datetime'].isoformat()

        records.append(record)
        row_count += 1

        if row_count % 50000 == 0:
            log.info(f'  Processed {row_count:,} access log records...')

    log.info(f'Extracted {len(records):,} audit events')
    return records


# ─── MAIN PIPELINE ──────────────────────────────────────────────────────────
def send_in_batches(config, table, records, dry_run):
    """Send records to API in batches of BATCH_SIZE."""
    if not records:
        log.info(f'No records to send for {table}')
        return True

    total_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE
    log.info(f'Sending {len(records):,} records to {table} in {total_batches} batches')

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        is_last = batch_num == total_batches

        success = send_batch(config, table, batch, is_last, batch_num, dry_run)
        if not success:
            log.error(f'Batch {batch_num} failed — aborting {table} sync')
            return False

    return True


def main():
    parser = argparse.ArgumentParser(description='SentinelEHR Clarity Extractor')
    parser.add_argument('--dry-run', action='store_true',
                        help='Extract data but do not send to API')
    parser.add_argument('--full-sync', action='store_true',
                        help='Ignore last sync timestamp and extract last 90 days')
    args = parser.parse_args()

    log.info('=' * 60)
    log.info('SentinelEHR Clarity Extractor starting')
    log.info(f'Mode: {"DRY RUN" if args.dry_run else "LIVE"}')
    log.info(f'Sync type: {"FULL" if args.full_sync else "DELTA"}')
    log.info('=' * 60)

    config = load_config()

    # Get current sync state
    sync_state = get_sync_state(config)
    log.info(f'Last audit_events sync: {sync_state.get("audit_events", "Never")}')

    # Connect to Clarity
    clarity_conn = get_clarity_connection(config)

    try:
        # Step 1 — Employees (always full sync — reference data)
        employees = extract_employees(clarity_conn, config)
        if not send_in_batches(config, 'employees', employees, args.dry_run):
            log.error('Employee sync failed — aborting')
            sys.exit(1)

        # Step 2 — Patient panels (always full sync — relationship data)
        panels = extract_patient_panels(clarity_conn)
        if not send_in_batches(config, 'patient_panels', panels, args.dry_run):
            log.error('Panel sync failed — aborting')
            sys.exit(1)

        # Step 3 — Audit events (delta sync)
        last_sync = sync_state.get('audit_events')
        events = extract_audit_events(clarity_conn, last_sync, args.full_sync)
        if not send_in_batches(config, 'audit_events', events, args.dry_run):
            log.error('Audit events sync failed — aborting')
            sys.exit(1)

    finally:
        clarity_conn.close()
        log.info('Clarity connection closed')

    log.info('=' * 60)
    log.info('Extraction complete')
    log.info('=' * 60)


if __name__ == '__main__':
    main()
