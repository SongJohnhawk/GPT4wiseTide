"""
KIS (Korea Investment & Securities) API Connector
한국투자증권 OpenAPI 연동을 위한 API 커넥터

주요 기능:
- OAuth 토큰 관리 (발급/갱신/폐기)
- REST API 호출
- WebSocket 실시간 데이터 연결
- 해시키 생성 및 보안 처리
"""

import json
import hashlib
import hmac
import time
import asyncio
from datetime import datetime, timedelta, date
from time import sleep
from typing import Dict, Optional, Any
import random
from support.token_manager import TokenManagerFactory
from support.token_auto_refresher import get_token_refresher, get_valid_token

# 깔끔한 콘솔 로거 사용
from support.clean_console_logger import (
    get_clean_logger, Phase, log as clean_log
)

# Fast Token Manager 기능 추가 (KIS 공식 스펙 최적화)
try:
    import sys
    from pathlib import Path
    # KIS_API_Test 폴더에서 Fast Token Manager import
    kis_test_path = Path(__file__).parent.parent / "KIS_API_Test"
    if kis_test_path.exists():
        sys.path.insert(0, str(kis_test_path))
        from fast_token_manager import create_fast_token_manager
        FAST_TOKEN_MANAGER_AVAILABLE = True
        # Fast Token Manager 활성화 (로그 제거 - 내부 기능)
    else:
        FAST_TOKEN_MANAGER_AVAILABLE = False
        # Fast Token Manager 사용 불가 (로그 제거)
except ImportError as e:
    FAST_TOKEN_MANAGER_AVAILABLE = False
    # Fast Token Manager import 실패 (로그 제거)
import threading
import os

import requests
import yaml
from support.log_manager import get_log_manager

# 로그 매니저를 통한 로거 설정
log_manager = get_log_manager()
logger = log_manager.setup_logger('system', __name__)


