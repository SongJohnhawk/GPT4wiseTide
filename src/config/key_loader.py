#!/usr/bin/env python3
"""
Key Loader - 등록 키 로드 모듈 (보안 강화 버전)
Register_Key.md 파일에서 암호화된 키를 읽어와 복호화하여 반환

보안 특징:
- Just-in-Time Decryption (사용 직전에만 복호화)
- SecureKeyHandler를 통한 안전한 복호화
- 메모리 노출 시간 최소화
"""

import os
import logging
from pathlib import Path
from utils.secure_key_handler import SecureKeyHandler, SecureKeyHandlerError

logger = logging.getLogger(__name__)

def load_registration_key():
    """
    Register_Key.md 파일에서 암호화된 등록 키를 읽어와 복호화하여 반환
    
    Returns:
        str: 복호화된 등록 키
        
    Raises:
        FileNotFoundError: Register_Key.md 파일을 찾을 수 없는 경우
        SecureKeyHandlerError: 복호화 실패 시
    """
    try:
        # SecureKeyHandler 인스턴스 생성
        handler = SecureKeyHandler()
        
        # Register_Key.md 파일 경로 설정 (프로젝트 루트 기준)
        key_file_path = Path('Register_Key.md')
        
        # 파일이 존재하지 않으면 Policy/Register_Key/ 경로에서 찾기
        if not key_file_path.exists():
            key_file_path = Path('Policy/Register_Key/Register_Key.md')
        
        if not key_file_path.exists():
            raise FileNotFoundError(
                f"Register_Key.md 파일을 찾을 수 없습니다. "
                f"다음 경로를 확인해주세요: Register_Key.md 또는 Policy/Register_Key/Register_Key.md"
            )
        
        # 암호화된 키 파일 읽기
        with open(key_file_path, 'r', encoding='utf-8') as f:
            encrypted_key_b64 = f.read().strip()
        
        if not encrypted_key_b64:
            raise ValueError("Register_Key.md 파일이 비어있습니다.")
        
        logger.debug(f"암호화된 키 파일 읽기 완료: {key_file_path}")
        
        # 사용 직전에만 복호화 수행 (Just-in-Time Decryption)
        decrypted_key = handler.decrypt(encrypted_key_b64)
        
        logger.info("등록 키 복호화 및 로드 완료")
        return decrypted_key
        
    except FileNotFoundError as e:
        logger.error(f"키 파일을 찾을 수 없습니다: {e}")
        raise
    except SecureKeyHandlerError as e:
        logger.error(f"키 복호화 실패: {e}")
        raise
    except Exception as e:
        logger.error(f"등록 키 로드 중 예상치 못한 오류: {e}")
        raise SecureKeyHandlerError(f"등록 키 로드 실패: {e}")

def load_registration_key_safe():
    """
    안전한 등록 키 로드 (예외 처리 포함)
    
    Returns:
        str or None: 성공 시 복호화된 등록 키, 실패 시 None
    """
    try:
        return load_registration_key()
    except Exception as e:
        logger.error(f"등록 키 로드 실패 (안전 모드): {e}")
        return None

def verify_key_file_encryption():
    """
    Register_Key.md 파일이 암호화되어 있는지 확인
    
    Returns:
        bool: 암호화되어 있으면 True, 평문이면 False
    """
    try:
        # 파일 경로 설정
        key_file_path = Path('Register_Key.md')
        if not key_file_path.exists():
            key_file_path = Path('Policy/Register_Key/Register_Key.md')
        
        if not key_file_path.exists():
            return False
        
        # 파일 내용 읽기
        with open(key_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # Base64 형태인지 간단히 확인 (암호화된 데이터는 Base64로 인코딩됨)
        import base64
        try:
            # Base64 디코딩 시도
            decoded = base64.b64decode(content)
            # 최소 길이 확인 (salt + nonce + 최소 암호문)
            return len(decoded) >= 32
        except:
            # Base64 디코딩 실패 = 평문
            return False
            
    except Exception as e:
        logger.error(f"키 파일 암호화 상태 확인 실패: {e}")
        return False