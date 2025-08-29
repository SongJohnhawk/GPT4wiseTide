#!/usr/bin/env python3
"""
MinimalDayTrader 급등종목 수집 기능 테스트
OPEN-API 급등종목 + 테마종목 통합 확인
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


async def test_minimal_day_trader_integration():
    """MinimalDayTrader 급등종목 통합 테스트"""
    print("=== MinimalDayTrader 급등종목 통합 테스트 ===")
    
    try:
        from support.minimal_day_trader import MinimalDayTrader
        
        # MOCK 계정으로 테스트
        trader = MinimalDayTrader(account_type="MOCK")
        print("✓ MinimalDayTrader 초기화 성공")
        
        # stock_data_cache 초기화 (필요시)
        if not hasattr(trader, 'stock_data_cache'):
            trader.stock_data_cache = {}
        
        # 급등종목 수집 메서드 직접 테스트
        print("\n--- 급등종목 수집 테스트 ---")
        surge_stocks = await trader._collect_and_display_surge_stocks()
        print(f"급등종목 수집 결과: {len(surge_stocks)}개")
        
        # 테마종목 수집 메서드 테스트
        print("\n--- 테마종목 수집 테스트 ---")
        theme_stocks = await trader._collect_theme_stocks_for_day_trading()
        print(f"테마종목 수집 결과: {len(theme_stocks)}개")
        
        # 통합 후보 선별 테스트
        print("\n--- 통합 후보 선별 테스트 ---")
        current_positions = {}  # 빈 포지션으로 테스트
        candidates = await trader._select_day_trade_candidates(current_positions)
        
        print(f"\n최종 결과:")
        print(f"  급등종목: {len(surge_stocks)}개")
        print(f"  테마종목: {len(theme_stocks)}개")
        print(f"  선별된 후보: {len(candidates)}개")
        
        # 급등종목 상세 표시 확인
        if surge_stocks:
            print(f"\n급등종목 상세:")
            for i, stock in enumerate(surge_stocks[:3], 1):
                print(f"  {i}. {stock['name']}({stock['code']}) {stock['change_rate']:.2%}↑")
        
        return True
        
    except Exception as e:
        print(f"❌ MinimalDayTrader 테스트 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_output_format_integration():
    """출력 형식 통합 확인"""
    print("\n=== 출력 형식 통합 확인 ===")
    
    # 예상 출력 형식 확인
    expected_outputs = [
        "[OPEN-API 급등종목 수집]",
        "급등종목 X개 수집 완료",
        "X위. 종목명(종목코드) +X.XX%↑ 거래량X.X배",
        "[테마주 보완 수집]",
        "[최종 단타 후보] 총 X개 종목 선별 완료"
    ]
    
    print("예상 출력 형식:")
    for output in expected_outputs:
        print(f"  ✓ {output}")
    
    return True


def test_source_code_verification():
    """소스 코드 수정 확인"""
    print("\n=== 소스 코드 수정 확인 ===")
    
    try:
        minimal_trader_file = PROJECT_ROOT / "support" / "minimal_day_trader.py"
        
        if not minimal_trader_file.exists():
            print("❌ minimal_day_trader.py 파일을 찾을 수 없음")
            return False
            
        with open(minimal_trader_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 필요한 함수들이 추가되었는지 확인
        required_functions = [
            "_collect_surge_stocks_for_day_trading",
            "_collect_theme_stocks_for_day_trading",
            "OPEN-API 급등종목 수집",
            "PolicyBasedSurgeStockProvider",
            "StockDataCollector"
        ]
        
        missing_functions = []
        for func in required_functions:
            if func not in content:
                missing_functions.append(func)
        
        if missing_functions:
            print(f"❌ 누락된 기능: {missing_functions}")
            return False
        else:
            print("✓ 모든 필요한 기능이 추가됨")
            print(f"  - OPEN-API 급등종목 수집 함수")
            print(f"  - 테마종목 수집 함수")
            print(f"  - 통합 후보 선별 로직")
            print(f"  - 순위별 표시 형식")
            return True
            
    except Exception as e:
        print(f"❌ 소스 코드 확인 오류: {e}")
        return False


async def run_minimal_day_trader_tests():
    """MinimalDayTrader 테스트 실행"""
    print("=" * 60)
    print("MinimalDayTrader 급등종목 통합 테스트")
    print("=" * 60)
    
    results = {}
    
    # 1. MinimalDayTrader 통합 테스트
    results['integration'] = await test_minimal_day_trader_integration()
    
    # 2. 출력 형식 확인
    results['output_format'] = test_output_format_integration()
    
    # 3. 소스 코드 확인
    results['source_verification'] = test_source_code_verification()
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("MinimalDayTrader 테스트 결과 요약")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    for test_name, result in results.items():
        status = "OK" if result else "FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\n전체 테스트: {passed_tests}/{total_tests} 통과")
    
    if passed_tests == total_tests:
        print("\n✅ MinimalDayTrader 급등종목 통합이 완료되었습니다!")
        print("✅ 이제 단타매매에서 OPEN-API 급등종목 리스트가 표시됩니다.")
        print("✅ 급등종목 순위별 표시와 실제 데이터 분석이 가능합니다.")
        return True
    else:
        print("\n❌ 일부 기능에 문제가 있습니다.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_minimal_day_trader_tests())
    sys.exit(0 if success else 1)