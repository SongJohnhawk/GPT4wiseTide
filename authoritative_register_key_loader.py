#!/usr/bin/env python3
"""
Authoritative Register Key Loader - 일반 텍스트 버전
Policy/Register_Key/Register_Key.md를 유일한 신뢰 소스로 하는 로더

**핵심 원칙:**
- Register_Key.md 파일만이 유일한 신뢰 소스 (일반 텍스트)
- 파일 변경시 즉시 리로드 (mtime + hash 검사)  
- 하드코딩된 값이나 캐시된 복사본 절대 사용 금지
- 서버 오류와 클라이언트 오류 명확한 구분
- 모든 4개 매매 모드가 동일한 로더 사용
"""

import os
import re
import hashlib
import logging
import threading
import sys
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class APIConfigurationError(Exception):
    """API 설정 오류 (클라이언트 측 문제)"""
    pass

class ValidationError(Exception):
    """스키마 검증 오류 (설정 파일 형식 문제)"""  
    pass

class ServerConnectionError(Exception):
    """서버 연결 오류 (서버 측 문제)"""
    pass

class AuthoritativeRegisterKeyLoader:
    """
    Register_Key.md 파일의 단일 신뢰 소스 로더
    
    **Non-Negotiable Constraints:**
    - Register_Key.md 파일에서만 인증정보 읽기
    - 파일 변경시 즉시 반영 (mtime + hash 체크)
    - 하드코딩된 fallback 값 절대 사용 금지
    - 서버 오류 마스킹 금지 (명확한 오류 전파)
    """
    
    def __init__(self, project_root: Path = None):
        """
        AuthoritativeRegisterKeyLoader 초기화
        
        Args:
            project_root: 프로젝트 루트 경로 (None일 경우 자동 감지)
        """
        if project_root is None:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
        
        self.project_root = Path(project_root)
        self.register_key_path = self.project_root / "Policy" / "Register_Key" / "Register_Key.md"
        
        # 파일 변경 감지를 위한 상태
        self.last_mtime = None
        self.file_hash = None
        self._current_data = None
        self.lock = threading.Lock()
        
        logger.info(f"AuthoritativeRegisterKeyLoader 초기화: {self.register_key_path}")
        
        # 초기 파일 존재 확인
        if not self.register_key_path.exists():
            raise APIConfigurationError(
                f"Register_Key.md 파일이 존재하지 않습니다: {self.register_key_path}. "
                "이 파일이 모든 인증정보의 유일한 신뢰 소스입니다."
            )
    
    def get_fresh_config(self, account_type: str) -> Dict[str, str]:
        """
        실시간 파일 체크 후 최신 API 설정 반환
        
        **중요**: 매 호출시 파일 변경여부를 확인하고 변경시 즉시 리로드
        
        Args:
            account_type: "REAL" 또는 "MOCK"
            
        Returns:
            Dict: API 설정 (app_key, app_secret, account_number, account_password)
            
        Raises:
            APIConfigurationError: 파일 누락 또는 설정 누락
            ValidationError: 스키마 검증 실패
        """
        with self.lock:
            # 1. 파일 변경여부 확인 및 필요시 리로드
            if self._is_file_changed():
                logger.info(f"Register_Key.md 파일 변경 감지, 리로드 수행")
                self._current_data = self._load_and_validate()
                self._update_file_state()
            
            # 2. 초기 로드 (최초 호출시)
            elif self._current_data is None:
                logger.info(f"Register_Key.md 파일 초기 로드")
                self._current_data = self._load_and_validate()
                self._update_file_state()
            
            # 3. 계정 타입에 따른 설정 반환
            account_type = account_type.upper()
            if account_type == "REAL":
                config = self._current_data.get('kis_real', {})
                if not config or not config.get('app_key'):
                    raise APIConfigurationError(
                        "실전투자 계정 설정이 Register_Key.md에 없습니다. "
                        "'### 실전투자 계좌 정보' 섹션을 확인하세요."
                    )
            elif account_type == "MOCK":  
                config = self._current_data.get('kis_mock', {})
                if not config or not config.get('app_key'):
                    raise APIConfigurationError(
                        "모의투자 계정 설정이 Register_Key.md에 없습니다. "
                        "'### 모의투자 계좌 정보' 섹션을 확인하세요."
                    )
            else:
                raise ValidationError(f"지원하지 않는 계정 타입: {account_type}. 'REAL' 또는 'MOCK'만 지원합니다.")
            
            logger.debug(f"{account_type} 계정 설정 로드 성공 (app_key: {config.get('app_key', '')[:8]}...)")
            return config.copy()  # 복사본 반환으로 원본 보호
    
    def get_fresh_urls(self) -> Dict[str, str]:
        """
        실시간 파일 체크 후 최신 API URL 설정 반환
        
        Returns:
            Dict: API URL 설정 (real_rest, real_websocket, mock_rest, mock_websocket)
        """
        with self.lock:
            # 파일 변경여부 확인 및 필요시 리로드
            if self._is_file_changed() or self._current_data is None:
                logger.info(f"Register_Key.md 파일 변경 감지 또는 초기 로드, URL 설정 리로드")
                self._current_data = self._load_and_validate()
                self._update_file_state()
            
            urls = self._current_data.get('kis_urls', {})
            if not urls:
                raise APIConfigurationError(
                    "API URL 설정이 Register_Key.md에 없습니다. "
                    "'### API 호출 URL 정보' 섹션을 확인하세요."
                )
            
            return urls.copy()
    
    def get_fresh_telegram_config(self) -> Dict[str, str]:
        """
        실시간 파일 체크 후 최신 텔레그램 설정 반환
        
        Returns:
            Dict: 텔레그램 설정 (bot_token, chat_id)
        """
        with self.lock:
            # 파일 변경여부 확인 및 필요시 리로드
            if self._is_file_changed() or self._current_data is None:
                self._current_data = self._load_and_validate() 
                self._update_file_state()
            
            telegram = self._current_data.get('telegram', {})
            return telegram.copy()
    
    def _is_file_changed(self) -> bool:
        """
        파일 변경여부 확인 (mtime + hash 이중 체크)
        
        Returns:
            bool: 파일이 변경되었으면 True
        """
        try:
            if not self.register_key_path.exists():
                raise APIConfigurationError(f"Register_Key.md 파일이 삭제되었습니다: {self.register_key_path}")
            
            # mtime 체크 (빠른 1차 체크)
            current_mtime = self.register_key_path.stat().st_mtime
            if self.last_mtime is None or current_mtime != self.last_mtime:
                # hash 체크 (정확한 2차 체크)
                current_hash = self._calculate_file_hash()
                if self.file_hash is None or current_hash != self.file_hash:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"파일 변경여부 확인 실패: {e}")
            # 확실하지 않으면 변경된 것으로 간주하여 리로드
            return True
    
    def _calculate_file_hash(self) -> str:
        """파일 해시 계산 (변경 감지용)"""
        try:
            with open(self.register_key_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"파일 해시 계산 실패: {e}")
            return ""
    
    def _update_file_state(self):
        """파일 상태 업데이트 (mtime, hash)"""
        try:
            self.last_mtime = self.register_key_path.stat().st_mtime
            self.file_hash = self._calculate_file_hash()
        except Exception as e:
            logger.error(f"파일 상태 업데이트 실패: {e}")
    
    # 암호화 관련 메서드 제거됨 - 일반 텍스트 파일만 지원
    
    def _load_and_validate(self) -> Dict[str, Any]:
        """
        파일 로드 및 스키마 검증 (보안 강화 버전)
        
        Returns:
            Dict: 검증된 설정 데이터
            
        Raises:
            APIConfigurationError: 파일 읽기 실패
            ValidationError: 스키마 검증 실패
        """
        try:
            if not self.register_key_path.exists():
                raise APIConfigurationError(
                    f"Register_Key.md 파일이 존재하지 않습니다: {self.register_key_path}"
                )
            
            with open(self.register_key_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_content = f.read().strip()
            
            if not file_content:
                raise APIConfigurationError("Register_Key.md 파일이 비어있습니다.")
            
            # 일반 텍스트 파일 처리
            logger.debug("Register_Key.md 일반 텍스트 파일로 처리")
            decrypted_content = file_content
            
            # 파일 내용 파싱
            parsed_data = self._parse_register_key_content(decrypted_content)
            logger.debug(f"파싱된 데이터: kis_real={bool(parsed_data.get('kis_real', {}))}, kis_mock={bool(parsed_data.get('kis_mock', {}))}")
            
            # 스키마 검증
            if not self._validate_schema(parsed_data):
                raise ValidationError("Register_Key.md 파일의 형식이 올바르지 않습니다.")
            
            logger.info("Register_Key.md 파일 로드 및 검증 성공")
            return parsed_data
            
        except (APIConfigurationError, ValidationError):
            # 설정 오류는 그대로 전파
            raise
        except Exception as e:
            # 예상치 못한 오류는 APIConfigurationError로 래핑
            logger.error(f"Register_Key.md 처리 실패: {e}")
            raise APIConfigurationError(f"Register_Key.md 파일 처리 실패: {e}")
    
    def _parse_register_key_content(self, content: str) -> Dict[str, Any]:
        """
        Register_Key.md 파일 내용 파싱
        
        Args:
            content: 파일 내용
            
        Returns:
            Dict: 파싱된 데이터 (kis_real, kis_mock, kis_urls, telegram)
        """
        data = {
            'kis_real': {},    # 한국투자증권 실전투자
            'kis_mock': {},    # 한국투자증권 모의투자
            'kis_urls': {},    # API URL들
            'telegram': {}     # 텔레그램 봇
        }
        
        try:
            # 실전투자 계좌 정보 추출
            real_section = re.search(r'### 실전투자 계좌 정보\s*```\s*(.*?)\s*```', content, re.DOTALL)
            if real_section:
                real_content = real_section.group(1)
                data['kis_real'] = self._parse_account_section(real_content, "실전투자")
            
            # 모의투자 계좌 정보 추출
            mock_section = re.search(r'### 모의투자 계좌 정보\s*```\s*(.*?)\s*```', content, re.DOTALL)
            if mock_section:
                mock_content = mock_section.group(1)
                data['kis_mock'] = self._parse_account_section(mock_content, "모의투자")
            
            # API URL 정보 추출
            url_section = re.search(r'### API 호출 URL 정보\s*```\s*(.*?)\s*```', content, re.DOTALL)
            if url_section:
                url_content = url_section.group(1)
                data['kis_urls'] = self._parse_url_section(url_content)
            
            # 텔레그램 봇 정보 추출 (개선된 파싱)
            telegram_section = re.search(r'### 연동 토큰\s*```\s*(.*?)\s*```', content, re.DOTALL)
            if telegram_section:
                telegram_content = telegram_section.group(1)
                data['telegram'] = self._parse_telegram_section(telegram_content)
            else:
                # 대안 파싱: Bot Token과 Chat ID를 직접 검색
                data['telegram'] = self._parse_telegram_alternative(content)
            
            return data
            
        except Exception as e:
            logger.error(f"Register_Key.md 내용 파싱 실패: {e}")
            raise ValidationError(f"파일 파싱 오류: {e}")
    
    def _parse_account_section(self, content: str, account_type: str) -> Dict[str, str]:
        """계좌 섹션 파싱 (실전투자/모의투자)"""
        result = {}
        try:
            # 계좌번호 추출 (대괄호 안의 값)
            account_match = re.search(r'계좌번호:\s*\[([^\]]+)\]', content)
            if account_match:
                result['account_number'] = account_match.group(1).strip()
            
            # 계좌 비밀번호 추출 (대괄호 안의 값)
            password_match = re.search(r'계좌 비밀번호:\s*\[([^\]]+)\]', content)
            if password_match:
                result['account_password'] = password_match.group(1).strip()
            
            # APP KEY 추출 (대괄호 안의 값)
            appkey_match = re.search(r'APP KEY:\s*\[([^\]]+)\]', content)
            if appkey_match:
                result['app_key'] = appkey_match.group(1).strip()
            
            # APP Secret KEY 추출 (대괄호 안의 값, 다중 줄 지원)
            secret_match = re.search(r'APP Secret KEY:\s*\[([^\]]+)\]', content, re.DOTALL)
            if secret_match:
                result['app_secret'] = secret_match.group(1).strip()
            
            # 레거시 호환성을 위한 대문자 키 설정
            if 'app_key' in result:
                result['APP_KEY'] = result['app_key']
            if 'app_secret' in result:
                result['APP_SECRET'] = result['app_secret']
            
        except Exception as e:
            logger.debug(f"{account_type} 계좌 섹션 파싱 오류: {e}")
        
        return result
    
    def _parse_url_section(self, content: str) -> Dict[str, str]:
        """URL 섹션 파싱"""
        result = {}
        try:
            # 실전투자 REST URL
            real_rest_match = re.search(r'실전투자 REST URL:\s*(\S+)', content)
            if real_rest_match:
                result['real_rest'] = real_rest_match.group(1).strip()
            
            # 실전투자 Websocket URL
            real_ws_match = re.search(r'실전투자 Websocket URL:\s*(\S+)', content)
            if real_ws_match:
                result['real_websocket'] = real_ws_match.group(1).strip()
            
            # 모의투자 REST URL
            mock_rest_match = re.search(r'모의투자 REST URL:\s*(\S+)', content)
            if mock_rest_match:
                result['mock_rest'] = mock_rest_match.group(1).strip()
            
            # 모의투자 Websocket URL
            mock_ws_match = re.search(r'모의투자 Websocket URL:\s*(\S+)', content)
            if mock_ws_match:
                result['mock_websocket'] = mock_ws_match.group(1).strip()
            
        except Exception as e:
            logger.debug(f"URL 섹션 파싱 오류: {e}")
        
        return result
    
    def _parse_telegram_section(self, content: str) -> Dict[str, str]:
        """텔레그램 섹션 파싱"""
        result = {}
        try:
            # Bot Token 추출 (템플릿 값 제외)
            token_match = re.search(r'Bot Token:\s*(\S+)', content)
            if token_match:
                token = token_match.group(1).strip()
                # 템플릿 값이 아닌 실제 값만 저장
                if not token.startswith('[여기에') and token != '[여기에' and ':' in token:
                    result['bot_token'] = token
            
            # Chat ID 추출 (템플릿 값 제외)
            chat_match = re.search(r'Chat ID:\s*(\S+)', content)
            if chat_match:
                chat_id = chat_match.group(1).strip()
                # 템플릿 값이 아닌 실제 값만 저장
                if not chat_id.startswith('[여기에') and chat_id != '[여기에' and chat_id.isdigit():
                    result['chat_id'] = chat_id
            
        except Exception as e:
            logger.debug(f"텔레그램 섹션 파싱 오류: {e}")
        
        return result
    
    def _parse_telegram_alternative(self, content: str) -> Dict[str, str]:
        """텔레그램 섹션 대안 파싱 (직접 검색)"""
        result = {}
        try:
            # Bot Token 직접 검색
            token_match = re.search(r'Bot Token:\s*([^\s\n]+)', content)
            if token_match:
                token = token_match.group(1).strip()
                # 템플릿 값이 아닌 실제 값만 저장
                if not token.startswith('[여기에') and token != '[여기에' and ':' in token:
                    result['bot_token'] = token
                    logger.debug(f"텔레그램 봇 토큰 찾음: {token[:20]}...")
            
            # Chat ID 직접 검색
            chat_match = re.search(r'Chat ID:\s*([^\s\n]+)', content)
            if chat_match:
                chat_id = chat_match.group(1).strip()
                # 템플릿 값이 아닌 실제 값만 저장
                if not chat_id.startswith('[여기에') and chat_id != '[여기에' and chat_id.isdigit():
                    result['chat_id'] = chat_id
                    logger.debug(f"텔레그램 채팅 ID 찾음: {chat_id}")
            
        except Exception as e:
            logger.debug(f"텔레그램 대안 파싱 오류: {e}")
        
        return result
    
    def _validate_schema(self, data: Dict[str, Any]) -> bool:
        """
        설정 데이터 스키마 유효성 검증
        
        Args:
            data: 파싱된 설정 데이터
            
        Returns:
            bool: 유효하면 True
        """
        try:
            # 필수 섹션 존재 확인
            if not isinstance(data, dict):
                logger.error("설정 데이터가 딕셔너리가 아닙니다.")
                return False
            
            # 실전투자 설정 검증
            kis_real = data.get('kis_real', {})
            if kis_real:  # 설정이 있으면 검증
                required_fields = ['app_key', 'app_secret', 'account_number', 'account_password']
                missing_fields = [field for field in required_fields if not kis_real.get(field)]
                if missing_fields:
                    logger.error(f"실전투자 설정에서 누락된 필드: {missing_fields}")
                    return False
            
            # 모의투자 설정 검증  
            kis_mock = data.get('kis_mock', {})
            if kis_mock:  # 설정이 있으면 검증
                required_fields = ['app_key', 'app_secret', 'account_number', 'account_password']
                missing_fields = [field for field in required_fields if not kis_mock.get(field)]
                if missing_fields:
                    logger.error(f"모의투자 설정에서 누락된 필드: {missing_fields}")
                    return False
            
            # 최소 하나의 계정 설정은 있어야 함
            if not kis_real and not kis_mock:
                logger.error("실전투자 또는 모의투자 설정 중 최소 하나는 있어야 합니다.")
                return False
            
            # URL 설정 검증
            kis_urls = data.get('kis_urls', {})
            if kis_urls:
                # URL 형식 간단 검증
                for url_type, url in kis_urls.items():
                    if url and not (url.startswith('http://') or url.startswith('https://') or url.startswith('ws://')):
                        logger.error(f"잘못된 URL 형식: {url_type} = {url}")
                        return False
            
            logger.debug("스키마 검증 성공")
            return True
            
        except Exception as e:
            logger.error(f"스키마 검증 중 오류: {e}")
            return False
    
    def invalidate_cache(self):
        """
        캐시 강제 무효화 (테스트용)
        """
        with self.lock:
            self._current_data = None
            self.last_mtime = None
            self.file_hash = None
            logger.debug("캐시 강제 무효화 완료")
    
    def load_register_keys(self) -> Dict[str, Any]:
        """
        Register_Key.md 파일에서 모든 설정 로드 (레거시 호환성)
        
        TokenAutoRefresher와의 호환성을 위한 메서드
        
        Returns:
            Dict: 모든 설정 데이터 (kis_real, kis_mock, telegram 등)
            
        Raises:
            APIConfigurationError: 파일 읽기 실패
            ValidationError: 스키마 검증 실패
        """
        with self.lock:
            # 파일 변경여부 확인 및 필요시 리로드
            if self._is_file_changed() or self._current_data is None:
                logger.info("Register_Key.md 파일 변경 감지 또는 초기 로드")
                self._current_data = self._load_and_validate()
                self._update_file_state()
            
            # 전체 설정 데이터 반환 (복사본)
            return self._current_data.copy() if self._current_data else {}
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        현재 캐시 상태 정보 반환 (디버깅용)
        """
        with self.lock:
            return {
                "file_path": str(self.register_key_path),
                "file_exists": self.register_key_path.exists(),
                "last_mtime": self.last_mtime,
                "file_hash": self.file_hash[:16] + "..." if self.file_hash else None,
                "cache_loaded": self._current_data is not None,
                "timestamp": datetime.now().isoformat()
            }
    
    def test_server_connectivity(self, account_type: str) -> Dict[str, Any]:
        """
        서버 연결 상태 테스트 (설정 오류 vs 서버 오류 구분)
        
        Args:
            account_type: "REAL" 또는 "MOCK"
            
        Returns:
            Dict: 연결 테스트 결과
            - success: 연결 성공 여부
            - error_type: 'config' | 'server' | 'network'
            - error_message: 오류 메시지
            - response_time: 응답 시간 (ms)
        """
        import requests
        import time
        
        start_time = time.time()
        result = {
            "success": False,
            "error_type": None,
            "error_message": None,
            "response_time": None
        }
        
        try:
            # 설정 로드 시도
            config = self.get_fresh_config(account_type)
            urls = self.get_fresh_urls()
            
            # 필수 설정 검사
            required_fields = ['app_key', 'app_secret']
            missing_fields = [field for field in required_fields if not config.get(field)]
            if missing_fields:
                result["error_type"] = "config"
                result["error_message"] = f"설정 누락: {missing_fields}"
                return result
            
            # URL 선택
            if account_type == "REAL":
                base_url = urls.get('real_rest')
            else:
                base_url = urls.get('mock_rest')
            
            if not base_url:
                result["error_type"] = "config"
                result["error_message"] = f"{account_type} REST URL이 설정되지 않았습니다"
                return result
            
            # 서버 연결 테스트 (토큰 발급 시도)
            headers = {
                'Content-Type': 'application/json',
                'appkey': config['app_key'],
                'appsecret': config['app_secret']
            }
            
            # 기본 연결성 테스트 (토큰 발급 엔드포인트)
            test_url = f"{base_url}/oauth2/tokenP"
            response = requests.post(
                test_url,
                headers=headers,
                json={
                    "grant_type": "client_credentials",
                    "appkey": config['app_key'],
                    "appsecret": config['app_secret']
                },
                timeout=10
            )
            
            result["response_time"] = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                result["success"] = True
                logger.info(f"{account_type} 서버 연결 성공")
            elif response.status_code in [401, 403]:
                result["error_type"] = "config" 
                result["error_message"] = f"인증 실패 (HTTP {response.status_code}): API 키나 시크릿이 올바르지 않습니다"
            elif response.status_code >= 500:
                result["error_type"] = "server"
                result["error_message"] = f"서버 오류 (HTTP {response.status_code}): 서버 측 문제입니다"
            else:
                result["error_type"] = "server"
                result["error_message"] = f"예상치 못한 HTTP 응답 ({response.status_code})"
                
        except requests.exceptions.ConnectionError:
            result["error_type"] = "network"
            result["error_message"] = "네트워크 연결 실패: 서버에 연결할 수 없습니다"
            result["response_time"] = int((time.time() - start_time) * 1000)
        except requests.exceptions.Timeout:
            result["error_type"] = "network" 
            result["error_message"] = "연결 시간 초과: 서버 응답이 없습니다"
            result["response_time"] = int((time.time() - start_time) * 1000)
        except (APIConfigurationError, ValidationError) as e:
            result["error_type"] = "config"
            result["error_message"] = f"설정 오류: {str(e)}"
        except Exception as e:
            result["error_type"] = "unknown"
            result["error_message"] = f"알 수 없는 오류: {str(e)}"
            result["response_time"] = int((time.time() - start_time) * 1000)
        
        return result


# 전역 인스턴스 (싱글톤)
_authoritative_loader = None
_loader_lock = threading.Lock()

def get_authoritative_loader() -> AuthoritativeRegisterKeyLoader:
    """
    AuthoritativeRegisterKeyLoader 싱글톤 인스턴스 반환
    
    **중요**: 모든 4개 매매 모드가 이 동일한 인스턴스를 사용해야 함
    """
    global _authoritative_loader
    
    with _loader_lock:
        if _authoritative_loader is None:
            _authoritative_loader = AuthoritativeRegisterKeyLoader()
            logger.info("AuthoritativeRegisterKeyLoader 싱글톤 인스턴스 생성")
        return _authoritative_loader

def reset_authoritative_loader():
    """
    전역 인스턴스 리셋 (테스트용)
    """
    global _authoritative_loader
    
    with _loader_lock:
        _authoritative_loader = None
        logger.debug("AuthoritativeRegisterKeyLoader 전역 인스턴스 리셋")