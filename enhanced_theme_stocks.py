"""
테마 종목 로더 (NumPy 최적화)
enhanced_theme_stocks.json 파일에서 종목을 빠르게 로드하고 분석합니다
"""

import json
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
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

def _extract_symbols_fast(stock_codes: np.ndarray, max_symbols: int = 20) -> np.ndarray:
    """Python 기본 구현 심볼 추출"""
    result_size = min(len(stock_codes), max_symbols)
    return stock_codes[:result_size]

# 깔끔한 콘솔 로거 사용
from support.clean_console_logger import (
    get_clean_logger, Phase, log as clean_log
)

def get_enhanced_theme_stocks() -> Dict[str, Any]:
    """enhanced_theme_stocks.json에서 테마별 종목 데이터 직접 로드"""
    try:
        theme_file = Path(__file__).parent / "enhanced_theme_stocks.json"
        if not theme_file.exists():
            # enhanced_theme_stocks.json 파일이 없음 (로그 제거)
            return {}
        
        with open(theme_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        clean_log(f"Enhanced theme stocks 로드 성공: {len([k for k in data.keys() if not k.startswith('_')])}개 테마", "SUCCESS")
        return data
        
    except Exception as e:
        clean_log(f"Enhanced theme stocks 로드 실패: {e}", "ERROR")
        return {}

def load_theme_stocks() -> Dict[str, Any]:
    """NumPy 최적화된 테마 종목 로드 (딕셔너리 형태로 반환)"""
    try:
        theme_file = Path(__file__).parent / "enhanced_theme_stocks.json"
        if not theme_file.exists():
            # enhanced_theme_stocks.json 파일이 없음 (로그 제거)
            return {}
        
        with open(theme_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # NumPy 기반 데이터 정규화 (벡터화 처리)
        normalized_data = {}
        all_symbols = []  # 전체 심볼 수집용
        
        for theme_name, theme_data in data.items():
            if isinstance(theme_data, dict) and 'stocks' in theme_data:
                # 심볼 추출을 NumPy 배열로 벡터화
                theme_symbols = []
                for stock in theme_data['stocks']:
                    if isinstance(stock, dict) and 'symbol' in stock:
                        theme_symbols.append(stock['symbol'])
                    elif isinstance(stock, str):
                        theme_symbols.append(stock)
                
                # NumPy 배열로 변환하여 빠른 슬라이싱
                if theme_symbols:
                    symbols_array = np.array(theme_symbols, dtype='U10')  # 최대 10자 문자열
                    # Numba JIT 함수로 빠른 추출
                    selected_symbols = _extract_symbols_fast(symbols_array, 20)
                    final_symbols = selected_symbols.tolist()
                    
                    normalized_data[theme_name] = {
                        'stocks': final_symbols,
                        'description': theme_data.get('description', ''),
                        'count': len(final_symbols)
                    }
                    
                    all_symbols.extend(final_symbols)
        
        # 중복 제거 (NumPy unique 사용)
        if all_symbols:
            unique_symbols = np.unique(np.array(all_symbols))
            clean_log(f"테마별 종목 로드 완룼: {len(normalized_data)}개 테마, "
                       f"총 {len(unique_symbols)}개 고유 종목", "SUCCESS")
        else:
            clean_log("로드된 종목이 없습니다", "WARNING")
        
        return normalized_data
        
    except Exception as e:
        clean_log(f"테마 종목 로드 실패: {e}", "ERROR")
        return {}

def load_theme_stocks_list() -> List[str]:
    """NumPy 최적화된 테마 종목 리스트 로드 (하위 호환성)"""
    theme_data = load_theme_stocks()
    
    # 모든 종목을 수집하여 NumPy 배열로 처리
    all_stocks = []
    for theme_name, theme_info in theme_data.items():
        if isinstance(theme_info, dict) and 'stocks' in theme_info:
            all_stocks.extend(theme_info['stocks'])
    
    if not all_stocks:
        clean_log("동적 테마 종목 로드 실패 - 하드코딩 데이터 사용 금지", "WARNING")
        return []
    
    # NumPy 배열로 변환하여 빠른 처리
    stocks_array = np.array(all_stocks, dtype='U10')
    
    # 중복 제거 및 최대 100개 선택 (NumPy 벡터화)
    unique_stocks = np.unique(stocks_array)
    final_stocks = unique_stocks[:100] if len(unique_stocks) > 100 else unique_stocks
    
    return final_stocks.tolist()


def get_default_stocks() -> List[str]:
    """기본 종목 리스트 - 동적 로드만 허용, 하드코딩 데이터 사용 금지"""
    try:
        # enhanced_theme_stocks.json에서 Core_Large_Cap 테마를 동적으로 로드
        theme_data = get_enhanced_theme_stocks()
        if 'Core_Large_Cap' in theme_data and 'stocks' in theme_data['Core_Large_Cap']:
            return theme_data['Core_Large_Cap']['stocks']
    except Exception:
        clean_log("동적 종목 데이터 로드 실패", "WARNING")
    
    # 하드코딩된 fallback 데이터 사용 금지 - 빈 리스트 반환
    # 하드코딩된 종목 데이터 사용 금지 (로그 제거)
    return []


def get_default_theme_stocks() -> Dict[str, Any]:
    """기본 테마별 종목 데이터 - JSON에서 동적 로드"""
    try:
        # enhanced_theme_stocks.json에서 직접 로드
        return get_enhanced_theme_stocks()
    except Exception:
        # JSON 파일에서 직접 로드 시도 (최종 fallback)
        try:
            theme_file = Path(__file__).parent / "enhanced_theme_stocks.json"  
            if theme_file.exists():
                with open(theme_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        # 최종 emergency fallback - 빈 테마
        return {}


def get_theme_info() -> Dict[str, Any]:
    """테마 정보 조회"""
    try:
        theme_file = Path(__file__).parent / "enhanced_theme_stocks.json"
        if theme_file.exists():
            with open(theme_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    
    return {
        "default_theme": {
            "name": "기본 종목",
            "stocks": get_default_stocks(),
            "description": "기본 대형주 종목"
        }
    }