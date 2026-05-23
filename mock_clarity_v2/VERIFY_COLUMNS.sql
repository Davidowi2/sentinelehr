-- ============================================================ 
-- SENTINELEHR CLARITY COLUMN VERIFICATION SCRIPT 
-- Run this against your Epic Clarity database (read-only) 
-- before connecting SentinelEHR. 
-- Share the output with your SentinelEHR implementation contact. 
-- ============================================================ 
 
-- TEST 1: Confirm ACCESS_LOG table exists 
 SELECT 'ACCESS_LOG exists' AS test, 
   COUNT(*) AS row_count 
 FROM ACCESS_LOG 
 WHERE ROWNUM <= 1; 
 
-- TEST 2: Confirm critical column names in ACCESS_LOG 
-- If any column is missing, Epic may use a different name. 
 SELECT 
   CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL - column missing' END AS ACCESS_LOG_ID_check 
 FROM INFORMATION_SCHEMA.COLUMNS 
 WHERE TABLE_NAME = 'ACCESS_LOG' 
 AND COLUMN_NAME = 'ACCESS_LOG_ID'; 
 
 SELECT 
   CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL - may be LOG_TIME or EVENT_INSTANT' END AS ACCESS_INSTANT_check 
 FROM INFORMATION_SCHEMA.COLUMNS 
 WHERE TABLE_NAME = 'ACCESS_LOG' 
 AND COLUMN_NAME = 'ACCESS_INSTANT'; 
 
 SELECT 
   CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL - column missing' END AS USER_ID_check 
 FROM INFORMATION_SCHEMA.COLUMNS 
 WHERE TABLE_NAME = 'ACCESS_LOG' 
 AND COLUMN_NAME = 'USER_ID'; 
 
 SELECT 
   CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL - column missing' END AS PAT_ID_check 
 FROM INFORMATION_SCHEMA.COLUMNS 
 WHERE TABLE_NAME = 'ACCESS_LOG' 
 AND COLUMN_NAME = 'PAT_ID'; 
 
 SELECT 
   CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL - may be DEPARTMENT_ID' END AS DEP_ID_check 
 FROM INFORMATION_SCHEMA.COLUMNS 
 WHERE TABLE_NAME = 'ACCESS_LOG' 
 AND COLUMN_NAME = 'DEP_ID'; 
 
-- TEST 3: Confirm CLARITY_EMP columns 
 SELECT 
   CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL - column missing' END AS CLARITY_EMP_USER_ID_check 
 FROM INFORMATION_SCHEMA.COLUMNS 
 WHERE TABLE_NAME = 'CLARITY_EMP' 
 AND COLUMN_NAME = 'USER_ID'; 
 
-- TEST 4: Confirm PAT_ENC exists and has expected columns 
 SELECT 
   CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL - column missing' END AS PAT_ENC_CSN_ID_check 
 FROM INFORMATION_SCHEMA.COLUMNS 
 WHERE TABLE_NAME = 'PAT_ENC' 
 AND COLUMN_NAME = 'PAT_ENC_CSN_ID'; 
 
-- TEST 5: Sample 5 rows from ACCESS_LOG to verify date format 
-- ACCESS_INSTANT should be a float (Epic internal datetime) 
-- Values should be around 67000-68000 range for recent dates 
 SELECT TOP 5 
   ACCESS_LOG_ID, 
   USER_ID, 
   PAT_ID, 
   ACTION_C, 
   ACCESS_INSTANT, 
   DEP_ID 
 FROM ACCESS_LOG 
 ORDER BY ACCESS_INSTANT DESC; 
 
-- TEST 6: Confirm ACTION_C values match expected codes 
-- Expected: 1=View/InChart, 3=Open, 4=Print, 5=Export, 6=BreakGlass 
 SELECT ACTION_C, COUNT(*) as event_count 
 FROM ACCESS_LOG 
 GROUP BY ACTION_C 
 ORDER BY ACTION_C; 
 
-- TEST 7: Date range sanity check 
 SELECT 
   MIN(ACCESS_INSTANT) as earliest_event, 
   MAX(ACCESS_INSTANT) as latest_event, 
   COUNT(*) as total_events 
 FROM ACCESS_LOG; 
 
-- ============================================================ 
-- RESULTS INTERPRETATION 
-- Send all output to your SentinelEHR contact. 
-- Any FAIL results require column name confirmation 
-- before ingestion pipeline can connect. 
-- Expected Epic date range for 2026: 67,526 to 67,890 
-- ============================================================ 