class RateLimiter:
    """API 요청 빈도 제한 (한투서버 정책 기반)"""
    
    def __init__(self, max_requests: int = 2, time_window: int = 1):
        """
        Args:
            max_requests: 시간 창 내 최대 요청 수 (한투: 초당 2-5건, 안전하게 2건)
            time_window: 시간 창(초)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = threading.Lock()
        self.call_count = 0
        self.error_count = 0
        self.rate_limit_count = 0
    
    async def wait_if_needed(self):
        """필요시 대기 (한투서버 정책 준수)"""
        with self.lock:
            now = time.time()
            
            # 시간 창 밖의 요청 제거
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            # 요청 한도 확인
            if len(self.requests) >= self.max_requests:
                # 가장 오래된 요청이 시간 창을 벗어날 때까지 대기
                sleep_time = self.time_window - (now - self.requests[0]) + 0.1
                if sleep_time > 0:
                    # Rate limit 대기 (로그 제거)
                    await asyncio.sleep(sleep_time)
                    
                    # 대기 후 요청 목록 재정리
                    now = time.time()
                    self.requests = [req_time for req_time in self.requests 
                                   if now - req_time < self.time_window]
            
            # 현재 요청 기록
            self.requests.append(now)
    
    def record_call(self, status_code: int):
        """API 호출 결과 기록 (통계 및 모니터링용)"""
        with self.lock:
            self.call_count += 1
            
            if status_code == 429:
                self.rate_limit_count += 1
                clean_log(f"API Rate Limit: {self.rate_limit_count}회", "WARNING")
            elif status_code >= 400:
                self.error_count += 1
                # API 오류 발생 (로그 제거 - 대량 메시지)
                pass
            elif status_code == 200:
                # API 성공 호출 (로그 제거 - 대량 메시지)
                pass
    
    def get_stats(self) -> Dict[str, int]:
        """호출 통계 반환"""
        with self.lock:
            return {
                "total_calls": self.call_count,
                "error_calls": self.error_count,
                "rate_limit_calls": self.rate_limit_count,
                "success_calls": self.call_count - self.error_count
            }


class KISAPIError(Exception):
    """KIS API 관련 예외"""
    
    def __init__(self, message: str, error_code: str = None, response_data: Dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.response_data = response_data


class KISAPIConnector:
    """한국투자증권 OpenAPI 커넥터"""
    
    def __init__(self, config_path: str = "", is_mock: bool = True):
        """
        API 커넥터 초기화
        
        Args:
            config_path: 설정 파일 경로
            is_mock: 모의투자 여부
        """
        self.config = self._load_config(config_path)
        self.websocket_approval_key: Optional[str] = None
        self.is_mock = is_mock
        
        # 실시간성 보장을 위해 캐시 제거 - 항상 실시간 조회
        
        # API 엔드포인트 설정 (Register_Key.md에서 실시간 로드)
        try:
            from support.authoritative_register_key_loader import get_authoritative_loader
            loader = get_authoritative_loader()
            urls_config = loader.get_fresh_urls()
            
            if is_mock:
                self.base_url = urls_config.get('mock_rest')
                if not self.base_url:
                    raise APIConnectionError("모의투자 서버 URL이 Register_Key.md에 설정되지 않았습니다")
                self.account_type = "MOCK"
                # 보안상 서버 주소 노출 차단
                # logger.info(f"모의투자 서버로 연결 설정: {self.base_url}")
                clean_log("모의투자 서버 연결 완룼", "SUCCESS")
            else:
                self.base_url = urls_config.get('real_rest')
                if not self.base_url:
                    raise APIConnectionError("실계좌 서버 URL이 Register_Key.md에 설정되지 않았습니다")
                self.account_type = "REAL"
                # 보안상 서버 주소 노출 차단
                # logger.info(f"실계좌 서버로 연결 설정: {self.base_url}")
                clean_log("실계좌 서버 연결 완료", "SUCCESS")
                
        except Exception as e:
            # Register_Key.md 로드 실패시 즉시 실패 - 백업 없음
            clean_log(f"API 설정 로드 실패: {str(e)[:100]}...", "ERROR")
            raise APIConnectionError(f"Register_Key.md 파일이 필요합니다. 설정을 확인해주세요: {e}")
        
        # 실계좌/모의투자별 설정 적용
        self._apply_account_specific_config()
        
        # 토큰 관리자 초기화 (Enhanced 버전 우선 사용)
        token_config = self._get_token_config()
        
        if FAST_TOKEN_MANAGER_AVAILABLE:
            try:
                # Fast Token Manager 사용 (KIS 공식 스펙 최적화)
                self.token_manager = create_fast_token_manager(
                    account_type=self.account_type
                )
                self._using_fast_manager = True
                logger.info(f"Fast Token Manager 초기화 완료: {self.account_type}")
            except Exception as e:
                logger.warning(f"Fast Token Manager 초기화 실패, 기존 방식 사용: {e}")
                self.token_manager = TokenManagerFactory.get_token_manager(
                    account_type=self.account_type,
                    api_config=token_config,
                    base_url=self.base_url
                )
                self._using_fast_manager = False
        else:
            # 기존 토큰 관리자 사용
            self.token_manager = TokenManagerFactory.get_token_manager(
                account_type=self.account_type,
                api_config=token_config,
                base_url=self.base_url
            )
            self._using_fast_manager = False
        if hasattr(self, 'use_virtual_keys') and self.use_virtual_keys:
            logger.debug(f"토큰 관리자 초기화 완료: {self.account_type} (모의투자 전용 키 사용)")
        else:
            logger.debug(f"토큰 관리자 초기화 완료: {self.account_type} (실전용 키 사용)")
        
        # 세션 설정 (기본 헤더 최소화)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "tideWise/1.0"
        })
        
        # Rate Limiter 설정 (모의투자는 더 보수적으로)
        if is_mock:
            # 모의투자: 초당 1회 요청으로 매우 보수적 설정 (KIS 모의투자 서버가 더 엄격)
            self.rate_limiter = RateLimiter(max_requests=1, time_window=2)  # 2초에 1회
            logger.debug("모의투자용 Rate Limiter: 2초당 1회 요청")
        else:
            # 실전투자: 초당 2회 요청
            self.rate_limiter = RateLimiter(max_requests=2, time_window=1)  # 1초에 2회
            logger.debug("실전투자용 Rate Limiter: 1초당 2회 요청")
    
    async def initialize(self) -> bool:
        """API 커넥터 초기화 (비동기 호환성)
        
        Returns:
            bool: 초기화 성공 여부
        """
        try:
            # __init__에서 이미 대부분의 초기화가 완료됨
            # 추가적인 초기화 작업이 필요하면 여기에 추가
            
            # 토큰 유효성 간단 체크 (선택사항)
            if hasattr(self, 'token_manager') and self.token_manager:
                logger.debug(f"KIS API 커넥터 초기화 완료: {self.account_type}")
                return True
            else:
                logger.warning("토큰 관리자 초기화 실패")
                return False
                
        except Exception as e:
            logger.error(f"KIS API 커넥터 초기화 오류: {e}")
            return False
    
    def _apply_account_specific_config(self):
        """실계좌/모의투자별 설정 적용"""
        if "MOCK_CONFIG" in self.config and "REAL_CONFIG" in self.config:
            # 분리된 설정 구조인 경우
            if self.is_mock:
                account_config = self.config["MOCK_CONFIG"]
                logger.debug("모의투자 전용 설정 적용")
                
                # 모의투자 전용 키 확인 및 적용
                if account_config.get("VIRTUAL_APP_KEY") and account_config.get("VIRTUAL_APP_SECRET"):
                    # 모의투자 전용 키가 있으면 사용
                    logger.debug("모의투자 전용 API 키 사용")
                    self.use_virtual_keys = True
                else:
                    # 모의투자 전용 키가 없으면 실전용 키 사용 (기존 방식)
                    logger.debug("모의투자: 실전 계좌 API 사용 (정상 동작)")
                    self.use_virtual_keys = False
            else:
                account_config = self.config["REAL_CONFIG"]
                logger.debug("실계좌 전용 설정 적용")
                self.use_virtual_keys = False
            
            # 계좌별 설정으로 기본 설정 덮어쓰기
            for key, value in account_config.items():
                self.config[key] = value
                logger.debug(f"계좌별 설정 적용: {key}")
            
            # 계좌번호 검증 및 표준화
            self._validate_account_number()
        else:
            # 기존 단일 설정 구조
            logger.debug("기존 통합 설정 사용")
            self.use_virtual_keys = False
            self._validate_account_number()
    
    def _get_token_config(self) -> Dict[str, str]:
        """토큰 발급용 설정 반환 (모의투자 전용 키 적용)"""
        if hasattr(self, 'use_virtual_keys') and self.use_virtual_keys and self.is_mock:
            # 모의투자 전용 키 사용
            return {
                'APP_KEY': self.config.get('VIRTUAL_APP_KEY', ''),
                'APP_SECRET': self.config.get('VIRTUAL_APP_SECRET', ''),
                'VIRTUAL_ID': self.config.get('VIRTUAL_ID', 'Handler1')
            }
        else:
            # 실전용 키 사용 (기존 방식)
            return {
                'APP_KEY': self.config.get('APP_KEY', ''),
                'APP_SECRET': self.config.get('APP_SECRET', '')
            }
    
    def _validate_account_number(self):
        """계좌번호 형식 검증 및 표준화 (KIS API 호환)"""
        account_num = self.config.get("CANO", "")
        
        # KIS API는 8자리 계좌번호 + 2자리 상품코드로 분리 사용
        if account_num and "-" in account_num:
            # 계좌번호-상품코드 분리 (예: 계좌번호-01 → 계좌번호:8자리, 상품코드:2자리)
            parts = account_num.split("-")
            if len(parts) == 2:
                clean_account = parts[0]  # 8자리 계좌번호만 사용
                product_code = parts[1]   # 2자리 상품코드
                self.config["CANO"] = clean_account
                self.config["ACNT_PRDT_CD"] = product_code
                logger.debug(f"계좌번호 KIS API 형식 변환: {account_num} → 계좌번호:{clean_account}, 상품코드:{product_code}")
            else:
                # 하이픈이 있지만 형식이 잘못된 경우
                clean_account = account_num.replace("-", "")
                self.config["CANO"] = clean_account
                logger.warning(f"계좌번호 형식 오류, 하이픈만 제거: {account_num} → {clean_account}")
        
        # 계좌번호 타입 로깅
        final_account = self.config.get("CANO", "")
        product_code = self.config.get("ACNT_PRDT_CD", "01")
        account_type = "모의투자" if self.is_mock else "실계좌"
        logger.debug(f"{account_type} 계좌번호: {final_account}, 상품코드: {product_code}")
        
        # 계좌번호를 인스턴스 속성으로 저장 (전체 번호 포함)
        self.account_number = final_account
        
        # 토큰 관리자로 교체됨 - 초기화 완료
        
        logger.debug("KIS API Connector initialized successfully")
    
    def _load_config_from_register_key(self) -> Dict[str, Any]:
        """Register_Key.md 파일에서 설정 로드 (기존 register_key_reader 사용)"""
        try:
            from support.authoritative_register_key_loader import get_authoritative_loader
            loader = get_authoritative_loader()
            
            # 실전투자 설정 (실시간 로드)
            real_config = loader.get_fresh_config("REAL")
            # 모의투자 설정 (실시간 로드)
            mock_config = loader.get_fresh_config("MOCK")
            # 텔레그램 설정 (실시간 로드)
            telegram_config = loader.get_fresh_telegram_config()
            # KRX 설정은 현재 AuthoritativeRegisterKeyLoader에서 지원하지 않으므로 빈 딕셔너리로 설정
            krx_config = {}
            # URL 설정 (실시간 로드)
            url_config = loader.get_fresh_urls()
            
            config = {}
            
            # 실전투자 설정
            if real_config:
                config["REAL_CONFIG"] = {
                    "CANO": real_config.get('account_number', ''),
                    "ACNT_PRDT_CD": "01",
                    "ACNT_PASS_WD": real_config.get('account_password', ''),
                    "APP_KEY": real_config.get('app_key', ''),
                    "APP_SECRET": real_config.get('app_secret', '')
                }
            
            # 모의투자 설정
            if mock_config:
                config["MOCK_CONFIG"] = {
                    "CANO": mock_config.get('account_number', ''),
                    "ACNT_PRDT_CD": "01",
                    "ACNT_PASS_WD": mock_config.get('account_password', ''),
                    "APP_KEY": mock_config.get('app_key', ''),
                    "APP_SECRET": mock_config.get('app_secret', '')
                }
                
                # 하위 호환성을 위한 기본 설정 (모의투자 기본값)
                config.update({
                    "CANO": mock_config.get('account_number', ''),
                    "ACNT_PRDT_CD": "01",
                    "ACNT_PASS_WD": mock_config.get('account_password', ''),
                    "APP_KEY": mock_config.get('app_key', ''),
                    "APP_SECRET": mock_config.get('app_secret', '')
                })
            
            # 텔레그램 설정
            if telegram_config:
                config["TELEGRAM_BOT_TOKEN"] = telegram_config.get('bot_token', '')
                config["TELEGRAM_CHAT_ID"] = telegram_config.get('chat_id', '')
            
            # KRX API 설정
            if krx_config:
                config["KRX_API_KEY"] = krx_config.get('api_key', '')
            
            # URL 설정 추가 (기본값은 모의투자)
            if url_config:
                config["URL_BASE"] = url_config.get('mock_rest')
                if not config["URL_BASE"]:
                    raise APIConnectionError("모의투자 서버 URL이 설정되지 않았습니다")
                config["WEBSOCKET_URL"] = url_config.get('mock_websocket', 'ws://ops.koreainvestment.com:21000')
                config["REAL_URL_BASE"] = url_config.get('real_rest')
                if not config["REAL_URL_BASE"]:
                    raise APIConnectionError("실계좌 서버 URL이 설정되지 않았습니다")
                config["REAL_WEBSOCKET_URL"] = url_config.get('real_websocket', 'ws://ops.koreainvestment.com:21000')
            else:
                raise APIConnectionError("Register_Key.md에서 모의투자 서버 URL을 로드할 수 없습니다")
                config["WEBSOCKET_URL"] = "ws://ops.koreainvestment.com:21000"
                raise APIConnectionError("Register_Key.md에서 실계좌 서버 URL을 로드할 수 없습니다")
                config["REAL_WEBSOCKET_URL"] = "ws://ops.koreainvestment.com:21000"
            
            return config
            
        except Exception as e:
            raise ValueError(f"Error loading from Register_Key.md: {e}")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """설정 파일 로드 - Register_Key.md만 사용"""
        try:
            # Register_Key.md에서만 로드
            return self._load_config_from_register_key()
        except Exception as register_error:
            logger.error(f"Register_Key.md 로드 실패: {register_error}")
            raise ValueError(f"Register_Key.md 파일이 필요합니다. 파일 위치: Policy/Register_Key/Register_Key.md")
    
    # 기존 토큰 관련 메서드들은 새로운 토큰 관리자로 대체됨
    
    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        액세스 토큰 획득 (Fast Token Manager 우선 사용)
        
        Args:
            force_refresh: 강제 갱신 여부
            
        Returns:
            액세스 토큰
        """
        try:
            # Fast Token Manager 사용 가능하면 우선 사용
            if self._using_fast_manager and hasattr(self.token_manager, 'get_valid_token'):
                try:
                    if force_refresh:
                        token = self.token_manager.force_refresh()
                    else:
                        token = self.token_manager.get_valid_token()
                    
                    if token:
                        return token
                    else:
                        logger.warning("Fast Token Manager에서 토큰 획득 실패, 기존 방식으로 재시도")
                except Exception as e:
                    logger.warning(f"Fast Token Manager 토큰 획득 실패: {e}, 기존 방식으로 재시도")
            
            # 기존 토큰 관리 시스템 사용
            account_type = "real" if not self.is_mock else "mock"
            
            # 자동 갱신 토큰 시스템 시도
            try:
                from support.token_auto_refresher import get_valid_token
                
                # 비동기 함수를 동기적으로 호출
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 이미 이벤트 루프가 실행 중인 경우 - 토큰 캐시에서 직접 조회
                        try:
                            from support.token_auto_refresher import get_token_refresher
                            refresher = get_token_refresher()
                            cached_token = refresher.get_cached_token(account_type)
                            if cached_token and cached_token.get("access_token"):
                                logger.debug(f"캐시된 토큰 사용: {self.account_type}")
                                return cached_token["access_token"]
                        except Exception:
                            pass
                        
                        # 토큰 요청
                        try:
                            token = loop.run_until_complete(get_valid_token(account_type))
                            if token:
                                logger.debug(f"자동 갱신 토큰 획득: {self.account_type}")
                                return token
                        except RuntimeError:
                            # 새로운 이벤트 루프 생성
                            token = asyncio.run(get_valid_token(account_type))
                            if token:
                                logger.debug(f"자동 갱신 토큰 획득: {self.account_type}")
                                return token
                    else:
                        # 새로운 이벤트 루프에서 실행
                        token = asyncio.run(get_valid_token(account_type))
                        if token:
                            logger.debug(f"자동 갱신 토큰 획득: {self.account_type}")
                            return token
                except Exception as async_error:
                    logger.debug(f"비동기 토큰 획득 오류: {async_error}")
            except Exception as auto_refresh_error:
                logger.debug(f"자동 갱신 시스템 오류: {auto_refresh_error}")
            
            # 기존 토큰 매니저로 폴백
            if force_refresh:
                # 강제 갱신
                token = self.token_manager.force_refresh_token()
                logger.debug(f"강제 토큰 갱신 완료: {self.account_type}")
            else:
                # 일반 토큰 획득 (자동 갱신 포함)
                token = self.token_manager.get_valid_token()
                logger.debug(f"기존 토큰 매니저 사용: {self.account_type}")
            
            if token:
                return token
            else:
                raise ValueError("토큰 획득 실패: 유효하지 않은 응답")
                
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"네트워크 오류로 토큰 획득 실패 ({self.account_type})")
            raise ConnectionError("네트워크 연결 오류가 발생했습니다")
        except (ValueError, KeyError) as e:
            logger.error(f"토큰 데이터 오류 ({self.account_type})")
            raise ValueError("토큰 데이터 처리 중 오류가 발생했습니다")
        except Exception as e:
            logger.error(f"예상치 못한 토큰 획득 실패 ({self.account_type})")
            raise RuntimeError("토큰 획득 중 예상치 못한 오류가 발생했습니다")
    
    # _request_access_token 메서드는 토큰 관리자로 대체됨
    
    def revoke_access_token(self) -> bool:
        """액세스 토큰 폐기 (토큰 관리자 사용)"""
        try:
            # 토큰 관리자를 통한 강제 갱신으로 기존 토큰 무효화
            self.token_manager.force_refresh_token()
            logger.debug(f"토큰 무효화 완료: {self.account_type}")
            return True
        except Exception as e:
            logger.error(f"토큰 무효화 실패: {e}")
            return False
    
    def get_token_info(self) -> Optional[Dict[str, Any]]:
        """현재 토큰 정보 반환"""
        return self.token_manager.get_token_info()
    
    def cleanup(self):
        """리소스 정리"""
        try:
            # 세션 정리
            if hasattr(self, 'session'):
                self.session.close()
            
            # 토큰 관리자 정리는 팩토리에서 처리됨
            logger.debug(f"API 커넥터 정리 완료: {self.account_type}")
        except Exception as e:
            logger.warning(f"API 커넥터 정리 중 오류: {e}")
    
    def get_websocket_approval_key(self) -> str:
        """웹소켓 접속키 발급"""
        url = f"{self.base_url}/oauth2/Approval"
        
        data = {
            "grant_type": "client_credentials",
            "appkey": self.config["APP_KEY"],
            "secretkey": self.config["APP_SECRET"]  # 웹소켓용은 secretkey 사용
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            if "approval_key" not in result:
                raise KISAPIError(
                    "WebSocket approval key request failed",
                    response_data=result
                )
            
            self.websocket_approval_key = result["approval_key"]
            logger.debug("WebSocket approval key obtained")
            return self.websocket_approval_key
            
        except Exception as e:
            raise KISAPIError("WebSocket approval key request failed")
    
    def generate_hashkey(self, data: Dict[str, Any]) -> str:
        """해시키 생성"""
        url = f"{self.base_url}/uapi/hashkey"
        
        headers = {
            "content-type": "application/json; charset=utf-8",
            "appkey": self.config["APP_KEY"],
            "appsecret": self.config["APP_SECRET"]
        }
        
        try:
            response = self.session.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            if "HASH" not in result:
                raise KISAPIError(
                    "Hashkey generation failed",
                    response_data=result
                )
            
            return result["HASH"]
            
        except Exception as e:
            raise KISAPIError("Hashkey generation failed")
    
    def get_api_headers(self, tr_id: str, use_hashkey: bool = False, 
                       post_data: Dict[str, Any] = None) -> Dict[str, str]:
        """
        API 호출용 헤더 생성
        
        Args:
            tr_id: 거래 ID (TR_ID)
            use_hashkey: 해시키 사용 여부
            post_data: POST 데이터 (해시키 생성용)
            
        Returns:
            API 헤더 딕셔너리
        """
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.get_access_token()}",
            "appkey": self.config["APP_KEY"],
            "appsecret": self.config["APP_SECRET"],
            "tr_id": tr_id,
            "custtype": "P"  # 개인고객 타입 (표준 코드 기준)
        }
        
        # 해시키가 필요한 경우 생성
        if use_hashkey and post_data:
            try:
                hashkey = self.generate_hashkey(post_data)
                headers["hashkey"] = hashkey
            except Exception as e:
                logger.warning(f"Hashkey generation failed, proceeding without: {e}")
        
        return headers
    
    def get_token_health_status(self) -> Dict[str, Any]:
        """Fast Token Manager 상태 확인"""
        if self._using_fast_manager and hasattr(self.token_manager, 'get_token_status'):
            try:
                return self.token_manager.get_token_status()
            except Exception as e:
                logger.warning(f"토큰 상태 확인 실패: {e}")
                return {"status": "error", "message": str(e)}
        else:
            return {"status": "not_available", "message": "Fast Token Manager 사용 중이 아님"}
    
    def log_token_performance(self):
        """토큰 성능 로그 출력"""
        health_status = self.get_token_health_status()
        if health_status.get("status") == "not_available":
            return
            
        try:
            token_status = health_status.get('token_status', {})
            performance_stats = health_status.get('performance_stats', {})
            
            logger.info(f"=== 토큰 관리자 성능 현황 ({self.account_type}) ===")
            logger.info(f"토큰 상태 - 존재: {token_status.get('exists', False)}, 유효: {token_status.get('valid', False)}")
            logger.info(f"성능 통계 - 성공률: {performance_stats.get('success_rate', 'N/A')}, 총 요청: {performance_stats.get('total_requests', 0)}")
            logger.info(f"재시도 통계 - 재시도 횟수: {performance_stats.get('retry_attempts', 0)}, 자동 갱신: {performance_stats.get('auto_refreshes', 0)}")
            
        except Exception as e:
            logger.warning(f"성능 로그 출력 실패: {e}")
    
    async def api_call(self, method: str, endpoint: str, tr_id: str, 
                params: Dict[str, Any] = None, data: Dict[str, Any] = None,
                use_hashkey: bool = False) -> Dict[str, Any]:
        """
        API 호출 (공통 메서드)
        
        Args:
            method: HTTP 메서드 (GET, POST, PUT, DELETE)
            endpoint: API 엔드포인트
            tr_id: 거래 ID
            params: URL 파라미터
            data: POST 데이터
            use_hashkey: 해시키 사용 여부
            
        Returns:
            API 응답 데이터
        """
        # Rate Limiting 적용
        await self.rate_limiter.wait_if_needed()
        
        url = f"{self.base_url}{endpoint}"
        headers = self.get_api_headers(tr_id, use_hashkey, data)
        
        try:
            # 요청 로깅 (디버깅용) - URL 정보 제거
            logger.debug(f"API 요청: {method} [URL 숨김 처리]")
            logger.debug(f"헤더: {headers}")
            if params:
                logger.debug(f"파라미터: {params}")
            if data:
                logger.debug(f"데이터: {data}")
            
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=10)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=10)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # 응답 로깅 (디버깅용) - 민감한 정보 제거
            logger.debug("API 응답 수신 완료")
            logger.debug("응답 헤더 확인 완료")
            
            # 200이 아닌 경우에만 에러 처리
            if response.status_code != 200:
                logger.error(f"HTTP Error {response.status_code}: API 요청 실패")
                raise requests.RequestException(f"HTTP {response.status_code}")
                
            result = response.json()
            
            # API 에러 체크
            if result.get("rt_cd") not in ["0", "1"]:  # 성공 코드가 아닌 경우
                error_code = result.get("rt_cd", "Unknown")
                error_msg = result.get("msg1", "No error message")
                raise KISAPIError(
                    f"API call failed (code: {error_code}): {error_msg}",
                    error_code=error_code,
                    response_data=result
                )
            
            return result
            
        except requests.RequestException as e:
            # 500 에러 등 서버 에러에 대해 로그만 남기고 예외 발생
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"API request failed: {e.response.status_code}")
            else:
                logger.error("API network error occurred")
            raise KISAPIError("API call failed")
        except json.JSONDecodeError as e:
            raise KISAPIError(f"API response JSON decode error: {e}")
    
    async def api_call_with_retry(self, method: str, endpoint: str, tr_id: str, 
                           params: Dict[str, Any] = None, data: Dict[str, Any] = None,
                           use_hashkey: bool = False, max_retries: int = 5) -> Dict[str, Any]:
        """
        Policy 문서 기반 KIS API 호출 및 500 오류 해결
        
        Args:
            method: HTTP 메서드
            endpoint: API 엔드포인트
            tr_id: 거래 ID
            params: URL 파라미터
            data: POST 데이터
            use_hashkey: 해시키 사용 여부
            max_retries: 최대 재시도 횟수 (기본 5회)
            
        Returns:
            API 응답 데이터
        """
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(max_retries):
            try:
                # Rate Limiting 적용
                await self.rate_limiter.wait_if_needed()
                
                # Policy 문서 기반 헤더 설정
                headers = self.get_api_headers(tr_id, use_hashkey, data)
                
                # Policy 문서 기반 요청 실행 (타임아웃 10초 설정)
                if method.upper() == "GET":
                    response = self.session.get(url, headers=headers, params=params, timeout=10)
                elif method.upper() == "POST":
                    response = self.session.post(url, headers=headers, json=data, timeout=10)
                elif method.upper() == "PUT":
                    response = self.session.put(url, headers=headers, json=data, timeout=10)
                elif method.upper() == "DELETE":
                    response = self.session.delete(url, headers=headers, params=params, timeout=10)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # 한투서버 정책 기반 응답 처리
                # HTTP 429 (Rate Limit) 처리
                if response.status_code == 429:
                    self.rate_limiter.record_call(429)
                    if attempt < max_retries - 1:
                        retry_delay = min(2 ** attempt, 10)  # Exponential backoff (최대 10초)
                        logger.warning(f"Rate limit 감지 (HTTP 429), {retry_delay}초 후 재시도... ({attempt + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        raise KISAPIError("Rate limit 초과 - 최대 재시도 횟수 도달", error_code="429")
                
                # HTTP 500 (서버 오류 또는 Rate Limit) 처리
                elif response.status_code == 500:
                    # KIS API가 Rate Limit을 HTTP 500으로 응답하는 경우 확인
                    try:
                        error_response = response.json()
                        error_msg = error_response.get('msg1', '')
                        if '초당 거래건수' in error_msg or 'EGW00201' in error_response.get('msg_cd', ''):
                            # Rate Limit 초과로 판단하여 429처럼 처리
                            logger.warning(f"KIS API Rate Limit 초과 (HTTP 500): {error_msg}")
                            self.rate_limiter.record_call(429)  # Rate limit으로 기록
                            
                            if attempt < max_retries - 1:
                                retry_delay = min(2 ** attempt, 15)  # 1, 2, 4, 8, 15초로 증가
                                logger.warning(f"초당 거래건수 초과, {retry_delay}초 후 재시도... ({attempt + 1}/{max_retries})")
                                await asyncio.sleep(retry_delay)
                                continue
                            else:
                                raise KISAPIError("초당 거래건수 초과 - 최대 재시도 횟수 도달", error_code="RATE_LIMIT")
                        else:
                            # 실제 서버 오류
                            logger.error(f"KIS API 서버 오류 (HTTP 500): {error_msg}")
                    except:
                        # JSON 파싱 실패시 일반 서버 오류로 처리
                        logger.error(f"HTTP 500 서버 오류 발생: {response.text}")
                    
                    self.rate_limiter.record_call(500)
                    if attempt < max_retries - 1:
                        retry_delay = 5 * (attempt + 1)  # 5, 10, 15초로 증가
                        logger.warning(f"서버 오류 감지, {retry_delay}초 후 재시도... ({attempt + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        raise KISAPIError("서버 내부 오류 - 최대 재시도 횟수 도달", error_code="500")
                
                # HTTP 200 정상 응답 처리
                elif response.status_code == 200:
                    self.rate_limiter.record_call(200)
                    result = response.json()
                    
                    # API 에러 체크 (한투서버 응답 구조 기반)
                    rt_cd = result.get("rt_cd", "0")
                    msg1 = result.get("msg1", "")
                    
                    # Rate limit 관련 메시지 확인
                    if "제한" in msg1 or "초과" in msg1 or "many" in msg1.lower():
                        logger.warning(f"Rate limit 관련 오류 감지: {msg1}")
                        if attempt < max_retries - 1:
                            retry_delay = min(2 ** attempt, 10)
                            await asyncio.sleep(retry_delay)
                            continue
                    
                    # API 오류 코드 확인
                    if rt_cd not in ["0", "1"]:
                        error_code = rt_cd
                        error_msg = msg1
                        raise KISAPIError(
                            f"API call failed (code: {error_code}): {error_msg}",
                            error_code=error_code,
                            response_data=result
                        )
                    
                    return result
                    
                elif response.status_code == 500:
                    # Policy 문서 기반 500 오류 처리
                    wait_time = 3 * (attempt + 1)
                    print(f"서버 오류 발생, {wait_time}초 후 재시도... ({attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise KISAPIError(f"Server error 500 after {max_retries} attempts")
                        
                elif response.status_code == 429:
                    # API 호출 한도 초과
                    print("API 호출 한도 초과, 대기 필요")
                    await asyncio.sleep(60)  # 1분 대기
                    if attempt < max_retries - 1:
                        continue
                    else:
                        raise KISAPIError("Rate limit exceeded")
                        
                else:
                    print(f"예상치 못한 오류: {response.status_code}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3 * (attempt + 1))
                        continue
                    else:
                        raise KISAPIError(f"Unexpected error: {response.status_code}")
                
            except requests.exceptions.Timeout:
                print(f"요청 타임아웃 발생, 재시도 중... ({attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3 * (attempt + 1))
                    continue
                else:
                    raise KISAPIError("Request timeout")
                    
            except requests.exceptions.ConnectionError:
                print(f"연결 오류 발생, 재시도 중... ({attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3 * (attempt + 1))
                    continue
                else:
                    raise KISAPIError("Connection error")
                    
            except Exception as e:
                print(f"API 연결 오류, 재시도 중... ({attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3 * (attempt + 1))
                    continue
                else:
                    raise KISAPIError(f"API call error: {e}")
        
        raise KISAPIError(f"최대 재시도 횟수({max_retries}) 초과")
    
    def get_stock_price(self, symbol: str) -> Dict[str, Any]:
        """현재가 조회 (동기 버전 - 재시도 로직 포함)"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        tr_id = "FHKST01010100"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Rate Limiting (동기 버전)
                import time
                if hasattr(self, '_last_request_time'):
                    elapsed = time.time() - self._last_request_time
                    if elapsed < 2.0:  # 초당 0.5회 제한 (서버 안정성 향상)
                        time.sleep(2.0 - elapsed)
                self._last_request_time = time.time()
                
                headers = self.get_api_headers(tr_id, False, None)
                
                response = self.session.get(url, headers=headers, params=params, timeout=10)
                
                # HTTP 상태 코드 확인
                if response.status_code == 200:
                    result = response.json()
                    
                    # API 응답 코드 확인
                    if result.get("rt_cd") in ["0", "1"]:
                        return result
                    else:
                        error_code = result.get("rt_cd", "Unknown")
                        error_msg = result.get("msg1", "No error message")
                        logger.warning(f"현재가 조회 API 오류 (시도 {attempt + 1}/{max_retries}): {error_code} - {error_msg}")
                        
                        if attempt < max_retries - 1:
                            time.sleep(2 * (attempt + 1))  # 재시도 간격
                            continue
                        else:
                            raise KISAPIError(f"현재가 조회 실패: {error_msg}", error_code=error_code)
                
                elif response.status_code == 500:
                    logger.warning(f"서버 오류 발생 (시도 {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(3 * (attempt + 1))
                        continue
                    else:
                        raise KISAPIError("서버 내부 오류", error_code="500")
                        
                else:
                    logger.error(f"HTTP 오류: {response.status_code}")
                    raise KISAPIError(f"HTTP 오류: {response.status_code}")
                    
            except requests.RequestException as e:
                error_msg = str(e)
                
                # RemoteDisconnected 오류 처리 개선
                if "RemoteDisconnected" in error_msg or "Connection aborted" in error_msg:
                    logger.warning(f"연결이 끊어짐 (시도 {attempt + 1}/{max_retries}): 서버가 연결을 종료했습니다.")
                    print(f"Error: 네트워크 오류 (시도 {attempt + 1}/{max_retries}): {error_msg}")
                    
                    if attempt < max_retries - 1:
                        # 연결 끊김 시 더 긴 대기 시간과 세션 재생성
                        wait_time = 10 * (attempt + 1)  # 10초, 20초, 30초... (서버 안정성 향상)
                        logger.info(f"연결 재시도 전 {wait_time}초 대기...")
                        time.sleep(wait_time)
                        
                        # 세션 재생성 시도
                        try:
                            self.session.close()
                            self.session = requests.Session()
                            self.session.headers.update({
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                'Accept': 'application/json',
                                'Content-Type': 'application/json'
                            })
                            logger.info("세션을 재생성했습니다.")
                        except:
                            pass
                        
                        continue
                    else:
                        # 최종 실패 시 사용자 친화적 메시지
                        print(f"\n⚠️ 네트워크 연결 오류가 발생했습니다.")
                        print(f"   한국투자증권 서버가 일시적으로 응답하지 않습니다.")
                        print(f"   잠시 후 다시 시도해주세요.\n")
                        raise KISAPIError(f"네트워크 오류: 서버 연결 끊김")
                else:
                    # 기타 네트워크 오류
                    logger.warning(f"네트워크 오류 (시도 {attempt + 1}/{max_retries}): {e}")
                    print(f"Error: 네트워크 오류 (시도 {attempt + 1}/{max_retries}): {error_msg}")
                    
                    if attempt < max_retries - 1:
                        wait_time = 3 * (attempt + 1)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise KISAPIError(f"네트워크 오류: {e}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON 파싱 오류: {e}")
                raise KISAPIError(f"응답 파싱 오류: {e}")
        
        raise KISAPIError("현재가 조회 최대 재시도 횟수 초과")
    
    def sync_api_call_with_retry(self, method: str, endpoint: str, tr_id: str, 
                                params: Dict[str, Any] = None, data: Dict[str, Any] = None,
                                use_hashkey: bool = False, max_retries: int = 3) -> Dict[str, Any]:
        """동기 API 호출 (재시도 로직 포함)"""
        import time
        
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(max_retries):
            try:
                # Rate Limiting (동기 버전)
                if hasattr(self, '_last_request_time'):
                    elapsed = time.time() - self._last_request_time
                    if elapsed < 2.0:  # 초당 0.5회 제한 (서버 안정성 향상)
                        time.sleep(2.0 - elapsed)
                self._last_request_time = time.time()
                
                headers = self.get_api_headers(tr_id, use_hashkey, data)
                
                if method.upper() == "GET":
                    response = self.session.get(url, headers=headers, params=params, timeout=10)
                elif method.upper() == "POST":
                    response = self.session.post(url, headers=headers, json=data, timeout=10)
                elif method.upper() == "PUT":
                    response = self.session.put(url, headers=headers, json=data, timeout=10)
                elif method.upper() == "DELETE":
                    response = self.session.delete(url, headers=headers, params=params, timeout=10)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # HTTP 상태 코드 확인
                if response.status_code == 200:
                    result = response.json()
                    
                    # API 응답 코드 확인
                    if result.get("rt_cd") in ["0", "1"]:
                        return result
                    else:
                        error_code = result.get("rt_cd", "Unknown")
                        error_msg = result.get("msg1", "No error message")
                        logger.warning(f"API 오류 (시도 {attempt + 1}/{max_retries}): {error_code} - {error_msg}")
                        
                        if attempt < max_retries - 1:
                            time.sleep(2 * (attempt + 1))  # 재시도 간격
                            continue
                        else:
                            raise KISAPIError(f"API 호출 실패: {error_msg}", error_code=error_code, response_data=result)
                
                elif response.status_code == 500:
                    # 급등주 조회의 경우 별도 처리 (반복 로그 억제)
                    if "ranking/fluctuation" in endpoint:
                        if attempt == 0:  # 첫 번째 시도에서만 로깅
                            logger.warning(f"급등주 순위 조회 서버 오류 (재시도 {max_retries}회 예정)")
                        if attempt < max_retries - 1:
                            time.sleep(5 * (attempt + 1))  # 급등주 조회 시 더 긴 대기
                            continue
                        else:
                            logger.error("급등주 순위 조회 서버 오류 지속 - 최대 재시도 초과")
                            raise KISAPIError("서버 내부 오류", error_code="500")
                    else:
                        logger.warning(f"서버 오류 발생 (시도 {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            time.sleep(3 * (attempt + 1))
                            continue
                        else:
                            raise KISAPIError("서버 내부 오류", error_code="500")
                        
                elif response.status_code == 429:
                    logger.warning(f"Rate limit 초과 (시도 {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(5 * (attempt + 1))  # Rate limit 시 더 긴 대기
                        continue
                    else:
                        raise KISAPIError("Rate limit 초과", error_code="429")
                        
                else:
                    logger.error(f"HTTP 오류: {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(2 * (attempt + 1))
                        continue
                    else:
                        raise KISAPIError(f"HTTP 오류: {response.status_code}")
                    
            except requests.RequestException as e:
                error_msg = str(e)
                
                # RemoteDisconnected 오류 처리 개선
                if "RemoteDisconnected" in error_msg or "Connection aborted" in error_msg:
                    logger.warning(f"연결이 끊어짐 (시도 {attempt + 1}/{max_retries}): 서버가 연결을 종료했습니다.")
                    print(f"Error: 네트워크 오류 (시도 {attempt + 1}/{max_retries}): {error_msg}")
                    
                    if attempt < max_retries - 1:
                        # 연결 끊김 시 더 긴 대기 시간과 세션 재생성
                        wait_time = 10 * (attempt + 1)  # 10초, 20초, 30초... (서버 안정성 향상)
                        logger.info(f"연결 재시도 전 {wait_time}초 대기...")
                        time.sleep(wait_time)
                        
                        # 세션 재생성 시도
                        try:
                            self.session.close()
                            self.session = requests.Session()
                            self.session.headers.update({
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                'Accept': 'application/json',
                                'Content-Type': 'application/json'
                            })
                            logger.info("세션을 재생성했습니다.")
                        except:
                            pass
                        
                        continue
                    else:
                        # 최종 실패 시 사용자 친화적 메시지
                        print(f"\n⚠️ 네트워크 연결 오류가 발생했습니다.")
                        print(f"   한국투자증권 서버가 일시적으로 응답하지 않습니다.")
                        print(f"   잠시 후 다시 시도해주세요.\n")
                        raise KISAPIError(f"네트워크 오류: 서버 연결 끊김")
                else:
                    # 기타 네트워크 오류
                    logger.warning(f"네트워크 오류 (시도 {attempt + 1}/{max_retries}): {e}")
                    print(f"Error: 네트워크 오류 (시도 {attempt + 1}/{max_retries}): {error_msg}")
                    
                    if attempt < max_retries - 1:
                        wait_time = 3 * (attempt + 1)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise KISAPIError(f"네트워크 오류: {e}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON 파싱 오류: {e}")
                raise KISAPIError(f"응답 파싱 오류: {e}")
        
        raise KISAPIError("동기 API 호출 최대 재시도 횟수 초과")
    
    async def get_account_balance(self, force_refresh: bool = False) -> Dict[str, Any]:
        """계좌 잔고 조회 (실시간 조회 - 캐시 제거)"""
        logger.debug(f"계좌 잔고 실시간 조회 ({'모의투자' if self.is_mock else '실전투자'})")
        
        # 텔레그램 알림 (계좌 조회 시작)
        # 텔레그램 알림 제거 (API 블로킹 방지)
        
        # 보유종목 상세 조회 API 사용 (보유종목 정보 포함)
        if self.is_mock:
            tr_id = "VTTC8434R"  # 모의투자용 주식잔고조회 (보유종목 포함)
            logger.debug("모의투자 보유종목 상세 조회 시작")
        else:
            tr_id = "TTTC8434R"  # 실전투자용 주식잔고조회 (보유종목 포함)  
            logger.debug("실계좌 보유종목 상세 조회 시작")
            
        # KIS API용 계좌번호 처리 (이미 8자리로 처리됨)
        account_number = self.config["CANO"]
        logger.debug(f"API 호출용 계좌번호: {account_number}")
            
        # 서버 오류 발생시 더 관대한 처리 (KIS 서버 불안정성 고려)
        max_retries = 5  # 재시도 횟수 증가
        
        for attempt in range(max_retries):
            try:
                # 보유종목 상세 정보 포함하도록 파라미터 수정
                params = {
                    "CANO": account_number,  # KIS API는 하이픈 없는 계좌번호 사용
                    "ACNT_PRDT_CD": self.config["ACNT_PRDT_CD"],
                    "AFHR_FLPR_YN": "N",     # 시간외단일가여부
                    "OFL_YN": "",            # 오프라인여부 (공백)
                    "INQR_DVSN": "02",       # 조회구분 (01: 종목별, 02: 전체잔고)
                    "UNPR_DVSN": "01",       # 단가구분
                    "FUND_STTL_ICLD_YN": "N",      # 펀드결제분포함여부
                    "FNCG_AMT_AUTO_RDPT_YN": "N",  # 융자금액자동상환여부
                    "PRCS_DVSN": "01",       # 처리구분 (01: 표준코드 기준)
                    "CTX_AREA_FK100": "",    # 연속조회검색조건100
                    "CTX_AREA_NK100": ""     # 연속조회키100
                }
                
                logger.debug(f"계좌 조회 파라미터: {params}")
                
                result = await self.api_call(
                    method="GET",
                    endpoint="/uapi/domestic-stock/v1/trading/inquire-balance",
                    tr_id=tr_id,
                    params=params
                )
                
                if result:
                    logger.debug("계좌 조회 성공")
                    if result.get('output1'):
                        logger.debug(f"보유 종목 수: {len(result.get('output1', []))}")
                    
                    # output2에서 잔고 정보 추출
                    if result.get('output2'):
                        balance_data = result['output2'][0] if isinstance(result['output2'], list) else result['output2']
                        # ord_psbl_cash 필드가 없는 경우 다른 필드 사용
                        if 'ord_psbl_cash' not in balance_data:
                            # nxdy_excc_amt (익일정산금액)을 주문가능금액으로 사용
                            # nxdy_excc_amt가 없으면 API 데이터 오류로 처리
                            nxdy_amt = balance_data.get('nxdy_excc_amt')
                            if nxdy_amt is None:
                                raise Exception("API 응답에 주문가능금액 정보가 없습니다")
                            balance_data['ord_psbl_cash'] = nxdy_amt
                        # 필수 필드 존재 확인
                        dnca_amt = balance_data.get('dnca_tot_amt')
                        ord_cash = balance_data.get('ord_psbl_cash')
                        if dnca_amt is None or ord_cash is None:
                            raise Exception(f"API 응답에 필수 잔고 정보가 없습니다: dnca_tot_amt={dnca_amt}, ord_psbl_cash={ord_cash}")
                        logger.debug(f"잔고 정보: 예수금={dnca_amt}원, 주문가능금액={ord_cash}원")
                        
                        # 텔레그램 알림 제거 (API 블로킹 방지)
                        # 계좌 조회 완료 로그만 유지 (계좌번호 전체 표시)
                        cash = int(balance_data['dnca_tot_amt'])  # 이미 존재 확인됨
                        full_account_number = f"{self.config['CANO']}-{self.config['ACNT_PRDT_CD']}"
                        logger.debug(f"계좌 조회 완료 [계좌: {full_account_number}] - 예수금: {cash:,}원, 보유종목: {len(result.get('output1', []))}개")
                        
                        # 전체 API 응답을 캐시에 저장 (보유종목 정보 포함)
                        full_result = {
                            **balance_data,  # output2 (잔고 정보)
                            'output1': result.get('output1', []),  # 보유종목 정보 추가
                            'account_number': full_account_number  # 계좌번호 전체 추가
                        }
                        
                        logger.debug("계좌 잔고 및 보유종목 실시간 조회 완료")
                        
                        return full_result
                    else:
                        logger.warning("잔고 정보(output2)가 없습니다")
                        return {}
                
                # 결과가 없으면 재시도
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # 5초씩 증가
                    logger.warning(f"계좌 조회 결과 없음, {wait_time}초 후 재시도... (시도 {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error("계좌 조회 최대 재시도 횟수 초과")
                    return {}
                    
            except KISAPIError as e:
                if "500" in str(e) and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 10  # 서버 오류시 더 긴 대기
                    logger.warning(f"KIS 서버 오류 발생, {wait_time}초 후 재시도... (시도 {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"계좌 조회 API 오류: {e}")
                    if attempt == max_retries - 1:
                        # 최종 실패시 예외 발생 (하드코딩된 0값 제거)
                        logger.error("계좌 조회 최종 실패 - 하드코딩된 0값 반환 제거")
                        raise Exception(f"계좌 조회 API 최종 실패: {e}")
                    continue
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    logger.warning(f"계좌 조회 일반 오류, {wait_time}초 후 재시도... (시도 {attempt + 1}/{max_retries}): {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"계좌 조회 최종 실패: {e}")
                    # 하드코딩된 0값 반환 제거 - 예외 발생
                    raise Exception(f"계좌 조회 최종 실패: {e}")
        
        # 모든 재시도 실패시 예외 발생 (하드코딩된 0값 제거)
        logger.error("계좌 조회 모든 재시도 실패 - 하드코딩된 0값 반환 제거")
        raise Exception("계좌 조회 모든 재시도 실패")
    
    async def get_stock_balance(self) -> list:
        """보유종목 조회 (전체 계좌 정보에서 output1 추출)"""
        try:
            # 모의투자와 실전투자의 TR_ID가 다름
            if self.is_mock:
                tr_id = "VTTC8434R"  # 모의투자용 TR_ID
            else:
                tr_id = "TTTC8434R"  # 실전투자용 TR_ID
                
            # KIS API용 계좌번호 처리 (이미 8자리로 처리됨)
            account_number = self.config["CANO"]
                
            params = {
                "CANO": account_number,
                "ACNT_PRDT_CD": self.config["ACNT_PRDT_CD"],
                "AFHR_FLPR_YN": "N",     # 시간외단일가여부
                "OFL_YN": "",            # 오프라인여부 (공백)
                "INQR_DVSN": "02",       # 조회구분 (02: 잔고)
                "UNPR_DVSN": "01",       # 단가구분
                "FUND_STTL_ICLD_YN": "N",      # 펀드결제분포함여부
                "FNCG_AMT_AUTO_RDPT_YN": "N",  # 융자금액자동상환여부
                "PRCS_DVSN": "00",       # 처리구분 (00: 전일매매포함)
                "CTX_AREA_FK100": "",    # 연속조회검색조건100
                "CTX_AREA_NK100": ""     # 연속조회키100
            }
            
            result = await self.api_call(
                method="GET",
                endpoint="/uapi/domestic-stock/v1/trading/inquire-balance",
                tr_id=tr_id,
                params=params
            )
            
            if result and result.get('output1'):
                # output1에 보유종목 정보가 들어있음
                positions = result['output1']
                
                # 보유수량이 0이 아닌 종목만 필터링
                valid_positions = []
                for position in positions:
                    if int(position.get('hldg_qty', 0)) > 0:
                        valid_positions.append(position)
                
                logger.debug(f"보유종목 조회 성공: {len(valid_positions)}개")
                return valid_positions
            else:
                logger.debug("보유종목 없음")
                return []
                
        except Exception as e:
            logger.error(f"보유종목 조회 실패: {e}")
            return []
    
    def place_buy_order(self, symbol: str, quantity: int, price: int = 0, 
                       order_type: str = "03") -> Dict[str, Any]:
        """매수 주문 (시장가 기본) - KIS API 공식 규격"""
        
        # 매수/매도 비활성화 설정 확인
        try:
            import json
            from pathlib import Path
            config_path = Path(__file__).parent / "trading_config.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    trading_exec = config.get('trading_execution', {})
                    
                    if not trading_exec.get('enable_buy_orders', True):
                        # 시뮬레이션 모드 - 실제 주문 없이 로깅만
                        logger.info(f"[시뮬레이션] 매수 주문 (실제 실행 안함): {symbol} {quantity}주")
                        if trading_exec.get('log_simulated_trades', False):
                            account_type = "실계좌" if not self.is_mock else "모의투자"
                            logger.info(f"[{account_type}] 매수 시뮬레이션: {symbol} {quantity}주 @ 시장가")
                        
                        # 성공적인 주문 응답 시뮬레이션
                        return {
                            "rt_cd": "0", 
                            "msg1": "매수 주문 시뮬레이션 완료",
                            "output": {"odno": "SIMULATION_ORDER_" + str(int(time.time()))}
                        }
        except Exception as e:
            logger.debug(f"매수 설정 확인 중 오류 (계속 진행): {e}")
        
        # 모의투자와 실전투자의 TR_ID가 다름
        if self.is_mock:
            tr_id = "VTTC0802U"  # 모의투자 매수
        else:
            tr_id = "TTTC0802U"  # 실전투자 매수
        
        # KIS API 주문 구분 (모의투자와 실제투자 다름)
        if self.is_mock:
            # 모의투자: 01=시장가, 00=지정가
            market_order_type = "01"  # 모의투자 시장가
        else:
            # 실제투자: 03=시장가, 00=지정가  
            market_order_type = "03"  # 실제투자 시장가
        
        market_price = "0"  # 시장가는 가격 0
        
        account_type = "실계좌" if not self.is_mock else "모의투자"
        order_code = market_order_type
        logger.info(f"KIS API 매수 주문 시작: {symbol} {quantity}주 (시장가 코드: {order_code}) - {account_type}")
        
        # 실제투자 안전장치
        if not self.is_mock:
            logger.warning(f"WARNING 실계좌 매수 주문 실행: {symbol} {quantity}주 @ 시장가 (코드: {order_code})")
        else:
            logger.info(f"[모의투자] 매수 주문 실행: {symbol} {quantity}주 @ 시장가 (코드: {order_code})")
            
        data = {
            "CANO": self.config["CANO"],
            "ACNT_PRDT_CD": self.config["ACNT_PRDT_CD"],
            "PDNO": symbol,
            "ORD_DVSN": market_order_type,  # 03: 시장가
            "ORD_QTY": str(quantity),
            "ORD_UNPR": market_price  # 시장가는 항상 0
        }
        
        # 매수 데이터 검증
        logger.debug(f"매수 주문 데이터: {data}")
        
        # 추가 안전 검증
        if int(quantity) <= 0:
            logger.error(f"유효하지 않은 매수 수량: {quantity}")
            return {"rt_cd": "1", "msg1": "유효하지 않은 매수 수량"}
        
        if not symbol or len(symbol) != 6:
            logger.error(f"유효하지 않은 종목코드: {symbol}")
            return {"rt_cd": "1", "msg1": "유효하지 않은 종목코드"}
        
        result = self.sync_api_call_with_retry(
            method="POST",
            endpoint="/uapi/domestic-stock/v1/trading/order-cash",
            tr_id=tr_id,
            data=data,
            use_hashkey=True,
            max_retries=3
        )
        
        # 매수 결과 로깅 및 텔레그램 알림
        if result and result.get('rt_cd') == '0':
            order_no = result.get('output', {}).get('odno', 'N/A')
            if self.is_mock:
                logger.info(f"[모의투자] 매수 성공: {symbol} {quantity}주 (코드: {order_code}) - 주문번호: {order_no}")
            else:
                logger.info(f"[실계좌] 매수 성공: {symbol} {quantity}주 (코드: {order_code}) - 주문번호: {order_no}")
            
            # 텔레그램 알림 (매수 성공)
            try:
                from support.telegram_notifier import get_telegram_notifier
                telegram = get_telegram_notifier()
                msg = f"{'[모의투자]' if self.is_mock else '[실전투자]'} 매수 성공\n"
                msg += f"종목: {self.get_stock_display_name(symbol)}\n"
                msg += f"수량: {quantity}주\n"
                msg += f"주문번호: {order_no}"
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(telegram.send_message(msg))
                    else:
                        loop.run_until_complete(telegram.send_message(msg))
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(telegram.send_message(msg))
                    loop.close()
            except Exception as e:
                logger.debug(f"텔레그램 알림 실패: {e}")
            
            self.invalidate_balance_cache()
        else:
            error_msg = result.get('msg1', '알 수 없는 오류') if result else '응답 없음'
            
            # 장 종료 메시지 체크
            if '장종료' in error_msg or '장마감' in error_msg:
                logger.info(f"장이 종료되어 매수할 수 없습니다: {symbol}")
            else:
                if self.is_mock:
                    logger.error(f"[모의투자] 매수 실패: {symbol} {quantity}주 (코드: {order_code}) - 오류: {error_msg}")
                else:
                    logger.error(f"[실계좌] 매수 실패: {symbol} {quantity}주 (코드: {order_code}) - 오류: {error_msg}")
            
        return result
    
    def place_sell_order(self, symbol: str, quantity: int, price: int = 0,
                        order_type: str = "03") -> Dict[str, Any]:
        """매도 주문 (시장가 기본) - KIS API 공식 규격"""
        
        # 매수/매도 비활성화 설정 확인
        try:
            import json
            from pathlib import Path
            config_path = Path(__file__).parent / "trading_config.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    trading_exec = config.get('trading_execution', {})
                    
                    if not trading_exec.get('enable_sell_orders', True):
                        # 시뮬레이션 모드 - 실제 주문 없이 로깅만
                        logger.info(f"[시뮬레이션] 매도 주문 (실제 실행 안함): {symbol} {quantity}주")
                        if trading_exec.get('log_simulated_trades', False):
                            account_type = "실계좌" if not self.is_mock else "모의투자"
                            logger.info(f"[{account_type}] 매도 시뮬레이션: {symbol} {quantity}주 @ 시장가")
                        
                        # 성공적인 주문 응답 시뮬레이션
                        return {
                            "rt_cd": "0", 
                            "msg1": "매도 주문 시뮬레이션 완료",
                            "output": {"odno": "SIMULATION_ORDER_" + str(int(time.time()))}
                        }
        except Exception as e:
            logger.debug(f"매도 설정 확인 중 오류 (계속 진행): {e}")
        
        # 모의투자와 실전투자의 TR_ID가 다름
        if self.is_mock:
            tr_id = "VTTC0801U"  # 모의투자 매도
        else:
            tr_id = "TTTC0801U"  # 실전투자 매도
        
        # KIS API 주문 구분 (모의투자와 실제투자 다름)
        if self.is_mock:
            # 모의투자: 01=시장가, 00=지정가
            market_order_type = "01"  # 모의투자 시장가
        else:
            # 실제투자: 03=시장가, 00=지정가  
            market_order_type = "03"  # 실제투자 시장가
        
        market_price = "0"  # 시장가는 가격 0
        
        account_type = "실계좌" if not self.is_mock else "모의투자"
        order_code = market_order_type
        logger.info(f"KIS API 매도 주문 시작: {symbol} {quantity}주 (시장가 코드: {order_code}) - {account_type}")
        
        # 실제투자 안전장치
        if not self.is_mock:
            logger.warning(f"WARNING 실계좌 매도 주문 실행: {symbol} {quantity}주 @ 시장가 (코드: {order_code})")
        else:
            logger.info(f"[모의투자] 매도 주문 실행: {symbol} {quantity}주 @ 시장가 (코드: {order_code})")
            
        data = {
            "CANO": self.config["CANO"],
            "ACNT_PRDT_CD": self.config["ACNT_PRDT_CD"],
            "PDNO": symbol,
            "ORD_DVSN": market_order_type,  # 03: 시장가
            "ORD_QTY": str(quantity),
            "ORD_UNPR": market_price  # 시장가는 항상 0
        }
        
        # 매도 데이터 검증
        logger.debug(f"매도 주문 데이터: {data}")
        
        # 추가 안전 검증
        if int(quantity) <= 0:
            logger.error(f"유효하지 않은 매도 수량: {quantity}")
            return {"rt_cd": "1", "msg1": "유효하지 않은 매도 수량"}
        
        if not symbol or len(symbol) != 6:
            logger.error(f"유효하지 않은 종목코드: {symbol}")
            return {"rt_cd": "1", "msg1": "유효하지 않은 종목코드"}
        
        result = self.sync_api_call_with_retry(
            method="POST",
            endpoint="/uapi/domestic-stock/v1/trading/order-cash",
            tr_id=tr_id,
            data=data,
            use_hashkey=True,
            max_retries=3
        )
        
        # 매도 결과 로깅 및 텔레그램 알림
        if result and result.get('rt_cd') == '0':
            order_no = result.get('output', {}).get('odno', 'N/A')
            if self.is_mock:
                logger.info(f"[모의투자] 매도 성공: {symbol} {quantity}주 (코드: {order_code}) - 주문번호: {order_no}")
            else:
                logger.info(f"[실계좌] 매도 성공: {symbol} {quantity}주 (코드: {order_code}) - 주문번호: {order_no}")
            
            # 텔레그램 알림 (매도 성공)
            try:
                from support.telegram_notifier import get_telegram_notifier
                telegram = get_telegram_notifier()
                msg = f"{'[모의투자]' if self.is_mock else '[실전투자]'} 매도 성공\n"
                msg += f"종목: {self.get_stock_display_name(symbol)}\n"
                msg += f"수량: {quantity}주\n"
                msg += f"주문번호: {order_no}"
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(telegram.send_message(msg))
                    else:
                        loop.run_until_complete(telegram.send_message(msg))
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(telegram.send_message(msg))
                    loop.close()
            except Exception as e:
                logger.debug(f"텔레그램 알림 실패: {e}")
            
            self.invalidate_balance_cache()
        else:
            error_msg = result.get('msg1', '알 수 없는 오류') if result else '응답 없음'
            
            # 장 종료 메시지 체크
            if '장종료' in error_msg or '장마감' in error_msg:
                logger.info(f"장이 종료되어 매도할 수 없습니다: {symbol}")
            else:
                if self.is_mock:
                    logger.error(f"[모의투자] 매도 실패: {symbol} {quantity}주 (코드: {order_code}) - 오류: {error_msg}")
                else:
                    logger.error(f"[실계좌] 매도 실패: {symbol} {quantity}주 (코드: {order_code}) - 오류: {error_msg}")
            
        return result
    
    def invalidate_balance_cache(self):
        """잔고 캐시 무효화 메서드
        
        매수/매도 주문 후 잔고 캐시를 무효화하여 
        다음 조회 시 최신 정보를 가져오도록 함
        """
        # 현재는 캐시를 사용하지 않지만, 향후 캐시 구현 시 여기서 처리
        logger.debug("잔고 캐시 무효화 (현재 캐시 미사용)")
        pass
    
    # 기존 인터페이스 호환성을 위한 별칭 메서드
    def buy_order(self, stock_code: str, quantity: int, price: int = 0, order_type: str = "MARKET") -> Dict[str, Any]:
        """매수 주문 (기존 인터페이스 호환)"""
        # place_buy_order는 symbol 파라미터를 사용
        return self.place_buy_order(symbol=stock_code, quantity=quantity, price=price)
    
    def sell_order(self, stock_code: str, quantity: int, price: int = 0, order_type: str = "MARKET") -> Dict[str, Any]:
        """매도 주문 (기존 인터페이스 호환)"""
        # place_sell_order는 symbol 파라미터를 사용
        return self.place_sell_order(symbol=stock_code, quantity=quantity, price=price)
    
    def get_top_gainers(self, count: int = 20) -> Dict[str, Any]:
        """등락률 상위 종목 조회"""
        return self.sync_api_call_with_retry(
            method="GET",
            endpoint="/uapi/domestic-stock/v1/ranking/fluctuation",
            tr_id="FHPST01710000",
            params={
                "FID_RSFL_RATE1": "",
                "FID_RSFL_RATE2": "",
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_COND_SCR_DIV_CODE": "20171",
                "FID_INPUT_ISCD": "0000",
                "FID_DIV_CLS_CODE": "0",
                "FID_BLNG_CLS_CODE": "0",
                "FID_TRGT_CLS_CODE": "111111111",
                "FID_TRGT_EXLS_CLS_CODE": "000000",
                "FID_INPUT_PRICE_1": "",
                "FID_INPUT_PRICE_2": "",
                "FID_VOL_CNT": "",
                "FID_INPUT_DATE_1": "",
            },
            max_retries=3
        )
    
    def get_minute_chart_data(self, symbol: str, count: int = 30) -> Dict[str, Any]:
        """분봉 차트 데이터 조회"""
        return self.sync_api_call_with_retry(
            method="GET",
            endpoint="/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
            tr_id="FHKST03010200",
            params={
                "FID_ETC_CLS_CODE": "",
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
                "FID_INPUT_HOUR_1": "",
                "FID_PW_DATA_INCU_YN": "Y",
                "FID_HOUR_CLS_CODE": "1"  # 1분봉
            },
            max_retries=3
        )
    
    def get_daily_chart(self, symbol: str, period: int = 30) -> Dict[str, Any]:
        """일봉 차트 데이터 조회"""
        try:
            result = self.sync_api_call_with_retry(
                method="GET",
                endpoint="/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
                tr_id="FHKST03010100",
                params={
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": symbol,
                    "FID_INPUT_DATE_1": "",  # 시작일 (빈값이면 최근일부터)
                    "FID_INPUT_DATE_2": "",  # 종료일 (빈값이면 오늘까지)
                    "FID_PERIOD_DIV_CODE": "D",  # D: 일봉
                    "FID_ORG_ADJ_PRC": "1"  # 수정주가 적용
                },
                max_retries=3
            )
            
            if result.get("rt_cd") == "0" and "output2" in result:
                # 최대 period 개수만 반환
                chart_data = result["output2"][:period] if result["output2"] else []
                return chart_data
            else:
                logger.warning(f"일봉 데이터 조회 실패: {symbol}, 응답: {result}")
                return []
                
        except Exception as e:
            logger.error(f"일봉 차트 조회 오류 ({symbol}): {e}")
            return []
    
    def _get_stock_name_fallback(self, symbol: str) -> str:
        """종목코드에 대한 fallback 종목명 제공 (StockDataCollector 기반)"""
        try:
            # StockDataCollector를 통한 동적 종목명 조회
            from stock_data_collector import StockDataCollector
            collector = StockDataCollector()
            stock_name = collector.get_stock_name(symbol)
            return stock_name
        except Exception as e:
            logger.debug(f"StockDataCollector 종목명 조회 실패 {symbol}: {e}")
            # 최종 fallback
            return f"종목_{symbol}"
    
    def get_stock_name(self, symbol: str) -> str:
        """종목명 조회 (종목 코드로부터 한글명 반환)"""
        try:
            # 현재가 API를 통해 종목명 조회
            price_data = self.get_stock_price(symbol)
            if price_data.get("rt_cd") == "0" and "output" in price_data:
                # 한글 종목명 추출 (여러 필드 시도)
                output = price_data["output"]
                stock_name = (output.get("hts_kor_isnm") or 
                             output.get("bstp_kor_isnm") or 
                             output.get("itms_nm") or 
                             self._get_stock_name_fallback(symbol))
                return stock_name
            else:
                logger.warning(f"종목명 조회 실패: {symbol}")
                return self._get_stock_name_fallback(symbol)
                
        except Exception as e:
            logger.error(f"종목명 조회 오류 ({symbol}): {e}")
            return self._get_stock_name_fallback(symbol)
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """종목 기본 정보 조회 (모의투자에서는 현재가 API를 통해 종목명 획득)"""
        if self.is_mock:
            # 모의투자에서는 현재가 API를 통해 종목명 획득
            try:
                price_response = self.get_stock_price(symbol)
                if price_response.get("rt_cd") == "0" and "output" in price_response:
                    stock_name = price_response["output"].get("bstp_kor_isnm", self._get_stock_name_fallback(symbol))
                    # 종목정보 조회 API와 동일한 응답 형식으로 변환
                    return {
                        "rt_cd": "0",
                        "msg_cd": "SUCCESS",
                        "msg1": "모의투자에서 현재가 API를 통해 종목명 조회 성공",
                        "output": {
                            "hts_kor_isnm": stock_name
                        }
                    }
                else:
                    logger.warning(f"모의투자에서 종목명 조회 실패: {symbol}")
                    return {
                        "rt_cd": "1",
                        "msg_cd": "PRICE_API_FAILED", 
                        "msg1": "현재가 API를 통한 종목명 조회 실패"
                    }
            except Exception as e:
                logger.warning(f"모의투자에서 종목명 조회 중 오류 ({symbol}): {e}")
                return {
                    "rt_cd": "1",
                    "msg_cd": "MOCK_ERROR", 
                    "msg1": f"모의투자에서 종목명 조회 오류: {str(e)}"
                }
        
        # 실전투자에서는 기존 종목정보 API 사용
        return self.api_call(
            method="GET",
            endpoint="/uapi/domestic-stock/v1/quotations/search-stock-info",
            tr_id="CTPF1002R",
            params={
                "PRDT_TYPE_CD": "300",
                "PDNO": symbol
            }
        )
    
    # 캐시 관련 메서드 제거 - 실시간성 보장
    
    # 캐시 관련 메서드 제거됨 - 세션 기반 계좌 관리자 사용
    
    def get_stock_name(self, symbol: str) -> str:
        """종목코드로 종목명 조회"""
        try:
            # 현재가 조회 API로 종목명 확인
            price_data = self.get_stock_price(symbol)
            if price_data and price_data.get('rt_cd') == '0':
                output = price_data.get('output', {})
                
                # 디버깅을 위해 응답 구조 로깅
                logger.debug(f"가격 조회 응답 필드: {list(output.keys())}")
                
                # StockDataCollector를 통한 동적 종목명 조회
                try:
                    from stock_data_collector import StockDataCollector
                    collector = StockDataCollector()
                    stock_name = collector.get_stock_name(symbol)
                    if stock_name and not stock_name.startswith('종목'):
                        logger.debug(f"종목명 동적 조회: {symbol} → {stock_name}")
                        return stock_name
                except Exception as e:
                    logger.debug(f"StockDataCollector 종목명 조회 실패 {symbol}: {e}")
                
                # API 응답에서 종목명 시도
                for name_field in ['hts_kor_isnm', 'prdt_name', 'prdt_abrv_name']:
                    stock_name = output.get(name_field, '').strip()
                    if stock_name and stock_name != symbol:
                        # 업종명이 아닌 실제 종목명인지 확인
                        if not any(keyword in stock_name for keyword in ['전기·전자', 'IT 서비스', '일반서비스', '화학', '기타']):
                            logger.debug(f"종목명 조회 성공: {symbol} → {stock_name} (필드: {name_field})")
                            return stock_name
                
                # 현재가 조회로 안되면 종목정보 조회 시도
                stock_info = self.get_stock_info(symbol)
                if stock_info and stock_info.get('rt_cd') == '0':
                    output2 = stock_info.get('output', {})
                    if isinstance(output2, list) and len(output2) > 0:
                        output2 = output2[0]
                    
                    for name_field in ['prdt_name', 'prdt_abrv_name', 'hts_kor_isnm']:
                        stock_name = output2.get(name_field, '').strip()
                        if stock_name and stock_name != symbol:
                            logger.debug(f"종목명 조회 성공: {symbol} → {stock_name} (종목정보 필드: {name_field})")
                            return stock_name
            
            logger.warning(f"종목명 조회 실패: {symbol} (종목코드 반환)")
            return symbol
                
        except Exception as e:
            logger.error(f"종목명 조회 중 오류: {symbol} - {e}")
            return symbol
    
    def get_stock_display_name(self, symbol: str) -> str:
        """종목명(종목코드) 형태로 표시명 반환"""
        try:
            stock_name = self.get_stock_name(symbol)
            if stock_name and stock_name != symbol:
                return f"{stock_name}({symbol})"
            else:
                return symbol
        except Exception as e:
            logger.error(f"종목 표시명 생성 중 오류: {symbol} - {e}")
            return symbol
    
    def get_stock_chart_data(self, symbol: str, period: str = 'day', count: int = 30) -> Optional[Any]:
        """차트 데이터 조회 (SimpleSurgeDetector용 호환성)"""
        try:
            import pandas as pd
            
            if period == 'day':
                # 일봉 데이터 조회
                chart_data = self.get_daily_chart(symbol, period=count)
                if not chart_data:
                    logger.warning(f"차트 데이터 없음: {symbol}")
                    return None
                
                # DataFrame으로 변환
                df_data = []
                for item in chart_data:
                    df_data.append({
                        'date': item.get('stck_bsop_date', ''),  # 영업일자
                        'Open': float(item.get('stck_oprc', 0)),  # 시가
                        'High': float(item.get('stck_hgpr', 0)),  # 고가
                        'Low': float(item.get('stck_lwpr', 0)),   # 저가
                        'Close': float(item.get('stck_clpr', 0)), # 종가
                        'Volume': int(item.get('acml_vol', 0))    # 누적거래량
                    })
                
                # 날짜 순으로 정렬 (최신 데이터가 마지막에 오도록)
                df_data.reverse()
                df = pd.DataFrame(df_data)
                
                logger.debug(f"차트 데이터 조회 성공: {symbol}, {len(df_data)}개 데이터")
                return df
                
            elif period == 'minute':
                # 분봉 데이터는 현재 미구현
                logger.warning(f"분봉 데이터는 현재 미지원: {symbol}")
                return None
            else:
                logger.error(f"지원하지 않는 차트 기간: {period}")
                return None
                
        except Exception as e:
            logger.error(f"차트 데이터 조회 실패 ({symbol}): {e}")
            return None
    
    def order_stock_buy(self, stock_code: str, quantity: int, price: int = 0, 
                       order_type: str = "MARKET") -> Dict[str, Any]:
        """매수 주문 (호환성을 위한 별칭)"""
        return self.place_buy_order(stock_code, quantity, price)
    
    def get_market_surge_ranking(self, market_type: str = "ALL", limit: int = 20) -> Dict[str, Any]:
        """실시간 급등주 순위 조회 (OPEN-API)"""
        try:
            if self.is_mock:
                # 모의투자: 실전투자 API로 급등주 데이터 조회 (읽기 전용)
                logger.info("모의투자: 실전투자 API로 급등주 데이터 조회")
                return self._get_surge_ranking_with_real_api(limit)
            
            # 급등주 순위 조회 API 호출 (서버 불안정성 고려하여 재시도 증가)
            result = self.sync_api_call_with_retry(
                method="GET",
                endpoint="/uapi/domestic-stock/v1/ranking/fluctuation",
                tr_id="FHPST01710000",  # 실전투자용만 지원
                params={
                    "FID_COND_MRKT_DIV_CODE": "J",     # J: 전체, U: 코스피, Q: 코스닥
                    "FID_COND_SCR_DIV_CODE": "20170",  # 화면구분코드
                    "FID_INPUT_ISCD": "0000",          # 종목코드 (전체)
                    "FID_DIV_CLS_CODE": "0",           # 구분 (0: 전체)
                    "FID_BLNG_CLS_CODE": "0",          # 소속부 (0: 전체)
                    "FID_TRGT_CLS_CODE": "111111111",  # 대상구분 (전체)
                    "FID_TRGT_EXLS_CLS_CODE": "000000", # 제외구분
                    "FID_INPUT_PRICE_1": "",           # 시작가격
                    "FID_INPUT_PRICE_2": "",           # 종료가격
                    "FID_VOL_CNT": "",                 # 거래량
                    "FID_INPUT_DATE_1": ""             # 날짜
                },
                max_retries=5  # 서버 불안정성 고려하여 2→5로 증가
            )
            
            if result and result.get('rt_cd') == '0':
                # 상위 급등주만 추출
                surge_stocks = result.get('output', [])
                if surge_stocks and len(surge_stocks) > limit:
                    surge_stocks = surge_stocks[:limit]
                
                logger.info(f"실시간 급등주 조회 성공: {len(surge_stocks)}개")
                return {
                    "rt_cd": "0",
                    "msg1": "성공",
                    "output": surge_stocks
                }
            else:
                logger.warning(f"급등주 순위 조회 실패: {result}")
                return result or {"rt_cd": "1", "msg1": "조회 실패"}
                
        except Exception as e:
            logger.error(f"급등주 순위 조회 오류: {e}")
            return {"rt_cd": "1", "msg1": f"오류: {e}"}
    
    def _get_surge_ranking_with_real_api(self, limit: int = 20) -> Dict[str, Any]:
        """모의투자에서 실전투자 API로 급등주 데이터 조회 (읽기 전용)"""
        try:
            # 임시로 실전투자 설정 사용 (읽기 전용)
            original_is_mock = self.is_mock
            original_base_url = self.base_url
            
            # 실전투자 설정으로 변경
            self.is_mock = False
            # 동적 URL 로드 시도 (AuthoritativeRegisterKeyLoader 사용)
            try:
                from support.authoritative_register_key_loader import get_authoritative_loader
                loader = get_authoritative_loader()
                urls_config = loader.get_fresh_urls()
                self.base_url = urls_config.get('real_rest')
                if not self.base_url:
                    raise APIConnectionError("실계좌 서버 URL이 Register_Key.md에 설정되지 않았습니다")
                logger.debug(f"실계좌 URL 동적 로드 성공: {self.base_url}")
            except Exception as e:
                # 하드코딩된 fallback URL 제거 - Register_Key.md만이 유일한 신뢰 소스
                raise APIConnectionError(
                    f"실계좌 서버 URL 로드 실패: {e}. "
                    "Register_Key.md의 '### API 호출 URL 정보' 섹션을 확인하세요."
                )
            
            try:
                # 실전투자 API로 급등주 조회 (서버 불안정성 고려하여 재시도 증가)
                result = self.sync_api_call_with_retry(
                    method="GET",
                    endpoint="/uapi/domestic-stock/v1/ranking/fluctuation",
                    tr_id="FHPST01710000",
                    params={
                        "FID_COND_MRKT_DIV_CODE": "J",
                        "FID_COND_SCR_DIV_CODE": "20170",
                        "FID_INPUT_ISCD": "0000",
                        "FID_DIV_CLS_CODE": "0",
                        "FID_BLNG_CLS_CODE": "0",
                        "FID_TRGT_CLS_CODE": "111111111",
                        "FID_TRGT_EXLS_CLS_CODE": "000000",
                        "FID_INPUT_PRICE_1": "",
                        "FID_INPUT_PRICE_2": "",
                        "FID_VOL_CNT": "",
                        "FID_INPUT_DATE_1": ""
                    },
                    max_retries=5  # 서버 불안정성 고려하여 2→5로 증가
                )
                
                if result and result.get('rt_cd') == '0':
                    surge_stocks = result.get('output', [])
                    if surge_stocks and len(surge_stocks) > limit:
                        surge_stocks = surge_stocks[:limit]
                    
                    logger.info(f"모의투자: 실전API로 급등주 조회 성공 {len(surge_stocks)}개")
                    return {
                        "rt_cd": "0",
                        "msg1": "성공",
                        "output": surge_stocks
                    }
                else:
                    logger.warning(f"모의투자: 실전API 급등주 조회 실패 {result}")
                    return result or {"rt_cd": "1", "msg1": "조회 실패"}
            
            finally:
                # 원래 설정으로 복구
                self.is_mock = original_is_mock
                self.base_url = original_base_url
                
        except Exception as e:
            logger.error(f"모의투자 급등주 조회 오류: {e}")
            return {"rt_cd": "1", "msg1": f"오류: {e}"}
    
    async def async_get_surge_stocks(self, limit: int = 30) -> Optional[Dict[str, Any]]:
        """비동기 실시간 급등종목 조회 (surge_trading.py 전용)"""
        import asyncio
        import concurrent.futures
        
        try:
            # ThreadPoolExecutor를 사용하여 비동기로 실행
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self.get_market_surge_ranking, "ALL", limit)
                result = await asyncio.wait_for(asyncio.wrap_future(future), timeout=10.0)
                return result
        except asyncio.TimeoutError:
            logger.warning("비동기 급등종목 조회 타임아웃")
            return None
        except Exception as e:
            logger.error(f"비동기 급등종목 조회 오류: {e}")
            return None
    
    async def async_place_buy_order(self, symbol: str, quantity: int, order_type: str = "03") -> Optional[Dict[str, Any]]:
        """비동기 매수 주문 (surge_trading.py 전용)"""
        import asyncio
        import concurrent.futures
        
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self.place_buy_order, symbol, quantity, None, order_type)
                result = await asyncio.wait_for(asyncio.wrap_future(future), timeout=10.0)
                return result
        except asyncio.TimeoutError:
            logger.warning(f"비동기 매수 주문 타임아웃: {symbol}")
            return None
        except Exception as e:
            logger.error(f"비동기 매수 주문 오류: {symbol} - {e}")
            return None
    
    async def async_place_sell_order(self, symbol: str, quantity: int, order_type: str = "03") -> Optional[Dict[str, Any]]:
        """비동기 매도 주문 (surge_trading.py 전용)"""
        import asyncio
        import concurrent.futures
        
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self.place_sell_order, symbol, quantity, None, order_type)
                result = await asyncio.wait_for(asyncio.wrap_future(future), timeout=10.0)
                return result
        except asyncio.TimeoutError:
            logger.warning(f"비동기 매도 주문 타임아웃: {symbol}")
            return None
        except Exception as e:
            logger.error(f"비동기 매도 주문 오류: {symbol} - {e}")
            return None
    
    def __enter__(self):
        """컨텍스트 매니저 진입"""
        return self
    
    def get_account_positions(self) -> list:
        """계좌 보유종목 조회 (호환성을 위한 별칭 메서드)"""
        return self.get_stock_balance()
    
    async def get_positions(self) -> list:
        """보유종목 조회 (비동기 버전)"""
        try:
            # 비동기 메서드 호출
            positions = await self.get_stock_balance()
            
            # 데이터 형식 표준화 (ProductionAutoTrader 호환성)
            standardized_positions = []
            for position in positions:
                standardized_positions.append({
                    'stock_code': position.get('pdno', ''),
                    'stock_name': position.get('prdt_name', '').strip(),
                    'quantity': int(position.get('hldg_qty', 0)),
                    'avg_price': float(position.get('pchs_avg_pric', 0)),
                    'current_price': float(position.get('prpr', 0)),
                    'evaluation_amount': float(position.get('evlu_amt', 0)),
                    'profit_loss': float(position.get('evlu_pfls_amt', 0)),
                    'profit_rate': float(position.get('evlu_pfls_rt', 0))
                })
            
            return standardized_positions
            
        except Exception as e:
            logger.error(f"보유종목 조회 실패 (async): {e}")
            return []
    
    async def sell_market_order(self, stock_code: str, quantity: int) -> Dict[str, Any]:
        """시장가 매도 주문 (비동기 버전)"""
        try:
            # 동기 메서드를 비동기적으로 호출
            result = self.place_sell_order(symbol=stock_code, quantity=quantity, price=0, order_type="01" if self.is_mock else "03")
            
            # 결과 형식 표준화 (ProductionAutoTrader 호환성)
            if result and result.get('rt_cd') == '0':
                return {
                    'success': True,
                    'executed_price': result.get('output', {}).get('PSBL_QTY', 0),  # 실제 체결가
                    'order_no': result.get('output', {}).get('ODNO', ''),
                    'message': result.get('msg1', '')
                }
            else:
                error_msg = result.get('msg1', '매도 주문 실패') if result else '매도 주문 실패'
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            logger.error(f"시장가 매도 주문 실패: {stock_code} - {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        # 토큰 정리
        if self.access_token:
            try:
                self.revoke_access_token()
            except Exception as e:
                logger.warning(f"Failed to revoke token during cleanup: {e}")
        
        # 세션 정리
        if hasattr(self, 'session'):
            self.session.close()