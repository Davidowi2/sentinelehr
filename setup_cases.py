import os
from dotenv import load_dotenv
from db import get_connection
from passlib.context import CryptContext

load_dotenv()

def setup():
    conn = get_connection()
    cursor = conn.cursor()

    # TABLE 1: users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id              SERIAL PRIMARY KEY,
      username        TEXT UNIQUE NOT NULL,
      email           TEXT UNIQUE NOT NULL,
      password_hash   TEXT NOT NULL,
      role            TEXT NOT NULL
                      CHECK (role IN ('admin','investigator','auditor')),
      is_senior       BOOLEAN DEFAULT false,
      active          BOOLEAN DEFAULT true,
      created_at      TIMESTAMP DEFAULT NOW()
    );
    """)

    # TABLE 2: cases
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cases (
      case_id         TEXT PRIMARY KEY,
      emp_id          INTEGER NOT NULL,
      patient_ids     JSONB DEFAULT '[]',
      department      TEXT,
      status          TEXT NOT NULL DEFAULT 'Open'
                      CHECK (status IN (
                        'Open',
                        'Under Investigation',
                        'Pending HR',
                        'Resolved',
                        'Closed'
                      )),
      priority        TEXT NOT NULL DEFAULT 'Medium'
                      CHECK (priority IN ('Low','Medium','Critical')),
      assigned_to     INTEGER REFERENCES users(id) NULL,
      alert_ids       JSONB DEFAULT '[]',
      window_start    TIMESTAMP NOT NULL,
      window_end      TIMESTAMP NOT NULL,
      outcome         TEXT NULL
                      CHECK (outcome IN (
                        'Legitimate Access',
                        'Policy Violation',
                        'Training Required',
                        'Termination Recommended',
                        'No Action',
                        NULL
                      )),
      created_at      TIMESTAMP DEFAULT NOW(),
      updated_at      TIMESTAMP DEFAULT NOW(),
      resolved_at     TIMESTAMP NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_emp_id ON cases(emp_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_window ON cases(window_start, window_end);")

    # TABLE 3: case_audit_log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS case_audit_log (
      id              SERIAL PRIMARY KEY,
      case_id         TEXT NOT NULL REFERENCES cases(case_id),
      user_id         INTEGER NULL REFERENCES users(id),
      action          TEXT NOT NULL,
      field_name      TEXT NULL,
      old_value       TEXT NULL,
      new_value       TEXT NULL,
      note            TEXT NULL,
      timestamp       TIMESTAMP DEFAULT NOW()
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_case_id ON case_audit_log(case_id);")

    # TABLE 4: watchlist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watchlist (
      id              SERIAL PRIMARY KEY,
      emp_id          INTEGER NOT NULL,
      added_at        TIMESTAMP DEFAULT NOW(),
      added_by        TEXT NOT NULL,
      reason          TEXT NOT NULL,
      active          BOOLEAN DEFAULT true,
      escalation_threshold INTEGER DEFAULT 1
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_emp ON watchlist(emp_id, active);")

    # ALTER TABLE alerts
    cursor.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='alerts' AND column_name='case_id') THEN
            ALTER TABLE alerts ADD COLUMN case_id TEXT NULL REFERENCES cases(case_id);
        END IF;
    END
    $$;
    """)

    # BOOTSTRAP ADMIN USER
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()['count'] == 0:
        username = os.getenv("ADMIN_USERNAME", "admin")
        email = os.getenv("ADMIN_EMAIL", "admin@sentinelehr.com")
        password = os.getenv("ADMIN_PASSWORD", "sentinelehr2026")
        
        import bcrypt
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, is_senior)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, email, hashed, 'admin', True))
        print("Bootstrap admin user: created")
    else:
        print("Bootstrap admin user: already exists")

    conn.commit()
    conn.close()
    
    print("Tables created: users, cases, case_audit_log, watchlist")
    print("alerts.case_id column: added or already exists")

if __name__ == "__main__":
    setup()
