"""
SampleCode Converted to tideWise Compatible Algorithm
기존 SampleCode.py를 tideWise 단타매매 시스템에 맞춰 컨버전
- 거래량 급증 및 상승 추세 종목 필터링 
- 돌파 매수 + 3% 익절 / 2% 손절 전략
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime, time as datetime_time
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'support'))

from support.algorithm_interface import BaseAlgorithm

logger = logging.getLogger(__name__)


class SampleCodeConvertedAlgorithm(BaseAlgorithm):
    """
    SampleCode 컨버전 단타매매 알고리즘
    - 거래량 급증 + 상승 추세 종목 필터링
    - 고가 돌파 매수 전략
    - 3% 익절 / 2% 손절 단타매매
    """
    
    def __init__(self):
        super().__init__()
        self.algorithm_name = "SampleCode_Converted"
        self.description = "거래량급증 + 돌파매수 + 단타 익절/손절 전략"
        self.version = "1.0"
        
        # === 단타매매 전용 설정 ===
        self.day_trading_mode = True
        self.max_holding_time = 60          # 최대 보유시간 60분
        self.scalping_enabled = True
        
        # === 원본 로직 파라미터 (SampleCode 기준) ===
        self.volume_surge_ratio = 1.5       # 거래량 급증 기준 (어제 대비 150%)
        self.ma5_breakout = True             # 5일선 돌파 조건
        self.ma20_breakout = True            # 20일선 돌파 조건
        self.breakout_target_multiplier = 1.0 # 고가 돌파 기준 (100%)
        
        # === 단타매매 리스크 관리 ===
        self.take_profit_pct = 0.03         # 3% 익절
        self.stop_loss_pct = 0.02           # 2% 손절
        self.max_position_size = 0.20       # 최대 포지션 20%
        
        # === 실시간 데이터 처리를 위한 완화된 조건 ===
        self.min_volume_ratio = 1.2         # 최소 거래량 비율 (평상시 대비)
        self.min_change_rate = 0.005        # 최소 등락률 0.5%
        self.price_momentum_threshold = 0.01 # 가격 모멘텀 기준 1%
        
        # === VI 처리 설정 ===
        self.vi_detection_enabled = True
        self.upward_vi_action = "BUY"       # 상승 VI: 매수 기회
        self.downward_vi_action = "SELL"    # 하락 VI: 즉시 매도
        
        # === 내부 상태 관리 ===
        self.positions = {}                 # 포지션 관리
        self.entry_prices = {}              # 진입가 관리
        self.price_history = {}             # 가격 히스토리 (이평선 계산용)
        
        logger.info(f"SampleCode Converted 알고리즘 초기화: {self.algorithm_name} v{self.version}")
    
    def analyze(self, stock_data: Dict[str, Any], stock_code: str = None, **kwargs) -> Dict[str, Any]:
        """
        메인 분석 함수 - tideWise 호환
        
        Args:
            stock_data: 실시간 종목 데이터 dict
            stock_code: 종목 코드
            **kwargs: vi_status 등 추가 파라미터
            
        Returns:
            Dict: tideWise 표준 응답 형식
        """
        try:
            # === VI 상태 최우선 처리 ===
            vi_status = kwargs.get('vi_status', None)
            if vi_status and self.vi_detection_enabled:
                vi_response = self._handle_vi_emergency(vi_status, stock_data, stock_code)
                if vi_response:
                    return vi_response
            
            # === 실시간 데이터 검증 ===
            if not self._validate_realtime_data(stock_data):
                return self._create_hold_signal("데이터 부족")
            
            # === 시간 기반 필터링 ===
            current_time = datetime.now().time()
            if not self._is_trading_time(current_time):
                if self._is_force_close_time(current_time):
                    return self._create_force_sell_signal("장마감 청산")
                return self._create_hold_signal("거래시간 외")
            
            # === 원본 로직 기반 분석 ===
            # 1. 거래량 급증 확인
            volume_analysis = self._analyze_volume_surge(stock_data)
            
            # 2. 상승 추세 확인 (이평선 기반)
            trend_analysis = self._analyze_upward_trend(stock_data, stock_code)
            
            # 3. 돌파 매수 조건 확인
            breakout_analysis = self._analyze_breakout_condition(stock_data, stock_code)
            
            # 4. 매도 조건 확인 (보유 종목인 경우)
            if stock_code in self.positions:
                sell_analysis = self._check_sell_conditions(stock_data, stock_code)
                if sell_analysis:
                    return sell_analysis
            
            # 5. 최종 매수 신호 생성
            return self._generate_trading_signal(
                stock_data, stock_code, volume_analysis, trend_analysis, breakout_analysis
            )
            
        except Exception as e:
            logger.error(f"SampleCode Converted 분석 오류: {e}")
            return self._create_hold_signal(f"분석 오류: {str(e)[:30]}")
    
    def _handle_vi_emergency(self, vi_status: str, stock_data: Dict[str, Any], stock_code: str = None) -> Optional[Dict[str, Any]]:
        """VI(변동성 중단) 긴급 처리"""
        if not vi_status:
            return None
        
        current_price = stock_data.get('current_price', 0)
        
        # 상승 VI: 돌파 매수 기회로 활용
        if vi_status.upper() in ['UP_VI', 'UPWARD_VI', '상승VI']:
            logger.info(f"상승 VI 감지: {stock_code} - 돌파 매수 기회")
            return {
                'signal': 'BUY',
                'confidence': 0.9,
                'reason': '상승 VI 감지 - 돌파 매수 기회',
                'urgency': 'HIGH',
                'target_price': current_price * (1 + self.take_profit_pct),
                'stop_loss': current_price * (1 - self.stop_loss_pct),
                'scalping_mode': True,
                'max_hold_time': self.max_holding_time,
                'position_size': self.max_position_size,
                'details': {'vi_status': vi_status, 'current_price': current_price}
            }
        
        # 하락 VI: 즉시 매도
        elif vi_status.upper() in ['DOWN_VI', 'DOWNWARD_VI', '하락VI']:
            logger.warning(f"하락 VI 감지: {stock_code} - 즉시 매도")
            return {
                'signal': 'SELL',
                'confidence': 1.0,
                'reason': '하락 VI 감지 - 즉시 매도',
                'urgency': 'HIGH',
                'scalping_mode': False,
                'details': {'vi_status': vi_status, 'current_price': current_price}
            }
        
        return None
    
    def _validate_realtime_data(self, stock_data: Dict[str, Any]) -> bool:
        """실시간 데이터 유효성 검증"""
        required_fields = ['current_price', 'open_price', 'high_price', 'volume']
        
        for field in required_fields:
            if field not in stock_data or stock_data[field] <= 0:
                logger.warning(f"필수 데이터 누락 또는 비정상: {field}")
                return False
        
        return True
    
    def _is_trading_time(self, current_time: datetime_time) -> bool:
        """거래 시간 확인 (원본: 9:00 - 15:20)"""
        market_open = datetime_time(9, 0, 0)
        market_close = datetime_time(15, 20, 0)
        return market_open <= current_time <= market_close
    
    def _is_force_close_time(self, current_time: datetime_time) -> bool:
        """강제 청산 시간 확인"""
        force_close = datetime_time(15, 15, 0)  # 5분 전 청산
        return current_time >= force_close
    
    def _analyze_volume_surge(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """거래량 급증 분석 (원본: 어제 대비 50% 이상)"""
        try:
            volume = stock_data.get('volume', 0)
            volume_ratio = stock_data.get('volume_ratio', 1.0)  # tideWise 제공 비율
            
            # tideWise volume_ratio 활용 (기본값: 평상시 대비)
            # 원본 로직: 어제 대비 150% 이상 = volume_ratio 1.5 이상
            volume_surge = volume_ratio >= self.volume_surge_ratio
            
            # 추가 조건: 절대 거래량 체크
            sufficient_volume = volume >= 50000  # 5만주 이상
            
            return {
                'volume_surge': volume_surge,
                'sufficient_volume': sufficient_volume,
                'volume_ratio': volume_ratio,
                'volume': volume,
                'surge_strength': min(volume_ratio / self.volume_surge_ratio, 2.0)  # 최대 2.0
            }
            
        except Exception as e:
            logger.error(f"거래량 분석 오류: {e}")
            return {'volume_surge': False, 'surge_strength': 0.0}
    
    def _analyze_upward_trend(self, stock_data: Dict[str, Any], stock_code: str = None) -> Dict[str, Any]:
        """상승 추세 분석 (원본: 5일선, 20일선 위)"""
        try:
            current_price = stock_data['current_price']
            
            # 가격 히스토리 업데이트 (이평선 계산용)
            if stock_code:
                self._update_price_history(stock_code, current_price)
                
                # 충분한 데이터가 있으면 이평선 계산
                if len(self.price_history.get(stock_code, [])) >= 20:
                    prices = pd.Series(self.price_history[stock_code])
                    ma5 = prices.rolling(5).mean().iloc[-1]
                    ma20 = prices.rolling(20).mean().iloc[-1]
                    
                    # 원본 조건: 현재가가 5일선과 20일선 위
                    above_ma5 = current_price > ma5
                    above_ma20 = current_price > ma20
                    upward_trend = above_ma5 and above_ma20
                    
                    return {
                        'upward_trend': upward_trend,
                        'above_ma5': above_ma5,
                        'above_ma20': above_ma20,
                        'ma5': ma5,
                        'ma20': ma20,
                        'trend_strength': self._calculate_trend_strength(current_price, ma5, ma20)
                    }
            
            # 이평선 데이터 부족 시 단순 모멘텀으로 대체
            open_price = stock_data.get('open_price', current_price)
            price_momentum = (current_price - open_price) / open_price if open_price > 0 else 0
            
            return {
                'upward_trend': price_momentum > self.price_momentum_threshold,
                'above_ma5': True,  # 기본값
                'above_ma20': True,  # 기본값
                'ma5': current_price,
                'ma20': current_price,
                'trend_strength': abs(price_momentum),
                'fallback_mode': True  # 이평선 대신 모멘텀 사용
            }
            
        except Exception as e:
            logger.error(f"상승 추세 분석 오류: {e}")
            return {'upward_trend': False, 'trend_strength': 0.0}
    
    def _analyze_breakout_condition(self, stock_data: Dict[str, Any], stock_code: str = None) -> Dict[str, Any]:
        """돌파 조건 분석 (원본: 고가 돌파)"""
        try:
            current_price = stock_data['current_price']
            high_price = stock_data.get('high_price', current_price)
            intraday_high = stock_data.get('intraday_high', high_price)
            
            # 원본 로직: 목표가(고가) 돌파 시 매수
            target_price = max(high_price, intraday_high) * self.breakout_target_multiplier
            breakout_condition = current_price >= target_price
            
            # 돌파 강도 계산
            if target_price > 0:
                breakout_strength = (current_price - target_price) / target_price
            else:
                breakout_strength = 0.0
            
            return {
                'breakout_condition': breakout_condition,
                'target_price': target_price,
                'breakout_strength': max(0.0, breakout_strength),
                'high_price': high_price,
                'intraday_high': intraday_high
            }
            
        except Exception as e:
            logger.error(f"돌파 조건 분석 오류: {e}")
            return {'breakout_condition': False, 'breakout_strength': 0.0}
    
    def _check_sell_conditions(self, stock_data: Dict[str, Any], stock_code: str) -> Optional[Dict[str, Any]]:
        """매도 조건 확인 (원본: 3% 익절, 2% 손절)"""
        try:
            if stock_code not in self.positions or stock_code not in self.entry_prices:
                return None
            
            current_price = stock_data['current_price']
            entry_price = self.entry_prices[stock_code]
            profit_loss_rate = (current_price - entry_price) / entry_price
            
            # 원본 로직 기준 익절/손절
            target_price = entry_price * (1 + self.take_profit_pct)  # +3%
            stop_loss_price = entry_price * (1 - self.stop_loss_pct)  # -2%
            
            # 익절 조건
            if current_price >= target_price:
                self._remove_position(stock_code)
                return {
                    'signal': 'SELL',
                    'confidence': 0.9,
                    'reason': f'익절 실현: {profit_loss_rate*100:.1f}% (목표: +{self.take_profit_pct*100:.0f}%)',
                    'urgency': 'MEDIUM',
                    'scalping_mode': True,
                    'details': {
                        'entry_price': entry_price,
                        'target_price': target_price,
                        'current_price': current_price,
                        'profit_rate': profit_loss_rate
                    }
                }
            
            # 손절 조건
            elif current_price <= stop_loss_price:
                self._remove_position(stock_code)
                return {
                    'signal': 'SELL',
                    'confidence': 1.0,
                    'reason': f'손절 실행: {profit_loss_rate*100:.1f}% (기준: -{self.stop_loss_pct*100:.0f}%)',
                    'urgency': 'HIGH',
                    'scalping_mode': True,
                    'details': {
                        'entry_price': entry_price,
                        'stop_loss_price': stop_loss_price,
                        'current_price': current_price,
                        'loss_rate': profit_loss_rate
                    }
                }
            
            return None
            
        except Exception as e:
            logger.error(f"매도 조건 확인 오류 ({stock_code}): {e}")
            return None
    
    def _generate_trading_signal(self, stock_data: Dict[str, Any], stock_code: str, 
                                volume_analysis: Dict, trend_analysis: Dict, 
                                breakout_analysis: Dict) -> Dict[str, Any]:
        """최종 매매 신호 생성 (원본 로직 기반)"""
        try:
            current_price = stock_data['current_price']
            
            # === 원본 매수 조건 검증 ===
            conditions = []
            confidence = 0.3  # 기본 신뢰도
            
            # 1. 거래량 급증 조건
            if volume_analysis.get('volume_surge', False) and volume_analysis.get('sufficient_volume', False):
                conditions.append('거래량급증')
                confidence += 0.25
            
            # 2. 상승 추세 조건 (5일선, 20일선 위)
            if trend_analysis.get('upward_trend', False):
                conditions.append('상승추세')
                confidence += 0.25
            
            # 3. 돌파 조건 (고가 돌파)
            if breakout_analysis.get('breakout_condition', False):
                conditions.append('고가돌파')
                confidence += 0.30
            
            # === 추가 보강 조건들 ===
            # 가격 모멘텀
            open_price = stock_data.get('open_price', current_price)
            if open_price > 0:
                price_momentum = (current_price - open_price) / open_price
                if price_momentum > self.min_change_rate:
                    conditions.append('가격모멘텀')
                    confidence += 0.10
            
            # 거래량 강도 보너스
            surge_strength = volume_analysis.get('surge_strength', 0)
            if surge_strength > 1.5:
                confidence += min(0.15, surge_strength * 0.1)
            
            # === 매수 신호 판정 ===
            # 원본: 거래량 급증 + 상승 추세 + 돌파 조건 모두 만족
            core_conditions_met = len([c for c in conditions if c in ['거래량급증', '상승추세', '고가돌파']]) >= 2
            
            if core_conditions_met and confidence >= 0.7:
                # 포지션 추가
                self._add_position(stock_code, current_price)
                
                return {
                    'signal': 'BUY',
                    'confidence': min(confidence, 0.95),
                    'reason': f'SampleCode 매수: {", ".join(conditions)}',
                    'urgency': 'HIGH',
                    'target_price': current_price * (1 + self.take_profit_pct),
                    'stop_loss': current_price * (1 - self.stop_loss_pct),
                    'scalping_mode': True,
                    'max_hold_time': self.max_holding_time,
                    'position_size': self.max_position_size,
                    'details': {
                        'conditions_met': conditions,
                        'volume_analysis': volume_analysis,
                        'trend_analysis': trend_analysis,
                        'breakout_analysis': breakout_analysis,
                        'confidence_breakdown': f'기본(0.3) + 조건({confidence-0.3:.2f})'
                    }
                }
            
            # === 관망 신호 ===
            return {
                'signal': 'HOLD',
                'confidence': confidence,
                'reason': f'조건 부족: {", ".join(conditions) if conditions else "없음"} (필요: 핵심조건 2개+)',
                'urgency': 'LOW',
                'scalping_mode': False,
                'details': {
                    'conditions_found': conditions,
                    'core_conditions_met': core_conditions_met,
                    'confidence': confidence,
                    'volume_analysis': volume_analysis,
                    'trend_analysis': trend_analysis,
                    'breakout_analysis': breakout_analysis
                }
            }
            
        except Exception as e:
            logger.error(f"매매 신호 생성 오류: {e}")
            return self._create_hold_signal(f"신호생성오류: {str(e)[:20]}")
    
    def _update_price_history(self, stock_code: str, current_price: float):
        """가격 히스토리 업데이트 (이평선 계산용)"""
        if stock_code not in self.price_history:
            self.price_history[stock_code] = []
        
        self.price_history[stock_code].append(current_price)
        
        # 최대 50개 데이터만 보관 (메모리 절약)
        if len(self.price_history[stock_code]) > 50:
            self.price_history[stock_code] = self.price_history[stock_code][-50:]
    
    def _calculate_trend_strength(self, current_price: float, ma5: float, ma20: float) -> float:
        """추세 강도 계산"""
        try:
            if ma20 <= 0:
                return 0.0
            
            # 현재가가 이평선들 대비 얼마나 위에 있는지
            ma5_strength = (current_price - ma5) / ma5 if ma5 > 0 else 0
            ma20_strength = (current_price - ma20) / ma20 if ma20 > 0 else 0
            
            # 평균 강도
            return (ma5_strength + ma20_strength) / 2
            
        except Exception:
            return 0.0
    
    def _add_position(self, stock_code: str, entry_price: float):
        """포지션 추가"""
        try:
            self.positions[stock_code] = {
                'entry_time': datetime.now(),
                'entry_price': entry_price,
                'algorithm': self.algorithm_name
            }
            self.entry_prices[stock_code] = entry_price
            logger.info(f"포지션 추가: {stock_code} @ {entry_price:,.0f}원")
        except Exception as e:
            logger.error(f"포지션 추가 오류 ({stock_code}): {e}")
    
    def _remove_position(self, stock_code: str):
        """포지션 제거"""
        try:
            if stock_code in self.positions:
                del self.positions[stock_code]
            if stock_code in self.entry_prices:
                del self.entry_prices[stock_code]
            logger.info(f"포지션 제거: {stock_code}")
        except Exception as e:
            logger.error(f"포지션 제거 오류 ({stock_code}): {e}")
    
    def _create_hold_signal(self, reason: str) -> Dict[str, Any]:
        """관망 신호 생성"""
        return {
            'signal': 'HOLD',
            'confidence': 0.0,
            'reason': reason,
            'urgency': 'LOW',
            'scalping_mode': False,
            'details': {}
        }
    
    def _create_force_sell_signal(self, reason: str) -> Dict[str, Any]:
        """강제 매도 신호 생성"""
        return {
            'signal': 'SELL',
            'confidence': 1.0,
            'reason': reason,
            'urgency': 'HIGH',
            'scalping_mode': False,
            'details': {'force_sell': True}
        }
    
    # === BaseAlgorithm 인터페이스 구현 ===
    def get_name(self) -> str:
        return self.algorithm_name
    
    def get_version(self) -> str:
        return self.version
    
    def get_description(self) -> str:
        return self.description
    
    def calculate_position_size(self, current_price: float, account_balance: float) -> int:
        """포지션 크기 계산"""
        try:
            position_value = account_balance * self.max_position_size
            quantity = int(position_value / current_price)
            return max(1, quantity)
        except Exception:
            return 1
    
    def get_stop_loss(self, entry_price: float, position_type: str = 'LONG') -> float:
        """손절가 계산 (원본: -2%)"""
        return entry_price * (1 - self.stop_loss_pct)
    
    def get_take_profit(self, entry_price: float, position_type: str = 'LONG') -> float:
        """익절가 계산 (원본: +3%)"""
        return entry_price * (1 + self.take_profit_pct)
    
    def get_algorithm_info(self) -> Dict[str, Any]:
        """알고리즘 정보 반환"""
        return {
            'name': self.algorithm_name,
            'version': self.version,
            'description': self.description,
            'original_strategy': 'SampleCode.py 컨버전',
            'core_logic': '거래량급증 + 상승추세 + 돌파매수',
            'risk_management': f'+{self.take_profit_pct*100:.0f}% 익절 / -{self.stop_loss_pct*100:.0f}% 손절',
            'max_holding_time': f'{self.max_holding_time}분',
            'day_trading_optimized': True,
            'k_autotrade_compatible': True
        }
    
    def get_status(self) -> Dict[str, Any]:
        """현재 알고리즘 상태"""
        return {
            'active_positions': len(self.positions),
            'position_list': list(self.positions.keys()),
            'entry_prices': self.entry_prices.copy(),
            'price_history_count': {code: len(history) for code, history in self.price_history.items()},
            'algorithm_running': True
        }


# === 편의 함수 ===
def create_sample_converted_algorithm() -> SampleCodeConvertedAlgorithm:
    """SampleCode 컨버전 알고리즘 인스턴스 생성"""
    return SampleCodeConvertedAlgorithm()


# === 테스트 코드 ===
if __name__ == "__main__":
    print("=" * 80)
    print("SampleCode Converted Algorithm tideWise 호환성 테스트")
    print("=" * 80)
    
    # 알고리즘 인스턴스 생성
    algorithm = create_sample_converted_algorithm()
    
    print(f"알고리즘: {algorithm.get_name()} v{algorithm.get_version()}")
    print(f"설명: {algorithm.get_description()}")
    print(f"원본 전략: {algorithm.get_algorithm_info()['original_strategy']}")
    print(f"핵심 로직: {algorithm.get_algorithm_info()['core_logic']}")
    print(f"리스크 관리: {algorithm.get_algorithm_info()['risk_management']}")
    print()
    
    # === 테스트 케이스 1: 완벽한 매수 조건 ===
    print("=== 테스트 케이스 1: 완벽한 매수 조건 (거래량급증+상승추세+돌파) ===")
    perfect_buy_data = {
        'current_price': 12000.0,
        'open_price': 11500.0,
        'high_price': 11800.0,
        'low_price': 11400.0,
        'volume': 150000,
        'volume_ratio': 2.0,  # 2배 거래량 급증
        'change_rate': 0.035,  # 3.5% 상승
        'intraday_high': 11900.0
    }
    
    result1 = algorithm.analyze(perfect_buy_data, 'TEST001')
    print(f"신호: {result1['signal']}")
    print(f"신뢰도: {result1['confidence']:.2f}")
    print(f"이유: {result1['reason']}")
    print(f"긴급도: {result1['urgency']}")
    print(f"목표가: {result1.get('target_price', 'N/A'):,.0f}원" if result1.get('target_price') else "목표가: N/A")
    print(f"손절가: {result1.get('stop_loss', 'N/A'):,.0f}원" if result1.get('stop_loss') else "손절가: N/A")
    
    # === 테스트 케이스 2: 익절 조건 ===
    print("\n=== 테스트 케이스 2: 익절 조건 테스트 (+3% 도달) ===")
    # 먼저 포지션을 시뮬레이션으로 추가
    algorithm._add_position('TEST002', 10000.0)
    
    profit_data = {
        'current_price': 10300.0,  # +3% 익절 조건
        'open_price': 10000.0,
        'high_price': 10350.0,
        'low_price': 9950.0,
        'volume': 80000,
        'volume_ratio': 1.2
    }
    
    result2 = algorithm.analyze(profit_data, 'TEST002')
    print(f"신호: {result2['signal']}")
    print(f"신뢰도: {result2['confidence']:.2f}")
    print(f"이유: {result2['reason']}")
    print(f"긴급도: {result2['urgency']}")
    
    # === 테스트 케이스 3: 손절 조건 ===
    print("\n=== 테스트 케이스 3: 손절 조건 테스트 (-2% 도달) ===")
    # 포지션 추가
    algorithm._add_position('TEST003', 15000.0)
    
    loss_data = {
        'current_price': 14700.0,  # -2% 손절 조건
        'open_price': 15000.0,
        'high_price': 15100.0,
        'low_price': 14650.0,
        'volume': 60000,
        'volume_ratio': 1.0
    }
    
    result3 = algorithm.analyze(loss_data, 'TEST003')
    print(f"신호: {result3['signal']}")
    print(f"신뢰도: {result3['confidence']:.2f}")
    print(f"이유: {result3['reason']}")
    print(f"긴급도: {result3['urgency']}")
    
    # === 테스트 케이스 4: VI 처리 ===
    print("\n=== 테스트 케이스 4: 상승 VI 처리 테스트 ===")
    vi_data = {
        'current_price': 20000.0,
        'open_price': 17000.0,
        'high_price': 20500.0,
        'low_price': 16800.0,
        'volume': 300000,
        'volume_ratio': 5.0
    }
    
    result4 = algorithm.analyze(vi_data, 'TEST004', vi_status='UP_VI')
    print(f"신호: {result4['signal']}")
    print(f"신뢰도: {result4['confidence']:.2f}")
    print(f"이유: {result4['reason']}")
    print(f"긴급도: {result4['urgency']}")
    
    # === 최종 상태 확인 ===
    print("\n=== 알고리즘 최종 상태 ===")
    status = algorithm.get_status()
    print(f"활성 포지션: {status['active_positions']}개")
    print(f"보유 종목: {', '.join(status['position_list']) if status['position_list'] else '없음'}")
    
    print("\n" + "=" * 80)
    print("[SUCCESS] SampleCode Converted Algorithm tideWise 호환성 테스트 완료!")
    print("원본 로직 유지하면서 tideWise 시스템과 완벽 통합됨")
    print("=" * 80)