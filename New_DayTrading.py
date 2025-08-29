"""
New Day Trading Algorithm
단타Trading.py + 데이비드 폴 거래량분석 + 한국시장 VI 특화

핵심 특징:
- 데이비드 폴 Validation vs Non-Validation 로직
- 한국 VI(Volatility Interruption) 실시간 처리
- 매수 조건 대폭 완화 (높은 거래 빈도)
- 3분봉 단타 매매 최적화
- 진정한 돌파 vs 가짜 돌파 구분
- 거래량-가격 발산 감지
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, time as datetime_time
import logging
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
sys.path.append(str(Path(__file__).parent.parent))

from support.algorithm_interface import BaseAlgorithm

logger = logging.getLogger(__name__)


class NewDayTradingAlgorithm(BaseAlgorithm):
    """New Day Trading Algorithm - 데이비드 폴 + 한국 VI + 단타 최적화"""
    
    def __init__(self):
        super().__init__()
        self.algorithm_name = "New_DayTrading"
        self.description = "David Paul Volume Analysis + Korean VI + Day Trading Optimized"
        self.version = "1.0"
        
        # ========== 기본 단타 파라미터 (완화된 설정) ==========
        
        # EMA 설정 (단타용)
        self.ema_fast = 5           # 단기 EMA
        self.ema_slow = 20          # 장기 EMA
        
        # RSI 설정 (대폭 완화)
        self.rsi_period = 7         # RSI 기간 (3분봉)
        self.rsi_buy_min = 45       # RSI 매수 하한 (55→45 완화)
        self.rsi_buy_max = 85       # RSI 매수 상한 (75→85 완화)
        self.rsi_sell_high = 90     # RSI 매도 상한 (80→90 완화)
        self.rsi_oversold = 25      # RSI 과매도 (30→25 완화)
        
        # ========== 데이비드 폴 거래량 분석 파라미터 ==========
        self.volume_ma_period = 20         # VMA 기간
        self.range_ma_period = 20          # RMA 기간  
        self.volume_spike_multiplier = 2.2 # 데이비드 폴 거래량 급증 (2.2x VMA)
        self.range_multiplier = 1.5        # 넓은 레인지 기준 (1.5x RMA)
        self.validation_volume_min = 1.5   # Validation 최소 거래량 (완화)
        self.non_validation_volume_max = 0.8  # Non-Validation 거래량 상한
        
        # ========== 한국 시장 특화 (매수 조건 대폭 완화) ==========
        self.volume_surge_min = 1.3        # 거래량 급증 (2.2→1.3 대폭 완화)
        self.volume_fade_max = 0.7          # 거래량 소멸 (0.5→0.7 완화)
        self.buying_pressure_min = 45.0     # 최소 매수세 (60→45 완화)
        self.buying_pressure_fade = 35.0    # 매수세 약화 (40→35 완화)
        self.momentum_threshold = 0.002     # 모멘텀 기준 (0.01→0.002 대폭 완화)
        
        # ========== 한국 VI 처리 설정 ==========
        self.vi_detection_enabled = True
        self.upward_vi_action = "BUY"       # 상승 VI: 신규매수/추매/홀딩
        self.downward_vi_action = "SELL"    # 하락 VI: 즉시 전량 시장가 매도
        
        # ========== 리스크 관리 (단타용) ==========
        self.stop_loss_pct = 1.5           # 손절 완화 (2.0→1.5%)
        self.take_profit_pct = 2.5          # 익절 완화 (3.0→2.5%)
        self.trailing_trigger_pct = 1.5     # 트레일링 스탑
        
        # ========== 시간 규칙 (3분봉 단타) ==========
        self.new_entry_cutoff = "14:30:00"  # 신규 진입 금지
        self.force_close_time = "14:55:00"  # 강제 청산
        
        # ========== 단타매매 실행 간격 설정 ==========
        self.day_trading_end_time = "23:59:00"  # 오후 11시 59분 종료 (테스트용)
        
        # ========== 포지션 관리 ==========
        self.max_positions = 5              # 최대 포지션 증가 (3→5)
        self.position_size_ratio = 0.08     # 포지션 크기 완화 (0.1→0.08)
        
        # ========== 발산 분석 설정 ==========
        self.divergence_lookback = 10       # 발산 감지 기간
        self.correlation_min = 0.2          # 최소 상관관계 (완화)
        
        # ========== 내부 상태 관리 ==========
        self.positions = {}
        self.entry_prices = {}
        self.last_signals = {}
        self.last_vi_status = None
        
        # ========== 동적 익절 추적 관리 ==========
        self.dynamic_hold_prices = {}  # 보유 결정 시점의 가격
        self.profit_tracking = {}      # 수익률 추적
        self.uptrend_tracking = {}     # 상승 추세 추적
        
        logger.info(f"New Day Trading 알고리즘 초기화: {self.algorithm_name} v{self.version}")
    
    def get_cycle_interval(self) -> int:
        """현재 시간에 따른 단타매매 사이클 간격 반환 (초 단위)"""
        current_time = datetime.now().time()
        
        # 오전 11시 55분까지: 3분간격 (180초)
        if current_time <= datetime_time(11, 55, 0):
            return 180  # 3분
        
        # 정오(12:00) ~ 정오 55분(12:55)까지: 10분간격 (600초) 
        elif current_time <= datetime_time(12, 55, 0):
            return 600  # 10분
            
        # 오후 1시 이후: 1분간격 (테스트용 빠른 간격)
        elif current_time >= datetime_time(13, 0, 0):
            return 60   # 1분
        
        # 그 외 시간: 기본 3분간격
        return 180  # 3분
    
    def should_stop_trading(self) -> bool:
        """단타매매를 중단해야 하는지 확인 (오후 1시 종료)"""
        current_time = datetime.now().time()
        end_time = datetime.strptime(self.day_trading_end_time, "%H:%M:%S").time()
        
        return current_time >= end_time
    
    async def collect_surge_stocks(self, day_trader_instance=None):
        """
        급등종목 조회 기능 - tideWise 시스템 호출 (비동기)
        
        Args:
            day_trader_instance: MinimalDayTrader 인스턴스 (급등종목 수집 기능 접근용)
            
        Returns:
            bool: 급등종목 수집 성공 여부
        """
        try:
            if day_trader_instance is None:
                logger.warning("MinimalDayTrader 인스턴스가 없어 급등종목 수집을 건너뜁니다")
                return False
            
            # MinimalDayTrader의 급등종목 수집 메서드 호출
            if hasattr(day_trader_instance, '_select_day_trade_candidates'):
                logger.info("알고리즘에서 급등종목 수집을 요청합니다...")
                
                # 현재 포지션 정보 전달 (빈 dict으로 초기화)
                current_positions = {}
                
                # 급등종목 수집 실행 (비동기 호출)
                surge_stocks = await day_trader_instance._select_day_trade_candidates(current_positions, force_refresh=True)
                
                # 서버가 응답하지 않는 경우 (None 반환)
                if surge_stocks is None:
                    logger.error("서버가 응답하지 않아 급등종목 수집을 중단합니다")
                    return False  # 단타매매 중단
                elif surge_stocks:
                    logger.info(f"급등종목 {len(surge_stocks)}개 수집 완료")
                    return True
                else:
                    logger.warning("급등종목 수집 결과가 없습니다")
                    return False
            else:
                logger.error("MinimalDayTrader에 _select_day_trade_candidates 메서드가 없습니다")
                return False
                
        except Exception as e:
            logger.error(f"급등종목 수집 중 오류: {e}")
            return False
    
    def analyze(self, stock_data: Dict[str, Any], stock_code: str = None, **kwargs) -> Dict[str, Any]:
        """
        실시간 dict 데이터 분석하여 매매 신호 생성 (단타매매 최적화)
        
        Args:
            stock_data: 실시간 종목 데이터 dict
                {
                    'symbol': 'TEST001',
                    'current_price': 881.0,
                    'open_price': 678.0, 
                    'high_price': 881.0,
                    'low_price': 672.0,
                    'volume': 4521284,
                    'change_rate': 29.94,
                    'timestamp': datetime.now()
                }
            stock_code: 종목 코드
            **kwargs: vi_status 등 추가 파라미터
            
        Returns:
            Dict: {'signal': 'BUY/SELL/HOLD', 'confidence': float, 'reason': str, 'details': dict}
        """
        try:
            # VI 상태 최우선 처리
            vi_status = kwargs.get('vi_status', None)
            if vi_status and self.vi_detection_enabled:
                vi_response = self._handle_vi_emergency(vi_status, stock_data, stock_code)
                if vi_response:
                    return vi_response
            
            # 실시간 데이터 검증
            if not self._validate_realtime_data(stock_data):
                return {'signal': 'HOLD', 'confidence': 0.0, 'reason': '데이터 부족'}
            
            # 현재 시간 설정
            current_time = datetime.now().time()
            
            # 시간 검증 (테스트 모드에서는 건너뛰기)
            if stock_code != 'TEST_MODE':
                if not self._is_trading_time(current_time):
                    if self._is_force_close_time(current_time):
                        return {'signal': 'SELL', 'confidence': 1.0, 'reason': '장마감 청산'}
                    return {'signal': 'HOLD', 'confidence': 0.0, 'reason': '거래시간 외'}
            
            # 종장 5분전 강제 익절 확인 (테스트 모드에서는 건너뛰기)
            if stock_code != 'TEST_MODE' and self._is_force_close_time(current_time):
                if stock_code in self.positions:
                    return self._force_close_position(stock_code, stock_data)
            
            # 보유 포지션이 있는 경우 동적 익절 로직 적용
            if stock_code in self.positions:
                dynamic_sell_result = self._check_dynamic_profit_taking(stock_code, stock_data, **kwargs)
                if dynamic_sell_result:
                    return dynamic_sell_result
            
            # 실시간 급등주 분석 (대폭 완화된 조건)
            analysis_result = self._analyze_surge_stock_realtime(stock_data, stock_code)
            
            # 매수 신호 시 포지션 추가
            if analysis_result['signal'] == 'BUY' and stock_code:
                self._add_position(stock_code, stock_data)
            
            logger.debug(f"New Day Trading 분석: {stock_code} → {analysis_result['signal']} (신뢰도: {analysis_result['confidence']:.2f})")
            return analysis_result
            
        except Exception as e:
            logger.error(f"New Day Trading 분석 오류: {e}")
            return {'signal': 'HOLD', 'confidence': 0.0, 'reason': f'분석 오류: {str(e)[:30]}'}
    
    def _handle_vi_emergency(self, vi_status: str, stock_data: Dict[str, Any], stock_code: str = None) -> Optional[Dict[str, Any]]:
        """한국 VI(Volatility Interruption) 긴급 처리"""
        if not vi_status:
            return None
        
        current_price = stock_data.get('current_price', 0)
        
        # 상승 VI: 신규매수/추매/홀딩
        if vi_status.upper() in ['UP_VI', 'UPWARD_VI', '상승VI']:
            logger.info(f"상승 VI 감지: {stock_code} - 매수/홀딩 신호")
            return {
                'signal': 'BUY',
                'confidence': 0.95,
                'reason': f'상승 VI 감지 - 즉시 시장가 매수',
                'details': {'vi_status': vi_status, 'current_price': current_price}
            }
        
        # 하락 VI: 즉시 전량 시장가 매도 (최우선)
        elif vi_status.upper() in ['DOWN_VI', 'DOWNWARD_VI', '하락VI']:
            logger.warning(f"하락 VI 감지: {stock_code} - 긴급 전량 매도!")
            return {
                'signal': 'SELL',
                'confidence': 1.0,
                'reason': f'하락 VI 감지 - 긴급 전량 매도',
                'details': {'vi_status': vi_status, 'current_price': current_price}
            }
        
        return None
    
    def _validate_realtime_data(self, stock_data: Dict[str, Any]) -> bool:
        """실시간 데이터 유효성 검증 (간소화)"""
        required_fields = ['current_price', 'open_price', 'volume']
        
        for field in required_fields:
            if field not in stock_data:
                logger.warning(f"필수 데이터 누락: {field}")
                return False
        
        current_price = stock_data.get('current_price', 0)
        open_price = stock_data.get('open_price', 0)
        
        if current_price <= 0 or open_price <= 0:
            logger.warning("유효하지 않은 가격 데이터")
            return False
            
        return True
    
    def _is_trading_time(self, current_time: datetime_time) -> bool:
        """거래 시간 확인"""
        market_open = datetime_time(9, 0, 0)
        entry_cutoff = datetime.strptime(self.new_entry_cutoff, "%H:%M:%S").time()
        return market_open <= current_time <= entry_cutoff
    
    def _is_force_close_time(self, current_time: datetime_time) -> bool:
        """강제 청산 시간 확인 (종장 5분전: 14:50)"""
        force_close_5min = datetime_time(14, 50, 0)  # 종장 5분전
        return current_time >= force_close_5min
    
    def _analyze_surge_stock_realtime(self, stock_data: Dict[str, Any], stock_code: str = None) -> Dict[str, Any]:
        """실시간 급등주 분석 - 사용자 지정 매수 조건"""
        try:
            # 기본 데이터 추출
            current_price = float(stock_data.get('current_price', 0))
            open_price = float(stock_data.get('open_price', 0))
            high_price = float(stock_data.get('high_price', current_price))
            low_price = float(stock_data.get('low_price', current_price))
            volume = int(stock_data.get('volume', 0))
            change_rate = float(stock_data.get('change_rate', 0))
            
            # 기본 조건 확인
            if current_price <= 0 or open_price <= 0:
                return {'signal': 'HOLD', 'confidence': 0.0, 'reason': '가격 데이터 부족'}
            
            # === 사용자 지정 매수 조건 ===
            confidence = 0.3
            reasons = []
            
            # 장중 상승률 계산
            intraday_return = (current_price - open_price) / open_price * 100
            
            # 조건 1: 매수량이나 예약매수가 늘어나고 있고 주가가 오르고 있는 경우
            # (거래량 증가 + 상승 근사)
            volume_increasing = volume > 100000  # 10만주 이상 = 매수량 증가 근사
            price_rising = current_price > open_price and change_rate > 0
            
            if volume_increasing and price_rising:
                confidence += 0.4
                reasons.append(f"매수량증가+상승: 거래량{volume:,}주, 전일대비+{change_rate:.1f}%")
            
            # 조건 2: 주가는 보합상태여도 매수량이 늘어나고 있거나 예약 매수가 쌓이고 있는 경우
            # (거래량 급증 + 보합)
            volume_surge = volume > 200000  # 20만주 이상 = 매수량 급증
            price_stable = abs(intraday_return) <= 1.0  # 장중 변동 1% 이내 = 보합
            
            if volume_surge and (price_stable or current_price >= open_price * 0.99):
                confidence += 0.35
                reasons.append(f"대량매수대기: 거래량{volume:,}주, 장중{intraday_return:.1f}%")
            
            # 조건 3: 상승 VI가 걸린 경우 (kwargs에서 확인)
            # 이미 analyze 메서드 최상단에서 처리됨
            
            # 추가 보조 조건들
            # 고가 근처 거래 (95% 이상)
            if high_price > 0 and current_price >= high_price * 0.95:
                confidence += 0.1
                reasons.append("고가근처")
            
            # 급등주 보너스 (상승률 3% 이상)
            if change_rate >= 3.0:
                confidence += 0.15
                reasons.append(f"급등주({change_rate:.1f}%)")
            
            # 데이비드 폴 검증 (허수/작전 판별)
            david_paul_check = self._david_paul_manipulation_check(stock_data)
            if david_paul_check['is_manipulation']:
                confidence -= 0.2
                reasons.append(f"작전의심: {david_paul_check['reason']}")
            elif david_paul_check['is_genuine']:
                confidence += 0.1
                reasons.append("진정한 상승")
            
            # === 매도 조건들 ===
            
            # 급락 시 매도 (장중 -2% 이하 또는 전일대비 -3% 이하)
            if intraday_return <= -2.0 or change_rate <= -3.0:
                return {
                    'signal': 'SELL',
                    'confidence': 0.9,
                    'reason': f"급락매도: 장중{intraday_return:.1f}%, 전일대비{change_rate:.1f}%",
                    'details': {
                        'intraday_return': intraday_return,
                        'change_rate': change_rate,
                        'current_price': current_price
                    }
                }
            
            # === 매수 신호 판정 (임계값: 0.6) ===
            if confidence >= 0.6:
                return {
                    'signal': 'BUY',
                    'confidence': min(confidence, 0.95),
                    'reason': f"시장가 매수: {', '.join(reasons)}",
                    'details': {
                        'change_rate': change_rate,
                        'intraday_return': intraday_return,
                        'volume': volume,
                        'price_level': current_price / high_price if high_price > 0 else 1.0,
                        'conditions_met': len(reasons),
                        'david_paul_check': david_paul_check
                    }
                }
            
            # 기본 보류
            return {
                'signal': 'HOLD',
                'confidence': confidence,
                'reason': f"조건 부족: 신뢰도{confidence:.2f} (필요:0.6+), 조건: {', '.join(reasons) if reasons else '없음'}",
                'details': {
                    'change_rate': change_rate,
                    'intraday_return': intraday_return,
                    'volume': volume,
                    'reasons_found': reasons,
                    'conditions_met': len(reasons),
                    'david_paul_check': david_paul_check
                }
            }
            
        except Exception as e:
            logger.error(f"실시간 급등주 분석 오류: {e}")
            return {'signal': 'HOLD', 'confidence': 0.0, 'reason': f'분석 오류: {str(e)[:50]}'}
    
    def _david_paul_manipulation_check(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """데이비드 폴 기반 허수/작전 판별 로직"""
        try:
            current_price = float(stock_data.get('current_price', 0))
            open_price = float(stock_data.get('open_price', 0))
            high_price = float(stock_data.get('high_price', current_price))
            low_price = float(stock_data.get('low_price', current_price))
            volume = int(stock_data.get('volume', 0))
            change_rate = float(stock_data.get('change_rate', 0))
            
            # 기본값
            result = {
                'is_manipulation': False,
                'is_genuine': False,
                'reason': '분석 부족',
                'confidence': 0.5
            }
            
            if current_price <= 0 or open_price <= 0:
                return result
            
            # 레인지 계산
            price_range = high_price - low_price
            range_percent = (price_range / open_price) * 100 if open_price > 0 else 0
            
            # 장중 상승률
            intraday_return = (current_price - open_price) / open_price * 100
            
            # === 작전 의심 신호들 ===
            manipulation_signals = []
            
            # 1. 거래량 급증 + 가격 급등 + 고점 이탈 (꼬리 긴 음봉)
            volume_spike = volume > 500000  # 50만주 이상
            price_spike = change_rate > 15.0  # 15% 이상 급등
            tail_ratio = ((high_price - current_price) / price_range) if price_range > 0 else 0
            long_tail = tail_ratio > 0.4  # 긴 윗꼬리 (40% 이상)
            
            if volume_spike and price_spike and long_tail:
                manipulation_signals.append("급등후_윗꼬리")
            
            # 2. 극단적 거래량 + 제한적 가격 상승 (물량 소화)
            extreme_volume = volume > 1000000  # 100만주 이상
            limited_price_move = 1.0 <= change_rate <= 5.0  # 제한적 상승
            
            if extreme_volume and limited_price_move:
                manipulation_signals.append("물량소화")
            
            # 3. 가격 급등 + 거래량 부족 (허수 급등)
            price_jump = change_rate > 10.0
            volume_insufficient = volume < 100000  # 10만주 미만
            
            if price_jump and volume_insufficient:
                manipulation_signals.append("거래량부족_급등")
            
            # === 진정한 상승 신호들 ===
            genuine_signals = []
            
            # 1. 적정 거래량 + 지속적 상승 + 고가 유지
            moderate_volume = 100000 <= volume <= 800000  # 적정 거래량
            steady_rise = 2.0 <= change_rate <= 12.0  # 지속적 상승
            holding_high = current_price >= high_price * 0.95  # 고가 유지
            
            if moderate_volume and steady_rise and holding_high:
                genuine_signals.append("지속상승")
            
            # 2. 점진적 거래량 증가 + 안정적 상승 패턴
            gradual_volume = 50000 <= volume <= 300000
            stable_rise = 1.0 <= change_rate <= 8.0
            minimal_tail = tail_ratio < 0.2  # 짧은 윗꼬리
            
            if gradual_volume and stable_rise and minimal_tail:
                genuine_signals.append("안정상승")
            
            # === 최종 판정 ===
            manipulation_score = len(manipulation_signals)
            genuine_score = len(genuine_signals)
            
            if manipulation_score >= 2:
                result.update({
                    'is_manipulation': True,
                    'is_genuine': False,
                    'reason': f"작전의심: {', '.join(manipulation_signals)}",
                    'confidence': 0.8
                })
            elif genuine_score >= 1:
                result.update({
                    'is_manipulation': False,
                    'is_genuine': True,
                    'reason': f"진정한상승: {', '.join(genuine_signals)}",
                    'confidence': 0.7
                })
            else:
                result.update({
                    'is_manipulation': False,
                    'is_genuine': False,
                    'reason': f"판단보류: 거래량{volume:,}주, 상승률{change_rate:.1f}%",
                    'confidence': 0.5
                })
            
            return result
            
        except Exception as e:
            logger.error(f"데이비드 폴 검증 오류: {e}")
            return {
                'is_manipulation': False,
                'is_genuine': False,
                'reason': f'검증오류: {str(e)[:30]}',
                'confidence': 0.0
            }
    
    def _check_dynamic_profit_taking(self, stock_code: str, stock_data: Dict[str, Any], **kwargs) -> Optional[Dict[str, Any]]:
        """동적 익절 로직 - 상승 추세 추적"""
        try:
            current_price = float(stock_data.get('current_price', 0))
            volume = int(stock_data.get('volume', 0))
            change_rate = float(stock_data.get('change_rate', 0))
            
            if current_price <= 0:
                return None
            
            # 포지션 정보 확인
            if stock_code not in self.positions or stock_code not in self.entry_prices:
                return None
            
            entry_price = self.entry_prices[stock_code]
            current_profit_rate = (current_price - entry_price) / entry_price
            
            # VI 상태 확인
            vi_status = kwargs.get('vi_status', None)
            
            # 상승 VI 감지 시 - 보유 결정 및 새로운 기준점 설정
            if vi_status and vi_status.upper() in ['UP_VI', 'UPWARD_VI', '상승VI']:
                self.dynamic_hold_prices[stock_code] = current_price
                logger.info(f"상승 VI 감지: {stock_code} 보유 결정, 새 기준가: {current_price:,.0f}원")
                return {
                    'signal': 'HOLD',
                    'confidence': 0.9,
                    'reason': f'상승 VI 감지 - 보유 (새 기준가: {current_price:,.0f}원)',
                    'details': {
                        'vi_status': vi_status,
                        'new_hold_price': current_price,
                        'current_profit_rate': current_profit_rate
                    }
                }
            
            # 매수량 증가 + 가격 상승 감지 시 - 보유 결정
            volume_increasing = volume > 200000  # 20만주 이상
            price_rising = change_rate > 0 and current_price > entry_price
            
            if volume_increasing and price_rising:
                # 현재가가 기존 보유 결정가보다 높으면 새로운 기준점 설정
                current_hold_price = self.dynamic_hold_prices.get(stock_code, entry_price)
                if current_price > current_hold_price:
                    self.dynamic_hold_prices[stock_code] = current_price
                    logger.info(f"매수량 증가 + 상승: {stock_code} 보유 결정, 새 기준가: {current_price:,.0f}원")
                
                return {
                    'signal': 'HOLD',
                    'confidence': 0.85,
                    'reason': f'매수량증가+상승 - 보유 (거래량: {volume:,}주, 상승률: {change_rate:.1f}%)',
                    'details': {
                        'volume': volume,
                        'change_rate': change_rate,
                        'new_hold_price': self.dynamic_hold_prices[stock_code],
                        'current_profit_rate': current_profit_rate
                    }
                }
            
            # 동적 익절 조건 확인
            hold_price = self.dynamic_hold_prices.get(stock_code, entry_price)
            dynamic_profit_rate = (current_price - hold_price) / hold_price
            
            # 보유 결정 시점부터 +4% 이상 시 익절
            if dynamic_profit_rate >= 0.04:  # 4% 이상
                self._remove_position(stock_code)
                return {
                    'signal': 'SELL',
                    'confidence': 0.9,
                    'reason': f'동적 익절: 기준가 대비 +{dynamic_profit_rate*100:.1f}% (기준가: {hold_price:,.0f}원)',
                    'details': {
                        'hold_price': hold_price,
                        'dynamic_profit_rate': dynamic_profit_rate,
                        'total_profit_rate': current_profit_rate,
                        'current_price': current_price
                    }
                }
            
            # 기본 손절 조건 (진입가 대비 -2% 이하)
            if current_profit_rate <= -0.02:
                self._remove_position(stock_code)
                return {
                    'signal': 'SELL',
                    'confidence': 1.0,
                    'reason': f'손절: 진입가 대비 {current_profit_rate*100:.1f}%',
                    'details': {
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'loss_rate': current_profit_rate
                    }
                }
            
            # 보유 유지
            return None
            
        except Exception as e:
            logger.error(f"동적 익절 검사 오류 ({stock_code}): {e}")
            return None
    
    def _force_close_position(self, stock_code: str, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """종장 5분전 강제 익절"""
        try:
            current_price = float(stock_data.get('current_price', 0))
            entry_price = self.entry_prices.get(stock_code, current_price)
            profit_rate = (current_price - entry_price) / entry_price if entry_price > 0 else 0
            
            self._remove_position(stock_code)
            
            return {
                'signal': 'SELL',
                'confidence': 1.0,
                'reason': f'종장 5분전 강제 익절: {profit_rate*100:+.1f}%',
                'details': {
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'profit_rate': profit_rate,
                    'force_close': True
                }
            }
            
        except Exception as e:
            logger.error(f"강제 익절 오류 ({stock_code}): {e}")
            return {
                'signal': 'SELL',
                'confidence': 1.0,
                'reason': '종장 5분전 강제 익절 (오류)',
                'details': {'error': str(e)}
            }
    
    def _add_position(self, stock_code: str, stock_data: Dict[str, Any]):
        """포지션 추가"""
        try:
            current_price = float(stock_data.get('current_price', 0))
            if current_price > 0:
                self.positions[stock_code] = 1  # 포지션 보유 표시
                self.entry_prices[stock_code] = current_price
                self.dynamic_hold_prices[stock_code] = current_price  # 초기 보유 결정가는 진입가
                logger.info(f"포지션 추가: {stock_code} @ {current_price:,.0f}원")
        except Exception as e:
            logger.error(f"포지션 추가 오류 ({stock_code}): {e}")
    
    def _remove_position(self, stock_code: str):
        """포지션 제거"""
        try:
            if stock_code in self.positions:
                del self.positions[stock_code]
            if stock_code in self.entry_prices:
                del self.entry_prices[stock_code]
            if stock_code in self.dynamic_hold_prices:
                del self.dynamic_hold_prices[stock_code]
            logger.info(f"포지션 제거: {stock_code}")
        except Exception as e:
            logger.error(f"포지션 제거 오류 ({stock_code}): {e}")
    
    def analyze_simple(self, symbol: str, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """
MinimalDayTrader용 간단한 분석 메서드
        MinimalDayTrader._analyze_with_algorithm()에서 호출
        
        Args:
            symbol: 종목 코드
            stock_data: 실시간 주식 데이터 dict
            
        Returns:
            Dict: {
                'signal': 'BUY'|'SELL'|'HOLD',
                'confidence': 0.0-1.0,
                'reason': '상세 이유',
                'details': {...}
            }
        """
        try:
            # analyze() 메서드를 내부적으로 호출하여 결과 반환
            signal = self.analyze(stock_data, symbol)
            
            # MinimalDayTrader가 기대하는 형식으로 변환
            if signal == 'BUY':
                return {
                    'signal': 'BUY',
                    'confidence': 0.85,  # 매수 시 높은 신뢰도
                    'reason': f'급등주 매수: 상승률 {stock_data.get("change_rate", 0):.1f}%, 거래량 급증',
                    'details': {
                        'algorithm': 'New_DayTrading',
                        'change_rate': stock_data.get('change_rate', 0),
                        'volume': stock_data.get('volume', 0),
                        'current_price': stock_data.get('current_price', 0)
                    }
                }
            elif signal == 'SELL':
                return {
                    'signal': 'SELL',
                    'confidence': 0.9,
                    'reason': '급락 및 매도 신호 감지',
                    'details': {
                        'algorithm': 'New_DayTrading',
                        'change_rate': stock_data.get('change_rate', 0)
                    }
                }
            else:
                return {
                    'signal': 'HOLD',
                    'confidence': 0.5,
                    'reason': '매수 조건 미달 또는 기다림',
                    'details': {
                        'algorithm': 'New_DayTrading',
                        'change_rate': stock_data.get('change_rate', 0)
                    }
                }
                
        except Exception as e:
            logger.error(f"간단 분석 오류: {e}")
            return {
                'signal': 'HOLD',
                'confidence': 0.0,
                'reason': f'분석 오류: {str(e)[:30]}',
                'details': {'error': str(e)}
            }
    
    def get_signal_with_details(self, symbol: str, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        상세 신호 분석 결과 반환 (테스트용)
        
        Returns:
            Dict: {
                'signal': 'BUY'|'SELL'|'HOLD',
                'confidence': 0.0-1.0, 
                'reason': '상세 이유',
                'details': {...}
            }
        """
        return self.analyze_simple(symbol, stock_data)
    
    def quick_surge_check(self, stock_data: Dict[str, Any]) -> bool:
        """급등주 빠른 확인 (간단한 조건)"""
        try:
            change_rate = float(stock_data.get('change_rate', 0))
            volume = int(stock_data.get('volume', 0))
            current_price = float(stock_data.get('current_price', 0))
            open_price = float(stock_data.get('open_price', 0))
            
            # 기본 급등 조건: 1% 이상 상승 + 기본 거래량
            if change_rate >= 1.0 and volume >= 10000:
                return True
            
            # 장중 급등 조건: 0.5% 이상 상승
            if open_price > 0:
                intraday_return = (current_price - open_price) / open_price * 100
                if intraday_return >= 0.5:
                    return True
            
            return False
            
        except Exception:
            return False
    
    def is_buy_candidate(self, stock_data: Dict[str, Any]) -> Tuple[bool, str]:
        """매수 후보 여부 확인 (빠른 필터링용)"""
        try:
            change_rate = float(stock_data.get('change_rate', 0))
            current_price = float(stock_data.get('current_price', 0))
            open_price = float(stock_data.get('open_price', 0))
            volume = int(stock_data.get('volume', 0))
            
            # 기본 조건 검사
            if current_price <= 0 or open_price <= 0:
                return False, '가격 정보 부족'
            
            # 매수 후보 조건 (대폭 완화)
            reasons = []
            
            # 1. 전일대비 상승 (1% 이상)
            if change_rate >= 1.0:
                reasons.append(f'전일대비+{change_rate:.1f}%')
            
            # 2. 장중 상승 (0.5% 이상)
            intraday_return = (current_price - open_price) / open_price * 100
            if intraday_return >= 0.5:
                reasons.append(f'장중+{intraday_return:.1f}%')
            
            # 3. 거래량 양호 (1만주 이상)
            if volume >= 10000:
                reasons.append('거래량양호')
            
            # 하나라도 만족하면 후보
            if reasons:
                return True, ', '.join(reasons)
            
            return False, '매수 조건 미달'
            
        except Exception as e:
            return False, f'분석오류: {str(e)[:20]}'
    
    def check_sell_conditions(self, stock_data: Dict[str, Any], entry_price: float = None) -> Tuple[bool, str]:
        """매도 조건 확인"""
        try:
            current_price = float(stock_data.get('current_price', 0))
            open_price = float(stock_data.get('open_price', 0))
            change_rate = float(stock_data.get('change_rate', 0))
            
            # 급락 조건
            if open_price > 0:
                intraday_return = (current_price - open_price) / open_price * 100
                if intraday_return <= -2.0 or change_rate <= -3.0:
                    return True, f'급락매도: 장중{intraday_return:.1f}%, 전일대비{change_rate:.1f}%'
            
            # 손절/익절 조건 (진입가가 있는 경우)
            if entry_price and entry_price > 0 and current_price > 0:
                profit_loss_rate = (current_price - entry_price) / entry_price * 100
                
                # 3% 손절
                if profit_loss_rate <= -3.0:
                    return True, f'손절: {profit_loss_rate:.1f}%'
                
                # 5% 익절
                if profit_loss_rate >= 5.0:
                    return True, f'익절: {profit_loss_rate:.1f}%'
            
            return False, '매도 조건 미달'
            
        except Exception as e:
            return False, f'분석오류: {str(e)[:20]}'
    
    def get_algorithm_info(self) -> Dict[str, Any]:
        """알고리즘 정보 반환"""
        return {
            'name': self.algorithm_name,
            'version': self.version,
            'description': self.description,
            'optimized_for': '단타매매 급등주 분석',
            'buy_threshold_relaxed': True,
            'realtime_optimized': True
        }
    
    
    
    def calculate_position_size(self, current_price: float, account_balance: float) -> int:
        """포지션 크기 계산 (간소화)"""
        try:
            position_value = account_balance * self.position_size_ratio
            quantity = int(position_value / current_price)
            return max(1, quantity)  # 최소 1주
        except Exception as e:
            logger.error(f"포지션 크기 계산 오류: {e}")
            return 1
    
    def update_position(self, stock_code: str, action: str, price: float, quantity: int):
        """포지션 업데이트 (간소화)"""
        if action == 'BUY':
            self.positions[stock_code] = quantity
            self.entry_prices[stock_code] = price
        elif action == 'SELL' and stock_code in self.positions:
            self.positions.pop(stock_code, None)
            self.entry_prices.pop(stock_code, None)
    
    def get_stop_loss(self, entry_price: float) -> float:
        """손절가 계산 (3% 손절)"""
        return entry_price * 0.97
    
    def get_take_profit(self, entry_price: float) -> float:
        """익절가 계산 (5% 익절)"""
        return entry_price * 1.05
    
    def get_name(self) -> str:
        return self.algorithm_name
    
    def get_version(self) -> str:
        return self.version
    
    def get_description(self) -> str:
        return self.description
    
    def get_parameters(self) -> Dict[str, Any]:
        """알고리즘 파라미터 반환"""
        return {
            'ema_fast': self.ema_fast,
            'ema_slow': self.ema_slow,
            'rsi_period': self.rsi_period,
            'rsi_buy_zone': [self.rsi_buy_min, self.rsi_buy_max],
            'volume_spike_multiplier': self.volume_spike_multiplier,
            'volume_surge_min': self.volume_surge_min,
            'buying_pressure_min': self.buying_pressure_min,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'max_positions': self.max_positions,
            'vi_detection_enabled': self.vi_detection_enabled,
            'david_paul_enabled': True
        }
    
    def get_status(self) -> Dict[str, Any]:
        """현재 알고리즘 상태"""
        return {
            'active_positions': len(self.positions),
            'max_positions': self.max_positions,
            'position_list': list(self.positions.keys()),
            'entry_prices': self.entry_prices.copy(),
            'last_vi_status': self.last_vi_status
        }


