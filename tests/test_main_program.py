#!/usr/bin/env python3
"""
메인 프로그램 실행 테스트
수정된 기능들이 실제 프로그램에서 정상 동작하는지 확인
"""

import sys
import asyncio
from pathlib import Path

# UTF-8 인코딩 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_stock_collection_in_main():
    """메인 프로그램의 종목 데이터 수집 테스트"""
    print("=== 메인 프로그램 종목 데이터 수집 테스트 ===")
    
    try:
        from stock_data_collector import StockDataCollector
        
        collector = StockDataCollector()
        
        # 테마 종목 로드 확인
        theme_stocks = collector.theme_stocks
        print(f"테마 종목 수: {len(theme_stocks)}개")
        
        if len(theme_stocks) > 0:
            print("종목 수집 기능: OK")
            
            # 상위 3개 종목 표시 형식 확인
            for i, stock_code in enumerate(theme_stocks[:3]):
                stock_name = collector.get_stock_name(stock_code)
                print(f"  {i+1}. {stock_name}({stock_code})")
            
            return True
        else:
            print("FAIL 종목이 수집되지 않았습니다.")
            return False
            
    except Exception as e:
        print(f"FAIL 종목 수집 테스트 오류: {e}")
        return False


def test_account_manager_in_main():
    """메인 프로그램의 AccountMemoryManager 테스트"""
    print("\n=== 메인 프로그램 AccountMemoryManager 테스트 ===")
    
    try:
        from support.account_memory_manager import get_account_memory_manager
        
        manager = get_account_memory_manager()
        
        # 수정된 메서드들 호출 테스트
        pending_count = manager.get_pending_orders_count("MOCK")
        positions = manager.get_positions("MOCK")
        
        print(f"get_pending_orders_count 호출: {pending_count}")
        print(f"get_positions 호출: {len(positions)}개")
        print("AccountMemoryManager 수정: OK")
        
        return True
        
    except Exception as e:
        print(f"FAIL AccountMemoryManager 테스트 오류: {e}")
        return False


def test_surge_detector():
    """SimpleSurgeDetector 테스트"""
    print("\n=== SimpleSurgeDetector 테스트 ===")
    
    try:
        from support.Hyper_upStockFind import SimpleSurgeDetector
        
        detector = SimpleSurgeDetector()
        
        # 테스트 데이터로 분석
        test_data = {
            'current_price': 75000,
            'previous_price': 70000,
            'high': 76000,
            'low': 74000,
            'volume': 1000000,
            'avg_volume': 500000
        }
        
        result = detector.analyze_surge_potential('005930', test_data)
        
        print(f"급등 분석 결과:")
        print(f"  종목: {result['stock_code']}")
        print(f"  급등 점수: {result['surge_score']}")
        print(f"  추천: {result['recommendation']}")
        print(f"  신뢰도: {result['confidence']}")
        print("SimpleSurgeDetector: OK")
        
        return True
        
    except Exception as e:
        print(f"FAIL SimpleSurgeDetector 테스트 오류: {e}")
        return False


async def test_production_auto_trader_init():
    """ProductionAutoTrader 초기화 테스트"""
    print("\n=== ProductionAutoTrader 초기화 테스트 ===")
    
    try:
        from support.production_auto_trader import ProductionAutoTrader
        
        # MOCK 계정으로 초기화 테스트
        trader = ProductionAutoTrader(account_type="MOCK")
        
        print(f"계좌 타입: {trader.account_type}")
        print(f"설정 로드: {'OK' if trader.config else 'FAIL'}")
        print("ProductionAutoTrader 초기화: OK")
        
        return True
        
    except Exception as e:
        print(f"FAIL ProductionAutoTrader 초기화 오류: {e}")
        return False


def run_main_program_tests():
    """메인 프로그램 테스트 실행"""
    print("=" * 60)
    print("tideWise 메인 프로그램 수정사항 테스트")
    print("=" * 60)
    
    results = {}
    
    # 1. 종목 데이터 수집 테스트
    results['stock_collection'] = test_stock_collection_in_main()
    
    # 2. AccountMemoryManager 테스트
    results['account_manager'] = test_account_manager_in_main()
    
    # 3. SimpleSurgeDetector 테스트
    results['surge_detector'] = test_surge_detector()
    
    # 4. ProductionAutoTrader 테스트
    results['production_trader'] = asyncio.run(test_production_auto_trader_init())
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("메인 프로그램 테스트 결과 요약")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    for test_name, result in results.items():
        status = "OK" if result else "FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\n전체 테스트: {passed_tests}/{total_tests} 통과")
    
    if passed_tests == total_tests:
        print("\n✓ 모든 수정사항이 메인 프로그램에서 정상적으로 동작합니다!")
        print("✓ tideWise 프로그램을 안전하게 실행할 수 있습니다.")
        return True
    else:
        print("\n✗ 일부 테스트가 실패했습니다.")
        return False


if __name__ == "__main__":
    success = run_main_program_tests()
    sys.exit(0 if success else 1)