#!/usr/bin/env python3
"""
SecureKeyHandler - 민감 정보 암호화/복호화 보안 모듈
AES-256-GCM 알고리즘을 사용한 산업 표준 암호화 구현

보안 원칙:
- 마스터 키는 환경 변수에서만 로드
- Just-in-Time Decryption (사용 직전에만 복호화)
- 메모리 노출 시간 최소화
- 검증된 cryptography 라이브러리 사용
"""

import os
import base64
import hashlib
import logging
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

class SecureKeyHandlerError(Exception):
    """보안 핸들러 관련 오류"""
    pass

class MasterKeyNotFoundError(SecureKeyHandlerError):
    """마스터 키를 찾을 수 없는 오류"""
    pass

class DecryptionError(SecureKeyHandlerError):
    """복호화 실패 오류"""
    pass

class SecureKeyHandler:
    """
    민감 정보 암호화/복호화 보안 핸들러
    
    **보안 특징:**
    - AES-256-GCM 인증 암호화 사용
    - PBKDF2를 통한 키 유도 (100,000 iterations)
    - 각 암호화마다 고유한 nonce 생성
    - 환경 변수 기반 마스터 키 관리
    - 메모리 내 키 노출 최소화
    """
    
    # 보안 상수
    MASTER_KEY_ENV_VAR = "TIDEWISE_SECRET_KEY"
    KEY_LENGTH = 32  # AES-256
    NONCE_LENGTH = 12  # GCM 권장 nonce 길이
    SALT_LENGTH = 16  # PBKDF2 salt 길이
    PBKDF2_ITERATIONS = 100000  # OWASP 권장 최소값
    
    def __init__(self):
        """
        SecureKeyHandler 초기화
        
        Raises:
            MasterKeyNotFoundError: 환경 변수에서 마스터 키를 찾을 수 없는 경우
        """
        self._master_key = self._load_master_key()
        logger.info("SecureKeyHandler 초기화 완료 (AES-256-GCM)")
    
    def _load_master_key(self) -> str:
        """
        환경 변수 또는 설정 파일에서 마스터 키 로드
        
        Returns:
            str: 마스터 키
            
        Raises:
            MasterKeyNotFoundError: 환경 변수나 설정 파일이 없는 경우
        """
        # 1. 환경 변수에서 시도
        master_key = os.environ.get(self.MASTER_KEY_ENV_VAR)
        
        # 2. 환경 변수가 없으면 설정 파일에서 시도
        if not master_key:
            try:
                import json
                from pathlib import Path
                config_path = Path(__file__).parent.parent / '.secure' / 'secure.config'
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        master_key = config.get('master_key')
                        if master_key:
                            logger.info("마스터 키를 .secure/secure.config 파일에서 로드했습니다")
            except Exception as e:
                logger.warning(f"설정 파일 읽기 실패: {e}")
        
        if not master_key:
            raise MasterKeyNotFoundError(
                f"환경 변수 '{self.MASTER_KEY_ENV_VAR}'가 설정되지 않았습니다. "
                f"32자리 이상의 강력한 비밀 키를 설정해주세요.\n"
                f"예시: export {self.MASTER_KEY_ENV_VAR}='your-super-secret-and-long-key-here'\n"
                f"또는 .secure/secure.config 파일을 생성하세요."
            )
        
        if len(master_key) < 32:
            raise MasterKeyNotFoundError(
                f"마스터 키가 너무 짧습니다. 최소 32자리 이상이어야 합니다. "
                f"현재 길이: {len(master_key)}"
            )
        
        logger.debug(f"마스터 키 로드 성공 (길이: {len(master_key)})")
        return master_key
    
    def _derive_key(self, salt: bytes) -> bytes:
        """
        PBKDF2를 사용하여 마스터 키에서 암호화 키 유도
        
        Args:
            salt: 키 유도용 salt
            
        Returns:
            bytes: 유도된 32바이트 암호화 키
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
        )
        return kdf.derive(self._master_key.encode('utf-8'))
    
    def encrypt(self, plaintext: str) -> str:
        """
        평문을 AES-256-GCM으로 암호화
        
        Args:
            plaintext: 암호화할 평문
            
        Returns:
            str: Base64로 인코딩된 암호문 (salt + nonce + ciphertext + tag)
            
        Raises:
            SecureKeyHandlerError: 암호화 실패 시
        """
        try:
            if not plaintext:
                raise SecureKeyHandlerError("암호화할 평문이 비어있습니다.")
            
            # 고유한 salt와 nonce 생성
            salt = os.urandom(self.SALT_LENGTH)
            nonce = os.urandom(self.NONCE_LENGTH)
            
            # 키 유도
            key = self._derive_key(salt)
            
            # AES-GCM 암호화
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
            
            # salt + nonce + ciphertext 결합
            encrypted_data = salt + nonce + ciphertext
            
            # Base64 인코딩
            encoded_data = base64.b64encode(encrypted_data).decode('ascii')
            
            logger.debug(f"암호화 성공 (평문 길이: {len(plaintext)}, 암호문 길이: {len(encoded_data)})")
            return encoded_data
            
        except Exception as e:
            logger.error(f"암호화 실패: {e}")
            raise SecureKeyHandlerError(f"암호화 실패: {e}")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Base64 암호문을 AES-256-GCM으로 복호화
        
        Args:
            ciphertext: Base64로 인코딩된 암호문
            
        Returns:
            str: 복호화된 평문
            
        Raises:
            DecryptionError: 복호화 실패 시
        """
        try:
            if not ciphertext:
                raise DecryptionError("복호화할 암호문이 비어있습니다.")
            
            # Base64 디코딩
            try:
                encrypted_data = base64.b64decode(ciphertext.encode('ascii'))
            except Exception as e:
                raise DecryptionError(f"Base64 디코딩 실패: {e}")
            
            # 최소 길이 검증
            min_length = self.SALT_LENGTH + self.NONCE_LENGTH + 16  # 16은 GCM 태그 길이
            if len(encrypted_data) < min_length:
                raise DecryptionError(f"암호문이 너무 짧습니다. 최소 {min_length}바이트 필요")
            
            # salt, nonce, ciphertext 분리
            salt = encrypted_data[:self.SALT_LENGTH]
            nonce = encrypted_data[self.SALT_LENGTH:self.SALT_LENGTH + self.NONCE_LENGTH]
            encrypted_content = encrypted_data[self.SALT_LENGTH + self.NONCE_LENGTH:]
            
            # 키 유도
            key = self._derive_key(salt)
            
            # AES-GCM 복호화
            aesgcm = AESGCM(key)
            decrypted_data = aesgcm.decrypt(nonce, encrypted_content, None)
            
            # UTF-8 디코딩
            plaintext = decrypted_data.decode('utf-8')
            
            logger.debug(f"복호화 성공 (암호문 길이: {len(ciphertext)}, 평문 길이: {len(plaintext)})")
            return plaintext
            
        except DecryptionError:
            # DecryptionError는 그대로 전파
            raise
        except Exception as e:
            logger.error(f"복호화 실패: {e}")
            raise DecryptionError(f"복호화 실패: {e}")
    
    def encrypt_file_content(self, file_path: str) -> str:
        """
        파일 내용을 읽어서 암호화
        
        Args:
            file_path: 암호화할 파일 경로
            
        Returns:
            str: Base64로 인코딩된 암호문
            
        Raises:
            SecureKeyHandlerError: 파일 읽기 또는 암호화 실패 시
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not content.strip():
                raise SecureKeyHandlerError(f"파일이 비어있습니다: {file_path}")
            
            return self.encrypt(content)
            
        except Exception as e:
            logger.error(f"파일 암호화 실패 ({file_path}): {e}")
            raise SecureKeyHandlerError(f"파일 암호화 실패: {e}")
    
    def decrypt_to_file(self, ciphertext: str, output_path: str) -> bool:
        """
        암호문을 복호화하여 파일로 저장
        
        Args:
            ciphertext: Base64로 인코딩된 암호문
            output_path: 저장할 파일 경로
            
        Returns:
            bool: 성공 여부
            
        Raises:
            DecryptionError: 복호화 또는 파일 저장 실패 시
        """
        try:
            plaintext = self.decrypt(ciphertext)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(plaintext)
            
            logger.info(f"복호화된 내용을 파일로 저장: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"파일 복호화 저장 실패 ({output_path}): {e}")
            raise DecryptionError(f"파일 복호화 저장 실패: {e}")
    
    def verify_master_key(self) -> bool:
        """
        마스터 키 유효성 검증 (테스트 암호화/복호화)
        
        Returns:
            bool: 마스터 키가 유효하면 True
        """
        try:
            test_data = "SecureKeyHandler_Test_Data_2025"
            encrypted = self.encrypt(test_data)
            decrypted = self.decrypt(encrypted)
            
            is_valid = (decrypted == test_data)
            logger.debug(f"마스터 키 검증 결과: {'성공' if is_valid else '실패'}")
            return is_valid
            
        except Exception as e:
            logger.error(f"마스터 키 검증 실패: {e}")
            return False
    
    def get_security_info(self) -> dict:
        """
        보안 설정 정보 반환 (디버깅용)
        
        Returns:
            dict: 보안 설정 정보
        """
        return {
            "algorithm": "AES-256-GCM",
            "key_derivation": "PBKDF2-SHA256",
            "iterations": self.PBKDF2_ITERATIONS,
            "key_length": self.KEY_LENGTH,
            "nonce_length": self.NONCE_LENGTH,
            "salt_length": self.SALT_LENGTH,
            "master_key_env_var": self.MASTER_KEY_ENV_VAR,
            "master_key_loaded": bool(self._master_key),
            "master_key_length": len(self._master_key) if self._master_key else 0
        }

# 전역 인스턴스 (싱글톤 패턴)
_secure_handler = None

def get_secure_handler() -> SecureKeyHandler:
    """
    SecureKeyHandler 싱글톤 인스턴스 반환
    
    Returns:
        SecureKeyHandler: 보안 핸들러 인스턴스
        
    Raises:
        MasterKeyNotFoundError: 마스터 키가 설정되지 않은 경우
    """
    global _secure_handler
    
    if _secure_handler is None:
        _secure_handler = SecureKeyHandler()
        logger.info("SecureKeyHandler 싱글톤 인스턴스 생성")
    
    return _secure_handler

def reset_secure_handler():
    """
    전역 인스턴스 리셋 (테스트용)
    """
    global _secure_handler
    _secure_handler = None
    logger.debug("SecureKeyHandler 전역 인스턴스 리셋")