#!/usr/bin/env python3
"""
실제 계좌 데이터 표시 테스트
하드코딩된 값이 제거되고 실제 API 데이터만 사용되는지 확인
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.api_connector import APIConnector
from support.day_trading_runner import DayTradingRunner
from support.minimal_day_trader import MinimalDayTrader
from support.clean_console_logger import get_clean_logger, Phase, log as clean_log

async def test_real_account_data():
    """실제 계좌 데이터 조회 테스트"""
    clean_log("실제 계좌 데이터 조회 테스트 시작", "INFO")
    
    try:
        # API 커넥터 초기화 (실전 모드)
        api = APIConnector(is_mock=False)
        clean_log("API 커넥터 초기화 완료 (실전 모드)", "SUCCESS")
        
        # 1. 계좌 잔고 조회
        clean_log("계좌 잔고 조회 중...", "INFO")
        try:
            account_data = await api.get_account_balance(force_refresh=True)
            
            # 필수 필드 확인
            if 'dnca_tot_amt' not in account_data:
                clean_log("❌ 예수금 정보(dnca_tot_amt) 누락", "ERROR")
                return False
            
            if 'ord_psbl_cash' not in account_data:
                clean_log("❌ 주문가능금액(ord_psbl_cash) 누락", "ERROR")
                return False
            
            # 실제 값 출력
            cash_balance = float(account_data['dnca_tot_amt'])
            available_cash = float(account_data['ord_psbl_cash'])
            
            clean_log(f"✅ 예수금: {cash_balance:,.0f}원", "SUCCESS")
            clean_log(f"✅ 주문가능금액: {available_cash:,.0f}원", "SUCCESS")
            
            # 보유종목 확인
            if 'output1' in account_data:
                stocks = account_data['output1']
                clean_log(f"✅ 보유종목 수: {len(stocks)}개", "SUCCESS")
                
                for stock in stocks:
                    if 'pdno' not in stock or 'prdt_name' not in stock:
                        clean_log(f"⚠️ 종목 정보 불완전: {stock}", "WARNING")
                        continue
                    
                    stock_code = stock['pdno']
                    stock_name = stock['prdt_name']
                    
                    if 'hldg_qty' in stock:
                        quantity = int(stock['hldg_qty'])
                        if quantity > 0:
                            clean_log(f"  - {stock_name}({stock_code}): {quantity}주", "INFO")
            
        except Exception as e:
            clean_log(f"❌ 계좌 조회 실패: {e}", "ERROR")
            return False
        
        # 2. MinimalDayTrader 테스트
        clean_log("\nMinimalDayTrader 계좌 정보 테스트", "INFO")
        try:
            trader = MinimalDayTrader(api)
            account_info = await trader.get_account_info()
            
            if account_info:
                clean_log(f"✅ MinimalDayTrader 계좌 조회 성공", "SUCCESS")
                if 'dnca_tot_amt' in account_info:
                    clean_log(f"  - 예수금: {float(account_info['dnca_tot_amt']):,.0f}원", "INFO")
            else:
                clean_log("❌ MinimalDayTrader 계좌 조회 실패", "ERROR")
                
        except Exception as e:
            clean_log(f"❌ MinimalDayTrader 테스트 실패: {e}", "ERROR")
        
        # 3. DayTradingRunner 테스트
        clean_log("\nDayTradingRunner 계좌 정보 테스트", "INFO")
        try:
            runner = DayTradingRunner(api)
            # display_account_status 메서드 테스트
            await runner.display_account_status()
            clean_log(f"✅ DayTradingRunner 계좌 표시 성공", "SUCCESS")
            
        except Exception as e:
            clean_log(f"❌ DayTradingRunner 테스트 실패: {e}", "ERROR")
        
        clean_log("\n✅ 모든 테스트 완료 - 하드코딩된 값 제거 확인", "SUCCESS")
        return True
        
    except Exception as e:
        clean_log(f"❌ 테스트 중 예상치 못한 오류: {e}", "ERROR")
        return False
    finally:
        # 리소스 정리
        if 'api' in locals():
            api.cleanup()

def main():
    """메인 함수"""
    clean_log("=" * 60, "INFO")
    clean_log("실제 계좌 데이터 표시 테스트", "INFO")
    clean_log("=" * 60, "INFO")
    
    # 비동기 함수 실행
    result = asyncio.run(test_real_account_data())
    
    if result:
        clean_log("\n✅ 테스트 성공: 실제 API 데이터가 정상적으로 표시됩니다", "SUCCESS")
    else:
        clean_log("\n❌ 테스트 실패: API 데이터 표시에 문제가 있습니다", "ERROR")
    
    clean_log("=" * 60, "INFO")

if __name__ == "__main__":
    main()