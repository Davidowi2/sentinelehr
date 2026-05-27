from db import get_connection 
import bcrypt 
 
conn = get_connection() 
cur = conn.cursor() 
 
pw1 = bcrypt.hashpw('hbh-demo-2026'.encode(), bcrypt.gensalt()).decode() 
pw2 = bcrypt.hashpw('it-demo-2026'.encode(), bcrypt.gensalt()).decode() 
 
cur.execute( 
    "INSERT INTO users (username, password_hash, role, email, active) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (username) DO UPDATE SET password_hash=EXCLUDED.password_hash, role=EXCLUDED.role, active=EXCLUDED.active", 
    ('demo', pw1, 'compliance_officer', 'demo@sentinelehr.com', True) 
) 
cur.execute( 
    "INSERT INTO users (username, password_hash, role, email, active) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (username) DO UPDATE SET password_hash=EXCLUDED.password_hash, role=EXCLUDED.role, active=EXCLUDED.active", 
    ('it_demo', pw2, 'it_director', 'it@sentinelehr.com', True) 
) 
 
conn.commit() 
print('Users seeded successfully') 
conn.close()