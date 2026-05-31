import pandas as pd
import numpy as np
import os
import time
from datetime import datetime, timezone
from db import get_connection
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

# ─── CONFIGURATION ──────────────────────────────────────────
MOCK_DATA_DIR = "./mock_data/"

def get_db_connection():
    return get_connection()

def run_rules_engine(org_id: int = 1):
    start_time = time.time()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('BEGIN')

        # Ensure schema is up to date (DDL outside transaction is fine; IF NOT EXISTS is idempotent)
        cursor.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS sensitive_out_of_panel INTEGER DEFAULT 0;")

        # DELETE existing alerts for this org inside the transaction
        cursor.execute("""
            DELETE FROM alerts 
            WHERE organization_id = %s
        """, (org_id,))

        print("Loading data from Neon PostgreSQL...")
        DATABASE_URL = os.getenv("DATABASE_URL")
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        engine = create_engine(DATABASE_URL)

        # anomaly_type must NEVER be read by this script
        df_audit = pd.read_sql_query("""
            SELECT audit_id, emp_id, pat_id, action_c, action_datetime, dept_id, in_panel, is_vip_access, is_sensitive_access
            FROM audit_events 
            WHERE is_known_user = 1 AND organization_id = %s
        """, engine, params=(org_id,))
        df_baselines = pd.read_sql_query("SELECT * FROM user_baselines WHERE organization_id = %s", engine, params=(org_id,))
        df_employees = pd.read_sql_query("SELECT emp_id, normal_start, normal_end FROM employees WHERE organization_id = %s", engine, params=(org_id,))

        df_audit['action_datetime'] = pd.to_datetime(df_audit['action_datetime'])
        df_audit['date'] = df_audit['action_datetime'].dt.date
        df_audit['hour'] = df_audit['action_datetime'].dt.hour

        dates = sorted(df_audit['date'].unique())
        if len(dates) < 5:
            print("Not enough days of data to run rules (need 5+ days).")
            conn.rollback()
            return

        processing_dates = dates[4:]
        print(f"Processing {len(processing_dates)} days of activity...")

        df = df_audit[df_audit['date'].isin(processing_dates)].copy()

        # Merge baselines and employee info
        df = df.merge(df_baselines, on='emp_id', how='inner')
        df = df.merge(df_employees, on='emp_id', how='inner', suffixes=('', '_emp'))

        # Row-level violations
        print("Calculating row-level indicators...")
        df['is_out_of_panel'] = ((df['in_panel'] == 0) & (df['pat_id'].notna())).astype(int)
        df['is_off_hours'] = ((df['hour'] < df['normal_start']) | (df['hour'] > df['normal_end'])).astype(int)
        df['is_export_print'] = df['action_c'].isin([3, 4]).astype(int)
        df['is_break_glass'] = (df['action_c'] == 5).astype(int)
        df['is_vip_out_of_panel'] = ((df['is_vip_access'] == 1) & (df['in_panel'] == 0)).astype(int)
        df['is_cross_dept'] = (df['dept_id'] != df['primary_dept_id']).astype(int)
        df['is_sensitive_out_of_panel'] = ((df['is_sensitive_access'] == 1) & (df['in_panel'] == 0)).astype(int)

        # Calculate daily metrics per (date, emp_id)
        print("Aggregating to daily metrics...")
        daily = df.groupby(['date', 'emp_id']).agg({
            'audit_id': 'count',
            'is_out_of_panel': 'sum',
            'is_off_hours': 'sum',
            'is_export_print': 'sum',
            'is_break_glass': 'sum',
            'is_vip_out_of_panel': 'sum',
            'is_cross_dept': 'sum',
            'is_sensitive_out_of_panel': 'sum'
        }).rename(columns={'audit_id': 'total_events'}).reset_index()

        # Re-merge baseline info to 'daily'
        daily = daily.merge(df_baselines, on='emp_id', how='inner')
        daily = daily.merge(df_employees, on='emp_id', how='inner', suffixes=('', '_emp'))

        # Vectorized Rule Checks
        print("Applying rules...")
        float_mult = np.where(daily['is_float'] == 1, 1.5, 1.0)

        # R1
        r1_thresh = np.maximum(3, (daily['avg_daily_volume'] * (1 - daily['in_panel_rate']) * 2))
        daily['R1'] = daily['is_out_of_panel'] > r1_thresh

        # R2
        r2_thresh = (daily['avg_daily_volume'] + 2 * daily['std_daily_volume']) * float_mult
        p95_thresh = daily['max_daily_volume_p95'] * float_mult
        daily['R2'] = (daily['total_events'] > r2_thresh) | (daily['total_events'] > p95_thresh)

        # R3
        r3_thresh = daily['off_hours_rate'] * daily['total_events'] * 2
        daily['R3'] = (daily['is_off_hours'] >= 3) & (daily['is_off_hours'] > r3_thresh)

        # R4
        daily['R4'] = daily['is_vip_out_of_panel'] >= 1

        # R5 (Old CROSS_DEPT rule, now SENSITIVE_SNOOP for v2)
        # Threshold 3 accounts for accidental access. 
        # In real Epic, extra access controls reduce 
        # accidental sensitive hits significantly. 
        # 3+ hits in one day indicates intent, not accident. 
        daily['R_SENSITIVE'] = daily['is_sensitive_out_of_panel'] >= 3

        # R6
        r6_thresh = daily['export_print_rate'] * daily['total_events'] * 2
        daily['R6'] = (daily['is_export_print'] >= 5) & (daily['is_export_print'] > r6_thresh)

        # R7
        r7_thresh = daily['break_glass_rate'] * daily['total_events'] * 2
        daily['R7'] = (daily['is_break_glass'] >= 2) & (daily['is_break_glass'] > r7_thresh)

        # R8 - SENSITIVE RECORD ACCESS (HARD RULE)
        daily['R8'] = daily['is_sensitive_out_of_panel'] >= 1

        # Calculate severity and explanation
        rules = ['R1', 'R2', 'R3', 'R4', 'R_SENSITIVE', 'R6', 'R7', 'R8']
        daily['rule_count'] = daily[rules].sum(axis=1)

        # Filter only triggered
        triggered_df = daily[daily['rule_count'] > 0].copy()

        if triggered_df.empty:
            print("No alerts generated.")
            conn.rollback()
            return

        def get_severity(row):
            # R4, R8 and R_SENSITIVE are HARD RULES - fire standalone
            if row['R_SENSITIVE']:
                return "CRITICAL"

            if row['R8']:
                # R8 alone -> High, R8 + any other -> Critical
                return "Critical" if row['rule_count'] > 1 else "High"

            if row['R4']:
                # R4 alone -> Medium (from previous logic), R4 + any other -> Critical if count > 1
                return "Critical" if row['rule_count'] > 1 else "Medium"

            # Rule of 3 for others
            count = row['rule_count']
            if count == 2: return "Medium"
            if count >= 3: return "High"
            return "Low"

        triggered_df['severity'] = triggered_df.apply(get_severity, axis=1)
        triggered_df = triggered_df[triggered_df['severity'] != "Low"].copy()

        def get_explanation(row):
            expl = []
            if row['R1']: expl.append(f"Accessed {row['is_out_of_panel']} records outside panel")
            if row['R2']: expl.append(f"Accessed {row['total_events']} records (volume spike)")
            if row['R3']: expl.append(f"{row['is_off_hours']} off-hours accesses")
            if row['R4']: expl.append(f"Accessed {row['is_vip_out_of_panel']} VIP records")
            if row['R_SENSITIVE']: expl.append("Out-of-panel access to highly sensitive patient record")
            if row['R6']: expl.append(f"{row['is_export_print']} export/print events")
            if row['R7']: expl.append(f"{row['is_break_glass']} break-glass events")
            if row['R8']: expl.append(f"{row['is_sensitive_out_of_panel']} accesses to sensitive records (HIV/behavioral health) with no documented care relationship")
            return f"{row['role']} on {row['date']}: " + ". ".join(expl) + "."

        triggered_df['explanation'] = triggered_df.apply(get_explanation, axis=1)
        triggered_df['rules_triggered'] = triggered_df.apply(lambda r: ",".join([rl for rl in rules if r[rl]]), axis=1)
        triggered_df['created_at'] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        triggered_df['organization_id'] = org_id

        # Prepare for insert
        print(f"Storing {len(triggered_df)} alerts...")
        alerts_to_insert = triggered_df[[
            'emp_id', 'date', 'rules_triggered', 'rule_count', 'severity', 'explanation',
            'total_events', 'is_out_of_panel', 'is_off_hours', 'is_export_print',
            'is_break_glass', 'is_vip_out_of_panel', 'is_cross_dept', 'created_at', 'is_sensitive_out_of_panel', 'organization_id'
        ]].values.tolist()

        from psycopg2.extras import execute_values
        execute_values(cursor, """
            INSERT INTO alerts (
                emp_id, alert_date, rules_triggered, rule_count, severity, explanation,
                event_count, out_of_panel, off_hours_count, export_print_count,
                break_glass_count, vip_out_of_panel, cross_dept_count, created_at, sensitive_out_of_panel, organization_id
            ) VALUES %s
        """, alerts_to_insert)

        conn.commit()
        print(f'[DETECTION] Rules engine complete for org {org_id}')

    except Exception as e:
        conn.rollback()
        print(f'[DETECTION] Rules engine failed for org {org_id}, rolled back: {str(e)}')
        raise
    finally:
        conn.close()

    runtime = time.time() - start_time
    print(f"\n=== RULES ENGINE SUMMARY ===")
    print(f"Total Medium+ alerts generated: {len(triggered_df)}")
    print(f"Processing time: {runtime:.2f} seconds")

if __name__ == "__main__": 
    import sys 
    if len(sys.argv) > 1: 
        try: 
            org_id = int(sys.argv[1]) 
        except ValueError: 
            print("Error: org_id must be an integer. Usage: python rules_engine.py <org_id>") 
            sys.exit(1) 
    else: 
        print("Error: org_id required. Usage: python rules_engine.py <org_id>") 
        print("Example: python rules_engine.py 1") 
        sys.exit(1) 
    run_rules_engine(org_id)
