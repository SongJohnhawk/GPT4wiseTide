"""
급등종목 독립 매수 전용 시스템
알고리즘과 독립적으로 급등종목을 매수하는 모듈
Hyper_upStockFind.py의 SimpleSurgeDetector 사용
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Hyper_upStockFind.py의 SimpleSurgeDetector import
from support.Hyper_upStockFind import SimpleSurgeDetector

logger = logging.getLogger(__name__)


@dataclass
class BuyableStock:
    """매수 가능한 급등종목 정보"""
    symbol: str
    name: str
    current_price: float
    change_rate: float
    volume_ratio: float
    surge_score: float
    quantity: int
    required_amount: int
    buying_pressure: float = 0.0
    k_shot_score: int = 0  # K-Shot 알고리즘 점수
    k_shot_indicators: Dict = None  # K-Shot 지표들


class KoreanStockMomentumAnalyzer:
    """K-ShotTradingAlgo 기반 모멘텀 분석기"""
    
    def __init__(self):
        pass
    
    @staticmethod
    def _calculate_rsi_numpy(prices, window=14):
        """NumPy/Numba 최적화된 RSI 계산"""
        n = len(prices)
        if n < window + 1:
            return np.full(n, 50.0)
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        
        rsi_values = np.zeros(n)
        rsi_values[:window] = 50.0
        
        for i in range(window, n):
            start_idx = i - window
            avg_gain = np.mean(gains[start_idx:i])
            avg_loss = np.mean(losses[start_idx:i])
            
            if avg_loss == 0:
                rsi_values[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_values[i] = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi_values

    @staticmethod 
    def _calculate_ema_numpy(prices, span):
        """NumPy/Numba 최적화된 EMA 계산"""
        n = len(prices)
        if n == 0:
            return np.array([])
        
        alpha = 2.0 / (span + 1.0)
        ema = np.zeros(n)
        ema[0] = prices[0]
        
        for i in range(1, n):
            ema[i] = alpha * prices[i] + (1.0 - alpha) * ema[i-1]
        
        return ema
    
    @staticmethod
    def _calculate_bollinger_bands_numpy(prices, window=20, num_std=2):
        """NumPy/Numba 최적화된 볼린저 밴드 계산"""
        n = len(prices)
        sma = np.zeros(n)
        std = np.zeros(n)
        
        for i in range(n):
            start_idx = max(0, i - window + 1)
            window_data = prices[start_idx:i+1]
            sma[i] = np.mean(window_data)
            std[i] = np.std(window_data)
        
        upper = sma + num_std * std
        lower = sma - num_std * std
        
        return upper, sma, lower
    
    def analyze_momentum(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """NumPy 최적화된 모멘텀 분석 및 점수 계산"""
        if len(price_data) < 60:  # 최소 60개 데이터 필요
            return {'score': 0, 'buy_signal': False, 'sell_signal': False, 'indicators': {}}
        
        df = price_data.copy()
        
        # NumPy 배열로 변환 (타입 동질성 보장)
        close_array = df['Close'].values.astype(np.float64)
        volume_array = df['Volume'].values.astype(np.float64)
        
        # NumPy 벡터화된 기본 지표 계산
        n = len(close_array)
        
        # 1. Return 계산 (NumPy diff 사용)
        returns = np.concatenate([[0], np.diff(close_array) / close_array[:-1]])
        df['Return'] = returns
        
        # 2. Momentum 계산 (NumPy 슬라이싱)
        momentum_20 = np.zeros(n)
        momentum_60 = np.zeros(n)
        momentum_20[20:] = close_array[20:] / close_array[:-20] - 1
        momentum_60[60:] = close_array[60:] / close_array[:-60] - 1
        df['Momentum_20'] = momentum_20
        df['Momentum_60'] = momentum_60
        
        # 3. RSI (Numba JIT 최적화)
        rsi_values = self._calculate_rsi_numpy(close_array, 14)
        df['RSI_14'] = rsi_values
        
        # 4. MACD (Numba JIT 최적화)
        ema_fast = self._calculate_ema_numpy(close_array, 12)
        ema_slow = self._calculate_ema_numpy(close_array, 26)
        macd_line = ema_fast - ema_slow
        macd_signal = self._calculate_ema_numpy(macd_line, 9)
        df['MACD'] = macd_line
        df['MACD_signal'] = macd_signal
        
        # 5. Bollinger Bands (Numba JIT 최적화)
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands_numpy(close_array, 20, 2)
        df['BB_upper'] = bb_upper
        df['BB_middle'] = bb_middle
        df['BB_lower'] = bb_lower
        
        # 6. Volume MA (NumPy rolling mean)
        volume_ma = np.zeros(n)
        for i in range(n):
            start_idx = max(0, i - 19)
            volume_ma[i] = np.mean(volume_array[start_idx:i+1])
        df['Volume_MA_20'] = volume_ma
        
        # 최신 데이터
        latest = df.iloc[-1]
        
        # 점수 계산 (K-ShotTradingAlgo 로직)
        score = 0
        
        # 모멘텀 점수
        if latest['Momentum_20'] > 0:
            score += 1
        if latest['Momentum_60'] > 0:
            score += 2
        
        # RSI 과매도 구간 점수
        if latest['RSI_14'] < 30:
            score += 2
        
        # MACD 골든크로스
        if (latest['MACD'] > latest['MACD_signal'] and 
            df.iloc[-2]['MACD'] <= df.iloc[-2]['MACD_signal']):
            score += 3
        
        # 볼린저 밴드 중앙선 위
        if latest['Close'] > latest['BB_middle']:
            score += 1
        
        # 거래량 증가
        if latest['Volume'] > latest['Volume_MA_20']:
            score += 1
        
        # 매수/매도 신호
        buy_signal = score >= 5
        sell_signal = latest['RSI_14'] > 70 or (
            latest['MACD'] < latest['MACD_signal'] and 
            df.iloc[-2]['MACD'] >= df.iloc[-2]['MACD_signal']
        )
        
        return {
            'score': score,
            'buy_signal': buy_signal,
            'sell_signal': sell_signal,
            'indicators': {
                'rsi': latest['RSI_14'],
                'momentum_20': latest['Momentum_20'],
                'momentum_60': latest['Momentum_60'],
                'macd': latest['MACD'],
                'macd_signal': latest['MACD_signal'],
                'price_position': 'above_bb' if latest['Close'] > latest['BB_middle'] else 'below_bb',
                'volume_trend': 'increasing' if latest['Volume'] > latest['Volume_MA_20'] else 'decreasing'
            }
        }


class SurgeStockBuyer:
    """급등종목 독립 매수 전용 시스템 (SimpleSurgeDetector 사용)"""
    
    def __init__(self, api_connector, surge_provider):
        self.api = api_connector
        self.surge_provider = surge_provider
        self.surge_detector = SimpleSurgeDetector()  # Hyper_upStockFind.py의 SimpleSurgeDetector 사용
        
        # 매수 조건 설정 (대폭 완화)
        self.MIN_PRICE = 9000           # 최소 가격 (9천원 이하 매수 금지 - 변경 금지)
        self.MAX_PRICE = 80000          # 최대 가격 (50,000원 → 80,000원으로 확대)
        self.MIN_BUY_COUNT = 1          # 최소 매수 종목 수 (1개 유지)
        self.HIGH_PRICE_THRESHOLD = 300000  # 고가 기준 (20만원 → 30만원으로 확대)
        self.HIGH_PRICE_MAX_QTY = 5     # 고가 종목 최대 수량
        self.MAX_BUY_COUNT = 8          # 최대 매수 종목 수 (6개 → 8개로 증가)
        self.PROFIT_TARGET = 0.07       # 7% 익절 기준 추가
        
        # 상태 관리
        self.last_attempt_time = None
        self.purchased_symbols = set()
        self.price_history = {}  # 종목별 가격 히스토리 저장
        
    def get_min_quantity_by_deposit(self, deposit_amount: int) -> int:
        """예수금별 최소 매수 수량"""
        if deposit_amount < 20000000:        # 2천만원 미만
            return 10
        elif deposit_amount < 50000000:      # 5천만원 미만  
            return 50
        elif deposit_amount <= 80000000:     # 8천만원 이하
            return 70
        else:                                # 8천만원 초과
            return 100
    
    def calculate_buy_quantity(self, price: float, deposit_amount: int) -> int:
        """매수 수량 계산 (7% 원칙 적용)"""
        try:
            # 기존 수량 계산
            min_qty = self.get_min_quantity_by_deposit(deposit_amount)
            
            # 고가 종목 제한 적용 (예수금 5천만원 이하만)
            if deposit_amount <= 50000000 and price > self.HIGH_PRICE_THRESHOLD:
                min_qty = min(min_qty, self.HIGH_PRICE_MAX_QTY)
            
            # 7% 원칙 적용
            from .trading_rules import get_trading_rules
            trading_rules = get_trading_rules()
            
            # 7% 원칙으로 최대 수량 제한
            max_qty_by_budget = trading_rules.calculate_max_quantity_by_budget_ratio(
                deposit_amount, price
            )
            
            # 기존 수량과 7% 원칙 중 작은 값 선택
            final_qty = min(min_qty, max_qty_by_budget)
            
            logger.debug(f"급등주 수량 계산: 기존={min_qty}, 7%제한={max_qty_by_budget}, 최종={final_qty}")
            return final_qty
            
        except Exception as e:
            logger.error(f"급등주 수량 계산 실패: {e}")
            # 실패 시 기존 로직 사용
            min_qty = self.get_min_quantity_by_deposit(deposit_amount)
            if deposit_amount <= 50000000 and price > self.HIGH_PRICE_THRESHOLD:
                return min(min_qty, self.HIGH_PRICE_MAX_QTY)
            return min_qty
    
    async def calculate_buying_pressure(self, symbol: str) -> float:
        """매수세 계산 (분봉 데이터 기반)"""
        try:
            # 분봉 데이터로 매수세 분석
            minute_data = self.api.get_minute_chart_data(symbol, count=5)
            
            if not minute_data or not isinstance(minute_data, dict):
                return 50.0  # 기본값
            
            output_data = minute_data.get('output2', [])
            if len(output_data) < 3:
                return 50.0  # 기본값
            
            # 최근 3분봉의 가격 상승 추세 분석
            recent_prices = []
            recent_volumes = []
            
            for candle in output_data[:3]:
                try:
                    close_price = float(candle.get('stck_clpr', 0))
                    volume = int(candle.get('acml_vol', 0))
                    if close_price > 0:
                        recent_prices.append(close_price)
                        recent_volumes.append(volume)
                except (ValueError, TypeError):
                    continue
            
            if len(recent_prices) < 2:
                return 50.0
            
            # 가격 상승률 계산
            price_trend = (recent_prices[0] - recent_prices[-1]) / recent_prices[-1] * 100
            
            # 거래량 증가율 계산
            if len(recent_volumes) >= 2:
                volume_trend = (recent_volumes[0] - recent_volumes[-1]) / recent_volumes[-1] * 100
            else:
                volume_trend = 0
            
            # 매수 압력 점수 계산 (0-100)
            buying_pressure = 50 + (price_trend * 2) + (volume_trend * 0.5)
            buying_pressure = max(0, min(100, buying_pressure))
            
            return buying_pressure
            
        except Exception as e:
            logger.debug(f"매수세 계산 실패 ({symbol}): {e}")
            return 50.0  # 기본값
    
    async def get_stock_price_history(self, symbol: str) -> pd.DataFrame:
        """종목의 가격 히스토리 조회 (K-Shot 알고리즘용)"""
        try:
            # 일봉 데이터 조회 (최근 100일)
            daily_data = self.api.get_daily_chart_data(symbol, count=100)
            
            if not daily_data or not isinstance(daily_data, dict):
                return None
            
            output_data = daily_data.get('output2', [])
            if len(output_data) < 60:  # 최소 60일 데이터 필요
                return None
            
            # DataFrame 생성
            price_list = []
            for candle in output_data:
                try:
                    price_list.append({
                        'Open': float(candle.get('stck_oprc', 0)),
                        'High': float(candle.get('stck_hgpr', 0)),
                        'Low': float(candle.get('stck_lwpr', 0)),
                        'Close': float(candle.get('stck_clpr', 0)),
                        'Volume': int(candle.get('acml_vol', 0))
                    })
                except (ValueError, TypeError):
                    continue
            
            if len(price_list) < 60:
                return None
            
            df = pd.DataFrame(price_list)
            df = df.iloc[::-1]  # 오래된 날짜부터 정렬
            df.reset_index(drop=True, inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"가격 히스토리 조회 실패 ({symbol}): {e}")
            return None
    
    async def analyze_with_surge_detector(self, symbol: str) -> Dict[str, Any]:
        """SimpleSurgeDetector로 종목 분석"""
        try:
            # 일봉 데이터 조회 (10일치)
            df = self.api.get_stock_chart_data(symbol, period='day', count=10)
            if df is None or len(df) < 6:
                return {'score': 0, 'is_surge': False, 'detail': '데이터 부족'}
            
            # DataFrame을 SimpleSurgeDetector 형식으로 변환
            stock_data = []
            for _, row in df.iterrows():
                stock_data.append({
                    "date": str(row.get('date', '')),
                    "open": float(row.get('Open', 0)),
                    "high": float(row.get('High', 0)),
                    "low": float(row.get('Low', 0)),
                    "close": float(row.get('Close', 0)),
                    "volume": int(row.get('Volume', 0))
                })
            
            # SimpleSurgeDetector로 분석
            is_surge, score, detail = self.surge_detector.detect(stock_data)
            
            return {
                'score': score,
                'is_surge': is_surge,
                'detail': detail,
                'buy_signal': is_surge
            }
            
        except Exception as e:
            logger.error(f"SimpleSurgeDetector 분석 실패 ({symbol}): {e}")
            return {'score': 0, 'is_surge': False, 'detail': f'분석 오류: {str(e)}'}
    
    async def filter_surge_stocks(self, surge_stocks: List, deposit_amount: int) -> List[BuyableStock]:
        """급등종목 필터링 및 매수 가능 종목 선별 (K-Shot 알고리즘 통합)"""
        buyable_stocks = []
        
        for stock in surge_stocks:
            try:
                # 1. 가격 조건 체크 (9천원 이하는 무조건 제외, 상한가 확대)
                if stock.current_price < self.MIN_PRICE:
                    logger.debug(f"최소가격 미달로 제외: {stock.symbol} ({stock.current_price:,}원 < {self.MIN_PRICE:,}원)")
                    continue
                if stock.current_price > self.MAX_PRICE:
                    logger.debug(f"가격 초과로 제외: {stock.symbol} ({stock.current_price:,}원 > {self.MAX_PRICE:,}원)")
                    continue
                
                # 2. 이미 매수한 종목 제외
                if stock.symbol in self.purchased_symbols:
                    logger.debug(f"이미 매수한 종목 제외: {stock.symbol}")
                    continue
                
                # 3. SimpleSurgeDetector 분석 
                surge_analysis = await self.analyze_with_surge_detector(stock.symbol)
                
                # SimpleSurgeDetector 결과 확인
                is_surge = surge_analysis.get('is_surge', False)
                surge_score = surge_analysis.get('score', 0)
                detail = surge_analysis.get('detail', '')
                
                # 급등주 조건: 점수 5점 이상이면 통과 (완화된 조건)
                if surge_score >= 5:
                    logger.info(f"급등주 조건 통과: {stock.symbol} (점수: {surge_score}, 상세: {detail})")
                else:
                    logger.debug(f"급등주 조건 미달로 제외: {stock.symbol} (점수: {surge_score}, 상세: {detail})")
                    continue
                
                # 4. 매수 가능 수량 계산
                buy_qty = self.calculate_buy_quantity(stock.current_price, deposit_amount)
                
                # 5. 필요 금액 계산
                required_amount = int(stock.current_price * buy_qty)
                
                # 6. 자금 충분성 체크
                if required_amount > deposit_amount:
                    logger.debug(f"자금 부족으로 제외: {stock.symbol} (필요: {required_amount:,}원 > 보유: {deposit_amount:,}원)")
                    continue
                
                # 7. 매수세 계산 (기존 로직 유지)
                buying_pressure = await self.calculate_buying_pressure(stock.symbol)
                
                buyable_stock = BuyableStock(
                    symbol=stock.symbol,
                    name=stock.name,
                    current_price=stock.current_price,
                    change_rate=stock.change_rate,
                    volume_ratio=stock.volume_ratio,
                    surge_score=stock.surge_score,
                    quantity=buy_qty,
                    required_amount=required_amount,
                    buying_pressure=buying_pressure,
                    k_shot_score=surge_analysis.get('score', 0),
                    k_shot_indicators={'surge_detail': surge_analysis.get('detail', '')}
                )
                
                buyable_stocks.append(buyable_stock)
                logger.info(f"급등주 통과 종목: {stock.name}({stock.symbol}) "
                           f"급등점수: {surge_analysis.get('score', 0)}, "
                           f"상세: {surge_analysis.get('detail', '')}, "
                           f"매수세: {buying_pressure:.1f}")
                
            except Exception as e:
                logger.error(f"종목 필터링 오류 ({stock.symbol}): {e}")
                continue
        
        return buyable_stocks
    
    def rank_by_surge_algorithm(self, buyable_stocks: List[BuyableStock]) -> List[BuyableStock]:
        """SimpleSurgeDetector 기반 종목 순위화"""
        # SimpleSurgeDetector 점수(60%) + 급등 점수(20%) + 매수세(20%) 종합 점수로 정렬
        for stock in buyable_stocks:
            # 각 점수 정규화
            normalized_surge = min(100, max(0, stock.surge_score))  # 급등 점수 (0-100)
            normalized_detector = min(100, max(0, stock.k_shot_score * 10))  # SimpleSurgeDetector 점수 (0-100)
            normalized_buying = min(100, max(0, stock.buying_pressure))  # 매수세 (0-100)
            
            # 종합 점수 계산 (SimpleSurgeDetector 우선)
            stock.total_score = (normalized_detector * 0.6) + (normalized_surge * 0.2) + (normalized_buying * 0.2)
        
        # 종합 점수 순 정렬
        ranked_stocks = sorted(buyable_stocks, key=lambda x: x.total_score, reverse=True)
        
        logger.info(f"K-Shot 알고리즘 기반 급등종목 순위화 완료: {len(ranked_stocks)}개 종목")
        for i, stock in enumerate(ranked_stocks[:6], 1):
            indicators = stock.k_shot_indicators or {}
            logger.info(f"{i}위: {stock.name}({stock.symbol}) - 종합점수: {stock.total_score:.1f} "
                       f"(K-Shot: {stock.k_shot_score}, 급등: {stock.surge_score:.1f}, 매수세: {stock.buying_pressure:.1f}) "
                       f"[RSI: {indicators.get('rsi', 0):.1f}, 모멘텀20일: {indicators.get('momentum_20', 0):.2%}]")
        
        return ranked_stocks
    
    async def execute_buy_order(self, stock: BuyableStock) -> bool:
        """개별 종목 매수 주문 실행"""
        try:
            # 매수 비활성화 설정 확인
            try:
                import json
                from pathlib import Path
                config_path = Path(__file__).parent / "trading_config.json"
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        trading_exec = config.get('trading_execution', {})
                        
                        if not trading_exec.get('enable_buy_orders', True):
                            logger.info(f"[시뮬레이션] 급등종목 매수 (실제 실행 안함): {stock.name}({stock.symbol}) {stock.quantity}주 "
                                       f"@ {stock.current_price:,}원 (총 {stock.required_amount:,}원)")
                            # 성공적인 매수로 시뮬레이션
                            return True
            except Exception as e:
                logger.debug(f"급등종목 매수 설정 확인 중 오류 (계속 진행): {e}")
            
            logger.info(f"급등종목 매수 시도: {stock.name}({stock.symbol}) {stock.quantity}주 "
                       f"@ {stock.current_price:,}원 (총 {stock.required_amount:,}원)")
            
            result = self.api.buy_order(
                stock_code=stock.symbol,
                quantity=stock.quantity,
                price=0,  # 시장가
                order_type="MARKET"
            )
            
            if result and result.get('rt_cd') == '0':
                logger.info(f"급등종목 매수 성공: {stock.name}({stock.symbol}) {stock.quantity}주")
                
                # 급등종목 매수 후 계좌 정보 조회
                balance_info = self.api.get_account_balance(force_refresh=True)
                
                # 텔레그램 알림 (텔레그램 알림 기능이 있다면)
                try:
                    from telegram_notifier import get_telegram_notifier
                    telegram = get_telegram_notifier()
                    if telegram:
                        import asyncio
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # 이벤트 루프가 실행 중이면 task 생성
                            asyncio.create_task(telegram.send_order_result(
                                stock.symbol, "매수 (급등)", stock.quantity, 
                                stock.current_price, "성공", balance_info=balance_info, api_connector=self.api
                            ))
                        else:
                            # 이벤트 루프가 실행 중이 아니면 직접 실행
                            asyncio.run(telegram.send_order_result(
                                stock.symbol, "매수 (급등)", stock.quantity, 
                                stock.current_price, "성공", balance_info=balance_info, api_connector=self.api
                            ))
                except Exception as e:
                    logger.debug(f"급등종목 매수 텔레그램 알림 실패: {e}")
                
                self.purchased_symbols.add(stock.symbol)
                return True
            else:
                # 장 종료 메시지 체크
                error_msg = result.get('msg1', '') if result else ''
                if '장종료' in error_msg or '장마감' in error_msg:
                    logger.info("장이 종료되었습니다.")
                else:
                    logger.error(f"급등종목 매수 실패: {stock.name}({stock.symbol}) - 응답: {result}")
                return False
                
        except Exception as e:
            logger.error(f"급등종목 매수 주문 오류: {stock.symbol} - {e}")
            return False
    
    async def execute_surge_buying(self) -> bool:
        """급등종목 독립 매수 메인 실행 함수"""
        try:
            logger.info("급등종목 독립 매수 시작")
            
            # 1. 계좌 잔고 조회
            balance_info = self.api.get_account_balance()
            if not balance_info:
                logger.error("계좌 잔고 조회 실패")
                return False
            
            deposit_amount = int(balance_info.get('ord_psbl_cash', 0))
            logger.info(f"주문 가능 금액: {deposit_amount:,}원")
            
            if deposit_amount < 100000:  # 10만원 미만
                logger.info("주문 가능 금액 부족 (10만원 미만)")
                return False
            
            # 2. 급등종목 스캔
            surge_stocks = await self.surge_provider.get_surge_stocks(limit=50)
            if not surge_stocks:
                logger.info("급등종목 스캔 결과 없음")
                return False
            
            logger.info(f"급등종목 스캔 완료: {len(surge_stocks)}개")
            
            # 3. 급등종목을 객체로 변환 (필요시)
            surge_stock_objects = []
            for symbol in surge_stocks:
                if isinstance(symbol, str):
                    # 문자열인 경우 주식 데이터 조회해서 객체 생성
                    try:
                        stock_data = await self._get_stock_info(symbol)
                        if stock_data:
                            surge_stock_objects.append(stock_data)
                    except Exception as e:
                        logger.debug(f"종목 정보 조회 실패: {symbol} - {e}")
                        continue
                else:
                    surge_stock_objects.append(symbol)
            
            # 4. 필터링
            buyable_stocks = await self.filter_surge_stocks(surge_stock_objects, deposit_amount)
            logger.info(f"필터링 완료: {len(surge_stock_objects)}개 → {len(buyable_stocks)}개")
            
            # 5. 최소 매수 종목 조건 체크
            if len(buyable_stocks) < self.MIN_BUY_COUNT:
                logger.info(f"급등종목 조건 미충족: {len(buyable_stocks)}개 < {self.MIN_BUY_COUNT}개 (재검색 대기)")
                # 필터링 상세 정보 출력
                if len(surge_stock_objects) > 0:
                    logger.info(f"필터링 전 종목 수: {len(surge_stock_objects)}개")
                    logger.info(f"필터링 후 종목 수: {len(buyable_stocks)}개")
                    logger.info(f"주문 가능 금액: {deposit_amount:,}원")
                return False
            
            # 6. K-Shot 알고리즘 기반 순위화
            ranked_stocks = self.rank_by_surge_algorithm(buyable_stocks)
            
            # 7. 상위 종목 매수 실행
            target_stocks = ranked_stocks[:self.MAX_BUY_COUNT]
            success_count = 0
            
            for stock in target_stocks:
                try:
                    # 잔고 재확인 (이전 매수로 인한 잔고 감소 고려)
                    current_balance = self.api.get_account_balance()
                    if current_balance:
                        current_cash = int(current_balance.get('ord_psbl_cash', 0))
                        if current_cash < stock.required_amount:
                            logger.info(f"잔고 부족으로 매수 중단: {stock.symbol} (필요: {stock.required_amount:,}원, 보유: {current_cash:,}원)")
                            break
                    
                    success = await self.execute_buy_order(stock)
                    if success:
                        success_count += 1
                    
                    # Rate Limit 준수
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"급등종목 매수 중 오류: {stock.symbol} - {e}")
                    continue
            
            logger.info(f"급등종목 매수 완료: {success_count}개 성공 / {len(target_stocks)}개 시도")
            return success_count >= self.MIN_BUY_COUNT
            
        except Exception as e:
            logger.error(f"급등종목 독립 매수 실행 실패: {e}")
            return False
    
    async def _get_stock_info(self, symbol: str):
        """종목 정보 조회 (급등종목 객체 생성용)"""
        try:
            # 현재가 조회
            price_data = self.api.get_stock_price(symbol)
            if not price_data or price_data.get('rt_cd') != '0':
                return None
            
            output_data = price_data.get('output', {})
            current_price = float(output_data.get('stck_prpr', 0))
            change_rate = float(output_data.get('prdy_ctrt', 0)) / 100  # 백분율을 소수로 변환
            
            if current_price <= 0:
                return None
            
            # 간단한 급등종목 객체 생성
            class SimpleStockInfo:
                def __init__(self, symbol, current_price, change_rate):
                    self.symbol = symbol
                    self.name = symbol  # 종목명은 일단 심볼로 대체
                    self.current_price = current_price
                    self.change_rate = change_rate
                    self.volume_ratio = 2.0  # 기본값
                    self.surge_score = abs(change_rate) * 10  # 변화율 기반 급등 점수
            
            return SimpleStockInfo(symbol, current_price, change_rate)
            
        except Exception as e:
            logger.debug(f"종목 정보 조회 실패: {symbol} - {e}")
            return None
    
    def should_attempt_surge_buying(self) -> bool:
        """급등종목 매수 시도 여부 판단"""
        now = datetime.now()
        
        # 첫 시도이거나 마지막 시도 후 5분 경과
        if (self.last_attempt_time is None or 
            (now - self.last_attempt_time).seconds >= 300):
            return True
        
        return False
    
    def should_take_profit(self, stock_code: str, purchase_price: float, current_price: float) -> bool:
        """7% 익절 여부 판단"""
        try:
            profit_rate = (current_price - purchase_price) / purchase_price
            
            if profit_rate >= self.PROFIT_TARGET:
                logger.info(f"급등종목 7% 익절 신호: {stock_code} - 매수가: {purchase_price:,}원, "
                           f"현재가: {current_price:,}원, 수익률: {profit_rate:.2%}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"익절 판단 오류: {stock_code} - {e}")
            return False
    
    async def check_profit_targets(self) -> List[str]:
        """보유 중인 급등종목의 7% 익절 확인"""
        profit_targets = []
        
        try:
            # 계좌 보유 종목 조회
            positions = self.api.get_account_positions()
            if not positions:
                return profit_targets
            
            for position in positions:
                try:
                    stock_code = position.get('pdno', '')
                    if stock_code not in self.purchased_symbols:
                        continue  # 급등주 매수로 취득한 종목이 아님
                    
                    quantity = int(position.get('hldg_qty', 0))
                    if quantity <= 0:
                        continue
                    
                    purchase_price = float(position.get('pchs_avg_pric', 0))
                    current_price = self.api.get_current_price(stock_code)
                    
                    if purchase_price <= 0 or current_price <= 0:
                        continue
                    
                    # 7% 익절 조건 확인
                    if self.should_take_profit(stock_code, purchase_price, current_price):
                        profit_targets.append(stock_code)
                        
                except Exception as e:
                    logger.debug(f"개별 종목 익절 확인 오류: {e}")
                    continue
            
            if profit_targets:
                logger.info(f"7% 익절 대상 종목: {len(profit_targets)}개 - {profit_targets}")
            
            return profit_targets
            
        except Exception as e:
            logger.error(f"익절 대상 확인 오류: {e}")
            return profit_targets
    
    async def execute_profit_sell(self, stock_code: str) -> bool:
        """7% 익절 매도 실행"""
        try:
            # 보유 수량 확인
            positions = self.api.get_account_positions()
            if not positions:
                return False
            
            target_position = None
            for position in positions:
                if position.get('pdno', '') == stock_code:
                    target_position = position
                    break
            
            if not target_position:
                logger.warning(f"익절 대상 종목 미보유: {stock_code}")
                return False
            
            quantity = int(target_position.get('hldg_qty', 0))
            if quantity <= 0:
                return False
            
            logger.info(f"급등종목 7% 익절 매도 시도: {stock_code} {quantity}주")
            
            # 시장가 매도 주문
            result = self.api.sell_order(
                stock_code=stock_code,
                quantity=quantity,
                price=0,  # 시장가
                order_type="MARKET"
            )
            
            if result and result.get('rt_cd') == '0':
                logger.info(f"급등종목 7% 익절 매도 성공: {stock_code} {quantity}주")
                
                # 매도 후 텔레그램 알림
                try:
                    from telegram_notifier import get_telegram_notifier
                    telegram = get_telegram_notifier()
                    if telegram:
                        current_price = self.api.get_current_price(stock_code)
                        purchase_price = float(target_position.get('pchs_avg_pric', 0))
                        
                        asyncio.create_task(telegram.send_order_result(
                            stock_code, "매도 (7% 익절)", quantity, 
                            current_price, "성공", 
                            purchase_price=purchase_price,
                            api_connector=self.api
                        ))
                except Exception as e:
                    logger.debug(f"익절 매도 텔레그램 알림 실패: {e}")
                
                # 매수 목록에서 제거
                self.purchased_symbols.discard(stock_code)
                return True
            else:
                logger.error(f"급등종목 7% 익절 매도 실패: {stock_code} - 응답: {result}")
                return False
                
        except Exception as e:
            logger.error(f"7% 익절 매도 실행 오류: {stock_code} - {e}")
            return False
    
    def reset_daily_state(self):
        """일일 상태 리셋 (새로운 거래일 시작시)"""
        self.purchased_symbols.clear()
        self.last_attempt_time = None
        logger.info("급등종목 매수 상태 리셋 완료")