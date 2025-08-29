#!/usr/bin/env python3
"""
장마감 체크 컨트롤러 - 시장 마감 시간 기반 자동매매 제어
"""

import json
import logging
from datetime import datetime, time
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class MarketCloseController:
    """장마감 시간 제어 및 매매 종료 관리"""
    
    def __init__(self, config_path: str = "trading_config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.is_enabled = self.config.get("market_close_check_enabled", False)
        self.market_close_time = time(14, 55)  # 기본 14:55
        self.guard_minutes = 5
        
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.warning(f"설정 파일 로드 실패: {e}")
            return {}
    
    def _save_config(self):
        """설정 파일 저장"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"설정 파일 저장 실패: {e}")
    
    def enable_market_close_check(self) -> bool:
        """장마감 체크 기능 활성화"""
        try:
            self.is_enabled = True
            self.config["market_close_check_enabled"] = True
            self._save_config()
            logger.info("[MARKET_CLOSE] 장마감 체크 기능 활성화")
            return True
        except Exception as e:
            logger.error(f"장마감 체크 활성화 실패: {e}")
            return False
    
    def disable_market_close_check(self) -> bool:
        """장마감 체크 기능 비활성화"""
        try:
            self.is_enabled = False
            self.config["market_close_check_enabled"] = False
            self._save_config()
            logger.info("[MARKET_CLOSE] 장마감 체크 기능 비활성화")
            return True
        except Exception as e:
            logger.error(f"장마감 체크 비활성화 실패: {e}")
            return False
    
    def is_market_close_check_enabled(self) -> bool:
        """장마감 체크 활성화 상태 확인"""
        return self.is_enabled
    
    def should_stop_trading(self, current_time: Optional[time] = None) -> bool:
        """매매 중단 여부 판단"""
        if not self.is_enabled:
            return False
        
        if current_time is None:
            current_time = datetime.now().time()
        
        return current_time >= self.market_close_time
    
    def should_enter_guard_mode(self, current_time: Optional[time] = None) -> bool:
        """가드 모드 진입 여부 판단 (신규 진입 금지)"""
        if not self.is_enabled:
            return False
        
        if current_time is None:
            current_time = datetime.now().time()
        
        # 마감 N분 전부터 가드 모드
        from datetime import datetime, timedelta
        today = datetime.today()
        t_now = today.replace(hour=current_time.hour, minute=current_time.minute, second=current_time.second)
        t_close = today.replace(hour=self.market_close_time.hour, minute=self.market_close_time.minute, second=0)
        
        time_diff = t_close - t_now
        return 0 < time_diff.total_seconds() <= (self.guard_minutes * 60)
    
    def get_time_until_close(self, current_time: Optional[time] = None) -> Dict[str, Any]:
        """마감까지 남은 시간 계산"""
        if current_time is None:
            current_time = datetime.now().time()
        
        today = datetime.today()
        t_now = today.replace(hour=current_time.hour, minute=current_time.minute, second=current_time.second)
        t_close = today.replace(hour=self.market_close_time.hour, minute=self.market_close_time.minute, second=0)
        
        time_diff = t_close - t_now
        
        if time_diff.total_seconds() <= 0:
            return {"minutes": 0, "seconds": 0, "is_past_close": True, "formatted": "장 마감"}
        
        minutes = int(time_diff.total_seconds() // 60)
        seconds = int(time_diff.total_seconds() % 60)
        
        return {
            "minutes": minutes,
            "seconds": seconds,
            "is_past_close": False,
            "formatted": f"{minutes}분 {seconds}초 남음"
        }
    
    async def generate_trading_report(self, account_type: str, algorithm_name: str, trading_stats: Dict[str, Any]) -> str:
        """매매 종료시 리포트 생성"""
        try:
            report_dir = Path("report")
            report_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"daily_close_report_{account_type}_{algorithm_name}_{timestamp}.json"
            report_path = report_dir / filename
            
            report_data = {
                "timestamp": timestamp,
                "account_type": account_type,
                "algorithm": algorithm_name,
                "market_close_time": self.market_close_time.strftime("%H:%M"),
                "trading_stats": trading_stats,
                "system_status": "MARKET_CLOSED"
            }
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[MARKET_CLOSE] 일일 매매 리포트 생성: {filename}")
            return str(report_path)
            
        except Exception as e:
            logger.error(f"매매 리포트 생성 실패: {e}")
            return ""

# 전역 인스턴스
_market_close_controller = None

def get_market_close_controller() -> MarketCloseController:
    """마켓 클로즈 컨트롤러 싱글톤 인스턴스 반환"""
    global _market_close_controller
    if _market_close_controller is None:
        _market_close_controller = MarketCloseController()
    return _market_close_controller