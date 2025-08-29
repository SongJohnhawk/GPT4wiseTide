#!/usr/bin/env python3
"""
테마 종목 초기화 모듈
- 백테스팅용: 100+개 종목 수집 (comprehensive_data_collector)
- 실전투자용: 30+개 종목 수집 (trading_stock_collector)
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

class ThemeStockInitializer:
    """테마 종목 초기화 클래스"""
    
    def __init__(self, is_for_trading: bool = True):
        self.project_root = Path(__file__).parent.parent
        self.enhanced_theme_file = self.project_root / "enhanced_theme_stocks.json"
        self.is_for_trading = is_for_trading  # True: 실전투자용(30+개), False: 백테스팅용(100+개)
    
    def is_theme_data_available(self) -> bool:
        """테마 데이터 파일이 존재하고 유효한지 확인 (용도별 최소 수량 체크)"""
        try:
            if not self.enhanced_theme_file.exists():
                return False
            
            # 파일 크기 및 기본 구조 확인
            import json
            with open(self.enhanced_theme_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 최소 테마와 종목 수 확인
            if not data or len(data) == 0:
                return False
            
            total_stocks = 0
            for theme_name, theme_data in data.items():
                if isinstance(theme_data, dict) and 'stocks' in theme_data:
                    total_stocks += len(theme_data['stocks'])
            
            # 용도별 최소 종목 수 확인
            min_required = 30 if self.is_for_trading else 80  # 실전투자: 30+개, 백테스팅: 80+개
            return total_stocks >= min_required
            
        except Exception as e:
            logger.debug(f"테마 데이터 확인 실패: {e}")
            return False
    
    async def initialize_theme_stocks(self, force_refresh: bool = False) -> bool:
        """테마 종목 데이터 초기화 (용도별 수집기 선택)"""
        try:
            # 기존 데이터가 있고 강제 새로고침이 아니면 스킵
            if not force_refresh and self.is_theme_data_available():
                data_type = "실전투자용" if self.is_for_trading else "백테스팅용"
                logger.info(f"기존 {data_type} 테마 종목 데이터를 사용합니다")
                return True
            
            if self.is_for_trading:
                # 실전투자용: 경량화된 데이터 수집 (30+개, 멀티스레드)
                logger.info("실전투자용 경량화된 테마 종목 데이터 수집을 시작합니다...")
                from support.trading_stock_collector import collect_trading_stocks
                success = await collect_trading_stocks(is_mock=True)
            else:
                # 백테스팅용: 종합적인 데이터 수집 (100+개)
                logger.info("백테스팅용 종합적인 테마 종목 데이터 수집을 시작합니다...")
                from backtesting.comprehensive_data_collector import ComprehensiveDataCollector
                collector = ComprehensiveDataCollector()
                success = await collector.run_comprehensive_collection()
            
            if success:
                data_type = "실전투자용 경량화" if self.is_for_trading else "백테스팅용 종합"
                logger.info(f"{data_type} 테마 종목 데이터 수집 완료")
                return True
            else:
                logger.warning("테마 종목 데이터 수집에 실패했습니다")
                return False
                
        except ImportError as e:
            logger.error(f"데이터 수집 모듈을 찾을 수 없습니다: {e}")
            return False
        except Exception as e:
            logger.error(f"테마 종목 초기화 실패: {e}")
            return False
    
    async def ensure_theme_stocks_ready(self, timeout_minutes: int = 10) -> bool:
        """테마 종목 데이터가 준비되었는지 확인하고 필요시 수집"""
        try:
            # 기존 데이터 확인
            if self.is_theme_data_available():
                logger.info("테마 종목 데이터가 이미 준비되어 있습니다")
                return True
            
            logger.info("테마 종목 데이터가 없어서 수집을 시작합니다...")
            
            # 타임아웃 설정
            timeout_seconds = timeout_minutes * 60
            
            try:
                # 타임아웃과 함께 데이터 수집 실행
                success = await asyncio.wait_for(
                    self.initialize_theme_stocks(force_refresh=True),
                    timeout=timeout_seconds
                )
                
                if success:
                    logger.info("테마 종목 데이터 수집이 완료되었습니다")
                    return True
                else:
                    logger.warning("테마 종목 데이터 수집에 실패했습니다. 기본 종목을 사용합니다.")
                    return False
                    
            except asyncio.TimeoutError:
                logger.warning(f"테마 종목 데이터 수집이 {timeout_minutes}분 내에 완료되지 않았습니다")
                return False
                
        except Exception as e:
            logger.error(f"테마 종목 준비 확인 실패: {e}")
            return False

# 글로벌 인스턴스
_trading_initializer = None
_backtesting_initializer = None

def get_theme_stock_initializer(is_for_trading: bool = True) -> ThemeStockInitializer:
    """ThemeStockInitializer 싱글톤 인스턴스 반환 (용도별)"""
    global _trading_initializer, _backtesting_initializer
    
    if is_for_trading:
        if _trading_initializer is None:
            _trading_initializer = ThemeStockInitializer(is_for_trading=True)
        return _trading_initializer
    else:
        if _backtesting_initializer is None:
            _backtesting_initializer = ThemeStockInitializer(is_for_trading=False)
        return _backtesting_initializer

async def ensure_theme_stocks_available(is_for_trading: bool = True) -> bool:
    """테마 종목 데이터가 사용 가능한지 확인하고 필요시 수집 (용도별)"""
    initializer = get_theme_stock_initializer(is_for_trading)
    return await initializer.ensure_theme_stocks_ready()

async def ensure_trading_stocks_available() -> bool:
    """실전투자용 테마 종목 데이터 확인 (30+개, 멀티스레드)"""
    return await ensure_theme_stocks_available(is_for_trading=True)

async def ensure_backtesting_stocks_available() -> bool:
    """백테스팅용 테마 종목 데이터 확인 (100+개)"""
    return await ensure_theme_stocks_available(is_for_trading=False)

if __name__ == "__main__":
    # 테스트 실행
    async def main():
        print("=== 테마 종목 초기화 테스트 ===")
        
        print("1. 실전투자용 데이터 테스트...")
        trading_success = await ensure_trading_stocks_available()
        if trading_success:
            print("✅ 실전투자용 데이터 준비 완료 (30+개, 멀티스레드)")
        else:
            print("❌ 실전투자용 데이터 준비 실패")
        
        print("2. 백테스팅용 데이터 테스트...")
        backtesting_success = await ensure_backtesting_stocks_available()
        if backtesting_success:
            print("✅ 백테스팅용 데이터 준비 완료 (100+개)")
        else:
            print("❌ 백테스팅용 데이터 준비 실패")
        
        print("=== 테스트 완료 ===")
    
    asyncio.run(main())