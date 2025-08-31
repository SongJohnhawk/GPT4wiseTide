#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha Vantage 무료 API 커넥터
- 무료 주식 데이터 및 뉴스 제공
- 한국 주식 지원 (KRX)
- 일일 500 requests 무료 제한
"""

import requests
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time
import logging
from dataclasses import dataclass
import yfinance as yf  # Yahoo Finance 백업용

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class StockData:
    """주식 데이터 클래스"""
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    timestamp: datetime = None

@dataclass
class MarketNews:
    """시장 뉴스 데이터 클래스"""
    title: str
    url: str
    summary: str
    source: str
    published_date: datetime
    sentiment: Optional[str] = None
    relevance_score: Optional[float] = None

class AlphaVantageConnector:
    """Alpha Vantage API 커넥터"""
    
    def __init__(self, api_key: str = "demo"):
        """
        Alpha Vantage API 초기화
        무료 계정: https://www.alphavantage.co/support/#api-key
        """
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.session = requests.Session()
        
        # Rate limiting (무료: 5 requests/minute, 500/day)
        self.last_request_time = 0
        self.min_request_interval = 12  # seconds (5 req/min)
        self.daily_request_count = 0
        self.daily_limit = 500
        self.request_date = datetime.now().date()
        
        # 한국 주식 심볼 매핑 (Alpha Vantage에서 지원되는 것들)
        self.korean_symbols = {
            '005930': '005930.KS',  # 삼성전자
            '000660': '000660.KS',  # SK하이닉스  
            '035420': '035420.KS',  # NAVER
            '051910': '051910.KS',  # LG화학
            '005380': '005380.KS',  # 현대차
            '207940': '207940.KS',  # 삼성바이오로직스
            '068270': '068270.KS',  # 셀트리온
            '035720': '035720.KS',  # 카카오
        }
        
        logger.info("Alpha Vantage 커넥터 초기화 완료")
        
    def _rate_limit_check(self):
        """Rate limit 체크 및 대기"""
        now = time.time()
        current_date = datetime.now().date()
        
        # 날짜가 바뀌면 카운터 리셋
        if current_date != self.request_date:
            self.daily_request_count = 0
            self.request_date = current_date
        
        # 일일 한도 체크
        if self.daily_request_count >= self.daily_limit:
            logger.warning("일일 API 요청 한도 초과")
            return False
        
        # 요청 간격 체크
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            logger.info(f"Rate limit 대기: {wait_time:.1f}초")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
        self.daily_request_count += 1
        return True
    
    def _make_request(self, params: Dict) -> Optional[Dict]:
        """API 요청 실행"""
        if not self._rate_limit_check():
            return None
        
        params['apikey'] = self.api_key
        
        try:
            response = self.session.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            # 에러 체크
            if 'Error Message' in data:
                logger.error(f"Alpha Vantage 에러: {data['Error Message']}")
                return None
            elif 'Note' in data:
                logger.warning(f"Alpha Vantage 제한: {data['Note']}")
                return None
                
            return data
            
        except Exception as e:
            logger.error(f"API 요청 실패: {e}")
            return None
    
    def get_stock_quote(self, symbol: str) -> Optional[StockData]:
        """실시간 주식 시세 조회"""
        # 한국 심볼 변환
        av_symbol = self.korean_symbols.get(symbol, symbol)
        
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': av_symbol
        }
        
        data = self._make_request(params)
        if not data or 'Global Quote' not in data:
            logger.warning(f"주식 시세 조회 실패: {symbol}")
            # Yahoo Finance 백업 사용
            return self._get_yfinance_quote(symbol)
        
        quote = data['Global Quote']
        
        try:
            return StockData(
                symbol=symbol,
                price=float(quote['05. price']),
                change=float(quote['09. change']),
                change_percent=float(quote['10. change percent'].replace('%', '')),
                volume=int(quote['06. volume']),
                timestamp=datetime.now()
            )
        except (KeyError, ValueError) as e:
            logger.error(f"주식 데이터 파싱 실패: {e}")
            return None
    
    def _get_yfinance_quote(self, symbol: str) -> Optional[StockData]:
        """Yahoo Finance 백업 데이터"""
        try:
            # 한국 심볼 변환
            yf_symbol = self.korean_symbols.get(symbol, f"{symbol}.KS")
            
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info
            hist = ticker.history(period="2d")
            
            if hist.empty:
                return None
            
            current_price = hist['Close'].iloc[-1]
            previous_price = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
            change = current_price - previous_price
            change_percent = (change / previous_price) * 100
            
            return StockData(
                symbol=symbol,
                price=float(current_price),
                change=float(change),
                change_percent=float(change_percent),
                volume=int(hist['Volume'].iloc[-1]),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Yahoo Finance 백업 실패: {e}")
            return None
    
    def get_market_news(self, topics: List[str] = None) -> List[MarketNews]:
        """시장 뉴스 조회"""
        if topics is None:
            topics = ['technology', 'finance', 'markets']
        
        all_news = []
        
        for topic in topics[:3]:  # 최대 3개 토픽 (API 한도 고려)
            params = {
                'function': 'NEWS_SENTIMENT',
                'topics': topic,
                'limit': '20'
            }
            
            data = self._make_request(params)
            if not data or 'feed' not in data:
                continue
            
            for item in data['feed'][:10]:  # 토픽당 최대 10개
                try:
                    news = MarketNews(
                        title=item.get('title', ''),
                        url=item.get('url', ''),
                        summary=item.get('summary', '')[:200],  # 200자 제한
                        source=item.get('source', 'Alpha Vantage'),
                        published_date=datetime.strptime(
                            item.get('time_published', '20240101T000000'), 
                            '%Y%m%dT%H%M%S'
                        ),
                        sentiment=self._parse_sentiment(item.get('overall_sentiment_label')),
                        relevance_score=float(item.get('relevance_score', 0.0))
                    )
                    all_news.append(news)
                except Exception as e:
                    logger.warning(f"뉴스 파싱 실패: {e}")
                    continue
        
        # 관련도 순으로 정렬
        all_news.sort(key=lambda x: x.relevance_score or 0, reverse=True)
        return all_news[:30]  # 최대 30개 반환
    
    def _parse_sentiment(self, sentiment_label: str) -> str:
        """감성 라벨 파싱"""
        if not sentiment_label:
            return 'neutral'
        
        label_map = {
            'Bearish': 'negative',
            'Somewhat-Bearish': 'negative', 
            'Neutral': 'neutral',
            'Somewhat-Bullish': 'positive',
            'Bullish': 'positive'
        }
        
        return label_map.get(sentiment_label, 'neutral')
    
    def get_korean_market_summary(self) -> Dict[str, Any]:
        """한국 시장 요약 정보"""
        major_symbols = ['005930', '000660', '035420', '051910', '005380']  # 주요 5개 종목
        market_data = {}
        
        for symbol in major_symbols:
            stock_data = self.get_stock_quote(symbol)
            if stock_data:
                market_data[symbol] = {
                    'price': stock_data.price,
                    'change': stock_data.change,
                    'change_percent': stock_data.change_percent,
                    'volume': stock_data.volume
                }
        
        # 전체 시장 동향 계산
        if market_data:
            changes = [data['change_percent'] for data in market_data.values()]
            avg_change = sum(changes) / len(changes)
            
            market_sentiment = 'positive' if avg_change > 0.5 else 'negative' if avg_change < -0.5 else 'neutral'
        else:
            avg_change = 0.0
            market_sentiment = 'neutral'
        
        return {
            'timestamp': datetime.now().isoformat(),
            'market_sentiment': market_sentiment,
            'average_change_percent': avg_change,
            'stocks': market_data,
            'api_requests_used': self.daily_request_count,
            'api_requests_remaining': self.daily_limit - self.daily_request_count
        }

class FreeDataAggregator:
    """무료 데이터 통합 관리자"""
    
    def __init__(self, alpha_vantage_key: str = "demo"):
        self.av_connector = AlphaVantageConnector(alpha_vantage_key)
        self.cache = {}
        self.cache_duration = 300  # 5분 캐시
        
    def get_comprehensive_market_data(self) -> Dict[str, Any]:
        """종합 시장 데이터 수집"""
        cache_key = "market_data"
        now = datetime.now()
        
        # 캐시 확인
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if (now - cached_time).seconds < self.cache_duration:
                logger.info("캐시된 데이터 사용")
                return cached_data
        
        logger.info("새로운 시장 데이터 수집")
        
        # 시장 요약
        market_summary = self.av_connector.get_korean_market_summary()
        
        # 시장 뉴스 (API 한도 고려하여 제한적으로)
        market_news = []
        if self.av_connector.daily_request_count < 480:  # 20개 여유분
            market_news = self.av_connector.get_market_news(['technology'])
        
        comprehensive_data = {
            'market_summary': market_summary,
            'market_news': [
                {
                    'title': news.title,
                    'summary': news.summary,
                    'sentiment': news.sentiment,
                    'relevance_score': news.relevance_score,
                    'published_date': news.published_date.isoformat()
                } for news in market_news
            ],
            'data_sources': [
                'Alpha Vantage (무료)',
                'Yahoo Finance (백업)',
            ],
            'update_time': now.isoformat(),
            'api_status': {
                'requests_used': self.av_connector.daily_request_count,
                'requests_remaining': self.av_connector.daily_limit - self.av_connector.daily_request_count
            }
        }
        
        # 캐시 저장
        self.cache[cache_key] = (now, comprehensive_data)
        
        return comprehensive_data
    
    def get_stock_analysis_data(self, symbol: str) -> Dict[str, Any]:
        """특정 종목 분석 데이터"""
        cache_key = f"stock_{symbol}"
        now = datetime.now()
        
        # 캐시 확인
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if (now - cached_time).seconds < self.cache_duration:
                return cached_data
        
        # 주식 데이터 수집
        stock_data = self.av_connector.get_stock_quote(symbol)
        
        analysis_data = {
            'symbol': symbol,
            'current_data': {
                'price': stock_data.price if stock_data else None,
                'change': stock_data.change if stock_data else None,
                'change_percent': stock_data.change_percent if stock_data else None,
                'volume': stock_data.volume if stock_data else None,
            },
            'data_quality': 'good' if stock_data else 'limited',
            'update_time': now.isoformat()
        }
        
        # 캐시 저장
        self.cache[cache_key] = (now, analysis_data)
        
        return analysis_data

# 테스트 함수
def test_alpha_vantage():
    """Alpha Vantage 커넥터 테스트"""
    connector = AlphaVantageConnector()  # demo key 사용
    
    print("\n=== Alpha Vantage 테스트 ===")
    
    # 주식 시세 테스트
    print("\n1. 주식 시세 조회:")
    test_symbols = ['005930', '000660', '035420']
    
    for symbol in test_symbols:
        stock_data = connector.get_stock_quote(symbol)
        if stock_data:
            print(f"{symbol}: {stock_data.price:,.0f} ({stock_data.change_percent:+.2f}%)")
        else:
            print(f"{symbol}: 데이터 없음")
    
    # 시장 요약 테스트
    print("\n2. 시장 요약:")
    market_summary = connector.get_korean_market_summary()
    print(f"시장 감성: {market_summary['market_sentiment']}")
    print(f"평균 변화율: {market_summary['average_change_percent']:+.2f}%")
    print(f"API 사용량: {market_summary['api_requests_used']}/{connector.daily_limit}")
    
    # 종합 데이터 테스트
    print("\n3. 종합 데이터:")
    aggregator = FreeDataAggregator()
    comprehensive = aggregator.get_comprehensive_market_data()
    print(f"데이터 소스: {', '.join(comprehensive['data_sources'])}")
    print(f"뉴스 개수: {len(comprehensive['market_news'])}")

if __name__ == "__main__":
    test_alpha_vantage()