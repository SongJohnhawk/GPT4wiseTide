#!/usr/bin/env python3
"""
Register_Key.md 복호화 스크립트
암호화된 키를 평문으로 복원

사용법:
    python utils/decrypt_key.py [encrypted_file_path]
"""

import os
import sys
import json
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def generate_key_from_password(password: str, salt: bytes) -> bytes:
    """패스워드와 salt로부터 암호화 키 생성"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def decrypt_register_key(encrypted_file_path: str = None):
    """Register_Key.md 파일 복호화"""
    project_root = Path(__file__).parent.parent
    
    if encrypted_file_path is None:
        # 기본 경로에서 암호화된 파일 찾기
        default_path = project_root / "Policy" / "Register_Key" / "Register_Key.md.encrypted"
        if default_path.exists():
            encrypted_file_path = str(default_path)
        else:
            print("❌ 오류: 암호화된 파일을 찾을 수 없습니다.")
            print(f"   기본 경로: {default_path}")
            return False
    
    encrypted_path = Path(encrypted_file_path)
    
    print("=== Register_Key.md 복호화 도구 ===")
    print(f"대상 파일: {encrypted_path}")
    
    # 파일 존재 확인
    if not encrypted_path.exists():
        print(f"❌ 오류: 암호화된 파일이 존재하지 않습니다.")
        return False
    
    try:
        # 메타데이터 읽기
        metadata_file = encrypted_path.with_suffix('.json')
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            print(f"📋 메타데이터: {metadata.get('encryption_method', 'Unknown')}")
            salt_length = metadata.get('salt_length', 16)
        else:
            print("⚠️  메타데이터 파일이 없습니다. 기본값 사용.")
            salt_length = 16
        
        # 암호화된 파일 읽기
        print("📖 암호화된 파일 읽는 중...")
        with open(encrypted_path, 'rb') as f:
            data = f.read()
        
        # salt와 암호화된 내용 분리
        salt = data[:salt_length]
        encrypted_content = data[salt_length:]
        
        print(f"✅ 파일 읽기 성공 (크기: {len(data)} 바이트)")
        
        # 복호화 패스워드 입력
        password = input("🔐 복호화 패스워드를 입력하세요: ").strip()
        if not password:
            print("❌ 오류: 패스워드가 입력되지 않았습니다.")
            return False
        
        # 암호화 키 생성
        print("🔑 복호화 키 생성 중...")
        key = generate_key_from_password(password, salt)
        fernet = Fernet(key)
        
        # 내용 복호화
        print("🔓 파일 내용 복호화 중...")
        decrypted_content = fernet.decrypt(encrypted_content)
        content = decrypted_content.decode('utf-8')
        
        # 복호화된 파일 저장
        original_path = Path(metadata.get('original_file', str(encrypted_path.with_suffix(''))))
        
        # 기존 파일이 있으면 백업
        if original_path.exists():
            backup_path = original_path.with_suffix('.md.old')
            original_path.rename(backup_path)
            print(f"📦 기존 파일 백업: {backup_path}")
        
        with open(original_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 복호화 완료: {original_path}")
        print(f"📄 복원된 파일 크기: {len(content)} 문자")
        
        # 암호화된 파일 삭제 여부 확인
        delete_choice = input("🗑️  암호화된 파일을 삭제하시겠습니까? (y/N): ").strip().lower()
        if delete_choice in ['y', 'yes']:
            encrypted_path.unlink()
            if metadata_file.exists():
                metadata_file.unlink()
            print("🗑️  암호화된 파일이 삭제되었습니다.")
        else:
            print("ℹ️  암호화된 파일이 유지됩니다.")
        
        print("\n🎉 복호화 작업 완료!")
        
        return True
        
    except Exception as e:
        print(f"❌ 복호화 실패: {e}")
        if "InvalidToken" in str(e):
            print("🔐 패스워드가 올바르지 않거나 파일이 손상되었습니다.")
        return False

def main():
    """메인 함수"""
    try:
        encrypted_file = sys.argv[1] if len(sys.argv) > 1 else None
        success = decrypt_register_key(encrypted_file)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()