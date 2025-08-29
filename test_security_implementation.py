#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Security Enhancement Implementation Test
Register_Key.md 암호화/복호화 시스템 통합 테스트
"""

import os
import sys
import tempfile
from pathlib import Path

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.secure_key_handler import SecureKeyHandler, setup_secure_environment
from support.authoritative_register_key_loader import AuthoritativeRegisterKeyLoader, APIConfigurationError, ValidationError

def test_secure_key_handler():
    """SecureKeyHandler 기본 기능 테스트"""
    print("[CRYPTO] SecureKeyHandler 기본 기능 테스트...")
    
    try:
        # 보안 환경 설정
        setup_secure_environment()
        
        # 핸들러 인스턴스 생성
        handler = SecureKeyHandler()
        
        # 테스트 데이터
        test_data = {
            "계좌번호": "12345678-01",
            "APP KEY": "test-app-key-123",
            "APP SECRET KEY": "test-secret-key-456789"
        }
        
        print("  ✅ 핸들러 초기화 성공")
        
        # JSON 암호화 테스트
        encrypted_json = handler.encrypt_json(test_data)
        print(f"  ✅ JSON 암호화 성공 (길이: {len(encrypted_json)})")
        
        # JSON 복호화 테스트
        decrypted_json = handler.decrypt_json(encrypted_json)
        print("  ✅ JSON 복호화 성공")
        
        # 데이터 일치 확인
        if test_data == decrypted_json:
            print("  ✅ 데이터 일치 검증 성공")
            return True
        else:
            print("  ❌ 데이터 불일치!")
            return False
            
    except Exception as e:
        print(f"  ❌ 테스트 실패: {e}")
        return False

def create_test_register_key_file(temp_dir: Path) -> Path:
    """테스트용 Register_Key.md 파일 생성"""
    
    register_key_content = """# Register_Key.md

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
    
    # 디렉토리 구조 생성
    policy_dir = temp_dir / "Policy" / "Register_Key"
    policy_dir.mkdir(parents=True, exist_ok=True)
    
    # Register_Key.md 파일 생성
    register_key_path = policy_dir / "Register_Key.md"
    register_key_path.write_text(register_key_content, encoding='utf-8')
    
    return register_key_path

def test_authoritative_loader_with_plaintext():
    """평문 Register_Key.md 파일로 AuthoritativeRegisterKeyLoader 테스트"""
    print("\n📋 평문 파일로 AuthoritativeRegisterKeyLoader 테스트...")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 테스트용 Register_Key.md 파일 생성
            register_key_path = create_test_register_key_file(temp_path)
            print(f"  ✅ 테스트 파일 생성: {register_key_path}")
            
            # AuthoritativeRegisterKeyLoader 인스턴스 생성
            loader = AuthoritativeRegisterKeyLoader(project_root=temp_path)
            print("  ✅ 로더 초기화 성공")
            
            # 실전투자 설정 로드 테스트
            real_config = loader.get_fresh_config("REAL")
            print("  ✅ 실전투자 설정 로드 성공")
            print(f"     APP KEY: {real_config.get('app_key', '')[:10]}...")
            
            # 모의투자 설정 로드 테스트
            mock_config = loader.get_fresh_config("MOCK")
            print("  ✅ 모의투자 설정 로드 성공")
            print(f"     APP KEY: {mock_config.get('app_key', '')[:10]}...")
            
            # URL 설정 로드 테스트
            urls = loader.get_fresh_urls()
            print("  ✅ URL 설정 로드 성공")
            print(f"     실전 REST: {urls.get('real_rest', '')}")
            
            # 텔레그램 설정 로드 테스트
            telegram = loader.get_fresh_telegram_config()
            print("  ✅ 텔레그램 설정 로드 성공")
            print(f"     Chat ID: {telegram.get('chat_id', 'N/A')}")
            
            return True
            
    except Exception as e:
        print(f"  ❌ 평문 파일 테스트 실패: {e}")
        return False

