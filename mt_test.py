import requests, warnings, json, base64, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from db import get_connection
warnings.filterwarnings('ignore')
BASE = 'https://sentinelehr.onrender.com'

# ── Login as admin ──────────────────────────────────────────
r = requests.post(BASE + '/login', json={'email':'admin@sentinelehr.com','password':'sentinelehr2026'}, verify=False, timeout=30)
token1 = r.json()['access_token']
h1 = {'Authorization': f'Bearer {token1}'}
print("=== PART 1 ===")

# ── Cleanup any leftover from prior runs ────────────────────
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id FROM organizations WHERE name = 'Multi-Tenancy Test Hospital'")
existing = cur.fetchone()
if existing:
    prior_id = existing['id']
    cur.execute("DELETE FROM alerts WHERE organization_id = %s", (prior_id,))
    cur.execute("DELETE FROM users WHERE email = 'mt_co@hospital2test.org'")
    cur.execute("DELETE FROM organizations WHERE id = %s", (prior_id,))
    conn.commit()
    print(f"Pre-cleaned prior org id={prior_id}")
conn.close()

# ── 1a: Create org 2 ────────────────────────────────────────
r = requests.post(BASE + '/admin/organizations', headers=h1, verify=False, timeout=30,
    json={'name':'Multi-Tenancy Test Hospital','type':'test',
          'contact_name':'MT Test','contact_email':'mt@hospital2test.org',
          'subscription_tier':'demo'})
print("CREATE ORG STATUS:", r.status_code)
org_data = r.json()
org2_id = org_data.get('organization_id')
print(f"ORG2 ID: {org2_id}")

# ── 1b: Create user in org 2 ────────────────────────────────
r = requests.post(BASE + '/admin/users/create', headers=h1, verify=False, timeout=30,
    json={'email':'mt_co@hospital2test.org','password':'MultiTenancyTest2026!',
          'role':'compliance_officer','organization_id': org2_id})
print("CREATE USER STATUS:", r.status_code, r.json())

# ── 1c: Insert 3 alerts for org 2 via direct DB ─────────────
print("\nInserting org 2 alerts...")
conn = get_connection()
cur = conn.cursor()
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
row = cur.fetchone()
print(f"ORG2 ALERT COUNT AFTER INSERT: {row['cnt']}")
conn.close()

# ── PART 2: Login as org 2 user ─────────────────────────────
print("\n=== PART 2 ===")
r = requests.post(BASE + '/login', json={'email':'mt_co@hospital2test.org','password':'MultiTenancyTest2026!'}, verify=False, timeout=30)
print("ORG2 LOGIN STATUS:", r.status_code)
login2 = r.json()
token2 = login2.get('access_token')
h2 = {'Authorization': f'Bearer {token2}'}
print("ORG2 LOGIN (no token):", {k:v for k,v in login2.items() if k != 'access_token'})

def decode_jwt_payload(token):
    try:
        p = token.split('.')[1]
        p += '=' * (4 - len(p) % 4)
        return json.loads(base64.b64decode(p))
    except Exception as e:
        return {'error': str(e)}

print("TOKEN1 PAYLOAD:", decode_jwt_payload(token1))
print("TOKEN2 PAYLOAD:", decode_jwt_payload(token2))

# ── PART 3: Read isolation ───────────────────────────────────
print("\n=== PART 3 ===")

# token2 alerts
r = requests.get(BASE + '/alerts?limit=10', headers=h2, verify=False, timeout=30)
t2_alerts_body = r.json()
t2_list = t2_alerts_body.get('alerts', [])
t2_dates = [a.get('alert_date','')[:10] for a in t2_list]
t2_expl  = [a.get('explanation','') for a in t2_list]
print(f"TOKEN2 /alerts total_count: {t2_alerts_body.get('total_count')}")
print(f"TOKEN2 alert dates: {t2_dates}")
print(f"TOKEN2 contains any '2026' date: {'❌ LEAK' if any('2026' in d for d in t2_dates) else '✅ No'}")
print(f"TOKEN2 all explanations contain 'MT Test': {all('MT Test' in e for e in t2_expl)}")

r = requests.get(BASE + '/summary', headers=h2, verify=False, timeout=30)
t2_sum = r.json()
print(f"TOKEN2 /summary: {t2_sum}")

r = requests.get(BASE + '/cases?limit=10', headers=h2, verify=False, timeout=30)
t2_cases_body = r.json()
print(f"TOKEN2 /cases total_count: {t2_cases_body.get('total_count')}")

