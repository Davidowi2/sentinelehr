"""Create org2 user directly via DB, bypassing the API endpoint."""
import requests, warnings, json, base64, sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from db import get_connection
import case_logic
warnings.filterwarnings('ignore')
BASE = 'https://sentinelehr.onrender.com'

TS = int(time.time())
TEST_EMAIL = f'mt_co_{TS}@hospital2test.org'
TEST_PASS = 'MultiTenancyTest2026!'

# Login as admin
r = requests.post(BASE + '/login', json={'email':'admin@sentinelehr.com','password':'sentinelehr2026'}, verify=False, timeout=30)
token1 = r.json()['access_token']
h1 = {'Authorization': f'Bearer {token1}'}
print("=== PART 1 ===")

# Pre-clean
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id FROM organizations WHERE name = 'Multi-Tenancy Test Hospital'")
row = cur.fetchone()
if row:
    oid = row['id']
    cur.execute("DELETE FROM alerts WHERE organization_id = %s", (oid,))
    cur.execute("DELETE FROM users WHERE organization_id = %s", (oid,))
    cur.execute("DELETE FROM organizations WHERE id = %s", (oid,))
    conn.commit()
    print(f"Pre-cleaned org id={oid}")
conn.close()

# Create org via API
r = requests.post(BASE + '/admin/organizations', headers=h1, verify=False, timeout=30,
    json={'name':'Multi-Tenancy Test Hospital','type':'test',
          'contact_name':'MT Test','contact_email':'mt@hospital2test.org',
          'subscription_tier':'demo'})
org2_id = r.json().get('organization_id')
print(f"ORG2 ID: {org2_id} (status {r.status_code})")

# Create user DIRECTLY via DB (bypasses broken API endpoint)
pw_hash = case_logic.hash_password(TEST_PASS)
conn = get_connection()
cur = conn.cursor()
cur.execute("""
    INSERT INTO users (username, email, password_hash, role, organization_id, is_active)
    VALUES (%s, %s, %s, 'compliance_officer', %s, TRUE)
    ON CONFLICT DO NOTHING
    RETURNING id, email, role, organization_id
""", (TEST_EMAIL, TEST_EMAIL, pw_hash, org2_id))
user = dict(cur.fetchone())
conn.commit()
print(f"Created user via DB: {user}")

# Insert 3 org2 alerts
cur.execute("""
    INSERT INTO alerts (
        emp_id, alert_date, rules_triggered, rule_count, severity, explanation,
        event_count, out_of_panel, off_hours_count, export_print_count,
        break_glass_count, vip_out_of_panel, cross_dept_count, is_acknowledged,
        created_at, status, reviewer_notes, priority_rank, reviewed_by,
        reviewed_at, anomaly_score, adjusted_severity, case_id,
        sensitive_out_of_panel, organization_id
    ) VALUES
        (10001,'2025-06-15','R1',1,'Critical','MT Test: org 2 unique alert June 15',25,5,0,0,0,0,0,0,NOW(),'open',NULL,1,NULL,NULL,0.95,'Critical',NULL,0,%s),
        (10002,'2025-06-20','R8',1,'Critical','MT Test: org 2 sensitive record June 20',15,0,0,0,0,0,0,0,NOW(),'open',NULL,1,NULL,NULL,0.88,'Critical',NULL,1,%s),
        (10003,'2025-06-25','R2',1,'High','MT Test: org 2 off-hours June 25',8,0,8,0,0,0,0,0,NOW(),'open',NULL,2,NULL,NULL,0.72,'High',NULL,0,%s)
""", (org2_id, org2_id, org2_id))
conn.commit()
cur.execute("SELECT COUNT(*) as cnt FROM alerts WHERE organization_id = %s", (org2_id,))
print(f"ORG2 ALERT COUNT: {cur.fetchone()['cnt']}")
conn.close()

# === PART 2: Login as org2 user ===
print("\n=== PART 2 ===")
r = requests.post(BASE + '/login', json={'email': TEST_EMAIL, 'password': TEST_PASS}, verify=False, timeout=30)
print("ORG2 LOGIN STATUS:", r.status_code)
login2 = r.json()
token2 = login2.get('access_token')
if not token2:
    print("FATAL: org2 login failed:", login2); sys.exit(1)
h2 = {'Authorization': f'Bearer {token2}'}

def decode_jwt(t):
    try:
        p = t.split('.')[1]; p += '=' * (4 - len(p) % 4)
        return json.loads(base64.b64decode(p))
    except Exception as e: return {'error': str(e)}

p1 = decode_jwt(token1); p2 = decode_jwt(token2)
print(f"TOKEN1: sub={p1.get('sub')} org_id={p1.get('org_id')} role={p1.get('role')}")
print(f"TOKEN2: sub={p2.get('sub')} org_id={p2.get('org_id')} role={p2.get('role')}")

# === PART 3: Read isolation ===
print("\n=== PART 3 ===")

