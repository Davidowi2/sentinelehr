import sqlite3

def run_queries():
    conn = sqlite3.connect('sentinel.db')
    cursor = conn.cursor()
    
    print("--- Query 1: Attacker Mean Scores ---")
    query1 = """
    SELECT a.emp_id, 
           ROUND(AVG(a.anomaly_score), 4) as mean_score, 
           COUNT(*) as alert_days 
    FROM alerts a 
    WHERE a.emp_id IN (1022, 1052, 1061, 1067) 
    GROUP BY a.emp_id 
    ORDER BY mean_score DESC;
    """
    cursor.execute(query1)
    r1 = cursor.fetchall()
    print('EMP_ID | MEAN_SCORE | ALERT_DAYS')
    print('-' * 35)
    for r in r1:
        print(f'{r[0]:<6} | {r[1]:<10} | {r[2]}')
        
    print("\n--- Query 2: Upgraded Alerts Distribution ---")
    query2 = """
    SELECT emp_id, COUNT(*) as upgraded_alerts 
    FROM alerts 
    WHERE adjusted_severity = 'High' 
    GROUP BY emp_id 
    ORDER BY upgraded_alerts DESC 
    LIMIT 10;
    """
    cursor.execute(query2)
    r2 = cursor.fetchall()
    print('EMP_ID | UPGRADED_ALERTS')
    print('-' * 25)
    for r in r2:
        print(f'{r[0]:<6} | {r[1]}')
        
    conn.close()

if __name__ == "__main__":
    run_queries()
