import pandas as pd
import os
import sys
from datetime import datetime, timezone
import numpy as np
from db import get_connection
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIGURATION ──────────────────────────────────────────
MOCK_DATA_DIR = "./mock_data/"
LOG_WARNINGS = []

def log_warning(msg):
    LOG_WARNINGS.append(msg)

def get_db_connection():
    return get_connection()

def setup_database(conn):
    # Tables are now handled by setup_db.py
    pass

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
        count = cursor.fetchone()['count']
        
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
            
            # For PostgreSQL, we use SQLAlchemy to append to table or manually insert
            from sqlalchemy import create_engine
            DATABASE_URL = os.getenv("DATABASE_URL")
            # Convert postgres:// to postgresql:// if needed for SQLAlchemy
            if DATABASE_URL.startswith("postgres://"):
                DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            engine = create_engine(DATABASE_URL)
            df.to_sql(table_name, engine, if_exists='append', index=False)
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            new_count = cursor.fetchone()['count']
            print(f"Loaded {table_name}: {new_count} rows.")
            
    # Return set of valid emp_ids
    cursor.execute("SELECT emp_id FROM employees")
    return set(r['emp_id'] for r in cursor.fetchall())

def get_watermark(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT last_ingested_date FROM ingestion_watermark WHERE id = 1")
    row = cursor.fetchone()
    return row['last_ingested_date'] if row else None

def update_watermark(conn, date_str):
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO ingestion_watermark (id, last_ingested_date, last_run_at)
        VALUES (1, %s, %s)
        ON CONFLICT(id) DO UPDATE SET
            last_ingested_date = EXCLUDED.last_ingested_date,
            last_run_at = EXCLUDED.last_run_at
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
    
    # anomaly_type: None/NaN to None (NULL in DB)
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
        
    print(f"Reading {audit_path}...")
    df = pd.read_csv(audit_path)
    print(f"Read {len(df)} rows.")
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

    # Drop future dates
    now = datetime.now()
    future_dates = df['ACTION_DATETIME'] > now
    if future_dates.any():
        log_warning(f"Skipped {future_dates.sum()} rows with future timestamps.")
        df = df[~future_dates]

    # Group by calendar date
    df['date_key'] = df['ACTION_DATETIME'].dt.date
    
    watermark = get_watermark(conn)
    if watermark:
        print(f"Resuming from {watermark}")
        watermark_date = datetime.strptime(watermark, "%Y-%m-%d").date()
        df_unprocessed = df[df['date_key'] > watermark_date].copy()
    else:
        df_unprocessed = df.copy()

    if df_unprocessed.empty:
        print("No new data to ingest.")
        return

    print(f"Ingesting {len(df_unprocessed)} events...")
    
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    # Vectorized normalization
    df_to_ingest = pd.DataFrame()
    df_to_ingest['audit_id'] = df_unprocessed['AUDIT_ID'].astype(int)
    df_to_ingest['emp_id'] = df_unprocessed['EMP_ID'].astype(int)
    df_to_ingest['pat_id'] = df_unprocessed['PAT_ID'].apply(lambda x: int(x) if pd.notna(x) else None)
    
    # action_c normalization
    df_to_ingest['action_c'] = df_unprocessed['ACTION_C'].apply(lambda x: int(x) if (pd.notna(x) and 1 <= int(x) <= 6) else 6)
    
    df_to_ingest['action_datetime'] = df_unprocessed['ACTION_DATETIME'].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_to_ingest['dept_id'] = df_unprocessed['DEPT_ID'].astype(int)
    df_to_ingest['workstation_id'] = df_unprocessed['WORKSTATION_ID'].astype(str)
    df_to_ingest['session_id'] = df_unprocessed['SESSION_ID'].astype(str)
    
    # Boolean to int
    df_to_ingest['in_panel'] = df_unprocessed['IN_PANEL'].apply(lambda x: 1 if str(x).lower() in ['true', '1', '1.0'] else 0)
    df_to_ingest['is_vip_access'] = df_unprocessed['IS_VIP_ACCESS'].apply(lambda x: 1 if str(x).lower() in ['true', '1', '1.0'] else 0)
    
    df_to_ingest['justification'] = df_unprocessed['JUSTIFICATION'].fillna("")
    df_to_ingest['anomaly_type'] = df_unprocessed['ANOMALY_TYPE'].where(pd.notna(df_unprocessed['ANOMALY_TYPE']), None)
    df_to_ingest['is_known_user'] = df_unprocessed['EMP_ID'].apply(lambda x: 1 if x in valid_emp_ids else 0)
    df_to_ingest['ingested_at'] = now_utc
    
    from psycopg2.extras import execute_batch
    print("Uploading to Neon PostgreSQL in batches...")
    
    batch_size = 10000
    cursor = conn.cursor()
    
    records = df_to_ingest.to_dict('records')
    total = len(records)
    
    for i in range(0, total, batch_size):
        batch = records[i:i+batch_size]
        # Convert dict to tuple for execute_batch
        batch_tuples = [tuple(r.values()) for r in batch]
        
        execute_batch(cursor, """
            INSERT INTO audit_events (
                audit_id, emp_id, pat_id, action_c, action_datetime,
                dept_id, workstation_id, session_id, in_panel,
                is_vip_access, justification, anomaly_type,
                is_known_user, ingested_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (audit_id) DO NOTHING
        """, batch_tuples)
        
        # Update watermark to the date of the last item in this batch
        last_dt_str = batch[-1]['action_datetime']
        last_date_str = last_dt_str.split(' ')[0]
        update_watermark(conn, last_date_str)
        conn.commit()
        print(f"Uploaded {min(i+batch_size, total)}/{total} events... (Watermark: {last_date_str})")

    
    print(f"Ingested {len(df_to_ingest)} events")


def print_final_summary(conn):
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM audit_events")
    total_rows = cursor.fetchone()['count']
    
    cursor.execute("SELECT MIN(action_datetime), MAX(action_datetime) FROM audit_events")
    row = cursor.fetchone()
    min_date, max_date = row['min'], row['max']
    
    cursor.execute("SELECT COUNT(*) FROM audit_events WHERE is_known_user = 0")
    unknown_users = cursor.fetchone()['count']
    
    watermark = get_watermark(conn)
    
    print("\n=== FINAL INGESTION SUMMARY ===")
    print(f"Total rows in audit_events:      {total_rows:,}")
    print(f"Date range:                      {min_date} to {max_date}")
    print(f"Unknown user events count:       {unknown_users:,}")
    print(f"Validation warnings count:       {len(LOG_WARNINGS)}")
    print(f"Current watermark date:          {watermark}")
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
