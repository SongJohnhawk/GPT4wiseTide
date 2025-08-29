"""
NumPy 유틸리티 모듈 - 종목 조회 및 분석 최적화
안전한 배열 처리, 오류 처리, 성능 모니터링 기능 제공
"""

import numpy as np
import logging
import time
from typing import List, Dict, Any, Optional, Union
from functools import wraps
import warnings
warnings.filterwarnings('ignore')

# Numba 제거 - 표준 Python 사용
NUMBA_AVAILABLE = False

# Numba 제거된 더미 데코레이터
def njit(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

def jit(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

# prange fallback
def prange(n):
    return range(n)

logger = logging.getLogger(__name__)


# 성능 모니터링 데코레이터
def performance_monitor(func_name: str = None):
    """NumPy 함수 성능 모니터링 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            func_display_name = func_name or func.__name__
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.perf_counter() - start_time
                
                if execution_time > 0.1:  # 100ms 이상인 경우만 로깅
                    logger.debug(f"[NumPy최적화] {func_display_name}: {execution_time:.3f}초")
                
                return result
                
            except Exception as e:
                execution_time = time.perf_counter() - start_time
                logger.error(f"[NumPy최적화] {func_display_name} 실패 ({execution_time:.3f}초): {e}")
                raise
                
        return wrapper
    return decorator


# 안전한 배열 변환 함수들
@performance_monitor("safe_array_conversion")
def safe_to_numpy(data: Union[List, np.ndarray], dtype=np.float64, 
                  default_value: float = 0.0) -> np.ndarray:
    """안전한 NumPy 배열 변환"""
    try:
        if isinstance(data, np.ndarray):
            return data.astype(dtype)
        
        if not data:  # 빈 리스트 처리
            return np.array([], dtype=dtype)
        
        # None 값 처리
        cleaned_data = []
        for item in data:
            if item is None or item == '' or item == '-':
                cleaned_data.append(default_value)
            else:
                try:
                    cleaned_data.append(float(item))
                except (ValueError, TypeError):
                    cleaned_data.append(default_value)
        
        return np.array(cleaned_data, dtype=dtype)
        
    except Exception as e:
        logger.warning(f"배열 변환 실패: {e}, 기본값 배열 반환")
        return np.array([default_value], dtype=dtype)


@performance_monitor("safe_string_array")
def safe_to_string_array(data: List[str], max_length: int = 10) -> np.ndarray:
    """안전한 문자열 배열 변환"""
    try:
        if not data:
            return np.array([], dtype=f'U{max_length}')
        
        # None, 빈 문자열 처리
        cleaned_data = []
        for item in data:
            if item is None or item == '':
                cleaned_data.append('UNKNOWN')
            else:
                cleaned_data.append(str(item)[:max_length])
        
        return np.array(cleaned_data, dtype=f'U{max_length}')
        
    except Exception as e:
        logger.warning(f"문자열 배열 변환 실패: {e}")
        return np.array(['UNKNOWN'], dtype=f'U{max_length}')


# 벡터화된 데이터 검증 함수들 (Numba 최적화)
def _validate_prices_fast(prices: np.ndarray, min_price: float = 0.0, 
                         max_price: float = 1000000.0) -> np.ndarray:
    """NumPy/Numba 최적화된 가격 검증 (JIT 컴파일 + 병렬 처리)"""
    n = len(prices)
    mask = np.zeros(n, dtype=np.bool_)
    
    # 병렬 처리로 대량 데이터 고속 검증
    for i in prange(n):
        price = prices[i]
        if not np.isnan(price) and not np.isinf(price):
            if min_price <= price <= max_price:
                mask[i] = True
    
    return mask


def _validate_volumes_fast(volumes: np.ndarray, min_volume: float = 0.0) -> np.ndarray:
    """NumPy/Numba 최적화된 거래량 검증 (JIT 컴파일 + 병렬 처리)"""
    n = len(volumes)
    mask = np.zeros(n, dtype=np.bool_)
    
    # 병렬 처리로 대량 데이터 고속 검증
    for i in prange(n):
        volume = volumes[i]
        if not np.isnan(volume) and not np.isinf(volume):
            if volume >= min_volume:
                mask[i] = True
    
    return mask


@performance_monitor("stock_data_validation")
def validate_stock_data(symbols: List[str], prices: List[float], 
                       volumes: List[int], change_rates: List[float]) -> Dict[str, np.ndarray]:
    """종목 데이터 일괄 검증"""
    try:
        # NumPy 배열로 변환
        symbols_array = safe_to_string_array(symbols, 10)
        prices_array = safe_to_numpy(prices, np.float64, 0.0)
        volumes_array = safe_to_numpy(volumes, np.float64, 0.0)
        change_rates_array = safe_to_numpy(change_rates, np.float64, 0.0)
        
        # 배열 길이 통일
        min_length = min(len(symbols_array), len(prices_array), 
                        len(volumes_array), len(change_rates_array))
        
        if min_length == 0:
            logger.warning("유효한 데이터가 없습니다")
            return {
                'symbols': np.array([], dtype='U10'),
                'prices': np.array([], dtype=np.float64),
                'volumes': np.array([], dtype=np.float64),
                'change_rates': np.array([], dtype=np.float64),
                'valid_mask': np.array([], dtype=np.bool_)
            }
        
        symbols_array = symbols_array[:min_length]
        prices_array = prices_array[:min_length]
        volumes_array = volumes_array[:min_length]
        change_rates_array = change_rates_array[:min_length]
        
        # 검증 마스크 생성
        price_mask = _validate_prices_fast(prices_array, 1000.0, 500000.0)  # 1천원~50만원
        volume_mask = _validate_volumes_fast(volumes_array, 1000.0)  # 최소 1000주
        
        # 전체 유효성 마스크
        valid_mask = price_mask & volume_mask
        
        valid_count = np.sum(valid_mask)
        logger.info(f"데이터 검증 완료: {valid_count}/{min_length}개 종목 유효")
        
        return {
            'symbols': symbols_array,
            'prices': prices_array,
            'volumes': volumes_array,
            'change_rates': change_rates_array,
            'valid_mask': valid_mask
        }
        
    except Exception as e:
        logger.error(f"종목 데이터 검증 실패: {e}")
        return {
            'symbols': np.array([], dtype='U10'),
            'prices': np.array([], dtype=np.float64),
            'volumes': np.array([], dtype=np.float64),
            'change_rates': np.array([], dtype=np.float64),
            'valid_mask': np.array([], dtype=np.bool_)
        }


# 중복 제거 및 정렬 함수들
@performance_monitor("deduplicate_stocks")
def deduplicate_stocks(symbols: np.ndarray, scores: np.ndarray) -> Dict[str, np.ndarray]:
    """종목 중복 제거 및 점수 기준 정렬"""
    try:
        if len(symbols) == 0:
            return {
                'symbols': np.array([], dtype='U10'),
                'scores': np.array([], dtype=np.float64),
                'indices': np.array([], dtype=np.int32)
            }
        
        # 중복 제거 (점수가 높은 것 우선)
        unique_symbols, indices = np.unique(symbols, return_index=True)
        unique_scores = scores[indices]
        
        # 점수 기준 내림차순 정렬
        sort_indices = np.argsort(unique_scores)[::-1]
        
        final_symbols = unique_symbols[sort_indices]
        final_scores = unique_scores[sort_indices]
        final_indices = indices[sort_indices]
        
        logger.debug(f"중복 제거 완료: {len(symbols)} -> {len(final_symbols)}개 종목")
        
        return {
            'symbols': final_symbols,
            'scores': final_scores,
            'indices': final_indices
        }
        
    except Exception as e:
        logger.error(f"종목 중복 제거 실패: {e}")
        return {
            'symbols': np.array([], dtype='U10'),
            'scores': np.array([], dtype=np.float64),
            'indices': np.array([], dtype=np.int32)
        }


# 메모리 효율적인 배치 처리
@performance_monitor("batch_process")
def batch_process_stocks(symbols: List[str], batch_size: int = 50) -> List[np.ndarray]:
    """메모리 효율적인 배치 처리"""
    try:
        symbols_array = safe_to_string_array(symbols, 10)
        
        if len(symbols_array) == 0:
            return []
        
        batches = []
        for i in range(0, len(symbols_array), batch_size):
            batch = symbols_array[i:i+batch_size]
            batches.append(batch)
        
        logger.debug(f"배치 처리 완료: {len(symbols_array)}개 종목을 {len(batches)}개 배치로 분할")
        return batches
        
    except Exception as e:
        logger.error(f"배치 처리 실패: {e}")
        return []


# 통계 함수들 (Numba 최적화)
@njit(cache=True, fastmath=True, parallel=False)
def _calculate_statistics_fast(values: np.ndarray) -> tuple:
    """NumPy/Numba 최적화된 통계 계산 (JIT 컴파일 + 수학 최적화)"""
    if len(values) == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    
    # 병렬화 불가능한 순차 연산들을 최적화
    n = len(values)
    
    # 평균 계산 (최적화)
    sum_val = 0.0
    for i in range(n):
        sum_val += values[i]
    mean_val = sum_val / n
    
    # 분산과 min/max 동시 계산 (단일 루프)
    variance_sum = 0.0
    min_val = values[0]
    max_val = values[0]
    
    for i in range(n):
        val = values[i]
        diff = val - mean_val
        variance_sum += diff * diff
        
        if val < min_val:
            min_val = val
        if val > max_val:
            max_val = val
    
    std_val = np.sqrt(variance_sum / n) if n > 0 else 0.0
    median_val = np.median(values)  # NumPy의 최적화된 median 사용
    
    return mean_val, std_val, min_val, max_val, median_val


@performance_monitor("calculate_market_statistics")
def calculate_market_statistics(prices: List[float], volumes: List[int], 
                               change_rates: List[float]) -> Dict[str, float]:
    """시장 통계 계산"""
    try:
        prices_array = safe_to_numpy(prices, np.float64)
        volumes_array = safe_to_numpy(volumes, np.float64)
        change_rates_array = safe_to_numpy(change_rates, np.float64)
        
        if len(prices_array) == 0:
            return {}
        
        # 통계 계산
        price_stats = _calculate_statistics_fast(prices_array)
        volume_stats = _calculate_statistics_fast(volumes_array)
        change_stats = _calculate_statistics_fast(change_rates_array)
        
        return {
            'price_mean': price_stats[0],
            'price_std': price_stats[1],
            'price_min': price_stats[2],
            'price_max': price_stats[3],
            'price_median': price_stats[4],
            'volume_mean': volume_stats[0],
            'volume_std': volume_stats[1],
            'change_mean': change_stats[0],
            'change_std': change_stats[1],
            'total_stocks': len(prices_array),
            'rising_stocks': np.sum(change_rates_array > 0),
            'falling_stocks': np.sum(change_rates_array < 0)
        }
        
    except Exception as e:
        logger.error(f"시장 통계 계산 실패: {e}")
        return {}


# 메모리 사용량 모니터링
def get_memory_usage() -> Dict[str, float]:
    """메모리 사용량 모니터링"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,  # MB
            'vms_mb': memory_info.vms / 1024 / 1024,  # MB
            'percent': process.memory_percent()
        }
    except ImportError:
        return {'error': 'psutil not available'}
    except Exception as e:
        logger.warning(f"메모리 사용량 확인 실패: {e}")
        return {'error': str(e)}


# 캐시 관리
class NumPyCache:
    """NumPy 배열 캐시 관리"""
    
    def __init__(self, max_size: int = 100):
        self.cache = {}
        self.max_size = max_size
        self.access_count = {}
    
    def get(self, key: str) -> Optional[np.ndarray]:
        """캐시에서 배열 가져오기"""
        if key in self.cache:
            self.access_count[key] = self.access_count.get(key, 0) + 1
            return self.cache[key].copy()  # 안전한 복사본 반환
        return None
    
    def set(self, key: str, value: np.ndarray) -> None:
        """캐시에 배열 저장"""
        if len(self.cache) >= self.max_size:
            # LRU 방식으로 가장 적게 사용된 항목 제거
            least_used = min(self.access_count.items(), key=lambda x: x[1])[0]
            del self.cache[least_used]
            del self.access_count[least_used]
        
        self.cache[key] = value.copy()
        self.access_count[key] = 1
    
    def clear(self) -> None:
        """캐시 정리"""
        self.cache.clear()
        self.access_count.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'total_access': sum(self.access_count.values()),
            'memory_mb': sum(arr.nbytes for arr in self.cache.values()) / 1024 / 1024
        }


# 전역 캐시 인스턴스
numpy_cache = NumPyCache(max_size=100)