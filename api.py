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
import secrets
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
        
        # Create settings table and seed defaults
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(100) PRIMARY KEY,
                value VARCHAR(255) NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        cursor.execute('''
            INSERT INTO settings (key, value) VALUES 
            ('critical_threshold', '0.7'), 
            ('high_threshold', '0.4'), 
            ('medium_threshold', '0.2') 
            ON CONFLICT (key) DO NOTHING 
        ''')
        conn.commit()
        print('[DATABASE] Settings table verified')
        
        try: 
            cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS organizations ( 
                    id SERIAL PRIMARY KEY, 
                    name VARCHAR(255) NOT NULL, 
                    type VARCHAR(100), 
                    epic_host VARCHAR(255), 
                    epic_port INTEGER, 
                    epic_db_user VARCHAR(255), 
                    epic_db_password_encrypted VARCHAR(500), 
                    subscription_tier VARCHAR(50) DEFAULT 'design_partner', 
                    is_active BOOLEAN DEFAULT TRUE, 
                    created_at TIMESTAMP DEFAULT NOW(), 
                    contact_name VARCHAR(255), 
                    contact_email VARCHAR(255) 
                ) 
            ''') 
            cursor.execute(''' 
                INSERT INTO organizations (id, name, type, subscription_tier) 
                VALUES (1, 'SentinelEHR Demo', 'demo', 'demo') 
                ON CONFLICT (id) DO NOTHING 
            ''') 
            conn.commit() 
            print('[DATABASE] Organizations table verified') 
        except Exception as e: 
            conn.rollback() 
            print(f'[DATABASE] Organizations table skip: {str(e)}') 

        try:
            cursor.execute('ALTER TABLE organizations ADD COLUMN IF NOT EXISTS api_key VARCHAR(64) UNIQUE')
            cursor.execute('ALTER TABLE organizations ADD COLUMN IF NOT EXISTS epic_connection_verified BOOLEAN DEFAULT FALSE')
            cursor.execute('ALTER TABLE organizations ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMP')
            conn.commit()
            print('[DATABASE] Organizations columns verified')
        except Exception as e:
            conn.rollback()
            print(f'[DATABASE] Organizations columns skip: {str(e)}')

        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_state (
                    id SERIAL PRIMARY KEY,
                    organization_id INTEGER NOT NULL,
                    table_name VARCHAR(100) NOT NULL,
                    last_sync_at TIMESTAMP,
                    last_record_count INTEGER DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'never_run',
                    error_message TEXT,
                    updated_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(organization_id, table_name)
                )
            ''')
            conn.commit()
            print('[DATABASE] Sync state table verified')
        except Exception as e:
            conn.rollback()
            print(f'[DATABASE] Sync state table skip: {str(e)}')

        try:
            cursor.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_id INTEGER DEFAULT 1') 
            cursor.execute('UPDATE users SET organization_id = 1 WHERE organization_id IS NULL') 
            conn.commit() 
            print('[DATABASE] organization_id verified on users') 
        except Exception as e: 
            conn.rollback() 
            print(f'[DATABASE] organization_id skip on users: {str(e)}') 
        
        # Add organization_id to core tables 
        for table in ['alerts', 'cases', 'employees', 'anomaly_scores', 'audit_events', 'patient_panels']: 
            try: 
                cursor.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS organization_id INTEGER DEFAULT 1') 
                cursor.execute(f'UPDATE {table} SET organization_id = 1 WHERE organization_id IS NULL') 
                conn.commit() 
                print(f'[DATABASE] organization_id verified on {table}') 
            except Exception as e: 
                conn.rollback() 
                print(f'[DATABASE] organization_id skip on {table}: {str(e)}')

        try:
            cursor.execute('''
                ALTER TABLE audit_events
                ADD CONSTRAINT audit_events_unique
                UNIQUE (audit_id, organization_id)
            ''')
            conn.commit()
            print('[DATABASE] audit_events unique constraint verified')
        except Exception as e:
            conn.rollback()
            print(f'[DATABASE] audit_events constraint skip: {str(e)}')

        try:
            cursor.execute('''
                ALTER TABLE patient_panels
                ADD CONSTRAINT patient_panels_unique
                UNIQUE (emp_id, pat_id, organization_id)
            ''')
            conn.commit()
            print('[DATABASE] patient_panels unique constraint verified')
        except Exception as e:
            conn.rollback()
            print(f'[DATABASE] patient_panels constraint skip: {str(e)}')

        try:
            cursor.execute('''
                ALTER TABLE employees
                ADD CONSTRAINT employees_org_unique
                UNIQUE (emp_id, organization_id)
            ''')
            conn.commit()
            print('[DATABASE] employees unique constraint verified')
        except Exception as e:
            conn.rollback()
            print(f'[DATABASE] employees constraint skip: {str(e)}')

        try:
            cursor.execute('ALTER TABLE user_baselines ADD COLUMN IF NOT EXISTS organization_id INTEGER DEFAULT 1')
            cursor.execute('UPDATE user_baselines SET organization_id = 1 WHERE organization_id IS NULL')
            conn.commit()
            print('[DATABASE] organization_id verified on user_baselines')
        except Exception as e:
            conn.rollback()
            print(f'[DATABASE] user_baselines skip: {str(e)}')

        try:
            cursor.execute('''
                ALTER TABLE user_baselines
                ADD CONSTRAINT user_baselines_emp_org_unique
                UNIQUE (emp_id, organization_id)
            ''')
            conn.commit()
            print('[DATABASE] user_baselines unique constraint verified')
        except Exception as e:
            conn.rollback()
            print(f'[DATABASE] user_baselines constraint skip: {str(e)}')

        # Recreate active_alerts view with organization_id 
        try: 
            cursor.execute('DROP VIEW IF EXISTS active_alerts') 
            cursor.execute(''' 
                CREATE VIEW active_alerts AS 
                SELECT alert_id, emp_id, alert_date, rules_triggered, rule_count, 
                       severity, explanation, event_count, out_of_panel, off_hours_count, 
                       export_print_count, break_glass_count, vip_out_of_panel, 
                       cross_dept_count, is_acknowledged, created_at, status, 
                       reviewer_notes, priority_rank, reviewed_by, reviewed_at, 
                       anomaly_score, adjusted_severity, case_id, sensitive_out_of_panel, 
                       organization_id 
                FROM alerts 
                WHERE adjusted_severity <> 'Suppressed' 
                AND status <> 'resolved' 
                ORDER BY priority_rank 
            ''') 
            conn.commit() 
            print('[DATABASE] active_alerts view recreated with organization_id') 
        except Exception as e: 
            conn.rollback() 
            print(f'[DATABASE] active_alerts view error: {str(e)}') 
        
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

        # Add per-email brute-force tracking columns
        try: 
            cursor.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_attempts INTEGER DEFAULT 0') 
            cursor.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP') 
            conn.commit() 
            print('[DATABASE] Login lockout columns verified') 
        except Exception as e: 
            conn.rollback() 
            print(f'[DATABASE] Lockout columns skip: {str(e)}') 
        
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
        
        try: 
            cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS refresh_tokens ( 
                    id SERIAL PRIMARY KEY, 
                    token VARCHAR(255) UNIQUE NOT NULL, 
                    user_id INTEGER NOT NULL, 
                    email VARCHAR(255) NOT NULL, 
                    org_id INTEGER NOT NULL, 
                    role VARCHAR(100) NOT NULL, 
                    expires_at TIMESTAMP NOT NULL, 
                    created_at TIMESTAMP DEFAULT NOW() 
                ) 
            ''') 
            conn.commit() 
            print('[DATABASE] Refresh tokens table verified') 
        except Exception as e: 
            conn.rollback() 
            print(f'[DATABASE] Refresh tokens skip: {str(e)}') 

        try: 
            cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS deleted_alerts_log ( 
                    alert_id INTEGER, 
                    deleted_at TIMESTAMP DEFAULT NOW(), 
                    deleted_by VARCHAR(255) 
                ) 
            ''') 
            conn.commit() 
            print('[DATABASE] Cascade deletion protection applied') 
        except Exception as e: 
            conn.rollback() 
            print(f'[DATABASE] Cascade protection skip: {str(e)}') 
        
        # One-time migration to fix existing case dates
        try:
            print('[DATABASE] Running one-time case date migration...')
            cursor.execute("""
                UPDATE cases 
                SET window_start = (
                    SELECT alert_date 
                    FROM alerts 
                    WHERE alert_id = (
                        SELECT (alert_ids::json->0)::text::integer 
                        FROM cases c2 
                        WHERE c2.case_id = cases.case_id
                    )
                ), 
                window_end = (
                    SELECT alert_date + INTERVAL '30 days'
                    FROM alerts 
                    WHERE alert_id = (
                        SELECT (alert_ids::json->0)::text::integer 
                        FROM cases c2 
                        WHERE c2.case_id = cases.case_id
                    )
                ), 
                created_at = (
                    SELECT alert_date 
                    FROM alerts 
                    WHERE alert_id = (
                        SELECT (alert_ids::json->0)::text::integer 
                        FROM cases c2 
                        WHERE c2.case_id = cases.case_id
                    )
                ) 
                WHERE window_start < '2026-01-01'
            """)
            conn.commit()
            print('[DATABASE] Case date migration complete')
        except Exception as e:
            conn.rollback()
            print(f'[DATABASE] Case date migration skip or error: {str(e)}')
            
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
 
