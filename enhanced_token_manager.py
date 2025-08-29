#!/usr/bin/env python3
"""
Enhanced KIS API 토큰 관리 시스템 (개선된 버전)
- 지수백오프 재시도 로직
- 만료 30분 전 자동 갱신  
- 토큰 상태 실시간 모니터링
- 멀티스레드 안전성 향상
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from threading import Lock
import requests

# TokenInfo와 KISTokenManager를 간소화된 버전으로 구현
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

@dataclass
class TokenInfo:
    """토큰 정보 데이터 클래스"""
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
        """토큰 만료 임박 여부 확인 (기본 30분 전)"""
        return datetime.now() >= (self.expires_at - timedelta(minutes=minutes))

class KISTokenManager:
    """기본 토큰 관리자 (KIS 공식 API 스펙 준수)"""
    
    def __init__(self, account_type: str, api_config: Dict[str, str], base_url: str):
        self.account_type = account_type.upper()
        self.api_config = api_config
        self.base_url = base_url
        self._current_token: Optional[TokenInfo] = None
        self._token_lock = Lock()
    
    def _request_new_token(self) -> Optional[TokenInfo]:
        """KIS 공식 API 스펙에 따른 토큰 발급"""
        try:
            import requests
            
            # KIS 공식 토큰 발급 API 엔드포인트
            url = f"{self.base_url}/oauth2/tokenP"
            
            # 공식 스펙에 따른 헤더
            headers = {
                "Content-Type": "application/json"
            }
            
            # 공식 스펙에 따른 요청 바디
            body = {
                "grant_type": "client_credentials",
                "appkey": self.api_config["APP_KEY"],
                "appsecret": self.api_config["APP_SECRET"]
            }
            
            # API 호출
            response = requests.post(url, headers=headers, json=body, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                
                # 응답 검증
                if "access_token" in token_data:
                    # TokenInfo 객체 생성
                    token_info = TokenInfo(
                        access_token=token_data["access_token"],
                        token_type=token_data.get("token_type", "Bearer"),
                        expires_in=token_data.get("expires_in", 86400)  # 24시간 기본값
                    )
                    
                    logger.info(f"토큰 발급 성공: {self.account_type}")
                    return token_info
                else:
                    logger.error(f"토큰 발급 응답에 access_token이 없음: {token_data}")
                    return None
            else:
                logger.error(f"토큰 발급 실패: HTTP {response.status_code}")
                try:
                    error_detail = response.json()
                    logger.error(f"오류 상세: {error_detail}")
                except:
                    logger.error(f"응답 내용: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"토큰 발급 중 예외 발생: {e}")
            return None
    
    def _save_token(self, token: TokenInfo):
        """토큰 저장 (기본 구현)"""
        # 기본적으로는 메모리에만 저장
        # 필요시 파일 저장 구현 가능
        pass
    
    def _load_token(self) -> Optional[TokenInfo]:
        """저장된 토큰 로드 (기본 구현)"""
        # 기본적으로는 None 반환
        # 필요시 파일에서 로드 구현 가능
        return None

from register_key_loader import get_api_config, validate_register_key

logger = logging.getLogger(__name__)

@dataclass
class TokenStats:
    """토큰 통계 정보"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    retry_attempts: int = 0
    auto_refreshes: int = 0
    last_request_time: Optional[datetime] = None
    last_error: Optional[str] = None


