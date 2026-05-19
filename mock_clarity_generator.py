import pandas as pd
import numpy as np
import random
import os
from datetime import datetime, timedelta

# ─── CONFIG CONSTANTS ───────────────────────────────────────
SEED = 42
NUM_DAYS = 90
START_DATE = datetime(2026, 1, 1)
NUM_EMPLOYEES = 80
NUM_PATIENTS = 5000

# Set seeds
random.seed(SEED)
np.random.seed(SEED)

# Output directory
OUTPUT_DIR = "./mock_data/"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# ─── ROLE CONFIGURATIONS ────────────────────────────────────
ROLE_CONFIGS = {
    "Physician":   {"panel_range": (150, 300), "hours": (7, 17),  "off_hours_prob": 0.08, "weights": [0.60, 0.20, 0.08, 0.05, 0.04, 0.03]},
    "Nurse":       {"panel_range": (80, 200),  "hours": (7, 19),  "off_hours_prob": 0.10, "weights": [0.65, 0.15, 0.08, 0.05, 0.04, 0.03]},
    "Float_Nurse": {"panel_range": (20, 60),   "hours": (6, 22),  "off_hours_prob": 0.15, "weights": [0.65, 0.15, 0.08, 0.05, 0.04, 0.03]},
    "MA":          {"panel_range": (40, 120),  "hours": (8, 17),  "off_hours_prob": 0.05, "weights": [0.70, 0.10, 0.10, 0.04, 0.02, 0.04]},
    "Scheduler":   {"panel_range": (10, 40),   "hours": (8, 17),  "off_hours_prob": 0.03, "weights": [0.80, 0.05, 0.05, 0.03, 0.01, 0.06]},
    "Billing":     {"panel_range": (5, 20),    "hours": (8, 17),  "off_hours_prob": 0.02, "weights": [0.75, 0.05, 0.05, 0.10, 0.01, 0.04]},
}

# ─── EMPLOYEES TABLE ────────────────────────────────────────
roles = list(ROLE_CONFIGS.keys())
employees_data = []
emp_id_start = 1001

for i in range(NUM_EMPLOYEES):
    role = roles[i % len(roles)]
    config = ROLE_CONFIGS[role]
    emp_id = emp_id_start + i
    dept_id = random.randint(1, 10)
    
    employees_data.append({
        "EMP_ID": emp_id,
        "ROLE": role,
        "DEPT_ID": dept_id,
        "NORMAL_START_HOUR": config["hours"][0],
        "NORMAL_END_HOUR": config["hours"][1],
        "IS_FLOAT": True if role == "Float_Nurse" else False,
        "OFF_HOURS_PROB": config["off_hours_prob"],
        "ACTION_WEIGHTS": config["weights"]
    })

df_employees = pd.DataFrame(employees_data)
# Drop internal columns for CSV
df_employees_csv = df_employees.drop(columns=["OFF_HOURS_PROB", "ACTION_WEIGHTS"])
df_employees_csv.to_csv(os.path.join(OUTPUT_DIR, "employees.csv"), index=False)

# ─── PATIENTS TABLE ─────────────────────────────────────────
patients_data = []
pat_id_start = 200001
for i in range(NUM_PATIENTS):
    pat_id = pat_id_start + i
    is_vip = random.random() < 0.02
    primary_dept_id = random.randint(1, 10)
    patients_data.append({
        "PAT_ID": pat_id,
        "IS_VIP": is_vip,
        "PRIMARY_DEPT_ID": primary_dept_id
    })

df_patients = pd.DataFrame(patients_data)
df_patients.to_csv(os.path.join(OUTPUT_DIR, "patients.csv"), index=False)

# ─── PATIENT_PANELS TABLE ───────────────────────────────────
panel_entries = []
panel_lookup = {} # {EMP_ID: set(PAT_IDs)}
patient_ids = df_patients["PAT_ID"].tolist()
vip_set = set(df_patients[df_patients["IS_VIP"]]["PAT_ID"])

for emp in employees_data:
    role = emp["ROLE"]
    panel_range = ROLE_CONFIGS[role]["panel_range"]
    panel_size = random.randint(panel_range[0], panel_range[1])
    
    # Randomly select patients for this employee
    emp_panel = set(random.sample(patient_ids, panel_size))
    panel_lookup[emp["EMP_ID"]] = emp_panel
    
    for pat_id in emp_panel:
        panel_entries.append({"EMP_ID": emp["EMP_ID"], "PAT_ID": pat_id})

df_panels = pd.DataFrame(panel_entries)
df_panels.to_csv(os.path.join(OUTPUT_DIR, "patient_panels.csv"), index=False)

# ─── PRE-BUILD LOOKUPS FOR AUDIT LOG GENERATION ──────────────
emp_list = employees_data # List of dicts
# Pre-calculate role weights and choices for faster access
action_choices = [1, 2, 3, 4, 5, 6]

