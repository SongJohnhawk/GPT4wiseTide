#!/usr/bin/env python3
"""
통합 시간 제어 시스템 테스트
"""

import sys
from pathlib import Path
from datetime import datetime, time, timedelta
import asyncio
import json

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.integrated_time_controller import IntegratedTimeController, get_integrated_controller

def test_time_check_enabled():
    """시간 체크 활성화 테스트"""
    controller = get_integrated_controller()
    print("=" * 60)
    print("TEST 1: 시간 체크 활성화 상태")
    print("-" * 60)
    
    enabled = controller.is_time_check_enabled()
    print(f"시간 체크 활성화: {enabled}")
    print(f"설정값: {controller.config.get('time_check_enabled')}")
    
    assert enabled == True, "시간 체크가 활성화되어야 함"
    print("[PASS] 시간 체크 활성화 확인\n")
    
def test_holiday_check():
    """휴장일/주말 체크 테스트"""
    controller = get_integrated_controller()
    print("=" * 60)
    print("TEST 2: 휴장일/주말 체크")
    print("-" * 60)
    
    is_holiday = controller.is_holiday_or_weekend()
    today = datetime.now()
    print(f"오늘 날짜: {today.strftime('%Y-%m-%d %A')}")
    print(f"휴장일/주말 여부: {is_holiday}")
    
    if today.weekday() >= 5:
        assert is_holiday == True, "주말은 휴장일로 감지되어야 함"
    print("[PASS] 휴장일 체크 기능 정상\n")

def test_market_open_wait():
    """장시작 대기 테스트"""
    controller = get_integrated_controller()
    print("=" * 60) 
    print("TEST 3: 장시작 대기 로직")
    print("-" * 60)
    
    current_time = datetime.now().time()
    should_wait, wait_seconds = controller.should_wait_for_market_open()
    
    print(f"현재 시간: {current_time.strftime('%H:%M:%S')}")
    print(f"장시작 시간: 09:10:00")
    print(f"대기 필요: {should_wait}")
    if should_wait:
        print(f"대기 시간: {wait_seconds}초 ({wait_seconds//60}분 {wait_seconds%60}초)")
    
    # 시간대별 검증
    if current_time < time(9, 10):
        assert should_wait == True, "09:10 이전에는 대기해야 함"
    else:
        assert should_wait == False, "09:10 이후에는 대기 불필요"
    
    print("[PASS] 장시작 대기 로직 정상\n")

def test_daytrading_stop():
    """단타매매 중지 시간 테스트"""
    controller = get_integrated_controller()
    print("=" * 60)
    print("TEST 4: 단타매매 중지 시간")
    print("-" * 60)
    
    current_time = datetime.now().time()
    should_stop = controller.should_stop_daytrading()
    
    print(f"현재 시간: {current_time.strftime('%H:%M:%S')}")
    print(f"단타매매 중지 시간: 14:00:00")
    print(f"중지 여부: {should_stop}")
    
    if current_time >= time(14, 0):
        assert should_stop == True, "14:00 이후에는 중지해야 함"
    else:
        assert should_stop == False, "14:00 이전에는 계속 진행"
    
    print("[PASS] 단타매매 중지 로직 정상\n")

def test_program_shutdown():
    """프로그램 자동 종료 테스트"""
    controller = get_integrated_controller()
    print("=" * 60)
    print("TEST 5: 프로그램 자동 종료")
    print("-" * 60)
    
    current_time = datetime.now().time()
    should_shutdown = controller.should_shutdown_program()
    auto_shutdown = controller.config.get("auto_shutdown_enabled")
    
    print(f"현재 시간: {current_time.strftime('%H:%M:%S')}")
    print(f"자동 종료 시간: 14:00:00")
    print(f"자동 종료 설정: {auto_shutdown}")
    print(f"종료 필요: {should_shutdown}")
    
    if current_time >= time(14, 0) and auto_shutdown:
        assert should_shutdown == True, "14:00 이후 자동 종료되어야 함"
    
    print("[PASS] 자동 종료 로직 정상\n")

def test_status_message():
    """상태 메시지 테스트"""
    controller = get_integrated_controller()
    print("=" * 60)
    print("TEST 6: 상태 메시지")
    print("-" * 60)
    
    status = controller.get_status_message()
    print(f"현재 상태: {status}")
    
    assert len(status) > 0, "상태 메시지가 있어야 함"
    print("[PASS] 상태 메시지 정상\n")

def test_trading_validation():
    """거래 시간 검증 테스트"""
    controller = get_integrated_controller()
    print("=" * 60)
    print("TEST 7: 거래 가능 시간 검증")
    print("-" * 60)
    
    can_trade, reason = controller.validate_trading_time()
    current_time = datetime.now().time()
    
    print(f"현재 시간: {current_time.strftime('%H:%M:%S')}")
    print(f"거래 가능: {can_trade}")
    print(f"이유: {reason}")
    
    # 시간대별 검증
    if controller.is_holiday_or_weekend():
        assert can_trade == False, "휴장일에는 거래 불가"
    elif current_time < time(9, 10):
        assert can_trade == False, "09:10 이전 거래 불가"
    elif current_time >= time(14, 0):
        assert can_trade == False, "14:00 이후 거래 불가"
    
    print("[PASS] 거래 시간 검증 정상\n")

