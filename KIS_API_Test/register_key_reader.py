#!/usr/bin/env python3
"""
Register_Key.md 파일을 읽어서 연동 정보를 파싱하는 유틸리티
"""

import re
import logging
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class RegisterKeyReader:
    """Register_Key.md 파일을 읽고 파싱하는 클래스"""
    
    def __init__(self, project_root: Path = None):
        """
        RegisterKeyReader 초기화
        
        Args:
            project_root: 프로젝트 루트 경로 (None일 경우 자동 감지)
        """
        if project_root is None:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
        
        self.project_root = Path(project_root)
        self.register_key_file = self.project_root / "Policy" / "Register_Key" / "Register_Key.md"
        self._cached_data = None
        
    def load_register_keys(self) -> Dict[str, Any]:
        """
        Register_Key.md 파일에서 모든 연동 정보 로드
        
        Returns:
            Dict: 파싱된 연동 정보
        """
        try:
            if not self.register_key_file.exists():
                logger.error(f"Register_Key.md 파일을 찾을 수 없습니다: {self.register_key_file}")
                return {}
            
            with open(self.register_key_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            parsed_data = self._parse_register_key_content(content)
            self._cached_data = parsed_data
            
            logger.info("Register_Key.md 파일 로드 성공")
            return parsed_data
            
        except Exception as e:
            logger.error(f"Register_Key.md 파일 로드 실패: {e}")
            return {}
    
    def _parse_register_key_content(self, content: str) -> Dict[str, Any]:
        """
        Register_Key.md 파일 내용 파싱
        
        Args:
            content: 파일 내용
            
        Returns:
            Dict: 파싱된 데이터
        """
        data = {
            'kis_real': {},    # 한국투자증권 실전투자
            'kis_mock': {},    # 한국투자증권 모의투자
            'kis_urls': {},    # API URL들
            'krx': {},         # KRX API
            'telegram': {}     # 텔레그램 봇
        }
        
        try:
            # 실전투자 계좌 정보 추출
            real_section = re.search(r'### 실전투자 계좌 정보\s*```\s*(.*?)\s*```', content, re.DOTALL)
            if real_section:
                real_content = real_section.group(1)
                data['kis_real'] = self._parse_account_section(real_content)
            
            # 모의투자 계좌 정보 추출
            mock_section = re.search(r'### 모의투자 계좌 정보\s*```\s*(.*?)\s*```', content, re.DOTALL)
            if mock_section:
                mock_content = mock_section.group(1)
                data['kis_mock'] = self._parse_account_section(mock_content)
            
            # API URL 정보 추출
            url_section = re.search(r'### API 호출 URL 정보\s*```\s*(.*?)\s*```', content, re.DOTALL)
            if url_section:
                url_content = url_section.group(1)
                data['kis_urls'] = self._parse_url_section(url_content)
            
            # KRX API 키 추출
            krx_section = re.search(r'### KRX API 인증키\s*```\s*(.*?)\s*```', content, re.DOTALL)
            if krx_section:
                krx_content = krx_section.group(1)
                krx_match = re.search(r'KRX API Key:\s*(\S+)', krx_content)
                if krx_match:
                    data['krx']['api_key'] = krx_match.group(1)
            
            # 텔레그램 봇 정보 추출
            telegram_section = re.search(r'### 연동 토큰\s*```\s*(.*?)\s*```', content, re.DOTALL)
            if telegram_section:
                telegram_content = telegram_section.group(1)
                data['telegram'] = self._parse_telegram_section(telegram_content)
            
            return data
            
        except Exception as e:
            logger.error(f"Register_Key.md 내용 파싱 실패: {e}")
            return data
    
    def _parse_account_section(self, content: str) -> Dict[str, str]:
        """계좌 섹션 파싱"""
        result = {}
        try:
            # 계좌번호 추출 (대괄호 안의 값)
            account_match = re.search(r'계좌번호:\s*\[([^\]]+)\]', content)
            if account_match:
                result['account_number'] = account_match.group(1)
            
            # 계좌 비밀번호 추출 (대괄호 안의 값)
            password_match = re.search(r'계좌 비밀번호:\s*\[([^\]]+)\]', content)
            if password_match:
                result['account_password'] = password_match.group(1)
            
            # APP KEY 추출 (대괄호 안의 값)
            appkey_match = re.search(r'APP KEY:\s*\[([^\]]+)\]', content)
            if appkey_match:
                result['app_key'] = appkey_match.group(1)
            
            # APP Secret KEY 추출 (대괄호 안의 값, 다중 줄 지원)
            secret_match = re.search(r'APP Secret KEY:\s*\[([^\]]+)\]', content, re.DOTALL)
            if secret_match:
                result['app_secret'] = secret_match.group(1)
            
            # 호환성을 위해 APP_KEY와 APP_SECRET 별칭도 설정
            if 'app_key' in result:
                result['APP_KEY'] = result['app_key']
            if 'app_secret' in result:
                result['APP_SECRET'] = result['app_secret']
            
        except Exception as e:
            logger.debug(f"계좌 섹션 파싱 오류: {e}")
        
        return result
    
    def _parse_url_section(self, content: str) -> Dict[str, str]:
        """URL 섹션 파싱"""
        result = {}
        try:
            # 실전투자 REST URL
            real_rest_match = re.search(r'실전투자 REST URL:\s*(\S+)', content)
            if real_rest_match:
                result['real_rest'] = real_rest_match.group(1)
            
            # 실전투자 Websocket URL
            real_ws_match = re.search(r'실전투자 Websocket URL:\s*(\S+)', content)
            if real_ws_match:
                result['real_websocket'] = real_ws_match.group(1)
            
            # 모의투자 REST URL
            mock_rest_match = re.search(r'모의투자 REST URL:\s*(\S+)', content)
            if mock_rest_match:
                result['mock_rest'] = mock_rest_match.group(1)
            
            # 모의투자 Websocket URL
            mock_ws_match = re.search(r'모의투자 Websocket URL:\s*(\S+)', content)
            if mock_ws_match:
                result['mock_websocket'] = mock_ws_match.group(1)
            
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
                token = token_match.group(1)
                # 템플릿 값이 아닌 실제 값만 저장
                if not token.startswith('[여기에') and token != '[여기에':
                    result['bot_token'] = token
            
            # Chat ID 추출 (템플릿 값 제외)
            chat_match = re.search(r'Chat ID:\s*(\S+)', content)
            if chat_match:
                chat_id = chat_match.group(1)
                # 템플릿 값이 아닌 실제 값만 저장
                if not chat_id.startswith('[여기에') and chat_id != '[여기에':
                    result['chat_id'] = chat_id
            
        except Exception as e:
            logger.debug(f"텔레그램 섹션 파싱 오류: {e}")
        
        return result
    
    def get_api_config(self, account_type: str) -> Dict[str, str]:
        """
        계좌 타입에 따른 API 설정 반환
        
        Args:
            account_type: "REAL" 또는 "MOCK"
            
        Returns:
            Dict: API 설정 (APP_KEY, APP_SECRET, ACCOUNT_NO, ACCOUNT_PASS)
        """
        if self._cached_data is None:
            self._cached_data = self.load_register_keys()
        
        if account_type.upper() == "REAL":
            return self._cached_data.get('kis_real', {})
        elif account_type.upper() == "MOCK":
            return self._cached_data.get('kis_mock', {})
        else:
            logger.warning(f"Unknown account type: {account_type}")
            return {}
    
    def get_kis_real_config(self) -> Dict[str, str]:
        """한국투자증권 실전투자 설정 반환"""
        if not self._cached_data:
            self.load_register_keys()
        return self._cached_data.get('kis_real', {})
    
    def get_kis_mock_config(self) -> Dict[str, str]:
        """한국투자증권 모의투자 설정 반환"""
        if not self._cached_data:
            self.load_register_keys()
        return self._cached_data.get('kis_mock', {})
    
    def get_kis_urls(self) -> Dict[str, str]:
        """한국투자증권 API URL 반환"""
        if not self._cached_data:
            self.load_register_keys()
        return self._cached_data.get('kis_urls', {})
    
    def get_krx_config(self) -> Dict[str, str]:
        """KRX API 설정 반환"""
        if not self._cached_data:
            self.load_register_keys()
        return self._cached_data.get('krx', {})
    
    def get_telegram_config(self) -> Dict[str, str]:
        """텔레그램 봇 설정 반환"""
        if not self._cached_data:
            self.load_register_keys()
        return self._cached_data.get('telegram', {})

# 전역 인스턴스
_register_key_reader = None

# def get_register_key_reader() -> RegisterKeyReader:
#     """DEPRECATED: 이 함수는 더 이상 사용되지 않습니다. authoritative_register_key_loader 사용하세요."""
#     global _register_key_reader
#     if _register_key_reader is None:
#         _register_key_reader = RegisterKeyReader()
#     return _register_key_reader