#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AuthoritativeRegisterKeyLoader Integration Test
암호화된 Register_Key.md 파일과 로더 통합 테스트
"""

import os
import sys
import tempfile
from pathlib import Path

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.secure_key_handler import SecureKeyHandler, setup_secure_environment
from support.authoritative_register_key_loader import AuthoritativeRegisterKeyLoader, APIConfigurationError

def create_test_register_key_content():
    """테스트용 Register_Key.md 내용 생성"""
    return """# Register_Key.md

한국투자증권 OpenAPI 인증정보 및 설정 파일

## API 인증정보

### 실전투자 계좌 정보
```
계좌번호: [12345678-01]
계좌 비밀번호: [1234]
APP KEY: [test-real-app-key-12345]
APP Secret KEY: [test-real-secret-key-abcdef123456789]
```

### 모의투자 계좌 정보
```
계좌번호: [98765432-01]
계좌 비밀번호: [5678]
APP KEY: [test-mock-app-key-67890]
APP Secret KEY: [test-mock-secret-key-fedcba987654321]
```

### API 호출 URL 정보
```
실전투자 REST URL: https://openapi.koreainvestment.com:9443
실전투자 Websocket URL: ws://ops.koreainvestment.com:21000
모의투자 REST URL: https://openapivts.koreainvestment.com:29443
모의투자 Websocket URL: ws://opsvts.koreainvestment.com:31000
```

### 연동 토큰
```
Bot Token: 1234567890:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPqq
Chat ID: 123456789
```
"""

def test_plaintext_loader():
    """평문 파일로 로더 테스트"""
    print("Testing plaintext Register_Key.md with loader...")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 디렉토리 구조 생성
            policy_dir = temp_path / "Policy" / "Register_Key"
            policy_dir.mkdir(parents=True, exist_ok=True)
            
            # Register_Key.md 파일 생성
            register_key_path = policy_dir / "Register_Key.md"
            content = create_test_register_key_content()
            register_key_path.write_text(content, encoding='utf-8')
            
            # 로더 테스트
            loader = AuthoritativeRegisterKeyLoader(project_root=temp_path)
            
            # 실전투자 설정 로드
            real_config = loader.get_fresh_config("REAL")
            print(f"  Real APP KEY: {real_config.get('app_key', '')[:15]}...")
            
            # 모의투자 설정 로드
            mock_config = loader.get_fresh_config("MOCK")
            print(f"  Mock APP KEY: {mock_config.get('app_key', '')[:15]}...")
            
            # URL 설정 로드
            urls = loader.get_fresh_urls()
            print(f"  Real REST URL: {urls.get('real_rest', '')}")
            
            return True
            
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def test_encrypted_loader():
    """암호화된 파일로 로더 테스트"""
    print("Testing encrypted Register_Key.md with loader...")
    
    try:
        # 보안 환경 설정
        setup_secure_environment()
        handler = SecureKeyHandler()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 디렉토리 구조 생성
            policy_dir = temp_path / "Policy" / "Register_Key"
            policy_dir.mkdir(parents=True, exist_ok=True)
            
            # 평문 내용 생성 및 암호화
            plaintext_content = create_test_register_key_content()
            encrypted_content = handler.encrypt(plaintext_content)
            
            # 암호화된 Register_Key.md 파일 생성
            register_key_path = policy_dir / "Register_Key.md"
            register_key_path.write_text(encrypted_content, encoding='utf-8')
            print(f"  Created encrypted file (size: {len(encrypted_content)})")
            
            # 로더 테스트
            loader = AuthoritativeRegisterKeyLoader(project_root=temp_path)
            
            # 실전투자 설정 로드
            real_config = loader.get_fresh_config("REAL")
            print(f"  Real APP KEY: {real_config.get('app_key', '')[:15]}...")
            
            # 모의투자 설정 로드
            mock_config = loader.get_fresh_config("MOCK")
            print(f"  Mock APP KEY: {mock_config.get('app_key', '')[:15]}...")
            
            # URL 설정 로드
            urls = loader.get_fresh_urls()
            print(f"  Real REST URL: {urls.get('real_rest', '')}")
            
            return True
            
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_consistency():
    """평문과 암호화 데이터 일치성 테스트"""
    print("Testing data consistency between plaintext and encrypted...")
    
    try:
        setup_secure_environment()
        handler = SecureKeyHandler()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            policy_dir = temp_path / "Policy" / "Register_Key"
            policy_dir.mkdir(parents=True, exist_ok=True)
            register_key_path = policy_dir / "Register_Key.md"
            
            plaintext_content = create_test_register_key_content()
            
            # 1. 평문 파일로 데이터 로드
            register_key_path.write_text(plaintext_content, encoding='utf-8')
            loader1 = AuthoritativeRegisterKeyLoader(project_root=temp_path)
            plaintext_data = {
                'real': loader1.get_fresh_config("REAL"),
                'mock': loader1.get_fresh_config("MOCK"),
                'urls': loader1.get_fresh_urls()
            }
            
            # 2. 암호화된 파일로 데이터 로드
            encrypted_content = handler.encrypt(plaintext_content)
            register_key_path.write_text(encrypted_content, encoding='utf-8')
            loader2 = AuthoritativeRegisterKeyLoader(project_root=temp_path)
            encrypted_data = {
                'real': loader2.get_fresh_config("REAL"),
                'mock': loader2.get_fresh_config("MOCK"),
                'urls': loader2.get_fresh_urls()
            }
            
            # 3. 데이터 일치성 확인
            if (plaintext_data['real'] == encrypted_data['real'] and
                plaintext_data['mock'] == encrypted_data['mock'] and
                plaintext_data['urls'] == encrypted_data['urls']):
                print("  Data consistency verified!")
                return True
            else:
                print("  ERROR: Data mismatch detected!")
                return False
                
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("AuthoritativeRegisterKeyLoader Integration Test")
    print("=" * 60)
    
    tests = [
        ("Plaintext Loader Test", test_plaintext_loader),
        ("Encrypted Loader Test", test_encrypted_loader),
        ("Data Consistency Test", test_data_consistency),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n[{test_name}]")
        result = test_func()
        results.append((test_name, result))
        status = "PASS" if result else "FAIL"
        print(f"Result: {status}")
    
    print("\n" + "=" * 60)
    print("Integration Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {total}, Passed: {passed}, Failed: {total - passed}")
    
    if passed == total:
        print("\nSUCCESS: All integration tests passed!")
        print("The security enhancement is fully integrated and working.")
        return 0
    else:
        print("\nFAILURE: Some integration tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())