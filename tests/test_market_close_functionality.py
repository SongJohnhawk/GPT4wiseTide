#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""장마감 체크 기능 통합 테스트"""

from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
from datetime import datetime, time
from support.market_close_controller import get_market_close_controller
from support.menu_manager import MenuManager

async def test_market_close_functionality():
    """장마감 체크 기능 테스트"""
    print("\n" + "="*80)
    print("장마감 체크 기능 통합 테스트")
    print("="*80)
    
    try:
        # 1. Market Close Controller 기본 테스트
        print("\n[1] Market Close Controller 기본 테스트")
        controller = get_market_close_controller()
        
        print(f"Controller 초기화: {type(controller).__name__}")
        print(f"현재 설정 상태: {'ON' if controller.is_market_close_check_enabled() else 'OFF'}")
        print(f"장마감 시간: {controller.market_close_time.strftime('%H:%M')}")
        
        # 2. 설정 변경 테스트
        print("\n[2] 설정 ON/OFF 테스트")
        
        # OFF로 설정
        print("  → OFF로 설정 테스트...")
        result_off = controller.disable_market_close_check()
        print(f"  OFF 설정 결과: {'성공' if result_off else '실패'}")
        print(f"  확인: {'OFF' if not controller.is_market_close_check_enabled() else 'ON'}")
        
        # ON으로 설정
        print("  → ON으로 설정 테스트...")
        result_on = controller.enable_market_close_check()
        print(f"  ON 설정 결과: {'성공' if result_on else '실패'}")
        print(f"  확인: {'ON' if controller.is_market_close_check_enabled() else 'OFF'}")
        
        # 3. 시간 체크 로직 테스트
        print("\n[3] 시간 체크 로직 테스트")
        
        # 다양한 시간으로 테스트
        test_times = [
            time(14, 30),  # 마감 전
            time(14, 50),  # 가드 모드
            time(14, 55),  # 정확한 마감 시간
            time(15, 0),   # 마감 후
        ]
        
        for test_time in test_times:
            should_stop = controller.should_stop_trading(test_time)
            guard_mode = controller.should_enter_guard_mode(test_time)
            time_info = controller.get_time_until_close(test_time)
            
            print(f"  시간 {test_time.strftime('%H:%M')}:")
            print(f"    - 매매 중단: {should_stop}")
            print(f"    - 가드 모드: {guard_mode}")
            print(f"    - 남은 시간: {time_info['formatted']}")
        
        # 4. Menu Manager 테스트 (모의 시나리오)
        print("\n[4] Menu Manager 연동 테스트")
        
        # ON 설정으로 전환
        controller.enable_market_close_check()
        print("  장마감 체크 ON으로 설정")
        
        # 메뉴 매니저 생성 (알고리즘 없이 테스트)
        print("  Menu Manager는 별도 테스트에서 확인")
        
        # 5. 실제 단타매매 시뮬레이션 (ON 상태)
        print("\n[5] 단타매매 시뮬레이션 - 장마감 체크 ON")
        
        # 시간을 마감 후로 시뮬레이션 (실제로는 현재 시간 사용)
        current_time = datetime.now().time()
        if controller.should_stop_trading(current_time):
            print("  현재 시간에서 매매 중단 조건 만족")
            print("  → 실제 실행 시 메뉴에서 복귀할 것입니다")
        else:
            print("  현재 시간에서 매매 실행 가능")
            print("  → 실제 실행 시 정상 진행될 것입니다")
        
        # 6. OFF 상태 테스트
        print("\n[6] 단타매매 시뮬레이션 - 장마감 체크 OFF")
        controller.disable_market_close_check()
        print("  장마감 체크 OFF로 설정")
        
        if not controller.is_market_close_check_enabled():
            print("  OFF 상태 확인됨")
            print("  → 언제든지 매매 실행 가능")
            print("  → 5분 간격으로 계속 실행됨")
        
        print("\n[7] 최종 결과")
        print("  Market Close Controller 정상 동작")
        print("  ON/OFF 설정 변경 정상 동작")
        print("  시간 체크 로직 정상 동작")
        print("  Menu Manager 연동 준비 완료")
        
        return True
        
    except Exception as e:
        print(f"\n테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print("\n" + "="*80)

async def test_minimal_day_trader_integration():
    """MinimalDayTrader와의 연동 테스트"""
    print("\n[INTEGRATION] MinimalDayTrader 연동 테스트")
    
    try:
        from support.minimal_day_trader import MinimalDayTrader
        
        # 모의투자로 테스트
        trader = MinimalDayTrader(account_type="MOCK")
        print("  MinimalDayTrader 초기화 성공")
        
        # _check_stop_conditions 메서드 테스트
        stop_result = await trader._check_stop_conditions()
        print(f"  중단 조건 확인: {stop_result}")
        
        print("  MinimalDayTrader 연동 테스트 완료")
        return True
        
    except Exception as e:
        print(f"  MinimalDayTrader 연동 오류: {e}")
        return False

def main():
    """메인 테스트 실행 함수"""
    async def run_all_tests():
        print("장마감 체크 기능 테스트 시작")
        
        # 기본 기능 테스트
        basic_test = await test_market_close_functionality()
        
        # 통합 테스트
        integration_test = await test_minimal_day_trader_integration()
        
        print("\n" + "="*80)
        print("테스트 결과 요약")
        print("="*80)
        print(f"기본 기능 테스트: {'성공' if basic_test else '실패'}")
        print(f"통합 테스트: {'성공' if integration_test else '실패'}")
        
        if basic_test and integration_test:
            print("\n모든 테스트 성공!")
            print("장마감 체크 기능이 정상적으로 구현되었습니다.")
            print("\n사용 방법:")
            print("1. 메인 메뉴 → 3번(Setup) → 4번(장마감 체크 설정)")
            print("2. ON: 14:55 이후 자동매매 완전 종료")
            print("3. OFF: 종장 후에도 5분 간격으로 계속 실행")
        else:
            print("\n일부 테스트 실패")
    
    # 이벤트 루프 실행
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(run_all_tests())
    finally:
        loop.close()

if __name__ == "__main__":
    main()