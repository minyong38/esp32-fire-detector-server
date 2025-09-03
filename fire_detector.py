"""
ESP32 화재 감지 시스템
센서 데이터를 기반으로 화재 위험도를 평가하는 모듈
"""

# 화재 감지 임계값 설정
FIRE_THRESHOLDS = {
    'temperature': 30.0,  # 온도 30도 이상
    'tvoc': 100,          # TVOC 300ppb 이상  
    'eco2': 100          # eCO2 1000ppm 이상
}

def check_fire_risk(temperature, humidity, eco2, tvoc):
    """
    센서 데이터를 기반으로 화재 위험도를 평가s
    
    Args:ss
        temperature: 온도 (°C)
        humidity: 습도 (%)
        eco2: eCO2 농도 (ppm)
        tvoc: TVOC 농도 (ppb)
        
    Returns:
        dict: 화재 위험도 분석 결과
    """
    risk_score = 0
    risk_factors = []
    
    # 온도 체크
    if temperature and temperature > FIRE_THRESHOLDS['temperature']:
        risk_score += 30
        risk_factors.append(f"고온 감지 ({temperature}°C)")
    
    # TVOC 체크 (연소시 발생하는 휘발성 유기화합물)
    if tvoc and tvoc > FIRE_THRESHOLDS['tvoc']:
        risk_score += 25
        risk_factors.append(f"TVOC 농도 증가 ({tvoc}ppb)")
    
    # eCO2 체크 (연소시 발생하는 이산화탄소)
    if eco2 and eco2 > FIRE_THRESHOLDS['eco2']:
        risk_score += 20
        risk_factors.append(f"eCO2 농도 증가 ({eco2}ppm)")
    
    # 습도가 너무 낮으면 화재 위험 증가
    if humidity and humidity < 30:
        risk_score += 15
        risk_factors.append(f"낮은 습도 ({humidity}%)")
    
    # 위험도 레벨 결정
    if risk_score >= 50:
        risk_level = "HIGH"
        message = "🚨 화재 위험 - 즉시 확인 필요!"
    elif risk_score >= 30:
        risk_level = "MEDIUM" 
        message = "⚠️ 주의 - 모니터링 강화"
    elif risk_score >= 15:
        risk_level = "LOW"
        message = "📊 경미한 이상 - 관찰 필요"
    else:
        risk_level = "SAFE"
        message = "✅ 정상 범위"
    
    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "message": message,
        "risk_factors": risk_factors,
        "thresholds_used": FIRE_THRESHOLDS
    }

def get_risk_level_color(risk_level):
    """위험도 레벨에 따른 색상 코드 반환"""
    colors = {
        "HIGH": "🔴",
        "MEDIUM": "🟡", 
        "LOW": "🟠",
        "SAFE": "🟢"
    }
    return colors.get(risk_level, "⚪")

def format_fire_alert(fire_risk, device_id=None):
    """화재 위험도 정보를 보기 좋게 포맷팅"""
    color = get_risk_level_color(fire_risk['risk_level'])
    
    alert_msg = f"{color} {fire_risk['message']}"
    if device_id:
        alert_msg += f" (기기: {device_id})"
    
    if fire_risk['risk_factors']:
        alert_msg += f"\n⚠️ 위험 요소: {', '.join(fire_risk['risk_factors'])}"
    
    return alert_msg

def is_fire_emergency(fire_risk):
    """긴급 화재 상황인지 확인"""
    return fire_risk['risk_level'] == "HIGH"

def should_send_alert(fire_risk):
    """알림을 보내야 하는 상황인지 확인"""
    return fire_risk['risk_level'] in ["HIGH", "MEDIUM"]
