import pandas as pd
import numpy as np
import random
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from clarity_config import *
from date_utils import to_epic_date, to_epic_datetime

# ── SETUP ───────────────────────────────────────────────────
random.seed(SEED)
np.random.seed(SEED)
OUTPUT_DIR = Path("mock_clarity_v2/output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── STEP 1: ZC_ACS_ACTION ───────────────────────────────────
print("Generating ZC_ACS_ACTION...")
actions_df = pd.DataFrame([
    {
        "ACTION_C": code,
        "NAME": data["NAME"],
        "ABBR": data["ABBR"],
        "INTERNAL_ID": f"ACT_{code:03d}"
    }
    for code, data in ACTION_CODES.items()
])
actions_df.to_csv(OUTPUT_DIR / "ZC_ACS_ACTION.csv", index=False)

# ── STEP 2: CLARITY_DEP ─────────────────────────────────────
print("Generating CLARITY_DEP...")
dep_names = [
    "Internal Medicine", "Pediatrics", "OB/GYN",
    "Emergency", "Oncology", "Behavioral Health",
    "Cardiology", "Orthopedics", "Billing/Admin", "Float Pool"
]
deps_df = pd.DataFrame([
    {
        "DEP_ID": i + 1,
        "DEPARTMENT_NAME": name,
        "REV_LOC_ID": 100 + (i // 3),
        "SPECIALTY_DEP_C": random.randint(1, 20)
    }
    for i, name in enumerate(dep_names)
])
deps_df.to_csv(OUTPUT_DIR / "CLARITY_DEP.csv", index=False)

# ── STEP 3: CLARITY_EMP ─────────────────────────────────────
print("Generating CLARITY_EMP...")
emp_records = []
user_id_counter = 10001
role_map = {
    "Physician": "Physician",
    "Nurse": "Registered Nurse",
    "Float_Nurse": "Registered Nurse",
    "MA": "Medical Assistant",
    "Scheduler": "Scheduling",
    "Billing": "Billing"
}

for role_name, config in ROLES.items():
    for _ in range(config["count"]):
        # DEP_ID logic
        if role_name == "Float_Nurse":
            dep_id = 10
        elif role_name == "Billing":
            dep_id = 9
        else:
            dep_id = random.randint(1, 8)
            
        start_date = START_DATE - timedelta(days=random.randint(365, 365*5))
        
        emp_records.append({
            "USER_ID": user_id_counter,
            "USER_NAME": f"USER_{user_id_counter}",
            "PROV_TYPE": role_map[role_name],
            "DEP_ID": dep_id,
            "EMP_STATUS_C": 1,
            "PROV_START_DATE": to_epic_date(start_date),
            "_ROLE": role_name,
            "_SHIFT_START": config["shift_start"],
            "_SHIFT_END": config["shift_end"],
            "_IS_FLOAT": 1 if role_name == "Float_Nurse" else 0
        })
        user_id_counter += 1

employees_df = pd.DataFrame(emp_records)
employees_df.to_csv(OUTPUT_DIR / "CLARITY_EMP.csv", index=False)

# ── STEP 4: PATIENT ─────────────────────────────────────────
print("Generating PATIENT...")
first_names = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "William", "Elizabeth", 
               "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen",
               "Charles", "Nancy", "Daniel", "Lisa", "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra",
               "Donald", "Ashley", "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
               "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa", "Timothy", "Deborah"]
last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
              "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
              "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
              "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
              "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts"]

patient_records = []
for i in range(NUM_PATIENTS):
    pat_id = 200001 + i
    birth_date = START_DATE - timedelta(days=random.randint(365, 365*90))
    sex_c = random.choices([1, 2, 3], weights=[48, 48, 4])[0]
    
    patient_records.append({
        "PAT_ID": pat_id,
        "PAT_MRN_ID": f"MRN{pat_id:06d}",
        "PAT_FIRST_NAME": random.choice(first_names),
        "PAT_LAST_NAME": random.choice(last_names),
        "BIRTH_DATE": to_epic_date(birth_date),
        "SEX_C": sex_c,
        "HOME_DEP_ID": random.randint(1, 8),
        "_IS_VIP": 1 if random.random() < 0.02 else 0,
        "_IS_SENSITIVE": 1 if random.random() < 0.015 else 0 # 1.5% of patients have sensitive records (HIV/behavioral health). Real Epic environments have stricter access controls on these records.
    })

