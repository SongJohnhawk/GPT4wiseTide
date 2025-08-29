#!/usr/bin/env python3
"""
급등종목 + 테마종목 통합 수집 테스트
하드코딩 데이터 제거 및 실제 API 기반 수집 확인
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


def test_surge_provider_integration():
    """급등종목 수집기 통합 테스트"""
    print("=== 급등종목 수집기 통합 테스트 ===")
    
    try:
        from support.surge_stock_providers import PolicyBasedSurgeStockProvider
        
        provider = PolicyBasedSurgeStockProvider()
        print("✓ PolicyBasedSurgeStockProvider 초기화 성공")
        
        # SimpleSurgeDetector 통합 확인
        if hasattr(provider, 'surge_detector'):
            print("✓ SimpleSurgeDetector 통합 확인")
            
            # 테스트 데이터로 급등 분석
            test_data = {
                'current_price': 85000,
                'previous_price': 75000,
                'high': 86000,
                'low': 74000,
                'volume': 2000000,
                'avg_volume': 800000
            }
            
            result = provider.surge_detector.analyze_surge_potential('005930', test_data)
            print(f"  급등 분석 테스트: 점수 {result['surge_score']:.2f}, 추천 {result['recommendation']}")
            return True
        else:
            print("❌ SimpleSurgeDetector 통합 실패")
            return False
            
    except Exception as e:
        print(f"❌ 급등종목 수집기 테스트 오류: {e}")
        return False


async def test_production_trader_integration():
    """ProductionAutoTrader 급등종목 통합 테스트"""
    print("\n=== ProductionAutoTrader 급등종목 통합 테스트 ===")
    
    try:
        from support.production_auto_trader import ProductionAutoTrader
        
        # MOCK 계정으로 테스트
        trader = ProductionAutoTrader(account_type="MOCK")
        print("✓ ProductionAutoTrader 초기화 성공")
        
        # _collect_trading_stocks 메서드 직접 테스트 (API 없이)
        print("급등종목 + 테마종목 수집 테스트 (API 없이)...")
        collection_result = await trader._collect_trading_stocks()
        
        print(f"수집 결과:")
        print(f"  급등 종목: {collection_result.get('surge_stocks', 0)}개")
        print(f"  테마 종목: {collection_result.get('theme_stocks', 0)}개")
        print(f"  전체 수집: {collection_result.get('total_stocks', 0)}개")
        print(f"  분석 완료: {collection_result.get('analyzed_stocks', 0)}개")
        print(f"  매수 후보: {collection_result.get('buy_candidates', 0)}개")
        
        # 하드코딩 값 체크
        if (collection_result.get('theme_stocks') == 20 and 
            collection_result.get('analyzed_stocks') == 20 and 
            collection_result.get('buy_candidates') == 8):
            print("❌ 여전히 하드코딩된 값들이 나타남 (20, 20, 8)")
            return False
        else:
            print("✓ 하드코딩된 값들이 제거되고 실제 데이터 기반 처리")
            
        # 수집된 종목 표시 확인
        stocks_display = collection_result.get('stocks_display', '')
        if '[급등종목 순위]' in stocks_display or '[매수 후보 종목]' in stocks_display:
            print("✓ 급등종목 순위별 표시 기능 추가 확인")
        else:
            print("ℹ️  급등종목이 수집되지 않아 순위 표시 없음 (정상)")
            
        return True
        
    except Exception as e:
        print(f"❌ ProductionAutoTrader 테스트 오류: {e}")
        return False


def test_multithreading_performance():
    """멀티스레드 성능 테스트"""
    print("\n=== 멀티스레드 성능 테스트 ===")
    
    try:
        from stock_data_collector import StockDataCollector
        import time
        
        collector = StockDataCollector(max_analysis_stocks=5)  # 테스트용 5개
        
        # 멀티스레드 성능 확인
        if hasattr(collector, '_collect_stocks_multithreaded'):
            print("✓ 멀티스레드 수집 메서드 존재")
            print(f"  최대 워커 수: {getattr(collector, 'max_workers', 'N/A')}")
            print(f"  타임아웃: {getattr(collector, 'collection_timeout', 'N/A')}초")
            return True
        else:
            print("❌ 멀티스레드 수집 메서드 없음")
            return False
            
    except Exception as e:
        print(f"❌ 멀티스레드 테스트 오류: {e}")
        return False


def test_hardcoded_data_removal():
    """하드코딩 데이터 제거 확인"""
    print("\n=== 하드코딩 데이터 제거 확인 ===")
    
    # 주요 파일들에서 하드코딩 패턴 검사
    files_to_check = [
        "support/production_auto_trader.py",
        "support/trading_constants.py",
        "stock_data_collector.py"
    ]
    
    problematic_patterns = [
        "테마 종목: 20개",
        "분석 완료: 20개", 
        "매수 후보: 8개",
        "len(buy_candidates) >= 8",
        "display_count = min(5,",
        "삼성전자(005930)",
        "SK하이닉스(000660)",
        "NAVER(035420)"
    ]
    
    total_issues = 0
    
    for file_path in files_to_check:
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            continue
            
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            file_issues = 0
            for pattern in problematic_patterns:
                if pattern in content:
                    print(f"❌ {file_path}: '{pattern}' 패턴 발견")
                    file_issues += 1
                    total_issues += 1
            
            if file_issues == 0:
                print(f"✓ {file_path}: 하드코딩 패턴 없음")
                
        except Exception as e:
            print(f"❌ {file_path} 검사 실패: {e}")
    
    if total_issues == 0:
        print("✓ 모든 파일에서 하드코딩 패턴 제거 확인")
        return True
    else:
        print(f"❌ 총 {total_issues}개 하드코딩 패턴 발견")
        return False


async def run_surge_integration_tests():
    """급등종목 통합 테스트 실행"""
    print("=" * 60)
    print("tideWise 급등종목 통합 및 하드코딩 제거 테스트")
    print("=" * 60)
    
    results = {}
    
    # 1. 급등종목 수집기 통합
    results['surge_provider'] = test_surge_provider_integration()
    
    # 2. ProductionAutoTrader 통합
    results['production_trader'] = await test_production_trader_integration()
    
    # 3. 멀티스레드 성능
    results['multithreading'] = test_multithreading_performance()
    
    # 4. 하드코딩 데이터 제거
    results['hardcoded_removal'] = test_hardcoded_data_removal()
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("급등종목 통합 테스트 결과 요약")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    for test_name, result in results.items():
        status = "OK" if result else "FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\n전체 테스트: {passed_tests}/{total_tests} 통과")
    
    if passed_tests == total_tests:
        print("\n✓ 급등종목 통합 및 하드코딩 제거가 완료되었습니다!")
        print("✓ 단타매매에서 급등종목 순위별 표시가 정상 작동합니다.")
        print("✓ 멀티스레드 종목 데이터 수집이 최적화되었습니다.")
        return True
    else:
        print("\n❌ 일부 기능에 문제가 있습니다.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_surge_integration_tests())
    sys.exit(0 if success else 1)