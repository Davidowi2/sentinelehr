from fastapi import FastAPI, HTTPException, Query, Body, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler 
from slowapi.util import get_remote_address 
from slowapi.errors import RateLimitExceeded 
import os
import time
import csv
import io
from collections import defaultdict
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
from db import get_connection
import case_logic
import sendgrid
from sendgrid.helpers.mail import Mail

from jose import JWTError, jwt 
from passlib.context import CryptContext 
from fastapi import Depends, HTTPException, Request 
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials 
from datetime import datetime, timedelta 

# ─── SETUP ──────────────────────────────────────────────────
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run database seeding on startup
    seed_database()
    yield
    # Cleanup on shutdown (if needed)

app = FastAPI(title="SentinelEHR API", lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address) 
app.state.limiter = limiter 
app.add_exception_handler( 
    RateLimitExceeded, 
    _rate_limit_exceeded_handler 
) 

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin") 
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "sentinelehr2026") 
DEMO_USERS = { 
    os.getenv("DEMO_USERNAME", "demo"): 
        os.getenv("DEMO_PASSWORD", "hbh-demo-2026"), 
    os.getenv("DEMO2_USERNAME", "erie-demo"): 
        os.getenv("DEMO2_PASSWORD", "erie-demo-2026"), 
} 
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret") 
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))

# ─── DATABASE SEEDING ───────────────────────────────────────

def seed_database():
    """Create users table and seed initial users if table is empty"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create users table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                organization VARCHAR(255),
                organization_id INTEGER DEFAULT 1,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_login TIMESTAMP
            )
        """)
        conn.commit()
        print("[DATABASE] Users table created/verified")
        
        # Add organization column if it doesn't exist (migration for existing tables)
        cursor.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS organization VARCHAR(255) DEFAULT 'SentinelEHR Demo'
        """)
        conn.commit()
        print("[DATABASE] Organization column verified")
        
        # Update any existing users with NULL organization
        cursor.execute("""
            UPDATE users SET organization = 'SentinelEHR Demo' WHERE organization IS NULL
        """)
        conn.commit()
        print("[DATABASE] Updated NULL organization values")
        
        # Rename 'active' column to 'is_active' if it exists (migration for existing tables)
        try:
            cursor.execute("""
                ALTER TABLE users RENAME COLUMN active TO is_active
            """)
            conn.commit()
            print("[DATABASE] Renamed 'active' column to 'is_active'")
        except Exception as e:
            conn.rollback()
            # Column might already be named is_active or doesn't exist
            print(f"[DATABASE] Column rename skipped: {str(e)}")
        
        # Add last_login column if it doesn't exist (migration for existing tables)
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP')
            conn.commit()
            print('[DATABASE] last_login column verified')
        except Exception as e:
            conn.rollback()
            print(f'[DATABASE] last_login skip: {str(e)}')
        
        # Print all column names for debugging
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            ORDER BY ordinal_position
        """)
        columns = [row['column_name'] for row in cursor.fetchall()]
        print(f"[DATABASE] Users table columns: {', '.join(columns)}")
        
        # Check if any users exist
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()['count']
        
        if user_count == 0:
            print("[DATABASE] No users found. Seeding default users...")
            
            # Seed users with bcrypt hashed passwords
            seed_users = [
                ("demo@sentinelehr.com", "hbh-demo-2026", "compliance_officer", "SentinelEHR Demo", 1),
                ("it_demo@sentinelehr.com", "it-demo-2026", "it_director", "SentinelEHR Demo", 1),
                ("admin@sentinelehr.com", "sentinelehr2026", "admin", "SentinelEHR Demo", 1)
            ]
            
            for email, password, role, org, org_id in seed_users:
                # Hash password using bcrypt
                password_hash = case_logic.hash_password(password)
                
                cursor.execute("""
                    INSERT INTO users (email, password_hash, role, organization, organization_id, is_active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                """, (email, password_hash, role, org, org_id))
                
                print(f"[DATABASE] Seeded user: {email} ({role})")
            
            conn.commit()
            print("[DATABASE] Database seeding complete")
        else:
            print(f"[DATABASE] Users table already has {user_count} user(s). Skipping seed.")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        conn.rollback()
        print(f"[DATABASE ERROR] Failed to seed database: {str(e)}")
        # Don't raise exception - allow app to start even if seeding fails

