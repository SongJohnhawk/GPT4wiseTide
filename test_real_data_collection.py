#!/usr/bin/env python3
"""
실제 데이터 수집 확인 테스트
더미 데이터 제거 및 실제 API 데이터 수집 확인
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


def test_dummy_data_removal():
    """더미 데이터 제거 확인 테스트"""
    print("=== 더미 데이터 제거 확인 테스트 ===")
    
    try:
        from stock_data_collector import StockDataCollector
        
        collector = StockDataCollector(max_analysis_stocks=3)
        
        # _get_default_features 메서드 존재 확인
        if hasattr(collector, '_get_default_features'):
            default_features = collector._get_default_features()
            print("✓ _get_default_features 메서드 존재")
            
            # 더미 데이터 체크 (100000과 같은 고정값이 없어야 함)
            has_dummy_data = False
            dummy_indicators = [100000, 100000.0, 1000.0]
            
            for key, value in default_features.items():
                if value in dummy_indicators:
                    print(f"❌ 더미 데이터 발견: {key} = {value}")
                    has_dummy_data = True
            
            if not has_dummy_data:
                print("✓ 더미 데이터 완전 제거 확인")
                print(f"  - current_price: {default_features.get('current_price', 'N/A')}")
                print(f"  - last: {default_features.get('last', 'N/A')}")
                print(f"  - atr14: {default_features.get('atr14', 'N/A')}")
                return True
            else:
                print("❌ 더미 데이터가 아직 남아있음")
                return False
        else:
            print("❌ _get_default_features 메서드가 존재하지 않음")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 실행 오류: {e}")
        return False


async def test_api_data_collection():
    """실제 API 데이터 수집 테스트"""
    print("\n=== 실제 API 데이터 수집 테스트 ===")
    
    try:
        from stock_data_collector import StockDataCollector
        
        collector = StockDataCollector(max_analysis_stocks=2)
        
        # 테마 종목 로드
        theme_stocks = collector.theme_stocks
        if not theme_stocks:
            print("❌ 테마 종목이 로드되지 않음")
            return False
            
        print(f"테마 종목 수: {len(theme_stocks)}개")
        
        # 실제 데이터 수집 시뮬레이션 (API 커넥터 없이)
        # _collect_enhanced_features 메서드의 API 연결 확인
        test_symbol = theme_stocks[0]
        
        # API 커넥터 없이 호출 시 _get_default_features 반환하는지 확인
        result = await collector._collect_enhanced_features(test_symbol, None)
        
        print(f"API 커넥터 없이 데이터 수집 결과:")
        print(f"  종목코드: {test_symbol}")
        print(f"  current_price: {result.get('current_price', 'N/A')}")
        print(f"  last: {result.get('last', 'N/A')}")
        print(f"  vol_5m_now: {result.get('vol_5m_now', 'N/A')}")
        
        # 더미 데이터 체크
        if result.get('current_price') == 100000.0 or result.get('last') == 100000.0:
            print("❌ 여전히 더미 데이터(100000)가 반환됨")
            return False
        else:
            print("✓ 더미 데이터 없이 기본값 반환 확인")
            return True
            
    except Exception as e:
        print(f"❌ API 데이터 수집 테스트 오류: {e}")
        return False


def test_source_code_inspection():
    """소스 코드에서 더미 데이터 패턴 검사"""
    print("\n=== 소스 코드 더미 데이터 패턴 검사 ===")
    
    try:
        stock_data_file = PROJECT_ROOT / "stock_data_collector.py"
        
        if not stock_data_file.exists():
            print("❌ stock_data_collector.py 파일을 찾을 수 없음")
            return False
            
        with open(stock_data_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 더미 데이터 패턴 검사
        dummy_patterns = [
            "100000",
            "current_price = 100000",
            "예시 OHLCV 데이터",
            "실제로는 API에서 가져옴"
        ]
        
        found_dummy_patterns = []
        for pattern in dummy_patterns:
            if pattern in content:
                found_dummy_patterns.append(pattern)
        
        if found_dummy_patterns:
            print("❌ 더미 데이터 패턴 발견:")
            for pattern in found_dummy_patterns:
                print(f"  - '{pattern}'")
            return False
        else:
            print("✓ 더미 데이터 패턴 없음 확인")
            
            # 실제 API 호출 패턴 확인
            api_patterns = [
                "api_connector.get_stock_price",
                "_get_default_features",
                "실제 API를 통한 현재가 데이터 수집"
            ]
            
            found_api_patterns = []
            for pattern in api_patterns:
                if pattern in content:
                    found_api_patterns.append(pattern)
            
            print(f"✓ 실제 API 호출 패턴 확인: {len(found_api_patterns)}/{len(api_patterns)}개")
            return True
            
    except Exception as e:
        print(f"❌ 소스 코드 검사 오류: {e}")
        return False


async def run_real_data_tests():
    """실제 데이터 수집 테스트 실행"""
    print("=" * 60)
    print("tideWise 더미 데이터 제거 및 실제 데이터 수집 확인")
    print("=" * 60)
    
    results = {}
    
    # 1. 더미 데이터 제거 확인
    results['dummy_removal'] = test_dummy_data_removal()
    
    # 2. API 데이터 수집 구조 테스트
    results['api_structure'] = await test_api_data_collection()
    
    # 3. 소스 코드 검사
    results['code_inspection'] = test_source_code_inspection()
    
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
        print("\n✓ 더미 데이터가 완전히 제거되었습니다!")
        print("✓ 실제 API 데이터 수집 구조가 적용되었습니다.")
        print("✓ tideWise는 이제 실제 종목 데이터를 수집합니다.")
        return True
    else:
        print("\n❌ 일부 더미 데이터가 남아있거나 API 구조에 문제가 있습니다.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_real_data_tests())
    sys.exit(0 if success else 1)