patients_df = pd.DataFrame(patient_records)
patients_df.to_csv(OUTPUT_DIR / "PATIENT.csv", index=False)

vip_set = set(patients_df[patients_df["_IS_VIP"] == 1]["PAT_ID"])
sensitive_set = set(patients_df[patients_df["_IS_SENSITIVE"] == 1]["PAT_ID"])

# ── STEP 5: PAT_ENC ─────────────────────────────────────────
print("Generating PAT_ENC (Panels)...")
enc_records = []
csn_counter = 9000001
panel_set = {}

for _, emp in employees_df.iterrows():
    role_config = ROLES[emp["_ROLE"]]
    panel_size = random.randint(*role_config["panel_size"])
    # Sample patients for the panel
    assigned_patients = random.sample(list(patients_df["PAT_ID"]), panel_size)
    panel_set[emp["USER_ID"]] = set(assigned_patients)
    
    for pat_id in assigned_patients:
        contact_date = START_DATE - timedelta(days=random.randint(1, 730))
        enc_records.append({
            "PAT_ENC_CSN_ID": csn_counter,
            "PAT_ID": pat_id,
            "PROV_ID": emp["USER_ID"],
            "DEP_ID": emp["DEP_ID"],
            "ENC_TYPE_C": random.choice([1, 2, 3]),
            "CONTACT_DATE": to_epic_date(contact_date),
            "ENC_CLOSED_YN": "Y" if random.random() < 0.8 else "N",
            "VISIT_PROV_ID": emp["USER_ID"]
        })
        csn_counter += 1

enc_df = pd.DataFrame(enc_records)
enc_df.to_csv(OUTPUT_DIR / "PAT_ENC.csv", index=False)

# ── STEP 6: ACCESS_LOG ──────────────────────────────────────
print("Generating ACCESS_LOG (this may take a minute)...")
access_log_records = []
access_id_counter = 50000001

# Attacker profiles
attacker_indices = random.sample(range(len(employees_df)), 4)
attackers = []
for i, idx in enumerate(attacker_indices):
    emp = employees_df.iloc[idx]
    anomaly_type = ["VIP_SNOOP", "BULK_EXPORT", "OFF_HOURS", "SENSITIVE_SNOOP"][i]
    attackers.append({
        "USER_ID": int(emp["USER_ID"]),
        "ROLE": emp["_ROLE"],
        "ANOMALY_TYPE": anomaly_type,
        "DEPT": int(emp["DEP_ID"])
    })

attacker_ids = {a["USER_ID"]: a["ANOMALY_TYPE"] for a in attackers}

