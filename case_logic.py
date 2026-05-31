import json
import os
import bcrypt
from datetime import datetime, timedelta
from db import get_connection
from breach_risk_scorer import calculate_breach_risk

def generate_case_id(year: int) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MAX(CAST(SUBSTRING(case_id FROM 'SEN-[0-9]{4}-([0-9]{4})') AS INTEGER)) as max_id 
        FROM cases 
        WHERE case_id LIKE %s
    """, (f"SEN-{year}-%",))
    result = cursor.fetchone()
    conn.close()
    max_id = result['max_id'] if result['max_id'] is not None else 0
    return f"SEN-{year}-{max_id + 1:04d}"

def find_open_case(emp_id: int) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT case_id FROM cases 
        WHERE emp_id = %s 
        AND status NOT IN ('Resolved', 'Closed') 
        AND NOW() BETWEEN window_start AND window_end
    """, (emp_id,))
    result = cursor.fetchone()
    conn.close()
    return result['case_id'] if result else None

def create_case(
    emp_id: int,
    alert_id: int,
    priority: str,
    department: str,
    patient_ids: list,
    created_by: str = 'system'
) -> str:
    # Fetch the alert's actual date 
    conn2 = get_connection() 
    cur2 = conn2.cursor() 
    cur2.execute( 
      "SELECT alert_date FROM alerts WHERE alert_id = %s", 
      (alert_id,) 
    ) 
    alert_row = cur2.fetchone() 
    conn2.close() 
    alert_dt = alert_row['alert_date'] if alert_row else datetime.now() 
    if isinstance(alert_dt, str): 
      from datetime import datetime as dt 
      alert_dt = dt.fromisoformat(alert_dt) 
    
    year = alert_dt.year
    case_id = generate_case_id(year)
    window_start = alert_dt 
    window_end = alert_dt + timedelta(days=30) 
    
    # HIPAA 4-Factor Risk Scoring
    conn_audit = get_connection()
    cur_audit = conn_audit.cursor()
    # Fetch most significant event for this alert to score risk
    # We join with audit_events to get action_c, is_sensitive_access and is_vip_access
    cur_audit.execute("""
        SELECT e.action_c, e.is_sensitive_access, e.is_vip_access, a.rules_triggered
        FROM alerts a
        JOIN audit_events e ON a.emp_id = e.emp_id AND a.alert_date = e.action_datetime::date
        WHERE a.alert_id = %s
        ORDER BY e.is_sensitive_access DESC, e.is_vip_access DESC, e.action_c DESC
        LIMIT 1
    """, (alert_id,))
    audit_row = cur_audit.fetchone()
    conn_audit.close()
    
    ocr_score = 0.0
    requires_ocr = 0
    
    if audit_row:
        # Determine primary anomaly type from rules_triggered
        rules = audit_row['rules_triggered']
        anomaly_type = "OTHER"
        if "R_SENSITIVE" in rules: anomaly_type = "SENSITIVE_SNOOP"
        elif "R4" in rules: anomaly_type = "VIP_SNOOP"
        elif "R2" in rules: anomaly_type = "BULK_EXPORT"
        elif "R3" in rules: anomaly_type = "OFF_HOURS"
        
        ocr_score, requires_review = calculate_breach_risk(
            anomaly_type=anomaly_type,
            action_c=audit_row['action_c'],
            is_sensitive_access=audit_row['is_sensitive_access'],
            is_vip=audit_row['is_vip_access']
        )
        requires_ocr = 1 if requires_review else 0

    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO cases (case_id, emp_id, alert_ids, priority, department, patient_ids, window_start, window_end, ocr_risk_score, requires_ocr_review, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (case_id, emp_id, json.dumps([alert_id]), priority, department, json.dumps(patient_ids), window_start, window_end, ocr_score, requires_ocr, alert_dt))
    
    cursor.execute("""
        INSERT INTO case_audit_log (case_id, action, note)
        VALUES (%s, %s, %s)
    """, (case_id, 'created', f'Case auto-created from alert {alert_id}'))
    
    cursor.execute("UPDATE alerts SET case_id = %s WHERE alert_id = %s", (case_id, alert_id))
    
    conn.commit()
    conn.close()
    return case_id

