from fastapi import FastAPI, HTTPException, Query, Body, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler 
from slowapi.util import get_remote_address 
from slowapi.errors import RateLimitExceeded 
import os
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
from db import get_connection
import case_logic

from jose import JWTError, jwt 
from passlib.context import CryptContext 
from fastapi import Depends, HTTPException, Request 
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials 
from datetime import datetime, timedelta 

# ─── SETUP ──────────────────────────────────────────────────
load_dotenv()
app = FastAPI(title="SentinelEHR API")

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
 
security = HTTPBearer() 
 
def create_token(username: str) -> str: 
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS) 
    return jwt.encode( 
        {"sub": username, "exp": expire}, 
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
        if not username: 
            raise HTTPException(status_code=401, 
                detail="Invalid token") 
        return username 
    except JWTError: 
        raise HTTPException(status_code=401, 
            detail="Invalid or expired token") 

def get_current_user( 
  credentials: HTTPAuthorizationCredentials = Depends(security) 
): 
  username = verify_token(credentials) 
  try: 
    conn = get_connection() 
    cursor = conn.cursor() 
    cursor.execute( 
      "SELECT id, username, role, is_senior FROM users WHERE username = %s", 
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
    "id": 0, 
    "username": username, 
    "role": "admin", 
    "is_senior": True 
  } 
 
def require_role(*allowed_roles): 
  def checker(user = Depends(get_current_user)): 
    if user['role'] not in allowed_roles: 
      raise HTTPException( 
        status_code=403, 
        detail=f"Role {user['role']} cannot access this endpoint" 
      ) 
    return user 
  return checker 

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ 
      "https://sentinelehr.vercel.app", 
      "http://localhost:5173", 
      "http://localhost:3000" 
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

# ─── MODELS ─────────────────────────────────────────────────
class StatusUpdate(BaseModel):
    status: str
    reviewer_notes: Optional[str] = None
    reviewed_by: Optional[str] = None

# ─── ENDPOINTS ──────────────────────────────────────────────

@app.post("/login") 
@limiter.limit("5/minute") 
def login(request: Request, body: dict): 
    username = body.get("username", "") 
    password = body.get("password", "") 
    
    # First check database users 
    try: 
        conn = get_connection() 
        cursor = conn.cursor() 
        cursor.execute( 
            "SELECT id, password_hash, role, is_senior, active FROM users WHERE username = %s", 
            (username,) 
        ) 
        user = cursor.fetchone() 
        conn.close() 
        
        if user and user['active'] and case_logic.verify_password(password, user['password_hash']): 
            token = create_token(username) 
            return { 
                "access_token": token, 
                "token_type": "bearer", 
                "role": user['role'], 
                "is_senior": user['is_senior'], 
                "user_id": user['id'] 
            } 
    except: 
        pass 
    
    # Fallback to env var admin (for bootstrap) 
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD: 
        token = create_token(username) 
        return { 
            "access_token": token, 
            "token_type": "bearer", 
            "role": "admin", 
            "is_senior": True, 
            "user_id": 0 
        } 
    
    # Also check demo users (existing logic) 
    if username in DEMO_USERS and DEMO_USERS.get(username) == password: 
        token = create_token(username) 
        return { 
            "access_token": token, 
            "token_type": "bearer", 
            "role": "auditor", 
            "is_senior": False, 
            "user_id": -1 
        } 
    
    raise HTTPException(status_code=401, detail="Incorrect username or password") 

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

@app.get("/summary")
@limiter.limit("60/minute") 
def get_summary(request: Request, user: str = Depends(verify_token)):
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
    user: str = Depends(verify_token)
):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = "SELECT * FROM alerts WHERE 1=1"
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
def get_alert(alert_id: int, user: str = Depends(verify_token)):
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
def update_alert_status(alert_id: int, update: StatusUpdate, user: str = Depends(verify_token)):
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
def get_employee_profile(request: Request, emp_id: int, user: str = Depends(verify_token)):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Employee info
        cursor.execute("SELECT * FROM employees WHERE emp_id = %s", (emp_id,))
        emp = cursor.fetchone()
        if not emp:
            conn.close()
            raise HTTPException(status_code=404, detail={"error": "Employee not found"})
            
        # Baseline info
        cursor.execute("SELECT * FROM user_baselines WHERE emp_id = %s", (emp_id,))
        baseline = cursor.fetchone()
        
        # Alert summary
        cursor.execute("""
            SELECT 
                COUNT(*) as total_alerts,
                SUM(CASE WHEN adjusted_severity = 'Critical' THEN 1 ELSE 0 END) as critical_count,
                SUM(CASE WHEN adjusted_severity = 'High' THEN 1 ELSE 0 END) as high_count,
                SUM(CASE WHEN adjusted_severity = 'Medium' THEN 1 ELSE 0 END) as medium_count,
                MAX(anomaly_score) as max_anomaly_score
            FROM alerts
            WHERE emp_id = %s AND adjusted_severity != 'Suppressed'
        """, (emp_id,))
        alert_summary = cursor.fetchone()
        
        conn.close()
        
        return {
            "emp_id": emp["emp_id"],
            "role": emp["role"],
            "dept_id": emp["dept_id"],
            "is_float": emp["is_float"],
            "baseline": dict(baseline) if baseline else None,
            "alert_summary": dict(alert_summary)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

@app.get("/digest")
@limiter.limit("30/minute") 
def get_digest(request: Request, days: int = 30, user: str = Depends(verify_token)):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_digest LIMIT %s", (days,))
        digest = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return digest
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

# USER MANAGEMENT (admin only) 
 
@app.post("/users") 
@limiter.limit("10/minute") 
def create_user( 
  request: Request, 
  body: dict, 
  user = Depends(require_role('admin')) 
): 
  username = body.get("username") 
  email = body.get("email") 
  password = body.get("password") 
  role = body.get("role", "investigator") 
  is_senior = body.get("is_senior", False) 
  
  if not all([username, email, password]): 
    raise HTTPException(400, "Missing required fields") 
  if role not in ['admin','investigator','auditor']: 
    raise HTTPException(400, "Invalid role") 
  
  hashed = case_logic.hash_password(password) 
  try: 
    conn = get_connection() 
    cursor = conn.cursor() 
    cursor.execute( 
      """INSERT INTO users 
         (username, email, password_hash, role, is_senior) 
         VALUES (%s,%s,%s,%s,%s) RETURNING id""", 
      (username, email, hashed, role, is_senior) 
    ) 
    new_id = cursor.fetchone()['id'] 
    conn.commit() 
    conn.close() 
    return {"id": new_id, "username": username, 
            "role": role, "created": True} 
  except Exception as e: 
    raise HTTPException(400, "Username or email already exists") 
 
@app.get("/users") 
def list_users( 
  user = Depends(require_role('admin')) 
): 
  conn = get_connection() 
  cursor = conn.cursor() 
  cursor.execute( 
    "SELECT id, username, email, role, is_senior, active, created_at FROM users ORDER BY created_at" 
  ) 
  users = [dict(r) for r in cursor.fetchall()] 
  conn.close() 
  return {"users": users} 
 
# CASE MANAGEMENT 
 
@app.get("/cases") 
def list_cases( 
  status: str = None, 
  priority: str = None, 
  assigned_to: int = None, 
  limit: int = 50, 
  offset: int = 0, 
  user = Depends(get_current_user) 
): 
  conditions = [] 
  params = [] 
  if status: 
    conditions.append("status = %s") 
    params.append(status) 
  if priority: 
    conditions.append("priority = %s") 
    params.append(priority) 
  if assigned_to: 
    conditions.append("assigned_to = %s") 
    params.append(assigned_to) 
  
  where = "WHERE " + " AND ".join(conditions) if conditions else "" 
  
  conn = get_connection() 
  cursor = conn.cursor() 
  cursor.execute( 
    f"""SELECT *, 
        EXTRACT(DAY FROM NOW() - window_start) as days_open 
        FROM cases {where} 
        ORDER BY 
          CASE priority 
            WHEN 'Critical' THEN 1 
            WHEN 'Medium' THEN 2 
            WHEN 'Low' THEN 3 
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
  user = Depends(get_current_user) 
): 
  conn = get_connection() 
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
  user = Depends(require_role('admin','investigator')) 
): 
  new_status = body.get("status") 
  note = body.get("note", "") 
  
  if not new_status: 
    raise HTTPException(400, "Status required") 
  
  success = case_logic.update_case_status( 
    case_id, new_status, user['id'], note 
  ) 
  if not success: 
    raise HTTPException(400, f"Invalid status transition to {new_status}") 
  return {"case_id": case_id, "status": new_status, "updated": True} 
 
@app.post("/cases/{case_id}/notes") 
def add_note( 
  case_id: str, 
  body: dict, 
  user = Depends(require_role('admin','investigator')) 
): 
  note_text = body.get("note", "").strip() 
  if not note_text: 
    raise HTTPException(400, "Note cannot be empty") 
  case_logic.add_case_note(case_id, user['id'], note_text) 
  return {"case_id": case_id, "note_added": True} 
 
@app.patch("/cases/{case_id}/assign") 
def assign_case( 
  case_id: str, 
  body: dict, 
  user = Depends(require_role('admin','investigator')) 
): 
  assign_to_id = body.get("user_id") 
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
    (case_id, user['id'], str(old_assigned), str(assign_to_id)) 
  ) 
  conn.commit() 
  conn.close() 
  return {"case_id": case_id, "assigned_to": assign_to_id} 
 
@app.patch("/cases/{case_id}/outcome") 
def set_outcome( 
  case_id: str, 
  body: dict, 
  user = Depends(require_role('admin','investigator')) 
): 
  outcome = body.get("outcome") 
  valid = ['Legitimate Access','Policy Violation','Training Required','Termination Recommended','No Action'] 
  if outcome not in valid: 
    raise HTTPException(400, f"Invalid outcome") 
  case_logic.set_case_outcome(case_id, outcome, user['id']) 
  return {"case_id": case_id, "outcome": outcome} 
 
@app.get("/cases/{case_id}/export") 
def export_case( 
  case_id: str, 
  user = Depends(require_role('admin','investigator','auditor')) 
): 
  conn = get_connection() 
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
  
  cursor.execute( 
    """INSERT INTO case_audit_log 
       (case_id, user_id, action, note) 
       VALUES (%s,%s,'exported','OCR export generated')""", 
    (case_id, user['id']) 
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
  user = Depends(require_role('admin','investigator')) 
): 
  case_id = case_logic.process_new_alert(alert_id) 
  if not case_id: 
    raise HTTPException(400, "Could not create case") 
  return {"alert_id": alert_id, "case_id": case_id, "created": True} 

# ─── SERVER STARTUP ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
