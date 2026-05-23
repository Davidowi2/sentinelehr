import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timezone
from db import get_connection
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

# ─── CONFIGURATION ──────────────────────────────────────────
BASELINE_WINDOW_DAYS = 90
COLD_START_THRESHOLD = 30
LOG_WARNINGS = []

def get_db_connection():
    return get_connection()

def setup_baseline_table(conn):
    # Handled by setup_db.py
    pass

def calculate_baselines():
    start_time = time.time()
    conn = get_db_connection()
    
    # Add column if not exists
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE user_baselines ADD COLUMN IF NOT EXISTS sensitive_access_rate REAL DEFAULT 0.0;")
    cursor.execute("ALTER TABLE user_baselines ADD COLUMN IF NOT EXISTS vip_access_rate REAL DEFAULT 0.0;")
    conn.commit()

    # Load data
    print("Loading data from Neon PostgreSQL...")
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
    
    # sensitive record accesses should never contribute to "normal" baseline behavior
    df_audit = pd.read_sql_query("SELECT * FROM audit_events WHERE is_known_user = 1 AND is_sensitive_access = 0", engine)
    # But we need total events for the new rates, so load a simplified version for rate calculation
    df_all_events = pd.read_sql_query("SELECT emp_id, is_sensitive_access, is_vip_access FROM audit_events WHERE is_known_user = 1", engine)
    df_emp = pd.read_sql_query("SELECT * FROM employees", engine)
    
    if df_audit.empty:
        print("No audit events found for known users.")
        conn.close()
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
        
        # New rates calculation using all events
        emp_all_events = df_all_events[df_all_events['emp_id'] == emp_id]
        total_ev = len(emp_all_events)
        if total_ev > 0:
            sensitive_rate = len(emp_all_events[emp_all_events['is_sensitive_access'] == 1]) / total_ev
            vip_rate = len(emp_all_events[emp_all_events['is_vip_access'] == 1]) / total_ev
        else:
            sensitive_rate = 0.0
            vip_rate = 0.0

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
            'sensitive_access_rate': sensitive_rate,
            'vip_access_rate': vip_rate,
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
            # Absolute fallback if no one in the role has data
            for col in ['avg_daily_volume', 'std_daily_volume', 'max_daily_volume_p95', 
                        'off_hours_rate', 'in_panel_rate', 'export_print_rate', 
                        'break_glass_rate', 'cross_dept_rate', 'avg_unique_patients_day', 
                        'std_unique_patients_day', 'sensitive_access_rate', 'vip_access_rate']:
                d[col] = 0.0
            d['primary_dept_id'] = emp_info['dept_id']
            
        final_baselines.append(d)
        
    # Store in DB
    print(f"Storing {len(final_baselines)} baselines in user_baselines table...")
    df_final = pd.DataFrame(final_baselines)
    
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE user_baselines") # Clear old baselines
    conn.commit()
    
    df_final.to_sql('user_baselines', engine, if_exists='append', index=False)
    
    runtime = time.time() - start_time
    print(f"Baseline calculation complete in {runtime:.2f} seconds.")
    print(f"Personal Baselines: {len(personal_df)}")
    print(f"Role-Group Baselines: {len(final_baselines) - len(personal_df)}")
    conn.close()

if __name__ == "__main__":
    calculate_baselines()
