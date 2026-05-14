import sqlite3
import pandas as pd
import numpy as np
import json
import os
import time
from datetime import datetime, timezone
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# ─── CONFIGURATION ──────────────────────────────────────────
DB_PATH = "./sentinel.db"
MOCK_DATA_DIR = "./mock_data/"

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def setup_anomaly_tables(conn):
    cursor = conn.cursor()
    
    # Create anomaly_scores table
    cursor.execute("DROP TABLE IF EXISTS anomaly_scores")
    cursor.execute("""
    CREATE TABLE anomaly_scores (
        score_id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER,
        score_date TEXT,
        anomaly_score REAL,
        feature_vector TEXT,
        created_at TEXT
    )
    """)
    cursor.execute("CREATE INDEX idx_scores_emp_date ON anomaly_scores (emp_id, score_date)")
    cursor.execute("CREATE INDEX idx_scores_val ON anomaly_scores (anomaly_score DESC)")
    
    # Idempotent ALTER TABLE for alerts
    cursor.execute("PRAGMA table_info(alerts)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if 'anomaly_score' not in existing_cols:
        cursor.execute("ALTER TABLE alerts ADD COLUMN anomaly_score REAL DEFAULT 0.0")
    if 'adjusted_severity' not in existing_cols:
        cursor.execute("ALTER TABLE alerts ADD COLUMN adjusted_severity TEXT DEFAULT ''")
    
    conn.commit()

def build_feature_matrix(conn):
    print("Building feature matrix from audit events and baselines...")
    
    # Load audit events, baselines, and alerts (to get rule counts)
    df_audit = pd.read_sql_query("""
        SELECT emp_id, action_datetime, pat_id, in_panel, is_vip_access, dept_id, action_c
        FROM audit_events WHERE is_known_user = 1
    """, conn)
    df_baselines = pd.read_sql_query("SELECT * FROM user_baselines", conn)
    df_alerts = pd.read_sql_query("SELECT emp_id, alert_date, rule_count FROM alerts", conn)
    df_employees = pd.read_sql_query("SELECT emp_id, normal_start, normal_end FROM employees", conn)
    
    df_audit['action_datetime'] = pd.to_datetime(df_audit['action_datetime'])
    df_audit['date'] = df_audit['action_datetime'].dt.date.astype(str)
    df_audit['hour'] = df_audit['action_datetime'].dt.hour
    
    # Group by emp_id and date
    daily_groups = df_audit.groupby(['emp_id', 'date'])
    
    baseline_lookup = df_baselines.set_index('emp_id').to_dict('index')
    emp_lookup = df_employees.set_index('emp_id').to_dict('index')
    alert_lookup = df_alerts.set_index(['emp_id', 'alert_date'])['rule_count'].to_dict()
    
    features = []
    
    for (emp_id, date_str), group in daily_groups:
        if emp_id not in baseline_lookup or emp_id not in emp_lookup:
            continue
            
        b = baseline_lookup[emp_id]
        e = emp_lookup[emp_id]
        
        # Calculate daily metrics for features
        total_events = len(group)
        out_of_panel_count = len(group[(group['in_panel'] == 0) & (group['pat_id'].notna())])
        total_patient_events = len(group[group['pat_id'].notna()])
        off_hours_count = len(group[(group['hour'] < e['normal_start']) | (group['hour'] > e['normal_end'])])
        export_print_count = len(group[group['action_c'].isin([3, 4])])
        vip_out_of_panel = len(group[(group['is_vip_access'] == 1) & (group['in_panel'] == 0)])
        cross_dept_count = len(group[group['dept_id'] != b['primary_dept_id']])
        unique_patients_today = group['pat_id'].nunique()
        
        # Feature calculations
        f1 = np.clip((total_events - b['avg_daily_volume']) / b['std_daily_volume'], -3, 10)
        f2 = out_of_panel_count / max(total_patient_events, 1)
        f3 = off_hours_count / max(total_events, 1)
        f4 = export_print_count / max(total_events, 1)
        f5 = float(break_glass_count := len(group[group['action_c'] == 5]))
        f6 = float(vip_out_of_panel)
        f7 = cross_dept_count / max(total_events, 1)
        f8 = np.clip((unique_patients_today - b['avg_unique_patients_day']) / b['std_unique_patients_day'], -3, 10)
        f9 = float(alert_lookup.get((emp_id, date_str), 0))
        
        features.append({
            'emp_id': emp_id,
            'score_date': date_str,
            'f1': f1, 'f2': f2, 'f3': f3, 'f4': f4, 'f5': f5,
            'f6': f6, 'f7': f7, 'f8': f8, 'f9': f9
        })
        
    return pd.DataFrame(features).fillna(0)

def run_anomaly_detector():
    start_time = time.time()
    conn = get_db_connection()
    setup_anomaly_tables(conn)
    
    df_features = build_feature_matrix(conn)
    if df_features.empty:
        print("No data found to score.")
        return
        
    # Isolation Forest Training
    print(f"Training Isolation Forest on {len(df_features)} employee-days...")
    X = df_features[['f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9']]
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = IsolationForest(
        n_estimators=200,
        contamination=0.02,
        random_state=42,
        max_samples='auto'
    )
    model.fit(X_scaled)
    
    # Scoring
    raw_scores = model.score_samples(X_scaled)
    min_s, max_s = raw_scores.min(), raw_scores.max()
    # Normalize to 0-1 and invert (1.0 = most anomalous)
    normalized = (raw_scores - min_s) / (max_s - min_s)
    anomaly_scores = 1.0 - normalized
    
    df_features['anomaly_score'] = anomaly_scores
    
    # Prepare and store scores
    print("Storing anomaly scores in database...")
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    score_records = []
    for _, row in df_features.iterrows():
        f_vec = {f'f{i}': row[f'f{i}'] for i in range(1, 10)}
        score_records.append((
            int(row['emp_id']),
            row['score_date'],
            float(row['anomaly_score']),
            json.dumps(f_vec),
            now_utc
        ))
        
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO anomaly_scores (emp_id, score_date, anomaly_score, feature_vector, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, score_records)
    conn.commit()
    
    # Update Alerts Table
    print("Updating alerts with anomaly scores and adjusted severity...")
    cursor.execute("SELECT emp_id, alert_date, severity FROM alerts")
    alerts = cursor.fetchall()
    
    # Create a lookup for anomaly scores
    score_lookup = df_features.set_index(['emp_id', 'score_date'])['anomaly_score'].to_dict()
    
    update_records = []
    for emp_id, alert_date, original_severity in alerts:
        score = score_lookup.get((emp_id, alert_date), 0.0)
        
        adjusted = original_severity
        if original_severity == "Medium":
            if score >= 0.7:
                adjusted = "High"
            elif score >= 0.4:
                adjusted = "Medium"
            else:
                adjusted = "Suppressed"
        
        update_records.append((score, adjusted, emp_id, alert_date))
        
    cursor.executemany("""
        UPDATE alerts SET anomaly_score = ?, adjusted_severity = ?
        WHERE emp_id = ? AND alert_date = ?
    """, update_records)
    conn.commit()
    
    # Load attacker manifest for summary
    attackers = {}
    manifest_path = os.path.join(MOCK_DATA_DIR, "attacker_manifest.txt")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            for line in f:
                parts = line.split(",")
                emp_id = int(parts[0].split(":")[1].strip())
                attackers[emp_id] = parts[2].split(":")[1].strip()

    # Summary Calculations
    runtime = time.time() - start_time
    print("\n=== ANOMALY DETECTION SUMMARY ===")
    print(f"Total employee-days scored: {len(df_features):,}")
    print(f"Score distribution:")
    print(f" - Mean: {anomaly_scores.mean():.4f}")
    print(f" - Std:  {anomaly_scores.std():.4f}")
    print(f" - P90:  {np.percentile(anomaly_scores, 90):.4f}")
    print(f" - P99:  {np.percentile(anomaly_scores, 99):.4f}")
    
    # Re-ranking results
    df_alerts_after = pd.read_sql_query("SELECT * FROM alerts", conn)
    upgraded = len(df_alerts_after[(df_alerts_after['severity'] == 'Medium') & (df_alerts_after['adjusted_severity'] == 'High')])
    suppressed = len(df_alerts_after[df_alerts_after['adjusted_severity'] == 'Suppressed'])
    kept_med = len(df_alerts_after[(df_alerts_after['severity'] == 'Medium') & (df_alerts_after['adjusted_severity'] == 'Medium')])
    
    print("\nAlert Re-ranking Results:")
    print(f" - Upgraded to High:  {upgraded}")
    print(f" - Suppressed:        {suppressed}")
    print(f" - Kept as Medium:    {kept_med}")
    
    print("\nAttacker Score Check:")
    for eid, anomaly in attackers.items():
        all_emp_scores = df_features[df_features['emp_id'] == eid]['anomaly_score']
        alert_days_scores = df_alerts_after[df_alerts_after['emp_id'] == eid]['anomaly_score']
        print(f" - EMP_ID {eid} ({anomaly}):")
        print(f"   * Mean Alert Score: {alert_days_scores.mean():.4f}")
        print(f"   * Mean Daily Score: {all_emp_scores.mean():.4f}")
        
    print("\nFalse Positive Reduction Check:")
    non_attacker_ids = [eid for eid in df_features['emp_id'].unique() if eid not in attackers]
    fp_before = len(df_alerts_after[(df_alerts_after['emp_id'].isin(non_attacker_ids)) & (df_alerts_after['severity'].isin(['Medium', 'High', 'Critical']))])
    fp_after = len(df_alerts_after[(df_alerts_after['emp_id'].isin(non_attacker_ids)) & (df_alerts_after['adjusted_severity'].isin(['Medium', 'High', 'Critical']))])
    reduction = (1 - (fp_after / fp_before)) * 100 if fp_before > 0 else 0
    print(f" - Medium+ Alerts for Non-Attackers (Before): {fp_before}")
    print(f" - Medium+ Alerts for Non-Attackers (After):  {fp_after}")
    print(f" - Reduction Percentage: {reduction:.1f}%")
    
    print(f"\nScript runtime: {runtime:.2f} seconds")
    print("==========================================================")
    conn.close()

if __name__ == "__main__":
    run_anomaly_detector()
