# SentinelEHR Mock Clarity Generator v2

This module simulates a real Epic Clarity database for testing the SentinelEHR ingestion pipeline.

## Schema Overview

The tables and columns are designed to match real Epic naming conventions as closely as possible.

### Table: ACCESS_LOG (The Main Audit Table)
| Column | Type | Source | Description |
|--------|------|--------|-------------|
| ACCESS_LOG_ID | BIGINT | CONFIRMED | Primary key for the audit event. |
| USER_ID | INTEGER | CONFIRMED | Foreign key to CLARITY_EMP. |
| PAT_ID | INTEGER | CONFIRMED | Foreign key to PATIENT. |
| ACTION_C | INTEGER | CONFIRMED | Epic action code (e.g., 3=Open Chart, 7=Search). |
| ACCESS_INSTANT | FLOAT | RECONSTRUCTED | Epic datetime format (days since 1840 + time fraction). |
| DEP_ID | INTEGER | RECONSTRUCTED | Department where access occurred. |
| SESSION_KEY | TEXT | RECONSTRUCTED | Groups events within a single user login. |
| LINE | INTEGER | RECONSTRUCTED | Line number for multi-row event logging. |

### Table: CLARITY_EMP (Employees)
- `USER_ID`, `USER_NAME`, `PROV_TYPE` are standard Epic fields.
- `PROV_START_DATE` is stored as an Epic date integer.

### Table: PATIENT (Patient Data)
- `PAT_ID` and `PAT_MRN_ID` follow standard Epic conventions.
- `BIRTH_DATE` is an Epic date integer.

## Epic Date Handling

Clarity stores dates as integers representing days since **December 31, 1840**.
Datetimes are stored as floats where the integer part is the date and the decimal part is the fraction of the day.

Example: `67234.5` represents noon on day `67234`.

The `date_utils.py` module handles these conversions for our pipeline.

## Logical Sessions vs. Database Rows

In real Clarity, a single logical "access" (like opening a chart and viewing labs) generates multiple rows:
1. `LINE 1`: ACTION_C = 3 (Open Chart)
2. `LINE 2`: ACTION_C = 1 (In Chart)
3. `LINE 3`: ACTION_C = 10 (View Result)

Our generator accurately models this multi-row behavior. Our pipeline must aggregate these per `SESSION_KEY` and `PAT_ID`.

## Excluding Search Hits

Action code `7` (Search) means a patient's name appeared in a search result list, but their chart was **not** opened. These events are excluded from our "access" counts to avoid false positives in detection.

## How to Connect to Real Clarity

1. Change the connection string in your ingestion pipeline.
2. Run `VERIFY_COLUMNS.sql` (to be developed) to map any local variations in column names.
3. Check the `clarity_table_verification_required` list in `attacker_manifest.json` for known variations.
