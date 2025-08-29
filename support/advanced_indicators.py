#!/usr/bin/env python3
"""
[opt][algo][ai] 고급 기술적 지표 라이브러리
- GPU 없이 구현 가능한 고성능 기술적 분석 지표들
- AdvancedAutoTradingAlgorithm 전용 최적화
- 15% 목표 수익률 달성을 위한 정밀 지표
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')

class AdvancedIndicators:
    """고급 기술적 지표 계산 클래스"""
    
    @staticmethod
    def calculate_macd_histogram(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
        """
        MACD Histogram 분석 - 추세 전환점 포착
        Returns: {'macd': array, 'signal': array, 'histogram': array, 'divergence': array}
        """
        if len(close) < slow + signal:
            return {
                'macd': np.zeros(len(close)),
                'signal': np.zeros(len(close)),
                'histogram': np.zeros(len(close)),
                'divergence': np.zeros(len(close))
            }
        
        # EMA 계산
        def calculate_ema(data, window):
            ema = np.zeros_like(data)
            multiplier = 2 / (window + 1)
            ema[window-1] = np.mean(data[:window])
            
            for i in range(window, len(data)):
                ema[i] = (data[i] * multiplier) + (ema[i-1] * (1 - multiplier))
            
            return ema
        
        # MACD 계산
        ema_fast = calculate_ema(close, fast)
        ema_slow = calculate_ema(close, slow)
        macd = ema_fast - ema_slow
        
        # Signal Line
        signal_line = calculate_ema(macd, signal)
        
        # Histogram
        histogram = macd - signal_line
        
        # Divergence 감지 (히스토그램과 가격의 분기)
        divergence = np.zeros(len(close))
        lookback = 10
        
        for i in range(lookback, len(close)):
            # 가격 추세
            price_trend = close[i] - close[i-lookback]
            # 히스토그램 추세  
            hist_trend = histogram[i] - histogram[i-lookback]
            
            # 분기 감지 (가격은 상승하지만 히스토그램은 하락)
            if price_trend > 0 and hist_trend < 0:
                divergence[i] = -1  # 약세 분기
            elif price_trend < 0 and hist_trend > 0:
                divergence[i] = 1   # 강세 분기
        
        return {
            'macd': macd,
            'signal': signal_line,
            'histogram': histogram,
            'divergence': divergence
        }
    
    @staticmethod
    def calculate_ichimoku_cloud(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Ichimoku Cloud 전략 - 종합적 추세 분석
        Returns: {'tenkan': array, 'kijun': array, 'senkou_a': array, 'senkou_b': array, 'chikou': array, 'cloud_signal': array}
        """
        if len(close) < 52:
            return {
                'tenkan': np.zeros(len(close)),
                'kijun': np.zeros(len(close)),
                'senkou_a': np.zeros(len(close)),
                'senkou_b': np.zeros(len(close)),
                'chikou': np.zeros(len(close)),
                'cloud_signal': np.zeros(len(close))
            }
        
        # Tenkan-sen (전환선) - 9일 중간값
        tenkan = np.zeros(len(close))
        for i in range(8, len(close)):
            tenkan[i] = (np.max(high[i-8:i+1]) + np.min(low[i-8:i+1])) / 2
        
        # Kijun-sen (기준선) - 26일 중간값
        kijun = np.zeros(len(close))
        for i in range(25, len(close)):
            kijun[i] = (np.max(high[i-25:i+1]) + np.min(low[i-25:i+1])) / 2
        
        # Senkou Span A (선행스팬A) - (전환선 + 기준선) / 2, 26일 후행
        senkou_a = np.zeros(len(close))
        for i in range(26, len(close)):
            if i >= 26:
                senkou_a[i] = (tenkan[i-26] + kijun[i-26]) / 2
        
        # Senkou Span B (선행스팬B) - 52일 중간값, 26일 후행
        senkou_b = np.zeros(len(close))
        for i in range(51, len(close)):
            if i >= 51:
                senkou_b[i] = (np.max(high[i-51:i-25]) + np.min(low[i-51:i-25])) / 2
        
        # Chikou Span (후행스팬) - 현재 종가를 26일 전에 표시
        chikou = np.zeros(len(close))
        for i in range(26, len(close)):
            chikou[i-26] = close[i]
        
        # Cloud Signal 생성
        cloud_signal = np.zeros(len(close))
        for i in range(26, len(close)):
            # 가격이 구름 위에 있고, 구름이 상승 추세
            if (close[i] > max(senkou_a[i], senkou_b[i]) and 
                tenkan[i] > kijun[i] and
                close[i] > kijun[i]):
                cloud_signal[i] = 1.0  # 강한 상승 신호
            # 가격이 구름 아래에 있고, 구름이 하락 추세
            elif (close[i] < min(senkou_a[i], senkou_b[i]) and
                  tenkan[i] < kijun[i]):
                cloud_signal[i] = -1.0  # 강한 하락 신호
            # 가격이 구름 내부 (보합)
            elif min(senkou_a[i], senkou_b[i]) <= close[i] <= max(senkou_a[i], senkou_b[i]):
                cloud_signal[i] = 0.0  # 중립
            # 기타 상황
            elif close[i] > kijun[i] and tenkan[i] > kijun[i]:
                cloud_signal[i] = 0.5  # 약한 상승 신호
        
        return {
            'tenkan': tenkan,
            'kijun': kijun,
            'senkou_a': senkou_a,
            'senkou_b': senkou_b,
            'chikou': chikou,
            'cloud_signal': cloud_signal
        }
    
    @staticmethod
    def calculate_volume_profile(close: np.ndarray, volume: np.ndarray, bins: int = 20) -> Dict[str, np.ndarray]:
        """
        Volume Profile 분석 - 가격대별 거래량 분포 (배열 안전성 강화)
        Returns: {'poc': array, 'volume_ratio': array, 'value_area': array}
        """
        # 배열 길이 검증 및 통일
        min_length = min(len(close), len(volume))
        if min_length < 20:
            return {
                'poc': np.zeros(min_length),
                'volume_ratio': np.ones(min_length),
                'value_area': np.zeros(min_length)
            }
        
        # 배열 길이 통일
        close = close[:min_length]
        volume = volume[:min_length]
        
        poc = np.zeros(min_length)  # Point of Control
        volume_ratio = np.ones(min_length)  # Current price vs POC
        value_area = np.zeros(min_length)  # Value Area indicator
        
        lookback = min(50, min_length // 2)  # 적응형 lookback 기간
        
        for i in range(lookback, min_length):
            try:
                # 최근 N일 데이터 (배열 경계 확인)
                start_idx = max(0, i - lookback)
                end_idx = min(i, min_length)
                
                recent_close = close[start_idx:end_idx]
                recent_volume = volume[start_idx:end_idx]
                
                # 길이 재확인
                if len(recent_close) != len(recent_volume) or len(recent_close) == 0:
                    poc[i] = close[i] if i < len(close) else 0
                    continue
                
                # 가격 범위 설정
                price_min = np.min(recent_close)
                price_max = np.max(recent_close)
                
                if price_max == price_min or price_max <= 0:
                    poc[i] = close[i] if i < len(close) else price_min
                    continue
                
                # 가격대별 구간 생성 (안전한 bins 수)
                safe_bins = min(bins, len(recent_close) // 2 + 1)
                safe_bins = max(3, safe_bins)  # 최소 3개 bins
                
                price_bins = np.linspace(price_min, price_max, safe_bins + 1)
                volume_by_price = np.zeros(safe_bins)
                
                # 각 가격대별 거래량 집계
                for j in range(len(recent_close)):
                    price_idx = np.searchsorted(price_bins[:-1], recent_close[j], side='right') - 1
                    price_idx = max(0, min(price_idx, safe_bins - 1))
                    volume_by_price[price_idx] += recent_volume[j]
                
                # POC (가장 거래량이 많은 가격대)
                if len(volume_by_price) > 0:
                    max_volume_idx = np.argmax(volume_by_price)
                    if max_volume_idx < len(price_bins) - 1:
                        poc[i] = (price_bins[max_volume_idx] + price_bins[max_volume_idx + 1]) / 2
                    else:
                        poc[i] = price_bins[max_volume_idx]
                else:
                    poc[i] = close[i] if i < len(close) else price_min
                
                # 현재 가격과 POC의 비율
                volume_ratio[i] = close[i] / poc[i] if poc[i] > 0 else 1.0
                
                # Value Area (상위 70% 거래량 구간) - 단순화
                if np.sum(volume_by_price) > 0:
                    value_area[i] = 1.0 if volume_by_price[max_volume_idx] > np.mean(volume_by_price) else 0.0
                else:
                    value_area[i] = 0.0
                    
            except Exception as e:
                # 개별 계산 실패시 기본값 설정
                poc[i] = close[i] if i < len(close) else 0
                volume_ratio[i] = 1.0
                value_area[i] = 0.0
        
        return {
            'poc': poc,
            'volume_ratio': volume_ratio,
            'value_area': value_area
        }
    
    @staticmethod
    def calculate_advanced_momentum(close: np.ndarray, high: np.ndarray, low: np.ndarray, volume: np.ndarray) -> Dict[str, np.ndarray]:
        """
        고급 모멘텀 지표 조합
        Returns: {'composite_momentum': array, 'momentum_divergence': array, 'acceleration': array}
        """
        if len(close) < 30:
            return {
                'composite_momentum': np.zeros(len(close)),
                'momentum_divergence': np.zeros(len(close)),
                'acceleration': np.zeros(len(close))
            }
        
        # 1. Rate of Change (여러 기간)
        roc_5 = np.zeros(len(close))
        roc_10 = np.zeros(len(close))
        roc_20 = np.zeros(len(close))
        
        for i in range(20, len(close)):
            if i >= 5:
                roc_5[i] = (close[i] - close[i-5]) / close[i-5] * 100
            if i >= 10:
                roc_10[i] = (close[i] - close[i-10]) / close[i-10] * 100
            if i >= 20:
                roc_20[i] = (close[i] - close[i-20]) / close[i-20] * 100
        
        # 2. Volume-Weighted Momentum
        volume_ma = pd.Series(volume).rolling(20).mean().values
        volume_momentum = np.zeros(len(close))
        
        for i in range(20, len(close)):
            if volume_ma[i] > 0:
                volume_momentum[i] = roc_10[i] * (volume[i] / volume_ma[i])
        
        # 3. Composite Momentum (가중평균)
        composite_momentum = (roc_5 * 0.5 + roc_10 * 0.3 + roc_20 * 0.2)
        
        # 4. Momentum Divergence (가격과 모멘텀의 분기)
        momentum_divergence = np.zeros(len(close))
        lookback = 10
        
        for i in range(lookback + 20, len(close)):
            # 가격 추세
            price_change = close[i] - close[i-lookback]
            # 모멘텀 추세
            momentum_change = composite_momentum[i] - composite_momentum[i-lookback]
            
            # 분기 감지
            if price_change > 0 and momentum_change < 0:
                momentum_divergence[i] = -1  # 약세 분기
            elif price_change < 0 and momentum_change > 0:
                momentum_divergence[i] = 1   # 강세 분기
        
        # 5. Acceleration (모멘텀의 변화율)
        acceleration = np.zeros(len(close))
        for i in range(5, len(composite_momentum)):
            acceleration[i] = composite_momentum[i] - composite_momentum[i-5]
        
        return {
            'composite_momentum': composite_momentum,
            'momentum_divergence': momentum_divergence,
            'acceleration': acceleration
        }
    
    @staticmethod
    def calculate_adaptive_bands(close: np.ndarray, volume: np.ndarray, period: int = 20) -> Dict[str, np.ndarray]:
        """
        적응형 변동성 밴드 - 거래량 가중 볼린저 밴드
        Returns: {'upper': array, 'middle': array, 'lower': array, 'bandwidth': array, 'position': array}
        """
        if len(close) < period:
            return {
                'upper': close.copy(),
                'middle': close.copy(),
                'lower': close.copy(),
                'bandwidth': np.ones(len(close)),
                'position': np.full(len(close), 0.5)
            }
        
        # Volume-Weighted Moving Average (VWMA)
        vwma = np.zeros(len(close))
        volume_sum = np.zeros(len(close))
        
        for i in range(period-1, len(close)):
            price_volume_sum = 0
            vol_sum = 0
            
            for j in range(i-period+1, i+1):
                price_volume_sum += close[j] * volume[j]
                vol_sum += volume[j]
            
            if vol_sum > 0:
                vwma[i] = price_volume_sum / vol_sum
            else:
                vwma[i] = np.mean(close[i-period+1:i+1])
        
        # Adaptive Standard Deviation (거래량 가중)
        adaptive_std = np.zeros(len(close))
        
        for i in range(period-1, len(close)):
            weighted_variance = 0
            total_weight = 0
            mean_price = vwma[i]
            
            for j in range(i-period+1, i+1):
                weight = volume[j]
                weighted_variance += weight * (close[j] - mean_price) ** 2
                total_weight += weight
            
            if total_weight > 0:
                adaptive_std[i] = np.sqrt(weighted_variance / total_weight)
            else:
                adaptive_std[i] = np.std(close[i-period+1:i+1])
        
        # Adaptive Bands
        multiplier = 2.0
        upper = vwma + (adaptive_std * multiplier)
        lower = vwma - (adaptive_std * multiplier)
        
        # Bandwidth (변동성 측정)
        bandwidth = (upper - lower) / vwma
        bandwidth = np.where(vwma > 0, bandwidth, 1.0)
        
        # Position within bands (0-1)
        position = np.zeros(len(close))
        for i in range(len(close)):
            if upper[i] != lower[i]:
                position[i] = (close[i] - lower[i]) / (upper[i] - lower[i])
            else:
                position[i] = 0.5
        
        return {
            'upper': upper,
            'middle': vwma,
            'lower': lower,
            'bandwidth': bandwidth,
            'position': position
        }
    
    @staticmethod
    def calculate_market_structure(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> Dict[str, np.ndarray]:
        """
        시장 구조 분석 - Higher Highs, Lower Lows 패턴 감지
        Returns: {'structure_signal': array, 'swing_highs': array, 'swing_lows': array, 'trend_strength': array}
        """
        if len(close) < 20:
            return {
                'structure_signal': np.zeros(len(close)),
                'swing_highs': np.full(len(close), np.nan),
                'swing_lows': np.full(len(close), np.nan),
                'trend_strength': np.zeros(len(close))
            }
        
        # Swing High/Low 감지
        swing_highs = np.full(len(high), np.nan)
        swing_lows = np.full(len(low), np.nan)
        lookback = 5
        
        for i in range(lookback, len(high) - lookback):
            # Swing High 검사
            is_swing_high = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and high[j] >= high[i]:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                swing_highs[i] = high[i]
            
            # Swing Low 검사
            is_swing_low = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and low[j] <= low[i]:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                swing_lows[i] = low[i]
        
        # Market Structure Signal
        structure_signal = np.zeros(len(close))
        trend_strength = np.zeros(len(close))
        
        # 최근 swing points 분석
        analysis_period = 50
        
        for i in range(analysis_period, len(close)):
            recent_highs = []
            recent_lows = []
            
            # 최근 swing points 수집
            for j in range(i - analysis_period, i):
                if not np.isnan(swing_highs[j]):
                    recent_highs.append((j, swing_highs[j]))
                if not np.isnan(swing_lows[j]):
                    recent_lows.append((j, swing_lows[j]))
            
            if len(recent_highs) >= 2 and len(recent_lows) >= 2:
                # Higher Highs, Higher Lows 확인
                recent_highs.sort(key=lambda x: x[0])  # 시간순 정렬
                recent_lows.sort(key=lambda x: x[0])
                
                # 최근 2개 high/low 비교
                higher_highs = recent_highs[-1][1] > recent_highs[-2][1]
                higher_lows = recent_lows[-1][1] > recent_lows[-2][1]
                
                lower_highs = recent_highs[-1][1] < recent_highs[-2][1]
                lower_lows = recent_lows[-1][1] < recent_lows[-2][1]
                
                # 구조 신호 생성
                if higher_highs and higher_lows:
                    structure_signal[i] = 1.0  # 상승 구조
                    trend_strength[i] = 0.8
                elif lower_highs and lower_lows:
                    structure_signal[i] = -1.0  # 하락 구조
                    trend_strength[i] = 0.8
                elif higher_highs and lower_lows:
                    structure_signal[i] = 0.0  # 확장 구조 (변동성 증가)
                    trend_strength[i] = 0.3
                else:
                    structure_signal[i] = 0.0  # 중립
                    trend_strength[i] = 0.1
        
        return {
            'structure_signal': structure_signal,
            'swing_highs': swing_highs,
            'swing_lows': swing_lows,
            'trend_strength': trend_strength
        }
    
    @classmethod
    def calculate_all_indicators(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        모든 고급 지표를 한번에 계산 - 배열 크기 안전성 강화
        """
        if len(df) < 100:  # 최소 데이터 요구량 증가
            # 데이터 부족시 기본값으로 채움
            for col in ['macd', 'macd_signal', 'macd_histogram', 'macd_divergence',
                       'ichimoku_signal', 'tenkan_sen', 'kijun_sen',
                       'poc', 'volume_ratio', 'value_area',
                       'composite_momentum', 'momentum_divergence', 'momentum_acceleration',
                       'adaptive_upper', 'adaptive_middle', 'adaptive_lower', 
                       'adaptive_position', 'bandwidth',
                       'structure_signal', 'trend_strength']:
                df[col] = 0.0
            return df
        
        try:
            data_length = len(df)
            close = df['Close'].values
            high = df['High'].values
            low = df['Low'].values
            volume = df['Volume'].values
            
            # 배열 길이 검증
            arrays = [close, high, low, volume]
            min_length = min(len(arr) for arr in arrays)
            if min_length != data_length:
                print(f"배열 길이 불일치 감지: {[len(arr) for arr in arrays]}")
                # 최소 길이로 통일
                close = close[:min_length]
                high = high[:min_length]
                low = low[:min_length]
                volume = volume[:min_length]
                df = df.iloc[:min_length].copy()
            
            # 1. MACD Histogram
            macd_data = cls.calculate_macd_histogram(close)
            for key, values in macd_data.items():
                col_name = 'macd' if key == 'macd' else f'macd_{key}'
                if key == 'signal':
                    col_name = 'macd_signal'
                # 배열 길이 확인 후 할당
                if len(values) == len(df):
                    df[col_name] = values
                else:
                    print(f"MACD {key} 배열 길이 불일치: {len(values)} vs {len(df)}")
                    df[col_name] = np.pad(values, (0, max(0, len(df) - len(values))), 'constant')[:len(df)]
            
            # 2. Ichimoku Cloud
            ichimoku_data = cls.calculate_ichimoku_cloud(high, low, close)
            for key, values in ichimoku_data.items():
                col_name = f'ichimoku_signal' if key == 'cloud_signal' else key
                if key in ['tenkan', 'kijun']:
                    col_name = f'{key}_sen'
                # 배열 길이 확인 후 할당
                if len(values) == len(df):
                    df[col_name] = values
                else:
                    print(f"Ichimoku {key} 배열 길이 불일치: {len(values)} vs {len(df)}")
                    df[col_name] = np.pad(values, (0, max(0, len(df) - len(values))), 'constant')[:len(df)]
            
            # 3. Volume Profile  
            volume_data = cls.calculate_volume_profile(close, volume)
            for key, values in volume_data.items():
                # 배열 길이 확인 후 할당
                if len(values) == len(df):
                    df[key] = values
                else:
                    print(f"Volume Profile {key} 배열 길이 불일치: {len(values)} vs {len(df)}")
                    df[key] = np.pad(values, (0, max(0, len(df) - len(values))), 'constant')[:len(df)]
            
            # 4. Advanced Momentum
            momentum_data = cls.calculate_advanced_momentum(close, high, low, volume)
            for key, values in momentum_data.items():
                col_name = f'momentum_{key}' if key != 'composite_momentum' else key
                if key == 'acceleration':
                    col_name = 'momentum_acceleration'
                # 배열 길이 확인 후 할당
                if len(values) == len(df):
                    df[col_name] = values
                else:
                    print(f"Momentum {key} 배열 길이 불일치: {len(values)} vs {len(df)}")
                    df[col_name] = np.pad(values, (0, max(0, len(df) - len(values))), 'constant')[:len(df)]
            
            # 5. Adaptive Bands
            bands_data = cls.calculate_adaptive_bands(close, volume)
            for key, values in bands_data.items():
                col_name = f'adaptive_{key}' if key not in ['bandwidth'] else key
                # 배열 길이 확인 후 할당
                if len(values) == len(df):
                    df[col_name] = values
                else:
                    print(f"Adaptive Bands {key} 배열 길이 불일치: {len(values)} vs {len(df)}")
                    df[col_name] = np.pad(values, (0, max(0, len(df) - len(values))), 'constant')[:len(df)]
            
            # 6. Market Structure (안전성 강화 후 활성화)
            structure_data = cls.calculate_market_structure(high, low, close)
            for key, values in structure_data.items():
                if key not in ['swing_highs', 'swing_lows']:  # NaN 배열은 제외
                    # 배열 길이 확인 후 할당
                    if len(values) == len(df):
                        df[key] = values
                    else:
                        print(f"Market Structure {key} 배열 길이 불일치: {len(values)} vs {len(df)}")
                        df[key] = np.pad(values, (0, max(0, len(df) - len(values))), 'constant')[:len(df)]
            
        except Exception as e:
            print(f"고급 지표 계산 오류: {e}")
            import traceback
            traceback.print_exc()
        
        return df

# 편의 함수들
def add_advanced_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame에 모든 고급 지표 추가"""
    return AdvancedIndicators.calculate_all_indicators(df)

def get_signal_strength(df: pd.DataFrame, index: int) -> float:
    """특정 시점의 종합 신호 강도 계산"""
    if index >= len(df) or index < 0:
        return 0.0
    
    signals = []
    
    # MACD 신호
    if 'macd_histogram' in df.columns and not pd.isna(df.iloc[index]['macd_histogram']):
        if df.iloc[index]['macd_histogram'] > 0:
            signals.append(0.25)
    
    # Ichimoku 신호
    if 'ichimoku_signal' in df.columns and not pd.isna(df.iloc[index]['ichimoku_signal']):
        signals.append(df.iloc[index]['ichimoku_signal'] * 0.3)
    
    # Volume Profile 신호
    if 'value_area' in df.columns and not pd.isna(df.iloc[index]['value_area']):
        if df.iloc[index]['value_area'] > 0:
            signals.append(0.2)
    
    # Momentum 신호
    if 'composite_momentum' in df.columns and not pd.isna(df.iloc[index]['composite_momentum']):
        momentum = df.iloc[index]['composite_momentum']
        if momentum > 2:
            signals.append(0.25)
        elif momentum > 0:
            signals.append(0.1)
    
    return sum(signals) if signals else 0.0

if __name__ == "__main__":
    print("=== AdvancedIndicators 테스트 ===")
    
    # 샘플 데이터 생성
    np.random.seed(42)
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.random.rand(n) * 2
    low = close - np.random.rand(n) * 2
    volume = np.random.randint(1000, 10000, n)
    
    df = pd.DataFrame({
        'Close': close,
        'High': high,
        'Low': low,
        'Volume': volume
    })
    
    # 지표 계산
    df_with_indicators = add_advanced_indicators(df)
    
    print(f"원본 컬럼 수: {len(df.columns)}")
    print(f"지표 추가 후 컬럼 수: {len(df_with_indicators.columns)}")
    print("추가된 고급 지표들:")
    
    new_columns = [col for col in df_with_indicators.columns if col not in df.columns]
    for col in new_columns:
        print(f"  - {col}")
    
    # 마지막 신호 강도 확인
    last_signal = get_signal_strength(df_with_indicators, -1)
    print(f"마지막 시점 신호 강도: {last_signal:.3f}")
    
    print("=== 테스트 완료 ===")