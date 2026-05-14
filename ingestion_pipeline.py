import sqlite3
import pandas as pd
import os
import sys
from datetime import datetime, timezone
import numpy as np

# ─── CONFIGURATION ──────────────────────────────────────────
DB_PATH = "./sentinel.db"
MOCK_DATA_DIR = "./mock_data/"
LOG_WARNINGS = []

def log_warning(msg):
    LOG_WARNINGS.append(msg)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def setup_database(conn):
    cursor = conn.cursor()
    
    # Employees Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        emp_id INTEGER PRIMARY KEY,
        role TEXT,
        dept_id INTEGER,
        normal_start INTEGER,
        normal_end INTEGER,
        is_float INTEGER
    )
    """)
    
    # Patients Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        pat_id INTEGER PRIMARY KEY,
        is_vip INTEGER,
        primary_dept_id INTEGER
    )
    """)
    
    # Patient Panels Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patient_panels (
        emp_id INTEGER,
        pat_id INTEGER,
        PRIMARY KEY (emp_id, pat_id)
    )
    """)
    
    # Audit Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_events (
        audit_id INTEGER PRIMARY KEY,
        emp_id INTEGER,
        pat_id INTEGER,
        action_c INTEGER,
        action_datetime TEXT,
        dept_id INTEGER,
        workstation_id TEXT,
        session_id TEXT,
        in_panel INTEGER,
        is_vip_access INTEGER,
        justification TEXT,
        anomaly_type TEXT,
        is_known_user INTEGER,
        ingested_at TEXT
    )
    """)
    
    # Ingestion Watermark Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ingestion_watermark (
        id INTEGER PRIMARY KEY DEFAULT 1,
        last_ingested_date TEXT,
        last_run_at TEXT
    )
    """)
    
    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_emp_date ON audit_events (emp_id, action_datetime);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_pat ON audit_events (pat_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_dept ON audit_events (dept_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_known ON audit_events (is_known_user);")
    
    conn.commit()

def load_reference_tables(conn):
    print("=== Loading Reference Tables ===")
    tables = {
        "employees.csv": ("employees", "emp_id"),
        "patients.csv": ("patients", "pat_id"),
        "patient_panels.csv": ("patient_panels", None)
    }
    
    for csv_file, (table_name, pk) in tables.items():
        path = os.path.join(MOCK_DATA_DIR, csv_file)
        if not os.path.exists(path):
            print(f"Error: {csv_file} not found.")
            sys.exit(1)
            
        df = pd.read_csv(path)
        if df.empty:
            print(f"Warning: {csv_file} is empty.")
            continue
            
        # Check current row count
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"Table {table_name} already populated ({count} rows). Skipping initial load.")
        else:
            # Map column names if necessary (e.g., lowercase for DB)
            df.columns = [c.lower() for c in df.columns]
            
            # Map specific columns to match the DB schema
            rename_map = {
                "normal_start_hour": "normal_start",
                "normal_end_hour": "normal_end"
            }
            df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
            
            # Convert boolean columns to int
            for col in ['is_float', 'is_vip']:
                if col in df.columns:
                    df[col] = df[col].astype(int)
            
            df.to_sql(table_name, conn, if_exists='append', index=False)
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            new_count = cursor.fetchone()[0]
            print(f"Loaded {table_name}: {new_count} rows.")
            
    # Return set of valid emp_ids
    cursor.execute("SELECT emp_id FROM employees")
    return set(r[0] for r in cursor.fetchall())

def get_watermark(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT last_ingested_date FROM ingestion_watermark WHERE id = 1")
    row = cursor.fetchone()
    return row[0] if row else None

def update_watermark(conn, date_str):
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO ingestion_watermark (id, last_ingested_date, last_run_at)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_ingested_date = excluded.last_ingested_date,
            last_run_at = excluded.last_run_at
    """, (date_str, now))
    conn.commit()

