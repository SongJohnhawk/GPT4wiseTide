#!/usr/bin/env python3
"""
Register_Key.md 암호화 스크립트
평문 키를 암호화된 키로 교체하여 보안 강화

사용법:
    python utils/encrypt_key.py
"""

import os
import sys
import json
import base64
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def generate_key_from_password(password: str, salt: bytes = None) -> bytes:
    """패스워드로부터 암호화 키 생성"""
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt

def encrypt_register_key():
    """Register_Key.md 파일 암호화"""
    project_root = Path(__file__).parent.parent
    register_key_path = project_root / "Policy" / "Register_Key" / "Register_Key.md"
    
    print("=== Register_Key.md 암호화 도구 ===")
    print(f"대상 파일: {register_key_path}")
    
    # 파일 존재 확인
    if not register_key_path.exists():
        print(f"❌ 오류: Register_Key.md 파일이 존재하지 않습니다.")
        print(f"   경로: {register_key_path}")
        return False
    
    try:
        # 파일 읽기 (UTF-8 인코딩, 오류 무시)
        print("📖 파일 읽는 중...")
        with open(register_key_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if not content.strip():
            print("❌ 오류: 파일이 비어있습니다.")
            return False
        
        print(f"✅ 파일 읽기 성공 (크기: {len(content)} 문자)")
        
        # 암호화 패스워드 입력
        password = input("🔐 암호화 패스워드를 입력하세요: ").strip()
        if not password:
            print("❌ 오류: 패스워드가 입력되지 않았습니다.")
            return False
        
        # 암호화 키 생성
        print("🔑 암호화 키 생성 중...")
        key, salt = generate_key_from_password(password)
        fernet = Fernet(key)
        
        # 내용 암호화
        print("🔒 파일 내용 암호화 중...")
        encrypted_content = fernet.encrypt(content.encode('utf-8'))
        
        # 암호화된 파일 저장
        encrypted_file_path = register_key_path.with_suffix('.md.encrypted')
        with open(encrypted_file_path, 'wb') as f:
            # salt + 암호화된 내용 저장
            f.write(salt + encrypted_content)
        
        print(f"✅ 암호화 완료: {encrypted_file_path}")
        
        # 메타데이터 저장
        metadata = {
            "original_file": str(register_key_path),
            "encrypted_file": str(encrypted_file_path),
            "salt_length": len(salt),
            "encryption_method": "Fernet (AES 128)",
            "created_at": str(Path(encrypted_file_path).stat().st_mtime)
        }
        
        metadata_file = encrypted_file_path.with_suffix('.json')
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"📋 메타데이터 저장: {metadata_file}")
        
        # 원본 파일 백업 후 삭제 여부 확인
        backup_choice = input("🗂️  원본 파일을 백업하고 삭제하시겠습니까? (y/N): ").strip().lower()
        if backup_choice in ['y', 'yes']:
            backup_path = register_key_path.with_suffix('.md.backup')
            register_key_path.rename(backup_path)
            print(f"📦 원본 파일 백업: {backup_path}")
            print("⚠️  원본 파일이 삭제되었습니다. 복호화 시 패스워드가 필요합니다.")
        else:
            print("ℹ️  원본 파일이 유지됩니다.")
        
        print("\n🎉 암호화 작업 완료!")
        print("📝 복호화 방법:")
        print(f"   python utils/decrypt_key.py {encrypted_file_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 암호화 실패: {e}")
        return False

def main():
    """메인 함수"""
    try:
        success = encrypt_register_key()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()