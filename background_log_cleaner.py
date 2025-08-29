#!/usr/bin/env python3
"""
백그라운드 로그 정리 서비스
사용자 개입 없이 자동으로 오래된 로그 파일을 정리하는 백그라운드 서비스
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Optional
from pathlib import Path

try:
    from .log_manager import get_log_manager
except ImportError:
    from log_manager import get_log_manager


class BackgroundLogCleaner:
    """백그라운드에서 실행되는 로그 정리 서비스"""
    
    def __init__(self, cleanup_time: time = time(2, 0), cleanup_interval_hours: int = 24):
        """
        백그라운드 로그 클리너 초기화
        
        Args:
            cleanup_time: 일일 정리 시간 (기본: 새벽 2시)
            cleanup_interval_hours: 정리 간격 (시간, 기본: 24시간)
        """
        self.log_manager = get_log_manager()
        self.cleanup_time = cleanup_time
        self.cleanup_interval_hours = cleanup_interval_hours
        self.is_running = False
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # 로거 설정 (시스템 로그)
        self.logger = self.log_manager.setup_logger(
            log_type='system',
            logger_name='BackgroundLogCleaner',
            level=logging.INFO
        )
    
    async def start(self):
        """백그라운드 로그 정리 서비스 시작"""
        if self.is_running:
            return
        
        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.logger.info("백그라운드 로그 정리 서비스가 시작되었습니다.")
    
    async def stop(self):
        """백그라운드 로그 정리 서비스 중지"""
        self.is_running = False
        
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("백그라운드 로그 정리 서비스가 중지되었습니다.")
    
    async def _cleanup_loop(self):
        """로그 정리 루프"""
        last_cleanup = None
        
        while self.is_running:
            try:
                current_time = datetime.now()
                
                # 첫 실행이거나 지정된 시간이 되었을 때 정리 실행
                should_cleanup = False
                
                if last_cleanup is None:
                    # 첫 실행 시 즉시 정리
                    should_cleanup = True
                    self.logger.info("첫 실행 로그 정리를 시작합니다.")
                else:
                    # 지정된 시간에 정리
                    time_since_last = (current_time - last_cleanup).total_seconds() / 3600
                    if time_since_last >= self.cleanup_interval_hours:
                        current_time_only = current_time.time()
                        if (current_time_only.hour == self.cleanup_time.hour and 
                            current_time_only.minute >= self.cleanup_time.minute):
                            should_cleanup = True
                            self.logger.info(f"정기 로그 정리를 시작합니다. (마지막 정리: {last_cleanup})")
                
                if should_cleanup:
                    await self._perform_cleanup()
                    last_cleanup = current_time
                
                # 10분마다 체크
                await asyncio.sleep(600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"로그 정리 중 오류 발생: {e}")
                await asyncio.sleep(3600)  # 오류 발생 시 1시간 대기
    
    async def _perform_cleanup(self):
        """실제 로그 정리 수행"""
        try:
            # 비동기적으로 정리 작업 실행
            deleted_files = await asyncio.get_event_loop().run_in_executor(
                None, self.log_manager.cleanup_old_logs, False
            )
            
            if deleted_files:
                self.logger.info(f"로그 파일 {len(deleted_files)}개를 정리했습니다.")
                for deleted_file in deleted_files:
                    self.logger.debug(f"삭제됨: {deleted_file}")
            else:
                self.logger.debug("정리할 로그 파일이 없습니다.")
            
            # 로그 통계 출력
            stats = await asyncio.get_event_loop().run_in_executor(
                None, self.log_manager.get_log_stats
            )
            
            self.logger.info(
                f"현재 로그 상태: {stats['total_files']}개 파일, "
                f"{stats['total_size_mb']:.2f}MB"
            )
            
        except Exception as e:
            self.logger.error(f"로그 정리 실행 중 오류: {e}")
    
    async def force_cleanup(self):
        """즉시 로그 정리 실행 (필요시 호출)"""
        if not self.is_running:
            await self.start()
        
        self.logger.info("즉시 로그 정리를 실행합니다.")
        await self._perform_cleanup()


# 전역 백그라운드 클리너 인스턴스
_background_cleaner: Optional[BackgroundLogCleaner] = None


async def start_background_log_cleaner():
    """백그라운드 로그 클리너 시작"""
    global _background_cleaner
    
    if _background_cleaner is None:
        _background_cleaner = BackgroundLogCleaner()
    
    await _background_cleaner.start()


async def stop_background_log_cleaner():
    """백그라운드 로그 클리너 중지"""
    global _background_cleaner
    
    if _background_cleaner:
        await _background_cleaner.stop()


def get_background_cleaner() -> Optional[BackgroundLogCleaner]:
    """백그라운드 클리너 인스턴스 반환"""
    return _background_cleaner


if __name__ == "__main__":
    # 테스트 실행
    async def test():
        cleaner = BackgroundLogCleaner()
        await cleaner.start()
        
        print("백그라운드 로그 클리너 테스트 실행 중...")
        print("5초 후 강제 정리 실행...")
        
        await asyncio.sleep(5)
        await cleaner.force_cleanup()
        
        print("10초 더 대기 후 종료...")
        await asyncio.sleep(10)
        await cleaner.stop()
        
        print("테스트 완료")
    
    asyncio.run(test())