def normalize_row(row, valid_emp_ids, now_utc):
    # action_c: integer 1-6
    try:
        ac = int(row['ACTION_C'])
        if ac < 1 or ac > 6:
            ac = 6
            log_warning(f"Audit {row['AUDIT_ID']}: ACTION_C {row['ACTION_C']} out of range, set to 6.")
    except (ValueError, TypeError):
        ac = 6
        log_warning(f"Audit {row['AUDIT_ID']}: ACTION_C {row['ACTION_C']} invalid, set to 6.")

    # emp_id and is_known_user
    emp_id = int(row['EMP_ID'])
    is_known = 1 if emp_id in valid_emp_ids else 0

    # in_panel, is_vip_access to int
    in_panel = 1 if str(row['IN_PANEL']).lower() in ['true', '1', '1.0'] else 0
    is_vip = 1 if str(row['IS_VIP_ACCESS']).lower() in ['true', '1', '1.0'] else 0

    # justification: None/NaN to empty string
    justification = str(row['JUSTIFICATION']) if pd.notna(row['JUSTIFICATION']) else ""
    
    # anomaly_type: None/NaN to None (NULL in SQLite)
    anomaly = row['ANOMALY_TYPE'] if pd.notna(row['ANOMALY_TYPE']) else None

    return (
        int(row['AUDIT_ID']),
        emp_id,
        int(row['PAT_ID']) if pd.notna(row['PAT_ID']) else None,
        ac,
        row['ACTION_DATETIME'].strftime("%Y-%m-%d %H:%M:%S"),
        int(row['DEPT_ID']),
        row['WORKSTATION_ID'],
        row['SESSION_ID'],
        in_panel,
        is_vip,
        justification,
        anomaly,
        is_known,
        now_utc
    )

def ingest_audit_logs(conn, valid_emp_ids):
    print("\n=== Incremental Audit Ingestion ===")
    audit_path = os.path.join(MOCK_DATA_DIR, "clarity_audit.csv")
    if not os.path.exists(audit_path):
        print("Error: clarity_audit.csv not found.")
        sys.exit(1)
        
    df = pd.read_csv(audit_path)
    if df.empty:
        print("Warning: clarity_audit.csv is empty.")
        return

    # Parse dates
    df['ACTION_DATETIME'] = pd.to_datetime(df['ACTION_DATETIME'], errors='coerce')
    failed_dates = df['ACTION_DATETIME'].isna()
    if failed_dates.any():
        for idx in df[failed_dates].index:
            log_warning(f"Row {idx}: Failed to parse ACTION_DATETIME. Skipping.")
        df = df.dropna(subset=['ACTION_DATETIME'])

    # Drop future dates (though unlikely in mock data)
    now = datetime.now()
    future_dates = df['ACTION_DATETIME'] > now
    if future_dates.any():
        log_warning(f"Skipped {future_dates.sum()} rows with future timestamps.")
        df = df[~future_dates]

    # Group by calendar date
    df['date_key'] = df['ACTION_DATETIME'].dt.date
    grouped = df.groupby('date_key')
    
    watermark = get_watermark(conn)
    if watermark:
        print(f"Resuming from {watermark}")
        watermark_date = datetime.strptime(watermark, "%Y-%m-%d").date()
        unprocessed_dates = sorted([d for d in grouped.groups.keys() if d > watermark_date])
    else:
        unprocessed_dates = sorted(list(grouped.groups.keys()))

    if not unprocessed_dates:
        print("No new data to ingest.")
        return

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    for d in unprocessed_dates:
        day_data = grouped.get_group(d)
        records = []
        for _, row in day_data.iterrows():
            records.append(normalize_row(row, valid_emp_ids, now_utc))
            
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT OR IGNORE INTO audit_events (
                audit_id, emp_id, pat_id, action_c, action_datetime,
                dept_id, workstation_id, session_id, in_panel,
                is_vip_access, justification, anomaly_type,
                is_known_user, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, records)
        
        update_watermark(conn, d.strftime("%Y-%m-%d"))
        print(f"Ingested {d}: {len(records)} events")

def print_final_summary(conn):
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM audit_events")
    total_rows = cursor.fetchone()[0]
    
    cursor.execute("SELECT MIN(action_datetime), MAX(action_datetime) FROM audit_events")
    min_date, max_date = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM audit_events WHERE is_known_user = 0")
    unknown_users = cursor.fetchone()[0]
    
    watermark = get_watermark(conn)
    
    db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    
    print("\n=== FINAL INGESTION SUMMARY ===")
    print(f"Total rows in audit_events:      {total_rows:,}")
    print(f"Date range:                      {min_date} to {max_date}")
    print(f"Unknown user events count:       {unknown_users:,}")
    print(f"Validation warnings count:       {len(LOG_WARNINGS)}")
    print(f"Current watermark date:          {watermark}")
    print(f"sentinel.db file size:           {db_size_mb:.2f} MB")
    print("==========================================================")

if __name__ == "__main__":
    conn = get_db_connection()
    try:
        setup_database(conn)
        valid_emp_ids = load_reference_tables(conn)
        ingest_audit_logs(conn, valid_emp_ids)
        print_final_summary(conn)
    finally:
        conn.close()
