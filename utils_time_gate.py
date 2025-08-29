"""
시간 게이트 유틸리티 모듈
장 마감 임박 시 신규 진입 금지 및 안전 모드 전환을 위한 시간 기반 제어
"""

from datetime import datetime, timedelta, time
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def is_close_guard_window(now: time, close: time, minutes: int = 5) -> bool:
    """
    장 마감 임박 여부 확인 (신규 진입 금지 구간)
    
    Args:
        now: 현재 시간
        close: 장 마감 시간
        minutes: 마감 전 몇 분부터 제한할지 (기본 5분)
    
    Returns:
        bool: 마감 임박 구간이면 True
    """
    try:
        today = datetime.today()
        t_now = today.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=0)
        t_close = today.replace(hour=close.hour, minute=close.minute, second=0, microsecond=0)
        
        time_diff = t_close - t_now
        return time_diff <= timedelta(minutes=minutes) and time_diff.total_seconds() > 0
    except Exception as e:
        logger.warning(f"시간 게이트 확인 실패: {e}")
        return False


def get_remaining_time_until_close(now: time, close: time) -> Dict[str, Any]:
    """
    장 마감까지 남은 시간 계산
    
    Args:
        now: 현재 시간
        close: 장 마감 시간
    
    Returns:
        Dict: 남은 시간 정보 (minutes, seconds, formatted_string)
    """
    try:
        today = datetime.today()
        t_now = today.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=0)
        t_close = today.replace(hour=close.hour, minute=close.minute, second=0, microsecond=0)
        
        time_diff = t_close - t_now
        
        if time_diff.total_seconds() <= 0:
            return {
                "minutes": 0,
                "seconds": 0,
                "total_seconds": 0,
                "formatted_string": "장 마감 시간 도달",
                "is_past_close": True
            }
        
        total_seconds = int(time_diff.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        return {
            "minutes": minutes,
            "seconds": seconds, 
            "total_seconds": total_seconds,
            "formatted_string": f"{minutes}분 {seconds}초",
            "is_past_close": False
        }
        
    except Exception as e:
        logger.error(f"남은 시간 계산 실패: {e}")
        return {
            "minutes": 0,
            "seconds": 0,
            "total_seconds": 0,
            "formatted_string": "계산 실패",
            "is_past_close": True
        }


def create_trading_policy_for_close_guard(base_policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    마감 임박 시 적용할 매매 정책 생성
    
    Args:
        base_policy: 기존 매매 정책 (옵션)
    
    Returns:
        Dict: 마감 임박 시 적용할 매매 정책
    """
    if base_policy is None:
        base_policy = {}
    
    close_guard_policy = base_policy.copy()
    
    # 신규 진입 금지
    close_guard_policy["allow_new_entry"] = False
    close_guard_policy["allow_new_buy"] = False
    
    # 포지션 관리 모드로 전환
    close_guard_policy["position_management_only"] = True
    close_guard_policy["emergency_sell_allowed"] = True
    
    # 리스크 관리 강화
    close_guard_policy["reduce_position_size"] = True
    close_guard_policy["strict_stop_loss"] = True
    
    return close_guard_policy


def format_close_guard_message(now: time, close: time, minutes: int = 5) -> str:
    """
    마감 임박 안내 메시지 포맷팅
    
    Args:
        now: 현재 시간
        close: 장 마감 시간
        minutes: 마감 전 제한 시간 (분)
    
    Returns:
        str: 포맷된 메시지
    """
    remaining = get_remaining_time_until_close(now, close)
    
    if remaining["is_past_close"]:
        return f"장 마감 시간 도달 — 자동매매 종료"
    
    return (
        f"장 마감 임박 알림\n"
        f"현재 시각: {now.strftime('%H:%M:%S')}\n"
        f"마감 시각: {close.strftime('%H:%M')}\n"
        f"남은 시간: {remaining['formatted_string']}\n"
        f"신규 진입 금지 — 포지션 관리 모드 전환({minutes}분 전)"
    )


def should_block_new_trades(now: time, close: time, guard_minutes: int = 5) -> tuple[bool, str]:
    """
    신규 거래 차단 여부 확인
    
    Args:
        now: 현재 시간
        close: 장 마감 시간
        guard_minutes: 마감 전 차단 시간 (분)
    
    Returns:
        tuple: (차단 여부, 차단 사유)
    """
    try:
        # 이미 장 마감 시간을 지났는지 확인
        remaining = get_remaining_time_until_close(now, close)
        if remaining["is_past_close"]:
            return True, "MARKET_CLOSED"
        
        # 마감 임박 구간인지 확인
        if is_close_guard_window(now, close, guard_minutes):
            return True, f"CLOSE_GUARD_{guard_minutes}MIN"
        
        return False, "NORMAL_TRADING"
        
    except Exception as e:
        logger.error(f"거래 차단 확인 실패: {e}")
        return True, "ERROR_SAFE_BLOCK"


class TimeGateManager:
    """시간 기반 거래 제어 관리자"""
    
    def __init__(self, market_close_time: time, guard_minutes: int = 5):
        """
        초기화
        
        Args:
            market_close_time: 장 마감 시간
            guard_minutes: 마감 전 제한 시간 (분)
        """
        self.market_close_time = market_close_time
        self.guard_minutes = guard_minutes
        self._last_warning_time = None
        self._close_guard_activated = False
        
    def check_trading_status(self, now: Optional[time] = None) -> Dict[str, Any]:
        """
        현재 거래 상태 확인
        
        Args:
            now: 현재 시간 (None이면 자동 계산)
        
        Returns:
            Dict: 거래 상태 정보
        """
        if now is None:
            now = datetime.now().time()
            
        should_block, block_reason = should_block_new_trades(now, self.market_close_time, self.guard_minutes)
        remaining = get_remaining_time_until_close(now, self.market_close_time)
        is_guard_window = is_close_guard_window(now, self.market_close_time, self.guard_minutes)
        
        return {
            "current_time": now,
            "market_close_time": self.market_close_time,
            "should_block_new_trades": should_block,
            "block_reason": block_reason,
            "is_close_guard_window": is_guard_window,
            "remaining_time": remaining,
            "trading_policy": create_trading_policy_for_close_guard() if is_guard_window else {"allow_new_entry": True}
        }
    
    def get_status_message(self, now: Optional[time] = None) -> str:
        """
        현재 상태 메시지 생성
        
        Args:
            now: 현재 시간 (None이면 자동 계산)
        
        Returns:
            str: 상태 메시지
        """
        status = self.check_trading_status(now)
        
        if status["remaining_time"]["is_past_close"]:
            return "장 마감 시간 도달 — 자동매매 종료"
        elif status["is_close_guard_window"]:
            return format_close_guard_message(status["current_time"], self.market_close_time, self.guard_minutes)
        else:
            return f"정상 거래 시간 — 남은 시간: {status['remaining_time']['formatted_string']}"
    
    def should_send_warning(self, now: Optional[time] = None, warning_interval_seconds: int = 60) -> bool:
        """
        경고 메시지 전송 여부 확인 (중복 방지)
        
        Args:
            now: 현재 시간 (None이면 자동 계산)
            warning_interval_seconds: 경고 간격 (초)
        
        Returns:
            bool: 경고 전송 여부
        """
        if now is None:
            now = datetime.now().time()
            
        current_datetime = datetime.now()
        
        # 마감 임박 구간이 아니면 경고 불필요
        if not is_close_guard_window(now, self.market_close_time, self.guard_minutes):
            self._last_warning_time = None
            self._close_guard_activated = False
            return False
        
        # 첫 번째 경고이거나 충분한 시간이 지났으면 전송
        if (self._last_warning_time is None or 
            (current_datetime - self._last_warning_time).total_seconds() >= warning_interval_seconds):
            self._last_warning_time = current_datetime
            return True
        
        return False