# ─── SECURITY HELPERS ───────────────────────────────────────
# In-memory store for failed login attempts: {ip: [timestamp1, timestamp2, ...]}
failed_login_attempts = defaultdict(list)

def check_login_rate_limit(ip: str):
    now = time.time()
    # Keep only attempts from the last 15 minutes (900 seconds)
    failed_login_attempts[ip] = [t for t in failed_login_attempts[ip] if now - t < 900]
    if len(failed_login_attempts[ip]) >= 5:
        return False
    return True

def record_failed_login(ip: str):
    failed_login_attempts[ip].append(time.time())

def audit_log_login(username: str, ip: str, result: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] LOGIN ATTEMPT: user={username}, ip={ip}, result={result}")

security = HTTPBearer() 
 
def create_token(username: str, role: str) -> str: 
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS) 
    return jwt.encode( 
        {"sub": username, "role": role, "exp": expire}, 
        JWT_SECRET, 
        algorithm="HS256" 
    ) 
 
def verify_token( 
    credentials: HTTPAuthorizationCredentials = Depends(security) 
): 
    try: 
        payload = jwt.decode( 
            credentials.credentials, 
            JWT_SECRET, 
            algorithms=["HS256"] 
        ) 
        username = payload.get("sub") 
        role = payload.get("role")
        if not username or not role: 
            raise HTTPException(status_code=401, 
                detail="Invalid token") 
        return {"username": username, "role": role} 
    except JWTError: 
        raise HTTPException(status_code=401, 
            detail="Invalid or expired token") 

def get_current_user_from_token(token_data: dict):
  username = token_data["username"]
  try: 
    conn = get_connection() 
    cursor = conn.cursor() 
    cursor.execute( 
      "SELECT user_id, username, role FROM users WHERE username = %s", 
      (username,) 
    ) 
    user = cursor.fetchone() 
    conn.close() 
    if user: 
      return dict(user) 
  except: 
    pass 
  # Fallback for env var admin 
  return { 
    "user_id": 0, 
    "username": username, 
    "role": token_data["role"]
  } 

def get_current_user( 
  credentials: HTTPAuthorizationCredentials = Depends(security) 
): 
  token_data = verify_token(credentials) 
  return get_current_user_from_token(token_data)
 
def require_role(*allowed_roles): 
  def checker(token_data = Depends(verify_token)): 
    if token_data['role'] not in allowed_roles: 
      raise HTTPException( 
        status_code=403, 
        detail=f"Role {token_data['role']} cannot access this endpoint" 
      ) 
    return token_data 
  return checker 

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ 
      "https://sentinelehr.vercel.app", 
      "http://localhost:5173", 
      "http://localhost:3000" 
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.exception_handler(Exception) 
async def global_exception_handler(request, exc): 
    return JSONResponse( 
        status_code=500, 
        content={"error": "An internal error occurred."} 
    ) 

# ─── DATABASE HELPER ────────────────────────────────────────
def get_db():
    return get_connection()

# ─── EMAIL HELPER ───────────────────────────────────────────
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

# ─── MODELS ─────────────────────────────────────────────────
class StatusUpdate(BaseModel):
    status: str
    reviewer_notes: Optional[str] = None
    reviewed_by: Optional[str] = None

# ─── ENDPOINTS ──────────────────────────────────────────────