for day_offset in range(NUM_DAYS):
    current_date = START_DATE + timedelta(days=day_offset)
    is_weekend = current_date.weekday() >= 5
    
    if is_weekend:
        num_events = random.randint(800, 1500)
    else:
        num_events = random.randint(4000, 7000)
        
    print(f"  Day {day_offset+1}/{NUM_DAYS}: {current_date.date()} ({num_events} events)")
    
    # Session tracking for grouping
    session_counts = {} # (user_id, date) -> counter

    for _ in range(num_events):
        emp = employees_df.sample(1).iloc[0]
        user_id = emp["USER_ID"]
        
        # Determine if Search or Open
        is_search = random.random() < 0.15
        
        # Determine patient
        if is_search:
            pat_id = random.choice(list(patients_df["PAT_ID"]))
        else:
            if random.random() < 0.85:
                # From panel
                pat_id = random.choice(list(panel_set[user_id]))
            else:
                # Outside panel
                pat_id = random.choice(list(patients_df["PAT_ID"]))
                
        # Determine timestamp
        hour = random.randint(0, 23)
        # Shift logic
        if random.random() > ROLES[emp["_ROLE"]]["off_hours_prob"]:
            hour = random.randint(emp["_SHIFT_START"], emp["_SHIFT_END"] - 1)
        
        timestamp = current_date.replace(hour=hour, 
                                       minute=random.randint(0, 59), 
                                       second=random.randint(0, 59))
        
        # Session Key
        session_date_str = timestamp.strftime("%Y%m%d")
        session_key_prefix = f"S{user_id}-{session_date_str}"
        session_seq = session_counts.get((user_id, session_date_str), 0)
        if random.random() < 0.1: # 10% chance to start new session
            session_seq += 1
            session_counts[(user_id, session_date_str)] = session_seq
        session_key = f"{session_key_prefix}-{session_seq:02d}"

        if is_search:
            # Single search row
            access_log_records.append({
                "ACCESS_LOG_ID": access_id_counter,
                "USER_ID": user_id,
                "PAT_ID": pat_id,
                "ACTION_C": SEARCH_ACTION_C,
                "ACCESS_INSTANT": to_epic_datetime(timestamp),
                "DEP_ID": emp["DEP_ID"],
                "WORKSTATION_ID": f"WS-{random.randint(100, 999)}",
                "SESSION_KEY": session_key,
                "LINE": 1,
                "_ACCESS_TIME_ISO": timestamp.isoformat(),
                "_IS_SEARCH_ONLY": 1,
                "_IS_CONTINUATION": 0,
                "_SESSION_EVENT_N": 1,
                "ANOMALY_TYPE": None
            })
            access_id_counter += 1
        else:
            # Multi-row session (1-3 rows)
            primary_action = random.choices(
                list(ROLES[emp["_ROLE"]]["action_weights"].keys()),
                weights=list(ROLES[emp["_ROLE"]]["action_weights"].values())
            )[0]
            if primary_action == SEARCH_ACTION_C: primary_action = OPEN_ACTION_C
            
            # Row 1: Primary
            access_log_records.append({
                "ACCESS_LOG_ID": access_id_counter,
                "USER_ID": user_id,
                "PAT_ID": pat_id,
                "ACTION_C": primary_action,
                "ACCESS_INSTANT": to_epic_datetime(timestamp),
                "DEP_ID": emp["DEP_ID"],
                "WORKSTATION_ID": f"WS-{random.randint(100, 999)}",
                "SESSION_KEY": session_key,
                "LINE": 1,
                "_ACCESS_TIME_ISO": timestamp.isoformat(),
                "_IS_SEARCH_ONLY": 0,
                "_IS_CONTINUATION": 0,
                "_SESSION_EVENT_N": 1,
                "ANOMALY_TYPE": None
            })
            access_id_counter += 1
            
            # Row 2: In Chart (+30s)
            ts2 = timestamp + timedelta(seconds=30)
            access_log_records.append({
                "ACCESS_LOG_ID": access_id_counter,
                "USER_ID": user_id,
                "PAT_ID": pat_id,
                "ACTION_C": 1, # In Chart
                "ACCESS_INSTANT": to_epic_datetime(ts2),
                "DEP_ID": emp["DEP_ID"],
                "WORKSTATION_ID": f"WS-{random.randint(100, 999)}",
                "SESSION_KEY": session_key,
                "LINE": 2,
                "_ACCESS_TIME_ISO": ts2.isoformat(),
                "_IS_SEARCH_ONLY": 0,
                "_IS_CONTINUATION": 1,
                "_SESSION_EVENT_N": 1,
                "ANOMALY_TYPE": None
            })
            access_id_counter += 1
            
            # Row 3: Optional (+90s)
            if random.random() < 0.6:
                ts3 = timestamp + timedelta(seconds=90)
                access_log_records.append({
                    "ACCESS_LOG_ID": access_id_counter,
                    "USER_ID": user_id,
                    "PAT_ID": pat_id,
                    "ACTION_C": random.choice([8, 10]), # Edit Note or View Result
                    "ACCESS_INSTANT": to_epic_datetime(ts3),
                    "DEP_ID": emp["DEP_ID"],
                    "WORKSTATION_ID": f"WS-{random.randint(100, 999)}",
                    "SESSION_KEY": session_key,
                    "LINE": 3,
                    "_ACCESS_TIME_ISO": ts3.isoformat(),
                    "_IS_SEARCH_ONLY": 0,
                    "_IS_CONTINUATION": 1,
                    "_SESSION_EVENT_N": 1,
                    "ANOMALY_TYPE": None
                })
                access_id_counter += 1

    # ── Attacker Injection (Weekdays only, after Day 5) ────────
    if not is_weekend and day_offset >= 5:
        for attacker in attackers:
            uid = attacker["USER_ID"]
            atype = attacker["ANOMALY_TYPE"]
            emp_row = employees_df[employees_df["USER_ID"] == uid].iloc[0]
            
            if atype == "VIP_SNOOP":
                num_attacks = random.randint(3, 8)
                target_pats = random.sample(list(vip_set), min(num_attacks, len(vip_set)))
                for p_id in target_pats:
                    # Session of 2 rows
                    ts = current_date.replace(hour=random.randint(9, 16), minute=random.randint(0, 59))
                    for line, action, offset in [(1, 3, 0), (2, 1, 30)]:
                        t_attack = ts + timedelta(seconds=offset)
                        access_log_records.append({
                            "ACCESS_LOG_ID": access_id_counter,
                            "USER_ID": uid,
                            "PAT_ID": p_id,
                            "ACTION_C": action,
                            "ACCESS_INSTANT": to_epic_datetime(t_attack),
                            "DEP_ID": emp_row["DEP_ID"],
                            "WORKSTATION_ID": "WS-ATTACK",
                            "SESSION_KEY": f"S{uid}-ATTACK-{day_offset}",
                            "LINE": line,
                            "_ACCESS_TIME_ISO": t_attack.isoformat(),
                            "_IS_SEARCH_ONLY": 0,
                            "_IS_CONTINUATION": 1 if line > 1 else 0,
                            "_SESSION_EVENT_N": 99,
                            "ANOMALY_TYPE": atype
                        })
                        access_id_counter += 1
            
            elif atype == "BULK_EXPORT":
                num_attacks = random.randint(40, 70)
                target_pats = random.sample(list(patients_df["PAT_ID"]), num_attacks)
                for p_id in target_pats:
                    ts = current_date.replace(hour=random.randint(14, 15), minute=random.randint(0, 59))
                    access_log_records.append({
                        "ACCESS_LOG_ID": access_id_counter,
                        "USER_ID": uid,
                        "PAT_ID": p_id,
                        "ACTION_C": 5, # Export
                        "ACCESS_INSTANT": to_epic_datetime(ts),
                        "DEP_ID": emp_row["DEP_ID"],
                        "WORKSTATION_ID": "WS-EXPORT",
                        "SESSION_KEY": f"S{uid}-BULK-{day_offset}",
                        "LINE": 1,
                        "_ACCESS_TIME_ISO": ts.isoformat(),
                        "_IS_SEARCH_ONLY": 0,
                        "_IS_CONTINUATION": 0,
                        "_SESSION_EVENT_N": 99,
                        "ANOMALY_TYPE": atype
                    })
                    access_id_counter += 1
            
            elif atype == "OFF_HOURS":
                num_attacks = random.randint(10, 20)
                target_pats = random.sample(list(patients_df["PAT_ID"]), num_attacks)
                for p_id in target_pats:
                    ts = current_date.replace(hour=random.randint(1, 3), minute=random.randint(0, 59))
                    for line, action, offset in [(1, 3, 0), (2, 1, 30)]:
                        t_attack = ts + timedelta(seconds=offset)
                        access_log_records.append({
                            "ACCESS_LOG_ID": access_id_counter,
                            "USER_ID": uid,
                            "PAT_ID": p_id,
                            "ACTION_C": action,
                            "ACCESS_INSTANT": to_epic_datetime(t_attack),
                            "DEP_ID": emp_row["DEP_ID"],
                            "WORKSTATION_ID": "WS-NIGHT",
                            "SESSION_KEY": f"S{uid}-OFF-{day_offset}",
                            "LINE": line,
                            "_ACCESS_TIME_ISO": t_attack.isoformat(),
                            "_IS_SEARCH_ONLY": 0,
                            "_IS_CONTINUATION": 1 if line > 1 else 0,
                            "_SESSION_EVENT_N": 99,
                            "ANOMALY_TYPE": atype
                        })
                        access_id_counter += 1
            
            elif atype == "SENSITIVE_SNOOP":
                num_attacks = random.randint(5, 10)
                target_pats = random.sample(list(sensitive_set), min(num_attacks, len(sensitive_set)))
                for p_id in target_pats:
                    ts = current_date.replace(hour=random.randint(9, 16), minute=random.randint(0, 59))
                    for line, action, offset in [(1, 3, 0), (2, 1, 30)]:
                        t_attack = ts + timedelta(seconds=offset)
                        access_log_records.append({
                            "ACCESS_LOG_ID": access_id_counter,
                            "USER_ID": uid,
                            "PAT_ID": p_id,
                            "ACTION_C": action,
                            "ACCESS_INSTANT": to_epic_datetime(t_attack),
                            "DEP_ID": emp_row["DEP_ID"],
                            "WORKSTATION_ID": "WS-SENSITIVE",
                            "SESSION_KEY": f"S{uid}-SENS-{day_offset}",
                            "LINE": line,
                            "_ACCESS_TIME_ISO": t_attack.isoformat(),
                            "_IS_SEARCH_ONLY": 0,
                            "_IS_CONTINUATION": 1 if line > 1 else 0,
                            "_SESSION_EVENT_N": 99,
                            "ANOMALY_TYPE": atype
                        })
                        access_id_counter += 1