r = requests.get(BASE + '/alerts?limit=10', headers=h2, verify=False, timeout=30)
t2b = r.json(); t2_list = t2b.get('alerts', [])
t2_dates = [a.get('alert_date','')[:10] for a in t2_list]
t2_expl  = [a.get('explanation','') for a in t2_list]
has_2026_in_t2 = any('2026' in d for d in t2_dates)
print(f"TOKEN2 /alerts total: {t2b.get('total_count')} | dates: {t2_dates}")
print(f"  '2026' in token2 dates: {'❌ LEAK' if has_2026_in_t2 else '✅ No'}")
print(f"  All expl contain 'MT Test': {all('MT Test' in e for e in t2_expl)}")

r = requests.get(BASE + '/summary', headers=h2, verify=False, timeout=30)
t2_sum = r.json(); print(f"TOKEN2 /summary: {t2_sum}")

r = requests.get(BASE + '/cases?limit=10', headers=h2, verify=False, timeout=30)
t2_cases = r.json(); print(f"TOKEN2 /cases total: {t2_cases.get('total_count')}")

r = requests.get(BASE + '/alerts?limit=10', headers=h1, verify=False, timeout=30)
t1b = r.json(); t1_list = t1b.get('alerts', [])
t1_dates = [a.get('alert_date','')[:10] for a in t1_list]
t1_expl  = [a.get('explanation','') for a in t1_list]
has_mt_in_t1 = any('MT Test' in e for e in t1_expl)
print(f"\nTOKEN1 /alerts total: {t1b.get('total_count')} | dates (first 5): {t1_dates[:5]}")
print(f"  'MT Test' in token1 explanations: {'❌ LEAK' if has_mt_in_t1 else '✅ No'}")

r = requests.get(BASE + '/summary', headers=h1, verify=False, timeout=30)
t1_sum = r.json(); print(f"TOKEN1 /summary: {t1_sum}")

r = requests.get(BASE + '/cases?limit=3', headers=h1, verify=False, timeout=30)
t1_cases = r.json(); print(f"TOKEN1 /cases total: {t1_cases.get('total_count')}")

print(f"\nTOKEN1 date range: {min(t1_dates) if t1_dates else 'N/A'} → {max(t1_dates) if t1_dates else 'N/A'}")
print(f"TOKEN2 date range: {min(t2_dates) if t2_dates else 'N/A'} → {max(t2_dates) if t2_dates else 'N/A'}")

# === PART 4: Direct ID attacks ===
print("\n=== PART 4 ===")
attack_paths = ['/cases/SEN-2026-0001', '/alerts/1', '/employees/10042']
part4 = {}
for path in attack_paths:
    r1 = requests.get(BASE + path, headers=h1, verify=False, timeout=30)
    r2 = requests.get(BASE + path, headers=h2, verify=False, timeout=30)
    leak = r2.status_code == 200 and len(r2.text) > 20
    part4[path] = (r1.status_code, r2.status_code, not leak)
    print(f"{path}: org1={r1.status_code}({len(r1.text)}b) | org2={r2.status_code}({len(r2.text)}b) {'❌ LEAK' if leak else '✅ OK'}")

# === PART 5: Final table ===
print("\n=== PART 5 — FINAL SUMMARY TABLE ===")
rows = [
    ('/summary total_active',  t1_sum.get('total_active'), t2_sum.get('total_active'),
     t1_sum.get('total_active')==1271 and t2_sum.get('total_active')==3),
    ('/alerts date range',     '2026-01→2026-03', '2025-06 only',
     not has_2026_in_t2 and not has_mt_in_t1),
    ('/cases total',           t1_cases.get('total_count'), t2_cases.get('total_count'),
     t2_cases.get('total_count')==0),
    ('/cases/SEN-2026-0001',   *part4['/cases/SEN-2026-0001']),
    ('/alerts/1',              *part4['/alerts/1']),
    ('/employees/10042',       *part4['/employees/10042']),
]
print(f"{'Endpoint':<30} {'org1 (token1)':>15} {'org2 (token2)':>15} {'Isolated?':>10}")
print("-"*75)
for row in rows:
    print(f"{row[0]:<30} {str(row[1]):>15} {str(row[2]):>15} {'✅ YES' if row[3] else '❌ NO':>10}")

verdict = all(r[3] for r in rows)
print(f"\nVERDICT: {'✅ PASS' if verdict else '❌ FAIL'} — multi-tenancy read isolation")
if not verdict:
    for row in rows:
        if not row[3]:
            print(f"  FAILING ROW: {row[0]} → org1={row[1]}, org2={row[2]}")

# === CLEANUP ===
print("\n=== CLEANUP ===")
conn = get_connection()
cur = conn.cursor()
cur.execute("DELETE FROM alerts WHERE organization_id = %s", (org2_id,))
a = cur.rowcount
cur.execute(f"DELETE FROM users WHERE email = '{TEST_EMAIL}'")
u = cur.rowcount
cur.execute("DELETE FROM organizations WHERE id = %s", (org2_id,))
o = cur.rowcount
conn.commit()
conn.close()
print(f"Deleted: {a} alerts, {u} users, {o} organizations. Done.")
