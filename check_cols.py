from db import get_connection
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
print([r['column_name'] for r in cur.fetchall()])
conn.close()