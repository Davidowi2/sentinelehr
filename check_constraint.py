from db import get_connection 
 
conn = get_connection() 
cur = conn.cursor() 
cur.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='users_role_check'") 
print(cur.fetchall()) 
conn.close()