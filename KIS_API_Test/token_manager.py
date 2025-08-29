#!/usr/bin/env python3
"""
KIS API 토큰 관리 시스템
- 실전투자/모의투자 토큰 완전 분리
- 자정 자동 토큰 파기
- 만료 시간 체크 및 자동 갱신
"""

import os
import json
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from threading import Lock

logger = logging.getLogger(__name__)

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
    
    def is_same_day(self) -> bool:
        """토큰이 오늘 발급되었는지 확인"""
        return self.issued_at.date() == datetime.now().date()
    
    def is_midnight_passed(self) -> bool:
        """발급일 자정이 지났는지 확인"""
        midnight = self.issued_at.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return datetime.now() >= midnight


class KISTokenManager:
    """KIS API 토큰 관리자"""
    
    def __init__(self, account_type: str, api_config: Dict[str, str], base_url: str):
        """
        토큰 관리자 초기화
        
        Args:
            account_type: "MOCK" 또는 "REAL"
            api_config: API 설정 (APP_KEY, APP_SECRET 포함)
            base_url: API 기본 URL
        """
        self.account_type = account_type.upper()
        self.api_config = api_config
        self.base_url = base_url
        self._token_lock = Lock()
        self._current_token: Optional[TokenInfo] = None
        
        # 토큰 저장 디렉토리 설정
        self.token_dir = Path(".token_cache")
        self.token_dir.mkdir(exist_ok=True)
        
        # 토큰 파일 경로 설정 (계좌 타입별 분리)
        self.token_file = self.token_dir / f"token_{self.account_type.lower()}_{datetime.now().strftime('%Y%m%d')}.json"
        
        # 연결정보 캐시 파일 (변경 감지용)
        self.connection_cache_file = self.token_dir / f"connection_{self.account_type.lower()}.json"
        
        # 토큰 자동 갱신 시스템 연동
        self.auto_refresher = None
        try:
            from support.token_auto_refresher import get_token_refresher
            self.auto_refresher = get_token_refresher()
            logger.debug(f"토큰 자동 갱신 시스템 연동 성공")
        except Exception as e:
            logger.warning(f"토큰 자동 갱신 시스템 연동 실패: {e}")
        
        logger.info(f"토큰 관리자 초기화: {self.account_type}")
    
    def _cleanup_old_tokens(self):
        """이전 날짜의 토큰 파일들 정리"""
        try:
            today = datetime.now().strftime('%Y%m%d')
            pattern = f"token_{self.account_type.lower()}_*.json"
            
            for token_file in self.token_dir.glob(pattern):
                # 오늘 날짜가 아닌 토큰 파일 삭제
                if today not in token_file.name:
                    logger.info("이전 토큰 파일 삭제")
                    token_file.unlink(missing_ok=True)
                    
        except Exception as e:
            logger.warning(f"이전 토큰 파일 정리 중 오류: {e}")
    
    def _check_connection_info_changed(self) -> bool:
        """연결정보 변경 여부 확인"""
        try:
            current_config = {
                "app_key": self.api_config.get("APP_KEY", ""),
                "app_secret": self.api_config.get("APP_SECRET", ""),
                "base_url": self.base_url
            }
            
            if not self.connection_cache_file.exists():
                # 최초 실행시 현재 설정 저장
                self._save_connection_info(current_config)
                return False
            
            with open(self.connection_cache_file, 'r', encoding='utf-8') as f:
                cached_config = json.load(f)
            
            # 중요한 연결 정보 변경 검사
            if (current_config["app_key"] != cached_config.get("app_key", "") or
                current_config["app_secret"] != cached_config.get("app_secret", "") or
                current_config["base_url"] != cached_config.get("base_url", "")):
                
                logger.info(f"{self.account_type} 연결정보 변경 감지")
                self._save_connection_info(current_config)
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"연결정보 변경 감지 실패: {e}")
            return False
    
    def _save_connection_info(self, config: Dict[str, str]):
        """연결정보 캐시 저장"""
        try:
            with open(self.connection_cache_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"연결정보 캐시 저장 실패: {e}")
    
    def _invalidate_token_on_config_change(self):
        """연결정보 변경 시 토큰 무효화"""
        if self._check_connection_info_changed():
            logger.info(f"{self.account_type} 연결정보 변경으로 토큰 무효화")
            self._current_token = None
            
            # 기존 토큰 파일 삭제
            if self.token_file.exists():
                self.token_file.unlink()
                logger.info(f"기존 토큰 파일 삭제: {self.token_file}")
            
            # 자동 갱신 시스템에 강제 갱신 요청
            if self.auto_refresher:
                try:
                    import asyncio
                    asyncio.create_task(self.auto_refresher.force_refresh_tokens())
                    logger.info("토큰 자동 갱신 시스템에 강제 갱신 요청")
                except Exception as e:
                    logger.warning(f"강제 토큰 갱신 요청 실패: {e}")
            
            return True
        return False
    
    def _save_token(self, token_info: TokenInfo):
        """토큰 정보를 파일에 저장"""
        try:
            token_data = {
                "access_token": token_info.access_token,
                "token_type": token_info.token_type,
                "expires_in": token_info.expires_in,
                "issued_at": token_info.issued_at.isoformat(),
                "expires_at": token_info.expires_at.isoformat()
            }
            
            with open(self.token_file, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=2, ensure_ascii=False)
                
            logger.info("토큰 저장 완료")
            
        except Exception as e:
            logger.error(f"토큰 저장 실패: {e}")
    
    def _load_token(self) -> Optional[TokenInfo]:
        """저장된 토큰 정보 로드"""
        try:
            if not self.token_file.exists():
                logger.info("토큰 파일 없음 - 새 토큰 발급 필요")
                return None
            
            with open(self.token_file, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
            
            # TokenInfo 객체 생성
            token_info = TokenInfo(
                access_token=token_data['access_token'],
                token_type=token_data.get('token_type', 'Bearer'),
                expires_in=token_data.get('expires_in', 86400),
                issued_at=datetime.fromisoformat(token_data['issued_at']),
                expires_at=datetime.fromisoformat(token_data['expires_at'])
            )
            
            logger.info("토큰 로드 완료")
            return token_info
            
        except Exception as e:
            logger.warning(f"토큰 로드 실패: {e}")
            return None
    
    def _request_new_token(self) -> Optional[TokenInfo]:
        """새 토큰 발급 요청"""
        try:
            token_url = f"{self.base_url}/oauth2/tokenP"
            
            token_data = {
                "grant_type": "client_credentials",
                "appkey": self.api_config['APP_KEY'],
                "appsecret": self.api_config['APP_SECRET']
            }
            
            headers = {
                "content-type": "application/json"
            }
            
            logger.info(f"새 토큰 발급 요청: {self.account_type}")
            
            response = requests.post(token_url, headers=headers, json=token_data, timeout=10)
            
            # HTTP 응답 상세 로깅 (오류 진단용) - 민감한 정보 제거
            logger.debug("토큰 발급 응답 수신 완료")
            
            if response.status_code != 200:
                logger.error("토큰 발급 HTTP 오류 발생")
                logger.error("토큰 발급 요청이 실패했습니다")
                return None
            
            result = response.json()
            
            if 'access_token' not in result:
                logger.error(f"토큰 발급 응답에 access_token 없음: {result}")
                return None
            
            # TokenInfo 객체 생성
            token_info = TokenInfo(
                access_token=result['access_token'],
                token_type=result.get('token_type', 'Bearer'),
                expires_in=result.get('expires_in', 86400)
            )
            
            logger.info(f"새 토큰 발급 성공: {self.account_type}")
            return token_info
            
        except Exception as e:
            logger.error(f"토큰 발급 실패: {e}")
            return None
    
    def get_valid_token(self) -> Optional[str]:
        """유효한 토큰 반환 (필요시 자동 갱신)"""
        with self._token_lock:
            # 1. 이전 토큰 파일들 정리
            self._cleanup_old_tokens()
            
            # 2. 연결정보 변경 확인 및 토큰 무효화
            self._invalidate_token_on_config_change()
            
            # 3. 현재 토큰 확인
            if self._current_token is None:
                self._current_token = self._load_token()
            
            # 3. 토큰 유효성 검사
            if self._current_token is not None:
                # 자정이 지났으면 토큰 파기
                if self._current_token.is_midnight_passed():
                    logger.info(f"자정 경과로 토큰 파기: {self.account_type}")
                    self._current_token = None
                    if self.token_file.exists():
                        self.token_file.unlink()
                
                # 토큰 만료 확인
                elif self._current_token.is_expired():
                    logger.info(f"토큰 만료로 갱신 필요: {self.account_type}")
                    self._current_token = None
                
                # 토큰 만료 임박 확인 (30분 전)
                elif self._current_token.is_near_expiry():
                    logger.info(f"토큰 만료 임박으로 갱신: {self.account_type}")
                    self._current_token = None
            
            # 4. 새 토큰 발급 (필요한 경우)
            if self._current_token is None:
                logger.info(f"새 토큰 발급 시작: {self.account_type}")
                self._current_token = self._request_new_token()
                
                if self._current_token is not None:
                    # 토큰 저장
                    self._save_token(self._current_token)
                else:
                    logger.error(f"토큰 발급 실패: {self.account_type}")
                    return None
            
            # 5. 유효한 토큰 반환
            if self._current_token is not None:
                logger.debug(f"유효한 토큰 반환: {self.account_type}")
                return self._current_token.access_token
            
            return None
    
    def force_refresh_token(self) -> Optional[str]:
        """강제 토큰 갱신"""
        with self._token_lock:
            logger.info(f"강제 토큰 갱신: {self.account_type}")
            
            # 기존 토큰 파기
            self._current_token = None
            if self.token_file.exists():
                self.token_file.unlink()
            
            # 새 토큰 발급
            return self.get_valid_token()
    
    def get_token_info(self) -> Optional[Dict[str, Any]]:
        """현재 토큰 정보 반환"""
        if self._current_token is not None:
            return {
                "account_type": self.account_type,
                "issued_at": self._current_token.issued_at,
                "expires_at": self._current_token.expires_at,
                "is_expired": self._current_token.is_expired(),
                "is_near_expiry": self._current_token.is_near_expiry(),
                "is_midnight_passed": self._current_token.is_midnight_passed()
            }
        return None
    
    def cleanup(self):
        """리소스 정리"""
        logger.info(f"토큰 관리자 정리: {self.account_type}")


class TokenManagerFactory:
    """토큰 관리자 팩토리"""
    
    _instances: Dict[str, KISTokenManager] = {}
    _lock = Lock()
    
    @classmethod
    def get_token_manager(cls, account_type: str, api_config: Dict[str, str], base_url: str) -> KISTokenManager:
        """토큰 관리자 인스턴스 반환 (싱글톤 패턴)"""
        with cls._lock:
            key = f"{account_type}_{base_url}"
            
            if key not in cls._instances:
                cls._instances[key] = KISTokenManager(account_type, api_config, base_url)
                logger.info(f"새 토큰 관리자 생성: {account_type}")
            
            return cls._instances[key]
    
    @classmethod
    def cleanup_all(cls):
        """모든 토큰 관리자 정리"""
        with cls._lock:
            for manager in cls._instances.values():
                manager.cleanup()
            cls._instances.clear()