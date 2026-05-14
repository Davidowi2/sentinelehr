import sqlite3
import os
from datetime import datetime, timezone

# ─── CONFIGURATION ──────────────────────────────────────────
DB_PATH = "./sentinel.db"

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def setup_alert_management(conn):
    cursor = conn.cursor()
    
    # Idempotent column additions
    cursor.execute("PRAGMA table_info(alerts)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    
    col_definitions = {
        'status': "TEXT DEFAULT 'open'",
        'reviewer_notes': "TEXT DEFAULT ''",
        'priority_rank': "INTEGER",
        'reviewed_by': "TEXT DEFAULT ''",
        'reviewed_at': "TEXT DEFAULT ''"
    }
    
    for col, definition in col_definitions.items():
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE alerts ADD COLUMN {col} {definition}")
            print(f"Added column: {col}")
            
    conn.commit()

def compute_priority_rank(conn):
    print("Computing priority rankings for alerts...")
    cursor = conn.cursor()
    
    # Assign priority_rank based on severity tier and anomaly_score
    # Tier mapping: Critical=1, High=2, Medium=3
    cursor.execute("""
        WITH ranked_alerts AS (
            SELECT 
                alert_id,
                adjusted_severity,
                anomaly_score,
                alert_date,
                CASE 
                    WHEN adjusted_severity = 'Critical' THEN 1
                    WHEN adjusted_severity = 'High' THEN 2
                    WHEN adjusted_severity = 'Medium' THEN 3
                    ELSE 4
                END as tier
            FROM alerts
            WHERE adjusted_severity != 'Suppressed'
        )
        SELECT 
            alert_id,
            ROW_NUMBER() OVER (
                ORDER BY tier ASC, anomaly_score DESC, alert_date DESC
            ) as new_rank
        FROM ranked_alerts
    """)
    
    ranks = cursor.fetchall()
    
    # Update priority_rank for non-suppressed alerts
    cursor.executemany(
        "UPDATE alerts SET priority_rank = ? WHERE alert_id = ?",
        [(r[1], r[0]) for r in ranks]
    )
    
    # Set priority_rank for suppressed alerts
    cursor.execute("UPDATE alerts SET priority_rank = 9999 WHERE adjusted_severity = 'Suppressed'")
    
    conn.commit()

def enhance_explanations(conn):
    print("Enhancing alert explanations with ML context...")
    cursor = conn.cursor()
    
    # Population mean from anomaly_detector.py summary was ~0.22
    POP_MEAN = 0.22
    
    # Update explanation where not already enhanced
    cursor.execute(f"""
        UPDATE alerts 
        SET explanation = explanation || ' | ML Anomaly Score: ' || printf('%.2f', anomaly_score) || ' (population mean: {POP_MEAN})'
        WHERE anomaly_score > 0 
        AND explanation NOT LIKE '% | ML Anomaly Score%'
    """)
    
    conn.commit()

def create_views(conn):
    print("Creating SQLite views for dashboarding...")
    cursor = conn.cursor()
    
    # VIEW: active_alerts
    cursor.execute("DROP VIEW IF EXISTS active_alerts")
    cursor.execute("""
        CREATE VIEW active_alerts AS
        SELECT * FROM alerts
        WHERE adjusted_severity != 'Suppressed'
        AND status != 'resolved'
        ORDER BY priority_rank ASC
    """)
    
    # VIEW: daily_digest
    cursor.execute("DROP VIEW IF EXISTS daily_digest")
    cursor.execute("""
        CREATE VIEW daily_digest AS
        SELECT 
            alert_date,
            COUNT(*) as total_alerts,
            SUM(CASE WHEN adjusted_severity = 'Critical' THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN adjusted_severity = 'High' THEN 1 ELSE 0 END) as high_count,
            SUM(CASE WHEN adjusted_severity = 'Medium' THEN 1 ELSE 0 END) as medium_count,
            MAX(anomaly_score) as top_score
        FROM alerts
        WHERE adjusted_severity != 'Suppressed'
        GROUP BY alert_date
        ORDER BY alert_date DESC
    """)
    
    conn.commit()

def print_summary(conn):
    cursor = conn.cursor()
    
    # Total active alerts
    cursor.execute("""
        SELECT 
            COUNT(*),
            SUM(CASE WHEN adjusted_severity = 'Critical' THEN 1 ELSE 0 END),
            SUM(CASE WHEN adjusted_severity = 'High' THEN 1 ELSE 0 END),
            SUM(CASE WHEN adjusted_severity = 'Medium' THEN 1 ELSE 0 END)
        FROM alerts
        WHERE adjusted_severity != 'Suppressed'
        AND status != 'resolved'
    """)
    total, critical, high, medium = cursor.fetchone()
    
    # Top 5 highest priority alerts
    cursor.execute("""
        SELECT emp_id, alert_date, adjusted_severity, anomaly_score, explanation
        FROM alerts
        WHERE adjusted_severity != 'Suppressed'
        AND status != 'resolved'
        ORDER BY priority_rank ASC
        LIMIT 5
    """)
    top_alerts = cursor.fetchall()
    
    # Date range of digest
    cursor.execute("SELECT MIN(alert_date), MAX(alert_date) FROM daily_digest")
    min_date, max_date = cursor.fetchone()
    
    print("\n=== ALERT MANAGEMENT SUMMARY ===")
    print(f"Total active alerts (non-suppressed): {total or 0}")
    print(f" - Critical: {critical or 0}")
    print(f" - High:     {high or 0}")
    print(f" - Medium:   {medium or 0}")
    
    print("\nTop 5 Highest Priority Alerts:")
    print(f"{'EMP_ID':<8} | {'DATE':<12} | {'SEVERITY':<10} | {'SCORE':<6} | {'EXPLANATION (PREVIEW)'}")
    print("-" * 85)
    for a in top_alerts:
        explanation_preview = a[4][:100].replace('\n', ' ') + "..."
        print(f"{a[0]:<8} | {a[1]:<12} | {a[2]:<10} | {a[3]:<6.2f} | {explanation_preview}")
        
    print(f"\nDate range of daily digest: {min_date} to {max_date}")
    print("==========================================================")

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found.")
    else:
        conn = get_db_connection()
        try:
            setup_alert_management(conn)
            compute_priority_rank(conn)
            enhance_explanations(conn)
            create_views(conn)
            print_summary(conn)
        finally:
            conn.close()
