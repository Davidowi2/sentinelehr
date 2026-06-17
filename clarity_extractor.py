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

Schema Mapping:
    By default, the extractor queries standard Epic Clarity column names
    (USER_ID, USER_TYPE, ACCESS_LOG_ID, etc.). If your hospital's Epic
    database uses non-standard column names — which is common for community
    health centers and customized Epic deployments — add a "schema_mapping"
    section to config.json. For each table, specify the actual column name
    that corresponds to each SentinelEHR output alias. See config.example.json
    for the full format with standard Epic defaults. Run:
        python clarity_extractor.py --print-schema
    to see the effective column mapping that will be used, and:
        python clarity_extractor.py --print-schema-example
    to print a template you can paste into config.json.

Usage:
    python clarity_extractor.py
    python clarity_extractor.py --dry-run              (extract but do not send)
    python clarity_extractor.py --full-sync            (ignore last sync, send everything)
    python clarity_extractor.py --print-schema         (show effective column mapping and exit)
    python clarity_extractor.py --print-schema-example (print default mapping template and exit)

Schedule:
    Run nightly via Windows Task Scheduler or cron.
    Recommended: 2:00 AM daily during low-activity period.
"""

import os
import sys
import json
import uuid
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

# --- schema_mapping support ---
# Standard Epic Clarity column names used when no schema_mapping is configured.
# A hospital with custom column names overrides these in config.json under
# the "schema_mapping" key — only the values (Epic column names) change;
# the keys (SentinelEHR output aliases) are always fixed.
DEFAULT_SCHEMA_MAPPING = {
    'employees': {
        'table': 'CLARITY_EMP',
        'columns': {
            'emp_id':        'USER_ID',
            'role':          'USER_TYPE',
            'dept_id':       'PRIMARY_DEP_ID',
            'login_dept_id': 'DEFAULT_LOGIN_DEP_ID',
            'is_float':      'IS_FLOAT',
        }
    },
    'patient_panels': {
        'table': 'PAT_ENC',
        'columns': {
            'emp_id': 'PROV_ID',
            'pat_id': 'PAT_ID',
        }
    },
    'patients': {
        'table': 'PATIENT',
        'columns': {
            'pat_id':       'PAT_ID',
            'is_vip':       'IS_VIP',
            'is_sensitive': 'IS_SENSITIVE',
        }
    },
    'audit_events': {
        'table': 'ACCESS_LOG',
        'columns': {
            'audit_id':        'ACCESS_LOG_ID',
            'emp_id':          'USER_ID',
            'pat_id':          'PAT_ID',
            'action_c':        'ACTION_C',
            'action_datetime': 'ACCESS_INSTANT',
            'dept_id':         'DEP_ID',
        }
    },
}

# Required output aliases per table — used to validate user-supplied mappings
REQUIRED_ALIASES = {
    'employees':      {'emp_id', 'role', 'dept_id', 'login_dept_id', 'is_float'},
    'patient_panels': {'emp_id', 'pat_id'},
    'patients':       {'pat_id', 'is_vip', 'is_sensitive'},
    'audit_events':   {'audit_id', 'emp_id', 'pat_id', 'action_c', 'action_datetime', 'dept_id'},
}


def _validate_and_merge_schema_mapping(user_mapping):
    """
    Merge user-supplied schema_mapping with DEFAULT_SCHEMA_MAPPING.

    Rules:
    - If a table is absent from user_mapping, use the default and log a warning.
    - If a table is present but missing 'table' key, error out.
    - If a table is present but columns dict is missing required aliases, error out
      with a specific list of the missing aliases.
    - Returns the merged mapping dict.
    """
    merged = {}
    for tbl, default in DEFAULT_SCHEMA_MAPPING.items():
        if tbl not in user_mapping:
            log.warning(f"No schema_mapping for '{tbl}' — using standard Epic defaults")
            merged[tbl] = default
            continue

        entry = user_mapping[tbl]

        if 'table' not in entry or not entry['table']:
            log.error(f"schema_mapping.{tbl} is missing required 'table' key (the Epic table name, e.g. 'CLARITY_EMP')")
            sys.exit(1)

        if 'columns' not in entry or not isinstance(entry['columns'], dict):
            log.error(f"schema_mapping.{tbl} is missing required 'columns' dict")
            sys.exit(1)

        required = REQUIRED_ALIASES[tbl]
        provided = set(entry['columns'].keys())
        missing  = required - provided
        if missing:
            log.error(
                f"schema_mapping.{tbl}.columns is missing required output aliases: "
                f"{sorted(missing)}. Each alias must map to the actual Epic column name."
            )
            sys.exit(1)

        merged[tbl] = entry

    return merged


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

    # --- schema_mapping support ---
    # Optional — if absent, standard Epic defaults are used automatically.
    user_mapping = config.get('schema_mapping')
    if user_mapping is not None:
        log.info('schema_mapping found in config.json — validating...')
        config['schema_mapping'] = _validate_and_merge_schema_mapping(user_mapping)
        log.info('schema_mapping validated successfully')
    else:
        config['schema_mapping'] = DEFAULT_SCHEMA_MAPPING

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

    batch_id = str(uuid.uuid4())

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
                'batch_id': batch_id,
                'is_last_batch': is_last_batch
            },
            timeout=120
        )
        response.raise_for_status()
        result = response.json()
        status = result.get('status', 'unknown')
        if status == 'duplicate':
            log.info(f'[DUPLICATE] Batch {batch_num} ({batch_id}): already processed — skipping ({result.get("skipped", 0)} records)')
        else:
            log.info(f'Batch {batch_num} ({batch_id}): inserted={result.get("inserted", 0)}, skipped={result.get("skipped", 0)}, status={status}')
        return True
    except requests.RequestException as e:
        log.error(f'Failed to send batch {batch_num} ({batch_id}) to {table}: {e}')
        return False


# ─── CLARITY CONNECTION ─────────────────────────────────────────────────────
def get_clarity_connection(config):
    """
    Connect to Epic Clarity database via ODBC.

    Authentication modes:
    - SQL authentication (production): used when both 'clarity_username' and
      'clarity_password' are non-empty in config.json. Sends UID and PWD in
      the connection string. Required for production hospital deployments.
    - Windows authentication (development/testing only): used when both
      'clarity_username' and 'clarity_password' are empty strings in config.json.
      Uses Trusted_Connection=yes — the OS login of the user running the script
      is passed to SQL Server. Suitable for local testing on a Windows developer
      machine where the developer is already authenticated to the local SQL Server.
      Do NOT use this mode in production.
    """
    try:
        import pyodbc
    except ImportError:
        log.error('pyodbc not installed. Run: pip install pyodbc')
        log.error('Also install Microsoft ODBC Driver 17 for SQL Server from Microsoft.')
        sys.exit(1)

    use_sql_auth = bool(config.get('clarity_username') and config.get('clarity_password'))

    if use_sql_auth:
        # Production: SQL Server authentication with explicit credentials
        log.info('Using SQL authentication')
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config['clarity_server']};"
            f"DATABASE={config['clarity_database']};"
            f"UID={config['clarity_username']};"
            f"PWD={config['clarity_password']};"
            f"TrustServerCertificate=yes;"
        )
    else:
        # Development/testing only: Windows integrated authentication
        log.info('Using Windows authentication (Trusted_Connection) — development mode only')
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config['clarity_server']};"
            f"DATABASE={config['clarity_database']};"
            f"Trusted_Connection=yes;"
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
    Extract employee reference data.
    Table and column names are read from config['schema_mapping']['employees'].
    No personally identifiable employee information is extracted.
    """
    log.info('Extracting employee reference data...')

    # --- schema_mapping support ---
    mapping = config['schema_mapping']['employees']
    table   = mapping['table']
    cols    = mapping['columns']

    query = f"""
        SELECT
            [{cols['emp_id']}]                              AS emp_id,
            COALESCE([{cols['role']}], 'Unknown')           AS role,
            COALESCE([{cols['dept_id']}], 0)                AS dept_id,
            COALESCE([{cols['login_dept_id']}], 0)          AS login_dept_id,
            '08:00'                                         AS normal_start,
            '17:00'                                         AS normal_end,
            CASE WHEN [{cols['role']}] = 'float' THEN 1 ELSE 0 END AS is_float
        FROM [{table}]
        WHERE [{cols['emp_id']}] IS NOT NULL
    """

    # Allow config override for custom shift hours
    if config.get('shift_start'):
        query = query.replace("'08:00'", f"'{config['shift_start']}'")
    if config.get('shift_end'):
        query = query.replace("'17:00'", f"'{config['shift_end']}'")

    cursor = clarity_conn.cursor()
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


