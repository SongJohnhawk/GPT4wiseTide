#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Security Enhancement Test
Register_Key.md 암호화/복호화 시스템 간단 테스트
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_imports():
    """기본 import 테스트"""
    print("Testing imports...")
    
    try:
        from support.secure_key_handler import SecureKeyHandler, setup_secure_environment
        print("  SUCCESS: SecureKeyHandler import")
        
        from support.authoritative_register_key_loader import AuthoritativeRegisterKeyLoader
        print("  SUCCESS: AuthoritativeRegisterKeyLoader import")
        
        return True
    except Exception as e:
        print(f"  ERROR: Import failed - {e}")
        return False

def test_basic_encryption():
    """기본 암호화/복호화 테스트"""
    print("Testing basic encryption...")
    
    try:
        from support.secure_key_handler import SecureKeyHandler, setup_secure_environment
        
        # 보안 환경 설정
        setup_secure_environment()
        print("  SUCCESS: Security environment setup")
        
        # 핸들러 생성
        handler = SecureKeyHandler()
        print("  SUCCESS: Handler created")
        
        # 테스트 데이터
        test_text = "test data for encryption"
        
        # 암호화
        encrypted = handler.encrypt(test_text)
        print(f"  SUCCESS: Encryption (length: {len(encrypted)})")
        
        # 복호화
        decrypted = handler.decrypt(encrypted)
        print("  SUCCESS: Decryption")
        
        # 검증
        if decrypted == test_text:
            print("  SUCCESS: Data integrity verified")
            return True
        else:
            print("  ERROR: Data mismatch")
            return False
            
    except Exception as e:
        print(f"  ERROR: Encryption test failed - {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("=" * 50)
    print("tideWise Security Test")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("Encryption Test", test_basic_encryption),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n[{test_name}]")
        result = test_func()
        results.append((test_name, result))
        status = "PASS" if result else "FAIL"
        print(f"Result: {status}")
    
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {total}, Passed: {passed}, Failed: {total - passed}")
    
    if passed == total:
        print("\nALL TESTS PASSED - Security implementation working!")
        return 0
    else:
        print("\nSOME TESTS FAILED - Check implementation")
        return 1

if __name__ == "__main__":
    sys.exit(main())