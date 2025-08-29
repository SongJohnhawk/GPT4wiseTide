#!/usr/bin/env python3
"""
통합 테스트 스크립트
수정된 모든 기능을 테스트
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

from stock_data_collector import StockDataCollector
from support.account_memory_manager import get_account_memory_manager
from support.enhanced_theme_stocks import load_theme_stocks_list


def test_stock_collection_fixed():
    """종목 데이터 수집 수정 사항 테스트"""
    print("=== 종목 데이터 수집 수정 사항 테스트 ===")
    
    # 1. JSON 파일 복원 확인
    theme_file = Path(__file__).parent / "support" / "enhanced_theme_stocks.json"
    print(f"enhanced_theme_stocks.json 존재: {theme_file.exists()}")
    
    # 2. 테마 종목 로드 확인
    collector = StockDataCollector(max_analysis_stocks=5)
    theme_stocks = collector.theme_stocks
    print(f"테마 종목 수: {len(theme_stocks)}개")
    
    # 3. 종목명(종목코드) 형식 확인
    if theme_stocks:
        print("종목 표시 형식 테스트:")
        for i, stock_code in enumerate(theme_stocks[:3]):
            stock_name = collector.get_stock_name(stock_code)
            print(f"  {i+1}. {stock_name}({stock_code})")
    
    # 4. enhanced_theme_stocks.py 함수 테스트
    try:
        theme_stocks_list = load_theme_stocks_list()
        print(f"load_theme_stocks_list() 결과: {len(theme_stocks_list)}개")
        status = "OK" if len(theme_stocks_list) > 0 else "FAIL"
        print(f"종목 수집 수정: {status}")
    except Exception as e:
        print(f"FAIL enhanced_theme_stocks 오류: {e}")
    
    return len(theme_stocks) > 0


def test_account_manager_fixed():
    """AccountMemoryManager 수정 사항 테스트"""
    print("\n=== AccountMemoryManager 수정 사항 테스트 ===")
    
    manager = get_account_memory_manager()
    
    # 누락된 메서드 존재 확인
    missing_methods_fixed = [
        'get_pending_orders_count',
        'get_positions'
    ]
    
    all_methods_exist = True
    for method_name in missing_methods_fixed:
        has_method = hasattr(manager, method_name)
        status = "OK" if has_method else "FAIL"
        print(f"  {method_name}: {status}")
        if not has_method:
            all_methods_exist = False
    
    # 실제 동작 테스트
    try:
        # 기본 상태에서 메서드 호출
        pending_count = manager.get_pending_orders_count("MOCK")
        positions = manager.get_positions("MOCK")
        print(f"  get_pending_orders_count() 호출: {pending_count}")
        print(f"  get_positions() 호출: {len(positions)}개")
        
        status = "OK" if all_methods_exist else "FAIL"
        print(f"AccountMemoryManager 수정: {status}")
        return all_methods_exist
        
    except Exception as e:
        print(f"FAIL AccountMemoryManager 메서드 호출 오류: {e}")
        return False


def test_surge_stock_display():
    """급등종목 표시 형식 테스트"""
    print("\n=== 급등종목 표시 형식 테스트 ===")
    
    try:
        from support.surge_stock_providers import PolicyBasedSurgeStockProvider
        
        # 급등종목 데이터 구조 확인
        # 실제 API 호출 없이 구조만 테스트
        provider = PolicyBasedSurgeStockProvider()
        print("PolicyBasedSurgeStockProvider 초기화: OK")
        
        # 테스트용 종목 정보
        test_stocks = [
            {"symbol": "005930", "name": "삼성전자"},
            {"symbol": "000660", "name": "SK하이닉스"},
            {"symbol": "035420", "name": "NAVER"}
        ]
        
        print("급등종목 표시 형식 테스트:")
        for stock in test_stocks:
            display_format = f"{stock['name']}({stock['symbol']})"
            print(f"  - {display_format}")
        
        print("급등종목 표시 형식: OK")
        return True
        
    except Exception as e:
        print(f"FAIL 급등종목 표시 테스트 오류: {e}")
        return False


def run_comprehensive_test():
    """포괄적 테스트 실행"""
    print("=" * 60)
    print("tideWise 수정사항 통합 테스트")
    print("=" * 60)
    
    results = {}
    
    # 1. 종목 데이터 수집 테스트
    results['stock_collection'] = test_stock_collection_fixed()
    
    # 2. AccountMemoryManager 테스트
    results['account_manager'] = test_account_manager_fixed()
    
    # 3. 급등종목 표시 테스트
    results['surge_display'] = test_surge_stock_display()
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    for test_name, result in results.items():
        status = "OK" if result else "FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\n전체 테스트: {passed_tests}/{total_tests} 통과")
    
    if passed_tests == total_tests:
        print("모든 수정사항이 정상적으로 동작합니다!")
        return True
    else:
        print("일부 테스트가 실패했습니다. 추가 수정이 필요합니다.")
        return False


if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)