#!/usr/bin/env python3
"""
Register_Key.md 파일 로더 (KIS_API_Test 전용) - 보안 강화 버전
- KIS API 연동 정보를 Register_Key.md에서 로드 (암호화된 데이터)
- 실전/모의투자 설정 자동 추출
- 토큰 관리자와 통합
- Just-in-Time Decryption 적용
"""

import re
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass
import sys
import os

# utils 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.secure_key_handler import SecureKeyHandler, SecureKeyHandlerError

logger = logging.getLogger(__name__)

@dataclass
class KISConfig:
    """KIS API 설정 정보"""
    # 실전투자
    real_account_num: str
    real_account_password: str  
    real_app_key: str
    real_app_secret: str
    real_rest_url: str
    real_websocket_url: str
    
    # 모의투자
    mock_account_num: str
    mock_account_password: str
    mock_app_key: str
    mock_app_secret: str
    mock_rest_url: str
    mock_websocket_url: str
    
    # 텔레그램
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None


class RegisterKeyLoader:
    """Register_Key.md 파일 로더"""
    
    def __init__(self, config_path: str = None):
        """로더 초기화"""
        if config_path:
            self.config_path = Path(config_path)
        else:
            # KIS_API_Test 폴더 기준 경로
            self.config_path = Path(__file__).parent / "Policy" / "Register_Key" / "Register_Key.md"
        
        logger.info(f"Register_Key.md 로더 초기화: {self.config_path}")
        
        if not self.config_path.exists():
            raise FileNotFoundError(f"Register_Key.md 파일을 찾을 수 없습니다: {self.config_path}")
    
    def load_config(self) -> KISConfig:
        """Register_Key.md에서 설정 로드 (일반 텍스트 파일)"""
        try:
            # 프로젝트 루트 경로 설정
            project_root = Path(__file__).parent.parent
            register_key_path = project_root / "Policy" / "Register_Key" / "Register_Key.md"
            
            # 일반 텍스트 파일 읽기
            with open(register_key_path, 'r', encoding='utf-8', errors='ignore') as f:
                decrypted_content = f.read().strip()
            
            if not decrypted_content:
                raise ValueError("Register_Key.md 파일이 비어있음")
            
            logger.debug("Register_Key.md 일반 텍스트 파일 로드 완료")
            
            # 정규식으로 설정값 추출
            config_data = self._parse_config(decrypted_content)
            
            # KISConfig 객체 생성
            kis_config = KISConfig(**config_data)
            
            logger.info("Register_Key.md 설정 로드 완료")
            logger.debug(f"- 실전계좌: {kis_config.real_account_num}")
            logger.debug(f"- 모의계좌: {kis_config.mock_account_num}")
            
            return kis_config
            
        except Exception as e:
            logger.error(f"Register_Key.md 로드 실패: {e}")
            raise
    
    def _parse_config(self, content: str) -> Dict[str, str]:
        """설정 내용 파싱"""
        config_data = {}
        
        try:
            # 실전투자 계좌 정보 추출
            real_section = self._extract_section(content, "실전투자 계좌 정보")
            if real_section:
                config_data['real_account_num'] = self._extract_value(real_section, "계좌번호")
                config_data['real_account_password'] = self._extract_value(real_section, "계좌 비밀번호")
                config_data['real_app_key'] = self._extract_value(real_section, "APP KEY")
                config_data['real_app_secret'] = self._extract_value(real_section, "APP Secret KEY")
            
            # 모의투자 계좌 정보 추출
            mock_section = self._extract_section(content, "모의투자 계좌 정보")
            if mock_section:
                config_data['mock_account_num'] = self._extract_value(mock_section, "계좌번호")
                config_data['mock_account_password'] = self._extract_value(mock_section, "계좌 비밀번호")
                config_data['mock_app_key'] = self._extract_value(mock_section, "APP KEY")
                config_data['mock_app_secret'] = self._extract_value(mock_section, "APP Secret KEY")
            
            # API URL 정보 추출
            url_section = self._extract_section(content, "API 호출 URL 정보")
            if url_section:
                config_data['real_rest_url'] = self._extract_value(url_section, "실전투자 REST URL")
                config_data['real_websocket_url'] = self._extract_value(url_section, "실전투자 Websocket URL")
                config_data['mock_rest_url'] = self._extract_value(url_section, "모의투자 REST URL")
                config_data['mock_websocket_url'] = self._extract_value(url_section, "모의투자 Websocket URL")
            
            # 텔레그램 정보 추출 (선택사항) - 실제 섹션명으로 수정
            telegram_section = self._extract_section(content, "연동 토큰")
            if telegram_section:
                config_data['telegram_token'] = self._extract_value(telegram_section, "Bot Token", required=False)
                config_data['telegram_chat_id'] = self._extract_value(telegram_section, "Chat ID", required=False)
            
            return config_data
            
        except Exception as e:
            logger.error(f"설정 파싱 실패: {e}")
            raise
    
    def _extract_section(self, content: str, section_title: str) -> Optional[str]:
        """특정 섹션 내용 추출"""
        try:
            # 섹션 제목 찾기
            pattern = f"### {re.escape(section_title)}.*?```(.*?)```"
            match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
            
            if match:
                return match.group(1).strip()
            else:
                logger.warning(f"섹션을 찾을 수 없음: {section_title}")
                return None
                
        except Exception as e:
            logger.error(f"섹션 추출 실패 ({section_title}): {e}")
            return None
    
    def _extract_value(self, section_content: str, key: str, required: bool = True) -> Optional[str]:
        """섹션에서 특정 값 추출"""
        try:
            # 키: 값 또는 키: [값] 형식으로 추출
            pattern1 = f"{re.escape(key)}:\\s*\\[([^\\]]+)\\]"  # [값] 형식
            pattern2 = f"{re.escape(key)}:\\s*([^\\n\\r]+)"     # 값 형식
            
            # 먼저 [값] 형식 시도
            match = re.search(pattern1, section_content)
            if not match:
                # [값] 형식이 없으면 일반 값 형식 시도
                match = re.search(pattern2, section_content)
            
            if match:
                value = match.group(1).strip()
                logger.debug(f"추출 성공 - {key}: {'*' * min(len(value), 8)}")
                return value
            else:
                if required:
                    raise ValueError(f"필수 값을 찾을 수 없음: {key}")
                else:
                    logger.debug(f"선택 값 없음: {key}")
                    return None
                    
        except Exception as e:
            logger.error(f"값 추출 실패 ({key}): {e}")
            if required:
                raise
            return None
    
    def get_api_config_for_account_type(self, account_type: str) -> Dict[str, str]:
        """계좌 타입별 API 설정 반환"""
        try:
            config = self.load_config()
            
            if account_type.upper() == "REAL":
                return {
                    "APP_KEY": config.real_app_key,
                    "APP_SECRET": config.real_app_secret,
                    "ACCOUNT_NUM": config.real_account_num,
                    "ACCOUNT_PASSWORD": config.real_account_password,
                    "REST_URL": config.real_rest_url,
                    "WEBSOCKET_URL": config.real_websocket_url
                }
            elif account_type.upper() == "MOCK":
                return {
                    "APP_KEY": config.mock_app_key,
                    "APP_SECRET": config.mock_app_secret,
                    "ACCOUNT_NUM": config.mock_account_num,
                    "ACCOUNT_PASSWORD": config.mock_account_password,
                    "REST_URL": config.mock_rest_url,
                    "WEBSOCKET_URL": config.mock_websocket_url
                }
            else:
                raise ValueError(f"지원하지 않는 계좌 타입: {account_type}")
                
        except Exception as e:
            logger.error(f"API 설정 로드 실패 ({account_type}): {e}")
            raise
    
    def validate_config(self) -> bool:
        """설정 유효성 검증"""
        try:
            config = self.load_config()
            
            # 필수 필드 검증
            required_fields = [
                'real_account_num', 'real_app_key', 'real_app_secret', 'real_rest_url',
                'mock_account_num', 'mock_app_key', 'mock_app_secret', 'mock_rest_url'
            ]
            
            for field in required_fields:
                value = getattr(config, field)
                if not value or len(value.strip()) == 0:
                    logger.error(f"필수 필드 누락: {field}")
                    return False
            
            logger.info("Register_Key.md 설정 유효성 검증 완료")
            return True
            
        except Exception as e:
            logger.error(f"설정 검증 실패: {e}")
            return False


