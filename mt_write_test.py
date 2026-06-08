"""Multi-tenancy WRITE isolation test for SentinelEHR."""
import requests, warnings, json, base64, sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from db import get_connection
import case_logic
warnings.filterwarnings('ignore')

BASE = 'https://sentinelehr.onrender.com'
TS   = int(time.time())
TEST_EMAIL = f'mt_write_{TS}@hospital2test.org'
TEST_PASS  = 'MTWriteTest2026!'

# ── Login as admin ───────────────────────────────────────────
r = requests.post(BASE + '/login',
    json={'email':'admin@sentinelehr.com','password':'sentinelehr2026'},
    verify=False, timeout=30)
token_admin = r.json()['access_token']
h_admin = {'Authorization': f'Bearer {token_admin}'}
print("Admin login OK\n")

# ── Pre-clean any leftover test orgs ────────────────────────
conn = get_connection()
cur  = conn.cursor()
for name in ('MT Write Test Hospital', 'Multi-Tenancy Test Hospital'):
    cur.execute("SELECT id FROM organizations WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        oid = row['id']
        cur.execute("DELETE FROM alerts WHERE organization_id = %s", (oid,))
        cur.execute("DELETE FROM users  WHERE organization_id = %s", (oid,))
        cur.execute("DELETE FROM organizations WHERE id = %s", (oid,))
        conn.commit()
        print(f"Pre-cleaned org '{name}' id={oid}")
cur.execute("DELETE FROM users WHERE email LIKE 'mt_write_%@hospital2test.org'")
conn.commit()
conn.close()

# ── Create test org ──────────────────────────────────────────
r = requests.post(BASE + '/admin/organizations', headers=h_admin, verify=False, timeout=30,
    json={'name':'MT Write Test Hospital','type':'test',
          'contact_name':'MT Write','contact_email':'mtwrite@hospital2test.org',
          'subscription_tier':'demo'})
org2_id = r.json().get('organization_id')
print(f"Test org created: org_id={org2_id}")

# ── Create test user via DB (API endpoint has username bug) ─
conn = get_connection()
cur  = conn.cursor()
pw_hash = case_logic.hash_password(TEST_PASS)
cur.execute("""
    INSERT INTO users (username, email, password_hash, role, organization_id, is_active)
    VALUES (%s, %s, %s, 'compliance_officer', %s, TRUE)
    RETURNING id
""", (TEST_EMAIL, TEST_EMAIL, pw_hash, org2_id))
new_uid = cur.fetchone()['id']
conn.commit()
conn.close()
print(f"Test user created: id={new_uid} email={TEST_EMAIL}\n")

# ── Login as test org user ───────────────────────────────────
r = requests.post(BASE + '/login',
    json={'email': TEST_EMAIL, 'password': TEST_PASS},
    verify=False, timeout=30)
if r.status_code != 200:
    print(f"FATAL: login failed {r.status_code} {r.text}")
    sys.exit(1)
token_mt = r.json()['access_token']
h_mt = {'Authorization': f'Bearer {token_mt}'}

def decode_jwt(t):
    try:
        p = t.split('.')[1]; p += '=' * (4 - len(p) % 4)
        return json.loads(base64.b64decode(p))
    except Exception as e: return {'error': str(e)}

p = decode_jwt(token_mt)
print(f"Token2 payload: sub={p.get('sub')} org_id={p.get('org_id')} role={p.get('role')}\n")

# ── Find an org 1 alert_id ───────────────────────────────────
conn = get_connection()
cur  = conn.cursor()
cur.execute("SELECT alert_id, status FROM alerts WHERE organization_id = 1 ORDER BY alert_id LIMIT 1")
org1_alert = cur.fetchone()
org1_alert_id     = org1_alert['alert_id']
org1_alert_status = org1_alert['status']

cur.execute("SELECT status, waiting_on FROM cases WHERE case_id = 'SEN-2026-0001' AND organization_id = 1")
org1_case = cur.fetchone()
org1_case_status   = org1_case['status']   if org1_case else 'NOTFOUND'
org1_case_waiton   = org1_case['waiting_on'] if org1_case else None
conn.close()

print(f"Org1 test alert: alert_id={org1_alert_id} status='{org1_alert_status}'")
print(f"Org1 test case:  SEN-2026-0001 status='{org1_case_status}' waiting_on='{org1_case_waiton}'\n")

results = {}

# ══════════════════════════════════════════════════════════════
# WRITE TEST 1 — Dismiss org 1's alert
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print(f"WRITE TEST 1 — Dismiss /alerts/{org1_alert_id}/dismiss")
r = requests.post(
    f"{BASE}/alerts/{org1_alert_id}/dismiss",
    headers=h_mt, verify=False, timeout=30,
    json={'reason_code': 'False Positive', 'reason_detail': 'MT write test'}
)
print(f"  Response: {r.status_code} {r.text[:120]}")

# Verify: was the alert actually dismissed?
conn = get_connection()
cur  = conn.cursor()
cur.execute("SELECT status FROM alerts WHERE alert_id = %s AND organization_id = 1", (org1_alert_id,))
row = cur.fetchone()
conn.close()
post_status = row['status'] if row else 'NOTFOUND'
was_dismissed = (post_status == 'dismissed' and org1_alert_status != 'dismissed')
print(f"  Alert status before: '{org1_alert_status}' | after: '{post_status}'")
if was_dismissed:
    print(f"  ❌ WRITE ISOLATION FAIL — alert was dismissed by cross-org token!")
else:
    print(f"  ✅ No write — status unchanged")
results['dismiss_alert'] = {
    'http_status': r.status_code,
    'write_succeeded': was_dismissed,
    'pass': r.status_code in (403, 404) and not was_dismissed
}

# ══════════════════════════════════════════════════════════════
# WRITE TEST 2 — Add note to org 1's case
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("WRITE TEST 2 — POST /cases/SEN-2026-0001/notes")
r = requests.post(
    f"{BASE}/cases/SEN-2026-0001/notes",
    headers=h_mt, verify=False, timeout=30,
    json={'content': 'MT write test - should not save', 'note_type': 'investigation'}
)
print(f"  Response: {r.status_code} {r.text[:120]}")

# Verify: does the note exist?
r_notes = requests.get(f"{BASE}/cases/SEN-2026-0001/notes", headers=h_admin, verify=False, timeout=30)
notes = r_notes.json().get('notes', [])
leaked_note = [n for n in notes if 'MT write test' in (n.get('content') or '')]
if leaked_note:
    print(f"  ❌ WRITE ISOLATION FAIL — note was saved: {leaked_note[0]}")
else:
    print(f"  ✅ No note written to org1 case")
results['add_note'] = {
    'http_status': r.status_code,
    'write_succeeded': bool(leaked_note),
    'pass': r.status_code in (403, 404) and not leaked_note
}

# ══════════════════════════════════════════════════════════════
# WRITE TEST 3 — Change status of org 1's case
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("WRITE TEST 3 — PATCH /cases/SEN-2026-0001/status")
r = requests.patch(
    f"{BASE}/cases/SEN-2026-0001/status",
    headers=h_mt, verify=False, timeout=30,
    json={'status': 'Closed', 'reason': 'MT write test'}
)
print(f"  Response: {r.status_code} {r.text[:120]}")

conn = get_connection()
cur  = conn.cursor()
cur.execute("SELECT status FROM cases WHERE case_id = 'SEN-2026-0001' AND organization_id = 1")
row = cur.fetchone()
conn.close()
post_case_status = row['status'] if row else 'NOTFOUND'
was_changed = (post_case_status != org1_case_status)
print(f"  Case status before: '{org1_case_status}' | after: '{post_case_status}'")
if was_changed:
    print(f"  ❌ WRITE ISOLATION FAIL — case status was changed!")
else:
    print(f"  ✅ No write — status unchanged")
results['change_status'] = {
    'http_status': r.status_code,
    'write_succeeded': was_changed,
    'pass': r.status_code in (403, 404) and not was_changed
}

# ══════════════════════════════════════════════════════════════
# WRITE TEST 4 — Snooze org 1's case
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("WRITE TEST 4 — POST /cases/SEN-2026-0001/snooze")
r = requests.post(
    f"{BASE}/cases/SEN-2026-0001/snooze",
    headers=h_mt, verify=False, timeout=30,
    json={'waiting_on': 'HR', 'due_back_date': '2025-12-31', 'reason': 'MT write test'}
)
print(f"  Response: {r.status_code} {r.text[:120]}")

conn = get_connection()
cur  = conn.cursor()
cur.execute("SELECT waiting_on, status FROM cases WHERE case_id = 'SEN-2026-0001' AND organization_id = 1")
row = cur.fetchone()
conn.close()
post_waiton = row['waiting_on'] if row else None
post_snooze_status = row['status'] if row else 'NOTFOUND'
was_snoozed = (post_waiton == 'HR' and org1_case_waiton != 'HR')
print(f"  waiting_on before: '{org1_case_waiton}' | after: '{post_waiton}'")
if was_snoozed:
    print(f"  ❌ WRITE ISOLATION FAIL — case was snoozed by cross-org token!")
else:
    print(f"  ✅ No write — waiting_on unchanged")
results['snooze'] = {
    'http_status': r.status_code,
    'write_succeeded': was_snoozed,
    'pass': r.status_code in (403, 404) and not was_snoozed
}

# ══════════════════════════════════════════════════════════════
# WRITE TEST 5 — OCR assessment on org 1's case
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("WRITE TEST 5 — POST /cases/SEN-2026-0001/ocr-assess")
conn = get_connection()
cur  = conn.cursor()
cur.execute("SELECT COUNT(*) as cnt FROM ocr_assessments WHERE case_id = 'SEN-2026-0001'")
ocr_before = cur.fetchone()['cnt']
conn.close()

r = requests.post(
    f"{BASE}/cases/SEN-2026-0001/ocr-assess",
    headers=h_mt, verify=False, timeout=30,
    json={'breach_confirmed': True}
)
print(f"  Response: {r.status_code} {r.text[:120]}")

conn = get_connection()
cur  = conn.cursor()
cur.execute("SELECT COUNT(*) as cnt FROM ocr_assessments WHERE case_id = 'SEN-2026-0001'")
ocr_after = cur.fetchone()['cnt']
conn.close()
was_ocr_written = (ocr_after > ocr_before)
print(f"  OCR assessments for SEN-2026-0001 before: {ocr_before} | after: {ocr_after}")
if was_ocr_written:
    print(f"  ❌ WRITE ISOLATION FAIL — OCR assessment was created by cross-org token!")
else:
    print(f"  ✅ No write — OCR count unchanged")
results['ocr_assess'] = {
    'http_status': r.status_code,
    'write_succeeded': was_ocr_written,
    'pass': r.status_code in (403, 404) and not was_ocr_written
}

# ══════════════════════════════════════════════════════════════
# FINAL VERDICT
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("WRITE ISOLATION — FINAL RESULTS")
print(f"{'Test':<30} {'HTTP':>6} {'Write?':>8} {'Pass?':>8}")
print("-" * 60)
labels = {
    'dismiss_alert':  'Dismiss org1 alert',
    'add_note':       'Add note to org1 case',
    'change_status':  'Change org1 case status',
    'snooze':         'Snooze org1 case',
    'ocr_assess':     'OCR assess org1 case',
}
all_pass = True
for key, label in labels.items():
    res = results[key]
    write = '❌ YES' if res['write_succeeded'] else '✅ No'
    passed = '✅ PASS' if res['pass'] else '❌ FAIL'
    if not res['pass']:
        all_pass = False
    print(f"{label:<30} {res['http_status']:>6} {write:>10} {passed:>10}")

print()
print(f"VERDICT: {'✅ PASS' if all_pass else '❌ FAIL'} — write isolation")
if not all_pass:
    for key, res in results.items():
        if not res['pass']:
            print(f"  FAILING: {labels[key]} — HTTP {res['http_status']}, write_succeeded={res['write_succeeded']}")

# ── CLEANUP ─────────────────────────────────────────────────
print()
print("=" * 60)
print("CLEANUP")
conn = get_connection()
cur  = conn.cursor()
cur.execute("DELETE FROM cases  WHERE organization_id = %s", (org2_id,)); c = cur.rowcount
cur.execute("DELETE FROM alerts WHERE organization_id = %s", (org2_id,)); a = cur.rowcount
cur.execute(f"DELETE FROM users WHERE email = '{TEST_EMAIL}'");            u = cur.rowcount
cur.execute("DELETE FROM organizations WHERE id = %s", (org2_id,));       o = cur.rowcount
conn.commit()
conn.close()
print(f"Deleted: {c} cases, {a} alerts, {u} users, {o} organizations")
