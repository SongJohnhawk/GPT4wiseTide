#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trading Time Manager
거래 시간 및 사이클 관리자 - 대기 기능 포함

핵심 기능:
- 거래 시작 전 대기 기능 (9:10 AM까지 대기)
- 시간대별 사이클 간격 관리 (오전 8분, 오후 15분)
- 거래 시간 모니터링 및 자동 종료 (2:00 PM)
- 장 개장/마감 시간 체크
- 휴장일 및 특별 시간 처리
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, Any, Optional, Callable
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class TradingPhase(Enum):
    """거래 단계"""
    BEFORE_MARKET = "before_market"      # 장 시작 전
    WAITING = "waiting"                  # 거래 시작 대기 중
    MORNING_TRADING = "morning_trading"  # 오전 거래 (9:10-12:00)
    LUNCH_BREAK = "lunch_break"         # 점심 시간 (12:00-12:01)
    AFTERNOON_TRADING = "afternoon_trading" # 오후 거래 (12:01-14:00)
    MARKET_CLOSED = "market_closed"      # 장 마감 후

class TradingTimeManager:
    """거래 시간 관리자"""
    
    def __init__(self, config_file: str = "trading_time_config.json"):
        """
        초기화
        
        Args:
            config_file: 시간 설정 파일 경로
        """
        # 기본 시간 설정 (사용자 요구사항)
        self.MARKET_OPEN = time(9, 5)      # 장 개장: 9:05
        self.TRADING_START = time(9, 10)   # 거래 시작: 9:10 (5분 대기)
        self.MORNING_END = time(12, 0)     # 오전 거래 종료: 12:00
        self.AFTERNOON_START = time(12, 1) # 오후 거래 시작: 12:01
        self.TRADING_END = time(14, 0)     # 거래 종료: 14:00 (2:00 PM)
        self.MARKET_CLOSE = time(15, 30)   # 장 마감: 15:30
        
        # 사이클 간격 (초)
        self.MORNING_INTERVAL = 480        # 8분 (480초)
        self.AFTERNOON_INTERVAL = 900      # 15분 (900초)
        
        # 설정 파일 로드
        self.config_file = Path(__file__).parent / config_file
        self._load_config()
        
        # 상태 관리
        self.current_phase = TradingPhase.BEFORE_MARKET
        self.is_trading_active = False
        self.last_cycle_time = None
        self.cycle_count = 0
        
        # 콜백 함수들
        self.on_trading_start: Optional[Callable] = None
        self.on_trading_end: Optional[Callable] = None
        self.on_phase_change: Optional[Callable] = None
        
        # 대기 모드 설정
        self.wait_mode_active = False
        self.wait_start_time = None
        
        logger.info("Trading Time Manager 초기화 완료")
        logger.info(f"거래시간: {self.TRADING_START} ~ {self.TRADING_END}")
        logger.info(f"사이클간격: 오전 {self.MORNING_INTERVAL//60}분, 오후 {self.AFTERNOON_INTERVAL//60}분")
    
    def _load_config(self):
        """시간 설정 로드"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 시간 설정 업데이트
                if 'trading_start' in config:
                    hour, minute = map(int, config['trading_start'].split(':'))
                    self.TRADING_START = time(hour, minute)
                
                if 'trading_end' in config:
                    hour, minute = map(int, config['trading_end'].split(':'))
                    self.TRADING_END = time(hour, minute)
                
                if 'morning_interval' in config:
                    self.MORNING_INTERVAL = config['morning_interval']
                
                if 'afternoon_interval' in config:
                    self.AFTERNOON_INTERVAL = config['afternoon_interval']
                
                logger.info(f"시간 설정 로드 완료: {self.config_file}")
            else:
                # 기본 설정 파일 생성
                self._save_config()
                
        except Exception as e:
            logger.error(f"시간 설정 로드 실패: {e}")
    
    def _save_config(self):
        """현재 설정을 파일로 저장"""
        try:
            config = {
                'trading_start': self.TRADING_START.strftime('%H:%M'),
                'trading_end': self.TRADING_END.strftime('%H:%M'),
                'morning_interval': self.MORNING_INTERVAL,
                'afternoon_interval': self.AFTERNOON_INTERVAL,
                'market_open': self.MARKET_OPEN.strftime('%H:%M'),
                'market_close': self.MARKET_CLOSE.strftime('%H:%M')
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"시간 설정 저장 완료: {self.config_file}")
            
        except Exception as e:
            logger.error(f"시간 설정 저장 실패: {e}")
    
    def get_current_phase(self) -> TradingPhase:
        """현재 거래 단계 반환"""
        now = datetime.now().time()
        current_date = datetime.now().date()
        
        # 평일 체크 (0=월요일, 6=일요일)
        if current_date.weekday() >= 5:  # 토요일, 일요일
            return TradingPhase.MARKET_CLOSED
        
        # 시간대별 단계 판정
        if now < self.MARKET_OPEN:
            return TradingPhase.BEFORE_MARKET
        elif now < self.TRADING_START:
            return TradingPhase.WAITING
        elif now < self.MORNING_END:
            return TradingPhase.MORNING_TRADING
        elif now < self.AFTERNOON_START:
            return TradingPhase.LUNCH_BREAK
        elif now < self.TRADING_END:
            return TradingPhase.AFTERNOON_TRADING
        else:
            return TradingPhase.MARKET_CLOSED
    
    def get_cycle_interval(self) -> int:
        """현재 시간대의 사이클 간격 반환 (초)"""
        phase = self.get_current_phase()
        
        if phase == TradingPhase.MORNING_TRADING:
            return self.MORNING_INTERVAL
        elif phase == TradingPhase.AFTERNOON_TRADING:
            return self.AFTERNOON_INTERVAL
        else:
            return 300  # 기본값 5분
    
    def is_trading_time(self) -> bool:
        """현재 거래 시간인지 확인"""
        phase = self.get_current_phase()
        return phase in [TradingPhase.MORNING_TRADING, TradingPhase.AFTERNOON_TRADING]
    
    def get_time_until_trading_start(self) -> Optional[timedelta]:
        """거래 시작까지 남은 시간"""
        now = datetime.now()
        today_trading_start = datetime.combine(now.date(), self.TRADING_START)
        
        if now.time() < self.TRADING_START:
            return today_trading_start - now
        else:
            # 다음날 거래 시작까지
            tomorrow_trading_start = today_trading_start + timedelta(days=1)
            return tomorrow_trading_start - now
    
    def get_time_until_trading_end(self) -> Optional[timedelta]:
        """거래 종료까지 남은 시간"""
        now = datetime.now()
        today_trading_end = datetime.combine(now.date(), self.TRADING_END)
        
        if now.time() < self.TRADING_END:
            return today_trading_end - now
        else:
            return timedelta(0)  # 이미 종료됨
    
    async def wait_for_trading_start(self, callback: Optional[Callable] = None) -> bool:
        """
        거래 시작 시간까지 대기
        
        Args:
            callback: 주기적으로 호출할 콜백 함수 (진행 상황 표시용)
            
        Returns:
            bool: 대기 완료 여부 (True: 거래 시작됨, False: 취소됨)
        """
        self.wait_mode_active = True
        self.wait_start_time = datetime.now()
        
        logger.info("거래 시작 대기 모드 활성화")
        
        try:
            while self.wait_mode_active:
                current_phase = self.get_current_phase()
                
                # 거래 시간 도달 체크
                if self.is_trading_time():
                    logger.info("거래 시간 도달 - 대기 모드 종료")
                    self.wait_mode_active = False
                    return True
                
                # 현재 상태 정보
                now = datetime.now()
                time_until_start = self.get_time_until_trading_start()
                
                # 콜백 호출 (진행 상황 알림)
                if callback:
                    wait_info = {
                        'current_time': now.strftime('%H:%M:%S'),
                        'current_phase': current_phase.value,
                        'time_until_start': str(time_until_start).split('.')[0],  # 소수점 제거
                        'trading_start_time': self.TRADING_START.strftime('%H:%M'),
                        'wait_duration': str(now - self.wait_start_time).split('.')[0]
                    }
                    
                    try:
                        await callback(wait_info)
                    except Exception as e:
                        logger.warning(f"대기 콜백 실행 오류: {e}")
                
                # 단계별 대기 전략
                if current_phase == TradingPhase.BEFORE_MARKET:
                    # 장 시작 전 - 30초마다 체크
                    await asyncio.sleep(30)
                elif current_phase == TradingPhase.WAITING:
                    # 거래 시작 대기 중 - 10초마다 체크
                    await asyncio.sleep(10)
                else:
                    # 기타 시간 - 60초마다 체크
                    await asyncio.sleep(60)
            
            return False  # 대기 취소됨
            
        except asyncio.CancelledError:
            logger.info("거래 시작 대기가 취소됨")
            self.wait_mode_active = False
            return False
        except Exception as e:
            logger.error(f"거래 시작 대기 중 오류: {e}")
            self.wait_mode_active = False
            return False
    
    def cancel_wait(self):
        """대기 모드 취소"""
        if self.wait_mode_active:
            logger.info("거래 시작 대기 취소 요청")
            self.wait_mode_active = False
    
    async def monitor_trading_session(self, on_cycle: Callable, on_end: Optional[Callable] = None):
        """
        거래 세션 모니터링 및 사이클 관리
        
        Args:
            on_cycle: 각 사이클마다 호출할 함수
            on_end: 거래 종료시 호출할 함수
        """
        logger.info("거래 세션 모니터링 시작")
        self.is_trading_active = True
        self.cycle_count = 0
        
        try:
            while self.is_trading_active:
                # 현재 거래 시간 체크
                if not self.is_trading_time():
                    logger.info("거래 시간 종료 - 세션 모니터링 중단")
                    break
                
                # 사이클 실행
                self.cycle_count += 1
                cycle_start_time = datetime.now()
                
                try:
                    # 사이클 정보
                    cycle_info = {
                        'cycle_number': self.cycle_count,
                        'start_time': cycle_start_time,
                        'phase': self.get_current_phase(),
                        'interval': self.get_cycle_interval(),
                        'time_until_end': self.get_time_until_trading_end()
                    }
                    
                    logger.info(f"거래 사이클 {self.cycle_count} 시작 - {cycle_info['phase'].value}")
                    
                    # 사이클 콜백 실행
                    await on_cycle(cycle_info)
                    
                    self.last_cycle_time = cycle_start_time
                    
                except Exception as e:
                    logger.error(f"거래 사이클 {self.cycle_count} 실행 오류: {e}")
                
                # 다음 사이클까지 대기
                if self.is_trading_active and self.is_trading_time():
                    interval = self.get_cycle_interval()
                    phase_name = self.get_current_phase().value
                    
                    logger.info(f"다음 사이클까지 {interval//60}분 대기 ({phase_name})")
                    
                    # 대기 중 거래 시간 종료 체크
                    for i in range(interval):
                        if not self.is_trading_time() or not self.is_trading_active:
                            logger.info("대기 중 거래 시간 종료 감지")
                            break
                        await asyncio.sleep(1)
            
            # 거래 세션 종료
            logger.info(f"거래 세션 종료 - 총 {self.cycle_count}개 사이클 완료")
            
            if on_end:
                try:
                    await on_end({
                        'total_cycles': self.cycle_count,
                        'session_duration': datetime.now() - (self.last_cycle_time or datetime.now()),
                        'end_reason': 'time_limit' if not self.is_trading_time() else 'manual_stop'
                    })
                except Exception as e:
                    logger.error(f"거래 종료 콜백 실행 오류: {e}")
        
        except asyncio.CancelledError:
            logger.info("거래 세션 모니터링이 취소됨")
        except Exception as e:
            logger.error(f"거래 세션 모니터링 오류: {e}")
        finally:
            self.is_trading_active = False
    
    def stop_trading(self):
        """거래 중단"""
        if self.is_trading_active:
            logger.info("거래 중단 요청")
            self.is_trading_active = False
    
    def get_trading_status(self) -> Dict[str, Any]:
        """거래 상태 정보 반환"""
        current_phase = self.get_current_phase()
        
        return {
            'current_time': datetime.now().strftime('%H:%M:%S'),
            'current_phase': current_phase.value,
            'is_trading_time': self.is_trading_time(),
            'is_trading_active': self.is_trading_active,
            'wait_mode_active': self.wait_mode_active,
            'cycle_count': self.cycle_count,
            'last_cycle_time': self.last_cycle_time.strftime('%H:%M:%S') if self.last_cycle_time else None,
            'time_until_start': str(self.get_time_until_trading_start()).split('.')[0] if not self.is_trading_time() else None,
            'time_until_end': str(self.get_time_until_trading_end()).split('.')[0] if self.is_trading_time() else None,
            'current_interval': self.get_cycle_interval() // 60,  # 분 단위
            'trading_hours': {
                'start': self.TRADING_START.strftime('%H:%M'),
                'end': self.TRADING_END.strftime('%H:%M'),
                'morning_interval': self.MORNING_INTERVAL // 60,
                'afternoon_interval': self.AFTERNOON_INTERVAL // 60
            }
        }
    
    def update_time_settings(self, trading_start: str = None, trading_end: str = None,
                           morning_interval: int = None, afternoon_interval: int = None):
        """시간 설정 업데이트"""
        try:
            updated = False
            
            if trading_start:
                hour, minute = map(int, trading_start.split(':'))
                self.TRADING_START = time(hour, minute)
                updated = True
                logger.info(f"거래 시작 시간 변경: {trading_start}")
            
            if trading_end:
                hour, minute = map(int, trading_end.split(':'))
                self.TRADING_END = time(hour, minute)
                updated = True
                logger.info(f"거래 종료 시간 변경: {trading_end}")
            
            if morning_interval:
                self.MORNING_INTERVAL = morning_interval
                updated = True
                logger.info(f"오전 사이클 간격 변경: {morning_interval//60}분")
            
            if afternoon_interval:
                self.AFTERNOON_INTERVAL = afternoon_interval
                updated = True
                logger.info(f"오후 사이클 간격 변경: {afternoon_interval//60}분")
            
            if updated:
                self._save_config()
                
        except Exception as e:
            logger.error(f"시간 설정 업데이트 오류: {e}")

# 전역 인스턴스 (싱글톤)
_time_manager_instance = None

def get_trading_time_manager() -> TradingTimeManager:
    """Trading Time Manager 인스턴스 반환 (싱글톤)"""
    global _time_manager_instance
    if _time_manager_instance is None:
        _time_manager_instance = TradingTimeManager()
    return _time_manager_instance

def reset_time_manager():
    """Time Manager 인스턴스 초기화 (테스트용)"""
    global _time_manager_instance
    _time_manager_instance = None

if __name__ == "__main__":
    # 테스트 코드
    import asyncio
    
    async def test_wait_callback(wait_info):
        """대기 중 호출되는 콜백 함수 테스트"""
        print(f"[{wait_info['current_time']}] {wait_info['current_phase']} - "
              f"거래 시작까지: {wait_info['time_until_start']} "
              f"(대기 시간: {wait_info['wait_duration']})")
    
    async def test_cycle_callback(cycle_info):
        """사이클 콜백 함수 테스트"""
        print(f"사이클 {cycle_info['cycle_number']}: {cycle_info['phase'].value} "
              f"- 종료까지: {cycle_info['time_until_end']}")
    
    async def test_trading_time_manager():
        manager = get_trading_time_manager()
        
        print("=== Trading Time Manager 테스트 ===")
        status = manager.get_trading_status()
        
        for key, value in status.items():
            print(f"{key}: {value}")
        
        # 대기 모드 테스트 (실제 거래 시간이 아닌 경우에만)
        if not manager.is_trading_time():
            print("\n거래 시작 대기 모드 테스트...")
            result = await manager.wait_for_trading_start(test_wait_callback)
            print(f"대기 결과: {result}")
        else:
            print("\n현재 거래 시간 - 세션 모니터링 테스트...")
            await manager.monitor_trading_session(test_cycle_callback)
    
    # asyncio.run(test_trading_time_manager())