# ─── CLARITY_AUDIT TABLE ────────────────────────────────────
audit_events = []
audit_id_counter = 1

# Randomly pick 4 employees as attackers
attacker_indices = random.sample(range(NUM_EMPLOYEES), 4)
attackers = [emp_list[i] for i in attacker_indices]
attacker_ids = [a["EMP_ID"] for a in attackers]

# Map attackers to profiles
attacker_profiles = {
    attacker_ids[0]: "VIP_SNOOP",
    attacker_ids[1]: "BULK_EXPORT",
    attacker_ids[2]: "OFF_HOURS",
    attacker_ids[3]: "CROSS_DEPT"
}

# Manifest for ground truth
with open(os.path.join(OUTPUT_DIR, "attacker_manifest.txt"), "w") as f:
    for a in attackers:
        f.write(f"EMP_ID: {a['EMP_ID']}, ROLE: {a['ROLE']}, ANOMALY: {attacker_profiles[a['EMP_ID']]}\n")

print(f"Generating data for {NUM_DAYS} days...")

for day_offset in range(NUM_DAYS):
    current_date = START_DATE + timedelta(days=day_offset)
    is_weekend = current_date.weekday() >= 5
    
    if is_weekend:
        num_events = random.randint(800, 1500)
    else:
        num_events = random.randint(4000, 7000)
        
    # --- Normal Events ---
    for _ in range(num_events):
        emp = random.choice(emp_list)
        
        # 85% chance patient comes from their own panel, 15% chance random patient
        if random.random() < 0.85:
            pat_id = random.choice(list(panel_lookup[emp["EMP_ID"]]))
        else:
            pat_id = random.choice(patient_ids)
            
        # Timestamp generation
        if random.random() < emp["OFF_HOURS_PROB"]:
            # Pick from (0-6) or (20-23)
            off_hours = [0, 1, 2, 3, 4, 5, 6, 20, 21, 22, 23]
            hour = random.choice(off_hours)
        else:
            # Pick from normal shift
            hour = random.randint(emp["NORMAL_START_HOUR"], emp["NORMAL_END_HOUR"])
        
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        dt = current_date.replace(hour=hour, minute=minute, second=second)
        
        action_c = random.choices(action_choices, weights=emp["ACTION_WEIGHTS"])[0]
        
        in_panel = pat_id in panel_lookup[emp["EMP_ID"]]
        is_vip = pat_id in vip_set
        
        audit_events.append({
            "AUDIT_ID": audit_id_counter,
            "EMP_ID": emp["EMP_ID"],
            "PAT_ID": pat_id,
            "ACTION_C": action_c,
            "ACTION_DATETIME": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "DEPT_ID": emp["DEPT_ID"],
            "WORKSTATION_ID": f"PC-{random.randint(1, 99):02d}",
            "SESSION_ID": f"SESS-{random.randint(10000, 99999)}",
            "IN_PANEL": in_panel,
            "IS_VIP_ACCESS": is_vip,
            "JUSTIFICATION": "Emergency override" if action_c == 5 else "",
            "ANOMALY_TYPE": None
        })
        audit_id_counter += 1

    # --- Malicious Events (Weekdays, starting day 5) ---
    if not is_weekend and day_offset >= 4:
        # ATTACKER_1 — VIP_SNOOP
        a1 = attackers[0]
        num_a1 = random.randint(3, 8)
        non_panel_vips = list(vip_set - panel_lookup[a1["EMP_ID"]])
        if non_panel_vips:
            for _ in range(num_a1):
                pat_id = random.choice(non_panel_vips)
                hour = random.randint(9, 16)
                dt = current_date.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))
                audit_events.append({
                    "AUDIT_ID": audit_id_counter,
                    "EMP_ID": a1["EMP_ID"],
                    "PAT_ID": pat_id,
                    "ACTION_C": 1, # View
                    "ACTION_DATETIME": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "DEPT_ID": a1["DEPT_ID"],
                    "WORKSTATION_ID": f"PC-{random.randint(1, 99):02d}",
                    "SESSION_ID": f"SESS-{random.randint(10000, 99999)}",
                    "IN_PANEL": False,
                    "IS_VIP_ACCESS": True,
                    "JUSTIFICATION": "",
                    "ANOMALY_TYPE": "VIP_SNOOP"
                })
                audit_id_counter += 1

        # ATTACKER_2 — BULK_EXPORT
        a2 = attackers[1]
        num_a2 = random.randint(40, 70)
        start_hour = 14
        for _ in range(num_a2):
            pat_id = random.choice(patient_ids)
            # 2-hour window starting at 14:00
            hour = random.randint(14, 15)
            dt = current_date.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))
            audit_events.append({
                "AUDIT_ID": audit_id_counter,
                "EMP_ID": a2["EMP_ID"],
                "PAT_ID": pat_id,
                "ACTION_C": 4, # Export
                "ACTION_DATETIME": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "DEPT_ID": a2["DEPT_ID"],
                "WORKSTATION_ID": f"PC-{random.randint(1, 99):02d}",
                "SESSION_ID": f"SESS-{random.randint(10000, 99999)}",
                "IN_PANEL": pat_id in panel_lookup[a2["EMP_ID"]],
                "IS_VIP_ACCESS": pat_id in vip_set,
                "JUSTIFICATION": "",
                "ANOMALY_TYPE": "BULK_EXPORT"
            })
            audit_id_counter += 1

        # ATTACKER_3 — OFF_HOURS
        a3 = attackers[2]
        num_a3 = random.randint(10, 20)
        for _ in range(num_a3):
            pat_id = random.choice(patient_ids)
            hour = random.randint(1, 3) # 01:00-04:00 (end hour exclusive in randint or just pick 1,2,3)
            dt = current_date.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))
            action_c = random.choice(action_choices)
            audit_events.append({
                "AUDIT_ID": audit_id_counter,
                "EMP_ID": a3["EMP_ID"],
                "PAT_ID": pat_id,
                "ACTION_C": action_c,
                "ACTION_DATETIME": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "DEPT_ID": a3["DEPT_ID"],
                "WORKSTATION_ID": f"PC-{random.randint(1, 99):02d}",
                "SESSION_ID": f"SESS-{random.randint(10000, 99999)}",
                "IN_PANEL": pat_id in panel_lookup[a3["EMP_ID"]],
                "IS_VIP_ACCESS": pat_id in vip_set,
                "JUSTIFICATION": "Emergency override" if action_c == 5 else "",
                "ANOMALY_TYPE": "OFF_HOURS"
            })
            audit_id_counter += 1

        # ATTACKER_4 — CROSS_DEPT
        a4 = attackers[3]
        num_a4 = random.randint(15, 30)
        # Filter patients with different PRIMARY_DEPT_ID
        cross_dept_patients = df_patients[df_patients["PRIMARY_DEPT_ID"] != a4["DEPT_ID"]]["PAT_ID"].tolist()
        if cross_dept_patients:
            for _ in range(num_a4):
                pat_id = random.choice(cross_dept_patients)
                hour = random.randint(a4["NORMAL_START_HOUR"], a4["NORMAL_END_HOUR"])
                dt = current_date.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))
                action_c = random.choices(action_choices, weights=a4["ACTION_WEIGHTS"])[0]
                audit_events.append({
                    "AUDIT_ID": audit_id_counter,
                    "EMP_ID": a4["EMP_ID"],
                    "PAT_ID": pat_id,
                    "ACTION_C": action_c,
                    "ACTION_DATETIME": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "DEPT_ID": a4["DEPT_ID"],
                    "WORKSTATION_ID": f"PC-{random.randint(1, 99):02d}",
                    "SESSION_ID": f"SESS-{random.randint(10000, 99999)}",
                    "IN_PANEL": pat_id in panel_lookup[a4["EMP_ID"]],
                    "IS_VIP_ACCESS": pat_id in vip_set,
                    "JUSTIFICATION": "Emergency override" if action_c == 5 else "",
                    "ANOMALY_TYPE": "CROSS_DEPT"
                })
                audit_id_counter += 1

