"""
Enhanced David Paul Trading Algorithm
Basic_Algorithm.py + 데이비드 폴 거래량분석 로직 + 한국시장 특화

핵심 특징:
- Basic_Algorithm의 ATR 기반 적응형 리스크 관리
- 데이비드 폴 거래량 검증 vs 비검증 로직
- 한국 시장 매수 조건 완화 (높은 거래 빈도)
- 한국 VI(Volatility Interruption) 처리
- 거래량-가격 검증 및 발산 감지
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from pathlib import Path
import sys
from datetime import datetime, time as datetime_time

sys.path.append(str(Path(__file__).parent.parent))
from support.algorithm_interface import BaseAlgorithm

# 로깅 설정
import logging
from support.log_manager import get_log_manager

# 깔끔한 콘솔 로거 사용
from support.clean_console_logger import (
    get_clean_logger, Phase, log as clean_log
)

# 로그 매니저를 통한 로거 설정
log_manager = get_log_manager()
logger = log_manager.setup_logger('system', __name__)


# ========== 유틸리티 함수 ==========
def _ema(series: pd.Series, span: int) -> pd.Series:
    """지수이동평균 계산"""
    return series.ewm(span=span, adjust=False).mean()

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI 계산"""
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / (loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def _macd(series: pd.Series, fast=12, slow=26, signal=9):
    """MACD 계산"""
    macd = _ema(series, fast) - _ema(series, slow)
    sig = _ema(macd, signal)
    return macd, sig

def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    """Average True Range 계산"""
    tr = pd.concat([
        (high - low).abs(),
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()

def _vwap(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Volume Weighted Average Price 계산"""
    tp = (df['high'] + df['low'] + df['close']) / 3.0
    vol = df['volume'].fillna(0)
    num = (tp * vol).rolling(window).sum()
    den = vol.rolling(window).sum().replace(0, np.nan)
    vwap = (num / den).fillna(df['close'])
    return vwap

def _vma(series: pd.Series, period: int) -> pd.Series:
    """Volume Moving Average 계산"""
    return series.rolling(period).mean()

def _safe(val, default):
    """안전한 값 반환"""
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return val
    except Exception:
        return default


class EnhancedDavidPaulTrading(BaseAlgorithm):
    """Enhanced David Paul Trading Algorithm - 한국 시장 특화"""
    
    def __init__(self):
        super().__init__()
        self.algorithm_name = "Enhanced_DavidPaul_Trading"
        self.description = "David Paul Volume Analysis + Korean Market Tuned + VI Handling"
        self.version = "1.0"
        
        # ========== Basic Algorithm 기반 핵심 파라미터 ==========
        self.sma_short = 5
        self.sma_long = 20
        self.rsi_period = 14
        self.rsi_cap = 85          # 한국시장: RSI 상한 대폭 완화 (78→85)
        self.breakout_k = 0.20     # 돌파 기준 완화 (30%→20%)
        
        # ========== 데이비드 폴 거래량 분석 파라미터 ==========
        self.vma_period = 20              # VMA 기간
        self.david_paul_surge = 2.2       # 데이비드 폴 거래량 급증 기준 (2.2x VMA)
        self.validation_threshold = 1.8   # Validation 거래량 임계치 (완화)
        self.non_validation_max = 1.3     # Non-Validation 상한 (완화)
        
        # ========== 한국 시장 특화 파라미터 (매수 조건 완화) ==========
        self.vol_pulse_min = 1.05         # 거래량 펄스 대폭 완화 (1.10→1.05)
        self.vol_rank_min = 50.0          # 거래량 순위 완화 (60→50)
        self.momentum_threshold = 0.003   # 모멘텀 기준 완화 (0.6%→0.3%)
        
        # ========== ATR 기반 리스크 관리 ==========
        self.atr_period = 14
        self.k_sl1 = 0.8          # 손절 ATR 계수
        self.k_tp1 = 1.5          # 익절 ATR 계수 (1.2→1.5 상향)
        self.k_trail = 1.0        # 추격 스탑 ATR 계수
        
        # ========== 한국 VI 처리 파라미터 ==========
        self.vi_detection_enabled = True
        self.upward_vi_action = "BUY"     # 상승 VI: 홀딩/매수
        self.downward_vi_action = "SELL"  # 하락 VI: 즉시 매도
        
        # ========== 발산 감지 파라미터 ==========
        self.divergence_period = 10       # 발산 감지 기간
        self.price_volume_correlation_min = 0.3  # 가격-거래량 상관관계 최소값
        
        # ========== 내부 상태 ==========
        self.last_vi_status = None
        self.entry_prices = {}
        self.position_status = {}
        
        clean_log(f"Enhanced David Paul Trading 알고리즘 초기화: v{self.version}", "SUCCESS")
    
    def analyze(self, data: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """
        메인 분석 함수
        
        Args:
            data: OHLCV 데이터프레임
            **kwargs: 추가 파라미터 (stock_code, vi_status 등)
            
        Returns:
            Dict: 매매 신호 및 분석 결과
        """
        try:
            # 데이터 검증
            if not self._validate_data(data):
                return self._default_response("HOLD", 15, "insufficient data")
            
            df = data.copy()
            df.columns = [c.lower() for c in df.columns]
            
            # VI 상태 확인 (최우선)
            vi_status = kwargs.get('vi_status', None)
            if vi_status and self.vi_detection_enabled:
                vi_response = self._handle_vi_status(vi_status, df)
                if vi_response:
                    return vi_response
            
            # 기술적 지표 계산
            indicators = self._calculate_indicators(df)
            
            # 데이비드 폴 거래량 분석
            volume_analysis = self._david_paul_volume_analysis(df, indicators)
            
            # 발산 분석
            divergence_analysis = self._analyze_divergences(df, indicators)
            
            # 시장 상태 분석
            market_state = self._analyze_market_state(df, indicators, volume_analysis, divergence_analysis)
            
            # 매매 신호 생성
            signal_result = self._generate_trading_signal(df, indicators, market_state, volume_analysis)
            
            return signal_result
            
        except Exception as e:
            logger.error(f"Enhanced David Paul Trading 분석 오류: {e}")
            return self._default_response("HOLD", 10, f"Error: {e}")
    
    def _validate_data(self, data: pd.DataFrame) -> bool:
        """데이터 유효성 검증"""
        required_cols = {'open', 'high', 'low', 'close', 'volume'}
        if data is None or data.empty:
            return False
        
        data_cols = set(map(str.lower, data.columns.map(str)))
        return required_cols.issubset(data_cols) and len(data) >= self.sma_long
    
    def _handle_vi_status(self, vi_status: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """한국 VI(Volatility Interruption) 처리"""
        if not vi_status:
            return None
        
        current_price = float(df['close'].iloc[-1])
        
        # 상승 VI: 홀딩 또는 신규매수/추매
        if vi_status.upper() in ['UP_VI', 'UPWARD_VI', '상승VI']:
            logger.info("상승 VI 감지: 홀딩/매수 신호")
            return {
                'recommendation': self.upward_vi_action,
                'confidence': 95,
                'algorithm': self.algorithm_name,
                'note': "Korean Market: Upward VI detected - Hold/Buy signal",
                'extras': {
                    'vi_status': vi_status,
                    'vi_action': 'upward_vi_response',
                    'current_price': current_price
                }
            }
        
        # 하락 VI: 즉시 시장가 매도
        elif vi_status.upper() in ['DOWN_VI', 'DOWNWARD_VI', '하락VI']:
            logger.warning("하락 VI 감지: 즉시 매도 신호")
            return {
                'recommendation': self.downward_vi_action,
                'confidence': 98,
                'algorithm': self.algorithm_name,
                'note': "Korean Market: Downward VI detected - Immediate market sell",
                'extras': {
                    'vi_status': vi_status,
                    'vi_action': 'downward_vi_emergency_sell',
                    'current_price': current_price,
                    'urgent': True
                }
            }
        
        return None
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """기술적 지표 계산"""
        indicators = {}
        
        try:
            # 기본 이동평균
            indicators['sma_short'] = df['close'].rolling(self.sma_short).mean()
            indicators['sma_long'] = df['close'].rolling(self.sma_long).mean()
            
            # RSI
            indicators['rsi'] = _rsi(df['close'], self.rsi_period)
            
            # ATR (리스크 관리용)
            indicators['atr'] = _atr(df['high'], df['low'], df['close'], self.atr_period)
            
            # VWAP
            indicators['vwap'] = _vwap(df, 20)
            
            # MACD
            indicators['macd'], indicators['macd_signal'] = _macd(df['close'])
            
            # 거래량 분석
            indicators['vma'] = _vma(df['volume'], self.vma_period)
            indicators['volume_ratio'] = df['volume'] / indicators['vma']
            
            # 가격 모멘텀
            indicators['price_momentum'] = df['close'].pct_change(5)  # 5봉 모멘텀
            
            # 거래량-가격 상관관계
            indicators['volume_price_corr'] = df['close'].rolling(self.divergence_period).corr(
                df['volume'].rolling(self.divergence_period).mean()
            )
            
            return indicators
            
        except Exception as e:
            logger.error(f"지표 계산 오류: {e}")
            return {}
    
    def _david_paul_volume_analysis(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """데이비드 폴 거래량 분석 구현"""
        try:
            latest = df.iloc[-1]
            latest_volume_ratio = float(_safe(indicators['volume_ratio'].iloc[-1], 1.0))
            
            # 가격 레인지 계산
            price_range = (latest['high'] - latest['low']) / latest['close']
            avg_range = ((df['high'] - df['low']) / df['close']).rolling(20).mean().iloc[-1]
            range_expansion = price_range / _safe(avg_range, price_range) if avg_range > 0 else 1.0
            
            # 데이비드 폴 핵심 분류
            wide_range = range_expansion >= 1.2  # 레인지 확장
            high_volume = latest_volume_ratio >= self.david_paul_surge  # 2.2x VMA 이상
            
            # Validation vs Non-Validation 판정
            is_validation = wide_range and high_volume
            is_non_validation = wide_range and not high_volume
            
            # 거래량 강도 세분화
            volume_strength = "LOW"
            if latest_volume_ratio >= self.david_paul_surge:
                volume_strength = "SURGE"  # 급증
            elif latest_volume_ratio >= self.validation_threshold:
                volume_strength = "HIGH"   # 높음
            elif latest_volume_ratio >= self.non_validation_max:
                volume_strength = "MEDIUM" # 중간
            
            # 진정한 돌파 vs 가짜 돌파 판정
            price_breakout = latest['close'] > latest['open'] * 1.005  # 0.5% 이상 상승
            true_breakout = is_validation and price_breakout
            false_breakout = is_non_validation and price_breakout
            
            return {
                'is_validation': is_validation,
                'is_non_validation': is_non_validation,
                'volume_ratio': latest_volume_ratio,
                'volume_strength': volume_strength,
                'range_expansion': range_expansion,
                'wide_range': wide_range,
                'high_volume': high_volume,
                'true_breakout': true_breakout,
                'false_breakout': false_breakout,
                'david_paul_score': self._calculate_david_paul_score(
                    is_validation, volume_strength, range_expansion, true_breakout
                )
            }
            
        except Exception as e:
            logger.error(f"데이비드 폴 거래량 분석 오류: {e}")
            return {'david_paul_score': 0, 'is_validation': False}
    
    def _calculate_david_paul_score(self, is_validation: bool, volume_strength: str, 
                                   range_expansion: float, true_breakout: bool) -> float:
        """데이비드 폴 점수 계산"""
        score = 0.0
        
        # Validation 보너스
        if is_validation:
            score += 40.0
        
        # 거래량 강도별 점수
        volume_scores = {"SURGE": 30.0, "HIGH": 20.0, "MEDIUM": 10.0, "LOW": 0.0}
        score += volume_scores.get(volume_strength, 0.0)
        
        # 레인지 확장 점수
        score += min(20.0, range_expansion * 10.0)
        
        # 진정한 돌파 보너스
        if true_breakout:
            score += 15.0
        
        return min(100.0, score)
    
    def _analyze_divergences(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """발산 분석"""
        try:
            # 가격-거래량 발산 감지
            price_trend = df['close'].rolling(self.divergence_period).apply(
                lambda x: 1 if x.iloc[-1] > x.iloc[0] else -1
            ).iloc[-1]
            
            volume_trend = df['volume'].rolling(self.divergence_period).apply(
                lambda x: 1 if x.iloc[-1] > x.iloc[0] else -1
            ).iloc[-1]
            
            # 발산 유형 분류
            bullish_divergence = (price_trend < 0) and (volume_trend > 0)  # 가격↓, 거래량↑
            bearish_divergence = (price_trend > 0) and (volume_trend < 0)  # 가격↑, 거래량↓
            convergence = price_trend == volume_trend  # 동일 방향
            
            # 상관관계 강도
            correlation = float(_safe(indicators['volume_price_corr'].iloc[-1], 0.0))
            strong_correlation = abs(correlation) >= self.price_volume_correlation_min
            
            return {
                'bullish_divergence': bullish_divergence,
                'bearish_divergence': bearish_divergence,
                'convergence': convergence,
                'price_volume_correlation': correlation,
                'strong_correlation': strong_correlation,
                'divergence_signal_strength': self._calculate_divergence_strength(
                    bullish_divergence, bearish_divergence, correlation
                )
            }
            
        except Exception as e:
            logger.error(f"발산 분석 오류: {e}")
            return {'divergence_signal_strength': 0}
    
    def _calculate_divergence_strength(self, bullish_div: bool, bearish_div: bool, correlation: float) -> float:
        """발산 신호 강도 계산"""
        strength = 0.0
        
        if bullish_div:
            strength += 25.0  # 강세 발산
        elif bearish_div:
            strength -= 25.0  # 약세 발산
        
        # 상관관계 강도 반영
        strength += abs(correlation) * 20.0
        
        return max(-50.0, min(50.0, strength))
    
    def _analyze_market_state(self, df: pd.DataFrame, indicators: Dict[str, Any], 
                             volume_analysis: Dict[str, Any], divergence_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """시장 상태 종합 분석"""
        latest = df.iloc[-1]
        
        # 기본 상태
        sma_bullish = float(_safe(indicators['sma_short'].iloc[-1], 0)) > float(_safe(indicators['sma_long'].iloc[-1], 0))
        rsi_value = float(_safe(indicators['rsi'].iloc[-1], 50))
        rsi_acceptable = rsi_value <= self.rsi_cap  # 한국시장: RSI 85까지 허용
        
        # VWAP 및 지지선
        above_vwap = latest['close'] >= float(_safe(indicators['vwap'].iloc[-1], latest['close']))
        above_support = latest['close'] >= max(
            float(_safe(indicators['sma_short'].iloc[-1], latest['close'])),
            float(_safe(indicators['vwap'].iloc[-1], latest['close']))
        )
        
        # 모멘텀 (완화된 기준)
        momentum = float(_safe(indicators['price_momentum'].iloc[-1], 0))
        positive_momentum = momentum >= self.momentum_threshold  # 0.3% 이상
        
        # 거래량 조건 (완화)
        volume_ratio = volume_analysis.get('volume_ratio', 1.0)
        volume_acceptable = volume_ratio >= self.vol_pulse_min  # 1.05배 이상
        
        # MACD
        macd_bullish = float(_safe(indicators['macd'].iloc[-1], 0)) > float(_safe(indicators['macd_signal'].iloc[-1], 0))
        
        return {
            'sma_bullish': sma_bullish,
            'rsi_value': rsi_value,
            'rsi_acceptable': rsi_acceptable,
            'above_vwap': above_vwap,
            'above_support': above_support,
            'positive_momentum': positive_momentum,
            'volume_acceptable': volume_acceptable,
            'macd_bullish': macd_bullish,
            'current_price': float(latest['close']),
            'atr_value': float(_safe(indicators['atr'].iloc[-1], 0))
        }
    
    def _generate_trading_signal(self, df: pd.DataFrame, indicators: Dict[str, Any], 
                                market_state: Dict[str, Any], volume_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """매매 신호 생성"""
        
        # ========== 매수 조건 (한국시장 특화 - 완화된 조건) ==========
        buy_conditions = []
        
        # 1. 데이비드 폴 Validation (높은 가중치)
        if volume_analysis.get('is_validation', False):
            buy_conditions.append(('david_paul_validation', 3.0))
        
        # 2. 거래량 급증 (완화된 기준)
        if volume_analysis.get('volume_strength') in ['SURGE', 'HIGH']:
            buy_conditions.append(('volume_surge', 2.5))
        
        # 3. 진정한 돌파
        if volume_analysis.get('true_breakout', False):
            buy_conditions.append(('true_breakout', 2.0))
        
        # 4. 기술적 조건들 (완화)
        if market_state.get('sma_bullish', False):
            buy_conditions.append(('sma_trend', 1.5))
        
        if market_state.get('rsi_acceptable', False):  # RSI 85 이하
            buy_conditions.append(('rsi_ok', 1.5))
        
        if market_state.get('above_support', False):
            buy_conditions.append(('support_level', 1.5))
        
        if market_state.get('positive_momentum', False):  # 0.3% 이상
            buy_conditions.append(('momentum', 1.0))
        
        if market_state.get('macd_bullish', False):
            buy_conditions.append(('macd_signal', 1.0))
        
        if market_state.get('volume_acceptable', False):  # 1.05배 이상
            buy_conditions.append(('volume_flow', 1.0))
        
        # ========== 매도 조건 ==========
        sell_conditions = []
        
        # 1. Non-Validation (가짜 돌파)
        if volume_analysis.get('false_breakout', False):
            sell_conditions.append(('false_breakout', 2.5))
        
        # 2. 기술적 약화
        if not market_state.get('sma_bullish', True):
            sell_conditions.append(('trend_weak', 2.0))
        
        if market_state.get('rsi_value', 50) > 90:  # 극도 과매수
            sell_conditions.append(('extreme_overbought', 2.0))
        
        if not market_state.get('macd_bullish', True):
            sell_conditions.append(('macd_bearish', 1.5))
        
        # ========== 신호 계산 ==========
        buy_score = sum(weight for _, weight in buy_conditions)
        sell_score = sum(weight for _, weight in sell_conditions)
        
        # 데이비드 폴 점수 반영
        david_paul_score = volume_analysis.get('david_paul_score', 0)
        buy_score += david_paul_score * 0.05  # 0-5점 추가
        
        # ========== 최종 신호 결정 (한국시장: 더 쉬운 매수) ==========
        if buy_score >= 4.0 and sell_score <= 1.5:  # 매수 임계치 낮춤
            confidence = min(95, 60 + int(buy_score * 5) + int(david_paul_score * 0.3))
            
            # ATR 기반 리스크 힌트
            atr = market_state.get('atr_value', 0)
            current_price = market_state.get('current_price', 0)
            risk_hint = self._calculate_risk_levels(current_price, atr)
            
            return {
                'recommendation': 'BUY',
                'confidence': confidence,
                'algorithm': self.algorithm_name,
                'note': f"Enhanced David Paul BUY: score={buy_score:.1f}, validation={volume_analysis.get('is_validation', False)}",
                'extras': {
                    'buy_score': buy_score,
                    'sell_score': sell_score,
                    'david_paul_score': david_paul_score,
                    'volume_analysis': volume_analysis,
                    'risk_hint': risk_hint,
                    'buy_conditions': [cond for cond, _ in buy_conditions]
                }
            }
        
        elif sell_score >= 2.0 or buy_score <= 1.0:
            confidence = min(90, 50 + int(sell_score * 8))
            
            return {
                'recommendation': 'SELL',
                'confidence': confidence,
                'algorithm': self.algorithm_name,
                'note': f"Enhanced David Paul SELL: sell_score={sell_score:.1f}, buy_score={buy_score:.1f}",
                'extras': {
                    'buy_score': buy_score,
                    'sell_score': sell_score,
                    'sell_conditions': [cond for cond, _ in sell_conditions]
                }
            }
        
        else:
            return {
                'recommendation': 'HOLD',
                'confidence': 45,
                'algorithm': self.algorithm_name,
                'note': f"Enhanced David Paul HOLD: buy={buy_score:.1f}, sell={sell_score:.1f}",
                'extras': {
                    'buy_score': buy_score,
                    'sell_score': sell_score,
                    'david_paul_score': david_paul_score
                }
            }
    
    def _calculate_risk_levels(self, current_price: float, atr: float) -> Dict[str, float]:
        """ATR 기반 리스크 레벨 계산"""
        if atr <= 0:
            atr = current_price * 0.01  # 1% 기본값
        
        return {
            'atr': atr,
            'stop_loss': current_price - (self.k_sl1 * atr),
            'take_profit': current_price + (self.k_tp1 * atr),
            'trail_stop': current_price - (self.k_trail * atr)
        }
    
    def _default_response(self, recommendation: str, confidence: int, note: str) -> Dict[str, Any]:
        """기본 응답 생성"""
        return {
            'recommendation': recommendation,
            'confidence': confidence,
            'algorithm': self.algorithm_name,
            'note': note,
            'extras': {}
        }
    
    # ========== BaseAlgorithm 인터페이스 구현 ==========
    def get_name(self) -> str:
        return self.algorithm_name
    
    def get_description(self) -> str:
        return self.description
    
    def get_version(self) -> str:
        return self.version
    
    def calculate_position_size(self, current_price: float, account_balance: float) -> int:
        """포지션 크기 계산"""
        try:
            # 계좌의 10% 기본 할당
            position_value = account_balance * 0.1
            quantity = int(position_value / current_price)
            return max(1, quantity) if position_value >= current_price else 0
        except Exception:
            return 0
    
    def get_stop_loss(self, entry_price: float, position_type: str = 'LONG') -> float:
        """손절가 계산"""
        atr_estimate = entry_price * 0.01  # 기본 ATR 추정치
        if position_type == 'LONG':
            return entry_price - (self.k_sl1 * atr_estimate)
        else:
            return entry_price + (self.k_sl1 * atr_estimate)
    
    def get_take_profit(self, entry_price: float, position_type: str = 'LONG') -> float:
        """익절가 계산"""
        atr_estimate = entry_price * 0.01  # 기본 ATR 추정치
        if position_type == 'LONG':
            return entry_price + (self.k_tp1 * atr_estimate)
        else:
            return entry_price - (self.k_tp1 * atr_estimate)


# ========== 편의 함수 ==========
def create_enhanced_david_paul_algorithm() -> EnhancedDavidPaulTrading:
    """Enhanced David Paul Trading 알고리즘 인스턴스 생성"""
    return EnhancedDavidPaulTrading()


# ========== 테스트 코드 ==========
if __name__ == "__main__":
    # 테스트 실행
    algorithm = create_enhanced_david_paul_algorithm()
    
    # 테스트 데이터 생성
    test_data = pd.DataFrame({
        'open': np.random.randn(50).cumsum() + 100,
        'high': np.random.randn(50).cumsum() + 102,
        'low': np.random.randn(50).cumsum() + 98,
        'close': np.random.randn(50).cumsum() + 100,
        'volume': np.random.randint(1000, 10000, 50)
    })
    
    # 분석 테스트
    result = algorithm.analyze(test_data, stock_code="TEST001")
    
    print("=" * 60)
    print(f"Enhanced David Paul Trading 테스트 결과:")
    print(f"알고리즘: {algorithm.get_name()} v{algorithm.get_version()}")
    print(f"설명: {algorithm.get_description()}")
    print(f"신호: {result['recommendation']}")
    print(f"신뢰도: {result['confidence']}%")
    print(f"노트: {result['note']}")
    print("=" * 60)
    
    # VI 처리 테스트
    vi_test_result = algorithm.analyze(test_data, vi_status="UP_VI")
    print(f"VI 테스트 (상승 VI): {vi_test_result['recommendation']} ({vi_test_result['confidence']}%)")
    
    vi_test_result2 = algorithm.analyze(test_data, vi_status="DOWN_VI")
    print(f"VI 테스트 (하락 VI): {vi_test_result2['recommendation']} ({vi_test_result2['confidence']}%)")