def test_end_to_end_encryption():
    """전체 암호화/복호화 워크플로우 테스트"""
    print("\n🔄 전체 암호화/복호화 워크플로우 테스트...")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 1. 평문 Register_Key.md 파일 생성
            register_key_path = create_test_register_key_file(temp_path)
            print("  ✅ 1단계: 평문 테스트 파일 생성")
            
            # 2. 평문 파일로 로더 테스트
            loader = AuthoritativeRegisterKeyLoader(project_root=temp_path)
            original_real_config = loader.get_fresh_config("REAL")
            print("  ✅ 2단계: 평문 파일 읽기 성공")
            
            # 3. 파일 암호화
            handler = SecureKeyHandler()
            original_content = register_key_path.read_text(encoding='utf-8')
            encrypted_content = handler.encrypt(original_content)
            register_key_path.write_text(encrypted_content, encoding='utf-8')
            print("  ✅ 3단계: 파일 암호화 완료")
            
            # 4. 암호화된 파일로 로더 테스트 (캐시 무효화)
            loader.invalidate_cache()
            encrypted_real_config = loader.get_fresh_config("REAL")
            print("  ✅ 4단계: 암호화된 파일 읽기 성공")
            
            # 5. 데이터 일치성 확인
            if original_real_config == encrypted_real_config:
                print("  ✅ 5단계: 암호화 전후 데이터 일치 확인")
                print(f"     APP KEY 일치: {original_real_config.get('app_key') == encrypted_real_config.get('app_key')}")
                print(f"     APP SECRET 일치: {original_real_config.get('app_secret') == encrypted_real_config.get('app_secret')}")
                return True
            else:
                print("  ❌ 5단계: 데이터 불일치!")
                print(f"  원본: {original_real_config}")
                print(f"  암호화 후: {encrypted_real_config}")
                return False
                
    except Exception as e:
        print(f"  ❌ 전체 워크플로우 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_handling():
    """오류 처리 테스트"""
    print("\n⚠️  오류 처리 테스트...")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 1. 파일 없음 테스트
            try:
                loader = AuthoritativeRegisterKeyLoader(project_root=temp_path)
                print("  ❌ 파일 없음 테스트 실패 - 예외가 발생하지 않음")
                return False
            except APIConfigurationError:
                print("  ✅ 파일 없음 예외 처리 성공")
            
            # 2. 잘못된 암호화 데이터 테스트
            policy_dir = temp_path / "Policy" / "Register_Key"
            policy_dir.mkdir(parents=True, exist_ok=True)
            register_key_path = policy_dir / "Register_Key.md"
            register_key_path.write_text("invalid_encrypted_data", encoding='utf-8')
            
            try:
                loader = AuthoritativeRegisterKeyLoader(project_root=temp_path)
                loader.get_fresh_config("REAL")
                print("  ❌ 잘못된 암호화 데이터 테스트 실패 - 예외가 발생하지 않음")
                return False
            except APIConfigurationError:
                print("  ✅ 잘못된 암호화 데이터 예외 처리 성공")
            
            return True
            
    except Exception as e:
        print(f"  ❌ 오류 처리 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    # Windows 콘솔 인코딩 문제 해결
    import locale
    try:
        # UTF-8으로 인코딩 설정 시도
        if sys.platform == "win32":
            os.system("chcp 65001 > nul")
    except:
        pass
    
    print("=" * 60)
    print("tideWise Security Enhancement Implementation Test")
    print("=" * 60)
    
    # 보안 환경 초기 설정
    print("🔧 보안 환경 설정...")
    try:
        setup_secure_environment()
        print("✅ 보안 환경 설정 완료")
    except Exception as e:
        print(f"❌ 보안 환경 설정 실패: {e}")
        return 1
    
    test_results = []
    
    # 1. SecureKeyHandler 기본 기능 테스트
    test_results.append(("SecureKeyHandler 기본 기능", test_secure_key_handler()))
    
    # 2. AuthoritativeRegisterKeyLoader 평문 테스트
    test_results.append(("평문 파일 로더", test_authoritative_loader_with_plaintext()))
    
    # 3. 전체 암호화/복호화 워크플로우 테스트
    test_results.append(("전체 워크플로우", test_end_to_end_encryption()))
    
    # 4. 오류 처리 테스트
    test_results.append(("오류 처리", test_error_handling()))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n총 테스트: {len(test_results)}개")
    print(f"성공: {passed}개")
    print(f"실패: {failed}개")
    
    if failed == 0:
        print("\n🎉 모든 테스트가 성공했습니다!")
        print("\n✅ 보안 강화 구현이 완료되었습니다:")
        print("   - AES-256-GCM 암호화 시스템")
        print("   - Just-in-Time Decryption")
        print("   - 통합된 AuthoritativeRegisterKeyLoader")
        print("   - 완전한 하위 호환성")
        return 0
    else:
        print("\n💥 일부 테스트가 실패했습니다. 구현을 검토해주세요.")
        return 1

if __name__ == "__main__":
    sys.exit(main())