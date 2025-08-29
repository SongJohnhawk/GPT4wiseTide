#!/usr/bin/env python3
"""
통합 시간 제어 시스템 - tideWise 시간 기반 자동화 컨트롤러
요구사항:
1. 시간 체크 ON/OFF 설정
2. 휴장일/장외시간 차단
3. 09:10 대기 및 시작
4. 14:00 프로그램 자동 종료
5. 단타매매 강제 종료
6. 순환 간격 동적 조정
7. 카운트다운 표시
8. 시간대별 자동 조정
"""

import json
import sys
import asyncio
import logging
import time as time_module
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import threading
import signal
import os
import locale

# 한글 출력 설정
def _fix_korean_encoding():
    """한글 출력 문제 해결"""
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

# 로거 설정
logger = logging.getLogger(__name__)

# 깔끔한 콘솔 로거 사용 시도
try:
    from support.clean_console_logger import (
        get_clean_logger, Phase, log as clean_log
    )
except ImportError:
    # 폴백: 기본 로거
    def clean_log(msg, level="INFO"):
        print(f"[{level}] {msg}")

class IntegratedTimeController:
    """통합 시간 제어 시스템"""
    
    # 시간 상수 정의
    MARKET_OPEN_WAIT = time(9, 10)      # 장시작 대기 시간
    MARKET_OPEN = time(9, 10)           # 장시작 시간
    DAYTRADING_STOP = time(14, 0)       # 단타매매 중지 시간
    PROGRAM_SHUTDOWN = time(14, 0)      # 프로그램 종료 시간
    MARKET_CLOSE = time(15, 30)         # 정규장 마감
    AUTO_STOP = time(15, 20)            # 자동 중지 시간
    LUNCH_START = time(12, 0)           # 점심 시작
    LUNCH_END = time(13, 0)             # 점심 종료
    
    def __init__(self, config_path: Optional[str] = None):
        """초기화"""
        if config_path is None:
            self.config_path = Path(__file__).parent / "integrated_time_config.json"
        else:
            self.config_path = Path(config_path)
        
        self.config = self._load_config()
        self.is_running = False
        self.shutdown_event = threading.Event()
        self._holiday_provider = None
        self._init_holiday_provider()
        
        # 순환 관리 변수
        self.cycle_interval_seconds = self.config.get("cycle_settings", {}).get("default_interval", 180)
        self.next_cycle_time = None
        self.cycle_count = 0
        self.start_time = None
        
        # 카운트다운 설정
        self.show_countdown = self.config.get("cycle_settings", {}).get("countdown_enabled", True)
        self.countdown_update_interval = self.config.get("cycle_settings", {}).get("countdown_update_interval", 10)
        self.last_countdown_display = 0
        
    def _init_holiday_provider(self):
        """휴장일 제공자 초기화"""
        try:
            from support.holiday_provider import HolidayProvider
            self._holiday_provider = HolidayProvider()
        except Exception as e:
            logger.warning(f"휴장일 제공자 초기화 실패: {e}")
            
    def _load_config(self) -> Dict[str, Any]:
        """설정 로드"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
        
        # 기본 설정
        default_config = {
            "time_check_enabled": True,
            "daytrading_stop_time": "14:00",
            "program_shutdown_time": "14:00",
            "market_open_time": "09:10",
            "auto_shutdown_enabled": True,
            "holiday_check_enabled": True,
            "description": "통합 시간 제어 설정",
            "cycle_settings": {
                "default_interval": 180,
                "min_interval": 30,
                "max_interval": 600,
                "countdown_enabled": True,
                "countdown_update_interval": 10
            },
            "auto_adjustment": {
                "enabled": True,
                "morning_boost": 0.8,
                "lunch_slowdown": 1.5,
                "closing_boost": 0.7
            }
        }
        self._save_config(default_config)
        return default_config
    
    def _save_config(self, config: Dict[str, Any]):
        """설정 저장"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"설정 파일 저장 실패: {e}")
    
    def is_time_check_enabled(self) -> bool:
        """시간 체크 활성화 여부"""
        return self.config.get("time_check_enabled", True)
    
    def is_holiday_or_weekend(self) -> bool:
        """휴장일 또는 주말 여부 확인"""
        if not self.config.get("holiday_check_enabled", True):
            return False
            
        today = datetime.now()
        
        # 주말 체크
        if today.weekday() >= 5:  # 토요일(5), 일요일(6)
            logger.info(f"주말 감지: {today.strftime('%Y-%m-%d %A')}")
            return True
        
        # 휴장일 체크
        if self._holiday_provider:
            try:
                if self._holiday_provider.is_holiday(today.date()):
                    logger.info(f"휴장일 감지: {today.strftime('%Y-%m-%d')}")
                    return True
            except Exception as e:
                logger.warning(f"휴장일 체크 실패: {e}")
                
        return False
    
    def is_before_market_open(self) -> bool:
        """장시작 전 여부 확인"""
        current_time = datetime.now().time()
        return current_time < self.MARKET_OPEN_WAIT
    
    def should_wait_for_market_open(self) -> Tuple[bool, Optional[int]]:
        """장시작 대기 필요 여부 및 대기 시간(초) 반환"""
        if not self.is_time_check_enabled():
            return False, None
            
        if self.is_holiday_or_weekend():
            return False, None
            
        current = datetime.now()
        current_time = current.time()
        
        if current_time < self.MARKET_OPEN_WAIT:
            # 대기 시간 계산
            target = current.replace(hour=9, minute=10, second=0, microsecond=0)
            wait_seconds = int((target - current).total_seconds())
            return True, wait_seconds
            
        return False, None
    
    def should_stop_daytrading(self) -> bool:
        """단타매매 중지 여부"""
        if not self.is_time_check_enabled():
            return False
            
        current_time = datetime.now().time()
        return current_time >= self.DAYTRADING_STOP
    
    def should_shutdown_program(self) -> bool:
        """프로그램 종료 여부"""
        if not self.is_time_check_enabled():
            return False
            
        if not self.config.get("auto_shutdown_enabled", True):
            return False
            
        current_time = datetime.now().time()
        return current_time >= self.PROGRAM_SHUTDOWN
    
    async def wait_for_market_open(self):
        """장시작까지 대기"""
        should_wait, wait_seconds = self.should_wait_for_market_open()
        
        if should_wait and wait_seconds:
            logger.info(f"장시작(09:10)까지 {wait_seconds}초 대기...")
            print(f"\n[WAIT] 장시작 시간(09:10)까지 대기 중...")
            print(f"   남은 시간: {wait_seconds//60}분 {wait_seconds%60}초")
            
            # 1분 단위로 상태 업데이트
            while wait_seconds > 0:
                if wait_seconds > 60:
                    await asyncio.sleep(60)
                    wait_seconds -= 60
                    print(f"   남은 시간: {wait_seconds//60}분 {wait_seconds%60}초")
                else:
                    await asyncio.sleep(wait_seconds)
                    break
            
            print("[START] 장시작! 매매를 시작합니다.")
            logger.info("장시작 - 매매 프로세스 개시")
            return True
        
        return False
    
    def schedule_auto_shutdown(self, callback=None):
        """자동 종료 스케줄링"""
        if not self.is_time_check_enabled():
            return
            
        if not self.config.get("auto_shutdown_enabled", True):
            return
        
        def shutdown_handler():
            """종료 핸들러"""
            while not self.shutdown_event.is_set():
                if self.should_shutdown_program():
                    logger.info("14:00 자동 종료 시간 도달")
                    print("\n" + "="*60)
                    print("[SHUTDOWN] 14:00 - 프로그램 자동 종료 시간")
                    print("모든 포지션을 정리하고 프로그램을 종료합니다.")
                    print("="*60)
                    
                    if callback:
                        callback()
                    
                    # 안전한 종료
                    self.safe_shutdown()
                    break
                
                # 30초마다 체크
                self.shutdown_event.wait(30)
        
        # 백그라운드 스레드로 실행
        shutdown_thread = threading.Thread(target=shutdown_handler, daemon=True)
        shutdown_thread.start()
        logger.info("자동 종료 스케줄러 시작")
    
    def safe_shutdown(self):
        """안전한 프로그램 종료"""
        logger.info("프로그램 안전 종료 프로세스 시작")
        
        try:
            # 진행 중인 작업 정리
            print("\n종료 준비 중...")
            print("- 진행 중인 매매 정리")
            print("- 데이터 저장")
            print("- 연결 종료")
            
            # 3초 대기 (정리 시간)
            import time
            time.sleep(3)
            
            print("\n[COMPLETE] 정상 종료 완료")
            logger.info("프로그램 정상 종료")
            
            # 시스템 종료
            os._exit(0)
            
        except Exception as e:
            logger.error(f"종료 중 오류: {e}")
            sys.exit(1)
    
    def get_status_message(self) -> str:
        """현재 상태 메시지"""
        if not self.is_time_check_enabled():
            return "[WARNING] 시간 체크 비활성화 - 수동 모드"
        
        current_time = datetime.now().time()
        messages = []
        
        # 휴장일 체크
        if self.is_holiday_or_weekend():
            messages.append("[CLOSED] 휴장일/주말 - 매매 불가")
            return " | ".join(messages)
        
        # 시간대별 상태
        if current_time < self.MARKET_OPEN_WAIT:
            wait_time = datetime.combine(datetime.today(), self.MARKET_OPEN_WAIT) - datetime.now()
            minutes = int(wait_time.total_seconds() // 60)
            messages.append(f"[WAITING] 장시작 대기 ({minutes}분 후 시작)")
        elif current_time < self.DAYTRADING_STOP:
            messages.append("[TRADING] 정상 매매 중")
        elif current_time < self.MARKET_CLOSE:
            messages.append("[STOPPING] 단타매매 중지 (청산만 진행)")
        else:
            messages.append("[CLOSED] 장마감")
        
        # 자동 종료 예정
        if self.config.get("auto_shutdown_enabled", True):
            if current_time < self.PROGRAM_SHUTDOWN:
                shutdown_time = datetime.combine(datetime.today(), self.PROGRAM_SHUTDOWN) - datetime.now()
                minutes = int(shutdown_time.total_seconds() // 60)
                if minutes < 30:  # 30분 이내만 표시
                    messages.append(f"[SHUTDOWN] {minutes}분 후 자동 종료")
        
        return " | ".join(messages)
    
    def validate_trading_time(self) -> Tuple[bool, str]:
        """거래 가능 시간 검증"""
        if not self.is_time_check_enabled():
            return True, "시간 체크 비활성화"
        
        # 휴장일 체크
        if self.is_holiday_or_weekend():
            return False, "휴장일 또는 주말"
        
        current_time = datetime.now().time()
        
        # 장시작 전
        if current_time < self.MARKET_OPEN:
            return False, "장시작 전 (09:10 이전)"
        
        # 단타매매 종료 후
        if current_time >= self.DAYTRADING_STOP:
            return False, "단타매매 종료 시간 (14:00 이후)"
        
        # 장마감 후
        if current_time >= self.MARKET_CLOSE:
            return False, "장마감 (15:30 이후)"
        
        return True, "정상 거래 시간"
    
    # ============ 순환 간격 관리 ============
    
    def start_cycle_timer(self) -> None:
        """순환 타이머 시작"""
        current_time = time_module.time()
        self.start_time = current_time
        
        # 시간대별 자동 조정 적용
        if self.config.get("auto_adjustment", {}).get("enabled", True):
            self._adjust_interval_by_time()
        
        self.next_cycle_time = current_time + self.cycle_interval_seconds
        self.is_running = True
        self.cycle_count = 0
        
        clean_log(f"순환 타이머 시작 (간격: {self.cycle_interval_seconds}초)", "SUCCESS")
    
    def _adjust_interval_by_time(self) -> None:
        """시간대별 순환 간격 자동 조정"""
        if not self.config.get("auto_adjustment", {}).get("enabled", True):
            return
        
        current_time = datetime.now().time()
        base_interval = self.config.get("cycle_settings", {}).get("default_interval", 180)
        auto_adj = self.config.get("auto_adjustment", {})
        
        # 아침 시간 (09:00 ~ 10:00): 간격 축소
        if time(9, 0) <= current_time < time(10, 0):
            adjusted = int(base_interval * auto_adj.get("morning_boost", 0.8))
        
        # 점심 시간 (12:00 ~ 13:00): 간격 확대
        elif self.LUNCH_START <= current_time < self.LUNCH_END:
            adjusted = int(base_interval * auto_adj.get("lunch_slowdown", 1.5))
        
        # 장 마감 전 (14:30 ~ 15:20): 간격 축소
        elif time(14, 30) <= current_time < self.AUTO_STOP:
            adjusted = int(base_interval * auto_adj.get("closing_boost", 0.7))
        
        # 기본 시간
        else:
            adjusted = base_interval
        
        # 최소/최대 범위 적용
        min_interval = self.config.get("cycle_settings", {}).get("min_interval", 30)
        max_interval = self.config.get("cycle_settings", {}).get("max_interval", 600)
        self.cycle_interval_seconds = max(min_interval, min(adjusted, max_interval))
    
    def get_countdown_remaining(self) -> int:
        """다음 순환까지 남은 시간(초) 반환"""
        if not self.next_cycle_time:
            return 0
        
        remaining = self.next_cycle_time - time_module.time()
        return max(0, int(remaining))
    
    def get_countdown_display(self) -> str:
        """카운트다운 표시 문자열 생성"""
        remaining_seconds = self.get_countdown_remaining()
        
        if remaining_seconds <= 0:
            return "다음 알고리즘 실행: \033[32m준비완료\033[0m"
        
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60
        
        # 시간대 정보 추가
        time_info = ""
        if self.LUNCH_START <= datetime.now().time() < self.LUNCH_END:
            time_info = " [점심시간]"
        elif datetime.now().time() < time(10, 0):
            time_info = " [아침장]"
        elif datetime.now().time() >= time(14, 30):
            time_info = " [마감전]"
        
        if minutes > 0:
            return f"다음 알고리즘 실행까지: \033[32m{minutes}분 {seconds:02d}초\033[0m{time_info}"
        else:
            return f"다음 알고리즘 실행까지: \033[32m{seconds}초\033[0m{time_info}"
    
    def should_display_countdown(self) -> bool:
        """카운트다운을 표시해야 하는지 확인"""
        if not self.show_countdown:
            return False
        
        current_time = time_module.time()
        if current_time - self.last_countdown_display >= self.countdown_update_interval:
            self.last_countdown_display = current_time
            return True
        return False
    
    def is_cycle_ready(self) -> bool:
        """다음 순환이 준비되었는지 확인"""
        if not self.next_cycle_time:
            return False
        return time_module.time() >= self.next_cycle_time
    
    def advance_to_next_cycle(self) -> None:
        """다음 순환으로 진행"""
        if not self.is_running:
            return
        
        self.cycle_count += 1
        current_time = time_module.time()
        
        # 시간대별 자동 조정 재적용
        if self.config.get("auto_adjustment", {}).get("enabled", True):
            self._adjust_interval_by_time()
        
        self.next_cycle_time = current_time + self.cycle_interval_seconds
    
    async def wait_for_next_cycle(self) -> bool:
        """
        다음 순환까지 대기 (카운트다운 표시 포함)
        
        Returns:
            bool: 정상 대기 완료 시 True, 중단 시 False
        """
        if not self.next_cycle_time:
            clean_log("순환 타이머가 시작되지 않음", "WARNING")
            return False
        
        try:
            while self.is_running and not self.is_cycle_ready():
                # 자동 중지 체크
                if datetime.now().time() >= self.AUTO_STOP:
                    clean_log(f"자동 중지 시간 도달 ({self.AUTO_STOP.strftime('%H:%M')})", "WARNING")
                    self.stop()
                    return False
                
                # 카운트다운 표시
                if self.should_display_countdown():
                    countdown_display = self.get_countdown_display()
                    print(countdown_display)
                
                # 1초씩 대기
                await asyncio.sleep(1)
            
            return True
            
        except asyncio.CancelledError:
            return False
        except Exception as e:
            clean_log(f"순환 대기 오류: {e}", "ERROR")
            return False
    
    def stop(self) -> None:
        """순환 관리자 중지"""
        self.is_running = False
        clean_log("통합 시간 제어 시스템 중지", "INFO")
    
    def get_cycle_stats(self) -> Dict[str, Any]:
        """순환 통계 정보 반환"""
        current_time = time_module.time()
        
        stats = {
            "cycle_interval_seconds": self.cycle_interval_seconds,
            "total_cycles": self.cycle_count,
            "is_running": self.is_running,
            "remaining_seconds": self.get_countdown_remaining(),
            "countdown_display": self.get_countdown_display(),
            "market_status": self.get_status_message()
        }
        
        if self.start_time:
            stats["running_duration_seconds"] = current_time - self.start_time
            stats["running_duration_minutes"] = (current_time - self.start_time) / 60
        
        if self.next_cycle_time:
            stats["next_cycle_time"] = datetime.fromtimestamp(self.next_cycle_time).strftime('%Y-%m-%d %H:%M:%S')
        
        # 시장 시간 정보 추가
        stats["market_times"] = {
            "open": self.MARKET_OPEN.strftime('%H:%M'),
            "close": self.MARKET_CLOSE.strftime('%H:%M'),
            "auto_stop": self.AUTO_STOP.strftime('%H:%M'),
            "lunch": f"{self.LUNCH_START.strftime('%H:%M')} ~ {self.LUNCH_END.strftime('%H:%M')}"
        }
        
        return stats
    
    def set_cycle_interval(self, seconds: int) -> None:
        """순환 간격 변경"""
        min_interval = self.config.get("cycle_settings", {}).get("min_interval", 30)
        max_interval = self.config.get("cycle_settings", {}).get("max_interval", 600)
        
        if seconds < min_interval:
            clean_log(f"순환 간격은 {min_interval}초 이상이어야 합니다", "WARNING")
            return
        
        if seconds > max_interval:
            clean_log(f"순환 간격은 {max_interval}초 이하여야 합니다", "WARNING")
            return
        
        old_interval = self.cycle_interval_seconds
        self.cycle_interval_seconds = seconds
        
        # 다음 순환 시간 재계산
        if self.next_cycle_time and self.is_running:
            current_time = time_module.time()
            remaining = self.next_cycle_time - current_time
            # 새로운 간격이 남은 시간보다 크면 재설정
            if seconds > remaining:
                self.next_cycle_time = current_time + seconds
        
        clean_log(f"순환 간격 변경: {old_interval}초 → {seconds}초", "SUCCESS")
    
    def is_lunch_time(self) -> bool:
        """점심 시간인지 확인"""
        current_time = datetime.now().time()
        return self.LUNCH_START <= current_time < self.LUNCH_END
    
    def get_market_phase(self) -> str:
        """현재 시장 단계 반환"""
        current_time = datetime.now().time()
        
        if current_time < self.MARKET_OPEN:
            return "장전"
        elif current_time < time(10, 0):
            return "아침장"
        elif self.LUNCH_START <= current_time < self.LUNCH_END:
            return "점심시간"
        elif current_time < time(14, 30):
            return "오후장"
        elif current_time < self.AUTO_STOP:
            return "마감전"
        elif current_time < self.MARKET_CLOSE:
            return "장마감임박"
        else:
            return "장마감"


# 싱글톤 인스턴스
_controller = None

def get_integrated_controller() -> IntegratedTimeController:
    """통합 컨트롤러 싱글톤 인스턴스"""
    global _controller
    if _controller is None:
        _controller = IntegratedTimeController()
    return _controller