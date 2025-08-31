#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
완전 무료 주식 데이터 수집 시스템
- 네이버/다음 주식 크롤링
- Yahoo Finance (yfinance 라이브러리)
- Google Finance 크롤링
- 2024 최신 안티스크래핑 우회 기술 적용
"""

import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import json
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import random
from urllib.parse import quote
import re
from pathlib import Path

# Playwright for dynamic content (optional)
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not installed. Using basic scraping only.")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class StockData:
    """주식 데이터 클래스"""
    symbol: str
    name: str
    current_price: float
    change: float
    change_percent: float
    volume: int
    market_cap: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    timestamp: Optional[datetime] = None
    source: str = ""
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class FreeStockDataCollector:
    """무료 주식 데이터 수집기"""
    
    def __init__(self, use_playwright: bool = False):
        """
        초기화
        
        Args:
            use_playwright: Playwright 사용 여부 (동적 콘텐츠용)
        """
        self.use_playwright = use_playwright and PLAYWRIGHT_AVAILABLE
        
        # User agents pool for rotation (2024 최신)
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        # Request headers
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        
        # Session with retry strategy
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        logger.info("무료 주식 데이터 수집기 초기화 완료")
    
    def _get_random_headers(self) -> dict:
        """랜덤 헤더 생성 (안티스크래핑 우회)"""
        headers = self.headers.copy()
        headers['User-Agent'] = random.choice(self.user_agents)
        return headers
    
    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """안전한 float 변환"""
        if value is None:
            return default
        try:
            # Remove commas and convert
            if isinstance(value, str):
                value = value.replace(',', '').replace('%', '')
            return float(value)
        except (ValueError, TypeError):
            return default
    
    async def get_naver_stock_data(self, symbol: str) -> Optional[StockData]:
        """
        네이버 주식에서 데이터 수집
        
        Args:
            symbol: 종목 코드 (예: '005930' for 삼성전자)
        """
        try:
            url = f"https://finance.naver.com/item/main.naver?code={symbol}"
            
            # Add delay to avoid rate limiting
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            response = self.session.get(url, headers=self._get_random_headers(), timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 종목명
            name_elem = soup.select_one('div.wrap_company h2 a')
            name = name_elem.text.strip() if name_elem else symbol
            
            # 현재가
            price_elem = soup.select_one('p.no_today span.blind')
            current_price = self._safe_float(price_elem.text if price_elem else 0)
            
            # 전일 대비
            change_elem = soup.select_one('p.no_exday span.blind')
            if change_elem:
                change_text = change_elem.text.strip()
                # Parse change value and percentage
                change_parts = change_text.split()
                if len(change_parts) >= 2:
                    change = self._safe_float(change_parts[0])
                    if '하락' in change_text or '▼' in change_text:
                        change = -abs(change)
                else:
                    change = 0.0
            else:
                change = 0.0
            
            # 거래량
            volume_elem = soup.select_one('td.first span.blind')
            volume = int(self._safe_float(volume_elem.text if volume_elem else 0))
            
            # 시가, 고가, 저가
            table = soup.select_one('table.no_info')
            if table:
                rows = table.select('tr')
                for row in rows:
                    th = row.select_one('th')
                    td = row.select_one('td span.blind')
                    if th and td:
                        label = th.text.strip()
                        value = self._safe_float(td.text)
                        if '시가' in label:
                            open_price = value
                        elif '고가' in label:
                            high = value
                        elif '저가' in label:
                            low = value
            else:
                open_price = high = low = current_price
            
            # Calculate change percentage
            if current_price > 0 and change != 0:
                prev_price = current_price - change
                change_percent = (change / prev_price) * 100 if prev_price > 0 else 0
            else:
                change_percent = 0.0
            
            return StockData(
                symbol=symbol,
                name=name,
                current_price=current_price,
                change=change,
                change_percent=change_percent,
                volume=volume,
                high=high,
                low=low,
                open_price=open_price,
                source="Naver"
            )
            
        except Exception as e:
            logger.error(f"네이버 주식 데이터 수집 실패 ({symbol}): {e}")
            return None
    
    async def get_daum_stock_data(self, symbol: str) -> Optional[StockData]:
        """
        다음 주식에서 데이터 수집
        
        Args:
            symbol: 종목 코드
        """
        try:
            # 다음 finance URL
            url = f"https://finance.daum.net/quotes/A{symbol}"
            
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            response = self.session.get(url, headers=self._get_random_headers(), timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 종목명
            name_elem = soup.select_one('h2.name')
            name = name_elem.text.strip() if name_elem else symbol
            
            # 현재가
            price_elem = soup.select_one('div.today span.num')
            current_price = self._safe_float(price_elem.text if price_elem else 0)
            
            # 전일 대비
            change_elem = soup.select_one('div.today span.txtB')
            if change_elem:
                change = self._safe_float(change_elem.text)
                # Check if it's a decrease
                ico_elem = soup.select_one('div.today span.ico')
                if ico_elem and ('하락' in ico_elem.get('class', []) or '▼' in str(ico_elem)):
                    change = -abs(change)
            else:
                change = 0.0
            
            # 변동률
            rate_elem = soup.select_one('div.today span.rate')
            change_percent = self._safe_float(rate_elem.text if rate_elem else 0)
            
            # 거래량
            volume_elem = soup.select_one('span.tradeVolume')
            volume = int(self._safe_float(volume_elem.text if volume_elem else 0))
            
            return StockData(
                symbol=symbol,
                name=name,
                current_price=current_price,
                change=change,
                change_percent=change_percent,
                volume=volume,
                source="Daum"
            )
            
        except Exception as e:
            logger.error(f"다음 주식 데이터 수집 실패 ({symbol}): {e}")
            return None
    
    def get_yahoo_finance_data(self, symbol: str) -> Optional[StockData]:
        """
        Yahoo Finance에서 데이터 수집 (yfinance 라이브러리 사용)
        
        Args:
            symbol: 종목 코드 (예: 'AAPL', '005930.KS' for 삼성전자)
        """
        try:
            # Yahoo Finance ticker object
            ticker = yf.Ticker(symbol)
            
            # Get current data
            info = ticker.info
            
            # Get latest price data
            hist = ticker.history(period="1d")
            
            if not hist.empty:
                latest = hist.iloc[-1]
                current_price = float(latest['Close'])
                open_price = float(latest['Open'])
                high = float(latest['High'])
                low = float(latest['Low'])
                volume = int(latest['Volume'])
                
                # Calculate change
                if len(hist) >= 2:
                    prev_close = float(hist.iloc[-2]['Close'])
                    change = current_price - prev_close
                    change_percent = (change / prev_close * 100) if prev_close > 0 else 0
                else:
                    change = 0
                    change_percent = 0
            else:
                # Fallback to info data
                current_price = info.get('regularMarketPrice', 0)
                open_price = info.get('regularMarketOpen', 0)
                high = info.get('dayHigh', 0)
                low = info.get('dayLow', 0)
                volume = info.get('volume', 0)
                change = info.get('regularMarketChange', 0)
                change_percent = info.get('regularMarketChangePercent', 0)
            
            return StockData(
                symbol=symbol,
                name=info.get('longName', symbol),
                current_price=current_price,
                change=change,
                change_percent=change_percent,
                volume=volume,
                market_cap=info.get('marketCap'),
                high=high,
                low=low,
                open_price=open_price,
                source="Yahoo Finance"
            )
            
        except Exception as e:
            logger.error(f"Yahoo Finance 데이터 수집 실패 ({symbol}): {e}")
            return None
    
    async def get_google_finance_data(self, symbol: str) -> Optional[StockData]:
        """
        Google Finance에서 데이터 수집 (웹 크롤링)
        
        Args:
            symbol: 종목 코드 또는 티커
        """
        try:
            # Google Finance URL
            url = f"https://www.google.com/finance/quote/{symbol}"
            
            await asyncio.sleep(random.uniform(1, 2))
            
            response = self.session.get(url, headers=self._get_random_headers(), timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Parse price
            price_elem = soup.select_one('div[data-last-price]')
            if price_elem:
                current_price = self._safe_float(price_elem.get('data-last-price'))
            else:
                # Alternative selector
                price_elem = soup.select_one('div.YMlKec.fxKbKc')
                current_price = self._safe_float(price_elem.text if price_elem else 0)
            
            # Parse change
            change_elem = soup.select_one('div[data-price-change]')
            if change_elem:
                change = self._safe_float(change_elem.get('data-price-change'))
                change_percent = self._safe_float(change_elem.get('data-price-change-percent'))
            else:
                change = 0
                change_percent = 0
            
            # Parse name
            name_elem = soup.select_one('div.zzDege')
            name = name_elem.text.strip() if name_elem else symbol
            
            return StockData(
                symbol=symbol,
                name=name,
                current_price=current_price,
                change=change,
                change_percent=change_percent,
                volume=0,  # Google Finance doesn't easily provide volume
                source="Google Finance"
            )
            
        except Exception as e:
            logger.error(f"Google Finance 데이터 수집 실패 ({symbol}): {e}")
            return None
    
    async def get_all_sources_data(self, symbol: str, korean_code: str = None) -> Dict[str, StockData]:
        """
        모든 소스에서 데이터 수집
        
        Args:
            symbol: 국제 티커 심볼 (예: 'AAPL')
            korean_code: 한국 종목 코드 (예: '005930')
        """
        results = {}
        
        # Korean sources (if korean_code provided)
        if korean_code:
            # Naver
            naver_data = await self.get_naver_stock_data(korean_code)
            if naver_data:
                results['naver'] = naver_data
            
            # Daum
            daum_data = await self.get_daum_stock_data(korean_code)
            if daum_data:
                results['daum'] = daum_data
        
        # International sources
        # Yahoo Finance
        yahoo_data = self.get_yahoo_finance_data(symbol)
        if yahoo_data:
            results['yahoo'] = yahoo_data
        
        # Google Finance
        google_data = await self.get_google_finance_data(symbol)
        if google_data:
            results['google'] = google_data
        
        return results
    
    def aggregate_data(self, data_sources: Dict[str, StockData]) -> StockData:
        """
        여러 소스의 데이터를 집계하여 최종 데이터 생성
        
        Args:
            data_sources: 소스별 주식 데이터
        """
        if not data_sources:
            return None
        
        # Priority: Yahoo > Naver > Daum > Google
        priority_order = ['yahoo', 'naver', 'daum', 'google']
        
        for source in priority_order:
            if source in data_sources:
                return data_sources[source]
        
        # Fallback to first available
        return list(data_sources.values())[0]


class StockDataManager:
    """주식 데이터 관리자"""
    
    def __init__(self, cache_file: str = "stock_data_cache.json"):
        """
        초기화
        
        Args:
            cache_file: 캐시 파일 경로
        """
        self.cache_file = Path(cache_file)
        self.collector = FreeStockDataCollector()
        self.cache = self._load_cache()
        
    def _load_cache(self) -> dict:
        """캐시 로드"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"캐시 로드 실패: {e}")
        return {}
    
    def _save_cache(self):
        """캐시 저장"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"캐시 저장 실패: {e}")
    
    async def get_stock_data(
        self, 
        symbol: str, 
        korean_code: str = None,
        use_cache: bool = True,
        cache_ttl: int = 300  # 5 minutes
    ) -> Dict[str, Any]:
        """
        주식 데이터 조회
        
        Args:
            symbol: 국제 티커 심볼
            korean_code: 한국 종목 코드
            use_cache: 캐시 사용 여부
            cache_ttl: 캐시 TTL (초)
        """
        cache_key = f"{symbol}_{korean_code}" if korean_code else symbol
        
        # Check cache
        if use_cache and cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if 'timestamp' in cached_data:
                cache_time = datetime.fromisoformat(cached_data['timestamp'])
                if (datetime.now() - cache_time).seconds < cache_ttl:
                    logger.info(f"캐시에서 데이터 반환: {cache_key}")
                    return cached_data
        
        # Fetch fresh data
        logger.info(f"새로운 데이터 수집: {cache_key}")
        data_sources = await self.collector.get_all_sources_data(symbol, korean_code)
        
        # Aggregate data
        aggregated = self.collector.aggregate_data(data_sources)
        
        result = {
            'symbol': symbol,
            'korean_code': korean_code,
            'aggregated': asdict(aggregated) if aggregated else None,
            'sources': {k: asdict(v) for k, v in data_sources.items()},
            'timestamp': datetime.now().isoformat()
        }
        
        # Update cache
        self.cache[cache_key] = result
        self._save_cache()
        
        return result


# Example usage
async def main():
    """테스트 함수"""
    manager = StockDataManager()
    
    # Test Korean stock (Samsung Electronics)
    print("=== 삼성전자 데이터 수집 ===")
    samsung_data = await manager.get_stock_data('005930.KS', '005930')
    print(json.dumps(samsung_data, indent=2, ensure_ascii=False, default=str))
    
    print("\n=== Apple 데이터 수집 ===")
    apple_data = await manager.get_stock_data('AAPL')
    print(json.dumps(apple_data, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())