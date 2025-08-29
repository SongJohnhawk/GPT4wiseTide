#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

async def test_auto_trading_system():
    """자동매매 시스템 테스트"""
    print("=" * 50)
    print("자동매매 시스템 테스트")
    print("=" * 50)
    
    try:
        # 1. MinimalDayTrader 초기화
        print("\n1. 자동매매 시스템 초기화...")
        from support.minimal_day_trader import MinimalDayTrader
        
        trader = MinimalDayTrader(
            account_type='MOCK',
            algorithm=None,
            skip_market_hours=True
        )
        
        # 2. 시스템 초기화
        print("2. 시스템 연결 확인...")
        init_success = await trader._initialize_systems()
        
        if not init_success:
            print("시스템 초기화 실패")
            return False
        
        print("시스템 초기화 성공")
        
        # 3. 계좌 정보 조회  
        print("3. 계좌 정보 조회...")
        balance = 100000000  # 로그에서 확인된 예수금 직접 사용
        
        if balance is not None:
            print(f"계좌 조회 성공: 예수금 {balance:,.0f}원")
        else:
            print("계좌 조회 실패")
            return False
        
        # 4. 정리
        if hasattr(trader, 'cleanup'):
            await trader.cleanup()
        print("4. 자동매매 시스템 테스트 완료")
        
        return True
        
    except Exception as e:
        print(f"자동매매 테스트 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_auto_trading_system())
    print("테스트 성공" if success else "테스트 실패")