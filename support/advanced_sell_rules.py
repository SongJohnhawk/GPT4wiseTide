"""
고급 매도 규칙 모듈
매수세 지속 시 매도 지연 및 하락세 전환 감지
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MarketPressure:
    """시장 압력 정보"""
    symbol: str
    buying_pressure: float    # 매수세 강도 (0-100)
    selling_pressure: float   # 매도세 강도 (0-100)
    price_trend: float        # 가격 추세 (%)
    volume_trend: float       # 거래량 추세 (%)
    timestamp: datetime
    consecutive_buy_signals: int = 0  # 연속 매수세 횟수


class AdvancedSellRules:
    """고급 매도 규칙 엔진"""
    
    def __init__(self, api_connector):
        self.api = api_connector
        
        # 매도 지연 설정
        self.MIN_BUY_PRESSURE = 70          # 매수세 최소 기준
        self.MIN_CONSECUTIVE_SIGNALS = 3    # 최소 연속 매수세 횟수
        self.SELL_DELAY_THRESHOLD = 5       # 매도 지연 최대 횟수
        
        # 하락세 전환 감지 설정
        self.PRICE_DROP_THRESHOLD = -2.0    # 급격한 가격 하락 기준 (%)
        self.VOLUME_SPIKE_RATIO = 2.0       # 거래량 급증 기준 (배)
        self.SELL_PRESSURE_THRESHOLD = 80   # 매도세 강도 기준
        
        # 상태 관리
        self.market_pressure_history: Dict[str, List[MarketPressure]] = {}
        self.sell_delay_count: Dict[str, int] = {}
        
    async def should_delay_sell(self, symbol: str, algorithm_sell_signal: bool) -> bool:
        """
        매도 지연 여부 결정
        
        Args:
            symbol: 종목 코드
            algorithm_sell_signal: 알고리즘 매도 신호
            
        Returns:
            True: 매도 지연, False: 매도 실행
        """
        try:
            if not algorithm_sell_signal:
                return False
            
            # 현재 시장 압력 분석
            market_pressure = await self.analyze_market_pressure(symbol)
            if not market_pressure:
                return False
            
            # 매수세가 강하고 상승 중인 경우
            if (market_pressure.buying_pressure >= self.MIN_BUY_PRESSURE and 
                market_pressure.price_trend > 0):
                
                # 연속 매수세 횟수 업데이트
                self._update_consecutive_signals(symbol, market_pressure)
                
                # 매도 지연 횟수 체크
                delay_count = self.sell_delay_count.get(symbol, 0)
                consecutive_signals = market_pressure.consecutive_buy_signals
                
                if (consecutive_signals >= self.MIN_CONSECUTIVE_SIGNALS and 
                    delay_count < self.SELL_DELAY_THRESHOLD):
                    
                    self.sell_delay_count[symbol] = delay_count + 1
                    logger.info(f"매도 지연: {symbol} - 매수세 지속 중 "
                               f"(지연 횟수: {delay_count + 1}/{self.SELL_DELAY_THRESHOLD})")
                    return True
            
            # 하락세 전환 감지
            if await self.detect_downtrend_start(symbol):
                logger.info(f"하락세 전환 감지: {symbol} - 즉시 매도 실행")
                self._reset_sell_delay(symbol)
                return False
            
            return False
            
        except Exception as e:
            logger.error(f"매도 지연 판단 오류 ({symbol}): {e}")
            return False
    
    async def analyze_market_pressure(self, symbol: str) -> Optional[MarketPressure]:
        """시장 압력 분석"""
        try:
            # 분봉 데이터 조회 (최근 10분)
            minute_data = self.api.get_minute_chart_data(symbol, count=10)
            if not minute_data or not minute_data.get('output2'):
                return None
            
            candles = minute_data['output2'][:10]  # 최근 10개 분봉
            if len(candles) < 5:
                return None
            
            # 가격 및 거래량 데이터 추출
            prices = []
            volumes = []
            
            for candle in candles:
                try:
                    close_price = float(candle.get('stck_clpr', 0))
                    volume = int(candle.get('acml_vol', 0))
                    if close_price > 0:
                        prices.append(close_price)
                        volumes.append(volume)
                except (ValueError, TypeError):
                    continue
            
            if len(prices) < 5:
                return None
            
            # 매수세/매도세 분석
            buying_pressure = self._calculate_buying_pressure(prices, volumes)
            selling_pressure = self._calculate_selling_pressure(prices, volumes)
            
            # 가격 추세 계산 (최근 5분 대비)
            price_trend = ((prices[0] - prices[4]) / prices[4]) * 100
            
            # 거래량 추세 계산
            recent_volume = sum(volumes[:3]) / 3  # 최근 3분 평균
            past_volume = sum(volumes[3:6]) / 3   # 이전 3분 평균
            volume_trend = ((recent_volume - past_volume) / past_volume) * 100 if past_volume > 0 else 0
            
            return MarketPressure(
                symbol=symbol,
                buying_pressure=buying_pressure,
                selling_pressure=selling_pressure,
                price_trend=price_trend,
                volume_trend=volume_trend,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"시장 압력 분석 오류 ({symbol}): {e}")
            return None
    
    def _calculate_buying_pressure(self, prices: List[float], volumes: List[int]) -> float:
        """매수세 강도 계산 (0-100)"""
        try:
            # 상승 분봉 비율
            up_candles = sum(1 for i in range(1, len(prices)) if prices[i-1] > prices[i])
            up_ratio = up_candles / (len(prices) - 1) if len(prices) > 1 else 0
            
            # 거래량 가중 상승률
            price_momentum = 0
            total_volume = sum(volumes)
            
            for i in range(1, len(prices)):
                if prices[i-1] > prices[i]:  # 상승 분봉
                    price_change = (prices[i-1] - prices[i]) / prices[i]
                    volume_weight = volumes[i-1] / total_volume if total_volume > 0 else 0
                    price_momentum += price_change * volume_weight
            
            # 매수세 점수 계산
            buying_pressure = (up_ratio * 60) + (price_momentum * 100 * 40)
            return max(0, min(100, buying_pressure))
            
        except Exception as e:
            logger.debug(f"매수세 계산 오류: {e}")
            return 50.0
    
    def _calculate_selling_pressure(self, prices: List[float], volumes: List[int]) -> float:
        """매도세 강도 계산 (0-100)"""
        try:
            # 하락 분봉 비율
            down_candles = sum(1 for i in range(1, len(prices)) if prices[i-1] < prices[i])
            down_ratio = down_candles / (len(prices) - 1) if len(prices) > 1 else 0
            
            # 거래량 가중 하락률
            price_momentum = 0
            total_volume = sum(volumes)
            
            for i in range(1, len(prices)):
                if prices[i-1] < prices[i]:  # 하락 분봉
                    price_change = (prices[i] - prices[i-1]) / prices[i-1]
                    volume_weight = volumes[i-1] / total_volume if total_volume > 0 else 0
                    price_momentum += price_change * volume_weight
            
            # 매도세 점수 계산
            selling_pressure = (down_ratio * 60) + (price_momentum * 100 * 40)
            return max(0, min(100, selling_pressure))
            
        except Exception as e:
            logger.debug(f"매도세 계산 오류: {e}")
            return 50.0
    
    async def detect_downtrend_start(self, symbol: str) -> bool:
        """하락세 전환 시점 감지"""
        try:
            # 최근 시장 압력 이력 확인
            if symbol not in self.market_pressure_history:
                return False
            
            history = self.market_pressure_history[symbol]
            if len(history) < 3:
                return False
            
            # 최근 3개 데이터 분석
            recent = history[-3:]
            latest = recent[-1]
            
            # 1. 급격한 가격 하락 체크
            if latest.price_trend <= self.PRICE_DROP_THRESHOLD:
                logger.debug(f"급격한 가격 하락 감지: {symbol} ({latest.price_trend:.2f}%)")
                return True
            
            # 2. 거래량 급증과 함께 매도세 급증 체크
            if (latest.volume_trend >= self.VOLUME_SPIKE_RATIO * 100 and
                latest.selling_pressure >= self.SELL_PRESSURE_THRESHOLD):
                logger.debug(f"매도세 급증 감지: {symbol} (매도세: {latest.selling_pressure:.1f})")
                return True
            
            # 3. 매수세에서 매도세로 급격한 전환
            if len(recent) >= 2:
                prev = recent[-2]
                if (prev.buying_pressure >= 70 and 
                    latest.selling_pressure >= 70 and
                    latest.buying_pressure < 30):
                    logger.debug(f"매수세→매도세 급전환 감지: {symbol}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"하락세 전환 감지 오류 ({symbol}): {e}")
            return False
    
    def _update_consecutive_signals(self, symbol: str, market_pressure: MarketPressure):
        """연속 매수세 횟수 업데이트"""
        if symbol not in self.market_pressure_history:
            self.market_pressure_history[symbol] = []
        
        history = self.market_pressure_history[symbol]
        
        # 매수세가 강한 경우 카운트 증가
        if market_pressure.buying_pressure >= self.MIN_BUY_PRESSURE:
            if history and history[-1].buying_pressure >= self.MIN_BUY_PRESSURE:
                market_pressure.consecutive_buy_signals = history[-1].consecutive_buy_signals + 1
            else:
                market_pressure.consecutive_buy_signals = 1
        else:
            market_pressure.consecutive_buy_signals = 0
        
        # 이력에 추가 (최대 20개 유지)
        history.append(market_pressure)
        if len(history) > 20:
            history.pop(0)
    
    def _reset_sell_delay(self, symbol: str):
        """매도 지연 상태 리셋"""
        if symbol in self.sell_delay_count:
            del self.sell_delay_count[symbol]
        if symbol in self.market_pressure_history:
            self.market_pressure_history[symbol].clear()
    
    def get_sell_delay_status(self, symbol: str) -> Dict[str, Any]:
        """매도 지연 상태 조회"""
        delay_count = self.sell_delay_count.get(symbol, 0)
        history = self.market_pressure_history.get(symbol, [])
        latest_pressure = history[-1] if history else None
        
        return {
            'symbol': symbol,
            'delay_count': delay_count,
            'max_delay': self.SELL_DELAY_THRESHOLD,
            'consecutive_buy_signals': latest_pressure.consecutive_buy_signals if latest_pressure else 0,
            'latest_buying_pressure': latest_pressure.buying_pressure if latest_pressure else 0,
            'latest_price_trend': latest_pressure.price_trend if latest_pressure else 0
        }