#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
지능형 컨텍스트 빌더
- 기술적 지표 + 뉴스 감정분석 + 시장 조건 통합
- 다중 모달 데이터 융합 (최신 연구 적용)
- 무료 데이터 소스 활용 (API 키 불필요)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from .gpt_interfaces import MarketContext
from .free_stock_data_collector import StockDataManager
from .integrated_free_data_system import IntegratedFreeDataSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TechnicalIndicatorCalculator:
    """기술적 지표 계산기"""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """RSI 계산"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    @staticmethod
    def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """MACD 계산"""
        if len(prices) < slow:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
        
        prices_series = pd.Series(prices)
        
        # EMA 계산
        ema_fast = prices_series.ewm(span=fast).mean()
        ema_slow = prices_series.ewm(span=slow).mean()
        
        # MACD 라인
        macd_line = ema_fast - ema_slow
        
        # 신호선
        signal_line = macd_line.ewm(span=signal).mean()
        
        # 히스토그램
        histogram = macd_line - signal_line
        
        return {
            "macd": float(macd_line.iloc[-1]),
            "signal": float(signal_line.iloc[-1]),
            "histogram": float(histogram.iloc[-1])
        }
    
    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2) -> Dict[str, float]:
        """볼린저 밴드 계산"""
        if len(prices) < period:
            current_price = prices[-1] if prices else 0
            return {
                "upper": current_price * 1.02,
                "middle": current_price,
                "lower": current_price * 0.98,
                "position": 0.5
            }
        
        prices_series = pd.Series(prices)
        middle = prices_series.rolling(window=period).mean()
        std = prices_series.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        current_price = prices[-1]
        upper_val = float(upper.iloc[-1])
        middle_val = float(middle.iloc[-1])
        lower_val = float(lower.iloc[-1])
        
        # 밴드 내 위치 (0: 하단, 0.5: 중앙, 1: 상단)
        if upper_val != lower_val:
            position = (current_price - lower_val) / (upper_val - lower_val)
        else:
            position = 0.5
        
        return {
            "upper": upper_val,
            "middle": middle_val,
            "lower": lower_val,
            "position": float(np.clip(position, 0, 1))
        }
    
    @staticmethod
    def calculate_volume_ratio(volumes: List[int], period: int = 20) -> float:
        """거래량 비율 (VR) 계산"""
        if len(volumes) < 2:
            return 1.0
        
        current_volume = volumes[-1]
        avg_volume = np.mean(volumes[-period:]) if len(volumes) >= period else np.mean(volumes)
        
        if avg_volume == 0:
            return 1.0
        
        return float(current_volume / avg_volume)

class MarketConditionAnalyzer:
    """시장 조건 분석기"""
    
    def __init__(self):
        self.kospi_threshold = {"bull": 0.02, "bear": -0.02}
        self.volatility_threshold = {"high": 0.03, "low": 0.01}
    
    def analyze_market_condition(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """시장 조건 분석"""
        conditions = {
            "market_trend": "NEUTRAL",
            "volatility": "MEDIUM",
            "sentiment": "NEUTRAL",
            "risk_level": "MEDIUM"
        }
        
        try:
            # 시장 추세 분석
            kospi_change = market_data.get("kospi_change_pct", 0)
            if kospi_change > self.kospi_threshold["bull"]:
                conditions["market_trend"] = "BULLISH"
            elif kospi_change < self.kospi_threshold["bear"]:
                conditions["market_trend"] = "BEARISH"
            
            # 변동성 분석
            volatility = market_data.get("volatility", 0.02)
            if volatility > self.volatility_threshold["high"]:
                conditions["volatility"] = "HIGH"
            elif volatility < self.volatility_threshold["low"]:
                conditions["volatility"] = "LOW"
            
            # 종합 리스크 레벨
            if conditions["market_trend"] == "BEARISH" and conditions["volatility"] == "HIGH":
                conditions["risk_level"] = "HIGH"
            elif conditions["market_trend"] == "BULLISH" and conditions["volatility"] == "LOW":
                conditions["risk_level"] = "LOW"
            
            # 추가 지표들
            conditions.update({
                "trading_session": self._get_trading_session(),
                "market_phase": self._analyze_market_phase(market_data),
                "liquidity": self._assess_liquidity(market_data)
            })
            
        except Exception as e:
            logger.error(f"시장 조건 분석 오류: {e}")
        
        return conditions
    
    def _get_trading_session(self) -> str:
        """거래 세션 구분"""
        now = datetime.now()
        hour = now.hour
        
        if 9 <= hour < 12:
            return "MORNING"
        elif 12 <= hour < 15:
            return "AFTERNOON"
        elif 15 <= hour < 16:
            return "CLOSING"
        else:
            return "AFTER_HOURS"
    
    def _analyze_market_phase(self, market_data: Dict[str, Any]) -> str:
        """시장 국면 분석"""
        # 간단한 국면 분류
        volume_ratio = market_data.get("volume_ratio", 1.0)
        price_momentum = market_data.get("price_momentum", 0.0)
        
        if volume_ratio > 1.5 and abs(price_momentum) > 0.02:
            return "ACTIVE"
        elif volume_ratio < 0.7:
            return "QUIET"
        else:
            return "NORMAL"
    
    def _assess_liquidity(self, market_data: Dict[str, Any]) -> str:
        """유동성 평가"""
        volume_ratio = market_data.get("volume_ratio", 1.0)
        spread = market_data.get("bid_ask_spread", 0.01)
        
        if volume_ratio > 1.5 and spread < 0.005:
            return "HIGH"
        elif volume_ratio < 0.5 or spread > 0.02:
            return "LOW"
        else:
            return "NORMAL"

class IntelligentContextBuilder:
    """지능형 컨텍스트 빌더"""
    
    def __init__(self):
        self.stock_manager = StockDataManager()
        self.data_system = IntegratedFreeDataSystem()
        self.tech_calculator = TechnicalIndicatorCalculator()
        self.market_analyzer = MarketConditionAnalyzer()
        
        # 캐시 설정
        self.cache_ttl = 300  # 5분
        self.price_history_cache = {}
        
        logger.info("지능형 컨텍스트 빌더 초기화 완료")
    
    async def build_context(self, symbol: str, korean_code: str = None) -> MarketContext:
        """
        종목별 시장 컨텍스트 구성
        
        Args:
            symbol: 국제 심볼 (예: 'AAPL', '005930.KS')
            korean_code: 한국 종목 코드 (예: '005930')
        
        Returns:
            완성된 시장 컨텍스트
        """
        try:
            # 1. 현재 주가 데이터 수집
            stock_data = await self.stock_manager.get_stock_data(
                symbol=symbol,
                korean_code=korean_code,
                use_cache=True,
                cache_ttl=self.cache_ttl
            )
            
            if not stock_data or not stock_data.get('aggregated'):
                raise ValueError(f"주가 데이터 없음: {symbol}")
            
            agg_data = stock_data['aggregated']
            
            # 2. 가격 히스토리 수집 (기술적 지표용)
            price_history = await self._get_price_history(symbol, korean_code)
            
            # 3. 기술적 지표 계산
            technical_indicators = await self._calculate_technical_indicators(price_history)
            
            # 4. 뉴스 감정분석
            news_sentiment = await self._analyze_news_sentiment(symbol, korean_code)
            
            # 5. 시장 조건 분석
            market_conditions = await self._get_market_conditions()
            
            # 6. 리스크 요인 식별
            risk_factors = await self._identify_risk_factors(
                symbol, agg_data, technical_indicators, news_sentiment
            )
            
            # 7. 컨텍스트 구성
            context = MarketContext(
                symbol=symbol,
                current_price=float(agg_data.get('current_price', 0)),
                price_change_pct=float(agg_data.get('change_percent', 0)),
                volume=int(agg_data.get('volume', 0)),
                technical_indicators=technical_indicators,
                news_sentiment=news_sentiment,
                market_conditions=market_conditions,
                risk_factors=risk_factors,
                timestamp=datetime.now()
            )
            
            logger.info(f"컨텍스트 구성 완료: {symbol}")
            return context
            
        except Exception as e:
            logger.error(f"컨텍스트 구성 실패 ({symbol}): {e}")
            return self._create_minimal_context(symbol)
    
    async def _get_price_history(self, symbol: str, korean_code: str) -> List[float]:
        """가격 히스토리 수집"""
        cache_key = f"{symbol}_{korean_code}_history"
        
        # 캐시 확인
        if cache_key in self.price_history_cache:
            cached_data, timestamp = self.price_history_cache[cache_key]
            if (datetime.now() - timestamp).seconds < self.cache_ttl:
                return cached_data
        
        try:
            # 실제 환경에서는 더 정교한 히스토리 데이터 수집 로직 필요
            # 현재는 시뮬레이션 데이터 생성
            current_data = await self.stock_manager.get_stock_data(symbol, korean_code)
            if current_data and current_data.get('aggregated'):
                current_price = current_data['aggregated'].get('current_price', 100)
                
                # 간단한 시뮬레이션 히스토리 (실제로는 DB나 API에서 가져와야 함)
                base_price = current_price
                history = []
                for i in range(50):  # 50일 히스토리 시뮬레이션
                    noise = np.random.normal(0, 0.02)  # 2% 표준편차
                    trend = -0.001 * i if i < 25 else 0.001 * (i - 25)  # 간단한 추세
                    price = base_price * (1 + trend + noise)
                    history.append(max(price, base_price * 0.5))  # 최소 50% 가격 보장
                
                history.append(current_price)  # 현재가 추가
                
                # 캐시 저장
                self.price_history_cache[cache_key] = (history, datetime.now())
                return history
            
        except Exception as e:
            logger.error(f"가격 히스토리 수집 실패: {e}")
        
        # 기본값
        return [100.0] * 20
    
    async def _calculate_technical_indicators(self, price_history: List[float]) -> Dict[str, float]:
        """기술적 지표 계산"""
        try:
            indicators = {}
            
            if len(price_history) >= 2:
                # RSI
                indicators['rsi'] = self.tech_calculator.calculate_rsi(price_history)
                
                # MACD
                macd_data = self.tech_calculator.calculate_macd(price_history)
                indicators.update({
                    'macd': macd_data['macd'],
                    'macd_signal': macd_data['signal'],
                    'macd_histogram': macd_data['histogram']
                })
                
                # 볼린저 밴드
                bb_data = self.tech_calculator.calculate_bollinger_bands(price_history)
                indicators.update({
                    'bb_upper': bb_data['upper'],
                    'bb_middle': bb_data['middle'], 
                    'bb_lower': bb_data['lower'],
                    'bb_position': bb_data['position']
                })
                
                # 추가 지표들
                indicators.update({
                    'price_momentum': (price_history[-1] / price_history[-5] - 1) if len(price_history) >= 5 else 0,
                    'price_volatility': float(np.std(price_history[-20:])) / np.mean(price_history[-20:]) if len(price_history) >= 20 else 0.02,
                    'trend_strength': self._calculate_trend_strength(price_history),
                })
                
            return indicators
            
        except Exception as e:
            logger.error(f"기술적 지표 계산 실패: {e}")
            return {
                'rsi': 50.0,
                'macd': 0.0,
                'macd_signal': 0.0,
                'macd_histogram': 0.0,
                'bb_position': 0.5,
                'price_momentum': 0.0,
                'price_volatility': 0.02,
                'trend_strength': 0.0
            }
    
    def _calculate_trend_strength(self, prices: List[float]) -> float:
        """추세 강도 계산"""
        if len(prices) < 10:
            return 0.0
        
        # 선형 회귀 기울기로 추세 강도 측정
        x = np.arange(len(prices))
        y = np.array(prices)
        
        try:
            slope, _ = np.polyfit(x, y, 1)
            return float(slope / np.mean(prices))  # 정규화된 기울기
        except:
            return 0.0
    
    async def _analyze_news_sentiment(self, symbol: str, korean_code: str) -> Dict[str, float]:
        """뉴스 감정분석"""
        try:
            # 뉴스 데이터 수집
            news_articles = await self.data_system.collect_news_data()
            
            if not news_articles:
                return {"positive": 0.33, "neutral": 0.34, "negative": 0.33}
            
            # 종목 관련 뉴스 필터링
            relevant_articles = []
            if korean_code:
                # 한국 종목의 경우 회사명으로 필터링 (개선 필요)
                company_names = {
                    '005930': ['삼성전자', '삼성', 'Samsung'],
                    '000660': ['SK하이닉스', 'SK Hynix'],
                    '035420': ['네이버', 'NAVER'],
                    # 더 많은 매핑 필요
                }
                names = company_names.get(korean_code, [symbol])
                
                for article in news_articles[:20]:  # 최근 20개
                    if any(name in article.title or name in article.content for name in names):
                        relevant_articles.append(article)
            
            # 감정분석 수행
            if relevant_articles:
                sentiment_scores = self.data_system.analyze_sentiment(relevant_articles)
            else:
                # 전체 시장 감정 사용
                sentiment_scores = self.data_system.analyze_sentiment(news_articles[:10])
            
            return sentiment_scores
            
        except Exception as e:
            logger.error(f"뉴스 감정분석 실패: {e}")
            return {"positive": 0.33, "neutral": 0.34, "negative": 0.33}
    
    async def _get_market_conditions(self) -> Dict[str, Any]:
        """시장 조건 분석"""
        try:
            # 시장 전반 데이터 수집
            market_data = {}
            
            # KOSPI 데이터 (시뮬레이션)
            market_data.update({
                "kospi_change_pct": np.random.normal(0, 0.015),  # ±1.5% 표준편차
                "kosdaq_change_pct": np.random.normal(0, 0.02),  # ±2% 표준편차
                "volatility": abs(np.random.normal(0.02, 0.01)),  # 변동성
                "volume_ratio": max(0.1, np.random.lognormal(0, 0.3)),  # 거래량 비율
                "market_cap_flow": np.random.normal(0, 1000000000),  # 자금 유입/유출
            })
            
            # 시장 조건 분석
            conditions = self.market_analyzer.analyze_market_condition(market_data)
            conditions.update(market_data)
            
            return conditions
            
        except Exception as e:
            logger.error(f"시장 조건 분석 실패: {e}")
            return {
                "market_trend": "NEUTRAL",
                "volatility": "MEDIUM",
                "risk_level": "MEDIUM",
                "trading_session": "NORMAL"
            }
    
    async def _identify_risk_factors(
        self,
        symbol: str,
        stock_data: Dict[str, Any],
        technical_indicators: Dict[str, float],
        news_sentiment: Dict[str, float]
    ) -> List[str]:
        """리스크 요인 식별"""
        risk_factors = []
        
        try:
            # 가격 급등/급락 위험
            change_pct = abs(stock_data.get('change_percent', 0))
            if change_pct > 5:
                risk_factors.append(f"급격한 가격 변동: {change_pct:.1f}%")
            
            # 기술적 리스크
            rsi = technical_indicators.get('rsi', 50)
            if rsi > 80:
                risk_factors.append("과매수 구간 (RSI > 80)")
            elif rsi < 20:
                risk_factors.append("과매도 구간 (RSI < 20)")
            
            bb_position = technical_indicators.get('bb_position', 0.5)
            if bb_position > 0.95:
                risk_factors.append("볼린저 밴드 상단 근접")
            elif bb_position < 0.05:
                risk_factors.append("볼린저 밴드 하단 근접")
            
            # 거래량 리스크
            volume = stock_data.get('volume', 0)
            if volume == 0:
                risk_factors.append("거래량 없음")
            
            # 뉴스 감정 리스크
            negative_sentiment = news_sentiment.get('negative', 0)
            if negative_sentiment > 0.7:
                risk_factors.append("부정적 뉴스 지배")
            
            # 변동성 리스크
            volatility = technical_indicators.get('price_volatility', 0)
            if volatility > 0.05:
                risk_factors.append(f"높은 변동성: {volatility*100:.1f}%")
            
            # 시간대 리스크
            hour = datetime.now().hour
            if hour < 9 or hour > 15:
                risk_factors.append("정규 거래시간 외")
            
        except Exception as e:
            logger.error(f"리스크 요인 식별 오류: {e}")
            risk_factors.append("데이터 분석 오류")
        
        return risk_factors
    
    def _create_minimal_context(self, symbol: str) -> MarketContext:
        """최소 컨텍스트 생성 (오류 시)"""
        return MarketContext(
            symbol=symbol,
            current_price=0.0,
            price_change_pct=0.0,
            volume=0,
            technical_indicators={
                'rsi': 50.0,
                'macd': 0.0,
                'bb_position': 0.5
            },
            news_sentiment={"positive": 0.33, "neutral": 0.34, "negative": 0.33},
            market_conditions={
                "market_trend": "NEUTRAL",
                "volatility": "MEDIUM",
                "risk_level": "HIGH"  # 데이터 없을 때는 고위험으로 처리
            },
            risk_factors=["데이터 수집 실패"],
            timestamp=datetime.now()
        )
    
    async def build_batch_contexts(self, symbols_and_codes: List[tuple]) -> List[MarketContext]:
        """여러 종목 컨텍스트 일괄 구성"""
        semaphore = asyncio.Semaphore(5)  # 동시 처리 제한
        
        async def limited_build(symbol_code):
            async with semaphore:
                symbol, korean_code = symbol_code
                return await self.build_context(symbol, korean_code)
        
        tasks = [limited_build(sc) for sc in symbols_and_codes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"배치 컨텍스트 구성 오류 ({symbols_and_codes[i]}): {result}")
                final_results.append(self._create_minimal_context(symbols_and_codes[i][0]))
            else:
                final_results.append(result)
        
        return final_results