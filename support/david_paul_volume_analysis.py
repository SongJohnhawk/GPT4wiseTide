"""
데이비드 폴 거래량 분석 기법 구현
Validation vs Non-Validation 원리 적용
"""

# pandas와 numpy 조건부 import
try:
    import pandas as pd
except ImportError:
    print("WARNING: pandas가 설치되지 않았습니다.")
    pd = None

try:
    import numpy as np
except ImportError:
    print("WARNING: NumPy가 설치되지 않았습니다.")
    np = None
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class DavidPaulVolumeAnalysis:
    """데이비드 폴의 거래량 분석 기법 구현 클래스"""
    
    def __init__(self):
        # DP 방식 매개변수 (파일 기준)
        self.volume_ma_length = 20          # 거래량 이동평균 기간
        self.range_ma_length = 20           # 변동폭 이동평균 기간  
        self.volume_multiplier = 2.2        # 거래량 급증 기준 (평균 × 2.2)
        self.range_multiplier = 1.5         # 변동폭 확대 기준 (평균 × 1.5)
        self.divergence_lookback = 60       # 다이버전스 분석 기간
        
        # 기울기 분석 매개변수
        self.slope_period = 5               # 기울기 계산 기간
        
    def analyze_validation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validation vs Non-Validation 분석"""
        try:
            if len(df) < max(self.volume_ma_length, self.range_ma_length):
                return self._get_safe_result()
            
            # 기본 계산
            df_copy = df.copy()
            df_copy['range'] = df_copy['high'] - df_copy['low']
            
            # 이동평균 계산
            df_copy['volume_ma'] = df_copy['volume'].rolling(window=self.volume_ma_length).mean()
            df_copy['range_ma'] = df_copy['range'].rolling(window=self.range_ma_length).mean()
            
            # 현재값
            current_volume = df_copy['volume'].iloc[-1]
            current_range = df_copy['range'].iloc[-1]
            current_volume_ma = df_copy['volume_ma'].iloc[-1]
            current_range_ma = df_copy['range_ma'].iloc[-1]
            
            # Spike 조건
            volume_spike = current_volume >= (self.volume_multiplier * current_volume_ma)
            wide_range = current_range >= (self.range_multiplier * current_range_ma)
            
            # DP 핵심: Validation vs Non-Validation
            validation = wide_range and volume_spike           # 진짜 힘
            non_validation = wide_range and (current_volume < current_volume_ma)  # 가짜 신호
            
            # 기울기 분석 (다이버전스)
            price_slope, volume_slope = self._calculate_slopes(df_copy)
            rise_on_falling_volume = price_slope > 0 and volume_slope < 0  # 위험 신호
            fall_on_rising_volume = price_slope < 0 and volume_slope > 0   # 반전 신호
            
            # True Breakout 분석
            true_breakout = self._analyze_true_breakout(df_copy, volume_spike)
            
            # 다이버전스 분석
            divergence_analysis = self._analyze_divergences(df_copy)
            
            return {
                'validation': validation,
                'non_validation': non_validation,
                'volume_spike': volume_spike,
                'wide_range': wide_range,
                'volume_ratio': current_volume / current_volume_ma if current_volume_ma > 0 else 1.0,
                'range_ratio': current_range / current_range_ma if current_range_ma > 0 else 1.0,
                'rise_on_falling_volume': rise_on_falling_volume,
                'fall_on_rising_volume': fall_on_rising_volume,
                'true_breakout': true_breakout,
                'price_slope': price_slope,
                'volume_slope': volume_slope,
                'divergence': divergence_analysis
            }
            
        except Exception as e:
            logger.error(f"DP 거래량 분석 오류: {e}")
            return self._get_safe_result()
    
    def _calculate_slopes(self, df: pd.DataFrame) -> Tuple[float, float]:
        """가격과 거래량의 기울기 계산"""
        try:
            if len(df) < self.slope_period:
                return 0.0, 0.0
            
            # 최근 N개 캔들의 선형 회귀 기울기
            recent_data = df.tail(self.slope_period)
            x = np.arange(len(recent_data))
            
            # 가격 기울기 (종가 기준)
            price_coef = np.polyfit(x, recent_data['close'], 1)[0]
            
            # 거래량 기울기
            volume_coef = np.polyfit(x, recent_data['volume'], 1)[0]
            
            return float(price_coef), float(volume_coef)
            
        except Exception:
            return 0.0, 0.0
    
    def _analyze_true_breakout(self, df: pd.DataFrame, volume_spike: bool) -> Dict[str, Any]:
        """True Breakout 분석 (DP 방식)"""
        try:
            current_close = df['close'].iloc[-1]
            
            # 최근 고점 (20개 캔들)
            lookback_period = min(20, len(df) - 1)
            swing_high = df['high'].iloc[-lookback_period:].max()
            
            # EMA 계산
            ema5 = df['close'].ewm(span=5).mean().iloc[-1]
            ema20 = df['close'].ewm(span=20).mean().iloc[-1]
            
            # VWAP 계산 (간소화)
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            vwap = (typical_price * df['volume']).sum() / df['volume'].sum()
            
            # True Breakout 조건 (DP 방식)
            price_breakout = current_close > swing_high
            trend_alignment = ema5 > ema20
            above_vwap = current_close > vwap
            
            true_breakout = volume_spike and price_breakout and trend_alignment and above_vwap
            
            return {
                'is_true_breakout': true_breakout,
                'price_breakout': price_breakout,
                'trend_alignment': trend_alignment,
                'above_vwap': above_vwap,
                'swing_high': swing_high,
                'ema5': ema5,
                'ema20': ema20,
                'vwap': vwap
            }
            
        except Exception:
            return {
                'is_true_breakout': False,
                'price_breakout': False,
                'trend_alignment': False,
                'above_vwap': False,
                'swing_high': 0,
                'ema5': 0,
                'ema20': 0,
                'vwap': 0
            }
    
    def _analyze_divergences(self, df: pd.DataFrame) -> Dict[str, Any]:
        """다이버전스 분석"""
        try:
            # 간단한 피벗 분석
            lookback = min(5, len(df) // 4)
            
            if len(df) < lookback * 3:
                return {'bearish_divergence': False, 'bullish_divergence': False}
            
            # 최근 고점/저점 찾기
            recent_highs = []
            recent_lows = []
            recent_vol_highs = []
            recent_vol_lows = []
            
            for i in range(lookback, len(df) - lookback):
                # 가격 피벗
                if all(df['high'].iloc[i] >= df['high'].iloc[i-j] for j in range(1, lookback+1)) and \
                   all(df['high'].iloc[i] >= df['high'].iloc[i+j] for j in range(1, lookback+1)):
                    recent_highs.append((i, df['high'].iloc[i]))
                
                if all(df['low'].iloc[i] <= df['low'].iloc[i-j] for j in range(1, lookback+1)) and \
                   all(df['low'].iloc[i] <= df['low'].iloc[i+j] for j in range(1, lookback+1)):
                    recent_lows.append((i, df['low'].iloc[i]))
                
                # 거래량 피벗
                if all(df['volume'].iloc[i] >= df['volume'].iloc[i-j] for j in range(1, lookback+1)) and \
                   all(df['volume'].iloc[i] >= df['volume'].iloc[i+j] for j in range(1, lookback+1)):
                    recent_vol_highs.append((i, df['volume'].iloc[i]))
                
                if all(df['volume'].iloc[i] <= df['volume'].iloc[i-j] for j in range(1, lookback+1)) and \
                   all(df['volume'].iloc[i] <= df['volume'].iloc[i+j] for j in range(1, lookback+1)):
                    recent_vol_lows.append((i, df['volume'].iloc[i]))
            
            # 다이버전스 확인
            bearish_div = False
            bullish_div = False
            
            if len(recent_highs) >= 2 and len(recent_vol_highs) >= 2:
                last_price_high = recent_highs[-1][1]
                prev_price_high = recent_highs[-2][1]
                last_vol_high = recent_vol_highs[-1][1] 
                prev_vol_high = recent_vol_highs[-2][1]
                
                # 약세 다이버전스: 가격 고점↑, 거래량 고점↓
                if last_price_high > prev_price_high and last_vol_high < prev_vol_high:
                    bearish_div = True
            
            if len(recent_lows) >= 2 and len(recent_vol_lows) >= 2:
                last_price_low = recent_lows[-1][1]
                prev_price_low = recent_lows[-2][1]
                last_vol_low = recent_vol_lows[-1][1]
                prev_vol_low = recent_vol_lows[-2][1]
                
                # 강세 다이버전스: 가격 저점↓, 거래량 저점↑
                if last_price_low < prev_price_low and last_vol_low > prev_vol_low:
                    bullish_div = True
            
            return {
                'bearish_divergence': bearish_div,
                'bullish_divergence': bullish_div,
                'price_highs_count': len(recent_highs),
                'price_lows_count': len(recent_lows),
                'volume_highs_count': len(recent_vol_highs),
                'volume_lows_count': len(recent_vol_lows)
            }
            
        except Exception:
            return {
                'bearish_divergence': False,
                'bullish_divergence': False,
                'price_highs_count': 0,
                'price_lows_count': 0,
                'volume_highs_count': 0,
                'volume_lows_count': 0
            }
    
    def generate_trading_signal(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """DP 분석 기반 매매 신호 생성"""
        try:
            signal = 'HOLD'
            confidence = 50
            reason = ""
            
            # 강력한 매수 신호 (True Breakout)
            if analysis['true_breakout']['is_true_breakout']:
                signal = 'BUY'
                confidence = 95
                reason = "DP True Breakout: 거래량 검증된 돌파"
            
            # 검증된 상승 (Validation)
            elif analysis['validation'] and not analysis['rise_on_falling_volume']:
                signal = 'BUY'
                confidence = 85
                reason = "DP Validation: 대량거래 + 넓은 변동폭"
            
            # 강세 다이버전스
            elif analysis['divergence']['bullish_divergence']:
                signal = 'BUY'
                confidence = 75
                reason = "DP 강세 다이버전스: 가격↓ 거래량↑"
            
            # 위험 신호들 (매도)
            elif analysis['non_validation']:
                signal = 'SELL'
                confidence = 80
                reason = "DP Non-Validation: 가짜 신호 의심"
            
            elif analysis['rise_on_falling_volume']:
                signal = 'SELL'  
                confidence = 85
                reason = "DP 위험신호: 상승 중 거래량 감소"
            
            elif analysis['divergence']['bearish_divergence']:
                signal = 'SELL'
                confidence = 90
                reason = "DP 약세 다이버전스: 가격↑ 거래량↓"
            
            return {
                'signal': signal,
                'confidence': confidence,
                'reason': reason,
                'validation_score': self._calculate_validation_score(analysis)
            }
            
        except Exception as e:
            logger.error(f"DP 신호 생성 오류: {e}")
            return {
                'signal': 'HOLD',
                'confidence': 30,
                'reason': f"분석 오류: {str(e)}",
                'validation_score': 0
            }
    
    def _calculate_validation_score(self, analysis: Dict[str, Any]) -> float:
        """검증 점수 계산 (0-100)"""
        try:
            score = 50  # 기본 점수
            
            # 긍정 요소
            if analysis['validation']:
                score += 20
            if analysis['true_breakout']['is_true_breakout']:
                score += 25  
            if analysis['divergence']['bullish_divergence']:
                score += 15
            if analysis['fall_on_rising_volume']:
                score += 10
            
            # 부정 요소  
            if analysis['non_validation']:
                score -= 25
            if analysis['rise_on_falling_volume']:
                score -= 20
            if analysis['divergence']['bearish_divergence']:
                score -= 30
            
            return max(0, min(100, score))
            
        except Exception:
            return 50
    
    def _get_safe_result(self) -> Dict[str, Any]:
        """안전한 기본 결과"""
        return {
            'validation': False,
            'non_validation': False,
            'volume_spike': False,
            'wide_range': False,
            'volume_ratio': 1.0,
            'range_ratio': 1.0,
            'rise_on_falling_volume': False,
            'fall_on_rising_volume': False,
            'true_breakout': {
                'is_true_breakout': False,
                'price_breakout': False,
                'trend_alignment': False,
                'above_vwap': False
            },
            'price_slope': 0.0,
            'volume_slope': 0.0,
            'divergence': {
                'bearish_divergence': False,
                'bullish_divergence': False
            }
        }

# 전역 인스턴스
_dp_analyzer = None

def get_david_paul_analyzer():
    """데이비드 폴 분석기 싱글톤 인스턴스 반환"""
    global _dp_analyzer
    if _dp_analyzer is None:
        _dp_analyzer = DavidPaulVolumeAnalysis()
    return _dp_analyzer