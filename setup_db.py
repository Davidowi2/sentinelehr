from db import get_connection
import case_logic
from datetime import datetime

def setup_database():
    print("=== Initializing Neon PostgreSQL Database ===")
    conn = get_connection()
    cursor = conn.cursor()
    
    # 0. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL, -- compliance_officer, it_director, admin
        email TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )
    """)
    
    # Seed users if not exists
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()['count'] == 0:
        print("Seeding initial users...")
        users_to_seed = [
            ("demo", "hbh-demo-2026", "compliance_officer", "demo@sentinelehr.com"),
            ("it_demo", "it-demo-2026", "it_director", "it_demo@sentinelehr.com"),
            ("admin", "sentinelehr2026", "admin", "admin@sentinelehr.com")
        ]
        for uname, pwd, role, email in users_to_seed:
            hashed = case_logic.hash_password(pwd)
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, email)
                VALUES (%s, %s, %s, %s)
            """, (uname, hashed, role, email))
        print("Users seeded.")

    # 1. Employees Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        emp_id INTEGER PRIMARY KEY,
        role TEXT,
        dept_id INTEGER,
        normal_start INTEGER,
        normal_end INTEGER,
        is_float INTEGER
    )
    """)
    
    # 2. Patients Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        pat_id INTEGER PRIMARY KEY,
        is_vip INTEGER,
        primary_dept_id INTEGER
    )
    """)
    
    # 3. Patient Panels Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patient_panels (
        emp_id INTEGER,
        pat_id INTEGER,
        PRIMARY KEY (emp_id, pat_id)
    )
    """)
    
    # 4. Audit Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_events (
        audit_id INTEGER PRIMARY KEY,
        emp_id INTEGER,
        pat_id INTEGER,
        action_c INTEGER,
        action_datetime TIMESTAMP,
        dept_id INTEGER,
        workstation_id TEXT,
        session_id TEXT,
        in_panel INTEGER,
        is_vip_access INTEGER,
        justification TEXT,
        anomaly_type TEXT,
        is_known_user INTEGER,
        ingested_at TIMESTAMP
    )
    """)
    
    # 5. User Baselines Table
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
        last_calculated_at TIMESTAMP
    )
    """)
    
    # 6. Alerts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        alert_id SERIAL PRIMARY KEY,
        emp_id INTEGER,
        alert_date DATE,
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
        created_at TIMESTAMP,
        status TEXT DEFAULT 'open',
        reviewer_notes TEXT DEFAULT '',
        priority_rank INTEGER,
        reviewed_by TEXT DEFAULT '',
        reviewed_at TIMESTAMP,
        anomaly_score REAL DEFAULT 0.0,
        adjusted_severity TEXT DEFAULT ''
    )
    """)
    
    # 7. Anomaly Scores Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS anomaly_scores (
        score_id SERIAL PRIMARY KEY,
        emp_id INTEGER,
        score_date DATE,
        anomaly_score REAL,
        feature_vector TEXT,
        created_at TIMESTAMP
    )
    """)
    
    # 8. Ingestion Watermark Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ingestion_watermark (
        id INTEGER PRIMARY KEY DEFAULT 1,
        last_ingested_date TEXT,
        last_run_at TIMESTAMP
    )
    """)
    
    # 9. Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_emp_date ON audit_events (emp_id, action_datetime);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_pat ON audit_events (pat_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_dept ON audit_events (dept_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_known ON audit_events (is_known_user);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_emp_date ON alerts (emp_id, alert_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts (severity);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_ack ON alerts (is_acknowledged);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_emp_date ON anomaly_scores (emp_id, score_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_val ON anomaly_scores (anomaly_score DESC);")
    
    # 10. Views
    cursor.execute("DROP VIEW IF EXISTS active_alerts")
    cursor.execute("""
        CREATE VIEW active_alerts AS
        SELECT * FROM alerts
        WHERE adjusted_severity != 'Suppressed'
        AND status != 'resolved'
        ORDER BY priority_rank ASC
    """)
    
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
    conn.close()
    print("All tables and views created in Neon PostgreSQL")

if __name__ == "__main__":
    setup_database()
