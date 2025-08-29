"""
tideWise 동적 매매 간격 제어 시스템
Korean Stock Auto Trading Dynamic Interval Controller

시장 상황과 매매 성과에 따라 자동매매 사이클 간격을 동적으로 조절
파일 기반 중단 신호 인식 개선을 위한 최소 4초 간격 보장
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)


class MarketCondition(Enum):
    """한국 주식 시장 상황"""
    VOLATILE = "volatile"        # 고변동성 (급등락)
    STABLE = "stable"           # 안정적 (정상 거래)
    TRENDING = "trending"       # 강한 추세 (상승/하락 지속)
    SIDEWAYS = "sideways"      # 횡보 (박스권)
    CRISIS = "crisis"          # 위기 상황 (서킷브레이커, VI 등)


class TradeResult(Enum):
    """매매 결과"""
    PROFIT = "profit"           # 수익 (7% 익절 등)
    LOSS = "loss"              # 손실
    BREAKEVEN = "breakeven"    # 무승부
    PENDING = "pending"        # 진행 중


@dataclass
class TradeRecord:
    """매매 기록"""
    timestamp: datetime
    action: str  # 'buy' or 'sell'
    symbol: str
    stock_name: str
    price: float
    quantity: int
    result: TradeResult = TradeResult.PENDING
    profit_loss: float = 0.0
    interval_before: float = 0.0  # 이전 매매와의 간격(초)


@dataclass
class tideWiseIntervalConfig:
    """tideWise용 간격 설정"""
    # 기본 간격 (초) - 파일 신호 인식을 위해 최소 4초
    base_interval: float = 180.0  # 3분 (사용자 요청으로 5분에서 단축)
    
    # 최소/최대 간격 제한 (파일 기반 중단 신호 고려)
    min_interval: float = 4.0     # 최소 4초 (ESC 신호 인식 보장)
    max_interval: float = 1800.0  # 최대 30분
    
    # 변동성 기반 승수
    volatility_multiplier: float = 1.8  # 급등락 시 간격 확대
    high_volatility_threshold: float = 3.0  # 한국 주식 기준
    
    # 손실 기반 쿨다운 (한국 투자자 성향 고려)
    loss_cooldown_multiplier: float = 2.5
    consecutive_loss_threshold: int = 2  # 2연속 손실시 쿨다운
    
    # 수익 기반 가속화
    profit_acceleration: float = 0.8  # 20% 단축
    consecutive_profit_threshold: int = 2  # 2연속 수익시 가속
    
    # 한국 시장 상황별 승수
    market_multipliers: Dict[MarketCondition, float] = field(default_factory=lambda: {
        MarketCondition.VOLATILE: 2.0,   # 급등락 시 간격 확대
        MarketCondition.STABLE: 1.0,     # 정상
        MarketCondition.TRENDING: 0.9,   # 추세 지속시 약간 가속
        MarketCondition.SIDEWAYS: 1.2,   # 박스권에서 간격 확대
        MarketCondition.CRISIS: 3.0      # 위기시 대폭 확대
    })


class tideWiseDynamicIntervalController:
    """tideWise 동적 매매 간격 제어기"""
    
    def __init__(self, config: tideWiseIntervalConfig = None):
        self.config = config or tideWiseIntervalConfig()
        
        # 매매 기록 관리
        self.trade_history: deque = deque(maxlen=100)  # 최근 100개 거래
        self.last_trade_time: Optional[datetime] = None
        
        # 상태 추적
        self.current_interval: float = self.config.base_interval
        self.consecutive_losses: int = 0
        self.consecutive_profits: int = 0
        self.total_trades: int = 0
        
        # 한국 시장 상황 분석
        self.current_market_condition: MarketCondition = MarketCondition.STABLE
        self.volatility_history: deque = deque(maxlen=20)
        
        # 스레드 안전성
        self._lock = threading.Lock()
        
        # 성능 통계
        self.performance_stats = {
            'total_profit_loss': 0.0,
            'win_rate': 0.0,
            'avg_interval': self.config.base_interval,
            'intervals_adjusted': 0,
            'emergency_adjustments': 0
        }
        
        logger.info(f"tideWise 동적 간격 제어기 초기화 완료 - 기본 간격: {self.config.base_interval}초")
    
    def calculate_next_interval(self, 
                               market_data: Optional[Dict[str, Any]] = None,
                               recent_algorithm_result: Optional[str] = None) -> float:
        """다음 매매까지의 간격 계산 (tideWise 맞춤)"""
        
        with self._lock:
            base_interval = self.config.base_interval
            
            # 1. 시장 상황 기반 조정
            market_multiplier = self.config.market_multipliers.get(
                self.current_market_condition, 1.0
            )
            interval = base_interval * market_multiplier
            
            # 2. 변동성 기반 조정 (한국 주식 특성)
            if market_data:
                volatility_adj = self._calculate_korean_market_volatility_adjustment(market_data)
                interval *= volatility_adj
            
            # 3. 연속 손실/수익 기반 조정
            performance_adj = self._calculate_performance_adjustment()
            interval *= performance_adj
            
            # 4. 시간대별 조정 (한국 장 시간)
            time_adj = self._calculate_korean_market_time_adjustment()
            interval *= time_adj
            
            # 5. KIS API 제한 준수 (한국투자증권)
            api_adj = self._calculate_kis_api_limit_adjustment()
            interval = max(interval, api_adj)
            
            # 6. 파일 기반 중단 신호 고려 (Claude CLI 환경)
            signal_adj = self._ensure_file_signal_recognition_time()
            interval = max(interval, signal_adj)
            
            # 7. 최종 제한 적용
            final_interval = np.clip(interval, 
                                   self.config.min_interval, 
                                   self.config.max_interval)
            
            self.current_interval = final_interval
            self._update_statistics()
            
            logger.debug(f"동적 간격 계산 완료: {final_interval:.1f}초 "
                        f"(기본:{base_interval}→시장:{market_multiplier}→성과:{performance_adj}→시간:{time_adj})")
            
            return final_interval
    
    def _calculate_korean_market_volatility_adjustment(self, market_data: Dict[str, Any]) -> float:
        """한국 주식 시장 변동성 기반 간격 조정"""
        try:
            # 한국 시장 특성을 고려한 변동성 지표
            price_change_rate = abs(market_data.get('price_change_rate', 0.0))
            volume_ratio = market_data.get('volume_ratio', 1.0)  # 평균 거래량 대비
            
            # 급등락 감지 (한국 시장 기준: 3% 이상 변동)
            if price_change_rate >= 3.0:
                self.current_market_condition = MarketCondition.VOLATILE
                logger.info(f"급등락 감지: 변동률 {price_change_rate:.1f}% - 간격 확대")
                return self.config.volatility_multiplier
            
            # 거래량 급증 감지 (3배 이상)
            if volume_ratio >= 3.0:
                logger.info(f"거래량 급증 감지: {volume_ratio:.1f}배 - 간격 확대")
                return 1.3
            
            # VI(변동성 완화장치) 발동 감지
            if market_data.get('vi_triggered', False):
                self.current_market_condition = MarketCondition.CRISIS
                logger.warning("VI 발동 감지 - 위기 모드 간격 적용")
                return 3.0
            
            return 1.0
            
        except Exception as e:
            logger.error(f"한국 시장 변동성 조정 계산 오류: {e}")
            return 1.0
    
    def _calculate_performance_adjustment(self) -> float:
        """성과 기반 간격 조정 (한국 투자 성향 고려)"""
        
        # 연속 손실 시 간격 확대 (쿨다운)
        if self.consecutive_losses >= self.config.consecutive_loss_threshold:
            cooldown_factor = min(
                self.consecutive_losses / self.config.consecutive_loss_threshold,
                4.0  # 최대 4배까지 (한국 투자자 심리 고려)
            )
            adjustment = self.config.loss_cooldown_multiplier * cooldown_factor
            logger.info(f"연속 손실({self.consecutive_losses}회) - 쿨다운 적용: {adjustment:.1f}배")
            return adjustment
        
        # 연속 수익 시 간격 단축 (가속화)
        if self.consecutive_profits >= self.config.consecutive_profit_threshold:
            logger.info(f"연속 수익({self.consecutive_profits}회) - 간격 가속화")
            return self.config.profit_acceleration
        
        return 1.0
    
    def _calculate_korean_market_time_adjustment(self) -> float:
        """한국 장 시간대별 조정 (09:00~15:30)"""
        now = datetime.now()
        
        # 장 시작 첫 10분: 간격 확대 (동시호가, 급변동)
        if now.hour == 9 and now.minute < 10:
            return 1.8
        
        # 장 시작 후 30분: 약간 확대 (변동성 높음)
        if now.hour == 9 and now.minute < 30:
            return 1.3
        
        # 점심 시간대 (12:00~13:00): 간격 확대 (거래량 감소)
        if 12 <= now.hour < 13:
            return 1.5
        
        # 장 마감 마지막 30분 (15:00~15:30): 간격 확대 (급변동 가능)
        if now.hour == 15:
            return 1.4
        
        # 정규 거래 시간
        return 1.0
    
    def _calculate_kis_api_limit_adjustment(self) -> float:
        """한국투자증권 API 제한 고려"""
        # KIS API: 초당 2-5건 제한 (안전하게 초당 2건)
        recent_requests = len([
            trade for trade in self.trade_history
            if trade.timestamp > datetime.now() - timedelta(seconds=60)
        ])
        
        # 1분간 요청이 많으면 간격 확대
        if recent_requests > 10:  # 10회/분 초과 시
            logger.warning(f"API 요청 과다({recent_requests}회/분) - 간격 확대")
            return 10.0  # 최소 10초 간격
        
        # 모의투자는 더 보수적인 간격 적용 (KIS 모의투자 서버가 더 엄격)
        try:
            # simple_auto_trader에서 계정 유형 확인
            import sys
            for frame_info in sys._current_frames().values():
                local_vars = frame_info.f_locals
                if 'self' in local_vars:
                    obj = local_vars['self']
                    if hasattr(obj, 'account_type') and obj.account_type == "MOCK":
                        return 5.0  # 모의투자: 최소 5초 간격
        except:
            pass
        
        return 2.0  # 실전투자: KIS API 기본 최소 간격 (초당 2건 제한)
    
    def _ensure_file_signal_recognition_time(self) -> float:
        """파일 기반 중단 신호 인식 시간 보장 (Claude CLI 환경)"""
        # 파일 기반 중단 신호가 제대로 인식되도록 최소 간격 보장
        return self.config.min_interval  # 최소 4초
    
    def record_trade(self, 
                    action: str, 
                    symbol: str,
                    stock_name: str,
                    price: float, 
                    quantity: int,
                    result: TradeResult = TradeResult.PENDING,
                    profit_loss: float = 0.0):
        """매매 기록 저장 (tideWise 형식)"""
        
        with self._lock:
            now = datetime.now()
            
            # 이전 매매와의 간격 계산
            interval_before = 0.0
            if self.last_trade_time:
                interval_before = (now - self.last_trade_time).total_seconds()
            
            # 매매 기록 생성
            trade_record = TradeRecord(
                timestamp=now,
                action=action,
                symbol=symbol,
                stock_name=stock_name,
                price=price,
                quantity=quantity,
                result=result,
                profit_loss=profit_loss,
                interval_before=interval_before
            )
            
            self.trade_history.append(trade_record)
            self.last_trade_time = now
            self.total_trades += 1
            
            # 연속 손익 추적 업데이트
            self._update_consecutive_performance(result, profit_loss)
            
            logger.info(f"매매 기록: {action.upper()} {stock_name}({symbol}) @{price:,}원 "
                       f"{quantity}주 (간격: {interval_before:.1f}초)")
    
    def _update_consecutive_performance(self, result: TradeResult, profit_loss: float):
        """연속 성과 추적 업데이트"""
        
        if result == TradeResult.PROFIT:
            self.consecutive_profits += 1
            self.consecutive_losses = 0
            logger.info(f"연속 수익: {self.consecutive_profits}회")
        elif result == TradeResult.LOSS:
            self.consecutive_losses += 1
            self.consecutive_profits = 0
            logger.warning(f"연속 손실: {self.consecutive_losses}회")
        else:
            # BREAKEVEN이나 PENDING의 경우 리셋하지 않음
            pass
        
        # 성과 통계 업데이트
        if result in [TradeResult.PROFIT, TradeResult.LOSS]:
            self.performance_stats['total_profit_loss'] += profit_loss
    
    def _update_statistics(self):
        """통계 정보 업데이트"""
        if len(self.trade_history) > 0:
            # 평균 간격 계산
            intervals = [trade.interval_before for trade in self.trade_history 
                        if trade.interval_before > 0]
            if intervals:
                self.performance_stats['avg_interval'] = np.mean(intervals)
            
            # 승률 계산
            completed_trades = [trade for trade in self.trade_history 
                              if trade.result in [TradeResult.PROFIT, TradeResult.LOSS]]
            if completed_trades:
                wins = len([trade for trade in completed_trades 
                           if trade.result == TradeResult.PROFIT])
                self.performance_stats['win_rate'] = wins / len(completed_trades)
        
        self.performance_stats['intervals_adjusted'] += 1
    
    def update_market_condition(self, 
                               condition: MarketCondition,
                               reason: str = ""):
        """시장 상황 수동 업데이트"""
        
        with self._lock:
            old_condition = self.current_market_condition
            self.current_market_condition = condition
            
            if old_condition != condition:
                logger.info(f"시장 상황 변경: {old_condition.value} → {condition.value} ({reason})")
    
    def can_trade_now(self) -> Tuple[bool, float, str]:
        """현재 매매 가능 여부 확인"""
        
        if not self.last_trade_time:
            return True, 0.0, "첫 매매 시작"
        
        elapsed = (datetime.now() - self.last_trade_time).total_seconds()
        
        if elapsed >= self.current_interval:
            return True, elapsed, f"간격 충족 ({elapsed:.1f}초 경과, 설정: {self.current_interval:.1f}초)"
        else:
            remaining = self.current_interval - elapsed
            return False, remaining, f"대기 필요 ({remaining:.1f}초 남음)"
    
    def force_reset_interval(self, reason: str = "수동 리셋"):
        """간격 강제 리셋 (응급 상황용)"""
        with self._lock:
            old_interval = self.current_interval
            self.current_interval = self.config.base_interval
            self.consecutive_losses = 0
            self.consecutive_profits = 0
            self.performance_stats['emergency_adjustments'] += 1
            
            logger.warning(f"매매 간격 강제 리셋: {old_interval:.1f}초 → {self.current_interval:.1f}초 ({reason})")
    
    def get_status_summary(self) -> Dict[str, Any]:
        """현재 상태 요약 조회"""
        can_trade, time_info, reason = self.can_trade_now()
        
        return {
            'current_interval': round(self.current_interval, 1),
            'can_trade_now': can_trade,
            'time_until_next_trade': round(time_info, 1) if not can_trade else 0.0,
            'reason': reason,
            'market_condition': self.current_market_condition.value,
            'consecutive_losses': self.consecutive_losses,
            'consecutive_profits': self.consecutive_profits,
            'total_trades': self.total_trades,
            'win_rate': round(self.performance_stats.get('win_rate', 0.0) * 100, 1),
            'avg_interval': round(self.performance_stats.get('avg_interval', 0.0), 1),
            'last_trade_time': self.last_trade_time.strftime('%H:%M:%S') if self.last_trade_time else None
        }
    
    def get_interval_recommendation_for_daily_target(self, target_trades: int = 10) -> Dict[str, Any]:
        """일일 목표 거래 횟수 기반 간격 추천"""
        
        # 한국 장 시간: 09:00-15:30 (6.5시간 = 23400초)
        # 실제 활용 시간: 점심시간 제외 약 5.5시간 = 19800초
        effective_trading_seconds = 19800
        recommended_interval = effective_trading_seconds / target_trades
        
        return {
            'recommended_base_interval': round(recommended_interval, 1),
            'target_daily_trades': target_trades,
            'current_base_interval': self.config.base_interval,
            'adjustment_needed': abs(recommended_interval - self.config.base_interval) > 60,
            'efficiency_rating': min(recommended_interval / self.config.base_interval, 2.0)
        }


# 글로벌 인스턴스 (싱글톤 패턴)
_interval_controller = None

def get_dynamic_interval_controller() -> tideWiseDynamicIntervalController:
    """동적 간격 제어기 싱글톤 인스턴스 반환"""
    global _interval_controller
    if _interval_controller is None:
        _interval_controller = tideWiseDynamicIntervalController()
    return _interval_controller