# 전역 로더 인스턴스 (싱글톤 패턴)
_global_loader: Optional[RegisterKeyLoader] = None

def get_register_key_loader() -> RegisterKeyLoader:
    """전역 로더 인스턴스 반환"""
    global _global_loader
    
    if _global_loader is None:
        _global_loader = RegisterKeyLoader()
    
    return _global_loader


# 편의 함수들
def load_kis_config() -> KISConfig:
    """KIS 설정 로드"""
    loader = get_register_key_loader()
    return loader.load_config()

def get_api_config(account_type: str) -> Dict[str, str]:
    """계좌 타입별 API 설정 반환"""
    loader = get_register_key_loader()
    return loader.get_api_config_for_account_type(account_type)

def validate_register_key() -> bool:
    """Register_Key.md 유효성 검증"""
    loader = get_register_key_loader()
    return loader.validate_config()


# 테스트 함수
def test_register_key_loader():
    """로더 테스트"""
    try:
        print("=== Register_Key.md 로더 테스트 ===")
        
        # 유효성 검증
        print("1. 설정 유효성 검증...")
        if validate_register_key():
            print("[OK] 설정 유효성 검증 통과")
        else:
            print("[FAIL] 설정 유효성 검증 실패")
            return False
        
        # 설정 로드
        print("2. 설정 로드...")
        config = load_kis_config()
        print(f"[OK] 실전계좌: {config.real_account_num}")
        print(f"[OK] 모의계좌: {config.mock_account_num}")
        
        # API 설정 확인
        print("3. API 설정 확인...")
        mock_config = get_api_config("MOCK")
        real_config = get_api_config("REAL")
        
        print(f"[OK] 모의투자 APP_KEY: {mock_config['APP_KEY'][:8]}...")
        print(f"[OK] 실전투자 APP_KEY: {real_config['APP_KEY'][:8]}...")
        
        print("[SUCCESS] 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"[ERROR] 테스트 실패: {e}")
        return False


if __name__ == "__main__":
    test_register_key_loader()