def add_alert_to_case(case_id: str, alert_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT alert_ids FROM cases WHERE case_id = %s", (case_id,))
    case = cursor.fetchone()
    if not case:
        conn.close()
        return
        
    alert_ids = case['alert_ids']
    if alert_id not in alert_ids:
        alert_ids.append(alert_id)
        cursor.execute("""
            UPDATE cases SET alert_ids = %s, updated_at = NOW() 
            WHERE case_id = %s
        """, (json.dumps(alert_ids), case_id))
        
        cursor.execute("UPDATE alerts SET case_id = %s WHERE alert_id = %s", (case_id, alert_id))
        
        cursor.execute("""
            INSERT INTO case_audit_log (case_id, action, new_value, note)
            VALUES (%s, %s, %s, %s)
        """, (case_id, 'alert_added', str(alert_id), f'Alert {alert_id} added to case'))
        
    conn.commit()
    conn.close()

def process_new_alert(alert_id: int) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts WHERE alert_id = %s", (alert_id,))
    alert = cursor.fetchone()
    conn.close()
    
    if not alert:
        return None
        
    # Always create standalone case for Critical or R4
    if alert['adjusted_severity'] == 'Critical' or 'R4' in alert['rules_triggered']:
        return create_case(
            emp_id=alert['emp_id'],
            alert_id=alert_id,
            priority='Critical' if alert['adjusted_severity'] == 'Critical' else 'Medium',
            department=None, # Not in alerts table, would need join
            patient_ids=[] # Not in alerts table
        )
    else:
        existing_case_id = find_open_case(alert['emp_id'])
        if existing_case_id:
            add_alert_to_case(existing_case_id, alert_id)
            return existing_case_id
        else:
            return create_case(
                emp_id=alert['emp_id'],
                alert_id=alert_id,
                priority=alert['adjusted_severity'],
                department=None,
                patient_ids=[]
            )

def enforce_state_transition(case_id: str, current_status: str, new_status: str) -> bool:
    allowed = {
        'Open': ['Under Investigation'],
        'Under Investigation': ['Pending HR', 'Resolved'],
        'Pending HR': ['Under Investigation'],
        'Resolved': ['Closed']
    }
    
    if new_status not in allowed.get(current_status, []):
        return False

    if new_status == 'Closed': 
        conn = get_connection() 
        cursor = conn.cursor() 
        cursor.execute( 
            "SELECT resolved_at FROM cases WHERE case_id = %s", 
            (case_id,) 
        ) 
        result = cursor.fetchone() 
        conn.close() 
        if result and result['resolved_at']: 
            from datetime import datetime, timezone 
            days_since = ( 
                datetime.now(timezone.utc) -  
                result['resolved_at'].replace(tzinfo=timezone.utc) 
            ).days 
            if days_since < 90: 
                return False 
    
    return True

def update_case_status(case_id: str, new_status: str, user_id: int, note: str = None) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, resolved_at FROM cases WHERE case_id = %s", (case_id,))
    case = cursor.fetchone()
    if not case:
        conn.close()
        return False
        
    current_status = case['status']
    
    if not enforce_state_transition(case_id, current_status, new_status):
        conn.close()
        return False
        
    cursor.execute("""
        UPDATE cases SET status = %s, updated_at = NOW() 
        WHERE case_id = %s
    """, (new_status, case_id))
    
    if new_status == 'Resolved':
        cursor.execute("UPDATE cases SET resolved_at = NOW() WHERE case_id = %s", (case_id,))
        
    cursor.execute("""
        INSERT INTO case_audit_log (case_id, user_id, action, field_name, old_value, new_value, note)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (case_id, user_id, 'status_changed', 'status', current_status, new_status, note))
    
    conn.commit()
    conn.close()
    return True

def add_case_note(case_id: str, user_id: int, note_text: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO case_audit_log (case_id, user_id, action, note)
        VALUES (%s, %s, %s, %s)
    """, (case_id, user_id, 'note_added', note_text))
    cursor.execute("UPDATE cases SET updated_at = NOW() WHERE case_id = %s", (case_id,))
    conn.commit()
    conn.close()

def set_case_outcome(case_id: str, outcome: str, user_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE cases SET outcome = %s, updated_at = NOW() 
        WHERE case_id = %s
    """, (outcome, case_id))
    cursor.execute("""
        INSERT INTO case_audit_log (case_id, user_id, action, field_name, new_value)
        VALUES (%s, %s, %s, %s, %s)
    """, (case_id, user_id, 'outcome_set', 'outcome', outcome))
    conn.commit()
    conn.close()

def flag_overdue_cases(conn) -> int:
    cursor = conn.cursor()
    # SELECT all cases where status NOT IN ('Resolved', 'Closed') AND created_at < NOW() - INTERVAL '90 days'
    cursor.execute("""
        SELECT case_id FROM cases 
        WHERE status NOT IN ('Resolved', 'Closed', 'overdue') 
        AND created_at < NOW() - INTERVAL '90 days'
    """)
    overdue_rows = cursor.fetchall()
    
    count = 0
    for row in overdue_rows:
        case_id = row['case_id']
        # UPDATE them: status='overdue'
        # Since 'notes' column doesn't exist in 'cases' table, we add the note to case_audit_log
        cursor.execute("""
            UPDATE cases SET status = 'overdue', updated_at = NOW() 
            WHERE case_id = %s
        """, (case_id,))
        
        cursor.execute("""
            INSERT INTO case_audit_log (case_id, action, note) 
            VALUES (%s, 'status_changed', 'Auto-flagged: exceeded 90-day resolution window')
        """, (case_id,))
        count += 1
        
    if count > 0:
        conn.commit()
    return count

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
