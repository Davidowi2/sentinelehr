from db import get_connection
import case_logic

def run(org_id: int = 1):
    print(f"Checking for critical alerts to auto-case (Organization: {org_id})...")
    conn = get_connection()
    cursor = conn.cursor()

    # Find Critical alerts with no case yet
    cursor.execute("""
      SELECT alert_id FROM alerts 
      WHERE adjusted_severity = 'Critical' 
      AND case_id IS NULL 
      AND status = 'open' 
      AND organization_id = %s 
      ORDER BY alert_date ASC 
      LIMIT 200 
    """, (org_id,))
    alerts = cursor.fetchall()
    conn.close()

    created = 0
    import time
    for alert_row in alerts:
      print(f"Processing alert {alert_row['alert_id']}...")
      case_id = case_logic.process_new_alert(alert_row['alert_id'])
      if case_id:
        print(f"Created case {case_id}")
        created += 1
        time.sleep(0.1)
      else:
        print(f"Failed to create case for alert {alert_row['alert_id']}")

    print(f"Cases created from existing Critical alerts: {created}")

if __name__ == "__main__": 
    import sys 
    if len(sys.argv) > 1: 
        try: 
            org_id = int(sys.argv[1]) 
        except ValueError: 
            print("Error: org_id must be an integer. Usage: python auto_case_creator.py <org_id>") 
            sys.exit(1) 
    else: 
        print("Error: org_id required. Usage: python auto_case_creator.py <org_id>") 
        print("Example: python auto_case_creator.py 1") 
        sys.exit(1) 
    run(org_id)
