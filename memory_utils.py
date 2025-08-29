#!/usr/bin/env python3
"""
Memory Management Utilities - 메모리 관리 유틸리티
다른 모듈들이 쉽게 메모리 정리 기능을 사용할 수 있도록 하는 유틸리티
"""

from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

def register_cache(cache_object, name: str):
    """
    캐시 객체를 자동 정리 대상으로 등록
    
    Args:
        cache_object: 정리할 캐시 객체 (dict, list 등)
        name: 캐시 이름 (로그용)
    """
    try:
        # 현재 디렉토리에서 import
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        from daily_token_manager import register_cache_for_cleanup
        register_cache_for_cleanup(cache_object, name)
        logger.debug(f"캐시 등록 성공: {name}")
    except Exception as e:
        logger.warning(f"캐시 등록 실패 {name}: {e}")

def force_cleanup() -> Optional[Dict[str, Any]]:
    """
    즉시 메모리 정리 실행
    
    Returns:
        정리 결과 딕셔너리 또는 None
    """
    try:
        # 현재 디렉토리에서 import
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        from daily_token_manager import force_memory_cleanup
        result = force_memory_cleanup()
        if result and result.get('success'):
            freed_mb = result.get('freed_memory_mb', 0)
            logger.info(f"메모리 정리 완료: {freed_mb:.1f}MB 해제")
        return result
    except Exception as e:
        logger.error(f"메모리 정리 실패: {e}")
        return None

def get_memory_status() -> Optional[Dict[str, Any]]:
    """
    현재 메모리 상태 조회
    
    Returns:
        메모리 상태 딕셔너리 또는 None
    """
    try:
        # 현재 디렉토리에서 import
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        from daily_token_manager import get_memory_status
        return get_memory_status()
    except Exception as e:
        logger.error(f"메모리 상태 조회 실패: {e}")
        return None

def print_memory_status():
    """메모리 상태를 콘솔에 출력"""
    status = get_memory_status()
    if status:
        current_memory = status['current_memory']
        print(f"현재 메모리: {current_memory['rss_mb']:.1f}MB ({current_memory['percent']:.1f}%)")
        print(f"사용 가능한 메모리: {current_memory['available_mb']:.0f}MB")
        print(f"등록된 캐시: {status['registered_caches']}개")
        
        last_cleanup = status.get('last_cleanup')
        if last_cleanup:
            print(f"마지막 정리: {last_cleanup}")
        else:
            print("아직 정리 실행 안됨")
    else:
        print("메모리 상태 조회 불가")

class MemoryTracker:
    """메모리 추적 및 관리 클래스"""
    
    def __init__(self, name: str):
        self.name = name
        self.caches = {}
        logger.debug(f"MemoryTracker 생성: {name}")
    
    def add_cache(self, cache_name: str, cache_object):
        """캐시 추가 및 자동 등록"""
        self.caches[cache_name] = cache_object
        register_cache(cache_object, f"{self.name}_{cache_name}")
        logger.debug(f"캐시 추가: {self.name}_{cache_name}")
    
    def clear_cache(self, cache_name: str):
        """특정 캐시 수동 정리"""
        if cache_name in self.caches:
            cache_obj = self.caches[cache_name]
            try:
                if hasattr(cache_obj, 'clear'):
                    cache_obj.clear()
                elif isinstance(cache_obj, (dict, list)):
                    cache_obj.clear()
                logger.debug(f"캐시 수동 정리: {self.name}_{cache_name}")
            except Exception as e:
                logger.warning(f"캐시 정리 실패 {self.name}_{cache_name}: {e}")
    
    def clear_all_caches(self):
        """모든 캐시 수동 정리"""
        for cache_name in list(self.caches.keys()):
            self.clear_cache(cache_name)

# 데코레이터: 함수 결과를 자동으로 캐시 등록
def auto_cache(cache_name: str):
    """
    함수의 결과를 자동으로 캐시로 등록하는 데코레이터
    
    Args:
        cache_name: 캐시 이름
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            # 결과가 캐시 가능한 객체면 등록
            if isinstance(result, (dict, list)):
                register_cache(result, f"{func.__name__}_{cache_name}")
            return result
        return wrapper
    return decorator

# 글로벌 메모리 추적기들
_memory_trackers = {}

def get_memory_tracker(name: str) -> MemoryTracker:
    """메모리 추적기 싱글톤 반환"""
    if name not in _memory_trackers:
        _memory_trackers[name] = MemoryTracker(name)
    return _memory_trackers[name]

# 편의 함수들
def cleanup_if_needed(threshold_mb: float = 100.0):
    """
    메모리 사용량이 임계값을 초과하면 정리 실행
    
    Args:
        threshold_mb: 메모리 사용 임계값 (MB)
    """
    status = get_memory_status()
    if status:
        current_mb = status['current_memory']['rss_mb']
        if current_mb > threshold_mb:
            logger.info(f"메모리 사용량 {current_mb:.1f}MB > {threshold_mb}MB, 정리 시작")
            force_cleanup()

def cleanup_on_low_memory(threshold_percent: float = 85.0):
    """
    시스템 메모리 사용률이 높으면 정리 실행
    
    Args:
        threshold_percent: 메모리 사용률 임계값 (%)
    """
    status = get_memory_status()
    if status:
        available_mb = status['current_memory']['available_mb']
        # 시스템 전체 메모리의 15% 미만이면 정리
        try:
            import psutil
            total_memory_mb = psutil.virtual_memory().total / 1024 / 1024
            usage_percent = ((total_memory_mb - available_mb) / total_memory_mb) * 100
            
            if usage_percent > threshold_percent:
                logger.warning(f"시스템 메모리 사용률 {usage_percent:.1f}% > {threshold_percent}%, 정리 시작")
                force_cleanup()
        except Exception as e:
            logger.debug(f"시스템 메모리 확인 실패: {e}")

# 사용 예제 및 테스트
def test_memory_utils():
    """메모리 유틸리티 테스트"""
    print("=== Memory Utils 테스트 ===")
    
    # 메모리 상태 출력
    print_memory_status()
    
    # 테스트용 캐시 생성
    tracker = get_memory_tracker('test_module')
    
    test_cache = {'data': list(range(1000))}
    tracker.add_cache('test_data', test_cache)
    
    # 메모리 정리 테스트
    result = force_cleanup()
    if result:
        print(f"\n정리 결과: {result.get('freed_memory_mb', 0):.1f}MB 해제")
    
    print("\n메모리 유틸리티 테스트 완료")

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    test_memory_utils()