# SentinelEHR — Hospital Implementation Guide 

## Before You Begin 
Run `VERIFY_COLUMNS.sql` against your Clarity database. Send results to your SentinelEHR contact before proceeding. 

## Connection Requirements 
- Read-only SQL access to Epic Clarity database 
- Tables required: `ACCESS_LOG`, `CLARITY_EMP`, `PATIENT`, `PAT_ENC`, `CLARITY_DEP`, `ZC_ACS_ACTION` 
- No write access ever required or requested 
- Connection string format (SQL Server): `mssql+pyodbc://user:password@server/ClarityDB` 
- Connection string format (Oracle): `oracle+cx_oracle://user:password@server/CLARITY` 

## What SentinelEHR Reads 
Only audit/access log data. Never clinical notes, diagnoses, medications, or treatment records. Zero PHI stored outside your environment. 

## Steps 
1. Run `VERIFY_COLUMNS.sql`, send results 
2. Provide read-only connection string 
3. SentinelEHR implementation team updates `ingestion_pipeline_v2.py` connection (1 line change) 
4. Run `setup_db.py` to create monitoring tables 
5. Run `ingestion_pipeline_v2.py` for initial load 
6. Review `baseline_calculator` output with IT team 
7. Dashboard available on your internal server 

## Estimated IT Time 
Initial setup: 4-6 hours  
Ongoing maintenance: None (automated nightly) 
