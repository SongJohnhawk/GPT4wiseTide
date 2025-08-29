#!/usr/bin/env python3
"""
한국투자증권 OPEN API Key 관리 클래스
완전히 독립적인 API Key 정보 관리 및 검증 시스템
"""

import json
import os
import re
import hashlib
import logging
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from datetime import datetime
import requests

# 로깅 설정
from support.log_manager import get_log_manager

# 깔끔한 콘솔 로거 사용
from support.clean_console_logger import (
    get_clean_logger, Phase, log as clean_log
)

# 로그 매니저를 통한 로거 설정
log_manager = get_log_manager()
logger = log_manager.setup_logger('system', __name__)

class APIKeyManager:
    """
    한국투자증권 OPEN API Key 관리 클래스
    완전히 독립적인 객체로 설계되어 API Key 정보를 안전하게 관리합니다.
    """
    
    def __init__(self, project_root: Path = None):
        """
        API Key 관리자 초기화
        
        Args:
            project_root: 프로젝트 루트 경로 (None일 경우 자동 감지)
        """
        if project_root is None:
            # 현재 파일 기준으로 프로젝트 루트 찾기
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
        
        self.project_root = Path(project_root)
        self.policy_dir = self.project_root / "Policy"
        # API 키 파일은 AuthoritativeRegisterKeyLoader에서 관리
        # self.api_key_file = self.policy_dir / "API_Key.json"  # 제거됨
        
        # 현재 메모리에 로드된 API 키 정보
        self._current_api_keys = {}
        
        # API 키 유효성 검증 기준
        self._validation_rules = {
            'app_key_length': (32, 50),  # APP KEY 길이 범위
            'secret_key_length': (100, 200),  # SECRET KEY 길이 범위
            'account_number_pattern': r'^[0-9]{8,10}(-[0-9]{2})?$',  # 계좌번호 패턴
            'password_length': (4, 8)  # 계좌 비밀번호 길이
        }
        
        # APIKeyManager 초기화 (로그 제거)
    
    def load_api_keys_from_policy(self) -> bool:
        """
        Register_Key.md 파일에서 API 키 정보를 로드 (AuthoritativeRegisterKeyLoader 사용)
        
        Returns:
            bool: 로드 성공 여부
        """
        try:
            if not self.api_key_file.exists():
                clean_log("API 키 파일 누락", "WARNING")
                return False
            
            with open(self.api_key_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # 기존 형식 파싱
            parsed_keys = self._parse_api_key_content(content)
            
            if parsed_keys:
                self._current_api_keys = parsed_keys
                # API 키 로드 성공 (로그 제거)
                return True
            else:
                clean_log("API 키 파싱 실패", "ERROR")
                return False
                
        except Exception as e:
            clean_log(f"API 키 로드 오류: {str(e)[:50]}...", "ERROR")
            return False
    
    def _parse_api_key_content(self, content: str) -> Dict[str, Any]:
        """
        Register_Key.md 파일 내용 파싱 (AuthoritativeRegisterKeyLoader 사용)
        
        Args:
            content: 파일 내용
            
        Returns:
            Dict: 파싱된 API 키 정보
        """
        parsed = {
            'real': {},
            'mock': {},
            'urls': {},
            'krx_key': None
        }
        
        lines = content.split('\n')
        current_section = None
        url_section_type = None  # 'real' or 'mock'
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 섹션 구분
            if '[API호출REST URL과 Websocket]' in line:
                current_section = 'urls'
                continue
            elif 'OAuth 인증' in line:
                current_section = 'oauth'
                continue
            
            # URL 섹션에서 실전투자/모의투자 구분
            if current_section == 'urls':
                if line == '실전투자':
                    url_section_type = 'real'
                    continue
                elif line == '모의투자':
                    url_section_type = 'mock'
                    continue
            
            # Key-Value 파싱
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip("'\"")
                
                # 일반 정보 파싱
                if key == "실전투자 계좌":
                    parsed['real']['account_number'] = value
                elif key == "실전투자계좌 password":
                    parsed['real']['account_password'] = value
                elif key == "모의투자계좌":
                    parsed['mock']['account_number'] = value
                elif key == "모의투자계좌 password":
                    parsed['mock']['account_password'] = value
                
                # APP KEY 파싱 - 첫 번째는 실전, 두 번째는 모의투자
                elif key == "APP KEY":
                    if 'app_key' not in parsed['real']:
                        parsed['real']['app_key'] = value
                    else:
                        parsed['mock']['app_key'] = value
                elif key == "APP Secret KEY":
                    if 'secret_key' not in parsed['real']:
                        parsed['real']['secret_key'] = value
                    else:
                        parsed['mock']['secret_key'] = value
                
                # URL 정보 파싱 - 현재 섹션에 따라 구분
                elif key == 'REST' and current_section == 'urls':
                    if url_section_type == 'real':
                        parsed['urls']['real_base_url'] = value
                    elif url_section_type == 'mock':
                        parsed['urls']['mock_base_url'] = value
                elif key == 'Websocket' and current_section == 'urls':
                    parsed['urls']['websocket_url'] = value
                
                # KRX 키
                elif 'KRX의 인증키' in key:
                    parsed['krx_key'] = value
        
        return parsed
    
    def validate_api_keys(self, api_keys: Dict[str, Any] = None) -> Tuple[bool, Dict[str, str]]:
        """
        API 키 정보 유효성 검증
        
        Args:
            api_keys: 검증할 API 키 정보 (None일 경우 현재 로드된 키 사용)
            
        Returns:
            Tuple[bool, Dict]: (검증 성공 여부, 오류 메시지들)
        """
        if api_keys is None:
            api_keys = self._current_api_keys
        
        if not api_keys:
            return False, {"general": "API 키 정보가 없습니다"}
        
        errors = {}
        
        # 실전투자 키 검증
        if 'real' in api_keys:
            real_errors = self._validate_account_keys(api_keys['real'], '실전투자')
            if real_errors:
                errors.update({f"real_{k}": v for k, v in real_errors.items()})
        
        # 모의투자 키 검증
        if 'mock' in api_keys:
            mock_errors = self._validate_account_keys(api_keys['mock'], '모의투자')
            if mock_errors:
                errors.update({f"mock_{k}": v for k, v in mock_errors.items()})
        
        # URL 검증
        if 'urls' in api_keys:
            url_errors = self._validate_urls(api_keys['urls'])
            if url_errors:
                errors.update({f"url_{k}": v for k, v in url_errors.items()})
        
        success = len(errors) == 0
        return success, errors
    
    def _validate_account_keys(self, account_data: Dict, account_type: str) -> Dict[str, str]:
        """
        계좌별 API 키 검증
        
        Args:
            account_data: 계좌 데이터
            account_type: 계좌 타입 (실전투자/모의투자)
            
        Returns:
            Dict: 오류 메시지들
        """
        errors = {}
        
        # APP KEY 검증
        app_key = account_data.get('app_key', '')
        if not app_key:
            errors['app_key'] = f"{account_type} APP KEY가 없습니다"
        elif not (self._validation_rules['app_key_length'][0] <= len(app_key) <= self._validation_rules['app_key_length'][1]):
            errors['app_key'] = f"{account_type} APP KEY 길이가 올바르지 않습니다 ({len(app_key)}자)"
        elif not re.match(r'^[A-Za-z0-9]+$', app_key):
            errors['app_key'] = f"{account_type} APP KEY에 허용되지 않는 문자가 포함되어 있습니다"
        
        # SECRET KEY 검증
        secret_key = account_data.get('secret_key', '')
        if not secret_key:
            errors['secret_key'] = f"{account_type} SECRET KEY가 없습니다"
        elif not (self._validation_rules['secret_key_length'][0] <= len(secret_key) <= self._validation_rules['secret_key_length'][1]):
            errors['secret_key'] = f"{account_type} SECRET KEY 길이가 올바르지 않습니다 ({len(secret_key)}자)"
        
        # 계좌번호 검증
        account_number = account_data.get('account_number', '')
        if not account_number:
            errors['account_number'] = f"{account_type} 계좌번호가 없습니다"
        elif not re.match(self._validation_rules['account_number_pattern'], account_number):
            errors['account_number'] = f"{account_type} 계좌번호 형식이 올바르지 않습니다"
        
        # 계좌 비밀번호 검증
        password = account_data.get('account_password', '')
        if not password:
            errors['account_password'] = f"{account_type} 계좌 비밀번호가 없습니다"
        elif not (self._validation_rules['password_length'][0] <= len(password) <= self._validation_rules['password_length'][1]):
            errors['password'] = f"{account_type} 계좌 비밀번호 길이가 올바르지 않습니다"
        elif not password.isdigit():
            errors['password'] = f"{account_type} 계좌 비밀번호는 숫자만 입력해야 합니다"
        
        return errors
    
    def _validate_urls(self, url_data: Dict) -> Dict[str, str]:
        """
        URL 정보 검증
        
        Args:
            url_data: URL 데이터
            
        Returns:
            Dict: 오류 메시지들
        """
        errors = {}
        
        # 실전투자 URL 검증 - 하드코딩된 포트번호 제거
        real_url = url_data.get('real_base_url', '')
        if not real_url:
            errors['real_url'] = "실전투자 REST URL이 없습니다"
        elif not real_url.startswith('https://'):
            errors['real_url'] = "실전투자 REST URL은 HTTPS를 사용해야 합니다"
        
        # 모의투자 URL 검증 - 하드코딩된 포트번호 제거
        mock_url = url_data.get('mock_base_url', '')
        if not mock_url:
            errors['mock_url'] = "모의투자 REST URL이 없습니다"
        elif not mock_url.startswith('https://'):
            errors['mock_url'] = "모의투자 REST URL은 HTTPS를 사용해야 합니다"
        
        return errors
    
    def update_api_keys(self) -> bool:
        """
        현재 시스템의 API 키 정보를 Policy 파일의 정보로 업데이트
        
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            # Policy 파일에서 새로운 키 정보 로드
            if not self.load_api_keys_from_policy():
                clean_log("API 키 로드 실패", "ERROR")
                return False
            
            # 유효성 검증
            is_valid, errors = self.validate_api_keys()
            if not is_valid:
                clean_log("API 키 유효성 검증 실패", "ERROR")
                return False
            
            # 구조 정리 및 검증 통과
            sanitized_keys = self._sanitize_api_keys(self._current_api_keys)
            if not sanitized_keys:
                clean_log("API 키 정리 실패", "ERROR")
                return False
            
            # 현재 시스템에 적용
            self._current_api_keys = sanitized_keys
            
            # API 키 업데이트 성공 (로그 제거)
            return True
            
        except Exception as e:
            clean_log(f"API 키 업데이트 오류: {str(e)[:50]}...", "ERROR")
            return False
    
    def _sanitize_api_keys(self, api_keys: Dict[str, Any]) -> Dict[str, Any]:
        """
        API 키 정보 정리 및 정규화
        
        Args:
            api_keys: 원본 API 키 정보
            
        Returns:
            Dict: 정리된 API 키 정보
        """
        try:
            sanitized = {}
            
            # 실전투자 정보 정리
            if 'real' in api_keys and api_keys['real']:
                real_data = api_keys['real']
                sanitized['real'] = {
                    'app_key': real_data.get('app_key', '').strip(),
                    'secret_key': real_data.get('secret_key', '').strip(),
                    'account_number': real_data.get('account_number', '').strip(),
                    'account_password': real_data.get('account_password', '').strip()
                }
            
            # 모의투자 정보 정리
            if 'mock' in api_keys and api_keys['mock']:
                mock_data = api_keys['mock']
                sanitized['mock'] = {
                    'app_key': mock_data.get('app_key', '').strip(),
                    'secret_key': mock_data.get('secret_key', '').strip(),
                    'account_number': mock_data.get('account_number', '').strip(),
                    'account_password': mock_data.get('account_password', '').strip()
                }
            
            # URL 정보 정리
            if 'urls' in api_keys and api_keys['urls']:
                url_data = api_keys['urls']
                sanitized['urls'] = {
                    'real_base_url': url_data.get('real_base_url', '').strip(),
                    'mock_base_url': url_data.get('mock_base_url', '').strip(),
                    'websocket_url': url_data.get('websocket_url', '').strip()
                }
            
            # KRX 키 정리
            if api_keys.get('krx_key'):
                sanitized['krx_key'] = api_keys['krx_key'].strip()
            
            # 업데이트 시간 기록
            sanitized['last_updated'] = datetime.now().isoformat()
            
            return sanitized
            
        except Exception as e:
            logger.error(f"API 키 정리 중 오류: {e}")
            return {}
    
    def clear_api_keys(self) -> bool:
        """
        현재 메모리에 로드된 API 키 정보 삭제
        (Policy 파일은 그대로 유지)
        
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            self._current_api_keys = {}
            logger.info("메모리의 API 키 정보 삭제 완료")
            return True
        except Exception as e:
            logger.error(f"API 키 삭제 중 오류: {e}")
            return False
    
    def get_api_keys(self, account_type: str = None) -> Dict[str, Any]:
        """
        현재 로드된 API 키 정보 조회
        
        Args:
            account_type: 조회할 계정 타입 ('real', 'mock', None=전체)
            
        Returns:
            Dict: API 키 정보
        """
        if not self._current_api_keys:
            return {}
        
        if account_type is None:
            return self._current_api_keys.copy()
        elif account_type in self._current_api_keys:
            return {account_type: self._current_api_keys[account_type]}
        else:
            return {}
    
    def is_api_keys_loaded(self) -> bool:
        """
        API 키가 메모리에 로드되어 있는지 확인
        
        Returns:
            bool: 로드 여부
        """
        return bool(self._current_api_keys)
    
    def get_status_info(self) -> Dict[str, Any]:
        """
        API Key 관리자 상태 정보 반환
        
        Returns:
            Dict: 상태 정보
        """
        status = {
            'policy_file_exists': self.api_key_file.exists(),
            'keys_loaded': self.is_api_keys_loaded(),
            'last_updated': self._current_api_keys.get('last_updated', 'Never'),
            'real_account_configured': bool(self._current_api_keys.get('real', {}).get('app_key')),
            'mock_account_configured': bool(self._current_api_keys.get('mock', {}).get('app_key')),
        }
        
        if self._current_api_keys:
            is_valid, errors = self.validate_api_keys()
            status['validation_status'] = 'valid' if is_valid else 'invalid'
            status['validation_errors'] = errors
        else:
            status['validation_status'] = 'not_loaded'
            status['validation_errors'] = {}
        
        return status

def get_api_key_manager() -> APIKeyManager:
    """
    전역 API Key 관리자 인스턴스 반환 (싱글톤 패턴)
    
    Returns:
        APIKeyManager: API Key 관리자 인스턴스
    """
    if not hasattr(get_api_key_manager, '_instance'):
        get_api_key_manager._instance = APIKeyManager()
    
    return get_api_key_manager._instance