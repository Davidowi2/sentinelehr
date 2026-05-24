import os 
import smtplib 
from email.mime.text import MIMEText 
from email.mime.multipart import MIMEMultipart 
 
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com") 
SMTP_PORT = int(os.getenv("SMTP_PORT", "587")) 
SMTP_USER = os.getenv("SMTP_USER", "") 
SMTP_PASS = os.getenv("SMTP_PASS", "") 
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "compliance@sentinelehr.com") 
 
def send_critical_alert_email(alert_id: int, anomaly_type: str, emp_id: int, score: float): 
    if not SMTP_USER or not SMTP_PASS: 
        print(f"[Email Service] Skipping email for Alert {alert_id} - No SMTP credentials configured.") 
        return 
 
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
     
    msg = MIMEMultipart() 
    msg['From'] = SMTP_USER 
    msg['To'] = ALERT_EMAIL_TO 
    msg['Subject'] = subject 
    msg.attach(MIMEText(body, 'plain')) 
 
    try: 
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT) 
        server.starttls() 
        server.login(SMTP_USER, SMTP_PASS) 
        server.send_message(msg) 
        server.quit() 
        print(f"[Email Service] Critical alert email sent to {ALERT_EMAIL_TO}") 
    except Exception as e: 
        print(f"[Email Service] Failed to send email: {e}") 
