#!/usr/bin/env python3
"""
Memory Cleanup Manager - 메모리 정리 관리 시스템
- 30분마다 자동으로 메모리 캐시 정리
- 백그라운드에서 실행되어 성능 최적화
- 중요한 데이터는 보존하고 불필요한 캐시만 삭제
"""

import os
import gc
import sys
import time
import psutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# 로거 설정
logger = logging.getLogger(__name__)

class MemoryCleanupManager:
    """메모리 정리 관리자"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self._cleanup_thread = None
        self._stop_flag = threading.Event()
        self.cleanup_interval = 1800  # 30분 (1800초)
        
        # 정리할 캐시 경로들
        self.cache_paths = [
            self.project_root / "cache",
            self.project_root / "temp",
            self.project_root / "logs" / "temp",
            Path.cwd() / "__pycache__",
        ]
        
        # 정리할 메모리 캐시 변수들 (전역 변수 추적)
        self.memory_caches = []
        
        # 성능 모니터링
        self.process = psutil.Process(os.getpid())
        self.cleanup_history = []
        
        # 백그라운드 스레드 시작
        self.start_background_cleanup()
        
        logger.info("Memory Cleanup Manager 초기화 완료 - 30분마다 자동 정리")
    
    def register_cache(self, cache_object, name: str):
        """정리할 캐시 객체 등록"""
        self.memory_caches.append({
            'object': cache_object,
            'name': name,
            'registered_at': datetime.now()
        })
        logger.debug(f"메모리 캐시 등록: {name}")
    
    def get_memory_usage(self) -> Dict[str, float]:
        """현재 메모리 사용량 반환"""
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            return {
                'rss_mb': memory_info.rss / 1024 / 1024,  # 물리 메모리 (MB)
                'vms_mb': memory_info.vms / 1024 / 1024,  # 가상 메모리 (MB)
                'percent': memory_percent,  # 메모리 사용률 (%)
                'available_mb': psutil.virtual_memory().available / 1024 / 1024
            }
        except Exception as e:
            logger.warning(f"메모리 사용량 조회 실패: {e}")
            return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0, 'available_mb': 0}
    
    def cleanup_file_caches(self) -> Dict[str, int]:
        """파일 캐시 정리"""
        cleanup_stats = {'deleted_files': 0, 'freed_space_mb': 0}
        
        try:
            # 임시 파일들 정리
            temp_patterns = [
                "*.tmp", "*.temp", "*.cache", "*.log.old", "*.bak"
            ]
            
            for cache_path in self.cache_paths:
                if cache_path.exists():
                    for pattern in temp_patterns:
                        for file_path in cache_path.glob(f"**/{pattern}"):
                            try:
                                if file_path.is_file():
                                    # 1시간 이상 된 파일만 삭제
                                    if datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime) > timedelta(hours=1):
                                        file_size = file_path.stat().st_size
                                        file_path.unlink()
                                        cleanup_stats['deleted_files'] += 1
                                        cleanup_stats['freed_space_mb'] += file_size / 1024 / 1024
                            except Exception as e:
                                logger.debug(f"파일 삭제 실패 {file_path}: {e}")
            
            # __pycache__ 디렉토리 정리
            for pycache_path in self.project_root.rglob("__pycache__"):
                if pycache_path.is_dir():
                    try:
                        import shutil
                        shutil.rmtree(pycache_path)
                        cleanup_stats['deleted_files'] += 1
                        logger.debug(f"__pycache__ 삭제: {pycache_path}")
                    except Exception as e:
                        logger.debug(f"__pycache__ 삭제 실패 {pycache_path}: {e}")
                        
        except Exception as e:
            logger.warning(f"파일 캐시 정리 중 오류: {e}")
        
        return cleanup_stats
    
    def cleanup_memory_caches(self) -> Dict[str, int]:
        """메모리 캐시 정리"""
        cleanup_stats = {'cleared_caches': 0, 'cleared_objects': 0}
        
        try:
            # 등록된 캐시 객체들 정리
            for cache_info in self.memory_caches[:]:  # 복사본으로 순회
                try:
                    cache_obj = cache_info['object']
                    cache_name = cache_info['name']
                    
                    # 캐시 객체가 여전히 유효한지 확인
                    if hasattr(cache_obj, 'clear'):
                        cache_obj.clear()
                        cleanup_stats['cleared_caches'] += 1
                        logger.debug(f"캐시 클리어: {cache_name}")
                    elif isinstance(cache_obj, dict):
                        cache_obj.clear()
                        cleanup_stats['cleared_caches'] += 1
                        logger.debug(f"딕셔너리 캐시 클리어: {cache_name}")
                    elif isinstance(cache_obj, list):
                        cache_obj.clear()
                        cleanup_stats['cleared_caches'] += 1
                        logger.debug(f"리스트 캐시 클리어: {cache_name}")
                        
                except Exception as e:
                    logger.debug(f"캐시 정리 실패 {cache_info['name']}: {e}")
                    # 실패한 캐시는 목록에서 제거
                    self.memory_caches.remove(cache_info)
            
            # Python 가비지 컬렉션 강제 실행
            collected = gc.collect()
            cleanup_stats['cleared_objects'] += collected
            
        except Exception as e:
            logger.warning(f"메모리 캐시 정리 중 오류: {e}")
        
        return cleanup_stats
    
    def cleanup_pandas_caches(self) -> Dict[str, int]:
        """pandas 관련 캐시 정리"""
        cleanup_stats = {'cleared_pandas': 0}
        
        try:
            # pandas가 임포트되어 있다면
            if 'pandas' in sys.modules:
                import pandas as pd
                # pandas 내부 캐시 정리 (가능한 경우)
                if hasattr(pd.core.computation, 'expressions'):
                    pd.core.computation.expressions._parsers.clear()
                    cleanup_stats['cleared_pandas'] += 1
                    
        except Exception as e:
            logger.debug(f"pandas 캐시 정리 실패: {e}")
            
        return cleanup_stats
    
    def cleanup_system_caches(self) -> Dict[str, int]:
        """시스템 레벨 캐시 정리"""
        cleanup_stats = {'cleared_system': 0}
        
        try:
            # import 캐시 정리
            importlib_modules = [name for name in sys.modules if name.startswith('importlib')]
            for module_name in importlib_modules:
                if hasattr(sys.modules[module_name], '_cache'):
                    sys.modules[module_name]._cache.clear()
                    cleanup_stats['cleared_system'] += 1
            
            # functools lru_cache 정리는 위험할 수 있으므로 제외
            
        except Exception as e:
            logger.debug(f"시스템 캐시 정리 실패: {e}")
            
        return cleanup_stats
    
    def perform_cleanup(self) -> Dict[str, Any]:
        """전체 정리 작업 수행"""
        start_time = datetime.now()
        before_memory = self.get_memory_usage()
        
        logger.info("=== 메모리 정리 시작 ===")
        logger.info(f"정리 전 메모리: {before_memory['rss_mb']:.1f}MB ({before_memory['percent']:.1f}%)")
        
        try:
            # 각 정리 작업 수행
            file_stats = self.cleanup_file_caches()
            memory_stats = self.cleanup_memory_caches()
            pandas_stats = self.cleanup_pandas_caches()
            system_stats = self.cleanup_system_caches()
            
            # 정리 후 메모리 상태
            after_memory = self.get_memory_usage()
            duration = (datetime.now() - start_time).total_seconds()
            
            # 통합 결과
            cleanup_result = {
                'timestamp': start_time,
                'duration_seconds': duration,
                'before_memory_mb': before_memory['rss_mb'],
                'after_memory_mb': after_memory['rss_mb'],
                'freed_memory_mb': before_memory['rss_mb'] - after_memory['rss_mb'],
                'memory_percent_before': before_memory['percent'],
                'memory_percent_after': after_memory['percent'],
                'file_stats': file_stats,
                'memory_stats': memory_stats,
                'pandas_stats': pandas_stats,
                'system_stats': system_stats,
                'success': True
            }
            
            # 히스토리에 저장 (최근 24개만 유지)
            self.cleanup_history.append(cleanup_result)
            if len(self.cleanup_history) > 24:  # 12시간 분량
                self.cleanup_history.pop(0)
            
            logger.info(f"정리 완료: {cleanup_result['freed_memory_mb']:.1f}MB 해제")
            logger.info(f"정리 후 메모리: {after_memory['rss_mb']:.1f}MB ({after_memory['percent']:.1f}%)")
            logger.info(f"소요 시간: {duration:.2f}초")
            
            return cleanup_result
            
        except Exception as e:
            logger.error(f"메모리 정리 중 오류 발생: {e}")
            return {
                'timestamp': start_time,
                'success': False,
                'error': str(e),
                'before_memory_mb': before_memory['rss_mb'],
                'freed_memory_mb': 0
            }
    
    def start_background_cleanup(self):
        """백그라운드 정리 스레드 시작"""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self._cleanup_thread.start()
            logger.info(f"백그라운드 메모리 정리 시작됨 (간격: {self.cleanup_interval/60:.0f}분)")
    
    def _cleanup_loop(self):
        """백그라운드 정리 루프"""
        while not self._stop_flag.is_set():
            try:
                # 30분 대기
                if self._stop_flag.wait(timeout=self.cleanup_interval):
                    break
                
                # 정리 작업 수행
                self.perform_cleanup()
                
            except Exception as e:
                logger.error(f"백그라운드 메모리 정리 오류: {e}")
                # 오류 시 5분 후 재시도
                if self._stop_flag.wait(timeout=300):
                    break
    
    def force_cleanup(self) -> Dict[str, Any]:
        """즉시 정리 작업 수행"""
        logger.info("수동 메모리 정리 시작")
        return self.perform_cleanup()
    
    def get_cleanup_history(self, hours: int = 12) -> List[Dict[str, Any]]:
        """정리 히스토리 반환"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            record for record in self.cleanup_history 
            if record['timestamp'] >= cutoff_time
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 반환"""
        memory_usage = self.get_memory_usage()
        
        return {
            'current_memory': memory_usage,
            'cleanup_interval_minutes': self.cleanup_interval / 60,
            'registered_caches': len(self.memory_caches),
            'cleanup_history_count': len(self.cleanup_history),
            'background_running': self._cleanup_thread.is_alive() if self._cleanup_thread else False,
            'last_cleanup': self.cleanup_history[-1]['timestamp'] if self.cleanup_history else None
        }
    
    def stop(self):
        """백그라운드 스레드 종료"""
        self._stop_flag.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        logger.info("Memory Cleanup Manager 종료됨")

# 싱글톤 인스턴스
_memory_cleanup_manager = None

def get_memory_cleanup_manager() -> MemoryCleanupManager:
    """메모리 정리 관리자 싱글톤 인스턴스 반환"""
    global _memory_cleanup_manager
    if _memory_cleanup_manager is None:
        _memory_cleanup_manager = MemoryCleanupManager()
    return _memory_cleanup_manager

# 편의 함수들
def register_cache_for_cleanup(cache_object, name: str):
    """캐시 객체를 정리 대상으로 등록"""
    manager = get_memory_cleanup_manager()
    manager.register_cache(cache_object, name)

def force_memory_cleanup():
    """즉시 메모리 정리 실행"""
    manager = get_memory_cleanup_manager()
    return manager.force_cleanup()

def get_memory_status():
    """현재 메모리 상태 반환"""
    manager = get_memory_cleanup_manager()
    return manager.get_status()

# 테스트 함수
def test_memory_cleanup():
    """메모리 정리 시스템 테스트"""
    print("=== Memory Cleanup Manager 테스트 ===")
    
    manager = get_memory_cleanup_manager()
    
    # 현재 상태 출력
    status = manager.get_status()
    print(f"현재 메모리: {status['current_memory']['rss_mb']:.1f}MB")
    print(f"메모리 사용률: {status['current_memory']['percent']:.1f}%")
    print(f"등록된 캐시: {status['registered_caches']}개")
    
    # 테스트용 캐시 등록
    test_cache = {'test_data': list(range(10000))}
    manager.register_cache(test_cache, 'test_cache')
    
    # 즉시 정리 테스트
    print("\n수동 정리 테스트...")
    result = manager.force_cleanup()
    
    if result['success']:
        print(f"정리 성공: {result['freed_memory_mb']:.1f}MB 해제")
        print(f"소요 시간: {result['duration_seconds']:.2f}초")
    else:
        print(f"정리 실패: {result.get('error', 'Unknown error')}")
    
    print(f"\n백그라운드 정리가 {manager.cleanup_interval/60:.0f}분마다 자동 실행됩니다")

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    test_memory_cleanup()
    
    # 테스트용으로 1분 대기
    print("1분간 백그라운드 실행 테스트...")
    time.sleep(60)