class ExponentialBackoffRetry:
    """지수백오프 재시도 전략"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay  
        self.max_delay = max_delay
        
    async def execute_with_backoff(self, func, *args, **kwargs):
        """지수백오프로 함수 실행"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"토큰 요청 시도: {attempt + 1}/{self.max_retries + 1}")
                return await self._run_sync_in_async(func, *args, **kwargs)
                
            except Exception as e:
                last_exception = e
                logger.warning(f"토큰 요청 실패 (시도 {attempt + 1}): {e}")
                
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt) + random.uniform(0, 1), self.max_delay)
                    logger.info(f"재시도 대기: {delay:.2f}초")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"모든 재시도 실패: {e}")
                    break
        
        raise last_exception if last_exception else Exception("재시도 한도 초과")
    
    async def _run_sync_in_async(self, func, *args, **kwargs):
        """동기 함수를 비동기 환경에서 실행"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)


class TokenHealthMonitor:
    """토큰 상태 모니터링"""
    
    def __init__(self):
        self.stats = TokenStats()
        self._lock = Lock()
        
    def record_request_success(self):
        """성공한 요청 기록"""
        with self._lock:
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.last_request_time = datetime.now()
            self.stats.last_error = None
            
    def record_request_failure(self, error: str):
        """실패한 요청 기록"""
        with self._lock:
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            self.stats.last_request_time = datetime.now()
            self.stats.last_error = error
            
    def record_retry_attempt(self):
        """재시도 기록"""
        with self._lock:
            self.stats.retry_attempts += 1
            
    def record_auto_refresh(self):
        """자동 갱신 기록"""
        with self._lock:
            self.stats.auto_refreshes += 1
            
    def get_success_rate(self) -> float:
        """성공률 반환"""
        with self._lock:
            if self.stats.total_requests == 0:
                return 0.0
            return (self.stats.successful_requests / self.stats.total_requests) * 100
            
    def get_stats_summary(self) -> Dict[str, Any]:
        """통계 요약 반환"""
        with self._lock:
            return {
                "success_rate": f"{self.get_success_rate():.1f}%",
                "total_requests": self.stats.total_requests,
                "successful_requests": self.stats.successful_requests,
                "failed_requests": self.stats.failed_requests,
                "retry_attempts": self.stats.retry_attempts,
                "auto_refreshes": self.stats.auto_refreshes,
                "last_request": self.stats.last_request_time.isoformat() if self.stats.last_request_time else None,
                "last_error": self.stats.last_error
            }


class EnhancedTokenManager(KISTokenManager):
    """개선된 토큰 관리자 (Register_Key.md 통합)"""
    
    def __init__(self, account_type: str, api_config: Dict[str, str] = None, base_url: str = None):
        """개선된 토큰 관리자 초기화 (Register_Key.md 자동 로드)"""
        
        # Register_Key.md에서 설정 자동 로드
        if api_config is None or base_url is None:
            logger.info(f"Register_Key.md에서 {account_type} 설정 자동 로드")
            
            # 설정 유효성 먼저 검증
            if not validate_register_key():
                raise ValueError("Register_Key.md 설정이 유효하지 않습니다")
            
            # 계정 타입별 설정 로드
            auto_config = get_api_config(account_type)
            api_config = {
                "APP_KEY": auto_config["APP_KEY"],
                "APP_SECRET": auto_config["APP_SECRET"]
            }
            base_url = auto_config["REST_URL"]
            
            logger.info(f"✅ Register_Key.md 설정 로드 완료: {account_type}")
            logger.debug(f"- APP_KEY: {api_config['APP_KEY'][:8]}...")
            logger.debug(f"- BASE_URL: {base_url}")
        
        # 부모 클래스 초기화
        super().__init__(account_type, api_config, base_url)
        
        # 개선 기능 초기화
        self.retry_strategy = ExponentialBackoffRetry(max_retries=3, base_delay=1.0, max_delay=15.0)
        self.health_monitor = TokenHealthMonitor()
        self._preemptive_refresh_enabled = True
        self._preemptive_refresh_minutes = 30  # 만료 30분 전 자동 갱신
        self._background_refresh_task = None
        
        logger.info(f"Enhanced TokenManager 초기화 완료: {account_type}")
        logger.info(f"- 지수백오프 재시도: 최대 3회")
        logger.info(f"- 자동 갱신: 만료 {self._preemptive_refresh_minutes}분 전")
        logger.info(f"- 건강상태 모니터링: 활성화")
        
    async def get_valid_token_async(self) -> Optional[str]:
        """비동기 토큰 요청 (개선된 버전)"""
        try:
            # 현재 토큰 상태 확인
            current_token = await self._get_current_token_async()
            
            if current_token and not current_token.is_expired():
                # 만료 임박시 백그라운드 갱신 시작
                if current_token.is_near_expiry(self._preemptive_refresh_minutes):
                    self._start_background_refresh()
                
                self.health_monitor.record_request_success()
                return current_token.access_token
            
            # 토큰이 없거나 만료된 경우 새로 발급
            logger.info("토큰 새로 발급 필요")
            new_token = await self._request_new_token_with_retry()
            
            if new_token:
                self._current_token = new_token
                self._save_token(new_token)
                self.health_monitor.record_request_success()
                return new_token.access_token
            else:
                self.health_monitor.record_request_failure("토큰 발급 실패")
                return None
                
        except Exception as e:
            error_msg = f"토큰 요청 중 오류: {e}"
            logger.error(error_msg)
            self.health_monitor.record_request_failure(error_msg)
            return None
    
    async def _get_current_token_async(self) -> Optional[TokenInfo]:
        """현재 토큰 비동기 확인"""
        if self._current_token is None:
            # 토큰 파일에서 로드 시도
            self._current_token = self._load_token()
        
        return self._current_token
    
    async def _request_new_token_with_retry(self) -> Optional[TokenInfo]:
        """재시도 로직을 포함한 토큰 발급"""
        try:
            # 지수백오프 재시도로 토큰 요청
            token_info = await self.retry_strategy.execute_with_backoff(
                self._request_new_token_sync
            )
            
            logger.info("토큰 발급 성공 (재시도 포함)")
            return token_info
            
        except Exception as e:
            logger.error(f"모든 재시도 실패: {e}")
            return None
    
    def _request_new_token_sync(self) -> Optional[TokenInfo]:
        """동기 방식 토큰 발급 (재시도 대상)"""
        try:
            # 부모 클래스의 토큰 발급 메서드 호출
            return super()._request_new_token()
            
        except Exception as e:
            # 재시도를 위해 예외 재발생
            self.health_monitor.record_retry_attempt()
            raise e
    
    def _start_background_refresh(self):
        """백그라운드 토큰 갱신 시작"""
        if self._background_refresh_task is None or self._background_refresh_task.done():
            logger.info("백그라운드 토큰 갱신 시작")
            loop = asyncio.get_event_loop()
            self._background_refresh_task = loop.create_task(self._background_refresh())
    
    async def _background_refresh(self):
        """백그라운드에서 토큰 갱신"""
        try:
            await asyncio.sleep(2)  # 잠시 대기 후 갱신
            
            logger.info("백그라운드 토큰 갱신 시도")
            new_token = await self._request_new_token_with_retry()
            
            if new_token:
                with self._token_lock:
                    self._current_token = new_token
                    self._save_token(new_token)
                
                self.health_monitor.record_auto_refresh()
                logger.info("백그라운드 토큰 갱신 완료")
            else:
                logger.warning("백그라운드 토큰 갱신 실패")
                
        except Exception as e:
            logger.error(f"백그라운드 토큰 갱신 오류: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """토큰 관리자 건강상태 반환"""
        current_token = self._current_token
        
        return {
            "token_status": {
                "exists": current_token is not None,
                "valid": current_token is not None and not current_token.is_expired() if current_token else False,
                "expires_at": current_token.expires_at.isoformat() if current_token else None,
                "near_expiry": current_token.is_near_expiry(self._preemptive_refresh_minutes) if current_token else False,
                "time_until_expiry": str(current_token.expires_at - datetime.now()) if current_token else None
            },
            "performance_stats": self.health_monitor.get_stats_summary(),
            "configuration": {
                "account_type": self.account_type,
                "preemptive_refresh_enabled": self._preemptive_refresh_enabled,
                "preemptive_refresh_minutes": self._preemptive_refresh_minutes,
                "max_retries": self.retry_strategy.max_retries,
                "base_delay": self.retry_strategy.base_delay,
                "max_delay": self.retry_strategy.max_delay
            }
        }
    
    def get_valid_token_sync(self) -> Optional[str]:
        """동기 방식 토큰 요청 (기존 호환성)"""
        try:
            # 이벤트 루프가 있으면 비동기로 실행
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 이미 실행중인 루프에서는 새 태스크 생성
                future = asyncio.ensure_future(self.get_valid_token_async())
                # 간단한 폴링으로 결과 대기 (비동기 환경에서)
                while not future.done():
                    time.sleep(0.1)
                return future.result()
            else:
                # 새로운 이벤트 루프에서 실행
                return loop.run_until_complete(self.get_valid_token_async())
                
        except RuntimeError:
            # 이벤트 루프가 없는 경우 새로 생성
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.get_valid_token_async())
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"동기 토큰 요청 실패: {e}")
            return None


# 팩토리 함수 (Register_Key.md 자동 로드)
def create_enhanced_token_manager(account_type: str, api_config: Dict[str, str] = None, base_url: str = None) -> EnhancedTokenManager:
    """개선된 토큰 관리자 생성 (Register_Key.md 자동 로드)"""
    return EnhancedTokenManager(account_type, api_config, base_url)


# 테스트용 래퍼 함수
async def test_enhanced_token_manager():
    """개선된 토큰 관리자 테스트 (Register_Key.md 사용)"""
    try:
        print("=== Enhanced Token Manager 테스트 (Register_Key.md 연동) ===")
        
        # Register_Key.md에서 자동으로 설정 로드
        print("1. Register_Key.md에서 모의투자 설정 로드...")
        manager = create_enhanced_token_manager("MOCK")
        
        # 건강상태 확인
        health = manager.get_health_status()
        print("=== Enhanced Token Manager 상태 ===")
        print(f"토큰 존재: {health['token_status']['exists']}")
        print(f"토큰 유효: {health['token_status']['valid']}")
        print(f"성공률: {health['performance_stats']['success_rate']}")
        print(f"총 요청: {health['performance_stats']['total_requests']}")
        print(f"자동 갱신: {health['performance_stats']['auto_refreshes']}")
        
        return health
        
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        return None


if __name__ == "__main__":
    # 간단한 테스트 실행
    async def main():
        print("Enhanced Token Manager 테스트 시작...")
        result = await test_enhanced_token_manager()
        if result:
            print("테스트 완료!")
        else:
            print("테스트 실패!")
    
    asyncio.run(main())