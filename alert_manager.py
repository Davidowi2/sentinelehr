import pandas as pd
import numpy as np
import os
import time
from datetime import datetime, timezone
from db import get_connection
from dotenv import load_dotenv
from sqlalchemy import create_engine
from email_service import send_critical_alert_email

load_dotenv()

def get_db_connection():
    return get_connection()

def run_alert_manager(org_id: int = 1):
    start_time = time.time()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('BEGIN')

        print("Computing priority rankings for alerts...")
        DATABASE_URL = os.getenv("DATABASE_URL")
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        engine = create_engine(DATABASE_URL)

        # Load alerts and anomaly scores — scoped to org
        df_alerts = pd.read_sql_query(
            "SELECT * FROM alerts WHERE organization_id = %s",
            engine, params=(org_id,)
        )
        df_scores = pd.read_sql_query(
            "SELECT * FROM anomaly_scores WHERE organization_id = %s",
            engine, params=(org_id,)
        )

        if df_alerts.empty:
            print(f"No alerts to process for org {org_id}.")
            conn.rollback()
            return

        df_alerts['alert_date'] = df_alerts['alert_date'].astype(str)
        df_scores['score_date'] = df_scores['score_date'].astype(str)

        # Merge alerts with scores
        df = df_alerts.merge(df_scores[['emp_id', 'score_date', 'anomaly_score']],
                             left_on=['emp_id', 'alert_date'],
                             right_on=['emp_id', 'score_date'],
                             how='left', suffixes=('', '_new'))

        df['anomaly_score'] = df['anomaly_score_new'].fillna(0)

        # Priority Logic
        def calculate_adjusted_severity(row):
            score = row['anomaly_score']
            sev = row['severity']

            if score > 0.8: return "Critical"
            if score > 0.5:
                if sev == "High": return "Critical"
                return "High"
            if score < 0.3:
                if sev == "Critical": return "High"
                if sev == "High": return "Medium"
                return "Suppressed"  # Demote Low/Medium with low anomaly score

            return sev

        df['adjusted_severity'] = df.apply(calculate_adjusted_severity, axis=1)

        # Apply R8 override in Python to ensure summary is accurate
        mask_r8 = (df['rules_triggered'].str.contains('R8')) & (df['rule_count'] > 1) & (df['adjusted_severity'] != 'Suppressed')
        df.loc[mask_r8, 'adjusted_severity'] = 'Critical'

        # Calculate priority_rank (1=Critical, 2=High, 3=Medium, 4=Low/Suppressed)
        rank_map = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4, "Suppressed": 5}
        df['priority_rank'] = df['adjusted_severity'].map(rank_map).fillna(5)

        # Update the database
        print(f"Updating {len(df)} alerts with adjusted severity and scores...")

        # Bulk update via temp table
        cursor.execute("CREATE TEMP TABLE alerts_update (alert_id INT, anomaly_score REAL, adjusted_severity TEXT, priority_rank INT)")

        update_data = df[['alert_id', 'anomaly_score', 'adjusted_severity', 'priority_rank']].values.tolist()

        from psycopg2.extras import execute_values
        execute_values(cursor, "INSERT INTO alerts_update (alert_id, anomaly_score, adjusted_severity, priority_rank) VALUES %s", update_data)

        # Update anomaly_score — scoped to org
        cursor.execute("""
            UPDATE alerts a
            SET anomaly_score = s.anomaly_score
            FROM anomaly_scores s
            WHERE a.emp_id = s.emp_id
            AND DATE(a.alert_date) = DATE(s.score_date)
            AND a.organization_id = %(org_id)s
            AND s.organization_id = %(org_id)s
        """, {'org_id': org_id})

        # Update adjusted_severity and priority_rank — scoped to org
        cursor.execute("""
            UPDATE alerts a
            SET adjusted_severity = u.adjusted_severity,
                priority_rank = u.priority_rank
            FROM alerts_update u
            WHERE a.alert_id = u.alert_id
            AND a.organization_id = %(org_id)s
        """, {'org_id': org_id})

        # R8 Critical override — scoped to org
        cursor.execute("""
            UPDATE alerts
            SET adjusted_severity = 'Critical'
            WHERE rules_triggered LIKE '%%R8%%'
            AND rule_count > 1
            AND adjusted_severity != 'Suppressed'
            AND organization_id = %(org_id)s
        """, {'org_id': org_id})

        conn.commit()
        print(f'[DETECTION] Alert manager complete for org {org_id}')

    except Exception as e:
        conn.rollback()
        print(f'[DETECTION] Alert manager failed for org {org_id}, rolled back: {str(e)}')
        raise
    finally:
        conn.close()

    # Trigger emails for new critical alerts (after transaction closes)
    critical_alerts = df[df['adjusted_severity'] == 'Critical']
    for _, row in critical_alerts.iterrows():
        send_critical_alert_email(
            alert_id=int(row['alert_id']),
            anomaly_type=row['rules_triggered'],
            emp_id=int(row['emp_id']),
            score=float(row['anomaly_score'])
        )

    # Final Summary
    counts = df['adjusted_severity'].value_counts()

    print(f"\n=== ALERT MANAGER SUMMARY ===")
    print(f"Total alerts processed: {len(df)}")
    print(f"  Critical:   {counts.get('Critical', 0)}")
    print(f"  High:       {counts.get('High', 0)}")
    print(f"  Medium:     {counts.get('Medium', 0)}")
    print(f"  Suppressed: {counts.get('Suppressed', 0)}")
    print(f"Processing time: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        try:
            org_id = int(sys.argv[1])
        except ValueError:
            print("Error: org_id must be an integer. Usage: python alert_manager.py <org_id>")
            sys.exit(1)
    else:
        print("Error: org_id required. Usage: python alert_manager.py <org_id>")
        print("Example: python alert_manager.py 1")
        sys.exit(1)
    run_alert_manager(org_id)
