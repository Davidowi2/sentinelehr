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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    if not ( 
        (username == ADMIN_USERNAME and 
         password == ADMIN_PASSWORD) or 
        (username in DEMO_USERS and 
         DEMO_USERS.get(username) == password) 
    ): 
        raise HTTPException( 
            status_code=401, 
            detail="Incorrect username or password" 
        ) 
    return { 
        "access_token": create_token(username), 
        "token_type": "bearer" 
    } 

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

# ─── SERVER STARTUP ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
