#!/usr/bin/env python3
"""
Fast Token Manager - KIS 공식 API 스펙 최적화 버전
단순하고 빠른 토큰 발급 및 관리
"""

import requests
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
from threading import Lock
from pathlib import Path

# 로깅 설정
logger = logging.getLogger(__name__)

# 전역 토큰 캐시 (계정 유형별 공유)
_global_token_cache = {}
_cache_lock = Lock()

# KIS API 속도 제한 추적 (계정 유형별)
_last_token_request_time = {}
_TOKEN_REQUEST_INTERVAL = 65  # 65초 간격 (1분 + 여유 시간)

@dataclass
class FastTokenInfo:
    """빠른 토큰 정보 클래스"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 86400  # 24시간 (초)
    issued_at: datetime = None
    expires_at: datetime = None
    
    def __post_init__(self):
        if self.issued_at is None:
            self.issued_at = datetime.now()
        if self.expires_at is None:
            self.expires_at = self.issued_at + timedelta(seconds=self.expires_in)
    
    def is_expired(self) -> bool:
        """토큰 만료 여부 확인"""
        return datetime.now() >= self.expires_at
    
    def is_near_expiry(self, minutes: int = 30) -> bool:
        """토큰 만료 임박 여부 확인"""
        return datetime.now() >= (self.expires_at - timedelta(minutes=minutes))
    
    def should_invalidate_at_daily_reset(self) -> bool:
        """23:59 이후 토큰 무효화 여부 확인"""
        current_time = datetime.now()
        return current_time.hour == 23 and current_time.minute >= 59

class FastTokenManager:
    """빠른 토큰 매니저 (KIS 공식 API 스펙 최적화)"""
    
    def __init__(self, account_type: str):
        self.account_type = account_type.upper()
        self._current_token: Optional[FastTokenInfo] = None
        self._token_lock = Lock()
        
        # Register_Key.md에서 설정 자동 로드
        self._load_config()
        
        logger.info(f"Fast Token Manager 초기화 완료: {self.account_type}")
    
    def _load_config(self):
        """Register_Key.md에서 설정 로드"""
        try:
            # 현재 디렉토리에서 register_key_loader 임포트
            import os
            import sys
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            from register_key_loader import get_api_config
            
            config = get_api_config(self.account_type)
            self.api_config = {
                "APP_KEY": config["APP_KEY"],
                "APP_SECRET": config["APP_SECRET"]
            }
            self.base_url = config["REST_URL"]
            
            logger.info(f"설정 로드 성공: {self.account_type}")
            
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
            raise ValueError(f"Register_Key.md 설정 로드 실패: {e}")
    
    def get_valid_token(self) -> Optional[str]:
        """유효한 토큰 획득 (전역 캐시 사용, 23:59 시간 체크 포함)"""
        with _cache_lock:
            # 전역 캐시에서 먼저 확인
            if self.account_type in _global_token_cache:
                cached_token = _global_token_cache[self.account_type]
                
                # 23:59 이후면 무조건 새 토큰 발급
                if cached_token.should_invalidate_at_daily_reset():
                    logger.info(f"23:59 이후 토큰 무효화: {self.account_type}")
                    del _global_token_cache[self.account_type]
                    self._current_token = None
                elif not cached_token.is_expired():
                    self._current_token = cached_token  # 로컬에도 저장
                    logger.debug(f"캐시된 토큰 사용: {self.account_type}")
                    return cached_token.access_token
            
            # 로컬 토큰 확인
            if self._current_token:
                # 23:59 이후면 무조건 새 토큰 발급
                if self._current_token.should_invalidate_at_daily_reset():
                    logger.info(f"23:59 이후 로컬 토큰 무효화: {self.account_type}")
                    self._current_token = None
                elif not self._current_token.is_expired():
                    _global_token_cache[self.account_type] = self._current_token  # 캐시에 저장
                    return self._current_token.access_token
            
            # 새 토큰 발급 (속도 제한 방지를 위한 체크)
            if self._should_request_new_token():
                new_token = self._request_new_token()
                if new_token:
                    self._current_token = new_token
                    _global_token_cache[self.account_type] = new_token  # 전역 캐시에 저장
                    logger.info(f"새 토큰 발급 및 캐싱: {self.account_type}")
                    return new_token.access_token
            
            return None
    
    def _should_request_new_token(self) -> bool:
        """새 토큰 요청 가능 여부 확인 (속도 제한 방지)"""
        current_time = time.time()
        
        # 이 계정 유형의 마지막 요청 시간 확인
        if self.account_type in _last_token_request_time:
            last_request = _last_token_request_time[self.account_type]
            time_diff = current_time - last_request
            
            if time_diff < _TOKEN_REQUEST_INTERVAL:
                remaining = _TOKEN_REQUEST_INTERVAL - time_diff
                logger.warning(f"KIS API 속도 제한: {remaining:.1f}초 후 토큰 요청 가능")
                return False
        
        return True
    
    def _request_new_token(self) -> Optional[FastTokenInfo]:
        """Daily Token Manager에서 토큰 가져오기"""
        try:
            # Daily Token Manager 사용
            import sys
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            support_dir = os.path.join(parent_dir, 'support')
            if support_dir not in sys.path:
                sys.path.insert(0, support_dir)
            
            from daily_token_manager import get_daily_token_manager
            
            manager = get_daily_token_manager()
            access_token = manager.get_token(self.account_type)
            
            if access_token:
                token_info = FastTokenInfo(
                    access_token=access_token,
                    token_type="Bearer",
                    expires_in=86400  # 24시간
                )
                logger.info(f"Daily Token Manager에서 토큰 획득 성공: {self.account_type}")
                return token_info
            else:
                logger.warning(f"Daily Token Manager에서 토큰 획득 실패: {self.account_type}")
                return None
            
        except Exception as e:
            logger.error(f"Daily Token Manager 연동 실패: {e}")
            return None
    
    def force_refresh(self) -> Optional[str]:
        """토큰 강제 갱신 (속도 제한 무시)"""
        with _cache_lock:
            # 캐시에서 제거
            if self.account_type in _global_token_cache:
                del _global_token_cache[self.account_type]
            
            self._current_token = None  # 기존 토큰 무효화
            
            # 강제로 새 토큰 요청 (속도 제한 체크 건너뛰기)
            new_token = self._request_new_token()
            if new_token:
                self._current_token = new_token
                _global_token_cache[self.account_type] = new_token
                logger.debug(f"토큰 강제 갱신 완료: {self.account_type}")
                return new_token.access_token
            
            return None
    
    def get_token_status(self) -> Dict[str, Any]:
        """토큰 상태 정보 반환"""
        if self._current_token:
            return {
                "exists": True,
                "valid": not self._current_token.is_expired(),
                "expires_at": self._current_token.expires_at.isoformat(),
                "near_expiry": self._current_token.is_near_expiry(),
                "token_length": len(self._current_token.access_token)
            }
        else:
            return {
                "exists": False,
                "valid": False,
                "expires_at": None,
                "near_expiry": False,
                "token_length": 0
            }

def create_fast_token_manager(account_type: str) -> FastTokenManager:
    """빠른 토큰 매니저 생성"""
    return FastTokenManager(account_type)

# 테스트용 함수
def test_fast_token_manager():
    """빠른 토큰 매니저 테스트"""
    print("=== Fast Token Manager 테스트 ===")
    
    try:
        # 모의투자용 토큰 매니저 생성
        manager = create_fast_token_manager("MOCK")
        
        # 토큰 발급 테스트
        token = manager.get_valid_token()
        
        if token:
            print(f"[SUCCESS] 토큰 발급 성공: {token[:30]}...")
            
            # 상태 확인
            status = manager.get_token_status()
            print(f"토큰 상태: {status}")
            
            return True
        else:
            print("[FAILED] 토큰 발급 실패")
            return False
            
    except Exception as e:
        print(f"[ERROR] 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    # 기본 테스트 실행
    result = test_fast_token_manager()
    if result:
        print("Fast Token Manager 테스트 성공!")
    else:
        print("Fast Token Manager 테스트 실패!")