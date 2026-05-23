import sys
import os
import json
from pathlib import Path

# ─── SETUP ───────────────────────────────────────────────────
# Add project root to path so we can import db
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from db import get_connection
from mock_clarity_v2.date_utils import from_epic_datetime
from psycopg2.extras import execute_values

OUTPUT_DIR = PROJECT_ROOT / "mock_clarity_v2" / "output"

def run_migrations(conn):
    """Ensure schema matches requirements."""
    print("=== Running Migrations ===")
    cursor = conn.cursor()
    
    # Add is_sensitive to patients
    cursor.execute("""
        ALTER TABLE patients ADD COLUMN IF NOT EXISTS is_sensitive INTEGER DEFAULT 0;
    """)
    
    # Add is_sensitive_access to audit_events
    cursor.execute("""
        ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS is_sensitive_access INTEGER DEFAULT 0;
    """)
    
    # Ensure ingestion_watermark table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_watermark (
            id INTEGER PRIMARY KEY,
            last_ingested_date TEXT,
            last_run_at TEXT
        );
    """)
    conn.commit()
    cursor.close()

def load_reference_tables(conn):
    """Load employees, patients, and panels from CSVs."""
    print("=== Loading Reference Tables ===")
    cursor = conn.cursor()
    
    # 1. Employees
    emp_path = OUTPUT_DIR / "CLARITY_EMP.csv"
    emp_df = pd.read_csv(emp_path)
    # Mapping: USER_ID -> emp_id, _ROLE -> role, DEP_ID -> dept_id, _SHIFT_START -> normal_start, _SHIFT_END -> normal_end, _IS_FLOAT -> is_float
    emp_data = [
        (int(r['USER_ID']), r['_ROLE'], int(r['DEP_ID']), int(r['_SHIFT_START']), int(r['_SHIFT_END']), int(r['_IS_FLOAT']))
        for _, r in emp_df.iterrows()
    ]
    execute_values(cursor, """
        INSERT INTO employees (emp_id, role, dept_id, normal_start, normal_end, is_float)
        VALUES %s ON CONFLICT (emp_id) DO NOTHING
    """, emp_data)
    print(f"Employees loaded: {len(emp_data)} rows.")

    # 2. Patients
    pat_path = OUTPUT_DIR / "PATIENT.csv"
    pat_df = pd.read_csv(pat_path)
    # Mapping: PAT_ID -> pat_id, _IS_VIP -> is_vip, HOME_DEP_ID -> primary_dept_id, _IS_SENSITIVE -> is_sensitive
    pat_data = [
        (int(r['PAT_ID']), int(r['HOME_DEP_ID']), int(r['_IS_VIP']), int(r['_IS_SENSITIVE']))
        for _, r in pat_df.iterrows()
    ]
    execute_values(cursor, """
        INSERT INTO patients (pat_id, primary_dept_id, is_vip, is_sensitive)
        VALUES %s ON CONFLICT (pat_id) DO NOTHING
    """, pat_data)
    print(f"Patients loaded: {len(pat_data)} rows.")

    # 3. Patient Panels
    enc_path = OUTPUT_DIR / "PAT_ENC.csv"
    enc_df = pd.read_csv(enc_path)
    # Mapping: PROV_ID -> emp_id, PAT_ID -> pat_id (deduplicate)
    panel_df = enc_df[['PROV_ID', 'PAT_ID']].drop_duplicates()
    panel_data = [
        (int(r['PROV_ID']), int(r['PAT_ID']))
        for _, r in panel_df.iterrows()
    ]
    execute_values(cursor, """
        INSERT INTO patient_panels (emp_id, pat_id)
        VALUES %s ON CONFLICT DO NOTHING
    """, panel_data)
    print(f"Patient Panels loaded: {len(panel_data)} rows.")
    
    conn.commit()
    cursor.close()

    return {
        "known_emp_set": set(emp_df['USER_ID']),
        "panel_set": set(zip(panel_df['PROV_ID'], panel_df['PAT_ID'])),
        "vip_set": set(pat_df[pat_df['_IS_VIP'] == 1]['PAT_ID']),
        "sensitive_set": set(pat_df[pat_df['_IS_SENSITIVE'] == 1]['PAT_ID']),
        "counts": {
            "employees": len(emp_data),
            "patients": len(pat_data),
            "panels": len(panel_data)
        }
    }

def get_watermark(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT last_ingested_date FROM ingestion_watermark WHERE id = 1")
    row = cursor.fetchone()
    cursor.close()
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
    cursor.close()

def ingest_access_logs(conn, ref_data):
    print("\n=== Processing ACCESS_LOG.csv ===")
    log_path = OUTPUT_DIR / "ACCESS_LOG.csv"
    if not log_path.exists():
        print(f"Error: {log_path} not found.")
        return

    # 1. Read and Filter
    print("Reading and filtering ACCESS_LOG...")
    chunks = pd.read_csv(log_path, chunksize=100000)
    
    total_rows_csv = 0
    search_only_dropped = 0
    continuation_dropped = 0
    filtered_chunks = []

    for chunk in chunks:
        total_rows_csv += len(chunk)
        
        # Filter A: Exclude search-only
        search_only_mask = chunk['_IS_SEARCH_ONLY'] == 1
        search_only_dropped += search_only_mask.sum()
        
        # Filter B: Exclude continuation
        continuation_mask = chunk['_IS_CONTINUATION'] == 1
        continuation_dropped += continuation_mask.sum()
        
        # Apply filters
        mask = (~search_only_mask) & (~continuation_mask)
        filtered_chunks.append(chunk[mask].copy())

    df = pd.concat(filtered_chunks)
    print(f"Dropped {search_only_dropped} search-only rows.")
    print(f"Dropped {continuation_dropped} continuation rows.")
    print(f"Primary events to process: {len(df):,}")

    # 2. Convert Dates
    print("Converting Epic datetimes...")
    if '_ACCESS_TIME_ISO' in df.columns:
        df['action_datetime'] = pd.to_datetime(df['_ACCESS_TIME_ISO'])
    else:
        df['action_datetime'] = df['ACCESS_INSTANT'].apply(from_epic_datetime)
    
    # Store as ISO string for DB
    df['action_datetime_str'] = df['action_datetime'].dt.strftime("%Y-%m-%d %H:%M:%S")
    df['date_key'] = df['action_datetime'].dt.date
    df = df.sort_values('action_datetime')

    # 3. Watermark logic
    watermark = get_watermark(conn)
    if watermark:
        print(f"Resuming from after {watermark}")
        watermark_date = datetime.strptime(watermark, "%Y-%m-%d").date()
        df = df[df['date_key'] > watermark_date].copy()
    
    if df.empty:
        print("No new data to ingest.")
        return {
            "total_csv": total_rows_csv,
            "search_dropped": search_only_dropped,
            "continuation_dropped": continuation_dropped,
            "ingested": 0,
            "sensitive_events": 0,
            "unknown_users": 0,
            "last_date": watermark
        }

    unique_dates = sorted(df['date_key'].unique())
    print(f"Ingesting {len(df):,} events across {len(unique_dates)} calendar days.")

    known_emp_set = ref_data["known_emp_set"]
    panel_set = ref_data["panel_set"]
    vip_set = ref_data["vip_set"]
    sensitive_set = ref_data["sensitive_set"]

    total_ingested = 0
    sensitive_access_count = 0
    unknown_user_count = 0
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 4. Batch Insert per Day
    for i, date_key in enumerate(unique_dates):
        day_df = df[df['date_key'] == date_key].copy()
        if (i + 1) % 10 == 0 or i == 0 or i == len(unique_dates) - 1:
            print(f"  [{i+1}/{len(unique_dates)}] Processing {date_key} ({len(day_df):,} rows)...")
        
        batch_rows = []
        for _, row in day_df.iterrows():
            emp_id = int(row['USER_ID'])
            pat_id = int(row['PAT_ID']) if pd.notna(row['PAT_ID']) else None
            
            is_known = 1 if emp_id in known_emp_set else 0
            if not is_known: unknown_user_count += 1
            
            in_panel = 1 if (emp_id, pat_id) in panel_set else 0
            is_vip = 1 if pat_id in vip_set else 0
            is_sensitive = 1 if pat_id in sensitive_set else 0
            if is_sensitive: sensitive_access_count += 1
            
            action_c = int(row['ACTION_C'])
            justification = "" if action_c != 6 else "Emergency Access" # Simple justification for break-glass

            batch_rows.append((
                int(row['ACCESS_LOG_ID']), # audit_id
                emp_id,
                pat_id,
                action_c,
                row['action_datetime_str'],
                int(row['DEP_ID']) if pd.notna(row['DEP_ID']) else None,
                row['WORKSTATION_ID'],
                row['SESSION_KEY'],
                in_panel,
                is_vip,
                justification,
                row['ANOMALY_TYPE'] if pd.notna(row['ANOMALY_TYPE']) else None,
                is_known,
                ingested_at,
                is_sensitive
            ))

        # Perform batch insert
        cursor = conn.cursor()
        query = """
            INSERT INTO audit_events (
                audit_id, emp_id, pat_id, action_c, action_datetime, 
                dept_id, workstation_id, session_id, in_panel, is_vip_access, 
                justification, anomaly_type, is_known_user, ingested_at, is_sensitive_access
            ) VALUES %s
            ON CONFLICT (audit_id) DO NOTHING
        """
        # Batching 5000 at a time as requested
        for j in range(0, len(batch_rows), 5000):
            execute_values(cursor, query, batch_rows[j:j+5000])
        
        conn.commit()
        cursor.close()
        
        total_ingested += len(day_df)
        update_watermark(conn, date_key.strftime("%Y-%m-%d"))

    return {
        "total_csv": total_rows_csv,
        "search_dropped": search_only_dropped,
        "continuation_dropped": continuation_dropped,
        "ingested": total_ingested,
        "sensitive_events": sensitive_access_count,
        "unknown_users": unknown_user_count,
        "last_date": unique_dates[-1].strftime("%Y-%m-%d")
    }

def print_summary(ref_data, results):
    print("\n" + "="*40)
    print("FINAL INGESTION SUMMARY")
    print("="*40)
    print(f"Reference tables loaded:")
    print(f"  - Employees:      {ref_data['counts']['employees']}")
    print(f"  - Patients:       {ref_data['counts']['patients']}")
    print(f"  - Patient Panels: {ref_data['counts']['panels']}")
    print("-" * 40)
    print(f"ACCESS_LOG rows in CSV:    {results['total_csv']:,}")
    print(f"Search-only rows excluded:  {results['search_dropped']:,}")
    print(f"Continuation rows excluded: {results['continuation_dropped']:,}")
    print(f"Primary events loaded:     {results['ingested']:,}")
    print(f"Sensitive access events:   {results['sensitive_events']:,}")
    print(f"Unknown user events:       {results['unknown_users']:,}")
    print(f"Watermark date:            {results['last_date']}")
    
    # Simple DB size estimate (very rough)
    # Each audit event row is roughly 200 bytes
    size_mb = (results['ingested'] * 200) / (1024 * 1024)
    print(f"DB size estimate (new):    {size_mb:.2f} MB")
    print("="*40)

def main():
    conn = get_connection()
    try:
        run_migrations(conn)
        ref_data = load_reference_tables(conn)
        results = ingest_access_logs(conn, ref_data)
        if results:
            print_summary(ref_data, results)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