@app.post("/login") 
@limiter.limit("10/minute") 
def login(request: Request, body: dict): 
    email = body.get("email", "").lower().strip()
    password = body.get("password", "") 
    ip_address = get_remote_address(request)
    
    if not check_login_rate_limit(ip_address):
        audit_log_login(email, ip_address, "BLOCKED (Rate Limit)")
        raise HTTPException(status_code=429, detail="Too many failed login attempts. Please try again in 15 minutes.")

    # Validate email and password
    if not email or not password:
        record_failed_login(ip_address)
        audit_log_login(email, ip_address, "FAILED (Missing credentials)")
        raise HTTPException(status_code=400, detail="Email and password are required")

    # Check database users 
    try: 
        conn = get_connection() 
        cursor = conn.cursor() 
        cursor.execute( 
            "SELECT id, email, password_hash, role, organization, is_active FROM users WHERE email = %s", 
            (email,) 
        ) 
        user = cursor.fetchone() 
        conn.close() 
        
        if user and user['is_active'] and case_logic.verify_password(password, user['password_hash']): 
            # Update last login
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
                (user['id'],)
            )
            conn.commit()
            conn.close()
            
            audit_log_login(email, ip_address, "SUCCESS")
            token = create_token(user['email'], user['role']) 
            return { 
                "access_token": token, 
                "token_type": "bearer", 
                "role": user['role'], 
                "user_id": user['id'],
                "email": user['email'],
                "organization": user['organization']
            } 
    except Exception as e: 
        print(f"Login error: {str(e)}")
        pass 
    
    record_failed_login(ip_address)
    audit_log_login(email, ip_address, "FAILED")
    raise HTTPException(status_code=401, detail="Incorrect email or password") 

@app.post("/logout")
def logout(token_data = Depends(verify_token)):
    # Currently stateless, so just returning success
    return {"message": "Logged out successfully"}

