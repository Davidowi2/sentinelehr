import os 
import sendgrid
from sendgrid.helpers.mail import Mail

ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "compliance@sentinelehr.com") 

def send_alert_email(to_email, subject, body):
    sg = sendgrid.SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))
    message = Mail(
        from_email=os.getenv('SENDGRID_FROM_EMAIL', 'david.sentinelehr@gmail.com'),
        to_emails=to_email,
        subject=subject,
        plain_text_content=body
    )
    try:
        response = sg.send(message)
        print(f"Email sent: {response.status_code}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def send_critical_alert_email(alert_id: int, anomaly_type: str, emp_id: int, score: float): 
    if not os.getenv('SENDGRID_API_KEY'):
        print(f"[Email Service] Skipping email for Alert {alert_id} - No SendGrid API key configured.") 
        return False
 
    subject = f"🚨 CRITICAL ALERT [{anomaly_type}] - SentinelEHR" 
    body = f""" 
    SentinelEHR has detected a CRITICAL security violation. 
     
    Alert ID: {alert_id} 
    Anomaly Type: {anomaly_type} 
    Employee ID: {emp_id} 
    Risk Score: {score:.2f} 
     
    Please log in to the SentinelEHR dashboard immediately to investigate this case. 
     
    - SentinelEHR Automated Monitor 
    """ 
    
    result = send_alert_email(ALERT_EMAIL_TO, subject, body)
    if result:
        print(f"[Email Service] Critical alert email sent to {ALERT_EMAIL_TO}")
    return result
 
