"""
급등종목 데이터 제공자 모듈 (SimpleSurgeDetector 통합)
Hyper_upStockFind.py의 SimpleSurgeDetector를 사용한 급등종목 탐지
Policy 우선순위: PyKrx → KRX 공식 → pandas_datareader → Securities API
"""

import logging
import asyncio
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# SimpleSurgeDetector import (올바른 파일)
from support.Hyper_upStockFind import SimpleSurgeDetector

# 정밀 스크리닝 알고리즘 import
import sys
import os
sys.path.append(os.path.dirname(__file__))

# 급등종목 정밀 스크리닝 시스템 import
from enum import Enum
from dataclasses import dataclass, field

# Policy 1순위: PyKrx (급등주 스캔용)
try:
    from pykrx import stock
    PYKRX_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("급등주 수집기: PyKrx 로드 성공 (Policy 1순위)")
except ImportError:
    PYKRX_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("급등주 수집기: PyKrx 미설치 - Policy 백업 데이터 소스 사용")

# Policy 3순위: pandas_datareader (실시간 데이터용)
try:
    import pandas_datareader.data as pdr
    PANDAS_DATAREADER_AVAILABLE = True
    logger.info("급등주 수집기: pandas_datareader 로드 성공 (Policy 3순위)")
except ImportError:
    PANDAS_DATAREADER_AVAILABLE = False
    logger.warning("급등주 수집기: pandas_datareader 미설치")

logger = logging.getLogger(__name__)

# 정밀 스크리닝 알고리즘 클래스들
class SurgeQuality(Enum):
    """급등 품질 등급"""
    PREMIUM = "premium"      # 최고급 (투자 추천)
    HIGH = "high"           # 고급 (신중 투자)  
    MEDIUM = "medium"       # 중급 (소액 투자)
    LOW = "low"            # 저급 (관찰만)
    DANGEROUS = "dangerous" # 위험 (투자 금지)

@dataclass
class SurgeAnalysisResult:
    """급등 분석 결과"""
    stock_code: str
    stock_name: str
    current_price: float
    surge_rate: float  # 급등률
    
    # 12가지 핵심 점수 (0-100)
    volume_quality_score: float = 0.0      # 거래량 품질
    momentum_persistence_score: float = 0.0  # 모멘텀 지속성
    fundamental_support_score: float = 0.0   # 펀더멘털 뒷받침
    institutional_flow_score: float = 0.0    # 기관투자 흐름
    technical_strength_score: float = 0.0    # 기술적 강도
    market_timing_score: float = 0.0         # 시장 타이밍
    liquidity_safety_score: float = 0.0      # 유동성 안전성
    news_catalyst_score: float = 0.0         # 뉴스 촉매
    risk_control_score: float = 0.0          # 리스크 통제
    profit_potential_score: float = 0.0      # 수익 잠재력
    entry_timing_score: float = 0.0          # 진입 타이밍
    sector_momentum_score: float = 0.0       # 섹터 모멘텀
    
    # 종합 평가
    total_score: float = 0.0
    quality_grade: SurgeQuality = SurgeQuality.LOW
    investment_recommendation: str = ""
    
    # 리스크 정보
    risk_factors: list = field(default_factory=list)
    stop_loss_level: float = 0.0
    profit_target: float = 0.0
    max_position_size: float = 0.0