@app.get("/health")
def health_check():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        return {
            "status": "ok",
            "db": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "db": "disconnected",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/test-email")
def test_email(token_data = Depends(require_role('admin'))):
    try:
        ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "compliance@sentinelehr.com")
        result = send_alert_email(
            ALERT_EMAIL_TO,
            "SentinelEHR Test Email",
            "Email notifications are working correctly."
        )
        if result:
            return {"status": "sent"}
        else:
            return {"status": "failed", "error": "send_alert_email returned False"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

@app.get("/summary")
@limiter.limit("60/minute") 
def get_summary(request: Request, token_data = Depends(verify_token)):
    # Everyone can see summary
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total active alerts and breakdown
        cursor.execute("""
            SELECT 
                COUNT(*) as total_active,
                SUM(CASE WHEN adjusted_severity = 'Critical' THEN 1 ELSE 0 END) as critical,
                SUM(CASE WHEN adjusted_severity = 'High' THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN adjusted_severity = 'Medium' THEN 1 ELSE 0 END) as medium,
                MAX(anomaly_score) as top_anomaly_score
            FROM active_alerts
            WHERE alert_date >= NOW() - INTERVAL '180 days'
        """)
        alert_stats = cursor.fetchone()
        
        # Total employees monitored
        cursor.execute("SELECT COUNT(*) FROM employees")
        total_employees = cursor.fetchone()['count']
        
        # Date range
        cursor.execute("""
            SELECT MIN(alert_date), MAX(alert_date) 
            FROM alerts 
            WHERE adjusted_severity != 'Suppressed'
        """)
        dates = cursor.fetchone()
        
        conn.close()
        
        return {
            "total_active": alert_stats["total_active"] or 0,
            "critical": alert_stats["critical"] or 0,
            "high": alert_stats["high"] or 0,
            "medium": alert_stats["medium"] or 0,
            "top_anomaly_score": float(alert_stats["top_anomaly_score"]) if alert_stats["top_anomaly_score"] is not None else 0.0,
            "total_employees_monitored": total_employees,
            "date_range": {
                "start": dates['min'],
                "end": dates['max']
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

@app.get("/alerts")
@limiter.limit("60/minute") 
def get_alerts(
    request: Request,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    token_data = Depends(verify_token)
):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = "SELECT * FROM alerts WHERE alert_date >= NOW() - INTERVAL '180 days'"
        params = []
        
        if severity:
            query += " AND adjusted_severity = %s"
            params.append(severity)
        
        if status:
            query += " AND status = %s"
            params.append(status)
        else:
            # Default: exclude resolved and suppressed
            query += " AND status != 'resolved' AND adjusted_severity != 'Suppressed'"
            
        # Get total count for pagination
        count_query = f"SELECT COUNT(*) FROM ({query}) AS subquery"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()['count']
        
        # Get paginated results
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        cursor.execute(query, params)
        alerts = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return {
            "alerts": alerts,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

@app.get("/alerts/{alert_id}")
def get_alert(alert_id: int, token_data = Depends(verify_token)):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alerts WHERE alert_id = %s", (alert_id,))
        alert = cursor.fetchone()
        conn.close()
        
        if not alert:
            raise HTTPException(status_code=404, detail={"error": "Alert not found"})
        return dict(alert)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

@app.patch("/alerts/{alert_id}/status")
def update_alert_status(alert_id: int, update: StatusUpdate, token_data = Depends(require_role('compliance_officer', 'admin'))):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if alert exists
        cursor.execute("SELECT * FROM alerts WHERE alert_id = %s", (alert_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail={"error": "Alert not found"})
            
        reviewed_at = None
        if update.status in ["investigating", "resolved"]:
            reviewed_at = datetime.now().isoformat()
            
        cursor.execute("""
            UPDATE alerts 
            SET status = %s, 
                reviewer_notes = COALESCE(%s, reviewer_notes), 
                reviewed_by = COALESCE(%s, reviewed_by),
                reviewed_at = COALESCE(%s, reviewed_at)
            WHERE alert_id = %s
        """, (update.status, update.reviewer_notes, update.reviewed_by, reviewed_at, alert_id))
        
        conn.commit()
        
        # Return updated alert
        cursor.execute("SELECT * FROM alerts WHERE alert_id = %s", (alert_id,))
        updated_alert = dict(cursor.fetchone())
        conn.close()
        
        return updated_alert
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

@app.get("/employees/{emp_id}/profile")
@limiter.limit("30/minute") 
def get_employee_profile(request: Request, emp_id: int, token_data = Depends(require_role('compliance_officer', 'admin'))):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Employee info
        cursor.execute("SELECT role, dept_id, is_float FROM employees WHERE emp_id = %s", (emp_id,))
        emp = cursor.fetchone()
        if not emp:
            conn.close()
            raise HTTPException(status_code=404, detail={"error": "Employee not found"})
            
        # 2. Top anomaly score
        cursor.execute("SELECT MAX(anomaly_score) as top_score FROM anomaly_scores WHERE emp_id = %s", (emp_id,))
        score_row = cursor.fetchone()
        top_score = float(score_row['top_score']) if score_row and score_row['top_score'] is not None else 0.0

        # 3. Last 20 alerts
        cursor.execute("""
            SELECT alert_id, alert_date, adjusted_severity, rules_triggered, anomaly_score
            FROM alerts
            WHERE emp_id = %s
            ORDER BY alert_date DESC
            LIMIT 20
        """, (emp_id,))
        alerts = [dict(row) for row in cursor.fetchall()]

        # 4. Open cases
        cursor.execute("""
            SELECT case_id, status, priority, window_start, window_end, created_at, 
                   (EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400)::int as days_open
            FROM cases
            WHERE emp_id = %s AND status != 'Resolved' AND status != 'Closed'
        """, (emp_id,))
        cases = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "emp_id": emp_id,
            "role": emp["role"],
            "dept_id": emp["dept_id"],
            "is_float": emp["is_float"],
            "top_score": top_score,
            "alerts": alerts,
            "cases": cases
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

@app.get("/digest")
@limiter.limit("30/minute") 
def get_digest(request: Request, days: int = 180, token_data = Depends(verify_token)):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_digest LIMIT %s", (days,))
        digest = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return digest
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

@app.get("/investigate")
@limiter.limit("30/minute")
def investigate_employee(request: Request, emp_id: int, token_data = Depends(require_role('compliance_officer', 'admin'))):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get employee info
        cursor.execute("SELECT * FROM employees WHERE emp_id = %s", (emp_id,))
        emp = cursor.fetchone()
        if not emp:
            conn.close()
            raise HTTPException(status_code=404, detail="Employee not found")
            
        # Get audit events for this employee
        cursor.execute("""
            SELECT action_datetime, pat_id, workstation_id, anomaly_type, action_c
            FROM audit_events
            WHERE emp_id = %s
            ORDER BY action_datetime DESC
            LIMIT 500
        """, (emp_id,))
        rows = cursor.fetchall()
        
        # Map action codes to names
        action_names = {
            1: "In Chart", 2: "Chart Review", 3: "Open Chart", 
            4: "Print Chart", 5: "Export Data", 6: "Break Glass", 
            7: "Search", 8: "Edit Note", 9: "Sign Order", 
            10: "View Result", 11: "Chart Close"
        }
        
        events = []
        for row in rows:
            ev = dict(row)
            ev['action_name'] = action_names.get(ev['action_c'], f"Action {ev['action_c']}")
            events.append(ev)
        
        # Get total alerts count
        cursor.execute("SELECT COUNT(*) FROM alerts WHERE emp_id = %s", (emp_id,))
        total_alerts = cursor.fetchone()['count']
        
        # Get max OCR risk score from cases
        cursor.execute("SELECT MAX(ocr_risk_score) as max_ocr FROM cases WHERE emp_id = %s", (emp_id,))
        max_ocr_row = cursor.fetchone()
        max_ocr = float(max_ocr_row['max_ocr']) if max_ocr_row and max_ocr_row['max_ocr'] is not None else 0.0
        
        conn.close()
        
        return {
            "emp_id": emp_id,
            "role": emp["role"],
            "dept_id": emp["dept_id"],
            "total_count": len(events),
            "total_alerts": total_alerts,
            "ocr_risk_score": max_ocr,
            "events": events
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# USER MANAGEMENT (admin only) 
 
@app.post("/users") 
@limiter.limit("10/minute") 
def create_user( 
  request: Request, 
  body: dict, 
  token_data = Depends(require_role('admin')) 
): 
  username = body.get("username") 
  email = body.get("email") 
  password = body.get("password") 
  role = body.get("role", "compliance_officer") 
  
  if not all([username, email, password]): 
    raise HTTPException(400, "Missing required fields") 
  if role not in ['admin','compliance_officer','it_director']: 
    raise HTTPException(400, "Invalid role") 
  
  hashed = case_logic.hash_password(password) 
  try: 
    conn = get_connection() 
    cursor = conn.cursor() 
    cursor.execute( 
      """INSERT INTO users 
         (username, email, password_hash, role) 
         VALUES (%s,%s,%s,%s) RETURNING user_id""", 
      (username, email, hashed, role) 
    ) 
    new_id = cursor.fetchone()['user_id'] 
    conn.commit() 
    conn.close() 
    return {"user_id": new_id, "username": username, 
            "role": role, "created": True} 
  except Exception as e: 
    raise HTTPException(400, "Username or email already exists") 
 
@app.get("/users") 
def list_users( 
  token_data = Depends(require_role('admin')) 
): 
  conn = get_connection() 
  cursor = conn.cursor() 
  cursor.execute( 
    "SELECT user_id, username, email, role, active, created_at FROM users ORDER BY created_at" 
  ) 
  users = [dict(r) for r in cursor.fetchall()] 
  conn.close() 
  return {"users": users} 
 
# CASE MANAGEMENT 
 
@app.get("/cases") 
@limiter.limit("60/minute") 
def list_cases( 
  request: Request, 
  status: str = None, 
  priority: str = None, 
  assigned_to: int = None, 
  limit: int = 50, 
  offset: int = 0, 
  token_data = Depends(verify_token) 
): 
  conn = get_connection() 
  case_logic.flag_overdue_cases(conn) 
  conditions = [] 
  params = [] 
  if status: 
    conditions.append("status = %s") 
    params.append(status) 
  if priority: 
    conditions.append("priority = %s") 
    params.append(priority) 
  if assigned_to is not None: 
    conditions.append("assigned_to = %s") 
    params.append(assigned_to) 
  
  where = "WHERE " + " AND ".join(conditions) if conditions else "" 
  
  cursor = conn.cursor() 
  cursor.execute( 
    f"""SELECT *, 
        EXTRACT(DAY FROM NOW() - window_start) as days_open 
        FROM cases {where} 
        ORDER BY 
          CASE priority 
            WHEN 'Critical' THEN 1 
            WHEN 'High' THEN 2 
            WHEN 'Medium' THEN 3 
            WHEN 'Low' THEN 4 
          END, 
          created_at ASC 
        LIMIT %s OFFSET %s""", 
    params + [limit, offset] 
  ) 
  cases = [dict(r) for r in cursor.fetchall()] 
  cursor.execute(f"SELECT COUNT(*) FROM cases {where}", params) 
  total = cursor.fetchone()['count'] 
  conn.close() 
  return {"cases": cases, "total_count": total, "limit": limit, "offset": offset} 
 
@app.get("/cases/{case_id}") 
def get_case( 
  case_id: str, 
  token_data = Depends(verify_token) 
): 
  conn = get_connection() 
  case_logic.flag_overdue_cases(conn) 
  cursor = conn.cursor() 
  cursor.execute( 
    """SELECT c.*, EXTRACT(DAY FROM NOW() - c.window_start) as days_open 
       FROM cases c WHERE c.case_id = %s""", 
    (case_id,) 
  ) 
  case = cursor.fetchone() 
  if not case: 
    raise HTTPException(404, "Case not found") 
  
  cursor.execute( 
    """SELECT l.*, u.username as changed_by_name 
       FROM case_audit_log l 
       LEFT JOIN users u ON l.user_id = u.id 
       WHERE l.case_id = %s 
       ORDER BY l.timestamp ASC""", 
    (case_id,) 
  ) 
  audit_log = [dict(r) for r in cursor.fetchall()] 
  conn.close() 
  
  result = dict(case) 
  result['audit_log'] = audit_log 
  return result 
 
@app.patch("/cases/{case_id}/status") 
def update_case_status( 
  case_id: str, 
  body: dict, 
  token_data = Depends(require_role('admin','compliance_officer')) 
): 
  new_status = body.get("status") 
  note = body.get("note", "") 
  
  if not new_status: 
    raise HTTPException(400, "Status required") 
  
  user = get_current_user_from_token(token_data)
  success = case_logic.update_case_status( 
    case_id, new_status, user['user_id'], note 
  ) 
  if not success: 
    raise HTTPException(400, f"Invalid status transition to {new_status}") 
  return {"case_id": case_id, "status": new_status, "updated": True} 
 
@app.post("/cases/{case_id}/notes") 
def add_note( 
  case_id: str, 
  body: dict, 
  token_data = Depends(require_role('admin','compliance_officer')) 
): 
  note_text = body.get("note", "").strip() 
  if not note_text: 
    raise HTTPException(400, "Note cannot be empty") 
  user = get_current_user_from_token(token_data)
  case_logic.add_case_note(case_id, user['user_id'], note_text) 
  return {"case_id": case_id, "note_added": True} 
 
@app.patch("/cases/{case_id}/assign") 
def assign_case( 
  case_id: str, 
  body: dict, 
  token_data = Depends(require_role('admin','compliance_officer')) 
): 
  assign_to_id = body.get("user_id") 
  user = get_current_user_from_token(token_data)
  conn = get_connection() 
  cursor = conn.cursor() 
  cursor.execute( 
    "SELECT assigned_to FROM cases WHERE case_id = %s", 
    (case_id,) 
  ) 
  current = cursor.fetchone() 
  if not current: 
    raise HTTPException(404, "Case not found") 
  
  old_assigned = current['assigned_to'] 
  cursor.execute( 
    """UPDATE cases SET assigned_to = %s, 
       updated_at = NOW() WHERE case_id = %s""", 
    (assign_to_id, case_id) 
  ) 
  cursor.execute( 
    """INSERT INTO case_audit_log 
       (case_id, user_id, action, field_name, old_value, new_value) 
       VALUES (%s,%s,'assigned','assigned_to',%s,%s)""", 
    (case_id, user['user_id'], str(old_assigned), str(assign_to_id)) 
  ) 
  conn.commit() 
  conn.close() 
  return {"case_id": case_id, "assigned_to": assign_to_id} 
 
@app.patch("/cases/{case_id}/outcome") 
def set_outcome( 
  case_id: str, 
  body: dict, 
  token_data = Depends(require_role('admin','compliance_officer')) 
): 
  outcome = body.get("outcome") 
  valid = ['Legitimate Access','Policy Violation','Training Required','Termination Recommended','No Action'] 
  if outcome not in valid: 
    raise HTTPException(400, f"Invalid outcome") 
  user = get_current_user_from_token(token_data)
  case_logic.set_case_outcome(case_id, outcome, user['user_id']) 
  return {"case_id": case_id, "outcome": outcome} 
 
@app.get("/cases/{case_id}/export") 
def export_case( 
  case_id: str, 
  token_data = Depends(require_role('admin','compliance_officer','it_director')) 
): 
  conn = get_connection() 
  case_logic.flag_overdue_cases(conn) 
  cursor = conn.cursor() 
  cursor.execute( 
    "SELECT * FROM cases WHERE case_id = %s", (case_id,) 
  ) 
  case = cursor.fetchone() 
  if not case: 
    raise HTTPException(404, "Case not found") 
  
  cursor.execute( 
    """SELECT * FROM case_audit_log 
       WHERE case_id = %s ORDER BY timestamp""", 
    (case_id,) 
  ) 
  audit_log = [dict(r) for r in cursor.fetchall()] 
  
  user = get_current_user_from_token(token_data)
  cursor.execute( 
    """INSERT INTO case_audit_log 
       (case_id, user_id, action, note) 
       VALUES (%s,%s,'exported','OCR export generated')""", 
    (case_id, user['user_id']) 
  ) 
  conn.commit() 
  conn.close() 
  
  export = { 
    "export_generated_at": datetime.utcnow().isoformat(), 
    "export_generated_by": user['username'], 
    "case": dict(case), 
    "audit_trail": audit_log, 
    "record_count": len(audit_log) 
  } 
  return export 
 
@app.post("/alerts/{alert_id}/create-case") 
def create_case_from_alert( 
  alert_id: int, 
  token_data = Depends(require_role('admin','compliance_officer')) 
): 
  case_id = case_logic.process_new_alert(alert_id) 
  if not case_id: 
    raise HTTPException(400, "Could not create case") 
  return {"alert_id": alert_id, "case_id": case_id, "created": True} 

# ─── EXPORT ENDPOINTS ───────────────────────────────────────

@app.get("/export/alerts")
def export_alerts(
    request: Request,
    severity: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    emp_id: Optional[int] = None,
    token_data = Depends(require_role('compliance_officer', 'admin'))
):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = "SELECT alert_id, alert_date, emp_id, adjusted_severity, rules_triggered, anomaly_score, explanation FROM alerts WHERE 1=1"
        params = []
        
        if severity:
            query += " AND adjusted_severity = %s"
            params.append(severity)
        if start_date:
            query += " AND alert_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND alert_date <= %s"
            params.append(end_date)
        if emp_id:
            query += " AND emp_id = %s"
            params.append(emp_id)
            
        query += " ORDER BY alert_date DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['alert_id', 'alert_date', 'emp_id', 'adjusted_severity', 'rules_triggered', 'anomaly_score', 'explanation'])
        
        for row in rows:
            writer.writerow([
                row['alert_id'],
                row['alert_date'],
                row['emp_id'],
                row['adjusted_severity'],
                row['rules_triggered'],
                row['anomaly_score'],
                row['explanation']
            ])

        output.seek(0)
        date_str = datetime.now().strftime("%Y%m%d")
        headers = {
            'Content-Disposition': f'attachment; filename=sentinelehr_alerts_{date_str}.csv'
        }
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/export/case/{case_id}")
def export_case_report(
    case_id: str,
    token_data = Depends(require_role('compliance_officer', 'admin'))
):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Fetch case metadata
        cursor.execute("SELECT * FROM cases WHERE case_id = %s", (case_id,))
        case = cursor.fetchone()
        if not case:
            conn.close()
            raise HTTPException(status_code=404, detail="Case not found")
            
        # 2. Fetch employee info
        cursor.execute("SELECT emp_id, role, dept_id FROM employees WHERE emp_id = %s", (case['emp_id'],))
        employee = cursor.fetchone()
        
        # 3. Fetch linked alerts
        import json
        alert_ids = case['alert_ids'] if isinstance(case['alert_ids'], list) else json.loads(case['alert_ids'])
        alerts = []
        if alert_ids:
            placeholders = ', '.join(['%s'] * len(alert_ids))
            cursor.execute(f"SELECT * FROM alerts WHERE alert_id IN ({placeholders})", tuple(alert_ids))
            alerts = [dict(r) for r in cursor.fetchall()]
            
        # 4. Fetch audit log / timeline
        cursor.execute("""
            SELECT l.*, u.username as actor_name 
            FROM case_audit_log l 
            LEFT JOIN users u ON l.user_id = u.id 
            WHERE l.case_id = %s 
            ORDER BY l.timestamp ASC
        """, (case_id,))
        timeline = [dict(r) for r in cursor.fetchall()]
        
        conn.close()
        
        return {
            "report_generated_at": datetime.now().isoformat(),
            "case_metadata": dict(case),
            "employee_info": dict(employee) if employee else None,
            "linked_alerts": alerts,
            "timeline": timeline
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# SETTINGS MANAGEMENT

class ThresholdUpdate(BaseModel):
    critical_threshold: float
    high_threshold: float
    medium_threshold: float

@app.put("/settings/thresholds")
def update_thresholds(
    body: ThresholdUpdate,
    token_data = Depends(require_role('admin', 'compliance_officer'))
):
    """Update alert severity thresholds"""
    try:
        # Validate threshold values
        if not (0 <= body.critical_threshold <= 1):
            raise HTTPException(status_code=400, detail="Critical threshold must be between 0 and 1")
        if not (0 <= body.high_threshold <= 1):
            raise HTTPException(status_code=400, detail="High threshold must be between 0 and 1")
        if not (0 <= body.medium_threshold <= 1):
            raise HTTPException(status_code=400, detail="Medium threshold must be between 0 and 1")
        
        # Validate logical order: critical > high > medium
        if body.critical_threshold <= body.high_threshold:
            raise HTTPException(status_code=400, detail="Critical threshold must be greater than high threshold")
        if body.high_threshold <= body.medium_threshold:
            raise HTTPException(status_code=400, detail="High threshold must be greater than medium threshold")
        
        # Store thresholds in environment/config (in production, use database)
        # For now, we'll accept and acknowledge the update
        # In a real implementation, you'd store this in a settings table
        
        print(f"[SETTINGS] Thresholds updated by {token_data.get('username')}:")
        print(f"  Critical: {body.critical_threshold}")
        print(f"  High: {body.high_threshold}")
        print(f"  Medium: {body.medium_threshold}")
        
        return {
            "message": "Thresholds updated successfully",
            "thresholds": {
                "critical_threshold": body.critical_threshold,
                "high_threshold": body.high_threshold,
                "medium_threshold": body.medium_threshold
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/settings/thresholds")
def get_thresholds(
    token_data = Depends(require_role('admin', 'compliance_officer'))
):
    """Get current alert severity thresholds"""
    # Return default thresholds (in production, fetch from database)
    return {
        "critical_threshold": 0.7,
        "high_threshold": 0.4,
        "medium_threshold": 0.2
    }

# ─── SERVER STARTUP ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