print("Finalizing ACCESS_LOG...")
access_log_df = pd.DataFrame(access_log_records)
access_log_df.to_csv(OUTPUT_DIR / "ACCESS_LOG.csv", index=False)

# ── STEP 7: manifest.json ───────────────────────────────────
manifest = {
    "attackers": attackers,
    "generated_at": datetime.now().isoformat(),
    "schema_version": "v2",
    "clarity_table_verification_required": [
        "ACCESS_LOG.ACCESS_INSTANT column name",
        "ACCESS_LOG.DEP_ID column name",
        "ACCESS_LOG.SESSION_KEY column name",
        "CLARITY_EMP.EMP_STATUS_C column name",
        "PATIENT.HOME_DEP_ID column name"
    ]
}
with open(OUTPUT_DIR / "attacker_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

# ── STEP 8: Summary ─────────────────────────────────────────
print("\n" + "="*50)
print("SENTINELEHR CLARITY SIMULATION v2 COMPLETE")
print("="*50)
print(f"Total ACCESS_LOG rows: {len(access_log_df):,}")
print(f"  Search-only events:  {(access_log_df['_IS_SEARCH_ONLY']==1).sum():,}")
print(f"  Continuation rows:   {(access_log_df['_IS_CONTINUATION']==1).sum():,}")
print(f"  Primary open events: {((access_log_df['_IS_SEARCH_ONLY']==0) & (access_log_df['_IS_CONTINUATION']==0)).sum():,}")
print(f"Normal vs Anomalous:   {(access_log_df['ANOMALY_TYPE'].isna()).sum():,} vs {(access_log_df['ANOMALY_TYPE'].notna()).sum():,}")
print(f"VIP Patients:          {len(vip_set)}")
print(f"Sensitive Patients:    {len(sensitive_set)}")
print("-" * 50)
for a in attackers:
    print(f"Attacker {a['USER_ID']} ({a['ROLE']}): {a['ANOMALY_TYPE']}")
print("-" * 50)
print(f"Output saved to: {OUTPUT_DIR}")
