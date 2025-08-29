"""
SimpleSurgeDetector - 급등주 탐지 시스템
실시간 급등주를 탐지하고 분석하는 모듈
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SurgeDetectionResult:
    """급등 탐지 결과"""
    stock_code: str
    current_price: float
    surge_score: float
    recommendation: str  # "BUY", "HOLD", "SELL"
    confidence: float    # 0.0-1.0
    volume_ratio: float
    price_change_rate: float
    technical_indicators: Dict[str, float]
    risk_level: str      # "LOW", "MEDIUM", "HIGH"


class SimpleSurgeDetector:
    """간단한 급등주 탐지기"""
    
    def __init__(self):
        """초기화"""
        self.name = "SimpleSurgeDetector"
        self.version = "1.0"
        
        # 급등 탐지 임계값
        self.min_surge_rate = 0.02      # 최소 2% 상승
        self.min_volume_ratio = 1.5     # 거래량 1.5배 이상
        self.max_price_threshold = 500000  # 50만원 이하
        
        # 기술적 지표 가중치
        self.weights = {
            'price_momentum': 0.3,
            'volume_surge': 0.25,
            'trend_strength': 0.2,
            'volatility': 0.15,
            'rsi': 0.1
        }
        
        logger.info(f"{self.name} v{self.version} 초기화 완료")
    
    def analyze_surge_potential(self, stock_code: str, price_data: Dict, **kwargs) -> Dict[str, Any]:
        """급등 잠재력 분석
        
        Args:
            stock_code: 종목 코드
            price_data: 가격 데이터 (OHLCV)
            **kwargs: 추가 파라미터
            
        Returns:
            분석 결과 딕셔너리
        """
        try:
            if not price_data or not isinstance(price_data, dict):
                return self._default_result(stock_code, "insufficient_data")
            
            # 기본 데이터 추출
            current_price = float(price_data.get('current_price', 0))
            previous_price = float(price_data.get('previous_price', current_price))
            volume = int(price_data.get('volume', 0))
            avg_volume = int(price_data.get('avg_volume', volume))
            
            if current_price <= 0 or previous_price <= 0:
                return self._default_result(stock_code, "invalid_price")
            
            # 가격 변화율 계산
            price_change_rate = (current_price - previous_price) / previous_price
            
            # 거래량 비율 계산
            volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
            
            # 기본 필터링
            if not self._basic_filter(current_price, price_change_rate, volume_ratio):
                return self._default_result(stock_code, "filtered_out")
            
            # 급등 점수 계산
            surge_score = self._calculate_surge_score(
                price_change_rate, volume_ratio, current_price, price_data
            )
            
            # 추천 결정
            recommendation = self._determine_recommendation(surge_score, price_change_rate)
            
            # 신뢰도 계산
            confidence = self._calculate_confidence(surge_score, volume_ratio)
            
            # 리스크 레벨 계산
            risk_level = self._assess_risk_level(price_change_rate, volume_ratio, current_price)
            
            # 기술적 지표
            technical_indicators = self._calculate_technical_indicators(price_data)
            
            return {
                'stock_code': stock_code,
                'surge_score': round(surge_score, 2),
                'recommendation': recommendation,
                'confidence': round(confidence, 3),
                'price_change_rate': round(price_change_rate * 100, 2),  # 퍼센트로 변환
                'volume_ratio': round(volume_ratio, 2),
                'current_price': current_price,
                'risk_level': risk_level,
                'technical_indicators': technical_indicators,
                'analysis_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"급등 분석 실패 ({stock_code}): {e}")
            return self._default_result(stock_code, f"error: {e}")
    
    def _basic_filter(self, price: float, change_rate: float, volume_ratio: float) -> bool:
        """기본 필터링"""
        # 가격이 너무 높으면 제외
        if price > self.max_price_threshold:
            return False
        
        # 최소 상승률 체크
        if change_rate < self.min_surge_rate:
            return False
        
        # 최소 거래량 증가 체크
        if volume_ratio < self.min_volume_ratio:
            return False
        
        return True
    
    def _calculate_surge_score(self, price_change_rate: float, volume_ratio: float, 
                              current_price: float, price_data: Dict) -> float:
        """급등 점수 계산"""
        try:
            # 1. 가격 모멘텀 점수 (0-30점)
            price_momentum = min(price_change_rate * 100 * 3, 30)
            
            # 2. 거래량 급증 점수 (0-25점)
            volume_surge = min((volume_ratio - 1) * 10, 25)
            
            # 3. 추세 강도 점수 (0-20점)
            trend_strength = self._calculate_trend_strength(price_data)
            
            # 4. 변동성 점수 (0-15점) - 적절한 변동성 선호
            volatility_score = self._calculate_volatility_score(price_data)
            
            # 5. RSI 점수 (0-10점) - 과매수 구간 회피
            rsi_score = self._calculate_rsi_score(price_data)
            
            # 가중 평균으로 최종 점수 계산
            total_score = (
                price_momentum * self.weights['price_momentum'] +
                volume_surge * self.weights['volume_surge'] +
                trend_strength * self.weights['trend_strength'] +
                volatility_score * self.weights['volatility'] +
                rsi_score * self.weights['rsi']
            )
            
            return max(0, min(100, total_score))
            
        except Exception as e:
            logger.debug(f"급등 점수 계산 오류: {e}")
            return 0.0
    
    def _calculate_trend_strength(self, price_data: Dict) -> float:
        """추세 강도 계산"""
        try:
            # 간단한 추세 강도 - 실제로는 더 복잡한 계산 필요
            high = float(price_data.get('high', 0))
            low = float(price_data.get('low', 0))
            close = float(price_data.get('current_price', 0))
            
            if high <= low:
                return 10.0  # 기본값
            
            # 봉의 위치 기반 추세 강도
            position = (close - low) / (high - low)
            return position * 20  # 0-20점
            
        except Exception:
            return 10.0  # 기본값
    
    def _calculate_volatility_score(self, price_data: Dict) -> float:
        """변동성 점수 계산"""
        try:
            high = float(price_data.get('high', 0))
            low = float(price_data.get('low', 0))
            close = float(price_data.get('current_price', 0))
            
            if close <= 0:
                return 7.5  # 기본값
            
            # 일간 변동성 계산
            volatility = (high - low) / close * 100
            
            # 적절한 변동성 범위 (2-8%)에서 높은 점수
            if 2 <= volatility <= 8:
                return 15.0
            elif volatility < 2:
                return volatility * 7.5  # 변동성이 너무 낮음
            else:
                return max(0, 15 - (volatility - 8) * 2)  # 변동성이 너무 높음
            
        except Exception:
            return 7.5  # 기본값
    
    def _calculate_rsi_score(self, price_data: Dict) -> float:
        """RSI 점수 계산"""
        try:
            # 간단한 RSI 추정 - 실제로는 14일 RSI 계산 필요
            current_price = float(price_data.get('current_price', 0))
            previous_price = float(price_data.get('previous_price', current_price))
            
            if previous_price <= 0:
                return 5.0  # 기본값
            
            change_rate = (current_price - previous_price) / previous_price
            
            # 간단한 RSI 추정 (실제 RSI와는 다름)
            estimated_rsi = 50 + (change_rate * 100 * 2)
            estimated_rsi = max(0, min(100, estimated_rsi))
            
            # RSI 30-70 구간에서 높은 점수
            if 30 <= estimated_rsi <= 70:
                return 10.0
            elif estimated_rsi < 30:
                return estimated_rsi / 3  # 과매도
            else:
                return max(0, 10 - (estimated_rsi - 70) * 0.3)  # 과매수
            
        except Exception:
            return 5.0  # 기본값
    
    def _determine_recommendation(self, surge_score: float, price_change_rate: float) -> str:
        """매매 추천 결정"""
        if surge_score >= 70:
            return "BUY"
        elif surge_score >= 40:
            return "HOLD"
        else:
            return "HOLD"  # 보수적 접근
    
    def _calculate_confidence(self, surge_score: float, volume_ratio: float) -> float:
        """신뢰도 계산"""
        # 점수와 거래량 기반 신뢰도
        score_confidence = surge_score / 100
        volume_confidence = min(volume_ratio / 5, 1.0)  # 5배 이상이면 최대
        
        return (score_confidence + volume_confidence) / 2
    
    def _assess_risk_level(self, price_change_rate: float, volume_ratio: float, price: float) -> str:
        """리스크 레벨 평가"""
        risk_score = 0
        
        # 가격 급등률이 높을수록 리스크 증가
        if price_change_rate > 0.15:  # 15% 이상
            risk_score += 3
        elif price_change_rate > 0.10:  # 10-15%
            risk_score += 2
        elif price_change_rate > 0.05:  # 5-10%
            risk_score += 1
        
        # 거래량이 극도로 많으면 리스크 증가
        if volume_ratio > 10:
            risk_score += 2
        elif volume_ratio > 5:
            risk_score += 1
        
        # 고가 종목일수록 리스크 증가
        if price > 300000:
            risk_score += 2
        elif price > 100000:
            risk_score += 1
        
        if risk_score >= 5:
            return "HIGH"
        elif risk_score >= 3:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _calculate_technical_indicators(self, price_data: Dict) -> Dict[str, float]:
        """기술적 지표 계산"""
        try:
            current_price = float(price_data.get('current_price', 0))
            high = float(price_data.get('high', current_price))
            low = float(price_data.get('low', current_price))
            volume = int(price_data.get('volume', 0))
            
            return {
                'price_position': (current_price - low) / (high - low) * 100 if high > low else 50,
                'volume_surge': volume / price_data.get('avg_volume', volume) if price_data.get('avg_volume', 0) > 0 else 1.0,
                'daily_range': (high - low) / current_price * 100 if current_price > 0 else 0,
                'momentum': (current_price / price_data.get('previous_price', current_price) - 1) * 100
            }
            
        except Exception:
            return {
                'price_position': 50.0,
                'volume_surge': 1.0,
                'daily_range': 3.0,
                'momentum': 0.0
            }
    
    def _default_result(self, stock_code: str, reason: str) -> Dict[str, Any]:
        """기본 결과 반환"""
        return {
            'stock_code': stock_code,
            'surge_score': 0.0,
            'recommendation': 'HOLD',
            'confidence': 0.0,
            'price_change_rate': 0.0,
            'volume_ratio': 1.0,
            'current_price': 0.0,
            'risk_level': 'LOW',
            'technical_indicators': {
                'price_position': 50.0,
                'volume_surge': 1.0,
                'daily_range': 0.0,
                'momentum': 0.0
            },
            'analysis_time': datetime.now().isoformat(),
            'reason': reason
        }
    
    def analyze_multiple_stocks(self, stock_data_list: List[Dict]) -> List[Dict]:
        """여러 종목 일괄 분석"""
        results = []
        
        for stock_data in stock_data_list:
            if not isinstance(stock_data, dict):
                continue
                
            stock_code = stock_data.get('stock_code', 'UNKNOWN')
            result = self.analyze_surge_potential(stock_code, stock_data)
            results.append(result)
        
        # 점수순으로 정렬
        results.sort(key=lambda x: x.get('surge_score', 0), reverse=True)
        
        return results
    
    def get_top_surge_stocks(self, stock_data_list: List[Dict], limit: int = 20) -> List[Dict]:
        """상위 급등주 반환"""
        all_results = self.analyze_multiple_stocks(stock_data_list)
        
        # 추천이 BUY이거나 점수가 40 이상인 것만 필터링
        filtered_results = [
            result for result in all_results
            if result.get('recommendation') == 'BUY' or result.get('surge_score', 0) >= 40
        ]
        
        return filtered_results[:limit]


# 편의 함수
def get_simple_surge_detector() -> SimpleSurgeDetector:
    """SimpleSurgeDetector 인스턴스 반환"""
    return SimpleSurgeDetector()


# 테스트용 함수
def test_surge_detector():
    """테스트 함수"""
    detector = SimpleSurgeDetector()
    
    # 테스트 데이터
    test_data = {
        'stock_code': 'TEST001',
        'current_price': 75000,
        'previous_price': 70000,
        'high': 76000,
        'low': 74000,
        'volume': 1000000,
        'avg_volume': 500000
    }
    
    result = detector.analyze_surge_potential('TEST001', test_data)
    print(f"테스트 결과: {result}")
    
    return result


if __name__ == "__main__":
    test_surge_detector()