#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Token Verification - 간단한 토큰 검증
"""

import sys
import json
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_token_status():
    """토큰 상태 확인"""
    print("=== Token Status Check ===")
    
    # 토큰 캐시 파일들 확인
    cache_files = [
        PROJECT_ROOT / "support" / "token_cache.json",
        PROJECT_ROOT / "support" / "fixed_token_cache.json",
    ]
    
    found_tokens = 0
    
    for cache_file in cache_files:
        if cache_file.exists():
            try:
                cache_data = json.loads(cache_file.read_text(encoding='utf-8'))
                token_count = len(cache_data)
                print(f"[OK] {cache_file.name}: {token_count} tokens")
                found_tokens += token_count
                
                # 토큰 상세 정보
                for key, value in cache_data.items():
                    if isinstance(value, dict) and 'token' in value:
                        token_preview = value['token'][:30] + "..." if len(value['token']) > 30 else value['token']
                        print(f"  - {key}: {token_preview}")
                    elif isinstance(value, str) and len(value) > 20:
                        token_preview = value[:30] + "..." if len(value) > 30 else value
                        print(f"  - {key}: {token_preview}")
                        
            except Exception as e:
                print(f"[ERROR] {cache_file.name}: {e}")
        else:
            print(f"[MISSING] {cache_file.name}")
    
    print(f"\nTotal tokens found: {found_tokens}")
    return found_tokens > 0

def test_api_connection_simple():
    """간단한 API 연결 테스트"""
    print("\n=== Simple API Connection Test ===")
    
    try:
        # KIS API 커넥터 로드 테스트
        from support.api_connector import KISAPIConnector
        
        # 커넥터 초기화
        connector = KISAPIConnector()
        print("[OK] KIS API Connector loaded")
        
        # 토큰 발급 테스트
        if hasattr(connector, 'get_access_token'):
            token = connector.get_access_token()
            if token and len(token) > 20:
                print(f"[OK] Token obtained: {token[:30]}...")
                return True
            else:
                print(f"[FAIL] Invalid token: {token}")
                return False
        else:
            print("[FAIL] No get_access_token method")
            return False
            
    except Exception as e:
        print(f"[ERROR] API connection test failed: {e}")
        return False

def test_trading_system():
    """거래 시스템 테스트"""
    print("\n=== Trading System Test ===")
    
    try:
        # 거래 시스템 로드
        from support.minimal_day_trader import MinimalDayTrader
        
        trader = MinimalDayTrader()
        print("[OK] Minimal Day Trader loaded")
        
        # 실제 메서드 확인 (올바른 메서드 이름 사용)
        methods_to_check = ['get_current_balance', 'get_positions', 'get_account_info']
        available_methods = []
        
        for method_name in methods_to_check:
            if hasattr(trader, method_name):
                available_methods.append(method_name)
                print(f"  [OK] {method_name} method available")
            else:
                print(f"  [MISSING] {method_name} method not found")
        
        print(f"Available methods: {len(available_methods)}/{len(methods_to_check)}")
        return len(available_methods) > 0
        
    except Exception as e:
        print(f"[ERROR] Trading system test failed: {e}")
        return False

def main():
    """메인 검증"""
    print("GPT Trading System Verification")
    print("=" * 40)
    
    results = []
    
    # 1. 토큰 상태 확인
    token_ok = check_token_status()
    results.append(("Token Status", token_ok))
    
    # 2. API 연결 테스트
    api_ok = test_api_connection_simple()
    results.append(("API Connection", api_ok))
    
    # 3. 거래 시스템 테스트
    trading_ok = test_trading_system()
    results.append(("Trading System", trading_ok))
    
    # 결과 요약
    print("\n" + "=" * 40)
    print("VERIFICATION SUMMARY:")
    
    passed = 0
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    total = len(results)
    success_rate = (passed / total) * 100
    print(f"\nOverall: {passed}/{total} ({success_rate:.1f}%)")
    
    if success_rate >= 70:
        print("Status: HEALTHY")
        return 0
    elif success_rate >= 50:
        print("Status: WARNING")
        return 1
    else:
        print("Status: CRITICAL")
        return 2

if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\nExit Code: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        print(f"Verification failed: {e}")
        sys.exit(3)