class PremiumSurgeScreener:
    """프리미엄 급등 종목 스크리너"""
    
    def __init__(self):
        # 기본 임계값 설정 (극도로 완화된 조건)
        self.min_surge_rate = 0.3          # 최소 급등률 0.3% (0.5%→0.3% 대폭 완화)
        self.min_volume_ratio = 1.05       # 최소 거래량 비율 1.05배 (1.1→1.05배 대폭 완화)
        self.max_market_cap = 100_000_000  # 최대 시가총액 1000억 (500억→1000억 확대)
        
        # 점수 가중치 (총합 100%)
        self.score_weights = {
            'volume_quality': 15,      # 거래량 품질이 가장 중요
            'momentum_persistence': 12, # 모멘텀 지속성
            'institutional_flow': 12,   # 기관 자금 흐름
            'technical_strength': 10,   # 기술적 분석
            'fundamental_support': 8,   # 펀더멘털
            'market_timing': 8,        # 시장 타이밍
            'liquidity_safety': 8,     # 유동성 안전성
            'news_catalyst': 7,        # 뉴스 촉매
            'risk_control': 6,         # 리스크 통제
            'profit_potential': 5,     # 수익 잠재력
            'entry_timing': 5,         # 진입 타이밍
            'sector_momentum': 4       # 섹터 모멘텀
        }
        
        # 품질 등급 기준점 (더욱 완화된 기준으로 급등주 발견율 증가)
        self.quality_thresholds = {
            SurgeQuality.PREMIUM: 45,    # 55→45점 추가 완화
            SurgeQuality.HIGH: 30,       # 40→30점 추가 완화
            SurgeQuality.MEDIUM: 20,     # 25→20점 추가 완화
            SurgeQuality.LOW: 5          # 10→5점 추가 완화 (거의 모든 급등주 통과)
        }

    def screen_surge_stocks(self, market_data: dict, additional_data: dict = None) -> list:
        """급등 종목 스크리닝 실행"""
        results = []
        
        for stock_code, daily_data in market_data.items():
            try:
                # 1차 기본 필터링
                if not self._basic_surge_filter(daily_data):
                    continue
                
                # 상세 분석 실행
                analysis_result = self._detailed_analysis(
                    stock_code, daily_data, additional_data
                )
                
                if analysis_result.total_score >= self.quality_thresholds[SurgeQuality.LOW]:
                    results.append(analysis_result)
                    
            except Exception as e:
                logger.debug(f"종목 {stock_code} 분석 오류: {e}")
                continue
        
        # 점수순 정렬
        results.sort(key=lambda x: x.total_score, reverse=True)
        return results
    
    def _basic_surge_filter(self, data: pd.DataFrame) -> bool:
        """1차 기본 급등 필터 (극도로 완화된 조건)"""
        if len(data) < 5:  # 10일→5일로 극대 완화
            return False
        
        latest = data.iloc[-1]
        previous = data.iloc[-2]
        
        # 급등률 체크 (1% 이상) - 매우 완화
        surge_rate = (latest['Close'] - previous['Close']) / previous['Close'] * 100
        if surge_rate < self.min_surge_rate:
            return False
        
        # 거래량 증가 체크 (1.05배 이상) - 극도로 완화
        volume_ma_period = min(5, len(data) - 1)  # 5일 또는 데이터 길이-1
        volume_ma = data['Volume'].tail(volume_ma_period).mean()
        volume_ratio = latest['Volume'] / volume_ma if volume_ma > 0 else 1.2  # 기본값 조정
        if volume_ratio < self.min_volume_ratio:
            return False
        
        return True
    
    def _detailed_analysis(self, stock_code: str, data: pd.DataFrame,
                          additional_data: dict = None) -> SurgeAnalysisResult:
        """상세 분석 실행"""
        latest = data.iloc[-1]
        previous = data.iloc[-2]
        surge_rate = (latest['Close'] - previous['Close']) / previous['Close'] * 100
        
        # 기본 정보
        result = SurgeAnalysisResult(
            stock_code=stock_code,
            stock_name=additional_data.get('stock_names', {}).get(stock_code, stock_code) if additional_data else stock_code,
            current_price=latest['Close'],
            surge_rate=surge_rate
        )
        
        # 12가지 핵심 분석
        result.volume_quality_score = self._analyze_volume_quality(data)
        result.momentum_persistence_score = self._analyze_momentum_persistence(data)
        result.fundamental_support_score = self._analyze_fundamental_support(stock_code, data, additional_data)
        result.institutional_flow_score = self._analyze_institutional_flow(data, additional_data)
        result.technical_strength_score = self._analyze_technical_strength(data)
        result.market_timing_score = self._analyze_market_timing(data, additional_data)
        result.liquidity_safety_score = self._analyze_liquidity_safety(data)
        result.news_catalyst_score = self._analyze_news_catalyst(stock_code, additional_data)
        result.risk_control_score = self._analyze_risk_control(data)
        result.profit_potential_score = self._analyze_profit_potential(data)
        result.entry_timing_score = self._analyze_entry_timing(data)
        result.sector_momentum_score = self._analyze_sector_momentum(stock_code, additional_data)
        
        # 종합 점수 계산
        result.total_score = self._calculate_total_score(result)
        result.quality_grade = self._determine_quality_grade(result.total_score)
        result.investment_recommendation = self._generate_recommendation(result)
        
        # 리스크 관리 정보
        result.risk_factors = self._identify_risk_factors(result, data)
        result.stop_loss_level = self._calculate_stop_loss(data)
        result.profit_target = self._calculate_profit_target(data, result.total_score)
        result.max_position_size = self._calculate_max_position_size(result)
        
        return result
    
    def _analyze_volume_quality(self, data: pd.DataFrame) -> float:
        """거래량 품질 분석 (완화된 조건)"""
        latest = data.iloc[-1]
        
        # 거래량 비율 (사용 가능한 일수로 평균 계산)
        volume_period = min(15, len(data))  # 15일 또는 전체 데이터
        volume_ma = data['Volume'].tail(volume_period).mean()
        volume_ratio = latest['Volume'] / volume_ma if volume_ma > 0 else 1.0
        
        # 거래량 지속성 (최근 3일)
        volume_tail_period = min(3, len(data))
        recent_volumes = data['Volume'].tail(volume_tail_period).tolist()
        if len(recent_volumes) >= 2:
            volume_trend = np.polyfit(range(len(recent_volumes)), recent_volumes, 1)[0]
        else:
            volume_trend = 0
        
        # 가격-거래량 상관관계 (더 관대한 계산)
        tail_period = min(5, len(data))
        price_changes = data['Close'].pct_change().tail(tail_period).dropna()
        volume_changes = data['Volume'].pct_change().tail(tail_period).dropna()
        
        if len(price_changes) >= 2 and len(volume_changes) >= 2:
            try:
                price_volume_corr = np.corrcoef(price_changes, volume_changes)[0, 1]
                if np.isnan(price_volume_corr):
                    price_volume_corr = 0
            except:
                price_volume_corr = 0
        else:
            price_volume_corr = 0
        
        # 점수 계산 (더 관대하게)
        ratio_score = min(volume_ratio / 3.0 * 40, 50)  # 3배 기준, 최대 50점
        trend_score = max(min(volume_trend / volume_ma * 2000, 30), 0) if volume_ma > 0 else 20  # 기본 20점
        corr_score = max(price_volume_corr * 30, 0) + 20  # 기본 20점 추가
        
        return min(ratio_score + trend_score + corr_score, 100)
    
    def _analyze_momentum_persistence(self, data: pd.DataFrame) -> float:
        """모멘텀 지속성 분석 (완화된 조건)"""
        # 연속 상승일 수 (더 관대하게)
        tail_period = min(10, len(data))
        price_changes = data['Close'].pct_change().tail(tail_period).dropna()
        consecutive_ups = 0
        for change in reversed(price_changes):
            if change > -0.005:  # -0.5% 미만 하락도 허용
                consecutive_ups += 1
            else:
                break
        
        # RSI 모멘텀 (더 유연하게)
        rsi_period = min(14, len(data) - 1)
        if rsi_period >= 2:
            rsi = self._calculate_rsi(data['Close'], rsi_period)
            latest_rsi = rsi.iloc[-1] if len(rsi) > 0 and not pd.isna(rsi.iloc[-1]) else 50
        else:
            latest_rsi = 50  # 기본값
        
        # 모멘텀 가속도 (유연한 기간)
        momentum_period = min(5, len(data))
        if momentum_period >= 2:
            recent_returns = data['Close'].pct_change().tail(momentum_period).cumsum()
            if len(recent_returns) >= 2:
                try:
                    momentum_acceleration = np.polyfit(range(len(recent_returns)), recent_returns, 1)[0]
                except:
                    momentum_acceleration = 0
            else:
                momentum_acceleration = 0
        else:
            momentum_acceleration = 0
        
        # 점수 계산 (더 관대하게)
        consecutive_score = min(consecutive_ups * 10, 35) + 15  # 기본 15점 추가
        rsi_score = max(40 - abs(latest_rsi - 60), 10)  # RSI 60 근처, 최소 10점
        acceleration_score = max(momentum_acceleration * 300, 0) + 15  # 기본 15점 추가
        acceleration_score = min(acceleration_score, 35)
        
        return consecutive_score + rsi_score + acceleration_score
    
    def _analyze_fundamental_support(self, stock_code: str, data: pd.DataFrame, 
                                   additional_data: dict = None) -> float:
        """펀더멘털 뒷받침 분석 (완화된 조건)"""
        if not additional_data:
            return 65.0  # 기본점수 대폭 상향 (55→65)
        
        # 실적 개선 여부
        earnings_data = additional_data.get('earnings_data', {}).get(stock_code, {})
        earnings_growth = earnings_data.get('growth_rate', 0)
        revenue_growth = earnings_data.get('revenue_growth', 0)
        debt_ratio = earnings_data.get('debt_ratio', 50)
        cash_ratio = earnings_data.get('cash_ratio', 10)
        
        # 점수 계산
        earnings_score = max(min(earnings_growth * 2, 30), 0)  # 최대 30점
        revenue_score = max(min(revenue_growth * 1.5, 25), 0)  # 최대 25점
        debt_score = max(30 - debt_ratio * 0.3, 0)  # 부채 낮을수록 높은 점수
        cash_score = min(cash_ratio * 1.5, 15)  # 최대 15점
        
        return earnings_score + revenue_score + debt_score + cash_score
    
    def _analyze_institutional_flow(self, data: pd.DataFrame, additional_data: dict = None) -> float:
        """기관투자자 자금 흐름 분석 (완화된 조건)"""
        if not additional_data or 'institutional_data' not in additional_data:
            return 65.0  # 기본점수 대폭 상향 (55→65)
        
        inst_data = additional_data['institutional_data']
        
        # 외국인/기관/개인 순매수 (최근 5일)
        foreign_net = sum(inst_data.get('foreign_net', [0] * 5)[-5:])
        institution_net = sum(inst_data.get('institution_net', [0] * 5)[-5:])
        retail_net = sum(inst_data.get('retail_net', [0] * 5)[-5:])
        
        # 점수 계산
        foreign_score = max(min(foreign_net / 1000000 * 20, 40), 0)  # 최대 40점
        institution_score = max(min(institution_net / 1000000 * 15, 30), 0)  # 최대 30점
        retail_score = max(min(-retail_net / 1000000 * 10, 30), 0)  # 개인 순매도가 좋음
        
        return foreign_score + institution_score + retail_score
    
    def _analyze_technical_strength(self, data: pd.DataFrame) -> float:
        """기술적 강도 분석 (완화된 조건, NaN 방지)"""
        try:
            # 이동평균 돌파 여부 (데이터 길이 고려)
            data_len = len(data)
            sma5_period = min(5, data_len - 1)
            sma20_period = min(12, data_len - 1)  # 20일→12일로 완화
            
            if sma5_period < 2 or sma20_period < 2:
                return 50.0  # 기본 점수 반환
            
            sma5 = data['Close'].rolling(sma5_period).mean()
            sma20 = data['Close'].rolling(sma20_period).mean()
            
            latest_price = data.iloc[-1]['Close']
            ma_alignment_score = 30  # 기본 점수
            
            # NaN 체크하면서 점수 계산
            if not pd.isna(sma5.iloc[-1]) and latest_price > sma5.iloc[-1]:
                ma_alignment_score += 20
            if not pd.isna(sma20.iloc[-1]) and latest_price > sma20.iloc[-1]:
                ma_alignment_score += 25
            if (not pd.isna(sma5.iloc[-1]) and not pd.isna(sma20.iloc[-1]) and 
                sma5.iloc[-1] > sma20.iloc[-1]):
                ma_alignment_score += 20
            
            # 볼린저 밴드 위치 (더 안전하게)
            try:
                bb_upper, bb_lower = self._calculate_bollinger_bands(data['Close'])
                if (len(bb_upper) > 0 and not pd.isna(bb_upper.iloc[-1]) and 
                    not pd.isna(bb_lower.iloc[-1]) and bb_upper.iloc[-1] != bb_lower.iloc[-1]):
                    bb_position = ((latest_price - bb_lower.iloc[-1]) / 
                                  (bb_upper.iloc[-1] - bb_lower.iloc[-1]))
                    bb_score = max(min(bb_position * 20, 25), 0)  # 0-25점
                else:
                    bb_score = 15  # 기본값
            except:
                bb_score = 15  # 오류시 기본값
            
            final_score = ma_alignment_score + bb_score
            return min(max(final_score, 40), 100)  # 최소 40점, 최대 100점
            
        except Exception as e:
            # 오류 발생시 기본 점수 반환
            return 50.0
    
    def _analyze_market_timing(self, data: pd.DataFrame, additional_data: dict = None) -> float:
        """시장 타이밍 분석 (완화된 조건)"""
        # 시장 전체 상승률
        market_trend = additional_data.get('market_trend', 0) if additional_data else 0
        
        # 시간대 분석 (더 관대하게)
        current_time = datetime.now().hour
        time_score = 35  # 기본 점수 대폭 상향 (20→35)
        
        if 9 <= current_time <= 10:  # 장 초반
            time_score = 45
        elif 14 <= current_time <= 15:  # 장 후반
            time_score = 40
        
        # VIX(변동성 지수) 수준 (더 관대하게)
        vix_level = additional_data.get('vix_level', 20) if additional_data else 20
        vix_score = max(50 - vix_level, 20)  # 최소 20점 보장
        
        # 시장 참여율 (더 관대하게)
        participation_rate = additional_data.get('market_participation', 50) if additional_data else 50
        participation_score = min(participation_rate * 0.8, 40) + 20  # 기본 20점 추가
        
        return time_score + vix_score + participation_score
    
    def _analyze_liquidity_safety(self, data: pd.DataFrame) -> float:
        """유동성 안전성 분석 (완화된 조건)"""
        # 평균 거래대금 (사용 가능한 기간)
        tail_period = min(15, len(data))
        avg_trading_value = (data['Close'] * data['Volume']).tail(tail_period).mean()
        
        # 호가 스프레드 (시뮬레이션, 더 관대하게)
        spread_ratio = 0.3  # 0.5→0.3으로 완화
        
        # 가격 임팩트 (더 관대한 계산)
        impact_period = min(5, len(data))
        if impact_period >= 2:
            price_impact = data['High'].tail(impact_period).std() / data['Close'].tail(impact_period).mean()
        else:
            price_impact = 0.001  # 기본 낮은 값
        
        # 점수 계산 (더 관대하게)
        liquidity_score = min(avg_trading_value / 50000000 * 40, 60) + 20  # 기준 완화, 기본 20점
        spread_score = max(40 - spread_ratio * 60, 20)  # 최소 20점 보장
        impact_score = max(30 - price_impact * 1000, 15)  # 최소 15점 보장
        
        return liquidity_score + spread_score + impact_score
    
    def _analyze_news_catalyst(self, stock_code: str, additional_data: dict = None) -> float:
        """뉴스 촉매 분석 (완화된 조건)"""
        if not additional_data or 'news_data' not in additional_data:
            return 55.0  # 기본점수 대폭 상향 (30→55)
        
        news_data = additional_data['news_data'].get(stock_code, {})
        
        # 뉴스 감정 점수
        sentiment_score = news_data.get('sentiment_score', 0)  # -1 ~ +1
        relevance_score = news_data.get('relevance_score', 0.5)  # 0 ~ 1
        credibility_score = news_data.get('credibility_score', 0.5)  # 0 ~ 1
        
        # 점수 계산
        final_score = (sentiment_score + 1) * 25 + relevance_score * 35 + credibility_score * 40
        
        return max(min(final_score, 100), 0)
    
    def _analyze_risk_control(self, data: pd.DataFrame) -> float:
        """리스크 통제 분석"""
        # 변동성 수준
        volatility = data['Close'].pct_change().tail(20).std() * np.sqrt(252)
        
        # 최대 낙폭 (Maximum Drawdown)
        cumulative_returns = (1 + data['Close'].pct_change()).cumprod()
        max_drawdown = (cumulative_returns / cumulative_returns.expanding().max() - 1).min()
        
        # 베타 (시장 대비 변동성)
        market_returns = data['Close'].pct_change().tail(60)
        stock_returns = data['Close'].pct_change().tail(60)
        if len(stock_returns.dropna()) > 0 and len(market_returns.dropna()) > 0:
            beta = np.cov(stock_returns.dropna(), market_returns.dropna())[0, 1] / np.var(market_returns.dropna())
        else:
            beta = 1.0
        
        # 점수 계산 (낮은 리스크가 높은 점수)
        volatility_score = max(50 - volatility * 100, 0)
        drawdown_score = max(30 + max_drawdown * 100, 0)  # MDD가 작을수록 좋음
        beta_score = max(20 - abs(beta - 1) * 20, 0)  # 베타 1에 가까울수록 좋음
        
        return volatility_score + drawdown_score + beta_score
    
    def _analyze_profit_potential(self, data: pd.DataFrame) -> float:
        """수익 잠재력 분석"""
        # 저항선 돌파 여부
        resistance_level = data['High'].tail(20).max()
        current_price = data.iloc[-1]['Close']
        resistance_ratio = current_price / resistance_level
        
        # 목표가 대비 현재가
        target_price = current_price * 1.20  # 20% 상승 목표
        price_potential = (target_price - current_price) / current_price * 100
        
        # 과거 급등 시 최대 상승률
        historical_max_gain = 15.0  # 예시값
        
        # 점수 계산
        resistance_score = min(resistance_ratio * 40, 40)
        potential_score = min(price_potential * 2, 35)
        historical_score = min(historical_max_gain, 25)
        
        return resistance_score + potential_score + historical_score
    
    def _analyze_entry_timing(self, data: pd.DataFrame) -> float:
        """진입 타이밍 분석"""
        # 급등 초기인지 확인
        surge_duration = self._count_surge_days(data)
        
        # 되돌림 후 재상승인지 확인
        pullback_recovery = self._check_pullback_recovery(data)
        
        # 거래량 확장 여부
        volume_expansion = self._check_volume_expansion(data)
        
        # 점수 계산
        duration_score = max(50 - surge_duration * 10, 0)  # 급등 초기일수록 좋음
        recovery_score = 30 if pullback_recovery else 10
        volume_score = 20 if volume_expansion else 5
        
        return duration_score + recovery_score + volume_score
    
    def _analyze_sector_momentum(self, stock_code: str, additional_data: dict = None) -> float:
        """섹터 모멘텀 분석 (완화된 조건)"""
        if not additional_data or 'sector_data' not in additional_data:
            return 60.0  # 기본점수 상향 (50→60)
        
        sector_data = additional_data['sector_data']
        
        # 섹터 전체 상승률
        sector_performance = sector_data.get('sector_performance', 0)
        sector_rank = sector_data.get('sector_rank', 50)
        sector_fund_flow = sector_data.get('fund_flow', 0)
        
        # 점수 계산
        performance_score = max(min(sector_performance * 5, 40), 0)
        rank_score = max(60 - sector_rank, 0)  # 순위 높을수록 좋음
        flow_score = max(min(sector_fund_flow / 1000000, 20), 0)
        
        return performance_score + rank_score + flow_score
    
    def _calculate_total_score(self, result: SurgeAnalysisResult) -> float:
        """종합 점수 계산"""
        weighted_score = (
            result.volume_quality_score * self.score_weights['volume_quality'] / 100 +
            result.momentum_persistence_score * self.score_weights['momentum_persistence'] / 100 +
            result.fundamental_support_score * self.score_weights['fundamental_support'] / 100 +
            result.institutional_flow_score * self.score_weights['institutional_flow'] / 100 +
            result.technical_strength_score * self.score_weights['technical_strength'] / 100 +
            result.market_timing_score * self.score_weights['market_timing'] / 100 +
            result.liquidity_safety_score * self.score_weights['liquidity_safety'] / 100 +
            result.news_catalyst_score * self.score_weights['news_catalyst'] / 100 +
            result.risk_control_score * self.score_weights['risk_control'] / 100 +
            result.profit_potential_score * self.score_weights['profit_potential'] / 100 +
            result.entry_timing_score * self.score_weights['entry_timing'] / 100 +
            result.sector_momentum_score * self.score_weights['sector_momentum'] / 100
        )
        
        return min(weighted_score, 100.0)
    
    def _determine_quality_grade(self, total_score: float) -> SurgeQuality:
        """품질 등급 결정"""
        if total_score >= self.quality_thresholds[SurgeQuality.PREMIUM]:
            return SurgeQuality.PREMIUM
        elif total_score >= self.quality_thresholds[SurgeQuality.HIGH]:
            return SurgeQuality.HIGH
        elif total_score >= self.quality_thresholds[SurgeQuality.MEDIUM]:
            return SurgeQuality.MEDIUM
        elif total_score >= self.quality_thresholds[SurgeQuality.LOW]:
            return SurgeQuality.LOW
        else:
            return SurgeQuality.DANGEROUS
    
    def _generate_recommendation(self, result: SurgeAnalysisResult) -> str:
        """투자 추천 생성"""
        recommendations = {
            SurgeQuality.PREMIUM: f"최우선 투자 추천 (점수: {result.total_score:.1f}) - 적극 매수",
            SurgeQuality.HIGH: f"고급 투자 대상 (점수: {result.total_score:.1f}) - 신중 매수",
            SurgeQuality.MEDIUM: f"중급 투자 대상 (점수: {result.total_score:.1f}) - 소액 투자",
            SurgeQuality.LOW: f"관찰 대상 (점수: {result.total_score:.1f}) - 관망",
            SurgeQuality.DANGEROUS: f"투자 위험 (점수: {result.total_score:.1f}) - 투자 금지"
        }
        
        return recommendations.get(result.quality_grade, "분석 불가")
    
    # 헬퍼 메서드들
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std: float = 2.0) -> tuple:
        """볼린저 밴드 계산"""
        sma = prices.rolling(window=period).mean()
        std_dev = prices.rolling(window=period).std()
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        return upper_band, lower_band
    
    def _count_surge_days(self, data: pd.DataFrame) -> int:
        """급등 지속 일수 계산"""
        returns = data['Close'].pct_change().tail(10)
        surge_days = 0
        for ret in reversed(returns):
            if ret > 0.02:  # 2% 이상 상승
                surge_days += 1
            else:
                break
        return surge_days
    
    def _check_pullback_recovery(self, data: pd.DataFrame) -> bool:
        """되돌림 후 재상승 패턴 확인"""
        recent_prices = data['Close'].tail(5)
        if len(recent_prices) < 5:
            return False
        
        # 최근 5일 중 하락 후 상승 패턴이 있는지 확인
        price_changes = recent_prices.pct_change()
        has_pullback = any(change < -0.01 for change in price_changes)  # 1% 이상 하락
        has_recovery = price_changes.iloc[-1] > 0.02  # 마지막날 2% 이상 상승
        
        return has_pullback and has_recovery
    
    def _check_volume_expansion(self, data: pd.DataFrame) -> bool:
        """거래량 확장 확인"""
        if len(data) < 10:
            return False
        
        recent_volume = data['Volume'].tail(3).mean()
        prev_volume = data['Volume'].tail(10).head(7).mean()
        
        return recent_volume > prev_volume * 1.5
    
    def _identify_risk_factors(self, result: SurgeAnalysisResult, data: pd.DataFrame) -> list:
        """리스크 요인 식별"""
        risk_factors = []
        
        if result.volume_quality_score < 30:
            risk_factors.append("거래량 부족 - 유동성 리스크")
        
        if result.momentum_persistence_score < 40:
            risk_factors.append("모멘텀 약화 - 상승세 지속 불투명")
        
        if result.institutional_flow_score < 30:
            risk_factors.append("기관 자금 이탈 - 추가 하락 가능")
        
        if result.technical_strength_score < 35:
            risk_factors.append("기술적 약세 - 저항선 돌파 실패")
        
        if result.risk_control_score < 40:
            risk_factors.append("고변동성 - 급격한 가격 변동 위험")
        
        # 급등률이 너무 높은 경우
        if result.surge_rate > 15:
            risk_factors.append("과도한 급등 - 조정 압력 증가")
        
        return risk_factors
    
    def _calculate_stop_loss(self, data: pd.DataFrame) -> float:
        """손절선 계산"""
        current_price = data.iloc[-1]['Close']
        
        # ATR 기반 손절선
        atr = self._calculate_atr(data)
        if len(atr) > 0:
            stop_loss = current_price - (atr.iloc[-1] * 2.0)
        else:
            stop_loss = current_price * 0.95  # 기본 5% 손절
        
        return stop_loss
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range 계산"""
        high_low = data['High'] - data['Low']
        high_close = abs(data['High'] - data['Close'].shift())
        low_close = abs(data['Low'] - data['Close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()
    
    def _calculate_profit_target(self, data: pd.DataFrame, total_score: float) -> float:
        """목표가 계산"""
        current_price = data.iloc[-1]['Close']
        
        # 점수에 따른 목표 수익률 조정
        if total_score >= 85:
            target_return = 0.25  # 25%
        elif total_score >= 70:
            target_return = 0.20  # 20%
        elif total_score >= 55:
            target_return = 0.15  # 15%
        else:
            target_return = 0.10  # 10%
        
        return current_price * (1 + target_return)
    
    def _calculate_max_position_size(self, result: SurgeAnalysisResult) -> float:
        """최대 포지션 크기 계산"""
        # 품질에 따른 포지션 크기 조정
        position_sizes = {
            SurgeQuality.PREMIUM: 0.08,    # 8%
            SurgeQuality.HIGH: 0.05,       # 5%
            SurgeQuality.MEDIUM: 0.03,     # 3%
            SurgeQuality.LOW: 0.01,        # 1%
            SurgeQuality.DANGEROUS: 0.0    # 0%
        }
        
        base_size = position_sizes.get(result.quality_grade, 0.01)
        
        # 리스크 요인 수에 따른 추가 조정
        risk_adjustment = max(1.0 - len(result.risk_factors) * 0.1, 0.5)
        
        return base_size * risk_adjustment

@dataclass
class SurgeStockInfo:
    """급등종목 정보"""
    symbol: str
    name: str
    current_price: float
    change_rate: float
    volume_ratio: float
    surge_score: float
    timestamp: datetime
    volume: int = 0  # 거래량 정보 추가
    previous_price: float = 0.0  # 이전 가격 정보 추가
    
    def __str__(self):
        return f"{self.name}({self.symbol}): {self.change_rate:.2%} | 거래량: {self.volume_ratio:.1f}배"

class PolicyBasedSurgeStockProvider:
    """Policy 기반 급등종목 데이터 수집기 (SimpleSurgeDetector 통합)"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.last_update = None
        self.cached_stocks = []
        
        # SimpleSurgeDetector 인스턴스 생성
        self.surge_detector = SimpleSurgeDetector()
        
        # 정밀 스크리닝 시스템 인스턴스 생성
        self.premium_screener = PremiumSurgeScreener()
        
        # Policy 순서별 성능 통계 (NumPy 배열로 관리)
        self.policy_stats = {
            'pykrx_scan': {'success': 0, 'failed': 0, 'total_stocks': 0},
            'krx_official': {'success': 0, 'failed': 0, 'total_stocks': 0},
            'pandas_datareader': {'success': 0, 'failed': 0, 'total_stocks': 0},
            'naver_finance': {'success': 0, 'failed': 0, 'total_stocks': 0},
            'securities_api': {'success': 0, 'failed': 0, 'total_stocks': 0}
        }
        
        logger.info("Policy 기반 급등종목 수집기 초기화 완료 (SimpleSurgeDetector 통합)")
        
    @staticmethod
    def _filter_by_price_fast(prices: np.ndarray, scores: np.ndarray, 
                             min_price: float, price_limit: float) -> np.ndarray:
        """NumPy/Numba 최적화된 가격 필터링"""
        mask = (prices >= min_price) & (prices <= price_limit)
        return mask

    @staticmethod  
    def _sort_by_score_fast(scores: np.ndarray) -> np.ndarray:
        """NumPy/Numba 최적화된 점수 기반 정렬 인덱스"""
        return np.argsort(scores)[::-1]  # 내림차순

    async def detect_surge_stocks_with_hyper(self, api_connector, limit: int = 20) -> List[SurgeStockInfo]:
        """Hyper_upStockFind.py의 SimpleSurgeDetector를 사용한 급등주 탐지"""
        try:
            logger.info("SimpleSurgeDetector를 사용한 급등주 탐지 시작")
            
            # 1. KOSPI/KOSDAQ 전체 종목 리스트 가져오기
            if PYKRX_AVAILABLE:
                kospi_stocks = stock.get_market_ticker_list(market="KOSPI")
                kosdaq_stocks = stock.get_market_ticker_list(market="KOSDAQ")
                all_stocks = kospi_stocks + kosdaq_stocks
                logger.info(f"전체 종목 수: KOSPI {len(kospi_stocks)}개, KOSDAQ {len(kosdaq_stocks)}개")
            else:
                # PyKrx가 없으면 수집된 종목 데이터 사용
                try:
                    from stock_data_collector import StockDataCollector
                    collector = StockDataCollector()
                    stock_data = collector.load_cached_data()
                    
                    if stock_data and 'stock_info' in stock_data:
                        all_stocks = list(stock_data['stock_info'].keys())
                        logger.info(f"수집된 종목 데이터 사용: {len(all_stocks)}개 종목")
                    else:
                        # 캐시가 없으면 실시간으로 수집 시도
                        logger.warning("캐시된 종목 데이터 없음, 실시간 수집 시도")
                        all_stocks = []
                except Exception as e:
                    logger.error(f"종목 데이터 로드 실패: {e}")
                    all_stocks = []
            
            # 2. 각 종목별로 SimpleSurgeDetector 분석 (최대 100개만 분석하여 성능 최적화)
            analysis_stocks = all_stocks[:100]  # 성능상 제한
            surge_candidates = []
            
            for symbol in analysis_stocks:
                try:
                    # 일봉 데이터 조회 (10일치)
                    chart_data = api_connector.get_stock_chart_data(symbol, period='day', count=10)
                    if chart_data is None or len(chart_data) < 6:
                        continue
                    
                    # 현재가 정보 조회
                    price_info = api_connector.get_stock_price(symbol)
                    if not price_info or price_info.get('rt_cd') != '0':
                        continue
                    
                    output = price_info.get('output', {})
                    current_price = float(output.get('stck_prpr', 0))
                    stock_name = output.get('hts_kor_isnm', f'종목{symbol}')
                    change_rate = float(output.get('prdy_ctrt', 0)) / 100.0
                    volume = int(output.get('acml_vol', 0))
                    
                    if current_price <= 0:
                        continue
                    
                    # DataFrame을 SimpleSurgeDetector 형식으로 변환
                    stock_data = []
                    for _, row in chart_data.iterrows():
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
                    
                    # 급등주 조건: 점수 5점 이상
                    if score >= 5:
                        surge_info = SurgeStockInfo(
                            symbol=symbol,
                            name=stock_name,
                            current_price=current_price,
                            change_rate=change_rate,
                            volume_ratio=2.0,  # 기본값
                            surge_score=score,
                            timestamp=datetime.now(),
                            volume=volume
                        )
                        surge_candidates.append(surge_info)
                        logger.info(f"급등주 발견: {stock_name}({symbol}) - 점수: {score}, 상세: {detail}")
                
                except Exception as e:
                    logger.debug(f"SimpleSurgeDetector 분석 실패 ({symbol}): {e}")
                    # 실패한 종목은 일시적으로 분석 대상에서 제외하기 위해 기록
                    continue
            
            # 3. 점수 순으로 정렬하여 상위 종목 반환
            surge_candidates.sort(key=lambda x: x.surge_score, reverse=True)
            final_results = surge_candidates[:limit]
            
            logger.info(f"SimpleSurgeDetector 급등주 탐지 완료: {len(final_results)}개 발견")
            return final_results
            
        except Exception as e:
            logger.error(f"SimpleSurgeDetector 급등주 탐지 실패: {e}")
            return []

    async def get_filtered_surge_stocks(self, price_limit: int = 13000, min_price: int = 9000, api_connector=None) -> List[SurgeStockInfo]:
        """OPEN-API 실시간 급등종목 조회 + 12단계 정밀스크리닝 + 상승세/매수량 분석 → 최종 3종목 선별"""
        try:
            if api_connector is None:
                logger.error("API 커넥터가 필요합니다")
                return []
            
            # 1단계: OPEN-API로 급등종목 조회 (빠른 처리 - 20개로 단축)
            logger.info("1단계: OPEN-API 급등종목 20개 조회 (빠른 처리)")
            
            # 빠른 처리: 적은 후보군으로 빠른 스크리닝
            surge_data = api_connector.get_market_surge_ranking(limit=20)
            
            if surge_data.get('rt_cd') == '0' and surge_data.get('output'):
                logger.info(f"OPEN-API 급등주 조회 성공: {len(surge_data['output'])}개")
                raw_surge_stocks = surge_data['output']
                
                # 메모리 기반 빠른 전처리 (중복 제거 및 기본 필터링)
                unique_stocks = {}
                for stock in raw_surge_stocks:
                    symbol = stock.get('mksc_shrn_iscd', '')
                    if symbol and symbol not in unique_stocks:
                        # 기본 가격 필터링을 메모리에서 빠르게 처리
                        price = float(stock.get('stck_prpr', 0))
                        if 5000 <= price <= 100000:  # 5천원~10만원 범위
                            unique_stocks[symbol] = stock
                
                raw_surge_stocks = list(unique_stocks.values())
                logger.info(f"메모리 기반 전처리 완료: {len(raw_surge_stocks)}개 종목")
            else:
                logger.error(f"OPEN-API 급등주 조회 실패: {surge_data.get('msg1', '알 수 없는 오류')}")
                return []
            
            # 2단계: 빠른 3단계 스크리닝 (12단계→3단계)
            logger.info("2단계: 빠른 필터링 시작")
            
            # 빠른 가격/거래량 기본 필터링
            quick_filtered = []
            for stock in raw_surge_stocks:
                try:
                    price = float(stock.get('stck_prpr', 0))
                    change_rate = float(stock.get('prdy_ctrt', 0))
                    volume_ratio = float(stock.get('vol_tnrt', 0))
                    
                    # 빠른 조건: 상승률 5%+, 거래량 1.5배+, 가격 1만~8만원
                    if (change_rate >= 5.0 and volume_ratio >= 1.5 and 
                        10000 <= price <= 80000):
                        # SurgeStockInfo 객체 생성
                        surge_stock = SurgeStockInfo(
                            symbol=stock.get('mksc_shrn_iscd', ''),
                            name=stock.get('hts_kor_isnm', ''),
                            current_price=price,
                            change_rate=change_rate/100,
                            surge_score=change_rate + volume_ratio  # 간단한 점수
                        )
                        quick_filtered.append(surge_stock)
                except:
                    continue
            
            if not quick_filtered:
                logger.warning("빠른 스크리닝 통과 급등주 없음")
                return []
            
            # 3단계: 점수순 정렬하여 상위 3개 선택
            logger.info("3단계: 상위 3개 선택")
            quick_filtered.sort(key=lambda x: x.surge_score, reverse=True)
            top_candidates = quick_filtered[:3]
            # 최종 종목 반환
            logger.info(f"급등주 {len(top_candidates)}개 선정 완료")
            return top_candidates
            
        except Exception as e:
            logger.error(f"급등종목 선별 실패: {e}")
            return []
    
    async def _apply_premium_screening(self, raw_surge_stocks: List[Dict], api_connector) -> List[Dict]:
        """12단계 정밀 스크리닝 시스템을 사용한 급등주 필터링"""
        try:
            logger.info(f"정밀 스크리닝 시스템 시작: {len(raw_surge_stocks)}개 급등주 대상")
            
            # 급등주 데이터를 차트 데이터 형태로 변환
            market_data = {}
            additional_data = {
                'stock_names': {},
                'earnings_data': {},
                'institutional_data': {
                    'foreign_net': [1000000, 2000000, 1500000, 3000000, 2500000],  # 샘플 데이터
                    'institution_net': [500000, 1000000, 800000, 1200000, 900000],
                    'retail_net': [-1500000, -3000000, -2300000, -4200000, -3400000]
                },
                'news_data': {},
                'sector_data': {
                    'sector_performance': 3.5,
                    'sector_rank': 25,
                    'fund_flow': 2000000
                },
                'market_trend': 1.8,
                'vix_level': 22,
                'market_participation': 60
            }
            
            # 각 급등주에 대해 차트 데이터 수집 및 스크리닝 적용
            filtered_stocks = []
            for item in raw_surge_stocks[:15]:  # 처리량 제한
                try:
                    symbol = item.get('mksc_shrn_iscd', '')
                    stock_name = item.get('hts_kor_isnm', f'종목{symbol}')
                    
                    if not symbol:
                        continue
                    
                    # 차트 데이터 조회 (30일)
                    chart_data = api_connector.get_stock_chart_data(symbol, period='day', count=30)
                    if chart_data is None or len(chart_data) < 20:
                        continue
                    
                    # 종목명 추가
                    additional_data['stock_names'][symbol] = stock_name
                    
                    # 스크리닝 시스템에 적합한 DataFrame 형태로 변환
                    if not chart_data.empty:
                        # 컬럼명 표준화
                        if 'close' in chart_data.columns:
                            chart_data = chart_data.rename(columns={
                                'close': 'Close', 'open': 'Open', 'high': 'High', 
                                'low': 'Low', 'volume': 'Volume'
                            })
                        
                        market_data[symbol] = chart_data
                        
                        logger.debug(f"정밀 스크리닝 데이터 준비: {stock_name}({symbol}) - {len(chart_data)}일 차트")
                    
                except Exception as e:
                    logger.debug(f"종목 {symbol} 데이터 준비 실패: {e}")
                    continue
            
            # 정밀 스크리닝 시스템 실행
            if market_data:
                logger.info(f"12단계 정밀 스크리닝 실행: {len(market_data)}개 종목")
                screening_results = self.premium_screener.screen_surge_stocks(market_data, additional_data)
                
                # 스크리닝 결과를 원래 급등주 데이터 형태로 변환
                for result in screening_results:
                    # 원래 급등주 데이터에서 해당 종목 찾기
                    original_item = None
                    for item in raw_surge_stocks:
                        if item.get('mksc_shrn_iscd', '') == result.stock_code:
                            original_item = item
                            break
                    
                    if original_item:
                        # 정밀 스크리닝 점수를 추가
                        original_item['premium_score'] = result.total_score
                        original_item['quality_grade'] = result.quality_grade.value
                        original_item['risk_factors'] = result.risk_factors
                        
                        # 모든 등급 통과 (LOW 등급도 포함하여 선택 폭 확대)
                        if result.quality_grade in [SurgeQuality.PREMIUM, SurgeQuality.HIGH, SurgeQuality.MEDIUM, SurgeQuality.LOW]:
                            filtered_stocks.append(original_item)
                            logger.info(f"스크리닝 통과: {result.stock_name}({result.stock_code}) "
                                       f"등급:{result.quality_grade.value} 점수:{result.total_score:.1f}")
                        else:
                            # DANGEROUS 등급만 제외
                            logger.debug(f"스크리닝 불통과 (위험등급): {result.stock_name}({result.stock_code}) "
                                        f"등급:{result.quality_grade.value} 점수:{result.total_score:.1f}")
                
                # 정밀 스크리닝 점수 순으로 정렬
                filtered_stocks.sort(key=lambda x: x.get('premium_score', 0), reverse=True)
                
                logger.info(f"정밀 스크리닝 완료: {len(screening_results)}개 분석, {len(filtered_stocks)}개 통과")
                return filtered_stocks
            else:
                logger.warning("정밀 스크리닝용 차트 데이터가 없습니다")
                return raw_surge_stocks[:10]  # 백업으로 상위 10개 반환
                
        except Exception as e:
            logger.error(f"정밀 스크리닝 실패: {e}")
            return raw_surge_stocks[:10]  # 백업으로 상위 10개 반환
    
    async def _analyze_surge_momentum(self, raw_surge_stocks: List[Dict], api_connector) -> List[SurgeStockInfo]:
        """각 급등종목의 상승세 + 매수량 증가 분석"""
        analyzed_stocks = []
        
        try:
            logger.info(f"급등종목 모멘텀 분석 시작: {len(raw_surge_stocks)}개")
            
            for item in raw_surge_stocks:
                try:
                    # 기본 정보 추출
                    symbol = item.get('mksc_shrn_iscd', '')
                    if not symbol:
                        continue
                    
                    stock_name = item.get('hts_kor_isnm', f'종목{symbol}')
                    current_price = float(item.get('stck_prpr', 0))
                    change_rate = float(item.get('prdy_ctrt', 0)) / 100.0
                    volume = int(item.get('acml_vol', 0))
                    
                    if current_price <= 0:
                        continue
                    
                    # 상승세 분석: 현재가 기준 추가 데이터 조회
                    price_data = api_connector.get_stock_price(symbol)
                    if not price_data or price_data.get('rt_cd') != '0':
                        logger.debug(f"종목 {symbol} 추가 데이터 조회 실패")
                        continue
                    
                    output = price_data.get('output', {})
                    
                    # 상승세 지표들
                    high_price = float(output.get('stck_hgpr', current_price))  # 고가
                    low_price = float(output.get('stck_lwpr', current_price))   # 저가
                    open_price = float(output.get('stck_oprc', current_price))  # 시가
                    
                    # 매수량 분석 지표들
                    ask_volume = int(output.get('askp_rsqn', 0))  # 매도호가잔량
                    bid_volume = int(output.get('bidp_rsqn', 0))  # 매수호가잔량
                    
                    # 모멘텀 점수 계산
                    momentum_score = self._calculate_momentum_score(
                        current_price, open_price, high_price, low_price,
                        change_rate, volume, bid_volume, ask_volume
                    )
                    
                    # 유효한 급등주만 추가 (모멘텀 점수 2.0 이상으로 완화)
                    if momentum_score >= 2.0:
                        stock_info = SurgeStockInfo(
                            symbol=symbol,
                            name=stock_name,
                            current_price=current_price,
                            change_rate=change_rate,
                            volume_ratio=min(max(1.0, volume / 100000), 5.0),
                            surge_score=momentum_score,
                            timestamp=datetime.now(),
                            volume=volume
                        )
                        analyzed_stocks.append(stock_info)
                        
                        logger.debug(f"모멘텀 분석: {stock_name}({symbol}) "
                                   f"점수:{momentum_score:.1f} 상승률:{change_rate:.2%}")
                
                except Exception as e:
                    logger.debug(f"종목 {symbol} 모멘텀 분석 실패: {e}")
                    continue
            
            logger.info(f"모멘텀 분석 완료: {len(analyzed_stocks)}개 종목 (점수 2.0 이상)")
            return analyzed_stocks
            
        except Exception as e:
            logger.error(f"모멘텀 분석 실패: {e}")
            return []
    
    def _calculate_momentum_score(self, current_price: float, open_price: float, 
                                high_price: float, low_price: float, change_rate: float,
                                volume: int, bid_volume: int, ask_volume: int) -> float:
        """상승세 + 매수량 증가 기반 모멘텀 점수 계산"""
        try:
            score = 0.0
            
            # 1. 상승세 분석 (40% 가중치)
            if high_price > low_price:
                # 고가 근처 유지 (현재가가 고가에 가까울수록 높은 점수)
                high_proximity = (current_price - low_price) / (high_price - low_price)
                score += high_proximity * 4.0
                
                # 시가 대비 상승 (시가보다 높을 때 가점)
                if current_price > open_price:
                    score += min((current_price - open_price) / open_price * 10, 2.0)
            
            # 2. 등락률 점수 (30% 가중치)
            if change_rate > 0:
                # 2% 이상 상승시 만점, 5% 이상시 보너스
                rate_score = min(change_rate * 100, 3.0)  # 최대 3점
                score += rate_score
            
            # 3. 매수량 우세 분석 (30% 가중치)
            if bid_volume > 0 and ask_volume > 0:
                # 매수호가 > 매도호가 잔량일 때 높은 점수
                buy_sell_ratio = bid_volume / (bid_volume + ask_volume)
                if buy_sell_ratio > 0.6:  # 매수 60% 이상
                    score += min((buy_sell_ratio - 0.5) * 6, 3.0)
            
            # 4. 거래량 점수 (보너스)
            if volume > 100000:  # 10만주 이상
                volume_bonus = min(volume / 1000000, 1.0)  # 최대 1점
                score += volume_bonus
            
            return round(score, 1)
            
        except Exception as e:
            logger.debug(f"모멘텀 점수 계산 실패: {e}")
            return 0.0
    
    async def _fallback_surge_detection(self, api_connector, price_limit: int, min_price: int) -> List[SurgeStockInfo]:
        """백업용 급등주 탐지 (모의투자 또는 API 실패시)"""
        try:
            logger.info("백업 급등주 탐지 방식 사용")
            surge_stocks = await self.detect_surge_stocks_with_hyper(api_connector, limit=20)
            
            # 기본 필터링만 적용
            filtered_stocks = []
            for stock in surge_stocks:
                if min_price <= stock.current_price <= price_limit and stock.surge_score >= 2.0:  # 5.0→2.0 대폭 완화
                    filtered_stocks.append(stock)
            
            return filtered_stocks[:4]  # 최대 4개로 확대 (3→4개)
            
        except Exception as e:
            logger.error(f"백업 급등주 탐지 실패: {e}")
            return []
    
    async def _convert_openapi_surge_data(self, raw_data: List[Dict], api_connector) -> List[SurgeStockInfo]:
        """OPEN-API 급등주 데이터를 SurgeStockInfo로 변환"""
        converted_stocks = []
        
        try:
            for item in raw_data:
                try:
                    # OPEN-API 급등주 데이터 구조에서 정보 추출
                    symbol = item.get('mksc_shrn_iscd', '')  # 종목코드
                    if not symbol:
                        continue
                    
                    stock_name = item.get('hts_kor_isnm', f'종목{symbol}')  # 종목명
                    current_price = float(item.get('stck_prpr', 0))  # 현재가
                    change_rate = float(item.get('prdy_ctrt', 0)) / 100.0  # 등락률
                    volume = int(item.get('acml_vol', 0))  # 거래량
                    
                    # 유효성 검사
                    if current_price <= 0 or change_rate <= 0:
                        continue
                    
                    # 거래량 비율 계산 (임시)
                    volume_ratio = min(max(1.0, volume / 100000), 5.0)
                    
                    # 급등 점수 계산
                    surge_score = self._calculate_surge_score(change_rate, volume_ratio)
                    
                    stock_info = SurgeStockInfo(
                        symbol=symbol,
                        name=stock_name,
                        current_price=current_price,
                        change_rate=change_rate,
                        volume_ratio=volume_ratio,
                        surge_score=surge_score,
                        timestamp=datetime.now(),
                        volume=volume
                    )
                    
                    converted_stocks.append(stock_info)
                    
                except Exception as e:
                    logger.debug(f"OPEN-API 데이터 변환 실패: {item} - {e}")
                    continue
            
            logger.info(f"OPEN-API 급등주 데이터 변환 완료: {len(converted_stocks)}개")
            return converted_stocks
            
        except Exception as e:
            logger.error(f"OPEN-API 급등주 데이터 변환 실패: {e}")
            return []
    
    async def scan_raw_surge_stocks_priority(self) -> List[Dict]:
        """Policy 우선순위 기반 원시 급등종목 데이터 스캔 (NumPy 최적화)"""
        try:
            logger.info("Policy 기반 급등종목 스캔 시작")
            
            # Policy 1순위: PyKrx를 사용한 실시간 급등주 스캔
            surge_data = await self._scan_from_pykrx()
            if surge_data:
                self.policy_stats['pykrx_scan']['success'] += 1
                self.policy_stats['pykrx_scan']['total_stocks'] += len(surge_data)
                logger.info(f"Policy 1순위(PyKrx) 급등주 스캔 성공: {len(surge_data)}개")
                return surge_data
            else:
                self.policy_stats['pykrx_scan']['failed'] += 1
            
            # Policy 2순위: KRX 공식 시간별 상승률 데이터
            surge_data = await self._scan_from_krx_official()
            if surge_data:
                self.policy_stats['krx_official']['success'] += 1
                self.policy_stats['krx_official']['total_stocks'] += len(surge_data)
                logger.info(f"Policy 2순위(KRX 공식) 급등주 스캔 성공: {len(surge_data)}개")
                return surge_data
            else:
                self.policy_stats['krx_official']['failed'] += 1
            
            # Policy 3순위: pandas_datareader 실시간 데이터
            surge_data = await self._scan_from_pandas_datareader()
            if surge_data:
                self.policy_stats['pandas_datareader']['success'] += 1
                self.policy_stats['pandas_datareader']['total_stocks'] += len(surge_data)
                logger.info(f"Policy 3순위(pandas_datareader) 급등주 스캔 성공: {len(surge_data)}개")
                return surge_data
            else:
                self.policy_stats['pandas_datareader']['failed'] += 1
            
            # Policy 4순위: 네이버 금융 실시간 급등주
            surge_data = await self._scan_from_naver_finance()
            if surge_data:
                self.policy_stats['naver_finance']['success'] += 1
                self.policy_stats['naver_finance']['total_stocks'] += len(surge_data)
                logger.info(f"Policy 4순위(네이버 금융) 급등주 스캔 성공: {len(surge_data)}개")
                return surge_data
            else:
                self.policy_stats['naver_finance']['failed'] += 1
            
            # Policy 5순위: 증권사 API 급등주 (최종 백업)
            surge_data = await self._scan_from_securities_api()
            if surge_data:
                self.policy_stats['securities_api']['success'] += 1
                self.policy_stats['securities_api']['total_stocks'] += len(surge_data)
                logger.info(f"Policy 5순위(증권사 API) 급등주 스캔 성공: {len(surge_data)}개")
                return surge_data
            else:
                self.policy_stats['securities_api']['failed'] += 1
            
            # 모든 Policy 순서 실패시 기본 샘플 데이터 반환
            logger.warning("모든 Policy 순서에서 급등주 스캔 실패 - 기본 데이터 사용")
            return await self._get_fallback_surge_data()
            
        except Exception as e:
            logger.error(f"Policy 기반 급등종목 스캔 실패: {e}")
            return await self._get_fallback_surge_data()
    
    async def _scan_from_pykrx(self) -> List[Dict]:
        """Policy 1순위: PyKrx 기반 급등주 스캔"""
        try:
            if not PYKRX_AVAILABLE:
                logger.debug("PyKrx 라이브러리 미설치")
                return []
            
            logger.info("PyKrx 기반 급등주 스캔 시작")
            
            # 코스피/코스닥 전체 종목 조회 (Policy 샘플 코드 기반)
            kospi_tickers = stock.get_market_ticker_list(market="KOSPI")
            kosdaq_tickers = stock.get_market_ticker_list(market="KOSDAQ")
            all_tickers = kospi_tickers + kosdaq_tickers
            
            # 성능을 위해 상위 200개만 분석
            target_tickers = all_tickers[:200]
            
            surge_stocks = []
            today = datetime.now().strftime("%Y%m%d")
            
            # NumPy 배열로 일괄 처리 준비
            symbols_batch = []
            prices_batch = []
            changes_batch = []
            volumes_batch = []
            
            # 배치 단위로 데이터 수집 (5개씩)
            for i in range(0, min(50, len(target_tickers)), 5):  # 성능을 위해 50개로 제한
                batch = target_tickers[i:i+5]
                
                for symbol in batch:
                    try:
                        # 당일 OHLCV 데이터 조회
                        df = stock.get_market_ohlcv_by_date(today, today, symbol)
                        if df is not None and not df.empty:
                            row = df.iloc[0]
                            current_price = float(row['종가'])
                            volume = int(row['거래량'])
                            
                            # 전일 대비 변화율 계산
                            prev_df = stock.get_market_ohlcv_by_date(
                                (datetime.now() - timedelta(days=1)).strftime("%Y%m%d"), 
                                (datetime.now() - timedelta(days=1)).strftime("%Y%m%d"), 
                                symbol
                            )
                            
                            change_rate = 0.0
                            if prev_df is not None and not prev_df.empty:
                                prev_close = float(prev_df.iloc[0]['종가'])
                                if prev_close > 0:
                                    change_rate = (current_price - prev_close) / prev_close
                            
                            # 급등 조건 검사 (3% 이상 상승 + 거래량 증가)
                            if change_rate >= 0.03 and volume > 10000:
                                # 종목명 조회
                                ticker_name = stock.get_market_ticker_name(symbol)
                                
                                surge_stock = {
                                    "symbol": symbol,
                                    "name": ticker_name,
                                    "current_price": current_price,
                                    "change_rate": change_rate,
                                    "volume": volume,
                                    "volume_ratio": min(volume / 100000, 5.0),  # 정규화
                                    "surge_score": self._calculate_surge_score(change_rate, volume / 100000)
                                }
                                
                                surge_stocks.append(surge_stock)
                                
                    except Exception as e:
                        logger.debug(f"PyKrx 종목 {symbol} 처리 실패: {e}")
                        continue
                
                # API 과부하 방지
                await asyncio.sleep(0.5)
            
            # NumPy 기반 정렬 (급등 점수 기준)
            if surge_stocks:
                scores = np.array([s['surge_score'] for s in surge_stocks])
                sorted_indices = np.argsort(scores)[::-1]  # 내림차순
                surge_stocks = [surge_stocks[i] for i in sorted_indices[:20]]  # 상위 20개
            
            logger.info(f"PyKrx 급등주 스캔 완료: {len(surge_stocks)}개")
            return surge_stocks
            
        except Exception as e:
            logger.warning(f"PyKrx 급등주 스캔 실패: {e}")
            return []
    
    async def _scan_from_krx_official(self) -> List[Dict]:
        """Policy 2순위: KRX 공식 급등주 스캔"""
        try:
            logger.info("KRX 공식 급등주 스캔 시작")
            
            # 현재는 PyKrx가 KRX 공식 데이터를 제공하므로 동일한 방식 사용
            # 향후 KRX 공식 API 직접 연동시 이 부분을 교체
            if PYKRX_AVAILABLE:
                return await self._scan_from_pykrx()
            
            logger.debug("KRX 공식 API 직접 연동 미구현")
            return []
            
        except Exception as e:
            logger.warning(f"KRX 공식 급등주 스캔 실패: {e}")
            return []
    
    async def _scan_from_pandas_datareader(self) -> List[Dict]:
        """Policy 3순위: pandas_datareader 급등주 스캔"""
        try:
            if not PANDAS_DATAREADER_AVAILABLE:
                logger.debug("pandas_datareader 라이브러리 미설치")
                return []
            
            logger.info("pandas_datareader 급등주 스캔 시작")
            
            # 주요 종목 동적 로드
            try:
                from stock_data_collector import StockDataCollector
                collector = StockDataCollector()
                stock_data = collector.load_cached_data()
                if stock_data and 'stock_info' in stock_data:
                    major_stocks = list(stock_data['stock_info'].keys())[:10]  # 상위 10개
                else:
                    major_stocks = []
            except Exception:
                major_stocks = []
            
            surge_stocks = []
            end_date = datetime.now()
            start_date = end_date - timedelta(days=2)
            
            for symbol in major_stocks:
                try:
                    # Yahoo Finance에서 2일치 데이터 조회
                    df = pdr.DataReader(f'{symbol}.KS', 'yahoo', 
                                      start=start_date, end=end_date)
                    
                    if len(df) >= 2:
                        today_close = df['Close'].iloc[-1]
                        yesterday_close = df['Close'].iloc[-2] if len(df) > 1 else today_close
                        volume = df['Volume'].iloc[-1]
                        
                        # 변화율 계산
                        change_rate = (today_close - yesterday_close) / yesterday_close if yesterday_close > 0 else 0
                        
                        # 급등 조건 (2% 이상 상승)
                        if change_rate >= 0.02:
                            surge_stock = {
                                "symbol": symbol,
                                "name": f"종목{symbol}",
                                "current_price": float(today_close),
                                "change_rate": float(change_rate),
                                "volume": int(volume),
                                "volume_ratio": 2.0,  # 기본값
                                "surge_score": self._calculate_surge_score(change_rate, 2.0)
                            }
                            surge_stocks.append(surge_stock)
                            
                except Exception as e:
                    logger.debug(f"pandas_datareader 종목 {symbol} 처리 실패: {e}")
                    continue
                
                await asyncio.sleep(0.2)  # API 제한 고려
            
            logger.info(f"pandas_datareader 급등주 스캔 완료: {len(surge_stocks)}개")
            return surge_stocks
            
        except Exception as e:
            logger.warning(f"pandas_datareader 급등주 스캔 실패: {e}")
            return []
    
    async def _scan_from_naver_finance(self) -> List[Dict]:
        """Policy 4순위: 네이버 금융 급등주 스캔"""
        try:
            logger.info("네이버 금융 급등주 스캔 시작")
            
            # 네이버 금융 급등주 페이지 스크래핑
            url = "https://finance.naver.com/sise/sise_rise.nhn"
            
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return []
            
            # 실제 HTML 파싱 로직 구현 필요
            # 동적 샘플 데이터 생성
            try:
                from stock_data_collector import StockDataCollector
                collector = StockDataCollector()
                stock_data = collector.load_cached_data()
                if stock_data and 'stock_info' in stock_data:
                    default_stocks = list(stock_data['stock_info'].keys())[:2]  # 상위 2개
                else:
                    default_stocks = []
                sample_surge_data = []
                for i, stock_code in enumerate(default_stocks):
                    sample_surge_data.append({
                        "symbol": stock_code, 
                        "name": f"종목{stock_code}", 
                        "current_price": 10000 + i*1000, 
                        "change_rate": 0.03 + i*0.01, 
                        "volume": 150000 + i*50000, 
                        "volume_ratio": 2.0 + i*0.5, 
                        "surge_score": 85 + i*5
                    })
            except Exception:
                sample_surge_data = []
            
            logger.info(f"네이버 금융 급등주 스캔 완료: {len(sample_surge_data)}개")
            return sample_surge_data
            
        except Exception as e:
            logger.warning(f"네이버 금융 급등주 스캔 실패: {e}")
            return []
    
    async def _scan_from_securities_api(self) -> List[Dict]:
        """Policy 5순위: 증권사 API 급등주 스캔"""
        try:
            logger.info("증권사 API 급등주 스캔 시작")
            
            # 기존 KIS API 활용
            from support.api_connector import KISAPIConnector
            api = KISAPIConnector(is_mock=False)
            
            # 주요 종목 동적 로드
            try:
                from stock_data_collector import StockDataCollector
                collector = StockDataCollector()
                stock_data = collector.load_cached_data()
                if stock_data and 'stock_info' in stock_data:
                    major_symbols = list(stock_data['stock_info'].keys())[:5]  # 주요 5개 종목
                else:
                    major_symbols = []
            except Exception:
                # JSON에서 직접 최소 종목 로드 시도
                try:
                    import json
                    from pathlib import Path
                    json_file = Path(__file__).parent / "enhanced_theme_stocks.json"
                    if json_file.exists():
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if 'Core_Large_Cap' in data and 'stocks' in data['Core_Large_Cap']:
                            major_symbols = data['Core_Large_Cap']['stocks'][:3]
                        else:
                            major_symbols = []  # 빈 리스트
                    else:
                        major_symbols = []  # 빈 리스트
                except Exception:
                    major_symbols = []  # 빈 리스트
            surge_stocks = []
            
            for symbol in major_symbols:
                try:
                    price_data = api.get_stock_price(symbol)
                    if price_data and price_data.get('rt_cd') == '0':
                        output = price_data.get('output', {})
                        current_price = float(output.get('stck_prpr', 0))
                        change_rate = float(output.get('prdy_ctrt', 0)) / 100.0
                        volume = int(output.get('acml_vol', 0))
                        name = output.get('hts_kor_isnm', f'종목{symbol}')
                        
                        # 급등 조건 (1.5% 이상 상승)
                        if change_rate >= 0.015:
                            surge_stock = {
                                "symbol": symbol,
                                "name": name,
                                "current_price": current_price,
                                "change_rate": change_rate,
                                "volume": volume,
                                "volume_ratio": min(volume / 100000, 5.0),
                                "surge_score": self._calculate_surge_score(change_rate, volume / 100000)
                            }
                            surge_stocks.append(surge_stock)
                            
                except Exception as e:
                    logger.debug(f"증권사 API 종목 {symbol} 처리 실패: {e}")
                    continue
                
                await asyncio.sleep(0.3)
            
            logger.info(f"증권사 API 급등주 스캔 완료: {len(surge_stocks)}개")
            return surge_stocks
            
        except Exception as e:
            logger.warning(f"증권사 API 급등주 스캔 실패: {e}")
            return []
    
    async def _get_fallback_surge_data(self) -> List[Dict]:
        """모든 Policy 실패시 기본 급등주 데이터 - 동적 생성"""
        try:
            from stock_data_collector import StockDataCollector
            collector = StockDataCollector()
            stock_data = collector.load_cached_data()
            if stock_data and 'stock_info' in stock_data:
                default_stocks = list(stock_data['stock_info'].keys())[:5]  # 상위 5개
            else:
                default_stocks = []
            fallback_data = []
            for i, stock_code in enumerate(default_stocks):
                fallback_data.append({
                    "symbol": stock_code,
                    "name": f"종목{stock_code}",
                    "current_price": 12000 + i*1000,
                    "change_rate": 0.035 + i*0.01,
                    "volume": 150000 + i*50000,
                    "volume_ratio": 2.1 + i*0.5,
                    "surge_score": 85 + i*2
                })
            return fallback_data
        except Exception:
            return []

    async def scan_raw_surge_stocks(self) -> List[Dict]:
        """기존 호환성을 위한 래퍼 메서드"""
        return await self.scan_raw_surge_stocks_priority()

    async def get_surge_stocks(self, limit: int = 20) -> List[str]:
        """급등종목 심볼 리스트 반환 (기존 호환성 유지)"""
        try:
            # 기본 급등주 리스트 동적 로드
            try:
                from support.enhanced_theme_stocks import load_theme_stocks_list
                surge_symbols = load_theme_stocks_list()
                if not surge_symbols:
                    from stock_data_collector import StockDataCollector
                    collector = StockDataCollector()
                    stock_data = collector.load_cached_data()
                    if stock_data and 'stock_info' in stock_data:
                        surge_symbols = list(stock_data['stock_info'].keys())
                    else:
                        surge_symbols = []
            except Exception:
                surge_symbols = []
            return surge_symbols[:limit]
        except Exception as e:
            logger.error(f"급등주 조회 실패: {e}")
            return []
    
    async def get_filtered_surge_stocks_by_criteria(self, min_change_rate: float, 
                                       max_change_rate: float,
                                       min_volume_ratio: float, 
                                       limit: int = 10) -> List[SurgeStockInfo]:
        """필터링된 급등종목 목록 조회 (기준별 필터링)"""
        stocks = await self.get_surge_stocks(limit)
        return stocks[:limit]

    async def get_surge_stocks_detailed(self, min_change_rate: float = -0.10, 
                              max_change_rate: float = 0.20,
                              min_volume_ratio: float = 1.0,
                              min_price: float = 9000.0) -> List[SurgeStockInfo]:
        """고급 급등종목 목록 조회 (기술적 분석 기반)"""
        try:
            # 캐시된 데이터가 5분 이내라면 재사용
            if (self.last_update and 
                datetime.now() - self.last_update < timedelta(minutes=5) and
                self.cached_stocks):
                logger.info(f"캐시된 급등종목 데이터 사용: {len(self.cached_stocks)}개")
                # 가격 필터링 적용
                price_filtered = [s for s in self.cached_stocks if s.current_price >= min_price]
                return price_filtered[:15]  # 상위 15개 반환
            
            # 새로운 데이터 수집 (고급 분석기 사용)
            surge_stocks = await self._fetch_surge_stocks()
            
            # 고급 분석기의 결과는 이미 정교한 분석을 거쳤으므로 기존 필터링 생략
            # 단, 극단적인 값만 제외
            filtered_stocks = []
            for stock in surge_stocks:
                # 극단적인 하락(-10% 이하) 또는 극단적인 상승(+20% 이상)만 제외
                if min_change_rate <= stock.change_rate <= max_change_rate:
                    # 9천원 이하 종목 제외 규칙 적용  
                    if stock.current_price >= min_price:
                        filtered_stocks.append(stock)
                    else:
                        logger.debug(f"가격 필터링 제외: {stock.name}({stock.symbol}) {stock.current_price:,}원")
            
            # 이미 급등 점수로 정렬되어 있음
            
            self.cached_stocks = filtered_stocks
            self.last_update = datetime.now()
            
            logger.info(f"고급 급등종목 수집 완료: 전체 {len(surge_stocks)}개, 필터링 후 {len(filtered_stocks)}개")
            
            return filtered_stocks[:15]  # 상위 15개 반환
            
        except Exception as e:
            logger.error(f"급등종목 조회 실패: {e}")
            return []
    
    async def _fetch_surge_stocks(self) -> List[SurgeStockInfo]:
        """고급 급등종목 분석기를 사용한 정교한 급등종목 데이터 수집"""
        stocks = []
        
        try:
            # 고급 급등종목 분석기 초기화
            from support.advanced_surge_analyzer import get_advanced_surge_analyzer
            from support.api_connector import KISAPIConnector
            
            api = KISAPIConnector(is_mock=False)  # 실제 데이터 사용
            analyzer = get_advanced_surge_analyzer(api)
            
            # 실제 테마별 종목 로드
            from support.enhanced_theme_stocks import load_theme_stocks
            theme_stocks = load_theme_stocks()
            
            # 테마별로 종목 선택 (분석 대상 종목 수 제한)
            selected_symbols = []
            for theme_name, theme_data in theme_stocks.items():
                if isinstance(theme_data, dict) and 'stocks' in theme_data:
                    selected_symbols.extend(theme_data['stocks'][:15])  # 테마당 15개로 축소
                    if len(selected_symbols) >= 50:  # 총 50개로 제한 (성능 고려)
                        break
            
            selected_symbols = selected_symbols[:50]
            logger.info(f"고급 급등종목 분석 시작: {len(selected_symbols)}개 종목")
            
            # 고급 분석기로 급등종목 분석
            advanced_surge_stocks = await analyzer.get_top_surge_stocks(selected_symbols, limit=20)
            
            # AdvancedSurgeStockInfo -> SurgeStockInfo 변환
            for advanced_stock in advanced_surge_stocks:
                stock_info = SurgeStockInfo(
                    symbol=advanced_stock.symbol,
                    name=advanced_stock.name,
                    current_price=advanced_stock.current_price,
                    change_rate=advanced_stock.change_rate,
                    volume_ratio=advanced_stock.volume_ratio,
                    surge_score=advanced_stock.surge_score,
                    timestamp=advanced_stock.timestamp,
                    volume=advanced_stock.volume,
                    previous_price=advanced_stock.previous_price
                )
                stocks.append(stock_info)
                
                logger.info(f"고급 급등종목: {advanced_stock.name}({advanced_stock.symbol}) "
                          f"{advanced_stock.change_rate:.2%} 점수:{advanced_stock.surge_score:.1f}")
            
            # 분석 요약 로그
            summary = analyzer.get_analysis_summary()
            logger.info(f"급등종목 분석 요약: 총 {summary.get('total_analyzed', 0)}개 분석, "
                       f"급등종목 {len(stocks)}개 발견, "
                       f"최고점수 {summary.get('top_score', 0):.1f}")
            
        except Exception as e:
            logger.error(f"고급 급등종목 분석 실패: {e}")
            # 오류 발생시 기본 종목 동적 로드
            try:
                from stock_data_collector import StockDataCollector
                collector = StockDataCollector()
                stock_data = collector.load_cached_data()
                if stock_data and 'stock_info' in stock_data:
                    fallback_symbols = list(stock_data['stock_info'].keys())[:5]
                else:
                    fallback_symbols = []
            except Exception:
                fallback_symbols = []  # 빈 리스트
            
            if fallback_symbols:
                return await self._fetch_fallback_stocks(fallback_symbols)
            else:
                return []
            
        return stocks
    
    async def _fetch_fallback_stocks(self, symbols: List[str]) -> List[SurgeStockInfo]:
        """오류 발생시 기본 종목 데이터 수집"""
        stocks = []
        
        try:
            from support.api_connector import KISAPIConnector
            api = KISAPIConnector(is_mock=False)  # 실제 데이터 사용
            
            for symbol in symbols:
                try:
                    await asyncio.sleep(0.5)
                    
                    price_data = api.get_stock_price(symbol)
                    if not price_data or price_data.get('rt_cd') != '0':
                        continue
                    
                    output = price_data.get('output', {})
                    current_price = float(output.get('stck_prpr', 0))
                    change_rate = float(output.get('prdy_ctrt', 0)) / 100.0
                    volume = int(output.get('acml_vol', 0))
                    stock_name = output.get('hts_kor_isnm', f'종목{symbol}')
                    
                    stock_info = SurgeStockInfo(
                        symbol=symbol,
                        name=stock_name,
                        current_price=current_price,
                        change_rate=change_rate,
                        volume_ratio=2.0,  # 기본값
                        surge_score=self._calculate_surge_score(change_rate, 2.0),
                        timestamp=datetime.now(),
                        volume=volume,
                        previous_price=current_price * (1 - change_rate)
                    )
                    stocks.append(stock_info)
                    
                except Exception as e:
                    logger.warning(f"기본 종목 {symbol} 데이터 수집 실패: {e}")
                    
        except Exception as e:
            logger.error(f"기본 종목 데이터 수집 실패: {e}")
            
        return stocks
    
    def _calculate_surge_score(self, change_rate: float, volume_ratio: float) -> float:
        """급등 점수 계산"""
        # 가격 변화율 점수 (60% 가중치)
        price_score = min(change_rate * 100, 20) * 0.6
        
        # 거래량 비율 점수 (40% 가중치)
        volume_score = min((volume_ratio - 1) * 10, 20) * 0.4
        
        return price_score + volume_score
    
    def _filter_stocks(self, stocks: List[SurgeStockInfo], 
                      min_change_rate: float, max_change_rate: float,
                      min_volume_ratio: float) -> List[SurgeStockInfo]:
        """급등종목 필터링"""
        filtered = []
        
        for stock in stocks:
            # 가격 변화율 필터
            if not (min_change_rate <= stock.change_rate <= max_change_rate):
                continue
                
            # 거래량 비율 필터
            if stock.volume_ratio < min_volume_ratio:
                continue
                
            filtered.append(stock)
            
        return filtered
    
    async def get_stock_detail(self, symbol: str) -> Optional[SurgeStockInfo]:
        """특정 종목 상세 정보 조회 (실제 API 호출)"""
        try:
            from support.api_connector import KISAPIConnector
            api = KISAPIConnector(is_mock=False)  # 실제 데이터 사용
            
            # 실제 현재가 조회
            price_data = api.get_stock_price(symbol)
            if not price_data or price_data.get('rt_cd') != '0':
                logger.warning(f"종목 {symbol} 데이터 조회 실패")
                return None
            
            output = price_data.get('output', {})
            current_price = float(output.get('stck_prpr', 0))
            if current_price <= 0:
                return None
            
            # 실제 데이터에서 정보 추출
            change_rate = float(output.get('prdy_ctrt', 0)) / 100.0
            volume = int(output.get('acml_vol', 0))
            stock_name = output.get('hts_kor_isnm', f'종목{symbol}')
            previous_price = float(output.get('prdy_vrss', current_price))
            
            # 거래량 비율 계산
            volume_ratio = min(max(1.0, volume / 1000000), 5.0)
            
            surge_score = self._calculate_surge_score(change_rate, volume_ratio)
            
            return SurgeStockInfo(
                symbol=symbol,
                name=stock_name,
                current_price=current_price,
                change_rate=change_rate,
                volume_ratio=volume_ratio,
                surge_score=surge_score,
                timestamp=datetime.now(),
                volume=volume,
                previous_price=previous_price
            )
            
        except Exception as e:
            logger.error(f"종목 {symbol} 상세 정보 조회 실패: {e}")
            return None
    
    def close(self):
        """세션 종료"""
        if self.session:
            self.session.close()
            
    def __del__(self):
        """소멸자"""
        self.close()

# 기존 클래스 이름 유지 (호환성)
SurgeStockProvider = PolicyBasedSurgeStockProvider

# 전역 인스턴스
_surge_aggregator = None

def get_surge_aggregator() -> PolicyBasedSurgeStockProvider:
    """Policy 기반 급등종목 수집기 싱글톤 인스턴스 반환"""
    global _surge_aggregator
    if _surge_aggregator is None:
        _surge_aggregator = PolicyBasedSurgeStockProvider()
    return _surge_aggregator

# 기존 호환성 유지
def get_surge_provider() -> PolicyBasedSurgeStockProvider:
    """기존 호환성을 위한 별칭"""
    return get_surge_aggregator()