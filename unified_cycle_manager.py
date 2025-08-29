#!/usr/bin/env python3
"""
통합 순환 관리 시스템
tideWise 성능 최적화: 순환 간격 통일 및 카운트다운 시스템
"""

import time
import asyncio
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
# 한글 출력 문제 해결을 위한 강화된 UTF-8 설정
import os
import locale

def _fix_korean_encoding():
    """한글 출력 문제 완전 해결"""
    try:
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PYTHONUTF8'] = '1'
        os.environ['PYTHONLEGACYWINDOWSSTDIO'] = '0'
        
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        
        try:
            locale.setlocale(locale.LC_ALL, 'ko_KR.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_ALL, 'Korean_Korea.UTF-8')
            except:
                pass
    except Exception:
        pass

_fix_korean_encoding()

# 깔끔한 콘솔 로거 사용
from support.clean_console_logger import (
    get_clean_logger, Phase, log as clean_log
)


class UnifiedCycleManager:
    """통합된 순환 간격 관리 및 카운트다운 시스템"""
    
    def __init__(self, cycle_interval_seconds: int = 120):
        """
        초기화
        
        Args:
            cycle_interval_seconds: 순환 간격 (기본 120초 = 2분)
        """
        self.cycle_interval_seconds = cycle_interval_seconds
        self.next_cycle_time: Optional[float] = None
        self.cycle_count = 0
        self.is_running = False
        self.start_time: Optional[float] = None
        
        # 카운트다운 표시 설정
        self.show_countdown = True
        self.countdown_update_interval = 10  # 10초마다 카운트다운 업데이트
        self.last_countdown_display = 0
        
    def start_cycle_timer(self) -> None:
        """순환 타이머 시작"""
        current_time = time.time()
        self.start_time = current_time
        self.next_cycle_time = current_time + self.cycle_interval_seconds
        self.is_running = True
        self.cycle_count = 0
        
        clean_log("통합 순환 관리자 준비 완료", "SUCCESS")
    
    def get_countdown_remaining(self) -> int:
        """다음 순환까지 남은 시간(초) 반환"""
        if not self.next_cycle_time:
            return 0
            
        remaining = self.next_cycle_time - time.time()
        return max(0, int(remaining))
    
    def get_countdown_display(self) -> str:
        """카운트다운 표시 문자열 생성"""
        remaining_seconds = self.get_countdown_remaining()
        
        if remaining_seconds <= 0:
            return "다음 알고리즘 실행까지: \033[32m0분 00초\033[0m"
        
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60
        
        if minutes > 0:
            return f"다음 알고리즘 실행까지: \033[32m{minutes}분 {seconds:02d}초\033[0m"
        else:
            return f"다음 알고리즘 실행까지: \033[32m0분 {seconds:02d}초\033[0m"
    
    def should_display_countdown(self) -> bool:
        """카운트다운을 표시해야 하는지 확인"""
        if not self.show_countdown:
            return False
            
        current_time = time.time()
        if current_time - self.last_countdown_display >= self.countdown_update_interval:
            self.last_countdown_display = current_time
            return True
        return False
    
    def is_cycle_ready(self) -> bool:
        """다음 순환이 준비되었는지 확인"""
        if not self.next_cycle_time:
            return False
        return time.time() >= self.next_cycle_time
    
    def advance_to_next_cycle(self) -> None:
        """다음 순환으로 진행"""
        if not self.is_running:
            return
            
        self.cycle_count += 1
        current_time = time.time()
        self.next_cycle_time = current_time + self.cycle_interval_seconds
        
        # 순환 시작 (로그 제거 - 대량 중복 메시지 방지)
    
    async def wait_for_next_cycle(self) -> bool:
        """
        다음 순환까지 대기 (카운트다운 표시 포함)
        
        Returns:
            bool: 정상 대기 완료 시 True, 중단 시 False
        """
        if not self.next_cycle_time:
            clean_log("순환 타이머 시작 실패", "WARNING")
            return False
        
        try:
            while self.is_running and not self.is_cycle_ready():
                # 카운트다운 표시
                if self.should_display_countdown():
                    countdown_display = self.get_countdown_display()
                    print(countdown_display)
                    # 카운트다운 디스플레이 (로그 제거 - 과도한 메시지)
                
                # 1초씩 대기하면서 확인
                await asyncio.sleep(1)
            
            return True
            
        except asyncio.CancelledError:
            # 순환 대기 취소 (로그 제거)
            return False
        except Exception as e:
            clean_log(f"순환 대기 오류: {e}", "ERROR")
            return False
    
    def stop(self) -> None:
        """순환 관리자 중지"""
        self.is_running = False
        # 순환 관리자 중지 (로그 제거)
    
    def get_cycle_stats(self) -> Dict[str, Any]:
        """순환 통계 정보 반환"""
        current_time = time.time()
        
        stats = {
            "cycle_interval_seconds": self.cycle_interval_seconds,
            "total_cycles": self.cycle_count,
            "is_running": self.is_running,
            "remaining_seconds": self.get_countdown_remaining(),
            "countdown_display": self.get_countdown_display()
        }
        
        if self.start_time:
            stats["running_duration_seconds"] = current_time - self.start_time
            stats["running_duration_minutes"] = (current_time - self.start_time) / 60
        
        if self.next_cycle_time:
            stats["next_cycle_time"] = datetime.fromtimestamp(self.next_cycle_time).strftime('%Y-%m-%d %H:%M:%S')
        
        return stats
    
    def set_cycle_interval(self, seconds: int) -> None:
        """순환 간격 변경"""
        if seconds < 30:
            clean_log("순환 간격은 30초 이상 필요", "WARNING")
            return
            
        old_interval = self.cycle_interval_seconds
        self.cycle_interval_seconds = seconds
        
        # 다음 순환 시간 재계산
        if self.next_cycle_time and self.is_running:
            current_time = time.time()
            remaining = self.next_cycle_time - current_time
            # 새로운 간격이 남은 시간보다 크면 재설정
            if seconds > remaining:
                self.next_cycle_time = current_time + seconds
        
        # 순환 간격 변경 (로그 제거 - 설정 변경시에만)


class StepDelayManager:
    """단계별 지연 처리 관리"""
    
    def __init__(self, step_delay_seconds: int = 2):
        """
        초기화
        
        Args:
            step_delay_seconds: 단계별 지연 시간 (기본 2초)
        """
        self.step_delay_seconds = step_delay_seconds
        self.current_step = ""
        self.step_count = 0
        
    async def delay_between_steps(self, current_step: str = "") -> None:
        """단계 간 지연 처리"""
        self.step_count += 1
        self.current_step = current_step
        
        if current_step:
            # 단계 완료 대기 (로그 제거 - 과도한 상태 보고)
            print(f"단계 완료: {current_step} → {self.step_delay_seconds}초 대기...")
        
        await asyncio.sleep(self.step_delay_seconds)
    
    def set_step_delay(self, seconds: int) -> None:
        """단계별 지연 시간 변경"""
        old_delay = self.step_delay_seconds
        self.step_delay_seconds = max(0, seconds)  # 음수 방지
        # 단계별 지연 시간 변경 (로그 제거)


# 전역 인스턴스 (싱글톤 패턴)
_unified_cycle_manager: Optional[UnifiedCycleManager] = None
_step_delay_manager: Optional[StepDelayManager] = None


def get_unified_cycle_manager(cycle_interval_seconds: int = 120) -> UnifiedCycleManager:
    """통합 순환 관리자 인스턴스 반환 (싱글톤)"""
    global _unified_cycle_manager
    if _unified_cycle_manager is None:
        _unified_cycle_manager = UnifiedCycleManager(cycle_interval_seconds)
    return _unified_cycle_manager


def get_step_delay_manager(step_delay_seconds: int = 2) -> StepDelayManager:
    """단계별 지연 관리자 인스턴스 반환 (싱글톤)"""
    global _step_delay_manager
    if _step_delay_manager is None:
        _step_delay_manager = StepDelayManager(step_delay_seconds)
    return _step_delay_manager


# 편의 함수들
async def wait_for_next_cycle() -> bool:
    """다음 순환까지 대기 (전역 관리자 사용)"""
    manager = get_unified_cycle_manager()
    return await manager.wait_for_next_cycle()


async def delay_between_steps(step_name: str = "") -> None:
    """단계 간 지연 처리 (전역 관리자 사용)"""
    delay_manager = get_step_delay_manager()
    await delay_manager.delay_between_steps(step_name)


def start_unified_cycles(cycle_interval: int = 120) -> None:
    """통합 순환 시스템 시작"""
    manager = get_unified_cycle_manager(cycle_interval)
    manager.start_cycle_timer()


def get_countdown_display() -> str:
    """현재 카운트다운 표시 반환"""
    manager = get_unified_cycle_manager()
    return manager.get_countdown_display()


if __name__ == "__main__":
    # 테스트 코드
    async def test_cycle_manager():
        print("=== 통합 순환 관리자 테스트 ===")
        
        # 테스트용 짧은 간격 (10초)
        manager = UnifiedCycleManager(10)
        delay_manager = StepDelayManager(1)  # 1초 지연
        
        manager.start_cycle_timer()
        
        for cycle in range(3):
            print(f"\n--- 사이클 {cycle + 1} 시작 ---")
            manager.advance_to_next_cycle()
            
            # 단계 시뮬레이션
            for step in range(3):
                step_name = f"테스트 단계 {step + 1}"
                print(f"실행 중: {step_name}")
                await delay_manager.delay_between_steps(step_name)
            
            # 다음 사이클까지 대기
            print("다음 사이클까지 대기 중...")
            await manager.wait_for_next_cycle()
        
        manager.stop()
        print("테스트 완료")
    
    # 테스트 실행
    asyncio.run(test_cycle_manager())