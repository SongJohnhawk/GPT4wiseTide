"""
MarketTimeManager - 종장 시간 체크 기능 관리
자동매매와 단타매매의 종장 시간 이후 동작을 제어하는 매니저
"""

import json
import os
from datetime import datetime, time
from pathlib import Path
from typing import Optional

class MarketTimeManager:
    """종장 시간 체크 설정을 관리하는 클래스"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        MarketTimeManager 초기화
        
        Args:
            config_path: 설정 파일 경로 (기본값: 프로젝트 루트/market_time_config.json)
        """
        if config_path is None:
            self.config_path = Path(__file__).parent / "market_time_config.json"
        else:
            self.config_path = Path(config_path)
        
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """설정 파일 로드"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # 기본 설정
                default_config = {
                    "market_time_check_enabled": True,  # 기본값: ON (종장 시간 체크 활성화)
                    "market_close_time": "14:55",        # 종장 시간
                    "description": "종장 시간 체크 설정 파일"
                }
                self._save_config(default_config)
                return default_config
        except Exception as e:
            print(f"설정 파일 로드 오류: {e}")
            # 기본 설정 반환
            return {
                "market_time_check_enabled": True,
                "market_close_time": "14:55"
            }
    
    def _save_config(self, config: dict):
        """설정 파일 저장"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"설정 파일 저장 오류: {e}")
    
    def is_market_time_check_enabled(self) -> bool:
        """종장 시간 체크 활성화 여부 확인"""
        return self.config.get("market_time_check_enabled", True)
    
    def enable_market_time_check(self):
        """종장 시간 체크 활성화"""
        self.config["market_time_check_enabled"] = True
        self._save_config(self.config)
        print("[MarketTimeManager] 종장 시간 체크 활성화됨")
    
    def disable_market_time_check(self):
        """종장 시간 체크 비활성화"""
        self.config["market_time_check_enabled"] = False
        self._save_config(self.config)
        print("[MarketTimeManager] 종장 시간 체크 비활성화됨")
    
    def get_market_close_time(self) -> time:
        """종장 시간 조회"""
        time_str = self.config.get("market_close_time", "14:55")
        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour, minute)
        except Exception:
            return time(14, 55)  # 기본값
    
    def set_market_close_time(self, market_time: str):
        """종장 시간 설정"""
        try:
            # 시간 형식 검증
            hour, minute = map(int, market_time.split(':'))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                self.config["market_close_time"] = market_time
                self._save_config(self.config)
                print(f"[MarketTimeManager] 종장 시간이 {market_time}로 설정됨")
            else:
                raise ValueError("잘못된 시간 형식")
        except Exception as e:
            print(f"종장 시간 설정 오류: {e}")
    
    def is_market_closed(self) -> bool:
        """현재 시간이 종장 시간 이후인지 확인"""
        if not self.is_market_time_check_enabled():
            return False  # 체크 비활성화 시 항상 장중으로 처리
        
        current_time = datetime.now().time()
        market_close = self.get_market_close_time()
        
        return current_time >= market_close
    
    def get_trading_mode_description(self) -> str:
        """현재 트레이딩 모드 설명 반환"""
        if self.is_market_time_check_enabled():
            if self.is_market_closed():
                return f"종장 시간 이후 (종장: {self.get_market_close_time().strftime('%H:%M')}) - 계좌조회만 실행"
            else:
                return f"장중 (종장: {self.get_market_close_time().strftime('%H:%M')}) - 정상 트레이딩"
        else:
            return "종장 시간 체크 비활성화 - 24시간 트레이딩 모드"
    
    def should_run_algorithm(self) -> bool:
        """알고리즘 실행 여부 결정"""
        if not self.is_market_time_check_enabled():
            return True  # 체크 비활성화 시 항상 실행
        
        return not self.is_market_closed()
    
    def should_only_check_account(self) -> bool:
        """계좌조회만 실행해야 하는지 여부"""
        if not self.is_market_time_check_enabled():
            return False  # 체크 비활성화 시 계좌조회만 하지 않음
        
        return self.is_market_closed()


# 전역 인스턴스
_market_time_manager = None

def get_market_time_manager() -> MarketTimeManager:
    """MarketTimeManager 싱글톤 인스턴스 반환"""
    global _market_time_manager
    if _market_time_manager is None:
        _market_time_manager = MarketTimeManager()
    return _market_time_manager