#!/usr/bin/env python3
"""
실전투자 자동매매 시스템 통합 테스트
ProductionAutoTrader 클래스 전체 기능 검증
"""

import sys
import asyncio
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from support.production_auto_trader import ProductionAutoTrader
    from support.algorithm_loader import AlgorithmLoader
    from support.api_connector import KISAPIConnector
except ImportError as e:
    print(f"Import 오류: {e}")
    sys.exit(1)

async def test_production_auto_trader():
    """실전투자 자동매매 시스템 테스트"""
    
    print("=== 실전투자 자동매매 시스템 테스트 ===\n")
    
    test_results = []
    
    # 1. ProductionAutoTrader 클래스 초기화 테스트
    print("1. ProductionAutoTrader 클래스 초기화...")
    try:
        trader = ProductionAutoTrader(account_type="MOCK")
        print("   ✅ ProductionAutoTrader 초기화 성공")
        test_results.append(("초기화", True))
    except Exception as e:
        print(f"   ❌ ProductionAutoTrader 초기화 실패: {e}")
        test_results.append(("초기화", False))
        return test_results
    
    # 2. 설정 로딩 테스트
    print("\n2. 거래 설정 로딩 테스트...")
    try:
        if hasattr(trader, 'config') and trader.config:
            print("   ✅ 거래 설정 로딩 성공")
            test_results.append(("설정로딩", True))
        else:
            print("   ❌ 거래 설정 로딩 실패")
            test_results.append(("설정로딩", False))
    except Exception as e:
        print(f"   ❌ 거래 설정 로딩 오류: {e}")
        test_results.append(("설정로딩", False))
    
    # 3. AI 분석 시스템 테스트
    print("\n3. AI 분석 시스템 테스트...")
    try:
        # AI 기반 분석 시스템 초기화 테스트
        await trader._initialize_algorithm()
        
        if trader.algorithm and hasattr(trader.algorithm, 'name'):
            print(f"   ✅ AI 분석 시스템 초기화: {trader.algorithm.name}")
            test_results.append(("AI분석시스템", True))
        else:
            print("   ⚠️ AI 분석 시스템 초기화 실패 - 안전모드 사용")
            test_results.append(("AI분석시스템", False))
            
    except Exception as e:
        print(f"   ❌ AI 분석 시스템 오류: {e}")
        test_results.append(("AI분석시스템", False))
    
    # 4. API 연결 준비 테스트
    print("\n4. API 연결 준비 테스트...")
    try:
        # API 객체 생성만 테스트 (실제 연결X)
        api = KISAPIConnector("MOCK")
        print("   ✅ API 객체 생성 성공")
        test_results.append(("API준비", True))
    except Exception as e:
        print(f"   ❌ API 객체 생성 실패: {e}")
        test_results.append(("API준비", False))
    
    # 5. 매매 결과 클래스 테스트
    print("\n5. 매매 결과 클래스 테스트...")
    try:
        from support.production_auto_trader import TradingResult
        result = TradingResult(success=True, data={"test": "value"})
        if result.success and "test" in result.data:
            print("   ✅ 매매 결과 클래스 정상")
            test_results.append(("매매결과", True))
        else:
            print("   ❌ 매매 결과 클래스 오류")
            test_results.append(("매매결과", False))
    except Exception as e:
        print(f"   ❌ 매매 결과 클래스 테스트 실패: {e}")
        test_results.append(("매매결과", False))
    
    # 6. 통합 순환 관리자 테스트
    print("\n6. 통합 순환 관리자 테스트...")
    try:
        if hasattr(trader, 'cycle_manager') and trader.cycle_manager:
            print("   ✅ 통합 순환 관리자 초기화 성공")
            test_results.append(("순환관리자", True))
        else:
            print("   ❌ 통합 순환 관리자 초기화 실패")
            test_results.append(("순환관리자", False))
    except Exception as e:
        print(f"   ❌ 통합 순환 관리자 테스트 실패: {e}")
        test_results.append(("순환관리자", False))
    
    # 결과 요약
    print("\n" + "="*50)
    print("실전투자 자동매매 시스템 테스트 결과:")
    
    success_count = 0
    for test_name, result in test_results:
        status = "✅ 성공" if result else "❌ 실패"
        print(f"   - {test_name}: {status}")
        if result:
            success_count += 1
    
    print(f"\n성공률: {success_count}/{len(test_results)} ({success_count/len(test_results)*100:.1f}%)")
    
    if success_count == len(test_results):
        print("\n🎉 실전투자 자동매매 전체 테스트 완료!")
        print("✅ 모든 핵심 컴포넌트가 정상 작동합니다.")
        return True
    else:
        print(f"\n⚠️ {len(test_results) - success_count}개 컴포넌트에서 문제 발견")
        print("시스템 점검이 필요합니다.")
        return False

async def main():
    """메인 함수"""
    success = await test_production_auto_trader()
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)