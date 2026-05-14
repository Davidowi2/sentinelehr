import sqlite3
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timezone

# ─── CONFIGURATION ──────────────────────────────────────────
DB_PATH = "./sentinel.db"
BASELINE_WINDOW_DAYS = 90
COLD_START_THRESHOLD = 30
LOG_WARNINGS = []

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def setup_baseline_table(conn):
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_baselines (
        emp_id INTEGER PRIMARY KEY,
        role TEXT,
        is_float INTEGER,
        baseline_type TEXT,
        avg_daily_volume REAL,
        std_daily_volume REAL,
        max_daily_volume_p95 REAL,
        off_hours_rate REAL,
        in_panel_rate REAL,
        export_print_rate REAL,
        break_glass_rate REAL,
        cross_dept_rate REAL,
        avg_unique_patients_day REAL,
        std_unique_patients_day REAL,
        primary_dept_id INTEGER,
        days_of_data INTEGER,
        baseline_window_days INTEGER,
        last_calculated_at TEXT
    )
    """)
    conn.commit()

def calculate_baselines():
    start_time = time.time()
    conn = get_db_connection()
    setup_baseline_table(conn)
    
    # Load data
    print("Loading data from sentinel.db...")
    df_audit = pd.read_sql_query("SELECT * FROM audit_events WHERE is_known_user = 1", conn)
    df_emp = pd.read_sql_query("SELECT * FROM employees", conn)
    
    if df_audit.empty:
        print("No audit events found for known users.")
        return

    df_audit['action_datetime'] = pd.to_datetime(df_audit['action_datetime'])
    df_audit['date'] = df_audit['action_datetime'].dt.date
    df_audit['hour'] = df_audit['action_datetime'].dt.hour
    
    # Merge employee info
    df = df_audit.merge(df_emp, on='emp_id', how='left')
    
    # Metric calculation per employee
    print("Calculating metrics per employee...")
    emp_metrics = []
    
    for emp_id, group in df.groupby('emp_id'):
        emp_info = df_emp[df_emp['emp_id'] == emp_id].iloc[0]
        
        # Days of data
        daily_groups = group.groupby('date')
        days_of_data = len(daily_groups)
        
        # Daily Volume
        daily_counts = daily_groups.size()
        avg_daily_vol = daily_counts.mean()
        std_daily_vol = max(1.0, daily_counts.std()) if len(daily_counts) > 1 else 1.0
        p95_daily_vol = np.percentile(daily_counts, 95)
        
        # Off-hours rate
        off_hours = group[(group['hour'] < group['normal_start']) | (group['hour'] > group['normal_end'])]
        off_hours_rate = len(off_hours) / len(group)
        
        # In-panel rate (only for events with pat_id)
        pat_events = group[group['pat_id'].notna()]
        if len(pat_events) > 0:
            in_panel_rate = len(pat_events[pat_events['in_panel'] == 1]) / len(pat_events)
        else:
            in_panel_rate = 1.0
            
        # Export/Print rate (3=Print, 4=Export)
        export_print_rate = len(group[group['action_c'].isin([3, 4])]) / len(group)
        
        # Break-glass rate (5=Break Glass)
        break_glass_rate = len(group[group['action_c'] == 5]) / len(group)
        
        # Cross-dept rate
        # First find primary_dept_id (mode of event dept_ids)
        if not group['dept_id_x'].empty:
            primary_dept_id = group['dept_id_x'].mode()[0]
        else:
            primary_dept_id = emp_info['dept_id']
            
        cross_dept_rate = len(group[group['dept_id_x'] != primary_dept_id]) / len(group)
        
        # Unique patients per day
        daily_unique_pats = daily_groups['pat_id'].nunique()
        avg_unique_pats = daily_unique_pats.mean()
        std_unique_pats = max(1.0, daily_unique_pats.std()) if len(daily_unique_pats) > 1 else 1.0
        
        emp_metrics.append({
            'emp_id': emp_id,
            'role': emp_info['role'],
            'is_float': emp_info['is_float'],
            'avg_daily_volume': avg_daily_vol,
            'std_daily_volume': std_daily_vol,
            'max_daily_volume_p95': p95_daily_vol,
            'off_hours_rate': off_hours_rate,
            'in_panel_rate': in_panel_rate,
            'export_print_rate': export_print_rate,
            'break_glass_rate': break_glass_rate,
            'cross_dept_rate': cross_dept_rate,
            'avg_unique_patients_day': avg_unique_pats,
            'std_unique_patients_day': std_unique_pats,
            'primary_dept_id': int(primary_dept_id),
            'days_of_data': days_of_data
        })
        
    df_metrics = pd.DataFrame(emp_metrics)
    
    # Identify Personal vs Role Group
    df_metrics['baseline_type'] = df_metrics['days_of_data'].apply(
        lambda x: "personal" if x >= COLD_START_THRESHOLD else "role_group"
    )
    
    # Calculate Role Group Averages (from employees with 30+ days)
    print("Calculating role-group averages...")
    senior_mask = df_metrics['baseline_type'] == "personal"
    role_group_avgs = df_metrics[senior_mask].groupby(['role', 'is_float']).mean(numeric_only=True).reset_index()
    
    # Handle missing role-group combinations
    def get_role_group_fallback(role, is_float):
        # Try specific (role, is_float)
        match = role_group_avgs[(role_group_avgs['role'] == role) & (role_group_avgs['is_float'] == is_float)]
        if not match.empty:
            return match.iloc[0]
        
        # Fallback to just role
        LOG_WARNINGS.append(f"No senior employees for group ({role}, float={is_float}). Falling back to broader role group.")
        match_broad = df_metrics[senior_mask & (df_metrics['role'] == role)].mean(numeric_only=True)
        if not match_broad.empty and not pd.isna(match_broad['avg_daily_volume']):
            return match_broad
            
        return None

    # Apply role-group baselines to juniors and finalize
    final_baselines = []
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    # Process all employees (including those with 0 events)
    all_emp_ids = df_emp['emp_id'].tolist()
    calculated_emp_ids = df_metrics['emp_id'].tolist()
    missing_emp_ids = set(all_emp_ids) - set(calculated_emp_ids)
    
    # 1. Update Personal Baselines
    personal_df = df_metrics[df_metrics['baseline_type'] == "personal"].copy()
    for _, row in personal_df.iterrows():
        d = row.to_dict()
        d['baseline_window_days'] = BASELINE_WINDOW_DAYS
        d['last_calculated_at'] = now_utc
        final_baselines.append(d)
        
    # 2. Update Role Group Baselines for Juniors
    junior_df = df_metrics[df_metrics['baseline_type'] == "role_group"].copy()
    for _, row in junior_df.iterrows():
        fallback = get_role_group_fallback(row['role'], row['is_float'])
        d = row.to_dict()
        if fallback is not None:
            # Overwrite metrics with group averages
            for col in role_group_avgs.columns:
                if col not in ['role', 'is_float', 'emp_id', 'days_of_data']:
                    d[col] = fallback[col]
        d['baseline_window_days'] = BASELINE_WINDOW_DAYS
        d['last_calculated_at'] = now_utc
        final_baselines.append(d)
        
    # 3. Handle employees with 0 events
    for emp_id in missing_emp_ids:
        emp_info = df_emp[df_emp['emp_id'] == emp_id].iloc[0]
        fallback = get_role_group_fallback(emp_info['role'], emp_info['is_float'])
        
        d = {
            'emp_id': emp_id,
            'role': emp_info['role'],
            'is_float': emp_info['is_float'],
            'baseline_type': 'role_group',
            'days_of_data': 0,
            'baseline_window_days': BASELINE_WINDOW_DAYS,
            'last_calculated_at': now_utc
        }
        if fallback is not None:
            for col in role_group_avgs.columns:
                if col not in ['role', 'is_float', 'emp_id', 'days_of_data']:
                    d[col] = fallback[col]
        else:
            # Absolute fallback if even role group has no seniors (shouldn't happen with our mock data)
            d.update({
                'avg_daily_volume': 0.0, 'std_daily_volume': 1.0, 'max_daily_volume_p95': 0.0,
                'off_hours_rate': 0.0, 'in_panel_rate': 1.0, 'export_print_rate': 0.0,
                'break_glass_rate': 0.0, 'cross_dept_rate': 0.0,
                'avg_unique_patients_day': 0.0, 'std_unique_patients_day': 1.0,
                'primary_dept_id': emp_info['dept_id']
            })
        final_baselines.append(d)

    # Store in DB
    print(f"Storing {len(final_baselines)} baselines in sentinel.db...")
    df_final = pd.DataFrame(final_baselines)
    
    # Final normalization: ensure std >= 1.0
    df_final['std_daily_volume'] = df_final['std_daily_volume'].clip(lower=1.0)
    df_final['std_unique_patients_day'] = df_final['std_unique_patients_day'].clip(lower=1.0)
    
    df_final.to_sql('user_baselines', conn, if_exists='replace', index=False)
    conn.close()
    
    runtime = time.time() - start_time
    
    # Summary
    print("\n=== BASELINE CALCULATION SUMMARY ===")
    print(f"Total baselines stored:   {len(df_final)}")
    print(f"Personal baselines:       {len(df_final[df_final['baseline_type'] == 'personal'])}")
    print(f"Role-group baselines:     {len(df_final[df_final['baseline_type'] == 'role_group'])}")
    print("\nBreakdown by role:")
    print(df_final['role'].value_counts())
    
    if LOG_WARNINGS:
        print("\nWarnings:")
        for w in set(LOG_WARNINGS):
            print(f" - {w}")
            
    print(f"\nScript runtime:           {runtime:.2f} seconds")
    print("==========================================================")

if __name__ == "__main__":
    calculate_baselines()
