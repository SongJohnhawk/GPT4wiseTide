"""
자동매매 설정 관리 모듈
GPT5 코드 리뷰 권장사항에 따른 설정 외부화
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import time
from .trading_constants import DEFAULT_CONFIG, TradingConfig

logger = logging.getLogger(__name__)


class TradingConfigManager:
    """자동매매 설정 관리 클래스"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        초기화
        
        Args:
            config_file: 설정 파일 경로 (기본값: trading_config.json)
        """
        self.config_file = Path(config_file) if config_file else Path(TradingConfig.CONFIG_FILE)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"설정 파일 로드 성공: {self.config_file}")
                return {**DEFAULT_CONFIG, **config}  # 기본값과 병합
            else:
                # 설정 파일 없음 로그 차단 - Register_Key.md 우선 사용
                # logger.info(f"설정 파일이 없어 기본값 사용: {self.config_file}")
                logger.debug("기본 설정값 사용")
                return DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.warning(f"설정 파일 로드 실패, 기본값 사용: {e}")
            return DEFAULT_CONFIG.copy()
    
    def save_config(self) -> bool:
        """설정 파일 저장"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"설정 파일 저장 성공: {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"설정 파일 저장 실패: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """설정값 조회"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """설정값 저장"""
        self.config[key] = value
    
    def get_market_close_time(self) -> time:
        """시장 마감 시간 조회"""
        time_str = self.get("market_close_time", "14:55")
        hour, minute = map(int, time_str.split(':'))
        return time(hour, minute)
    
    def get_trading_cycle_seconds(self) -> int:
        """매매 사이클 간격 조회 (초)"""
        return self.get("trading_cycle_seconds", 5)
    
    def get_countdown_seconds(self) -> int:
        """카운트다운 시간 조회 (초)"""
        return self.get("countdown_seconds", 5)
    
    def get_step_delay_seconds(self) -> int:
        """단계별 지연 시간 조회 (초)"""
        return self.get("step_delay_seconds", 2)
    
    def get_max_position_percent(self) -> int:
        """최대 포지션 비중 조회 (%)"""
        return self.get("max_position_percent", 20)
    
    def get_stop_loss_percent(self) -> int:
        """손절 기준 조회 (%)"""
        return self.get("stop_loss_percent", -3)
    
    def get_take_profit_percent(self) -> int:
        """익절 기준 조회 (%)"""
        return self.get("take_profit_percent", 5)
    
    def get_default_algorithm(self) -> str:
        """기본 알고리즘 이름 조회"""
        return self.get("default_algorithm", "default")
    
    def update_from_dict(self, updates: Dict[str, Any]) -> None:
        """딕셔너리로부터 설정 업데이트"""
        self.config.update(updates)
    
    def reset_to_defaults(self) -> None:
        """기본값으로 초기화"""
        self.config = DEFAULT_CONFIG.copy()
    
    def get_max_consecutive_failures(self) -> int:
        """최대 연속 실패 허용 횟수 조회"""
        return self.get("recovery_settings", {}).get("max_consecutive_failures", 5)
    
    def get_critical_failure_wait_minutes(self) -> int:
        """치명적 실패 시 대기 시간 조회 (분)"""
        return self.get("recovery_settings", {}).get("critical_failure_wait_minutes", 30)
    
    def get_api_reconnect_attempts(self) -> int:
        """API 재연결 시도 횟수 조회"""
        return self.get("recovery_settings", {}).get("api_reconnect_attempts", 3)
    
    def get_max_emergency_recoveries(self) -> int:
        """최대 비상 복구 횟수 조회"""
        return self.get("recovery_settings", {}).get("max_emergency_recoveries", 3)
    
    def is_health_check_enabled(self) -> bool:
        """Health Check 활성화 여부 조회"""
        return self.get("recovery_settings", {}).get("health_check_enabled", True)
    
    def get_memory_threshold_percent(self) -> int:
        """메모리 사용량 임계값 조회 (%)"""
        return self.get("recovery_settings", {}).get("memory_threshold_percent", 90)
    
    def get_disk_threshold_percent(self) -> int:
        """디스크 사용량 임계값 조회 (%)"""
        return self.get("recovery_settings", {}).get("disk_threshold_percent", 95)
    
    def is_auto_restart_enabled(self) -> bool:
        """자동 재시작 기능 활성화 여부 조회"""
        return self.get("recovery_settings", {}).get("auto_restart", True)
    
    def is_emergency_stop_losses_enabled(self) -> bool:
        """비상 손절 기능 활성화 여부 조회"""
        return self.get("recovery_settings", {}).get("emergency_stop_losses", True)
    
    def is_system_monitoring_enabled(self) -> bool:
        """시스템 모니터링 활성화 여부 조회"""
        return self.get("monitoring_settings", {}).get("enable_system_monitoring", True)
    
    def get_enable_esc_stop(self) -> bool:
        """ESC 키 중단 기능 활성화 여부 조회"""
        return self.get("enable_esc_stop", False)
    
    def get_close_guard_minutes(self) -> int:
        """마감 전 신규 진입 금지 시간 조회 (분)"""
        return self.get("close_guard_minutes", 5)
    
    def is_close_guard_enabled(self) -> bool:
        """마감 임박 제어 기능 활성화 여부 조회"""
        return self.get("close_guard_enabled", True)
    
    def is_new_entry_block_before_close_enabled(self) -> bool:
        """마감 전 신규 진입 차단 기능 활성화 여부 조회"""
        return self.get("new_entry_block_before_close", True)
    
    def is_countdown_warning_enabled(self) -> bool:
        """카운트다운 경고 메시지 활성화 여부 조회"""
        return self.get("countdown_warning_enabled", True)
    
    def is_termination_reason_logging_enabled(self) -> bool:
        """종료 사유 로깅 활성화 여부 조회"""
        return self.get("termination_reason_logging", True)
    
    def get_health_check_interval_minutes(self) -> int:
        """Health Check 간격 조회 (분)"""
        return self.get("monitoring_settings", {}).get("health_check_interval_minutes", 5)
    
    def is_performance_logging_enabled(self) -> bool:
        """성능 로깅 활성화 여부 조회"""
        return self.get("monitoring_settings", {}).get("performance_logging", True)
    
    def is_telegram_alerts_enabled(self) -> bool:
        """텔레그램 알림 활성화 여부 조회"""
        return self.get("monitoring_settings", {}).get("telegram_alerts", True)
    
    def get_log_level(self) -> str:
        """로그 레벨 조회"""
        return self.get("monitoring_settings", {}).get("log_level", "INFO")
    
    def validate_config(self) -> bool:
        """설정값 유효성 검증 (확장)"""
        try:
            # 기존 검증
            # 시간 형식 검증
            self.get_market_close_time()
            
            # 숫자 범위 검증
            cycle_seconds = self.get_trading_cycle_seconds()
            if not 1 <= cycle_seconds <= 3600:
                raise ValueError(f"Invalid trading_cycle_seconds: {cycle_seconds}")
            
            countdown_seconds = self.get_countdown_seconds()
            if not 1 <= countdown_seconds <= 60:
                raise ValueError(f"Invalid countdown_seconds: {countdown_seconds}")
            
            max_position = self.get_max_position_percent()
            if not 1 <= max_position <= 100:
                raise ValueError(f"Invalid max_position_percent: {max_position}")
            
            stop_loss = self.get_stop_loss_percent()
            if not -50 <= stop_loss <= 0:
                raise ValueError(f"Invalid stop_loss_percent: {stop_loss}")
            
            take_profit = self.get_take_profit_percent()
            if not 1 <= take_profit <= 100:
                raise ValueError(f"Invalid take_profit_percent: {take_profit}")
            
            # 새로운 복구 설정 검증
            max_failures = self.get_max_consecutive_failures()
            if not 1 <= max_failures <= 20:
                raise ValueError(f"Invalid max_consecutive_failures: {max_failures}")
            
            wait_minutes = self.get_critical_failure_wait_minutes()
            if not 1 <= wait_minutes <= 120:
                raise ValueError(f"Invalid critical_failure_wait_minutes: {wait_minutes}")
            
            reconnect_attempts = self.get_api_reconnect_attempts()
            if not 1 <= reconnect_attempts <= 10:
                raise ValueError(f"Invalid api_reconnect_attempts: {reconnect_attempts}")
            
            memory_threshold = self.get_memory_threshold_percent()
            if not 50 <= memory_threshold <= 99:
                raise ValueError(f"Invalid memory_threshold_percent: {memory_threshold}")
            
            disk_threshold = self.get_disk_threshold_percent()
            if not 70 <= disk_threshold <= 99:
                raise ValueError(f"Invalid disk_threshold_percent: {disk_threshold}")
            
            return True
            
        except Exception as e:
            logger.error(f"설정값 유효성 검증 실패: {e}")
            return False
    
    def __str__(self) -> str:
        """설정 정보 문자열 표현"""
        return f"TradingConfig({self.config_file}): {json.dumps(self.config, indent=2, ensure_ascii=False)}"


# 싱글톤 인스턴스
_config_manager = None


def get_trading_config() -> TradingConfigManager:
    """자동매매 설정 관리자 싱글톤 인스턴스 반환"""
    global _config_manager
    if _config_manager is None:
        _config_manager = TradingConfigManager()
    return _config_manager