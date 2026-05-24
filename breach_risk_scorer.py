def calculate_breach_risk(anomaly_type: str, action_c: int, is_sensitive_access: int, is_vip: int) -> tuple[float, bool]: 
    """ 
    Applies the HIPAA 4-factor risk assessment heuristic. 
    Returns (risk_score out of 10.0, requires_ocr_review boolean). 
    """ 
    score = 0.0 
    
    # Factor 1: Nature and extent of PHI 
    if is_sensitive_access == 1: 
        score += 4.0  # High risk: HIV, Behavioral Health 
    if is_vip == 1: 
        score += 2.0  # VIP records have higher exposure risk 
        
    # Factor 2: Unauthorized person (Anomaly Type) 
    if anomaly_type == "BULK_EXPORT": 
        score += 3.0 
    elif anomaly_type == "SENSITIVE_SNOOP": 
        score += 2.5 
    elif anomaly_type == "VIP_SNOOP": 
        score += 2.0 
    elif anomaly_type == "OFF_HOURS": 
        score += 1.0 

    # Factor 3: Was it actually acquired/viewed? 
    if action_c in (4, 5):  # Print (4) or Export (5) 
        score += 3.0 
    elif action_c == 3:  # Chart Open (3) 
        score += 1.0 
        
    # Factor 4: Mitigation (Handled manually by officers later, so we cap base score at 10) 
    score = min(score, 10.0) 
    
    # Threshold for OCR 72-hour review (e.g., score >= 6.0) 
    requires_review = bool(score >= 6.0) 
    
    return score, requires_review 
