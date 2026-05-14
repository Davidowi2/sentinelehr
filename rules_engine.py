import sqlite3
import pandas as pd
import numpy as np
import os
import time
from datetime import datetime, timezone

# ─── CONFIGURATION ──────────────────────────────────────────
DB_PATH = "./sentinel.db"
MOCK_DATA_DIR = "./mock_data/"

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def setup_alerts_table(conn):
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS alerts")
    cursor.execute("""
    CREATE TABLE alerts (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER,
        alert_date TEXT,
        rules_triggered TEXT,
        rule_count INTEGER,
        severity TEXT,
        explanation TEXT,
        event_count INTEGER,
        out_of_panel INTEGER,
        off_hours_count INTEGER,
        export_print_count INTEGER,
        break_glass_count INTEGER,
        vip_out_of_panel INTEGER,
        cross_dept_count INTEGER,
        is_acknowledged INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
    cursor.execute("CREATE INDEX idx_alerts_emp_date ON alerts (emp_id, alert_date)")
    cursor.execute("CREATE INDEX idx_alerts_severity ON alerts (severity)")
    cursor.execute("CREATE INDEX idx_alerts_ack ON alerts (is_acknowledged)")
    conn.commit()

def run_rules_engine():
    start_time = time.time()
    conn = get_db_connection()
    setup_alerts_table(conn)
    
    print("Loading data from sentinel.db...")
    # anomaly_type must NEVER be read by this script
    df_audit = pd.read_sql_query("""
        SELECT audit_id, emp_id, pat_id, action_c, action_datetime, dept_id, in_panel, is_vip_access 
        FROM audit_events 
        WHERE is_known_user = 1
    """, conn)
    df_baselines = pd.read_sql_query("SELECT * FROM user_baselines", conn)
    df_employees = pd.read_sql_query("SELECT emp_id, normal_start, normal_end FROM employees", conn)
    
    # Load attacker manifest for final summary
    attackers = {}
    manifest_path = os.path.join(MOCK_DATA_DIR, "attacker_manifest.txt")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            for line in f:
                parts = line.split(",")
                emp_id_part = parts[0].split(":")[1].strip()
                emp_id = int(emp_id_part)
                attackers[emp_id] = parts[2].split(":")[1].strip()

    df_audit['action_datetime'] = pd.to_datetime(df_audit['action_datetime'])
    df_audit['date'] = df_audit['action_datetime'].dt.date
    df_audit['hour'] = df_audit['action_datetime'].dt.hour
    
    dates = sorted(df_audit['date'].unique())
    if len(dates) < 5:
        print("Not enough days of data to run rules (need 5+ days).")
        return
        
    # Process from day 5 onwards
    processing_dates = dates[4:]
    baseline_lookup = df_baselines.set_index('emp_id').to_dict('index')
    emp_lookup = df_employees.set_index('emp_id').to_dict('index')
    
    all_alerts = []
    rule_usage = {"R1": 0, "R2": 0, "R3": 0, "R4": 0, "R5": 0, "R6": 0, "R7": 0}
    
    print(f"Processing {len(processing_dates)} days of activity...")
    
    for alert_date in processing_dates:
        day_df = df_audit[df_audit['date'] == alert_date]
        
        for emp_id, group in day_df.groupby('emp_id'):
            if emp_id not in baseline_lookup or emp_id not in emp_lookup:
                continue
                
            b = baseline_lookup[emp_id]
            e = emp_lookup[emp_id]
            
            # Daily Metrics
            total_events = len(group)
            out_of_panel = len(group[(group['in_panel'] == 0) & (group['pat_id'].notna())])
            off_hours_count = len(group[(group['hour'] < e['normal_start']) | (group['hour'] > e['normal_end'])])
            export_print_count = len(group[group['action_c'].isin([3, 4])])
            break_glass_count = len(group[group['action_c'] == 5])
            vip_out_of_panel = len(group[(group['is_vip_access'] == 1) & (group['in_panel'] == 0)])
            cross_dept_count = len(group[group['dept_id'] != b['primary_dept_id']])
            
            triggered = []
            explanations = []
            
            # Float Nurse Handling
            float_mult = 1.5 if b['is_float'] == 1 else 1.0
            
            # RULE 1 — PANEL VIOLATION (R1)
            r1_threshold = max(3, (b['avg_daily_volume'] * (1 - b['in_panel_rate']) * 2))
            if out_of_panel > r1_threshold:
                triggered.append("R1")
                explanations.append(f"Accessed {out_of_panel} records outside assigned panel (baseline: {r1_threshold:.1f})")
                
            # RULE 2 — VOLUME SPIKE (R2)
            r2_threshold = (b['avg_daily_volume'] + 2 * b['std_daily_volume']) * float_mult
            p95_threshold = b['max_daily_volume_p95'] * float_mult
            if total_events > r2_threshold or total_events > p95_threshold:
                triggered.append("R2")
                explanations.append(f"Accessed {total_events} records today (baseline avg: {b['avg_daily_volume']:.1f}, p95: {b['max_daily_volume_p95']:.1f})")
                
            # RULE 3 — OFF-HOURS (R3)
            r3_threshold = b['off_hours_rate'] * total_events * 2
            if off_hours_count >= 3 and off_hours_count > r3_threshold:
                triggered.append("R3")
                explanations.append(f"{off_hours_count} accesses outside normal shift hours {e['normal_start']}:00-{e['normal_end']}:00 (baseline rate: {b['off_hours_rate']:.1%})")
                
            # RULE 4 — VIP ACCESS (R4)
            if vip_out_of_panel >= 1:
                triggered.append("R4")
                explanations.append(f"Accessed {vip_out_of_panel} VIP-flagged records with no documented care relationship")
                
            # RULE 5 — CROSS-DEPT (R5)
            r5_threshold = b['cross_dept_rate'] * total_events * 2 * float_mult
            if cross_dept_count >= 3 and cross_dept_count > r5_threshold:
                triggered.append("R5")
                explanations.append(f"{cross_dept_count} accesses to patients outside primary department (baseline rate: {b['cross_dept_rate']:.1%})")
                
            # RULE 6 — BULK EXPORT/PRINT (R6)
            r6_threshold = b['export_print_rate'] * total_events * 2
            if export_print_count >= 5 and export_print_count > r6_threshold:
                triggered.append("R6")
                explanations.append(f"{export_print_count} export/print events in one day (baseline rate: {b['export_print_rate']:.1%})")
                
            # RULE 7 — BREAK-GLASS ABUSE (R7)
            r7_threshold = b['break_glass_rate'] * total_events * 2
            if break_glass_count >= 2 and break_glass_count > r7_threshold:
                triggered.append("R7")
                explanations.append(f"{break_glass_count} emergency override events with no documented justification (baseline rate: {b['break_glass_rate']:.1%})")
                
            # Severity Logic
            count = len(triggered)
            if count == 0:
                continue
                
            severity = "Low"
            if "R4" in triggered:
                if count > 1:
                    severity = "Critical"
                else:
                    severity = "Medium"
            elif count == 2:
                severity = "Medium"
            elif count >= 3:
                severity = "High"
                
            # Store only Medium+ alerts
            if severity != "Low":
                full_explanation = f"{b['role']} employee on {alert_date}: " + ". ".join(explanations) + "."
                all_alerts.append((
                    emp_id, str(alert_date), ",".join(triggered), count, severity, full_explanation,
                    total_events, out_of_panel, off_hours_count, export_print_count,
                    break_glass_count, vip_out_of_panel, cross_dept_count,
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                ))
                for r in triggered:
                    rule_usage[r] += 1

    # Batch insert alerts
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO alerts (
            emp_id, alert_date, rules_triggered, rule_count, severity, explanation,
            event_count, out_of_panel, off_hours_count, export_print_count,
            break_glass_count, vip_out_of_panel, cross_dept_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, all_alerts)
    conn.commit()
    conn.close()
    
    runtime = time.time() - start_time
    
    # Final Summary
    df_results = pd.DataFrame(all_alerts, columns=[
        'emp_id', 'alert_date', 'rules', 'count', 'severity', 'explanation',
        'event_count', 'out_of_panel', 'off_hours', 'export', 'break', 'vip', 'cross', 'created'
    ])
    
    print("\n=== RULES ENGINE SUMMARY ===")
    print(f"Total alerts generated (Medium+): {len(df_results)}")
    print("\nBreakdown by severity:")
    print(df_results['severity'].value_counts())
    
    print("\nBreakdown by rule triggered:")
    for r, c in sorted(rule_usage.items(), key=lambda x: x[1], reverse=True):
        print(f" - {r}: {c}")
        
    print("\nAttacker Detection Rate:")
    for emp_id, anomaly in attackers.items():
        alert_days = len(df_results[df_results['emp_id'] == emp_id]['alert_date'].unique())
        print(f" - EMP_ID {emp_id} ({anomaly}): {alert_days} alert days generated")
        
    print("\nFalse Positive Check (Non-attackers with 5+ alert days):")
    fp_df = df_results[~df_results['emp_id'].isin(attackers.keys())]
    fp_counts = fp_df.groupby('emp_id').size()
    fps = fp_counts[fp_counts > 5]
    if fps.empty:
        print(" - None found (Clean baseline)")
    else:
        for eid, count in fps.items():
            print(f" - EMP_ID {eid}: {count} alert days")
            
    print(f"\nScript runtime: {runtime:.2f} seconds")
    print("==========================================================")

if __name__ == "__main__":
    run_rules_engine()