# token1 alerts
r = requests.get(BASE + '/alerts?limit=10', headers=h1, verify=False, timeout=30)
t1_alerts_body = r.json()
t1_list = t1_alerts_body.get('alerts', [])
t1_dates = [a.get('alert_date','')[:10] for a in t1_list]
t1_expl  = [a.get('explanation','') for a in t1_list]
print(f"\nTOKEN1 /alerts total_count: {t1_alerts_body.get('total_count')}")
print(f"TOKEN1 alert dates (first 10): {t1_dates}")
print(f"TOKEN1 contains 'MT Test': {'❌ LEAK' if any('MT Test' in e for e in t1_expl) else '✅ No'}")

r = requests.get(BASE + '/summary', headers=h1, verify=False, timeout=30)
t1_sum = r.json()
print(f"TOKEN1 /summary: {t1_sum}")

r = requests.get(BASE + '/cases?limit=3', headers=h1, verify=False, timeout=30)
t1_cases_body = r.json()
print(f"TOKEN1 /cases total_count: {t1_cases_body.get('total_count')}")

print(f"\nTOKEN1 earliest date: {min(t1_dates) if t1_dates else 'N/A'}")
print(f"TOKEN1 latest date:   {max(t1_dates) if t1_dates else 'N/A'}")
print(f"TOKEN2 earliest date: {min(t2_dates) if t2_dates else 'N/A'}")
print(f"TOKEN2 latest date:   {max(t2_dates) if t2_dates else 'N/A'}")

# ── PART 4: Direct ID access attacks ────────────────────────
print("\n=== PART 4 ===")
for path in ['/cases/SEN-2026-0001', '/alerts/1', '/employees/10042']:
    r1 = requests.get(BASE + path, headers=h1, verify=False, timeout=30)
    r2 = requests.get(BASE + path, headers=h2, verify=False, timeout=30)
    leak = r2.status_code == 200 and len(r2.text) > 10
    print(f"{path}: token1={r1.status_code}({len(r1.text)}b)  token2={r2.status_code}({len(r2.text)}b)  {'❌ LEAK' if leak else '✅ OK'}")
    if leak:
        print(f"  LEAK BODY: {r2.text[:200]}")

# ── PART 5: Summary table ────────────────────────────────────
print("\n=== PART 5 — SUMMARY TABLE ===")
r_c1_t2 = requests.get(BASE + '/cases/SEN-2026-0001', headers=h2, verify=False, timeout=30)
r_a1_t1 = requests.get(BASE + '/alerts/1', headers=h1, verify=False, timeout=30)
r_a1_t2 = requests.get(BASE + '/alerts/1', headers=h2, verify=False, timeout=30)
r_e_t1  = requests.get(BASE + '/employees/10042', headers=h1, verify=False, timeout=30)
r_e_t2  = requests.get(BASE + '/employees/10042', headers=h2, verify=False, timeout=30)
r_c1_t1 = requests.get(BASE + '/cases/SEN-2026-0001', headers=h1, verify=False, timeout=30)

rows = [
    ('/summary total_active',    t1_sum.get('total_active'), t2_sum.get('total_active'),
        t1_sum.get('total_active') == 1271 and t2_sum.get('total_active') == 3),
    ('/alerts date range',       '2026-01→2026-03', '2025-06 only',
        not any('2026' in d for d in t2_dates) and not any('MT Test' in e for e in t1_expl)),
    ('/cases total',             t1_cases_body.get('total_count'), t2_cases_body.get('total_count'),
        t2_cases_body.get('total_count') == 0),
    ('/cases/SEN-2026-0001',     r_c1_t1.status_code, r_c1_t2.status_code,
        r_c1_t2.status_code in (403, 404)),
    ('/alerts/1',                r_a1_t1.status_code, r_a1_t2.status_code,
        r_a1_t2.status_code in (403, 404)),
    ('/employees/10042',         r_e_t1.status_code, r_e_t2.status_code,
        r_e_t2.status_code in (403, 404)),
]
print(f"{'Endpoint':<30} {'token1 (org1)':>15} {'token2 (org2)':>15} {'Isolated?':>10}")
print("-"*75)
for row in rows:
    print(f"{row[0]:<30} {str(row[1]):>15} {str(row[2]):>15} {'✅ YES' if row[3] else '❌ NO':>10}")

verdict = all(r[3] for r in rows)
print(f"\nVERDICT: {'✅ PASS' if verdict else '❌ FAIL'} — multi-tenancy read isolation")

# ── CLEANUP ─────────────────────────────────────────────────
print("\n=== CLEANUP ===")
conn = get_connection()
cur = conn.cursor()
cur.execute("DELETE FROM alerts WHERE organization_id = %s", (org2_id,))
a = cur.rowcount
cur.execute("DELETE FROM users WHERE email = 'mt_co@hospital2test.org'")
u = cur.rowcount
cur.execute("DELETE FROM organizations WHERE id = %s", (org2_id,))
o = cur.rowcount
conn.commit()
conn.close()
print(f"Deleted: {a} alerts, {u} users, {o} organizations")
