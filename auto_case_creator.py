from db import get_connection
import case_logic

def run():
    conn = get_connection()
    cursor = conn.cursor()

    # Find Critical alerts with no case yet
    cursor.execute("""
      SELECT alert_id FROM alerts 
      WHERE adjusted_severity = 'Critical' 
      AND case_id IS NULL 
      AND status = 'open' 
      ORDER BY alert_date ASC 
      LIMIT 200 
    """)
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
    run()