def extract_patient_panels(clarity_conn, config):
    """
    Extract care panel relationships.
    Table and column names are read from config['schema_mapping']['patient_panels'].
    No clinical content, diagnoses, or notes are extracted.
    """
    log.info('Extracting patient panel relationships...')

    # --- schema_mapping support ---
    mapping = config['schema_mapping']['patient_panels']
    table   = mapping['table']
    cols    = mapping['columns']

    query = f"""
        SELECT DISTINCT
            [{cols['emp_id']}] AS emp_id,
            [{cols['pat_id']}] AS pat_id
        FROM [{table}]
        WHERE [{cols['emp_id']}] IS NOT NULL
          AND [{cols['pat_id']}] IS NOT NULL
    """

    cursor = clarity_conn.cursor()
    cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    records = [dict(zip(columns, row)) for row in rows]

    log.info(f'Extracted {len(records)} panel relationships')
    return records


def extract_audit_events_streaming(clarity_conn, config, last_sync_at, send_callback, full_sync=False):
    """
    Stream audit log rows in chunks and pass each chunk to send_callback.
    Table and column names are read from config['schema_mapping'].

    Memory ceiling: AUDIT_CHUNK_SIZE records at any one time (~50K rows).
    For large hospitals this replaces the previous all-at-once approach which
    could allocate several GB for millions of audit events.

    send_callback signature:
        send_callback(table_name: str, records: list, is_final_table_batch: bool)
        Returns True on success, False on failure.
    """
    AUDIT_CHUNK_SIZE = 50000

    # --- schema_mapping support ---
    ae_mapping  = config['schema_mapping']['audit_events']
    ae_table    = ae_mapping['table']
    ae_cols     = ae_mapping['columns']

    pat_mapping = config['schema_mapping']['patients']
    pat_table   = pat_mapping['table']
    pat_cols    = pat_mapping['columns']

    pp_mapping  = config['schema_mapping']['patient_panels']
    pp_table    = pp_mapping['table']
    pp_cols     = pp_mapping['columns']

    emp_mapping = config['schema_mapping']['employees']
    emp_table   = emp_mapping['table']
    emp_cols    = emp_mapping['columns']

    # Determine the since-date for delta vs full sync — unchanged logic
    if full_sync or not last_sync_at:
        since = datetime.now() - timedelta(days=90)
        log.info('Full sync — extracting last 90 days')
    else:
        since = datetime.fromisoformat(str(last_sync_at))
        log.info(f'Delta sync — extracting records since {since}')

    # Pre-load lookup sets once (small tables, safe to hold in memory)
    log.info('Loading VIP and sensitive patient flags...')
    cur = clarity_conn.cursor()
    cur.execute(f"""
        SELECT [{pat_cols['pat_id']}],
               COALESCE([{pat_cols['is_vip']}], 0)       AS is_vip,
               COALESCE([{pat_cols['is_sensitive']}], 0) AS is_sensitive
        FROM [{pat_table}]
        WHERE [{pat_cols['pat_id']}] IS NOT NULL
    """)
    patient_rows = cur.fetchall()
    vip_set       = {row[0] for row in patient_rows if row[1]}
    sensitive_set = {row[0] for row in patient_rows if row[2]}
    log.info(f'Loaded {len(vip_set)} VIP patients, {len(sensitive_set)} sensitive patients')

    log.info('Loading panel relationships for in-panel derivation...')
    cur.execute(f"""
        SELECT DISTINCT [{pp_cols['emp_id']}], [{pp_cols['pat_id']}]
        FROM [{pp_table}]
        WHERE [{pp_cols['emp_id']}] IS NOT NULL
          AND [{pp_cols['pat_id']}] IS NOT NULL
    """)
    panel_set = {(row[0], row[1]) for row in cur.fetchall()}
    log.info(f'Loaded {len(panel_set)} panel relationships')

    cur.execute(f"SELECT [{emp_cols['emp_id']}] FROM [{emp_table}] WHERE [{emp_cols['emp_id']}] IS NOT NULL")
    known_emp_set = {row[0] for row in cur.fetchall()}

    # Stream the audit log in AUDIT_CHUNK_SIZE-row pages using OFFSET/FETCH NEXT
    log.info(f'Streaming [{ae_table}] in chunks...')
    total_extracted = 0
    offset = 0

    while True:
        chunk_cursor = clarity_conn.cursor()
        chunk_cursor.execute(f"""
            SELECT
                [{ae_cols['audit_id']}]        AS audit_id,
                [{ae_cols['emp_id']}]          AS emp_id,
                [{ae_cols['pat_id']}]          AS pat_id,
                [{ae_cols['action_c']}]        AS action_c,
                [{ae_cols['action_datetime']}] AS action_datetime,
                [{ae_cols['dept_id']}]         AS dept_id
            FROM [{ae_table}]
            WHERE [{ae_cols['action_datetime']}] >= ?
              AND [{ae_cols['emp_id']}] IS NOT NULL
              AND [{ae_cols['pat_id']}] IS NOT NULL
            ORDER BY [{ae_cols['audit_id']}] ASC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, (since, offset, AUDIT_CHUNK_SIZE))

        columns = [col[0] for col in chunk_cursor.description]
        records = []

        for row in chunk_cursor:
            record = dict(zip(columns, row))
            emp_id = record.get('emp_id')
            pat_id = record.get('pat_id')
            record['in_panel']            = (emp_id, pat_id) in panel_set
            record['is_vip_access']       = pat_id in vip_set
            record['is_sensitive_access'] = pat_id in sensitive_set
            record['is_known_user']       = emp_id in known_emp_set
            if record.get('action_datetime'):
                record['action_datetime'] = record['action_datetime'].isoformat()
            records.append(record)

        chunk_cursor.close()

        if not records:
            # No more rows — send final signal with is_final_table_batch=True
            log.info(f'Streaming complete. Total audit events extracted: {total_extracted:,}')
            send_callback('audit_events', [], is_final_table_batch=True)
            break

        total_extracted += len(records)
        log.info(f'  Chunk at offset {offset:,}: {len(records):,} records '
                 f'(total so far: {total_extracted:,})')

        # Determine if this chunk is the last one: fewer rows than AUDIT_CHUNK_SIZE
        is_last_chunk = len(records) < AUDIT_CHUNK_SIZE

        if not send_callback('audit_events', records, is_final_table_batch=is_last_chunk):
            log.error(f'Audit events chunk at offset {offset:,} failed — aborting')
            return False

        if is_last_chunk:
            # We know there are no more rows — exit without an extra empty query
            log.info(f'Streaming complete. Total audit events extracted: {total_extracted:,}')
            break

        offset += AUDIT_CHUNK_SIZE

    return True


# ─── MAIN PIPELINE ──────────────────────────────────────────────────────────
def send_in_batches(config, table, records, dry_run, is_final_table_batch=False):
    """Send records to API in batches of BATCH_SIZE.

    is_final_table_batch: if True, the last API batch in this call will have
    is_last_batch=True, signalling the server to update sync_state and trigger
    detection. Set this only when sending the last chunk of records for a table.
    """
    if not records:
        log.info(f'No records to send for {table}')
        return True

    total_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE
    log.info(f'Sending {len(records):,} records to {table} in {total_batches} batches')

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        is_last_api_batch = (batch_num == total_batches)
        # Only mark is_last_batch=True on the very last API call when
        # the caller has confirmed this is the final chunk for the table.
        is_last_batch = is_last_api_batch and is_final_table_batch

        success = send_batch(config, table, batch, is_last_batch, batch_num, dry_run)
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
    # --- schema_mapping support ---
    parser.add_argument('--print-schema', action='store_true',
                        help='Print the effective column mapping that will be used and exit')
    parser.add_argument('--print-schema-example', action='store_true',
                        help='Print a template schema_mapping block with standard Epic defaults and exit')
    args = parser.parse_args()

    # --- schema_mapping support: handle print flags before any connection ---
    if args.print_schema_example:
        print(json.dumps({'schema_mapping': DEFAULT_SCHEMA_MAPPING}, indent=4))
        sys.exit(0)

    if args.print_schema:
        config = load_config()
        print(json.dumps({'schema_mapping': config['schema_mapping']}, indent=4))
        sys.exit(0)

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
        # Step 1 — Employees (small reference table, all-at-once is fine)
        employees = extract_employees(clarity_conn, config)
        if not send_in_batches(config, 'employees', employees, args.dry_run,
                               is_final_table_batch=True):
            log.error('Employee sync failed — aborting')
            sys.exit(1)

        # Step 2 — Patient panels (small relationship table, all-at-once is fine)
        panels = extract_patient_panels(clarity_conn, config)
        if not send_in_batches(config, 'patient_panels', panels, args.dry_run,
                               is_final_table_batch=True):
            log.error('Panel sync failed — aborting')
            sys.exit(1)

        # Step 3 — Audit events: streamed in 50K-row chunks to bound memory usage.
        # The streaming function calls send_callback for each chunk and handles
        # the is_final_table_batch=True signal on the last chunk automatically.
        last_sync = sync_state.get('audit_events')

        def audit_send_callback(table, records, is_final_table_batch):
            return send_in_batches(config, table, records, args.dry_run,
                                   is_final_table_batch=is_final_table_batch)

        if not extract_audit_events_streaming(
                clarity_conn, config, last_sync, audit_send_callback,
                full_sync=args.full_sync):
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
