"""
ESP32 화재 감지 시스템
센서 데이터를 기반으로 화재 위험도를 평가하는 모듈
- NaN/None 안전 비교
- 가중치 기반 위험 점수(0~100)
- 변화량(트렌드) 보정
- 히스테리시스 및 알림 쿨다운 지원
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
import math
import time


# -----------------------------
# 임계값 & 가중치 (현실적인 기본값)
# -----------------------------
FIRE_THRESHOLDS: Dict[str, float] = {
    "temperature": 30.0,  # °C  (주의 온도 시작 구간; 화재성 상승 감지용)
    "tvoc": 300.0,        # ppb (연소·가스 누출 등 TVOC 급상승 감지)
    "eco2": 1000.0,       # ppm (연소 시 CO2 상승)
    "humidity_low": 30.0  # %   (건조 환경)
}

# 각 요인별 위험 가중치 (합 100 권장)
FIRE_WEIGHTS: Dict[str, int] = {
    "temperature": 40,
    "tvoc": 30,
    "eco2": 20,
    "humidity_low": 10,
}

# 급격한 상승(트렌드) 보정 임계값 (최근값 - 직전값 기준)
DELTA_THRESHOLDS: Dict[str, float] = {
    "temperature": 2.0,   # °C 이상 급상승 시 보정
    "tvoc": 100.0,        # ppb
    "eco2": 200.0,        # ppm
}

DELTA_BONUS: int = 10  # 급상승 시 점수 가산치(요소당)


@dataclass
class SensorReading:
    temperature: Optional[float]
    humidity: Optional[float]
    eco2: Optional[float]
    tvoc: Optional[float]
    ts: Optional[float] = None  # epoch seconds (옵션)


# -----------------------------
# 유틸
# -----------------------------
def _is_valid(x: Optional[float]) -> bool:
    return x is not None and isinstance(x, (int, float)) and not math.isnan(float(x))


def _gt(value: Optional[float], threshold: float) -> bool:
    return _is_valid(value) and float(value) > threshold


def _lt(value: Optional[float], threshold: float) -> bool:
    return _is_valid(value) and float(value) < threshold


# -----------------------------
# 핵심 평가 함수
# -----------------------------
def check_fire_risk(
    temperature: Optional[float],
    humidity: Optional[float],
    eco2: Optional[float],
    tvoc: Optional[float],
    *,
    prev: Optional[SensorReading] = None,
    thresholds: Dict[str, float] = FIRE_THRESHOLDS,
    weights: Dict[str, int] = FIRE_WEIGHTS,
) -> Dict[str, Any]:
    """
    센서 데이터를 기반으로 화재 위험도를 평가

    Args:
        temperature: °C
        humidity: %
        eco2: ppm
        tvoc: ppb
        prev: 직전 센서값(트렌드 보정용). 없으면 보정 미적용
        thresholds: 임계값 오버라이드
        weights: 가중치 오버라이드 (합계 100 권장)

    Returns:
        dict: {
          risk_level: SAFE/LOW/MEDIUM/HIGH,
          risk_score: 0~100,
          message: str,
          risk_factors: [str, ...],
          thresholds_used: dict,
          components: {temperature: 0|weight, ...},
          delta_bonus: int
        }
    """
    risk_score = 0
    risk_factors = []
    components: Dict[str, int] = {"temperature": 0, "tvoc": 0, "eco2": 0, "humidity_low": 0}
    delta_bonus_total = 0

    # --- 온도 ---
    if _gt(temperature, thresholds["temperature"]):
        risk_score += weights["temperature"]
        components["temperature"] = weights["temperature"]
        risk_factors.append(f"고온 감지 ({temperature:.2f}°C > {thresholds['temperature']}°C)")
    # --- TVOC ---
    if _gt(tvoc, thresholds["tvoc"]):
        risk_score += weights["tvoc"]
        components["tvoc"] = weights["tvoc"]
        risk_factors.append(f"TVOC 상승 ({tvoc:.0f}ppb > {thresholds['tvoc']}ppb)")
    # --- eCO2 ---
    if _gt(eco2, thresholds["eco2"]):
        risk_score += weights["eco2"]
        components["eco2"] = weights["eco2"]
        risk_factors.append(f"eCO2 상승 ({eco2:.0f}ppm > {thresholds['eco2']}ppm)")
    # --- 낮은 습도 ---
    if _lt(humidity, thresholds["humidity_low"]):
        risk_score += weights["humidity_low"]
        components["humidity_low"] = weights["humidity_low"]
        risk_factors.append(f"낮은 습도 ({humidity:.1f}% < {thresholds['humidity_low']}%)")

    # --- 트렌드(직전값 대비 급상승) 보정 ---
    if prev:
        if _is_valid(temperature) and _is_valid(prev.temperature):
            if temperature - prev.temperature >= DELTA_THRESHOLDS["temperature"]:
                risk_score += DELTA_BONUS
                delta_bonus_total += DELTA_BONUS
                risk_factors.append(f"온도 급상승 +{temperature - prev.temperature:.1f}°C")
        if _is_valid(tvoc) and _is_valid(prev.tvoc):
            if tvoc - prev.tvoc >= DELTA_THRESHOLDS["tvoc"]:
                risk_score += DELTA_BONUS
                delta_bonus_total += DELTA_BONUS
                risk_factors.append(f"TVOC 급상승 +{tvoc - prev.tvoc:.0f}ppb")
        if _is_valid(eco2) and _is_valid(prev.eco2):
            if eco2 - prev.eco2 >= DELTA_THRESHOLDS["eco2"]:
                risk_score += DELTA_BONUS
                delta_bonus_total += DELTA_BONUS
                risk_factors.append(f"eCO2 급상승 +{eco2 - prev.eco2:.0f}ppm")

    # 점수 상한/하한
    risk_score = max(0, min(100, risk_score))

    # 히스테리시스 규칙(너무 과민한 HIGH 방지):
    # - HIGH는 (a) 온도 + (TVOC 또는 eCO2) 둘 이상이 기준 초과이거나
    #           (b) 단일 요소라도 점수 70 이상(가중치+보정)일 때
    # - MEDIUM은 점수 40 이상
    # - LOW는 점수 20 이상
    over_flags = {
        "temperature": components["temperature"] > 0,
        "tvoc": components["tvoc"] > 0,
        "eco2": components["eco2"] > 0,
        "humidity_low": components["humidity_low"] > 0,
    }
    two_strong = (over_flags["temperature"] and (over_flags["tvoc"] or over_flags["eco2"]))

    if two_strong or risk_score >= 70:
        risk_level = "HIGH"
        message = "🚨 화재 위험 - 즉시 확인 필요!"
    elif risk_score >= 40:
        risk_level = "MEDIUM"
        message = "⚠️ 주의 - 모니터링 강화"
    elif risk_score >= 20:
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
        "thresholds_used": thresholds,
        "components": components,
        "delta_bonus": delta_bonus_total,
    }


# -----------------------------
# 표시/알림 유틸
# -----------------------------
def get_risk_level_color(risk_level: str) -> str:
    """위험도 레벨에 따른 표시 이모지 반환"""
    colors = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟠", "SAFE": "🟢"}
    return colors.get(risk_level, "⚪")


def format_fire_alert(fire_risk: Dict[str, Any], device_id: Optional[str] = None) -> str:
    """화재 위험도 정보를 보기 좋게 포맷팅"""
    color = get_risk_level_color(fire_risk["risk_level"])

    alert_msg = f"{color} {fire_risk['message']}"
    if device_id:
        alert_msg += f" (기기: {device_id})"

    if fire_risk.get("risk_factors"):
        alert_msg += "\n⚠️ 위험 요소: " + ", ".join(fire_risk["risk_factors"])

    score = fire_risk.get("risk_score")
    if isinstance(score, (int, float)):
        alert_msg += f"\n점수: {score:.0f}"

    return alert_msg


def is_fire_emergency(fire_risk: Dict[str, Any]) -> bool:
    """긴급 화재 상황인지 확인"""
    return fire_risk.get("risk_level") == "HIGH"


def should_send_alert(
    fire_risk: Dict[str, Any],
    *,
    last_sent_ts: Optional[float] = None,
    cooldown_sec: int = 60,
) -> bool:
    """
    알림을 보내야 하는 상황인지 확인
    - MEDIUM/HIGH에서만 발송
    - 쿨다운 시간 내에는 중복 발송 방지
    """
    if fire_risk.get("risk_level") not in ("HIGH", "MEDIUM"):
        return False
    if last_sent_ts is None:
        return True
    return (time.time() - last_sent_ts) >= cooldown_sec


__all__ = [
    "SensorReading",
    "FIRE_THRESHOLDS",
    "FIRE_WEIGHTS",
    "DELTA_THRESHOLDS",
    "check_fire_risk",
    "get_risk_level_color",
    "format_fire_alert",
    "is_fire_emergency",
    "should_send_alert",
]
