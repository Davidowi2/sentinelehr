import pandas as pd
import numpy as np
import os
import time
from datetime import datetime, timezone
from db import get_connection
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

def get_db_connection():
    return get_connection()

def run_alert_manager():
    start_time = time.time()
    conn = get_db_connection()
    
    print("Computing priority rankings for alerts...")
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
    
    # Load alerts and anomaly scores
    df_alerts = pd.read_sql_query("SELECT * FROM alerts", engine)
    df_scores = pd.read_sql_query("SELECT * FROM anomaly_scores", engine)
    
    if df_alerts.empty:
        print("No alerts to process.")
        conn.close()
        return
        
    df_alerts['alert_date'] = df_alerts['alert_date'].astype(str)
    df_scores['score_date'] = df_scores['score_date'].astype(str)
    
    # Merge alerts with scores
    # Note: Use suffixes to handle overlapping column names if any
    df = df_alerts.merge(df_scores[['emp_id', 'score_date', 'anomaly_score']], 
                         left_on=['emp_id', 'alert_date'], 
                         right_on=['emp_id', 'score_date'], 
                         how='left', suffixes=('', '_new'))
    
    df['anomaly_score'] = df['anomaly_score_new'].fillna(0)
    
    # Priority Logic
    def calculate_adjusted_severity(row):
        score = row['anomaly_score']
        sev = row['severity']
        
        if score > 8.0: return "Critical"
        if score > 5.0:
            if sev == "High": return "Critical"
            return "High"
        if score < 1.0:
            if sev == "Critical": return "High"
            if sev == "High": return "Medium"
            return "Suppressed" # Demote Low/Medium with low anomaly score
            
        return sev

    df['adjusted_severity'] = df.apply(calculate_adjusted_severity, axis=1)
    
    # Calculate priority_rank (1=Critical, 2=High, 3=Medium, 4=Low/Suppressed)
    rank_map = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4, "Suppressed": 5}
    df['priority_rank'] = df['adjusted_severity'].map(rank_map).fillna(5)
    
    # Update the database
    print(f"Updating {len(df)} alerts with adjusted severity and scores...")
    cursor = conn.cursor()
    
    # We'll use a temporary table to do a bulk update
    cursor.execute("CREATE TEMP TABLE alerts_update (alert_id INT, anomaly_score REAL, adjusted_severity TEXT, priority_rank INT)")
    
    update_data = df[['alert_id', 'anomaly_score', 'adjusted_severity', 'priority_rank']].values.tolist()
    
    from psycopg2.extras import execute_values
    execute_values(cursor, "INSERT INTO alerts_update (alert_id, anomaly_score, adjusted_severity, priority_rank) VALUES %s", update_data)
    
    cursor.execute("""
        UPDATE alerts a
        SET anomaly_score = u.anomaly_score,
            adjusted_severity = u.adjusted_severity,
            priority_rank = u.priority_rank
        FROM alerts_update u
        WHERE a.alert_id = u.alert_id
    """)
    
    conn.commit()
    
    # Final Summary
    counts = df['adjusted_severity'].value_counts()
    
    print(f"\n=== ALERT MANAGER SUMMARY ===")
    print(f"Total alerts processed: {len(df)}")
    print(f"  Critical: {counts.get('Critical', 0)}")
    print(f"  High:     {counts.get('High', 0)}")
    print(f"  Medium:   {counts.get('Medium', 0)}")
    print(f"  Suppressed: {counts.get('Suppressed', 0)}")
    print(f"Processing time: {time.time() - start_time:.2f} seconds")
    
    conn.close()

if __name__ == "__main__":
    run_alert_manager()