def create_token(username: str, role: str, org_id: int) -> str: 
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS) 
    return jwt.encode( 
        {"sub": username, "role": role, "org_id": org_id, "exp": expire}, 
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
        org_id = payload.get('org_id', 1)
        if not username or not role: 
            raise HTTPException(status_code=401, 
                detail="Invalid token") 
        return {"username": username, "role": role, "org_id": org_id} 
    except JWTError: 
        raise HTTPException(status_code=401, 
            detail="Invalid or expired token") 

def get_current_user_from_token(token_data: dict):
  username = token_data["username"]
  try: 
    conn = get_connection() 
    cursor = conn.cursor() 
    cursor.execute( 
      'SELECT id, email, role FROM users WHERE email = %s', 
      (username,) 
    ) 
    user = cursor.fetchone() 
    conn.close() 
    if user: 
      return {'user_id': user['id'], 'username': user['email'], 'role': user['role']} 
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

def get_org_from_api_key(request: Request):
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        raise HTTPException(status_code=401, detail='API key required')
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name, is_active FROM organizations WHERE api_key = %s',
            (api_key,)
        )
        org = cursor.fetchone()
        conn.close()
        if not org:
            raise HTTPException(status_code=401, detail='Invalid API key')
        if not org['is_active']:
            raise HTTPException(status_code=403, detail='Organization account is inactive')
        return dict(org)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")

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
        audit_log_login(email, ip_address, "BLOCKED (IP Rate Limit)")
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
            "SELECT id, email, password_hash, role, organization, organization_id, is_active, failed_attempts, locked_until FROM users WHERE email = %s", 
            (email,) 
        ) 
        user = cursor.fetchone() 
        
        if not user:
            conn.close()
            record_failed_login(ip_address)
            audit_log_login(email, ip_address, "FAILED (User not found)")
            raise HTTPException(status_code=401, detail="Incorrect email or password")

        if user.get('locked_until') and user['locked_until'] > datetime.utcnow(): 
            conn.close()
            audit_log_login(email, ip_address, "BLOCKED (Account Locked)")
            raise HTTPException(status_code=429, detail='Account temporarily locked. Too many failed attempts. Try again in 10 minutes.') 
        
        if not user['is_active']:
            conn.close()
            audit_log_login(email, ip_address, "FAILED (Inactive account)")
            raise HTTPException(status_code=401, detail="Account is deactivated")

        if len(password) > 128:
            conn.close()
            record_failed_login(ip_address)
            raise HTTPException(status_code=400, detail="Invalid credentials")

        if not case_logic.verify_password(password, user['password_hash']):
            cursor.execute('UPDATE users SET failed_attempts = COALESCE(failed_attempts, 0) + 1, locked_until = CASE WHEN COALESCE(failed_attempts, 0) + 1 >= 5 THEN NOW() + INTERVAL \'10 minutes\' ELSE locked_until END WHERE email = %s', (email,))
            conn.commit() 
            conn.close() 
            record_failed_login(ip_address)
            audit_log_login(email, ip_address, "FAILED")
            raise HTTPException(status_code=401, detail='Incorrect email or password') 
        
        # Reset failures and update last login
        cursor.execute('UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = NOW() WHERE email = %s', (email,)) 
        conn.commit()
        
        audit_log_login(email, ip_address, "SUCCESS")
        token = create_token(user['email'], user['role'], user['organization_id']) 
        
        refresh_token = secrets.token_urlsafe(64) 
        expires_at = datetime.utcnow() + timedelta(days=30) 
        cursor.execute( 
            'INSERT INTO refresh_tokens (token, user_id, email, org_id, role, expires_at) VALUES (%s, %s, %s, %s, %s, %s)', 
            (refresh_token, user['id'], user['email'], user['organization_id'], user['role'], expires_at) 
        ) 
        conn.commit() 
        conn.close()

        response = JSONResponse(content={ 
            'access_token': token, 
            'token_type': 'bearer', 
            'role': user['role'], 
            'user_id': user['id'], 
            'email': user['email'], 
            'organization': user['organization'] 
        }) 
        response.set_cookie( 
            key='refresh_token', 
            value=refresh_token, 
            httponly=True, 
            secure=True, 
            samesite='none', 
            max_age=30 * 24 * 60 * 60 
        ) 
        return response 
    except HTTPException:
        raise
    except Exception as e: 
        print(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post('/auth/refresh')
@limiter.limit("20/minute")
def refresh_access_token(request: Request): 
    refresh_token = request.cookies.get('refresh_token') 
    if not refresh_token: 
        raise HTTPException(status_code=401, detail='No refresh token') 
    try: 
        conn = get_connection() 
        cursor = conn.cursor() 
        cursor.execute( 
            'SELECT * FROM refresh_tokens WHERE token = %s AND expires_at > NOW()', 
            (refresh_token,) 
        ) 
        token_row = cursor.fetchone() 
        if not token_row: 
            conn.close() 
            raise HTTPException(status_code=401, detail='Invalid or expired refresh token') 
        new_access_token = create_token(token_row['email'], token_row['role'], token_row['org_id']) 
        conn.close() 
        return { 
            'access_token': new_access_token, 
            'token_type': 'bearer', 
            'role': token_row['role'], 
            'email': token_row['email'] 
        } 
    except HTTPException: 
        raise 
    except Exception as e: 
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred") 

@app.post('/auth/logout') 
def logout(request: Request): 
    refresh_token = request.cookies.get('refresh_token') 
    if refresh_token: 
        try: 
            conn = get_connection() 
            cursor = conn.cursor() 
            cursor.execute('DELETE FROM refresh_tokens WHERE token = %s', (refresh_token,)) 
            conn.commit() 
            conn.close() 
        except: 
            pass 
    response = JSONResponse(content={'message': 'Logged out'}) 
    response.delete_cookie(key='refresh_token', samesite='none', secure=True) 
    return response 

@app.api_route("/health", methods=['GET', 'HEAD'])
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
            "error": "Service unavailable",
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
        return {"status": "failed", "error": "An internal error occurred"}

@app.get("/summary")
@limiter.limit("60/minute") 
def get_summary(request: Request, token_data = Depends(verify_token)):
    # Everyone can see summary
    try:
        org_id = token_data.get('org_id', 1) 
        conn = get_db()
        cursor = conn.cursor()
        
        # Total active alerts and breakdown
        cursor.execute(''' 
            SELECT COUNT(*) as total_active, 
                SUM(CASE WHEN adjusted_severity = 'Critical' THEN 1 ELSE 0 END) as critical, 
                SUM(CASE WHEN adjusted_severity = 'High' THEN 1 ELSE 0 END) as high, 
                SUM(CASE WHEN adjusted_severity = 'Medium' THEN 1 ELSE 0 END) as medium, 
                MAX(anomaly_score) as top_anomaly_score 
            FROM active_alerts 
            WHERE alert_date >= NOW() - INTERVAL '180 days' 
            AND organization_id = %s 
        ''', (org_id,)) 
        alert_stats = cursor.fetchone()
        
        # Total employees monitored
        cursor.execute('SELECT COUNT(*) FROM employees WHERE organization_id = %s', (org_id,)) 
        total_employees = cursor.fetchone()['count']
        
        # Date range
        cursor.execute(''' 
            SELECT MIN(alert_date), MAX(alert_date) FROM alerts 
            WHERE adjusted_severity != 'Suppressed' AND organization_id = %s 
        ''', (org_id,)) 
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
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")

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
        org_id = token_data.get('org_id', 1) 
        conn = get_db()
        cursor = conn.cursor()
        
        query = "SELECT * FROM alerts WHERE alert_date >= NOW() - INTERVAL '180 days' AND organization_id = %s" 
        params = [org_id] 
        
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
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")

@app.get("/alerts/{alert_id}")
def get_alert(alert_id: int, token_data = Depends(verify_token)):
    try:
        org_id = token_data.get('org_id', 1) 
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM alerts WHERE alert_id = %s AND organization_id = %s', (alert_id, org_id)) 
        alert = cursor.fetchone()
        conn.close()
        
        if not alert:
            raise HTTPException(status_code=404, detail={"error": "Alert not found"})
        return dict(alert)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")

@app.patch("/alerts/{alert_id}/status")
def update_alert_status(alert_id: int, update: StatusUpdate, token_data = Depends(require_role('compliance_officer', 'admin'))):
    try:
        org_id = token_data.get('org_id', 1) 
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if alert exists
        cursor.execute('SELECT * FROM alerts WHERE alert_id = %s AND organization_id = %s', (alert_id, org_id)) 
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
            WHERE alert_id = %s AND organization_id = %s
        """, (update.status, update.reviewer_notes, update.reviewed_by, reviewed_at, alert_id, org_id))
        
        conn.commit()
        
        # Return updated alert
        cursor.execute('SELECT * FROM alerts WHERE alert_id = %s AND organization_id = %s', (alert_id, org_id)) 
        updated_alert = dict(cursor.fetchone())
        conn.close()
        
        return updated_alert
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")

@app.get("/employees/{emp_id}/profile")
@limiter.limit("30/minute") 
def get_employee_profile(request: Request, emp_id: int, token_data = Depends(require_role('compliance_officer', 'admin'))):
    try:
        org_id = token_data.get('org_id', 1) 
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Employee info
        cursor.execute('SELECT role, dept_id, is_float FROM employees WHERE emp_id = %s AND organization_id = %s', (emp_id, org_id)) 
        emp = cursor.fetchone()
        if not emp:
            conn.close()
            raise HTTPException(status_code=404, detail={"error": "Employee not found"})
            
        # 2. Top anomaly score
        cursor.execute('SELECT MAX(anomaly_score) as top_score FROM anomaly_scores WHERE emp_id = %s AND organization_id = %s', (emp_id, org_id)) 
        score_row = cursor.fetchone()
        top_score = float(score_row['top_score']) if score_row and score_row['top_score'] is not None else 0.0

        # 3. Last 20 alerts
        cursor.execute("""
            SELECT alert_id, alert_date, adjusted_severity, rules_triggered, anomaly_score
            FROM alerts
            WHERE emp_id = %s AND organization_id = %s
            ORDER BY alert_date DESC
            LIMIT 20
        """, (emp_id, org_id))
        alerts = [dict(row) for row in cursor.fetchall()]

        # 4. Open cases
        cursor.execute("""
            SELECT case_id, status, priority, window_start, window_end, created_at, 
                   (EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400)::int as days_open
            FROM cases
            WHERE emp_id = %s AND status != 'Resolved' AND status != 'Closed' AND organization_id = %s
        """, (emp_id, org_id))
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
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")

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
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")

@app.get("/investigate")
@limiter.limit("30/minute")
def investigate_employee(request: Request, emp_id: int, token_data = Depends(require_role('compliance_officer', 'admin'))):
    try:
        org_id = token_data.get('org_id', 1) 
        conn = get_db()
        cursor = conn.cursor()
        
        # Get employee info
        cursor.execute('SELECT * FROM employees WHERE emp_id = %s AND organization_id = %s', (emp_id, org_id)) 
        emp = cursor.fetchone()
        if not emp:
            conn.close()
            raise HTTPException(status_code=404, detail="Employee not found")
            
        # Get audit events for this employee
        cursor.execute("""
            SELECT action_datetime, pat_id, workstation_id, anomaly_type, action_c
            FROM audit_events
            WHERE emp_id = %s AND organization_id = %s
            ORDER BY action_datetime DESC
            LIMIT 500
        """, (emp_id, org_id))
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
        cursor.execute("SELECT COUNT(*) FROM alerts WHERE emp_id = %s AND organization_id = %s", (emp_id, org_id)) 
        total_alerts = cursor.fetchone()['count']
        
        # Get max OCR risk score from cases
        cursor.execute("SELECT MAX(ocr_risk_score) as max_ocr FROM cases WHERE emp_id = %s AND organization_id = %s", (emp_id, org_id)) 
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
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")

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
  if len(body.get('password', '')) > 128:
    raise HTTPException(status_code=400, detail="Password too long")

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
@limiter.limit("20/minute")
def list_users(
  request: Request,
  token_data = Depends(require_role('admin'))
): 
  conn = get_connection() 
  cursor = conn.cursor() 
  cursor.execute( 
    "SELECT id, email, role, is_active, created_at FROM users ORDER BY created_at" 
  ) 
  users = [dict(r) for r in cursor.fetchall()] 
  conn.close() 
  return {"users": users} 

@app.post('/users/change-password')
@limiter.limit("5/minute")
def change_password(request: Request, body: dict, token_data = Depends(verify_token)): 
    current_password = body.get('current_password') 
    new_password = body.get('new_password') 
    
    if not current_password or not new_password: 
        raise HTTPException(status_code=400, detail='Both current and new password required') 
    if len(new_password) < 8: 
        raise HTTPException(status_code=400, detail='New password must be at least 8 characters') 
    
    try: 
        conn = get_connection() 
        cursor = conn.cursor() 
        cursor.execute('SELECT id, password_hash FROM users WHERE email = %s', (token_data['username'],)) 
        user = cursor.fetchone() 
        
        if not user or not case_logic.verify_password(current_password, user['password_hash']): 
            conn.close() 
            raise HTTPException(status_code=401, detail='Current password is incorrect') 
        
        new_hash = case_logic.hash_password(new_password) 
        cursor.execute('UPDATE users SET password_hash = %s WHERE id = %s', (new_hash, user['id'])) 
        conn.commit() 
        conn.close() 
        return {'message': 'Password updated successfully'} 
    except HTTPException: 
        raise 
    except Exception as e: 
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred") 

@app.post('/users/update-email')
@limiter.limit("5/minute")
def update_email(request: Request, body: dict, token_data = Depends(verify_token)): 
    new_email = body.get('new_email', '').lower().strip() 
    if not new_email or '@' not in new_email: 
        raise HTTPException(status_code=400, detail='Valid email required') 
    try: 
        conn = get_connection() 
        cursor = conn.cursor() 
        cursor.execute('UPDATE users SET email = %s WHERE email = %s', (new_email, token_data['username'])) 
        conn.commit() 
        conn.close() 
        return {'message': 'Email updated successfully'} 
    except Exception as e: 
        raise HTTPException(status_code=400, detail='Email already in use or update failed') 
 
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
  org_id = token_data.get('org_id', 1) 
  conn = get_connection() 
  case_logic.flag_overdue_cases(conn) 
  conditions = [] 
  params = [] 
  conditions.append('organization_id = %s') 
  params.append(org_id) 
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
  org_id = token_data.get('org_id', 1) 
  conn = get_connection() 
  case_logic.flag_overdue_cases(conn) 
  cursor = conn.cursor() 
  cursor.execute( 
    """SELECT c.*, EXTRACT(DAY FROM NOW() - c.window_start) as days_open 
       FROM cases c WHERE c.case_id = %s AND c.organization_id = %s""", 
    (case_id, org_id) 
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
  org_id = token_data.get('org_id', 1) 
  new_status = body.get("status") 
  note = body.get("note", "") 
  
  if not new_status: 
    raise HTTPException(400, "Status required") 
  
  # Verify case exists for this organization
  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute("SELECT 1 FROM cases WHERE case_id = %s AND organization_id = %s", (case_id, org_id))
  if not cursor.fetchone():
    conn.close()
    raise HTTPException(404, "Case not found")
  conn.close()
  
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
  org_id = token_data.get('org_id', 1) 
  note_text = body.get("note", "").strip() 
  if not note_text: 
    raise HTTPException(400, "Note cannot be empty") 
  
  # Verify case exists for this organization
  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute("SELECT 1 FROM cases WHERE case_id = %s AND organization_id = %s", (case_id, org_id))
  if not cursor.fetchone():
    conn.close()
    raise HTTPException(404, "Case not found")
  conn.close()
  
  user = get_current_user_from_token(token_data)
  case_logic.add_case_note(case_id, user['user_id'], note_text) 
  return {"case_id": case_id, "note_added": True} 
 
@app.patch("/cases/{case_id}/assign") 
def assign_case( 
  case_id: str, 
  body: dict, 
  token_data = Depends(require_role('admin','compliance_officer')) 
): 
  org_id = token_data.get('org_id', 1) 
  assign_to_id = body.get("user_id") 
  user = get_current_user_from_token(token_data)
  conn = get_connection() 
  cursor = conn.cursor() 
  cursor.execute( 
    "SELECT assigned_to FROM cases WHERE case_id = %s AND organization_id = %s", 
    (case_id, org_id) 
  ) 
  current = cursor.fetchone() 
  if not current: 
    raise HTTPException(404, "Case not found") 
  
  old_assigned = current['assigned_to'] 
  cursor.execute( 
    """UPDATE cases SET assigned_to = %s, 
       updated_at = NOW() WHERE case_id = %s AND organization_id = %s""", 
    (assign_to_id, case_id, org_id) 
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
  org_id = token_data.get('org_id', 1) 
  outcome = body.get("outcome") 
  valid = ['Legitimate Access','Policy Violation','Training Required','Termination Recommended','No Action'] 
  if outcome not in valid: 
    raise HTTPException(400, f"Invalid outcome") 
  
  # Verify case exists for this organization
  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute("SELECT 1 FROM cases WHERE case_id = %s AND organization_id = %s", (case_id, org_id))
  if not cursor.fetchone():
    conn.close()
    raise HTTPException(404, "Case not found")
  conn.close()
  
  user = get_current_user_from_token(token_data)
  case_logic.set_case_outcome(case_id, outcome, user['user_id']) 
  return {"case_id": case_id, "outcome": outcome} 
 
@app.get("/cases/{case_id}/export") 
def export_case( 
  case_id: str, 
  token_data = Depends(require_role('admin','compliance_officer','it_director')) 
): 
  org_id = token_data.get('org_id', 1) 
  conn = get_connection() 
  case_logic.flag_overdue_cases(conn) 
  cursor = conn.cursor() 
  cursor.execute( 
    "SELECT * FROM cases WHERE case_id = %s AND organization_id = %s", (case_id, org_id) 
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
@limiter.limit("10/minute")
def export_alerts(
    request: Request,
    severity: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    emp_id: Optional[int] = None,
    token_data = Depends(require_role('compliance_officer', 'admin'))
):
    try:
        org_id = token_data.get('org_id', 1) 
        conn = get_db()
        cursor = conn.cursor()
        
        query = 'SELECT alert_id, alert_date, emp_id, adjusted_severity, rules_triggered, anomaly_score, explanation FROM alerts WHERE organization_id = %s' 
        params = [org_id] 
        
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
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")

@app.get("/export/case/{case_id}")
@limiter.limit("10/minute")
def export_case_report(
    case_id: str,
    request: Request,
    token_data = Depends(require_role('compliance_officer', 'admin'))
):
    try:
        org_id = token_data.get('org_id', 1) 
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Fetch case metadata
        cursor.execute('SELECT * FROM cases WHERE case_id = %s AND organization_id = %s', (case_id, org_id)) 
        case = cursor.fetchone()
        if not case:
            conn.close()
            raise HTTPException(status_code=404, detail="Case not found")
            
        # 2. Fetch employee info
        cursor.execute("SELECT emp_id, role, dept_id FROM employees WHERE emp_id = %s AND organization_id = %s", (case['emp_id'], org_id)) 
        employee = cursor.fetchone()
        
        # 3. Fetch linked alerts
        import json
        alert_ids = case['alert_ids'] if isinstance(case['alert_ids'], list) else json.loads(case['alert_ids'])
        alerts = []
        if alert_ids:
            placeholders = ', '.join(['%s'] * len(alert_ids))
            cursor.execute(f"SELECT * FROM alerts WHERE alert_id IN ({placeholders}) AND organization_id = %s", tuple(alert_ids) + (org_id,)) 
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
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")

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
        
        # Store thresholds in database
        conn = get_connection() 
        cursor = conn.cursor() 
        cursor.execute('UPDATE settings SET value = %s, updated_at = NOW() WHERE key = %s', (str(body.critical_threshold), 'critical_threshold')) 
        cursor.execute('UPDATE settings SET value = %s, updated_at = NOW() WHERE key = %s', (str(body.high_threshold), 'high_threshold')) 
        cursor.execute('UPDATE settings SET value = %s, updated_at = NOW() WHERE key = %s', (str(body.medium_threshold), 'medium_threshold')) 
        conn.commit() 
        conn.close() 
        
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
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")

@app.get("/settings/thresholds")
def get_thresholds(
    token_data = Depends(require_role('admin', 'compliance_officer'))
):
    """Get current alert severity thresholds"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings WHERE key IN ('critical_threshold', 'high_threshold', 'medium_threshold')")
        rows = cursor.fetchall()
        conn.close()
        
        # Convert to dictionary with float values
        thresholds = {row['key']: float(row['value']) for row in rows}
        
        # Ensure we have all keys, otherwise use defaults
        return {
            "critical_threshold": thresholds.get('critical_threshold', 0.7),
            "high_threshold": thresholds.get('high_threshold', 0.4),
            "medium_threshold": thresholds.get('medium_threshold', 0.2)
        }
    except Exception as e:
        # Fallback to defaults if database fails
        print(f"[DATABASE ERROR] Failed to fetch thresholds: {str(e)}")
        return {
            "critical_threshold": 0.7,
            "high_threshold": 0.4,
            "medium_threshold": 0.2
        }