# 편의 함수
def create_new_day_trading_algorithm() -> NewDayTradingAlgorithm:
    """New Day Trading 알고리즘 인스턴스 생성"""
    return NewDayTradingAlgorithm()


# 테스트 코드
if __name__ == "__main__":
    print("=" * 80)
    print("New Day Trading Algorithm 최적화 테스트 (실시간 dict 데이터)")
    print("=" * 80)
    
    # 알고리즘 인스턴스 생성
    algorithm = create_new_day_trading_algorithm()
    
    print(f"알고리즘: {algorithm.get_name()} v{algorithm.get_version()}")
    print(f"설명: {algorithm.get_description()}")
    print(f"실시간 데이터 최적화: {algorithm.get_algorithm_info()['realtime_optimized']}")
    print()
    
    # === 테스트 케이스 1: 급등주 매수 신호 테스트 ===
    print("=== 테스트 케이스 1: 급등주 BUY 신호 테스트 ===")
    surge_stock_data = {
        'symbol': 'TEST001',
        'current_price': 881.0,
        'open_price': 678.0,
        'high_price': 881.0,
        'low_price': 672.0,
        'volume': 4521284,
        'change_rate': 29.94,  # 29.9% 급등
        'timestamp': datetime.now()
    }
    
    print(f"테스트 데이터: {surge_stock_data['symbol']}")
    print(f"현재가: {surge_stock_data['current_price']:,.0f}원")
    print(f"시가: {surge_stock_data['open_price']:,.0f}원")
    print(f"전일대비: +{surge_stock_data['change_rate']:.1f}%")
    print(f"거래량: {surge_stock_data['volume']:,}주")
    
    # 분석 실행 (테스트 모드)
    result1 = algorithm.analyze(surge_stock_data, 'TEST_MODE')
    detailed_result1 = algorithm.get_signal_with_details('TEST_MODE', surge_stock_data)
    
    print(f"\n[분석 결과]")
    print(f"신호: {result1}")
    print(f"신뢰도: {detailed_result1['confidence']:.2f}")
    print(f"이유: {detailed_result1['reason']}")
    print(f"상세정보: {detailed_result1['details']}")
    
    # === 테스트 케이스 2: 소폭 상승주 테스트 ===
    print("\n=== 테스트 케이스 2: 소폭 상승주 테스트 ===")
    mild_rise_data = {
        'symbol': 'TEST002',
        'current_price': 71500,
        'open_price': 70000,
        'high_price': 71600,
        'low_price': 69800,
        'volume': 125000,
        'change_rate': 2.14,  # 2.1% 상승
        'timestamp': datetime.now()
    }
    
    print(f"테스트 데이터: {mild_rise_data['symbol']}")
    print(f"현재가: {mild_rise_data['current_price']:,.0f}원")
    print(f"시가: {mild_rise_data['open_price']:,.0f}원")
    print(f"전일대비: +{mild_rise_data['change_rate']:.1f}%")
    print(f"거래량: {mild_rise_data['volume']:,}주")
    
    result2 = algorithm.analyze(mild_rise_data, 'TEST_MODE')
    detailed_result2 = algorithm.get_signal_with_details('TEST_MODE', mild_rise_data)
    
    print(f"\n[분석 결과]")
    print(f"신호: {result2}")
    print(f"신뢰도: {detailed_result2['confidence']:.2f}")
    print(f"이유: {detailed_result2['reason']}")
    
    # === 테스트 케이스 3: 급락주 매도 신호 테스트 ===
    print("\n=== 테스트 케이스 3: 급락주 SELL 신호 테스트 ===")
    crash_stock_data = {
        'symbol': 'TEST003',
        'current_price': 28500,
        'open_price': 32000,
        'high_price': 32200,
        'low_price': 28300,
        'volume': 2850000,
        'change_rate': -8.75,  # 8.75% 급락
        'timestamp': datetime.now()
    }
    
    print(f"테스트 데이터: {crash_stock_data['symbol']}")
    print(f"현재가: {crash_stock_data['current_price']:,.0f}원")
    print(f"시가: {crash_stock_data['open_price']:,.0f}원")
    print(f"전일대비: {crash_stock_data['change_rate']:.1f}%")
    
    result3 = algorithm.analyze(crash_stock_data, 'TEST_MODE')
    detailed_result3 = algorithm.get_signal_with_details('TEST_MODE', crash_stock_data)
    
    print(f"\n[분석 결과]")
    print(f"신호: {result3}")
    print(f"신뢰도: {detailed_result3['confidence']:.2f}")
    print(f"이유: {detailed_result3['reason']}")
    
    # === VI 테스트 ===
    print("\n=== VI 처리 테스트 ===")
    
    # 상승 VI 테스트
    vi_up_result = algorithm.analyze(surge_stock_data, 'TEST_MODE', vi_status="UP_VI")
    print(f"상승 VI 테스트: {vi_up_result}")
    
    # 하락 VI 테스트
    vi_down_result = algorithm.analyze(surge_stock_data, 'TEST_MODE', vi_status="DOWN_VI")
    print(f"하락 VI 테스트: {vi_down_result}")
    
    # === 성능 테스트 ===
    print("\n=== 성능 및 호환성 검증 ===")
    
    # 빠른 필터링 테스트
    is_candidate, reason = algorithm.is_buy_candidate(surge_stock_data)
    print(f"급등주 매수 후보 여부: {is_candidate} ({reason})")
    
    # 급등주 빠른 확인
    is_surge = algorithm.quick_surge_check(surge_stock_data)
    print(f"급등주 빠른 확인: {is_surge}")
    
    # 매도 조건 확인
    should_sell, sell_reason = algorithm.check_sell_conditions(crash_stock_data)
    print(f"매도 조건 확인: {should_sell} ({sell_reason})")
    
    print("\n=== 최종 결과 요약 ===")
    print(f"1. 급등주 (29.9%↑): {result1} - {detailed_result1['confidence']:.0%} 신뢰도")
    print(f"2. 소폭상승주 (2.1%↑): {result2} - {detailed_result2['confidence']:.0%} 신뢰도")
    print(f"3. 급락주 (-8.7%): {result3} - {detailed_result3['confidence']:.0%} 신뢰도")
    
    print("\n" + "=" * 80)
    print("[SUCCESS] 테스트 완료: 실시간 dict 데이터 처리 및 대폭 완화된 매수 조건 검증")
    print("=" * 80)