# ─── SAVE AUDIT LOG ─────────────────────────────────────────
df_audit = pd.DataFrame(audit_events)
df_audit.to_csv(os.path.join(OUTPUT_DIR, "clarity_audit.csv"), index=False)

# ─── FINAL PRINT SUMMARY ────────────────────────────────────
total_events = len(df_audit)
normal_events = df_audit["ANOMALY_TYPE"].isna().sum()
anomalous_events = total_events - normal_events
anomaly_breakdown = df_audit["ANOMALY_TYPE"].value_counts(dropna=False)

print("\n=== GENERATION SUMMARY ===")
print(f"Total events generated:   {total_events:,}")
print(f"Normal events count:      {normal_events:,}")
print(f"Anomalous events count:   {anomalous_events:,}")
print("\nBreakdown by ANOMALY_TYPE:")
print(anomaly_breakdown)

print("\nAttacker Details:")
for a in attackers:
    print(f" - EMP_ID: {a['EMP_ID']} ({a['ROLE']}) -> {attacker_profiles[a['EMP_ID']]}")

print("\nFile paths saved:")
print(f" - {os.path.abspath(os.path.join(OUTPUT_DIR, 'employees.csv'))}")
print(f" - {os.path.abspath(os.path.join(OUTPUT_DIR, 'patients.csv'))}")
print(f" - {os.path.abspath(os.path.join(OUTPUT_DIR, 'patient_panels.csv'))}")
print(f" - {os.path.abspath(os.path.join(OUTPUT_DIR, 'clarity_audit.csv'))}")
print(f" - {os.path.abspath(os.path.join(OUTPUT_DIR, 'attacker_manifest.txt'))}")
print("==========================")
