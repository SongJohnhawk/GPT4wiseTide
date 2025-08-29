#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
직접 매매 시스템 테스트 - 시간 제한 없이 실행
"""

import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

async def run_auto_trading(account_type="MOCK"):
    """자동매매 시스템 실행 - 시간 제한 없이"""
    print("=" * 70)
    print(f"{account_type} 자동매매 시스템 실행 (시간 제한 없음)")
    print("=" * 70)
    
    from support.production_auto_trader import ProductionAutoTrader
    
    trader = ProductionAutoTrader(
        account_type=account_type
    )
    
    # 시간 제한 무시 설정
    if hasattr(trader, 'skip_market_hours'):
        trader.skip_market_hours = True
    
    try:
        print("자동매매 시스템 시작...")
        await trader.run_until_market_close()
        
    except KeyboardInterrupt:
        print("\n사용자가 중단했습니다.")
    except Exception as e:
        print(f"자동매매 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if hasattr(trader, 'cleanup'):
            await trader.cleanup()

async def run_day_trading(account_type="MOCK"):
    """단타매매 시스템 실행 - 시간 제한 없이"""
    print("=" * 70)
    print(f"{account_type} 단타매매 시스템 실행 (시간 제한 없음)")
    print("=" * 70)
    
    from support.minimal_day_trader import MinimalDayTrader
    
    trader = MinimalDayTrader(
        account_type=account_type,
        skip_market_hours=True  # 시간 제한 무시
    )
    
    try:
        print("단타매매 시스템 시작...")
        await trader.run()
        
    except KeyboardInterrupt:
        print("\n사용자가 중단했습니다.")
    except Exception as e:
        print(f"단타매매 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if hasattr(trader, 'cleanup'):
            await trader.cleanup()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="tideWise 직접 테스트")
    parser.add_argument("--mode", choices=["auto", "day"], default="auto", 
                       help="매매 모드 (auto: 자동매매, day: 단타매매)")
    parser.add_argument("--account", choices=["MOCK", "REAL"], default="MOCK",
                       help="계좌 타입 (MOCK: 모의투자, REAL: 실제투자)")
    
    args = parser.parse_args()
    
    if args.mode == "auto":
        asyncio.run(run_auto_trading(args.account))
    else:
        asyncio.run(run_day_trading(args.account))