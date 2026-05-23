-- ============================================================
-- SENTINELEHR CLARITY SIMULATION SCHEMA v2
-- Table names: CONFIRMED from public Epic documentation
-- Column names: CONFIRMED where marked, RECONSTRUCTED elsewhere
-- ============================================================

-- ZC_ACS_ACTION: Action code lookup table
-- CONFIRMED: ZC_ prefix convention for code tables
-- CONFIRMED: _C suffix for code columns
CREATE TABLE IF NOT EXISTS ZC_ACS_ACTION (
  ACTION_C INTEGER PRIMARY KEY, -- CONFIRMED convention
  NAME TEXT NOT NULL,           -- CONFIRMED exists
  ABBR TEXT,                    -- RECONSTRUCTED
  INTERNAL_ID TEXT              -- RECONSTRUCTED
);

-- CLARITY_EMP: Employee/user reference table
-- CONFIRMED: table name used in multiple public queries
CREATE TABLE IF NOT EXISTS CLARITY_EMP (
  USER_ID INTEGER PRIMARY KEY,   -- CONFIRMED: _ID convention
  USER_NAME TEXT NOT NULL,       -- CONFIRMED: standard field
  PROV_TYPE TEXT,                -- CONFIRMED: provider type
  DEP_ID INTEGER,                -- RECONSTRUCTED: dept FK
  -- VERIFY AGAINST REAL CLARITY BEFORE PRODUCTION
  EMP_STATUS_C INTEGER DEFAULT 1, -- RECONSTRUCTED: active=1
  PROV_START_DATE FLOAT,         -- RECONSTRUCTED: Epic date
  -- SentinelEHR additions (NOT real Clarity columns):
  _ROLE TEXT,                    -- role label for simulation
  _SHIFT_START INTEGER,          -- shift start hour
  _SHIFT_END INTEGER,            -- shift end hour
  _IS_FLOAT INTEGER DEFAULT 0    -- float nurse flag
);

-- PATIENT: Patient reference table
-- CONFIRMED: table name, PAT_ID as primary key
CREATE TABLE IF NOT EXISTS PATIENT (
  PAT_ID INTEGER PRIMARY KEY,    -- CONFIRMED
  PAT_MRN_ID TEXT,               -- CONFIRMED: MRN field
  PAT_FIRST_NAME TEXT,           -- CONFIRMED
  PAT_LAST_NAME TEXT,            -- CONFIRMED
  BIRTH_DATE FLOAT,              -- CONFIRMED: Epic date format
  SEX_C INTEGER,                 -- CONFIRMED: _C convention
  -- VERIFY AGAINST REAL CLARITY BEFORE PRODUCTION
  HOME_DEP_ID INTEGER,           -- RECONSTRUCTED
  -- SentinelEHR additions:
  _IS_VIP INTEGER DEFAULT 0,     -- VIP flag for simulation
  _IS_SENSITIVE INTEGER DEFAULT 0 -- HIV/behavioral health flag
);

-- CLARITY_DEP: Department reference table
-- CONFIRMED: table name used in public Epic queries
CREATE TABLE IF NOT EXISTS CLARITY_DEP (
  DEP_ID INTEGER PRIMARY KEY,    -- CONFIRMED: _ID convention
  DEPARTMENT_NAME TEXT NOT NULL, -- CONFIRMED
  REV_LOC_ID INTEGER,            -- RECONSTRUCTED: location FK
  -- VERIFY AGAINST REAL CLARITY BEFORE PRODUCTION
  SPECIALTY_DEP_C INTEGER        -- RECONSTRUCTED
);

-- PAT_ENC: Patient encounter table (care relationship)
-- CONFIRMED: table name, PAT_ENC_CSN_ID as primary key
CREATE TABLE IF NOT EXISTS PAT_ENC (
  PAT_ENC_CSN_ID BIGINT PRIMARY KEY, -- CONFIRMED: CSN = contact
  PAT_ID INTEGER NOT NULL,            -- CONFIRMED: FK to PATIENT
  PROV_ID INTEGER,                    -- CONFIRMED: attending provider
  DEP_ID INTEGER,                    -- CONFIRMED: encounter dept
  ENC_TYPE_C INTEGER,                -- CONFIRMED: _C convention
  CONTACT_DATE FLOAT,                -- CONFIRMED: Epic date format
  -- VERIFY AGAINST REAL CLARITY BEFORE PRODUCTION
  ENC_CLOSED_YN TEXT DEFAULT 'N',    -- CONFIRMED: _YN convention
  VISIT_PROV_ID INTEGER              -- RECONSTRUCTED: visit provider
);

-- ACCESS_LOG: Main audit event table
-- CONFIRMED: table name from multiple research papers
-- COLUMN NAMES: reconstructed from Epic naming conventions
-- # VERIFY ALL COLUMNS AGAINST REAL CLARITY BEFORE PRODUCTION
CREATE TABLE IF NOT EXISTS ACCESS_LOG (
  ACCESS_LOG_ID BIGINT PRIMARY KEY,  -- CONFIRMED: _ID convention
  USER_ID INTEGER NOT NULL,           -- CONFIRMED: FK to CLARITY_EMP
  PAT_ID INTEGER,                     -- CONFIRMED: FK to PATIENT
  ACTION_C INTEGER,                   -- CONFIRMED: _C convention
  ACCESS_INSTANT FLOAT NOT NULL,      -- RECONSTRUCTED: Epic datetime
  DEP_ID INTEGER,                     -- RECONSTRUCTED: dept FK
  WORKSTATION_ID TEXT,                -- RECONSTRUCTED
  SESSION_KEY TEXT,                   -- RECONSTRUCTED: session grouping
  LINE INTEGER DEFAULT 1,             -- RECONSTRUCTED: multi-row line
  -- Real Clarity may use: LOG_DTTM, EVENT_INSTANT, ACCESS_TIME
  -- VERIFY column name before production connection
  -- SentinelEHR additions (NOT real Clarity columns):
  _ACCESS_TIME_ISO TEXT,              -- human-readable ISO for our pipeline
  _IS_SEARCH_ONLY INTEGER DEFAULT 0,  -- 1 = search hit, not chart open
  _IS_CONTINUATION INTEGER DEFAULT 0, -- 1 = sub-event of prior open
  _SESSION_EVENT_N INTEGER DEFAULT 1, -- event number within session
  ANOMALY_TYPE TEXT                   -- SentinelEHR addition: anomaly label
);
