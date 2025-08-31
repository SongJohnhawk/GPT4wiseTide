#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
실제 거래 메서드 테스트
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_actual_trading_methods():
    """실제 거래 메서드 테스트"""
    print("=== Actual Trading Methods Test ===")
    
    try:
        # MinimalDayTrader 로드
        from support.minimal_day_trader import MinimalDayTrader
        
        # MOCK 계좌로 초기화
        trader = MinimalDayTrader(account_type="MOCK")
        print("[OK] MinimalDayTrader initialized")
        
        # 실제 메서드 테스트 (async 메서드들)
        test_results = {}
        
        # 1. 계좌 잔고 조회
        try:
            balance = await trader.get_current_balance()
            print(f"[OK] get_current_balance: {balance:,.0f}원" if balance else "[OK] get_current_balance: method works")
            test_results['balance'] = True
        except Exception as e:
            print(f"[ERROR] get_current_balance: {e}")
            test_results['balance'] = False
        
        # 2. 보유 종목 조회
        try:
            positions = await trader.get_positions()
            print(f"[OK] get_positions: {len(positions)}개 포지션" if positions else "[OK] get_positions: method works")
            test_results['positions'] = True
        except Exception as e:
            print(f"[ERROR] get_positions: {e}")
            test_results['positions'] = False
        
        # 3. 계좌 정보 조회
        try:
            account_info = await trader.get_account_info()
            print(f"[OK] get_account_info: {len(account_info)} 항목" if account_info else "[OK] get_account_info: method works")
            test_results['account_info'] = True
        except Exception as e:
            print(f"[ERROR] get_account_info: {e}")
            test_results['account_info'] = False
        
        # 4. 주가 조회 (내부 메서드)
        try:
            stock_data = await trader._get_stock_current_data("005930")  # 삼성전자
            if stock_data:
                print(f"[OK] _get_stock_current_data: {stock_data.get('name', '삼성전자')} 조회 성공")
                test_results['stock_data'] = True
            else:
                print("[WARN] _get_stock_current_data: no data returned")
                test_results['stock_data'] = False
        except Exception as e:
            print(f"[ERROR] _get_stock_current_data: {e}")
            test_results['stock_data'] = False
        
        # 결과 요약
        successful_methods = sum(test_results.values())
        total_methods = len(test_results)
        success_rate = (successful_methods / total_methods) * 100
        
        print(f"\n=== Test Results ===")
        print(f"Successful methods: {successful_methods}/{total_methods} ({success_rate:.1f}%)")
        
        for method, result in test_results.items():
            status = "PASS" if result else "FAIL"
            print(f"  {method}: {status}")
        
        return success_rate >= 50
        
    except Exception as e:
        print(f"[CRITICAL] Trading methods test failed: {e}")
        return False

async def test_gpt5_system():
    """GPT-5 시스템 테스트"""
    print("\n=== GPT-5 System Test ===")
    
    try:
        # GPT-5 시스템 컴포넌트 로드
        from support.integrated_gpt_trader import IntegratedGPTTrader
        
        gpt_trader = IntegratedGPTTrader()
        print("[OK] IntegratedGPTTrader loaded")
        
        # 기본 기능 확인
        if hasattr(gpt_trader, 'make_trading_decision'):
            print("[OK] make_trading_decision method available")
            
            # 간단한 결정 요청 테스트
            test_data = {
                'symbol': '005930',
                'price': 70000,
                'volume': 1000,
                'news': ['삼성전자 호실적 발표']
            }
            
            try:
                decision = await gpt_trader.make_trading_decision(test_data)
                print(f"[OK] Trading decision generated: {decision.get('action', 'Unknown')}")
                return True
            except Exception as e:
                print(f"[ERROR] Decision generation failed: {e}")
                return False
        else:
            print("[MISSING] make_trading_decision method not found")
            return False
            
    except Exception as e:
        print(f"[ERROR] GPT-5 system test failed: {e}")
        return False

async def test_data_collection():
    """데이터 수집 시스템 테스트"""
    print("\n=== Data Collection System Test ===")
    
    try:
        from support.integrated_free_data_system import IntegratedFreeDataSystem
        
        data_system = IntegratedFreeDataSystem()
        print("[OK] IntegratedFreeDataSystem loaded")
        
        # 기본 데이터 수집 테스트
        if hasattr(data_system, 'collect_korean_stock_data'):
            try:
                # 간단한 데이터 수집 시도
                korea_data = await data_system.collect_korean_stock_data()
                if korea_data:
                    print(f"[OK] Korean stock data collected: {len(korea_data)} items")
                    return True
                else:
                    print("[WARN] No Korean stock data collected")
                    return False
            except Exception as e:
                print(f"[ERROR] Korean stock data collection failed: {e}")
                return False
        else:
            print("[MISSING] collect_korean_stock_data method not found")
            return False
            
    except Exception as e:
        print(f"[ERROR] Data collection system test failed: {e}")
        return False

async def main():
    """메인 테스트 실행"""
    print("Comprehensive Trading System Test")
    print("=" * 50)
    
    test_results = []
    
    # 1. 실제 거래 메서드 테스트
    trading_ok = await test_actual_trading_methods()
    test_results.append(("Trading Methods", trading_ok))
    
    # 2. GPT-5 시스템 테스트
    gpt5_ok = await test_gpt5_system()
    test_results.append(("GPT-5 System", gpt5_ok))
    
    # 3. 데이터 수집 시스템 테스트
    data_ok = await test_data_collection()
    test_results.append(("Data Collection", data_ok))
    
    # 전체 결과 요약
    print("\n" + "=" * 50)
    print("COMPREHENSIVE TEST SUMMARY:")
    
    passed = 0
    for test_name, result in test_results:
        status = "PASS" if result else "FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    total = len(test_results)
    success_rate = (passed / total) * 100
    print(f"\nOverall Success Rate: {passed}/{total} ({success_rate:.1f}%)")
    
    if success_rate >= 80:
        print("🎉 System Status: EXCELLENT")
        return 0
    elif success_rate >= 60:
        print("✅ System Status: GOOD")
        return 0
    elif success_rate >= 40:
        print("⚠️  System Status: WARNING")
        return 1
    else:
        print("❌ System Status: CRITICAL")
        return 2

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        print(f"\nExit Code: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        print(f"Comprehensive test failed: {e}")
        sys.exit(3)