from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List

# ─── SETUP ──────────────────────────────────────────────────
app = FastAPI(title="SentinelEHR API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "./sentinel.db"

# ─── DATABASE HELPER ────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ─── MODELS ─────────────────────────────────────────────────
class StatusUpdate(BaseModel):
    status: str
    reviewer_notes: Optional[str] = None
    reviewed_by: Optional[str] = None

# ─── ENDPOINTS ──────────────────────────────────────────────

@app.get("/health")
def health_check():
    try:
        conn = get_db()
        conn.execute("SELECT 1")
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
def get_summary():
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
        total_employees = cursor.fetchone()[0]
        
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
            "top_anomaly_score": alert_stats["top_anomaly_score"] or 0.0,
            "total_employees_monitored": total_employees,
            "date_range": {
                "start": dates[0],
                "end": dates[1]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

@app.get("/alerts")
def get_alerts(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0
):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = "SELECT * FROM active_alerts WHERE 1=1"
        params = []
        
        if severity:
            query += " AND adjusted_severity = ?"
            params.append(severity)
        if status:
            query += " AND status = ?"
            params.append(status)
            
        # Get total count for pagination
        count_query = f"SELECT COUNT(*) FROM ({query})"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]
        
        # Get paginated results
        query += " LIMIT ? OFFSET ?"
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
def get_alert(alert_id: int):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
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
def update_alert_status(alert_id: int, update: StatusUpdate):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if alert exists
        cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail={"error": "Alert not found"})
            
        reviewed_at = None
        if update.status in ["investigating", "resolved"]:
            reviewed_at = datetime.now().isoformat()
            
        cursor.execute("""
            UPDATE alerts 
            SET status = ?, 
                reviewer_notes = COALESCE(?, reviewer_notes), 
                reviewed_by = COALESCE(?, reviewed_by),
                reviewed_at = COALESCE(?, reviewed_at)
            WHERE alert_id = ?
        """, (update.status, update.reviewer_notes, update.reviewed_by, reviewed_at, alert_id))
        
        conn.commit()
        
        # Return updated alert
        cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
        updated_alert = dict(cursor.fetchone())
        conn.close()
        
        return updated_alert
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

@app.get("/employees/{emp_id}/profile")
def get_employee_profile(emp_id: int):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Employee info
        cursor.execute("SELECT * FROM employees WHERE emp_id = ?", (emp_id,))
        emp = cursor.fetchone()
        if not emp:
            conn.close()
            raise HTTPException(status_code=404, detail={"error": "Employee not found"})
            
        # Baseline info
        cursor.execute("SELECT * FROM user_baselines WHERE emp_id = ?", (emp_id,))
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
            WHERE emp_id = ? AND adjusted_severity != 'Suppressed'
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
def get_digest(days: int = 30):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_digest LIMIT ?", (days,))
        digest = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return digest
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

# ─── SERVER STARTUP ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
