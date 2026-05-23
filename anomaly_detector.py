import pandas as pd
import numpy as np
import json
import os
import time
from datetime import datetime, timezone
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from db import get_connection
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

# ─── CONFIGURATION ──────────────────────────────────────────
MOCK_DATA_DIR = "./mock_data/"

def get_db_connection():
    return get_connection()

def setup_anomaly_tables(conn):
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE anomaly_scores RESTART IDENTITY")
    conn.commit()

def build_feature_matrix(conn):
    print("Building feature matrix from audit events and baselines...")
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
    
    df_audit = pd.read_sql_query("""
        SELECT audit_id, emp_id, action_datetime, pat_id, in_panel, is_vip_access, dept_id, action_c, is_sensitive_access
        FROM audit_events WHERE is_known_user = 1
    """, engine)
    df_baselines = pd.read_sql_query("SELECT * FROM user_baselines", engine)
    df_alerts = pd.read_sql_query("SELECT emp_id, alert_date, rule_count FROM alerts", engine)
    df_employees = pd.read_sql_query("SELECT emp_id, normal_start, normal_end FROM employees", engine)
    
    df_audit['action_datetime'] = pd.to_datetime(df_audit['action_datetime'])
    df_audit['date'] = df_audit['action_datetime'].dt.date.astype(str)
    df_audit['hour'] = df_audit['action_datetime'].dt.hour
    
    # Merge baselines and employee info
    df = df_audit.merge(df_baselines, on='emp_id', how='inner')
    df = df.merge(df_employees, on='emp_id', how='inner', suffixes=('', '_emp'))
    
    # Row-level indicators
    print("Calculating row-level indicators...")
    df['is_patient_event'] = df['pat_id'].notna().astype(int)
    df['is_out_of_panel'] = ((df['in_panel'] == 0) & (df['pat_id'].notna())).astype(int)
    df['is_off_hours'] = ((df['hour'] < df['normal_start']) | (df['hour'] > df['normal_end'])).astype(int)
    df['is_export_print'] = df['action_c'].isin([3, 4]).astype(int)
    df['is_break_glass'] = (df['action_c'] == 5).astype(int)
    df['is_vip_out_of_panel'] = ((df['is_vip_access'] == 1) & (df['in_panel'] == 0)).astype(int)
    df['is_cross_dept'] = (df['dept_id'] != df['primary_dept_id']).astype(int)
    df['is_sensitive_out_of_panel'] = ((df['is_sensitive_access'] == 1) & (df['in_panel'] == 0)).astype(int)
    
    # Aggregate daily
    print("Aggregating to daily metrics...")
    daily = df.groupby(['emp_id', 'date']).agg({
        'audit_id': 'count',
        'is_patient_event': 'sum',
        'is_out_of_panel': 'sum',
        'is_off_hours': 'sum',
        'is_export_print': 'sum',
        'is_break_glass': 'sum',
        'is_vip_out_of_panel': 'sum',
        'is_cross_dept': 'sum',
        'is_sensitive_out_of_panel': 'sum',
        'pat_id': 'nunique'
    }).rename(columns={'audit_id': 'total_events', 'pat_id': 'unique_patients_today'}).reset_index()
    
    # Re-merge baselines for feature calc
    daily = daily.merge(df_baselines, on='emp_id', how='inner')
    
    # Merge alert counts
    df_alerts['alert_date'] = df_alerts['alert_date'].astype(str)
    daily = daily.merge(df_alerts, left_on=['emp_id', 'date'], right_on=['emp_id', 'alert_date'], how='left')
    daily['rule_count'] = daily['rule_count'].fillna(0)
    
    # Feature Calculations
    print("Calculating features...")
    daily['f1'] = np.clip((daily['total_events'] - daily['avg_daily_volume']) / np.maximum(daily['std_daily_volume'], 0.1), -3, 10)
    daily['f2'] = daily['is_out_of_panel'] / np.maximum(daily['is_patient_event'], 1)
    daily['f3'] = daily['is_off_hours'] / np.maximum(daily['total_events'], 1)
    daily['f4'] = daily['is_export_print'] / np.maximum(daily['total_events'], 1)
    daily['f5'] = daily['is_break_glass'].astype(float)
    daily['f6'] = daily['is_vip_out_of_panel'].astype(float)
    daily['f7'] = daily['is_cross_dept'] / np.maximum(daily['total_events'], 1)
    daily['f8'] = np.clip((daily['unique_patients_today'] - daily['avg_unique_patients_day']) / np.maximum(daily['std_unique_patients_day'], 0.1), -3, 10)
    daily['f9'] = daily['rule_count'].astype(float)
    daily['f10'] = daily['is_sensitive_out_of_panel'] / np.maximum(daily['total_events'], 1)
    
    feature_cols = ['emp_id', 'date', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10']
    return daily[feature_cols].rename(columns={'date': 'score_date'}).fillna(0)

def run_anomaly_detector():
    start_time = time.time()
    conn = get_db_connection()
    setup_anomaly_tables(conn)
    
    df_features = build_feature_matrix(conn)
    if df_features.empty:
        print("No features built. Exiting.")
        conn.close()
        return
        
    print(f"Training Isolation Forest on {len(df_features)} daily profiles...")
    X = df_features[['f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10']].values
    
    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Model
    model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    model.fit(X_scaled)
    
    # score_samples returns negative values (more negative = more anomalous)
    raw_scores = model.score_samples(X_scaled)
    
    # Normalize to 0-1 where 1.0 = most anomalous
    min_score = raw_scores.min()
    max_score = raw_scores.max()
    normalized = (raw_scores - min_score) / (max_score - min_score)
    df_features['normalized_score'] = 1.0 - normalized
    
    # Store scores
    print("Storing anomaly scores...")
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
    
    scores_to_store = df_features[['emp_id', 'score_date', 'normalized_score']].copy()
    scores_to_store.columns = ['emp_id', 'score_date', 'anomaly_score']
    scores_to_store['created_at'] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    scores_to_store.to_sql('anomaly_scores', engine, if_exists='append', index=False)
    
    # Update audit_events with anomaly_type for future reference
    # For now, let's just mark the top 1% as 'ML_ANOMALY'
    threshold = np.percentile(df_features['normalized_score'], 99)
    top_anomalies = df_features[df_features['normalized_score'] >= threshold]
    
    print(f"Updating audit_events for {len(top_anomalies)} anomalous user-days...")
    cursor = conn.cursor()
    for _, row in top_anomalies.iterrows():
        cursor.execute("""
            UPDATE audit_events 
            SET anomaly_type = 'ML_ANOMALY' 
            WHERE emp_id = %s AND action_datetime::date = %s
        """, (int(row['emp_id']), row['score_date']))
    conn.commit()
    
    # False Positive Reduction calculation
    # Let's say we only keep alerts with score > 2.0
    df_alerts = pd.read_sql_query("SELECT alert_id, emp_id, alert_date FROM alerts", engine)
    df_alerts['alert_date'] = df_alerts['alert_date'].astype(str)
    
    # Merge alerts with scores
    df_eval = df_alerts.merge(df_features, left_on=['emp_id', 'alert_date'], right_on=['emp_id', 'score_date'], how='left')
    
    initial_alerts = len(df_alerts)
    reduced_alerts = len(df_eval[df_eval['normalized_score'] > 0.2])
    reduction = (initial_alerts - reduced_alerts) / initial_alerts if initial_alerts > 0 else 0
    
    print(f"\n=== ANOMALY DETECTOR SUMMARY ===")
    print(f"Initial rules-based alerts:   {initial_alerts}")
    print(f"Post-ML filtered alerts:      {reduced_alerts}")
    print(f"False positive reduction:     {reduction:.1%}")
    print(f"Total processing time:        {time.time() - start_time:.2f}s")
    
    conn.close()

if __name__ == "__main__":
    run_anomaly_detector()
