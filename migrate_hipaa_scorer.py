import os
from db import get_connection

def migrate():
    print("=== Running HIPAA 4-Factor Risk Scorer Migration ===")
    conn = get_connection()
    cursor = conn.cursor()
    
    # Add new columns to cases table
    print("Adding ocr_risk_score and requires_ocr_review columns to cases table...")
    try:
        cursor.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS ocr_risk_score FLOAT DEFAULT 0.0;")
        cursor.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS requires_ocr_review INTEGER DEFAULT 0;")
        conn.commit()
        print("Migration successful.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
