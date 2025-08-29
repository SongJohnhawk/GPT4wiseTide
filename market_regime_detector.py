#!/usr/bin/env python3
"""
[opt][algo][ai] 시장 상황별 적응형 시스템
- 고급 시장 상황 감지 (Bull/Bear/Sideways/High-Vol/Crisis)
- 리스크 온/오프 모드 자동 전환
- 동적 매개변수 조정 알고리즘
- 15% 목표 수익률 달성을 위한 정밀 시장 분석
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

class MarketRegime(Enum):
    """시장 상황 분류"""
    BULL_MARKET = "bull_market"      # 강세장
    BEAR_MARKET = "bear_market"      # 약세장  
    SIDEWAYS = "sideways"            # 횡보장
    HIGH_VOLATILITY = "high_vol"     # 고변동성
    CRISIS = "crisis"                # 위기 상황
    RECOVERY = "recovery"            # 회복 구간

class RiskMode(Enum):
    """리스크 모드"""
    RISK_ON = "risk_on"              # 위험 자산 선호
    RISK_OFF = "risk_off"            # 안전 자산 선호
    NEUTRAL = "neutral"              # 중립

class AdvancedMarketRegimeDetector:
    """고급 시장 상황 감지 시스템"""
    
    def __init__(self):
        # 분석 기간 설정
        self.short_period = 5          # 단기 추세 (5일)
        self.medium_period = 20        # 중기 추세 (20일)
        self.long_period = 60          # 장기 추세 (60일)
        self.volatility_period = 20    # 변동성 계산 기간
        
        # 임계값 설정
        self.bull_threshold = 0.03     # 상승장 판단 임계값 (3%)
        self.bear_threshold = -0.03    # 하락장 판단 임계값 (-3%)
        self.high_vol_threshold = 0.4  # 고변동성 임계값 (40%)
        self.crisis_vol_threshold = 0.8 # 위기상황 변동성 임계값 (80%)
        self.volume_surge_threshold = 2.0  # 거래량 급증 임계값 (200%)
        
        # 상황별 매개변수 템플릿
        self.regime_parameters = {
            MarketRegime.BULL_MARKET: {
                'signal_weights': [0.5, 0.05, 0.4, 0.05],  # 추세(50%)+모멘텀(40%) = 90%
                'position_multiplier': 1.5,                 # 포지션 50% 확대 (수익 극대화)
                'stop_loss_multiplier': 0.8,                # 손절 20% 완화 (2% → 1.6%)
                'take_profit_multiplier': 1.5,              # 익절 50% 확대 (10% → 15%)
                'confidence_threshold': 0.60,               # 신뢰도 60% (적극적 매수)
                'hold_days_multiplier': 1.5                 # 보유기간 50% 연장 (추세 활용)
            },
            MarketRegime.BEAR_MARKET: {
                'signal_weights': [0.2, 0.5, 0.1, 0.2],  # 평균회귀 강화
                'position_multiplier': 0.6,               # 포지션 40% 축소
                'stop_loss_multiplier': 0.7,              # 손절 30% 강화
                'take_profit_multiplier': 0.8,            # 익절 20% 축소 (빠른 확정)
                'confidence_threshold': 0.85,             # 신뢰도 85% (매우 엄격)
                'hold_days_multiplier': 0.6               # 보유기간 40% 단축
            },
            MarketRegime.SIDEWAYS: {
                'signal_weights': [0.2, 0.3, 0.2, 0.3],  # 균형 배치
                'position_multiplier': 0.8,               # 포지션 20% 축소
                'stop_loss_multiplier': 1.0,              # 손절 기본
                'take_profit_multiplier': 1.0,            # 익절 기본
                'confidence_threshold': 0.75,             # 신뢰도 75%
                'hold_days_multiplier': 0.8               # 보유기간 20% 단축
            },
            MarketRegime.HIGH_VOLATILITY: {
                'signal_weights': [0.1, 0.2, 0.2, 0.5],  # 변동성 신호 강화
                'position_multiplier': 0.5,               # 포지션 50% 축소
                'stop_loss_multiplier': 1.3,              # 손절 30% 확대 (변동성 대응)
                'take_profit_multiplier': 1.5,            # 익절 50% 확대 (큰 움직임 활용)
                'confidence_threshold': 0.80,             # 신뢰도 80%
                'hold_days_multiplier': 0.5               # 보유기간 50% 단축
            },
            MarketRegime.CRISIS: {
                'signal_weights': [0.1, 0.6, 0.1, 0.2],  # 평균회귀 최대 강화
                'position_multiplier': 0.3,               # 포지션 70% 축소 (최소화)
                'stop_loss_multiplier': 0.5,              # 손절 50% 강화 (빠른 손절)
                'take_profit_multiplier': 0.6,            # 익절 40% 축소 (빠른 확정)
                'confidence_threshold': 0.90,             # 신뢰도 90% (극도로 엄격)
                'hold_days_multiplier': 0.3               # 보유기간 70% 단축
            },
            MarketRegime.RECOVERY: {
                'signal_weights': [0.3, 0.2, 0.3, 0.2],  # 추세+모멘텀 중간 강화
                'position_multiplier': 1.0,               # 포지션 기본
                'stop_loss_multiplier': 0.8,              # 손절 20% 완화
                'take_profit_multiplier': 1.2,            # 익절 20% 확대
                'confidence_threshold': 0.75,             # 신뢰도 75%
                'hold_days_multiplier': 1.1               # 보유기간 10% 연장
            }
        }
        
        # 이력 저장
        self.regime_history = []
        self.risk_mode_history = []
        
    def calculate_trend_strength(self, prices: np.ndarray, period: int) -> float:
        """추세 강도 계산"""
        if len(prices) < period:
            return 0.0
        
        recent_prices = prices[-period:]
        
        # 선형 회귀를 통한 추세 기울기 계산
        x = np.arange(len(recent_prices))
        slope = np.polyfit(x, recent_prices, 1)[0]
        
        # 가격 대비 정규화
        price_range = np.max(recent_prices) - np.min(recent_prices)
        if price_range > 0:
            normalized_slope = slope / (np.mean(recent_prices) / period)
        else:
            normalized_slope = 0.0
            
        return normalized_slope
    
    def calculate_volatility_metrics(self, prices: np.ndarray, period: int) -> Dict[str, float]:
        """변동성 지표 계산"""
        if len(prices) < period + 1:
            return {'volatility': 0.0, 'volatility_percentile': 0.5, 'volatility_regime': 'normal'}
        
        # 수익률 계산
        returns = np.diff(prices[-period-1:]) / prices[-period-1:-1]
        
        # 현재 변동성 (연환산)
        current_volatility = np.std(returns) * np.sqrt(252)
        
        # 장기 변동성과 비교 (60일)
        if len(prices) >= 60:
            long_returns = np.diff(prices[-61:]) / prices[-61:-1]
            long_volatility = np.std(long_returns) * np.sqrt(252)
            volatility_ratio = current_volatility / long_volatility if long_volatility > 0 else 1.0
        else:
            volatility_ratio = 1.0
        
        # 변동성 백분위수 계산 (최근 100일 기준) - 배열 안전성 강화
        if len(prices) >= 100:
            vol_history = []
            for i in range(period, min(100, len(prices) - period - 1)):
                try:
                    start_idx = max(0, len(prices) - i - period)
                    end_idx = max(1, len(prices) - i)
                    
                    if end_idx <= start_idx or end_idx >= len(prices):
                        continue
                        
                    price_slice = prices[start_idx:end_idx]
                    denominator_slice = prices[start_idx:end_idx-1]
                    
                    if len(price_slice) != len(denominator_slice) + 1:
                        continue
                        
                    hist_returns = np.diff(price_slice) / denominator_slice
                    if len(hist_returns) > 0:
                        vol_history.append(np.std(hist_returns) * np.sqrt(252))
                except (IndexError, ValueError, ZeroDivisionError):
                    continue
            
            if vol_history:
                volatility_percentile = np.percentile(vol_history, current_volatility) / 100
            else:
                volatility_percentile = 0.5
        else:
            volatility_percentile = 0.5
        
        # 변동성 체제 분류
        if current_volatility > self.crisis_vol_threshold:
            volatility_regime = 'crisis'
        elif current_volatility > self.high_vol_threshold:
            volatility_regime = 'high'
        elif current_volatility < 0.15:
            volatility_regime = 'low'
        else:
            volatility_regime = 'normal'
        
        return {
            'volatility': current_volatility,
            'volatility_ratio': volatility_ratio,
            'volatility_percentile': volatility_percentile,
            'volatility_regime': volatility_regime
        }
    
    def calculate_volume_metrics(self, volume: np.ndarray, period: int) -> Dict[str, float]:
        """거래량 지표 계산"""
        if len(volume) < period:
            return {'volume_trend': 1.0, 'volume_surge': False, 'volume_regime': 'normal'}
        
        recent_volume = volume[-period:]
        
        # 거래량 추세 (최근 vs 이전)
        half_period = period // 2
        recent_avg = np.mean(recent_volume[-half_period:])
        previous_avg = np.mean(recent_volume[:half_period])
        volume_trend = recent_avg / previous_avg if previous_avg > 0 else 1.0
        
        # 거래량 급증 감지
        volume_ma = np.mean(recent_volume)
        current_volume = volume[-1]
        volume_surge = current_volume > volume_ma * self.volume_surge_threshold
        
        # 거래량 체제 분류
        if volume_trend > 1.5:
            volume_regime = 'surge'
        elif volume_trend > 1.2:
            volume_regime = 'increasing'
        elif volume_trend < 0.8:
            volume_regime = 'declining'
        else:
            volume_regime = 'normal'
        
        return {
            'volume_trend': volume_trend,
            'volume_surge': volume_surge,
            'volume_regime': volume_regime
        }
    
    def detect_market_regime(self, df: pd.DataFrame) -> Dict[str, Any]:
        """고급 시장 상황 감지"""
        if len(df) < self.long_period + 1:
            return {
                'regime': MarketRegime.SIDEWAYS,
                'confidence': 0.5,
                'risk_mode': RiskMode.NEUTRAL,
                'strength': 0.5,
                'metrics': {}
            }
        
        prices = df['Close'].values
        volume = df['Volume'].values
        
        # 1. 추세 분석 (다중 기간)
        short_trend = self.calculate_trend_strength(prices, self.short_period)
        medium_trend = self.calculate_trend_strength(prices, self.medium_period)
        long_trend = self.calculate_trend_strength(prices, self.long_period)
        
        # 2. 변동성 분석
        volatility_metrics = self.calculate_volatility_metrics(prices, self.volatility_period)
        
        # 3. 거래량 분석
        volume_metrics = self.calculate_volume_metrics(volume, self.medium_period)
        
        # 4. 가격 변화율 계산
        price_changes = {
            'short': (prices[-1] - prices[-self.short_period]) / prices[-self.short_period],
            'medium': (prices[-1] - prices[-self.medium_period]) / prices[-self.medium_period],
            'long': (prices[-1] - prices[-self.long_period]) / prices[-self.long_period]
        }
        
        # 5. 시장 상황 분류 로직
        regime, confidence = self._classify_market_regime(
            short_trend, medium_trend, long_trend,
            volatility_metrics, volume_metrics, price_changes
        )
        
        # 6. 리스크 모드 결정
        risk_mode = self._determine_risk_mode(regime, volatility_metrics, volume_metrics)
        
        # 7. 추세 강도 계산
        strength = self._calculate_regime_strength(
            short_trend, medium_trend, long_trend, volatility_metrics
        )
        
        # 8. 종합 메트릭
        metrics = {
            'trends': {'short': short_trend, 'medium': medium_trend, 'long': long_trend},
            'volatility': volatility_metrics,
            'volume': volume_metrics,
            'price_changes': price_changes
        }
        
        # 이력 저장
        self.regime_history.append(regime)
        self.risk_mode_history.append(risk_mode)
        
        # 최근 50개만 유지
        if len(self.regime_history) > 50:
            self.regime_history = self.regime_history[-50:]
            self.risk_mode_history = self.risk_mode_history[-50:]
        
        return {
            'regime': regime,
            'confidence': confidence,
            'risk_mode': risk_mode,
            'strength': strength,
            'metrics': metrics
        }
    
    def _classify_market_regime(self, short_trend: float, medium_trend: float, long_trend: float,
                              volatility_metrics: Dict, volume_metrics: Dict, 
                              price_changes: Dict) -> Tuple[MarketRegime, float]:
        """시장 상황 분류 로직"""
        
        # 위기 상황 우선 감지
        if (volatility_metrics['volatility_regime'] == 'crisis' or
            (volatility_metrics['volatility'] > self.crisis_vol_threshold and
             all(change < -0.1 for change in price_changes.values()))):
            return MarketRegime.CRISIS, 0.9
        
        # 고변동성 상황
        if (volatility_metrics['volatility_regime'] == 'high' or
            volatility_metrics['volatility'] > self.high_vol_threshold):
            return MarketRegime.HIGH_VOLATILITY, 0.8
            
        # 추세 기반 분류
        trend_score = (short_trend * 0.5 + medium_trend * 0.3 + long_trend * 0.2)
        medium_change = price_changes['medium']
        
        # 강세장 감지
        if (trend_score > 0.01 and medium_change > self.bull_threshold and
            medium_trend > 0 and long_trend > -0.005):
            confidence = min(0.9, 0.6 + abs(trend_score) * 10)
            
            # 회복 구간인지 확인 (이전이 하락장이었는지)
            if len(self.regime_history) >= 3:
                recent_regimes = self.regime_history[-3:]
                if any(regime in [MarketRegime.BEAR_MARKET, MarketRegime.CRISIS] for regime in recent_regimes):
                    return MarketRegime.RECOVERY, confidence
            
            return MarketRegime.BULL_MARKET, confidence
        
        # 약세장 감지
        elif (trend_score < -0.01 and medium_change < self.bear_threshold and
              medium_trend < 0 and short_trend < 0):
            confidence = min(0.9, 0.6 + abs(trend_score) * 10)
            return MarketRegime.BEAR_MARKET, confidence
        
        # 횡보장 (기본값)
        else:
            confidence = 0.6 - abs(trend_score) * 5  # 추세가 약할수록 횡보 신뢰도 높음
            confidence = max(0.3, min(0.8, confidence))
            return MarketRegime.SIDEWAYS, confidence
    
    def _determine_risk_mode(self, regime: MarketRegime, volatility_metrics: Dict, 
                           volume_metrics: Dict) -> RiskMode:
        """리스크 모드 결정"""
        
        # 위기 상황은 무조건 Risk Off
        if regime in [MarketRegime.CRISIS, MarketRegime.BEAR_MARKET]:
            return RiskMode.RISK_OFF
        
        # 고변동성 상황에서는 거래량에 따라 결정
        if regime == MarketRegime.HIGH_VOLATILITY:
            if volume_metrics['volume_surge']:
                return RiskMode.RISK_ON  # 거래량 급증시 기회로 판단
            else:
                return RiskMode.RISK_OFF  # 단순 변동성 증가는 위험
        
        # 강세장과 회복 구간은 Risk On
        if regime in [MarketRegime.BULL_MARKET, MarketRegime.RECOVERY]:
            return RiskMode.RISK_ON
        
        # 횡보장은 중립
        return RiskMode.NEUTRAL
    
    def _calculate_regime_strength(self, short_trend: float, medium_trend: float, 
                                 long_trend: float, volatility_metrics: Dict) -> float:
        """시장 상황 강도 계산"""
        
        # 추세 일치도 계산
        trends = [short_trend, medium_trend, long_trend]
        trend_consistency = 1.0 - np.std(trends) / (np.mean(np.abs(trends)) + 1e-6)
        trend_consistency = max(0.0, min(1.0, trend_consistency))
        
        # 절대적 추세 강도
        trend_magnitude = np.mean(np.abs(trends))
        
        # 변동성 보정 (변동성이 높으면 신뢰도 감소)
        volatility_penalty = min(1.0, volatility_metrics['volatility'] / 0.3)
        
        # 종합 강도 계산
        strength = (trend_consistency * 0.6 + trend_magnitude * 10 * 0.4) * (1 - volatility_penalty * 0.3)
        
        return max(0.1, min(1.0, strength))
    
    def adapt_algorithm_parameters(self, base_params: Dict[str, Any], 
                                 market_condition: Dict[str, Any]) -> Dict[str, Any]:
        """시장 상황에 따른 알고리즘 매개변수 적응"""
        
        regime = market_condition['regime']
        strength = market_condition['strength']
        confidence = market_condition['confidence']
        risk_mode = market_condition['risk_mode']
        
        # 기본 템플릿 가져오기
        regime_template = self.regime_parameters.get(regime, self.regime_parameters[MarketRegime.SIDEWAYS])
        
        # 적응형 매개변수 계산
        adapted_params = base_params.copy()
        
        # 1. 신호 가중치 조정
        adapted_params['signal_weights'] = regime_template['signal_weights'].copy()
        
        # 2. 포지션 크기 조정
        base_position = adapted_params.get('base_position_size', 0.08)
        position_multiplier = regime_template['position_multiplier']
        
        # 강도와 신뢰도에 따른 추가 조정
        strength_adjustment = 0.8 + (strength * 0.4)  # 0.8 ~ 1.2
        confidence_adjustment = 0.9 + (confidence * 0.2)  # 0.9 ~ 1.1
        
        adapted_params['adapted_position_size'] = (
            base_position * position_multiplier * strength_adjustment * confidence_adjustment
        )
        adapted_params['adapted_position_size'] = max(0.02, min(0.25, adapted_params['adapted_position_size']))
        
        # 3. 손절선 조정
        base_stop_loss = adapted_params.get('base_stop_loss', 3.0)
        stop_multiplier = regime_template['stop_loss_multiplier']
        adapted_params['adapted_stop_loss'] = base_stop_loss * stop_multiplier
        
        # 4. 익절선 조정
        base_take_profit = adapted_params.get('base_take_profit', 8.0)
        profit_multiplier = regime_template['take_profit_multiplier']
        adapted_params['adapted_take_profit'] = base_take_profit * profit_multiplier
        
        # 5. 신뢰도 임계값 조정
        adapted_params['adapted_confidence_threshold'] = regime_template['confidence_threshold']
        
        # 6. 보유 기간 조정
        base_hold_days = adapted_params.get('optimal_hold_days', 7)
        hold_multiplier = regime_template['hold_days_multiplier']
        adapted_params['adapted_hold_days'] = int(base_hold_days * hold_multiplier)
        adapted_params['adapted_hold_days'] = max(1, min(20, adapted_params['adapted_hold_days']))
        
        # 7. 리스크 모드별 추가 조정
        if risk_mode == RiskMode.RISK_OFF:
            adapted_params['adapted_position_size'] *= 0.7  # 포지션 30% 추가 축소
            adapted_params['adapted_confidence_threshold'] = min(0.95, adapted_params['adapted_confidence_threshold'] * 1.1)
        elif risk_mode == RiskMode.RISK_ON:
            adapted_params['adapted_position_size'] *= 1.2  # 포지션 20% 추가 확대
            adapted_params['adapted_confidence_threshold'] = max(0.6, adapted_params['adapted_confidence_threshold'] * 0.95)
        
        # 최종 한계값 적용
        adapted_params['adapted_position_size'] = max(0.01, min(0.3, adapted_params['adapted_position_size']))
        adapted_params['adapted_stop_loss'] = max(1.0, min(8.0, adapted_params['adapted_stop_loss']))
        adapted_params['adapted_take_profit'] = max(3.0, min(20.0, adapted_params['adapted_take_profit']))
        adapted_params['adapted_confidence_threshold'] = max(0.5, min(0.95, adapted_params['adapted_confidence_threshold']))
        
        return adapted_params
    
    def get_regime_statistics(self) -> Dict[str, Any]:
        """시장 상황 통계 조회"""
        if not self.regime_history:
            return {'message': 'No regime history available'}
        
        # 최근 상황 분포
        recent_regimes = self.regime_history[-20:] if len(self.regime_history) >= 20 else self.regime_history
        regime_counts = {}
        for regime in recent_regimes:
            regime_counts[regime.value] = regime_counts.get(regime.value, 0) + 1
        
        # 최근 리스크 모드 분포
        recent_risk_modes = self.risk_mode_history[-20:] if len(self.risk_mode_history) >= 20 else self.risk_mode_history
        risk_mode_counts = {}
        for risk_mode in recent_risk_modes:
            risk_mode_counts[risk_mode.value] = risk_mode_counts.get(risk_mode.value, 0) + 1
        
        return {
            'current_regime': self.regime_history[-1].value if self.regime_history else 'unknown',
            'current_risk_mode': self.risk_mode_history[-1].value if self.risk_mode_history else 'unknown',
            'regime_distribution': regime_counts,
            'risk_mode_distribution': risk_mode_counts,
            'total_periods_analyzed': len(self.regime_history)
        }

# 편의 함수들
def detect_market_regime(df: pd.DataFrame) -> Dict[str, Any]:
    """DataFrame에서 시장 상황 감지"""
    detector = AdvancedMarketRegimeDetector()
    return detector.detect_market_regime(df)

def adapt_parameters(base_params: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
    """시장 상황에 따른 매개변수 적응"""
    detector = AdvancedMarketRegimeDetector()
    market_condition = detector.detect_market_regime(df)
    return detector.adapt_algorithm_parameters(base_params, market_condition)

if __name__ == "__main__":
    print("=== AdvancedMarketRegimeDetector 테스트 ===")
    
    # 샘플 데이터 생성 (상승 추세)
    np.random.seed(42)
    n = 100
    trend = np.linspace(0, 10, n)  # 상승 추세
    noise = np.random.randn(n) * 2
    close = 100 + trend + noise
    high = close + np.random.rand(n) * 3
    low = close - np.random.rand(n) * 3
    volume = np.random.randint(1000, 50000, n)
    
    df = pd.DataFrame({
        'Close': close,
        'High': high,
        'Low': low,
        'Volume': volume
    })
    
    # 시장 상황 감지
    detector = AdvancedMarketRegimeDetector()
    market_condition = detector.detect_market_regime(df)
    
    print(f"감지된 시장 상황: {market_condition['regime'].value}")
    print(f"신뢰도: {market_condition['confidence']:.3f}")
    print(f"리스크 모드: {market_condition['risk_mode'].value}")
    print(f"추세 강도: {market_condition['strength']:.3f}")
    
    # 매개변수 적응 테스트
    base_params = {
        'base_position_size': 0.08,
        'base_stop_loss': 3.0,
        'base_take_profit': 8.0,
        'optimal_hold_days': 7
    }
    
    adapted_params = detector.adapt_algorithm_parameters(base_params, market_condition)
    
    print("\n매개변수 적응 결과:")
    print(f"포지션 크기: {base_params['base_position_size']:.3f} → {adapted_params['adapted_position_size']:.3f}")
    print(f"손절선: {base_params['base_stop_loss']:.1f}% → {adapted_params['adapted_stop_loss']:.1f}%")
    print(f"익절선: {base_params['base_take_profit']:.1f}% → {adapted_params['adapted_take_profit']:.1f}%")
    print(f"신뢰도 임계값: → {adapted_params['adapted_confidence_threshold']:.3f}")
    
    print("=== 테스트 완료 ===")