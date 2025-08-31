#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
David Paul Volume Validation Module
데이비드 폴 거래량 검증 시스템 - 가격×거래량 관계 분석

핵심 원리:
- Validation: 넓은 범위(큰 캔들) + 높은 거래량 → "의미 있는" 움직임
- Non-Validation: 넓은 범위 + 낮은 거래량 → "속 빈" 움직임(속임/피로)
- 다이버전스: 가격 고점↑에 거래량 고점↓(약세), 가격 저점↓에 거래량 저점↑(강세)
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class VolumeValidationResult:
    """거래량 검증 결과"""
    is_validated: bool          # 검증된 움직임 여부
    confidence: float           # 신뢰도 (0.0-1.0)
    signal_type: str           # 'VALIDATION', 'NON_VALIDATION', 'DIVERGENCE', 'NORMAL'
    reason: str                # 판단 근거
    price_range_ratio: float   # 가격 변동폭 비율
    volume_ratio: float        # 거래량 비율
    divergence_detected: bool  # 다이버전스 감지 여부
    risk_level: str           # 'LOW', 'MEDIUM', 'HIGH'

class DavidPaulVolumeValidator:
    """데이비드 폴 거래량 검증기"""
    
    def __init__(self, 
                 volume_ma_period: int = 20,
                 range_ma_period: int = 20,
                 volume_spike_multiplier: float = 2.2,
                 wide_range_multiplier: float = 1.5,
                 divergence_lookback: int = 10):
        """
        초기화
        
        Args:
            volume_ma_period: 거래량 이동평균 기간
            range_ma_period: 가격 범위 이동평균 기간
            volume_spike_multiplier: 거래량 급증 판단 배수
            wide_range_multiplier: 넓은 변동폭 판단 배수
            divergence_lookback: 다이버전스 탐지를 위한 과거 조회 기간
        """
        self.volume_ma_period = volume_ma_period
        self.range_ma_period = range_ma_period
        self.volume_spike_multiplier = volume_spike_multiplier
        self.wide_range_multiplier = wide_range_multiplier
        self.divergence_lookback = divergence_lookback
        
        # 과거 데이터 저장소 (다이버전스 분석용)
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.high_history: List[float] = []
        self.low_history: List[float] = []
        self.timestamp_history: List[datetime] = []
        
        logger.info(f"David Paul Volume Validator 초기화 완료")
        logger.info(f"설정: VMA({volume_ma_period}), RMA({range_ma_period}), "
                   f"볼륨배수({volume_spike_multiplier}), 범위배수({wide_range_multiplier})")
    
    def validate_price_volume_relationship(self, stock_data: Dict[str, Any]) -> VolumeValidationResult:
        """
        가격-거래량 관계 검증
        
        Args:
            stock_data: 종목 데이터 (current_price, volume, high, low, open 등)
            
        Returns:
            VolumeValidationResult: 검증 결과
        """
        try:
            # 필수 데이터 추출
            current_price = float(stock_data.get('current_price', 0))
            volume = int(stock_data.get('volume', 0))
            high_price = float(stock_data.get('high_price', 0))
            low_price = float(stock_data.get('low_price', 0))
            open_price = float(stock_data.get('open_price', 0))
            
            # 데이터 유효성 검증
            if not self._validate_input_data(current_price, volume, high_price, low_price, open_price):
                return VolumeValidationResult(
                    is_validated=False,
                    confidence=0.0,
                    signal_type='NORMAL',
                    reason='입력 데이터 부족',
                    price_range_ratio=0.0,
                    volume_ratio=0.0,
                    divergence_detected=False,
                    risk_level='HIGH'
                )
            
            # 과거 데이터 업데이트
            self._update_history(current_price, volume, high_price, low_price)
            
            # 핵심 분석 수행
            range_analysis = self._analyze_price_range(high_price, low_price, open_price)
            volume_analysis = self._analyze_volume_strength(volume)
            divergence_analysis = self._detect_divergence()
            
            # 통합 판정
            validation_result = self._generate_final_assessment(
                range_analysis, volume_analysis, divergence_analysis, stock_data
            )
            
            logger.debug(f"거래량 검증 결과: {validation_result.signal_type} "
                        f"(신뢰도: {validation_result.confidence:.2f})")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"거래량 검증 오류: {e}")
            return VolumeValidationResult(
                is_validated=False,
                confidence=0.0,
                signal_type='NORMAL',
                reason=f'분석 오류: {str(e)[:50]}',
                price_range_ratio=0.0,
                volume_ratio=0.0,
                divergence_detected=False,
                risk_level='HIGH'
            )
    
    def _validate_input_data(self, price: float, volume: int, high: float, low: float, open_price: float) -> bool:
        """입력 데이터 유효성 검증"""
        if price <= 0 or volume <= 0 or high <= 0 or low <= 0 or open_price <= 0:
            return False
        if high < low or price < low or price > high:
            return False
        return True
    
    def _update_history(self, price: float, volume: int, high: float, low: float):
        """과거 데이터 업데이트"""
        now = datetime.now()
        
        self.price_history.append(price)
        self.volume_history.append(volume)
        self.high_history.append(high)
        self.low_history.append(low)
        self.timestamp_history.append(now)
        
        # 과거 데이터 길이 제한 (메모리 관리)
        max_history = max(self.volume_ma_period, self.range_ma_period, self.divergence_lookback) * 2
        if len(self.price_history) > max_history:
            self.price_history = self.price_history[-max_history:]
            self.volume_history = self.volume_history[-max_history:]
            self.high_history = self.high_history[-max_history:]
            self.low_history = self.low_history[-max_history:]
            self.timestamp_history = self.timestamp_history[-max_history:]
    
    def _analyze_price_range(self, high: float, low: float, open_price: float) -> Dict[str, Any]:
        """가격 변동폭 분석"""
        current_range = high - low
        
        # 과거 변동폭 평균 계산
        if len(self.high_history) >= self.range_ma_period:
            recent_ranges = []
            for i in range(len(self.high_history) - self.range_ma_period, len(self.high_history)):
                if i > 0:
                    recent_ranges.append(self.high_history[i] - self.low_history[i])
            
            if recent_ranges:
                avg_range = np.mean(recent_ranges)
                range_ratio = current_range / avg_range if avg_range > 0 else 1.0
            else:
                range_ratio = 1.0
        else:
            # 데이터 부족시 현재 가격 대비 변동폭으로 계산
            range_ratio = current_range / open_price if open_price > 0 else 0.0
        
        is_wide_range = range_ratio >= self.wide_range_multiplier
        
        return {
            'current_range': current_range,
            'range_ratio': range_ratio,
            'is_wide_range': is_wide_range,
            'range_strength': min(range_ratio / self.wide_range_multiplier, 2.0)  # 최대 2배
        }
    
    def _analyze_volume_strength(self, current_volume: int) -> Dict[str, Any]:
        """거래량 강도 분석"""
        if len(self.volume_history) >= self.volume_ma_period:
            recent_volumes = self.volume_history[-self.volume_ma_period:]
            avg_volume = np.mean(recent_volumes)
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        else:
            # 데이터 부족시 기본값 적용
            volume_ratio = 1.0
            avg_volume = current_volume
        
        is_volume_spike = volume_ratio >= self.volume_spike_multiplier
        is_low_volume = volume_ratio < 0.5  # 평균 대비 50% 이하
        
        return {
            'current_volume': current_volume,
            'avg_volume': avg_volume,
            'volume_ratio': volume_ratio,
            'is_volume_spike': is_volume_spike,
            'is_low_volume': is_low_volume,
            'volume_strength': min(volume_ratio / self.volume_spike_multiplier, 3.0)  # 최대 3배
        }
    
    def _detect_divergence(self) -> Dict[str, Any]:
        """다이버전스 탐지"""
        if len(self.price_history) < self.divergence_lookback or len(self.volume_history) < self.divergence_lookback:
            return {
                'bearish_divergence': False,
                'bullish_divergence': False,
                'divergence_strength': 0.0,
                'divergence_type': 'NONE'
            }
        
        try:
            # 최근 데이터로 추세 분석
            recent_prices = np.array(self.price_history[-self.divergence_lookback:])
            recent_volumes = np.array(self.volume_history[-self.divergence_lookback:])
            
            # 선형 회귀를 통한 추세 계산
            x = np.arange(len(recent_prices))
            price_slope = np.polyfit(x, recent_prices, 1)[0]
            volume_slope = np.polyfit(x, recent_volumes, 1)[0]
            
            # 다이버전스 판정
            price_trend = 'UP' if price_slope > 0 else 'DOWN'
            volume_trend = 'UP' if volume_slope > 0 else 'DOWN'
            
            bearish_divergence = (price_trend == 'UP' and volume_trend == 'DOWN')
            bullish_divergence = (price_trend == 'DOWN' and volume_trend == 'UP')
            
            # 다이버전스 강도 계산 (기울기 차이를 정규화)
            if bearish_divergence or bullish_divergence:
                # 가격과 거래량의 정규화된 기울기 차이
                price_norm_slope = price_slope / np.mean(recent_prices) if np.mean(recent_prices) > 0 else 0
                volume_norm_slope = volume_slope / np.mean(recent_volumes) if np.mean(recent_volumes) > 0 else 0
                divergence_strength = abs(price_norm_slope + volume_norm_slope)  # 반대 방향이므로 절댓값의 합
                divergence_strength = min(divergence_strength * 10, 1.0)  # 0-1 범위로 정규화
            else:
                divergence_strength = 0.0
            
            divergence_type = 'BEARISH' if bearish_divergence else ('BULLISH' if bullish_divergence else 'NONE')
            
            return {
                'bearish_divergence': bearish_divergence,
                'bullish_divergence': bullish_divergence,
                'divergence_strength': divergence_strength,
                'divergence_type': divergence_type,
                'price_trend': price_trend,
                'volume_trend': volume_trend
            }
            
        except Exception as e:
            logger.warning(f"다이버전스 탐지 오류: {e}")
            return {
                'bearish_divergence': False,
                'bullish_divergence': False,
                'divergence_strength': 0.0,
                'divergence_type': 'NONE'
            }
    
    def _generate_final_assessment(self, range_analysis: Dict, volume_analysis: Dict, 
                                 divergence_analysis: Dict, stock_data: Dict) -> VolumeValidationResult:
        """최종 평가 생성"""
        
        # 1. David Paul 핵심 원리 적용
        is_wide_range = range_analysis['is_wide_range']
        is_volume_spike = volume_analysis['is_volume_spike']
        is_low_volume = volume_analysis['is_low_volume']
        
        # 2. 신호 분류
        if is_wide_range and is_volume_spike:
            # 검증된 움직임 (Validation)
            signal_type = 'VALIDATION'
            confidence = 0.8 + min(range_analysis['range_strength'] * 0.1, 0.15)
            risk_level = 'LOW'
            reason = f"검증된 움직임: 넓은 변동폭({range_analysis['range_ratio']:.1f}배) + 대량 거래량({volume_analysis['volume_ratio']:.1f}배)"
            is_validated = True
            
        elif is_wide_range and is_low_volume:
            # 비검증 움직임 (Non-Validation)
            signal_type = 'NON_VALIDATION'
            confidence = 0.7 + min(range_analysis['range_strength'] * 0.1, 0.2)
            risk_level = 'HIGH'
            reason = f"비검증 움직임: 넓은 변동폭({range_analysis['range_ratio']:.1f}배) + 저조한 거래량({volume_analysis['volume_ratio']:.1f}배)"
            is_validated = False
            
        elif divergence_analysis['divergence_type'] != 'NONE':
            # 다이버전스 감지
            signal_type = 'DIVERGENCE'
            confidence = 0.6 + divergence_analysis['divergence_strength'] * 0.3
            risk_level = 'HIGH' if divergence_analysis['divergence_type'] == 'BEARISH' else 'MEDIUM'
            reason = f"{divergence_analysis['divergence_type']} 다이버전스: 가격({divergence_analysis['price_trend']}) vs 거래량({divergence_analysis['volume_trend']})"
            is_validated = False
            
        else:
            # 일반 상태
            signal_type = 'NORMAL'
            base_confidence = 0.5
            # 거래량과 변동폭에 따른 신뢰도 조정
            confidence_adj = (volume_analysis['volume_strength'] + range_analysis['range_strength']) * 0.1
            confidence = min(base_confidence + confidence_adj, 0.8)
            risk_level = 'MEDIUM'
            reason = f"일반 상태: 변동폭({range_analysis['range_ratio']:.1f}배), 거래량({volume_analysis['volume_ratio']:.1f}배)"
            is_validated = True if confidence > 0.6 else False
        
        # 3. 최종 신뢰도 조정 (다이버전스 페널티)
        if divergence_analysis['bearish_divergence']:
            confidence *= 0.8  # 약세 다이버전스시 신뢰도 감소
        
        return VolumeValidationResult(
            is_validated=is_validated,
            confidence=min(confidence, 1.0),
            signal_type=signal_type,
            reason=reason,
            price_range_ratio=range_analysis['range_ratio'],
            volume_ratio=volume_analysis['volume_ratio'],
            divergence_detected=(divergence_analysis['divergence_type'] != 'NONE'),
            risk_level=risk_level
        )
    
    def get_volume_analysis_summary(self) -> Dict[str, Any]:
        """거래량 분석 요약 정보 반환"""
        if not self.volume_history:
            return {'status': 'no_data', 'message': '분석 데이터 없음'}
        
        recent_volume_avg = np.mean(self.volume_history[-self.volume_ma_period:]) if len(self.volume_history) >= self.volume_ma_period else 0
        recent_range_avg = 0
        
        if len(self.high_history) >= self.range_ma_period:
            recent_ranges = []
            for i in range(len(self.high_history) - self.range_ma_period, len(self.high_history)):
                if i > 0:
                    recent_ranges.append(self.high_history[i] - self.low_history[i])
            recent_range_avg = np.mean(recent_ranges) if recent_ranges else 0
        
        return {
            'status': 'active',
            'data_points': len(self.volume_history),
            'volume_ma': recent_volume_avg,
            'range_ma': recent_range_avg,
            'settings': {
                'volume_spike_threshold': self.volume_spike_multiplier,
                'wide_range_threshold': self.wide_range_multiplier,
                'divergence_lookback': self.divergence_lookback
            }
        }

# 전역 인스턴스 (싱글톤 패턴)
_volume_validator_instance = None

def get_david_paul_validator() -> DavidPaulVolumeValidator:
    """David Paul Volume Validator 인스턴스 반환 (싱글톤)"""
    global _volume_validator_instance
    if _volume_validator_instance is None:
        _volume_validator_instance = DavidPaulVolumeValidator()
    return _volume_validator_instance

def reset_validator():
    """Validator 인스턴스 초기화 (테스트용)"""
    global _volume_validator_instance
    _volume_validator_instance = None

if __name__ == "__main__":
    # 테스트 코드
    validator = get_david_paul_validator()
    
    # 샘플 데이터 테스트
    test_data = {
        'current_price': 100000,
        'volume': 150000,
        'high_price': 102000,
        'low_price': 98000,
        'open_price': 99000
    }
    
    result = validator.validate_price_volume_relationship(test_data)
    print(f"테스트 결과: {result.signal_type} (신뢰도: {result.confidence:.2f})")
    print(f"이유: {result.reason}")
    print(f"검증됨: {result.is_validated}")