# ─── ADMIN DETECTION PIPELINE ──────────────────────────────

@app.post('/admin/run-detection/{org_id}')
@limiter.limit("5/minute")
def trigger_detection(request: Request, org_id: int, token_data = Depends(require_role('admin'))):
    import subprocess
    import sys
    import os

    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    results = {}

    try:
        # Step 1 — Baseline calculator
        result0 = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, 'baseline_calculator.py'), str(org_id)],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result0.returncode != 0:
            raise Exception("Detection step failed. Check server logs for details.")
        results['baseline_calculator'] = 'success'

        # Step 2 — Rules engine
        result1 = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, 'rules_engine.py'), str(org_id)],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result1.returncode != 0:
            raise Exception("Detection step failed. Check server logs for details.")
        results['rules_engine'] = 'success'

        # Step 3 — Anomaly detector
        result2 = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, 'anomaly_detector.py'), str(org_id)],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result2.returncode != 0:
            raise Exception("Detection step failed. Check server logs for details.")
        results['anomaly_detector'] = 'success'

        # Step 4 — Auto case creator
        result3 = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, 'auto_case_creator.py'), str(org_id)],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result3.returncode != 0:
            raise Exception("Detection step failed. Check server logs for details.")
        results['auto_case_creator'] = 'success'

        return {
            'status': 'success',
            'org_id': org_id,
            'pipeline': results,
            'message': f'Detection pipeline completed for organization {org_id}'
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail='Detection pipeline timed out after 5 minutes')
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@app.get('/admin/detection-status/{org_id}')
def get_detection_status(org_id: int, token_data = Depends(require_role('admin'))):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MAX(created_at) as last_run, COUNT(*) as total_alerts
            FROM alerts WHERE organization_id = %s
        ''', (org_id,))
        result = cursor.fetchone()
        conn.close()
        return {
            'org_id': org_id,
            'last_detection_run': result['last_run'],
            'total_alerts': result['total_alerts']
        }
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


# ─── ADMIN ORGANIZATION MANAGEMENT ─────────────────────────

@app.post('/admin/organizations')
@limiter.limit("10/minute")
def create_organization(request: Request, body: dict, token_data = Depends(require_role('admin'))):
    name = body.get('name', '').strip()
    org_type = body.get('type', 'community_hospital')
    contact_name = body.get('contact_name', '').strip()
    contact_email = body.get('contact_email', '').strip()
    subscription_tier = body.get('subscription_tier', 'design_partner')

    if not name:
        raise HTTPException(status_code=400, detail='Organization name required')

    api_key = secrets.token_urlsafe(48)

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO organizations
            (name, type, contact_name, contact_email, subscription_tier, api_key, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            RETURNING id, name, api_key
        ''', (name, org_type, contact_name, contact_email, subscription_tier, api_key))
        org = cursor.fetchone()

        for table in ['audit_events', 'employees', 'patient_panels']:
            cursor.execute('''
                INSERT INTO sync_state (organization_id, table_name, status)
                VALUES (%s, %s, 'never_run')
                ON CONFLICT (organization_id, table_name) DO NOTHING
            ''', (org['id'], table))

        conn.commit()
        conn.close()

        return {
            'organization_id': org['id'],
            'name': org['name'],
            'api_key': org['api_key'],
            'message': 'Organization created. Store the api_key securely — it will not be shown again.'
        }
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@app.get('/admin/organizations')
def list_organizations(token_data = Depends(require_role('admin'))):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, type, contact_name, contact_email,
                    subscription_tier, is_active, created_at,
                   epic_connection_verified, last_sync_at,
                   LEFT(api_key, 8) || '...' as api_key_preview
            FROM organizations
            ORDER BY created_at DESC
        ''')
        orgs = cursor.fetchall()
        conn.close()
        return {'organizations': [dict(o) for o in orgs]}
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@app.post('/admin/organizations/{org_id}/rotate-key')
@limiter.limit("5/minute")
def rotate_api_key(request: Request, org_id: int, token_data = Depends(require_role('admin'))):
    new_key = secrets.token_urlsafe(48)
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE organizations SET api_key = %s WHERE id = %s RETURNING name',
            (new_key, org_id)
        )
        org = cursor.fetchone()
        if not org:
            conn.close()
            raise HTTPException(status_code=404, detail='Organization not found')
        conn.commit()
        conn.close()
        return {
            'organization_id': org_id,
            'name': org['name'],
            'new_api_key': new_key,
            'message': 'API key rotated. Update the extraction script config immediately.'
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


# ─── INGESTION ENDPOINTS ────────────────────────────────────

@app.get('/ingest/sync-state')
def get_sync_state(request: Request):
    org = get_org_from_api_key(request)
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT table_name, last_sync_at, last_record_count, status, error_message
            FROM sync_state
            WHERE organization_id = %s
            ORDER BY table_name
        ''', (org['id'],))
        states = cursor.fetchall()
        conn.close()
        return {
            'organization_id': org['id'],
            'organization_name': org['name'],
            'sync_state': [dict(s) for s in states]
        }
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@app.post('/ingest/data')
@limiter.limit("20/minute")
def ingest_data(request: Request, body: dict = Body(...)):
    org = get_org_from_api_key(request)
    org_id = org['id']

    table = body.get('table')
    records = body.get('records', [])
    if not isinstance(records, list):
        raise HTTPException(status_code=400, detail="records must be a list")
    if len(records) > 50000:
        raise HTTPException(status_code=400, detail="Batch too large. Maximum 50000 records per request.")
    batch_id = body.get('batch_id')
    is_last_batch = body.get('is_last_batch', False)

    valid_tables = ['audit_events', 'employees', 'patient_panels']
    if table not in valid_tables:
        raise HTTPException(status_code=400, detail=f'Invalid table. Must be one of: {valid_tables}')

    if not records:
        return {'status': 'skipped', 'message': 'No records to insert', 'count': 0}

    try:
        conn = get_connection()
        cursor = conn.cursor()

        inserted = 0
        skipped = 0

        if table == 'audit_events':
            for record in records:
                try:
                    cursor.execute('''
                        INSERT INTO audit_events (
                            audit_id, emp_id, pat_id, action_c, action_datetime,
                            dept_id, in_panel, is_vip_access, is_sensitive_access,
                            is_known_user, organization_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (audit_id, organization_id) DO NOTHING
                    ''', (
                        record.get('audit_id'),
                        record.get('emp_id'),
                        record.get('pat_id'),
                        record.get('action_c'),
                        record.get('action_datetime'),
                        record.get('dept_id'),
                        record.get('in_panel', False),
                        record.get('is_vip_access', False),
                        record.get('is_sensitive_access', False),
                        record.get('is_known_user', True),
                        org_id
                    ))
                    inserted += 1
                except Exception:
                    skipped += 1
                    conn.rollback()
                    continue

        elif table == 'employees':
            for record in records:
                try:
                    cursor.execute('''
                        INSERT INTO employees (
                            emp_id, role, dept_id, normal_start, normal_end,
                            is_float, organization_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (emp_id, organization_id)
                        DO UPDATE SET
                            role = EXCLUDED.role,
                            dept_id = EXCLUDED.dept_id,
                            normal_start = EXCLUDED.normal_start,
                            normal_end = EXCLUDED.normal_end,
                            is_float = EXCLUDED.is_float
                    ''', (
                        record.get('emp_id'),
                        record.get('role'),
                        record.get('dept_id'),
                        record.get('normal_start'),
                        record.get('normal_end'),
                        record.get('is_float', False),
                        org_id
                    ))
                    inserted += 1
                except Exception:
                    skipped += 1
                    conn.rollback()
                    continue

        elif table == 'patient_panels':
            for record in records:
                try:
                    cursor.execute('''
                        INSERT INTO patient_panels (emp_id, pat_id, organization_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (emp_id, pat_id, organization_id) DO NOTHING
                    ''', (
                        record.get('emp_id'),
                        record.get('pat_id'),
                        org_id
                    ))
                    inserted += 1
                except Exception:
                    skipped += 1
                    conn.rollback()
                    continue

        conn.commit()

        if is_last_batch:
            cursor.execute('''
                UPDATE sync_state
                SET last_sync_at = NOW(),
                    last_record_count = (
                        SELECT COUNT(*) FROM audit_events
                        WHERE organization_id = %s
                    ),
                    status = 'success',
                    error_message = NULL,
                    updated_at = NOW()
                WHERE organization_id = %s AND table_name = %s
            ''', (org_id, org_id, table))

            cursor.execute(
                'UPDATE organizations SET last_sync_at = NOW() WHERE id = %s',
                (org_id,)
            )
            conn.commit()

        if is_last_batch and table == 'audit_events':
            import subprocess
            import sys
            import threading
            import os

            SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

            def run_detection_async(org_id):
                try:
                    print(f'[INGEST] Auto-triggering detection for org {org_id} after sync')
                    result0 = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'baseline_calculator.py'), str(org_id)],
                                             capture_output=False, timeout=300)
                    print(f'[DETECTION] baseline_calculator exit code: {result0.returncode}')
                    result1 = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'rules_engine.py'), str(org_id)],
                                             capture_output=False, timeout=300)
                    print(f'[DETECTION] rules_engine exit code: {result1.returncode}')
                    result2 = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'anomaly_detector.py'), str(org_id)],
                                             capture_output=False, timeout=300)
                    print(f'[DETECTION] anomaly_detector exit code: {result2.returncode}')
                    result3 = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'auto_case_creator.py'), str(org_id)],
                                             capture_output=False, timeout=300)
                    print(f'[DETECTION] auto_case_creator exit code: {result3.returncode}')
                    print(f'[INGEST] Auto-detection complete for org {org_id}')
                except Exception as e:
                    print(f'[INGEST] Auto-detection failed for org {org_id}: {e}')

            thread = threading.Thread(target=run_detection_async, args=(org_id,), daemon=True)
            thread.start()
            print(f'[INGEST] Detection pipeline started async for org {org_id}')

        conn.close()

        return {
            'status': 'success',
            'table': table,
            'organization_id': org_id,
            'inserted': inserted,
            'skipped': skipped,
            'is_last_batch': is_last_batch
        }

    except Exception as e:
        try:
            cursor.execute('''
                UPDATE sync_state
                SET status = 'error', error_message = %s, updated_at = NOW()
                WHERE organization_id = %s AND table_name = %s
            ''', (str(e), org_id, table))
            conn.commit()
            conn.close()
        except:
            pass
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


# ─── SERVER STARTUP ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
