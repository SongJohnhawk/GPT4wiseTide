#!/usr/bin/env python3
"""
종목 데이터 수집 테스트 스크립트
"""

import sys
from pathlib import Path

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from stock_data_collector import StockDataCollector


def test_stock_collection():
    """종목 데이터 수집 테스트"""
    print("=== 종목 데이터 수집 테스트 시작 ===")
    
    # StockDataCollector 인스턴스 생성
    collector = StockDataCollector(max_analysis_stocks=10)  # 테스트용으로 10개로 제한
    
    # 테마 종목 로드 테스트
    theme_stocks = collector.theme_stocks
    print(f"테마 종목 수: {len(theme_stocks)}개")
    
    if theme_stocks:
        print("테마 종목 목록:")
        for i, stock_code in enumerate(theme_stocks[:5]):  # 상위 5개만 표시
            stock_name = collector.get_stock_name(stock_code)
            print(f"  {i+1}. {stock_name}({stock_code})")
    else:
        print("❌ 테마 종목이 로드되지 않았습니다!")
    
    # 캐시 데이터 로드 테스트
    cached_data = collector.load_cached_data()
    if cached_data:
        print(f"\n캐시 데이터 존재: {cached_data.get('cached_at', 'Unknown')}")
        stock_info = cached_data.get('stock_info', {})
        print(f"캐시된 종목 정보: {len(stock_info)}개")
    else:
        print("\n캐시 데이터가 없습니다.")
    
    # enhanced_theme_stocks.json 파일 존재 확인
    theme_file = Path(__file__).parent / "support" / "enhanced_theme_stocks.json"
    print(f"\nenhanced_theme_stocks.json 존재 여부: {theme_file.exists()}")
    
    if theme_file.exists():
        import json
        with open(theme_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"JSON 파일 테마 수: {len([k for k in data.keys() if not k.startswith('_')])}개")
    
    print("\n=== 테스트 완료 ===")


def test_enhanced_theme_stocks():
    """enhanced_theme_stocks.py 테스트"""
    print("\n=== enhanced_theme_stocks.py 테스트 ===")
    
    try:
        from support.enhanced_theme_stocks import load_theme_stocks_list, get_default_stocks
        
        # 테마 종목 리스트 로드
        theme_stocks_list = load_theme_stocks_list()
        print(f"load_theme_stocks_list() 결과: {len(theme_stocks_list)}개")
        
        # 기본 종목 로드
        default_stocks = get_default_stocks()
        print(f"get_default_stocks() 결과: {len(default_stocks)}개")
        
        if theme_stocks_list:
            print("테마 종목 샘플:")
            for stock_code in theme_stocks_list[:3]:
                print(f"  - {stock_code}")
        
    except Exception as e:
        print(f"❌ enhanced_theme_stocks.py 테스트 실패: {e}")


if __name__ == "__main__":
    test_stock_collection()
    test_enhanced_theme_stocks()