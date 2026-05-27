from db import get_connection 
import bcrypt 
 
conn = get_connection() 
cur = conn.cursor() 
cur.execute("SELECT username, role, active, password_hash FROM users WHERE username = 'demo'") 
row = cur.fetchone() 
print("User found:", row['username'], row['role'], row['active']) 
 
test_password = 'hbh-demo-2026' 
match = bcrypt.checkpw(test_password.encode(), row['password_hash'].encode()) 
print("Password match:", match) 
conn.close()