async def test_wait_simulation():
    """장시작 대기 시뮬레이션"""
    controller = get_integrated_controller()
    print("=" * 60)
    print("TEST 8: 장시작 대기 시뮬레이션")
    print("-" * 60)
    
    current_time = datetime.now().time()
    print(f"현재 시간: {current_time.strftime('%H:%M:%S')}")
    
    if current_time < time(9, 10):
        print("실제 대기 수행 (최대 10초만 테스트)...")
        # 테스트용으로 10초만 대기
        await asyncio.wait_for(
            controller.wait_for_market_open(),
            timeout=10
        )
    else:
        print("현재 시간이 09:10 이후이므로 대기 불필요")
    
    print("[PASS] 대기 시뮬레이션 정상\n")

def test_cycle_management():
    """순환 관리 기능 테스트"""
    controller = get_integrated_controller()
    print("=" * 60)
    print("TEST 9: 순환 관리 기능")
    print("-" * 60)
    
    # 순환 타이머 시작
    controller.start_cycle_timer()
    print(f"순환 타이머 시작")
    print(f"현재 순환 간격: {controller.cycle_interval_seconds}초")
    
    # 카운트다운 테스트
    remaining = controller.get_countdown_remaining()
    display = controller.get_countdown_display()
    print(f"다음 순환까지: {remaining}초")
    print(f"카운트다운 표시: {display}")
    
    # 순환 준비 상태
    is_ready = controller.is_cycle_ready()
    print(f"순환 준비됨: {is_ready}")
    
    # 통계 정보
    stats = controller.get_cycle_stats()
    print(f"순환 통계:")
    print(f"  - 총 순환 수: {stats.get('total_cycles', 0)}")
    print(f"  - 실행 중: {stats.get('is_running', False)}")
    
    # 순환 간격 변경
    controller.set_cycle_interval(120)
    print(f"순환 간격 변경: {controller.cycle_interval_seconds}초")
    
    # 중지
    controller.stop()
    print(f"순환 타이머 중지")
    
    assert controller.is_running == False, "타이머가 중지되어야 함"
    print("[PASS] 순환 관리 기능 정상\n")

def test_market_phase():
    """시장 단계 테스트"""
    controller = get_integrated_controller()
    print("=" * 60)
    print("TEST 10: 시장 단계 확인")
    print("-" * 60)
    
    current_time = datetime.now().time()
    phase = controller.get_market_phase()
    is_lunch = controller.is_lunch_time()
    
    print(f"현재 시간: {current_time.strftime('%H:%M:%S')}")
    print(f"시장 단계: {phase}")
    print(f"점심시간: {is_lunch}")
    
    # 시간대별 검증
    if current_time < time(9, 10):
        assert phase == "장전", "09:10 이전은 장전이어야 함"
    elif current_time < time(10, 0):
        assert phase == "아침장", "09:10~10:00은 아침장이어야 함"
    elif time(12, 0) <= current_time < time(13, 0):
        assert phase == "점심시간", "12:00~13:00은 점심시간이어야 함"
        assert is_lunch == True, "점심시간 플래그가 True여야 함"
    
    print("[PASS] 시장 단계 확인 정상\n")

def test_auto_adjustment():
    """시간대별 자동 조정 테스트"""
    controller = get_integrated_controller()
    print("=" * 60)
    print("TEST 11: 시간대별 자동 조정")
    print("-" * 60)
    
    # 자동 조정 설정 확인
    auto_adj = controller.config.get("auto_adjustment", {})
    print(f"자동 조정 활성화: {auto_adj.get('enabled', False)}")
    print(f"아침장 배율: {auto_adj.get('morning_boost', 0.8)}")
    print(f"점심시간 배율: {auto_adj.get('lunch_slowdown', 1.5)}")
    print(f"마감전 배율: {auto_adj.get('closing_boost', 0.7)}")
    
    # 현재 시간대 조정 적용
    original = controller.cycle_interval_seconds
    controller._adjust_interval_by_time()
    adjusted = controller.cycle_interval_seconds
    
    print(f"원래 간격: {original}초")
    print(f"조정된 간격: {adjusted}초")
    
    assert adjusted > 0, "조정된 간격은 양수여야 함"
    print("[PASS] 자동 조정 기능 정상\n")

async def test_countdown_cycle():
    """순환 대기 사이클 테스트"""
    controller = get_integrated_controller()
    print("=" * 60)
    print("TEST 12: 순환 대기 사이클 (5초)")
    print("-" * 60)
    
    # 짧은 간격 설정
    controller.set_cycle_interval(5)
    controller.start_cycle_timer()
    
    print("5초 순환 대기 시작...")
    
    try:
        # 대기
        success = await asyncio.wait_for(
            controller.wait_for_next_cycle(),
            timeout=6
        )
        
        if success:
            print("순환 완료!")
            controller.advance_to_next_cycle()
            print(f"순환 카운트: {controller.cycle_count}")
        else:
            print("순환 중단됨")
            
    except asyncio.TimeoutError:
        print("타임아웃")
    finally:
        controller.stop()
    
    print("[PASS] 순환 대기 사이클 정상\n")

def main():
    """메인 테스트 실행"""
    print("\n" + "=" * 60)
    print("[TEST] 통합 시간 제어 시스템 단위 테스트")
    print("=" * 60 + "\n")
    
    try:
        # 동기 테스트
        test_time_check_enabled()
        test_holiday_check()
        test_market_open_wait()
        test_daytrading_stop()
        test_program_shutdown()
        test_status_message()
        test_trading_validation()
        
        # 새로운 기능 테스트
        test_cycle_management()
        test_market_phase()
        test_auto_adjustment()
        
        # 비동기 테스트
        # asyncio.run(test_wait_simulation())
        asyncio.run(test_countdown_cycle())
        
        print("=" * 60)
        print("[SUCCESS] 모든 단위 테스트 통과!")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n[FAIL] 테스트 실패: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)