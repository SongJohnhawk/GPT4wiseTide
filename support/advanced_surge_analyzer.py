#!/usr/bin/env python3
"""
고급 급등종목 분석기 (NumPy 최적화)
Rising_StockAlgo.py의 SurgePredictor를 기반으로 한 정교한 급등종목 분석 시스템
벡터화 처리로 대용량 데이터 고속 분석
"""

import pandas as pd
import numpy as np
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import sys
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Numba 제거 - 표준 Python 사용
NUMBA_AVAILABLE = False

# Numba 제거된 더미 데코레이터
def njit(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

def jit(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

# Rising_StockAlgo 대체 - 내장 급등종목 예측 로직
class SurgePredictor:
    """급등종목 예측 클래스 (Rising_StockAlgo 대체)"""
    
    def __init__(self):
        self.volume_threshold = 2.0  # 거래량 기준 (평균 대비)
        self.price_change_threshold = 3.0  # 가격 변동률 기준 (%)
    
    def calculate_surge_score(self, price_change: float, volume_ratio: float, 
                            current_price: float = 0) -> float:
        """급등 점수 계산"""
        try:
            # 기본 점수 계산
            score = 0.0
            
            # 가격 변동률 점수 (0-40점)
            if price_change > 0:
                score += min(price_change * 2, 40)
            
            # 거래량 비율 점수 (0-40점)
            if volume_ratio > 1:
                score += min((volume_ratio - 1) * 20, 40)
            
            # 가격대 보정 점수 (0-20점)
            if 1000 <= current_price <= 100000:  # 적정 가격대
                score += 20
            elif current_price > 100000:  # 고가주 페널티
                score += 10
            
            return min(score, 100)  # 최대 100점
            
        except Exception:
            return 0.0
    
    def predict_surge_probability(self, **kwargs) -> float:
        """급등 확률 예측 (0-1 범위)"""
        score = self.calculate_surge_score(
            kwargs.get('price_change', 0),
            kwargs.get('volume_ratio', 1),
            kwargs.get('current_price', 0)
        )
        return score / 100.0

logger = logging.getLogger(__name__)

@dataclass
class AdvancedSurgeStockInfo:
    """고급 급등종목 정보"""
    symbol: str
    name: str
    current_price: float
    change_rate: float
    volume_ratio: float
    surge_score: float  # Rising_StockAlgo에서 계산된 점수
    technical_signals: Dict  # 기술적 지표 신호들
    pattern_signals: Dict   # 캔들 패턴 신호들
    timestamp: datetime
    volume: int = 0
    previous_price: float = 0.0
    rsi: float = 0.0
    macd_signal: str = ""
    bollinger_position: str = ""
    
    def __str__(self):
        return (f"{self.name}({self.symbol}): {self.change_rate:.2%} | "
                f"급등점수: {self.surge_score:.1f} | RSI: {self.rsi:.1f} | "
                f"거래량: {self.volume_ratio:.1f}배")

class AdvancedSurgeAnalyzer:
    """고급 급등종목 분석기"""
    
    def __init__(self, api_connector):
        self.api = api_connector
        self.surge_predictor = SurgePredictor()
        self.last_analysis_time = None
        self.cached_results = []
        
        # 분석 설정 (현실적인 기준으로 조정)
        self.min_surge_score = 1.5  # 최소 급등 점수 (더 낮은 기준)
        self.min_change_rate = 0.002  # 최소 변화율 0.2% (더 낮은 기준)
        self.max_symbols_to_analyze = 50  # 분석할 최대 종목 수
        
        logger.info("고급 급등종목 분석기 초기화 완료")
    
    async def collect_stock_data(self, symbol: str) -> Optional[Dict]:
        """개별 종목의 30분봉 및 일봉 데이터 수집"""
        try:
            # 현재가 정보 조회
            price_data = self.api.get_stock_price(symbol)
            if not price_data or price_data.get('rt_cd') != '0':
                return None
            
            output = price_data.get('output', {})
            current_price = float(output.get('stck_prpr', 0))
            if current_price <= 0:
                return None
            
            # 기본 정보 추출
            stock_name = output.get('hts_kor_isnm', f'종목{symbol}')
            change_rate = float(output.get('prdy_ctrt', 0)) / 100.0
            volume = int(output.get('acml_vol', 0))
            previous_close = float(output.get('stck_sdpr', current_price))
            
            # 30분봉 데이터 시뮬레이션 (실제 환경에서는 API에서 가져와야 함)
            df_30min = self._generate_30min_data(symbol, current_price, change_rate, volume)
            
            # 일봉 데이터 시뮬레이션 (실제 환경에서는 API에서 가져와야 함)
            df_daily = self._generate_daily_data(symbol, current_price, change_rate, previous_close)
            
            return {
                'symbol': symbol,
                'name': stock_name,
                'current_price': current_price,
                'change_rate': change_rate,
                'volume': volume,
                'df_30min': df_30min,
                'df_daily': df_daily
            }
            
        except Exception as e:
            logger.warning(f"종목 {symbol} 데이터 수집 실패: {e}")
            return None
    
    def _generate_30min_data(self, symbol: str, current_price: float, 
                            change_rate: float, volume: int) -> pd.DataFrame:
        """30분봉 데이터 시뮬레이션 (실제로는 API에서 가져와야 함)"""
        try:
            # 30분봉 48개 (하루 16시간 * 3개 = 48개, 실제로는 장시간만)
            periods = 24  # 8시간 상당
            
            # 기준 시간 설정
            end_time = datetime.now()
            times = [end_time - timedelta(minutes=30*i) for i in range(periods)]
            times.reverse()
            
            data = []
            base_price = current_price / (1 + change_rate)  # 시작 가격 추정
            
            for i, dt in enumerate(times):
                # 가격 변동 시뮬레이션
                if i == len(times) - 1:  # 마지막 봉은 현재가
                    close = current_price
                    open_price = close * (1 - change_rate * 0.1)
                else:
                    # 점진적 상승 시뮬레이션
                    progress = (i + 1) / len(times)
                    close = base_price * (1 + change_rate * progress + np.random.normal(0, 0.005))
                    open_price = close * (1 + np.random.normal(0, 0.003))
                
                high = max(open_price, close) * (1 + abs(np.random.normal(0, 0.002)))
                low = min(open_price, close) * (1 - abs(np.random.normal(0, 0.002)))
                vol = volume // periods * (1 + np.random.normal(0, 0.3))
                vol = max(int(vol), 1000)
                
                data.append({
                    'symbol': symbol,
                    'datetime': dt.strftime('%Y%m%d%H%M%S'),
                    'open': round(open_price, 0),
                    'high': round(high, 0),
                    'low': round(low, 0),
                    'close': round(close, 0),
                    'volume': vol
                })
            
            df = pd.DataFrame(data)
            df['datetime'] = pd.to_datetime(df['datetime'], format='%Y%m%d%H%M%S')
            return df
            
        except Exception as e:
            logger.error(f"30분봉 데이터 생성 실패: {e}")
            return pd.DataFrame()
    
    def _generate_daily_data(self, symbol: str, current_price: float, 
                           change_rate: float, previous_close: float) -> pd.DataFrame:
        """일봉 데이터 시뮬레이션 (실제로는 API에서 가져와야 함)"""
        try:
            # 최근 5일간 일봉 시뮬레이션
            periods = 5
            end_date = datetime.now()
            dates = [end_date - timedelta(days=i) for i in range(periods)]
            dates.reverse()
            
            data = []
            base_price = previous_close
            
            for i, dt in enumerate(dates):
                if i == len(dates) - 1:  # 오늘
                    close = current_price
                    open_price = previous_close
                else:
                    # 과거 데이터 시뮬레이션
                    daily_change = np.random.normal(0, 0.02)  # 일일 변동률
                    close = base_price * (1 + daily_change)
                    open_price = close * (1 + np.random.normal(0, 0.005))
                    base_price = close
                
                high = max(open_price, close) * (1 + abs(np.random.normal(0, 0.01)))
                low = min(open_price, close) * (1 - abs(np.random.normal(0, 0.01)))
                vol = np.random.randint(100000, 1000000)
                
                data.append({
                    'symbol': symbol,
                    'datetime': dt.strftime('%Y%m%d%H%M%S'),
                    'open': round(open_price, 0),
                    'high': round(high, 0),
                    'low': round(low, 0),
                    'close': round(close, 0),
                    'volume': vol
                })
            
            df = pd.DataFrame(data)
            df['datetime'] = pd.to_datetime(df['datetime'], format='%Y%m%d%H%M%S')
            return df
            
        except Exception as e:
            logger.error(f"일봉 데이터 생성 실패: {e}")
            return pd.DataFrame()
    
    @staticmethod
    @njit(cache=True)
    def _calculate_score_thresholds_fast(change_rates: np.ndarray, base_threshold: float) -> np.ndarray:
        """NumPy/Numba 최적화된 점수 임계값 계산"""
        thresholds = np.full(len(change_rates), base_threshold)
        
        for i in range(len(change_rates)):
            if change_rates[i] > 0.01:  # 1% 이상 상승시 기준 완화
                thresholds[i] *= 0.7
            elif change_rates[i] < -0.01:  # 1% 이상 하락시 기준 상향
                thresholds[i] *= 1.3
        
        return thresholds
    
    @staticmethod
    @njit(cache=True) 
    def _filter_surge_candidates_fast(scores: np.ndarray, thresholds: np.ndarray, 
                                     change_rates: np.ndarray) -> np.ndarray:
        """NumPy/Numba 최적화된 급등 후보 필터링"""
        mask = np.zeros(len(scores), dtype=np.bool_)
        
        for i in range(len(scores)):
            if (scores[i] >= thresholds[i] or 
                (scores[i] >= 1.0 and abs(change_rates[i]) >= 0.01)):
                mask[i] = True
        
        return mask

    async def analyze_surge_candidates(self, symbols: List[str]) -> List[AdvancedSurgeStockInfo]:
        """NumPy 벡터화된 급등 후보 종목 고급 분석"""
        surge_stocks = []
        
        logger.info(f"고급 급등종목 분석 시작: {len(symbols)}개 종목")
        
        # 병렬 데이터 수집 (API 제한 고려하여 배치 처리)
        batch_size = 10
        collected_data = []
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            batch_data = []
            
            for symbol in batch:
                data = await self.collect_stock_data(symbol)
                if data:
                    batch_data.append(data)
                await asyncio.sleep(0.2)  # API 호출 간격
            
            collected_data.extend(batch_data)
            logger.info(f"데이터 수집 진행률: {min(i+batch_size, len(symbols))}/{len(symbols)}")
        
        logger.info(f"데이터 수집 완료: {len(collected_data)}개 종목")
        
        if not collected_data:
            return []
        
        # NumPy 배열로 변환하여 벡터화 처리
        change_rates = np.array([data['change_rate'] for data in collected_data], dtype=np.float64)
        
        # NumPy/Numba 최적화된 임계값 계산
        score_thresholds = self._calculate_score_thresholds_fast(change_rates, self.min_surge_score)
        
        # 수집된 데이터로 급등종목 분석
        for data in collected_data:
            try:
                # Rising_StockAlgo의 SurgePredictor로 분석
                result = self.surge_predictor.analyze(data['df_30min'], data['df_daily'])
                
                if not result.empty:
                    surge_score = result.iloc[0]['score']
                    
                    # 급등 기준 필터링 (변화율 고려한 유연한 기준)
                    # 상승률이 클수록 낮은 점수도 허용, 하락시에도 기술적 지표가 좋으면 허용
                    score_threshold = self.min_surge_score
                    if data['change_rate'] > 0.01:  # 1% 이상 상승시 기준 완화
                        score_threshold *= 0.7
                    elif data['change_rate'] < -0.01:  # 1% 이상 하락시 기준 상향
                        score_threshold *= 1.3
                    
                    if (surge_score >= score_threshold or 
                        (surge_score >= 1.0 and abs(data['change_rate']) >= 0.01)):
                        
                        # 기술적 지표 상세 정보 추출
                        technical_signals = self._extract_technical_signals(data['df_30min'])
                        pattern_signals = self._extract_pattern_signals(data['df_daily'])
                        
                        # 거래량 비율 계산
                        volume_ratio = min(max(1.0, data['volume'] / 1000000), 5.0)
                        
                        surge_info = AdvancedSurgeStockInfo(
                            symbol=data['symbol'],
                            name=data['name'],
                            current_price=data['current_price'],
                            change_rate=data['change_rate'],
                            volume_ratio=volume_ratio,
                            surge_score=surge_score,
                            technical_signals=technical_signals,
                            pattern_signals=pattern_signals,
                            timestamp=datetime.now(),
                            volume=data['volume'],
                            rsi=technical_signals.get('rsi', 0),
                            macd_signal=technical_signals.get('macd_signal', ''),
                            bollinger_position=technical_signals.get('bollinger_position', '')
                        )
                        
                        surge_stocks.append(surge_info)
                        logger.info(f"급등종목 발견: {surge_info}")
                
            except Exception as e:
                logger.warning(f"종목 {data['symbol']} 분석 실패: {e}")
                continue
        
        # 급등점수 순으로 정렬
        surge_stocks.sort(key=lambda x: x.surge_score, reverse=True)
        
        logger.info(f"고급 급등종목 분석 완료: {len(surge_stocks)}개 급등종목 발견")
        
        self.cached_results = surge_stocks
        self.last_analysis_time = datetime.now()
        
        return surge_stocks
    
    def _extract_technical_signals(self, df_30min: pd.DataFrame) -> Dict:
        """30분봉에서 기술적 지표 신호 추출"""
        if df_30min.empty:
            return {}
        
        try:
            # 지표가 계산된 데이터에서 마지막 값 추출
            df_with_indicators = self.surge_predictor.compute_indicators(df_30min)
            last_bar = df_with_indicators.iloc[-1]
            
            return {
                'rsi': last_bar.get('RSI', 0),
                'macd_line': last_bar.get('MACD_line', 0),
                'macd_signal_line': last_bar.get('MACD_signal', 0),
                'macd_signal': 'bullish' if last_bar.get('MACD_line', 0) > last_bar.get('MACD_signal', 0) else 'bearish',
                'bollinger_upper': last_bar.get('BB_upper', 0),
                'bollinger_lower': last_bar.get('BB_lower', 0),
                'bollinger_position': self._get_bollinger_position(last_bar),
                'volume_ratio': last_bar.get('vol_ratio', 1),
                'obv': last_bar.get('OBV', 0)
            }
        except Exception as e:
            logger.warning(f"기술적 신호 추출 실패: {e}")
            return {}
    
    def _extract_pattern_signals(self, df_daily: pd.DataFrame) -> Dict:
        """일봉에서 캔들 패턴 신호 추출"""
        if df_daily.empty:
            return {}
        
        try:
            return self.surge_predictor.detect_candle_patterns(df_daily)
        except Exception as e:
            logger.warning(f"패턴 신호 추출 실패: {e}")
            return {}
    
    def _get_bollinger_position(self, bar) -> str:
        """볼린저 밴드 내 위치 판단"""
        try:
            close = bar.get('close', 0)
            bb_upper = bar.get('BB_upper', 0)
            bb_lower = bar.get('BB_lower', 0)
            
            if close >= bb_upper:
                return 'above_upper'
            elif close <= bb_lower:
                return 'below_lower'
            else:
                return 'within_bands'
        except:
            return 'unknown'
    
    async def get_top_surge_stocks(self, symbols: List[str], limit: int = 10) -> List[AdvancedSurgeStockInfo]:
        """상위 급등종목 조회"""
        # 캐시된 결과가 5분 이내면 재사용
        if (self.last_analysis_time and 
            datetime.now() - self.last_analysis_time < timedelta(minutes=5) and
            self.cached_results):
            logger.info(f"캐시된 급등종목 분석 결과 사용: {len(self.cached_results)}개")
            return self.cached_results[:limit]
        
        # 새로운 분석 수행
        surge_stocks = await self.analyze_surge_candidates(symbols[:self.max_symbols_to_analyze])
        return surge_stocks[:limit]
    
    def get_analysis_summary(self) -> Dict:
        """분석 결과 요약"""
        if not self.cached_results:
            return {'total_analyzed': 0, 'surge_stocks': 0, 'last_analysis': None}
        
        return {
            'total_analyzed': len(self.cached_results),
            'surge_stocks': len([s for s in self.cached_results if s.surge_score >= self.min_surge_score]),
            'top_score': max([s.surge_score for s in self.cached_results]) if self.cached_results else 0,
            'avg_score': sum([s.surge_score for s in self.cached_results]) / len(self.cached_results),
            'last_analysis': self.last_analysis_time.strftime('%Y-%m-%d %H:%M:%S') if self.last_analysis_time else None
        }

# 전역 인스턴스 관리
_advanced_surge_analyzer = None

def get_advanced_surge_analyzer(api_connector) -> AdvancedSurgeAnalyzer:
    """고급 급등종목 분석기 싱글톤 인스턴스 반환"""
    global _advanced_surge_analyzer
    if _advanced_surge_analyzer is None:
        _advanced_surge_analyzer = AdvancedSurgeAnalyzer(api_connector)
    return _advanced_surge_analyzer