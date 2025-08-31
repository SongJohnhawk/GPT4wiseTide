#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
완전 무료 통합 데이터 시스템
- API 키 불필요
- 네이버/다음 주식 + RSS 뉴스 + Yahoo Finance
- 로컬 감성분석 (KoBERT)
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import pandas as pd

# Import our free modules
from .free_news_crawler import FreeKoreanNewsCrawler, NewsDataManager
from .free_stock_data_collector import FreeStockDataCollector, StockDataManager
try:
    from .kobert_sentiment_analyzer import NewssentimentProcessor
    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False
    print("KoBERT sentiment analyzer not available. Install transformers and torch.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegratedFreeDataSystem:
    """완전 무료 통합 데이터 시스템"""
    
    def __init__(self, cache_dir: str = "free_data_cache"):
        """
        초기화
        
        Args:
            cache_dir: 캐시 디렉토리
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.news_manager = NewsDataManager(str(self.cache_dir / "news_cache.json"))
        self.stock_manager = StockDataManager(str(self.cache_dir / "stock_cache.json"))
        
        if SENTIMENT_AVAILABLE:
            self.sentiment_processor = NewssentimentProcessor()
        else:
            self.sentiment_processor = None
            
        # Korean stock mapping
        self.korean_stocks = {
            '삼성전자': {'code': '005930', 'yahoo': '005930.KS'},
            'SK하이닉스': {'code': '000660', 'yahoo': '000660.KS'},
            'NAVER': {'code': '035420', 'yahoo': '035420.KS'},
            '카카오': {'code': '035720', 'yahoo': '035720.KS'},
            'LG화학': {'code': '051910', 'yahoo': '051910.KS'},
            '현대차': {'code': '005380', 'yahoo': '005380.KS'},
            '삼성바이오로직스': {'code': '207940', 'yahoo': '207940.KS'},
            'LG에너지솔루션': {'code': '373220', 'yahoo': '373220.KS'},
            '셀트리온': {'code': '068270', 'yahoo': '068270.KS'},
            '기아': {'code': '000270', 'yahoo': '000270.KS'}
        }
        
        # US stock mapping
        self.us_stocks = {
            'Apple': 'AAPL',
            'Microsoft': 'MSFT',
            'Google': 'GOOGL',
            'Amazon': 'AMZN',
            'Tesla': 'TSLA',
            'Meta': 'META',
            'NVIDIA': 'NVDA',
            'Netflix': 'NFLX',
            'AMD': 'AMD',
            'Intel': 'INTC'
        }
        
        logger.info("완전 무료 통합 데이터 시스템 초기화 완료")
    
    async def collect_korean_stock_data(self, stock_name: str = None) -> Dict[str, Any]:
        """
        한국 주식 데이터 수집
        
        Args:
            stock_name: 주식명 (None이면 전체 수집)
        """
        results = {}
        
        stocks_to_collect = {}
        if stock_name and stock_name in self.korean_stocks:
            stocks_to_collect = {stock_name: self.korean_stocks[stock_name]}
        else:
            stocks_to_collect = self.korean_stocks
        
        for name, info in stocks_to_collect.items():
            try:
                logger.info(f"수집 중: {name}")
                data = await self.stock_manager.get_stock_data(
                    symbol=info['yahoo'],
                    korean_code=info['code']
                )
                results[name] = data
                
                # Add delay to avoid rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"{name} 데이터 수집 실패: {e}")
                results[name] = None
        
        return results
    
    async def collect_us_stock_data(self, stock_name: str = None) -> Dict[str, Any]:
        """
        미국 주식 데이터 수집
        
        Args:
            stock_name: 주식명 (None이면 전체 수집)
        """
        results = {}
        
        stocks_to_collect = {}
        if stock_name and stock_name in self.us_stocks:
            stocks_to_collect = {stock_name: self.us_stocks[stock_name]}
        else:
            stocks_to_collect = self.us_stocks
        
        for name, symbol in stocks_to_collect.items():
            try:
                logger.info(f"수집 중: {name}")
                data = await self.stock_manager.get_stock_data(symbol=symbol)
                results[name] = data
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"{name} 데이터 수집 실패: {e}")
                results[name] = None
        
        return results
    
    async def collect_news_data(self) -> List[Any]:
        """뉴스 데이터 수집"""
        try:
            logger.info("뉴스 데이터 수집 시작")
            articles = await self.news_manager.update_news_cache()
            logger.info(f"뉴스 {len(articles)}개 수집 완료")
            return articles
        except Exception as e:
            logger.error(f"뉴스 수집 실패: {e}")
            return []
    
    def analyze_sentiment(self, articles: List[Any]) -> Dict[str, float]:
        """
        뉴스 감성 분석
        
        Args:
            articles: 뉴스 기사 리스트
        """
        if not self.sentiment_processor or not articles:
            return {'positive': 0.33, 'neutral': 0.34, 'negative': 0.33}
        
        try:
            sentiments = {'positive': 0, 'neutral': 0, 'negative': 0}
            
            for article in articles[:20]:  # Limit to 20 articles for speed
                result = self.sentiment_processor.analyze_sentiment(article.content)
                if result['sentiment'] == 'positive':
                    sentiments['positive'] += 1
                elif result['sentiment'] == 'negative':
                    sentiments['negative'] += 1
                else:
                    sentiments['neutral'] += 1
            
            total = sum(sentiments.values())
            if total > 0:
                for key in sentiments:
                    sentiments[key] = sentiments[key] / total
            
            return sentiments
            
        except Exception as e:
            logger.error(f"감성분석 실패: {e}")
            return {'positive': 0.33, 'neutral': 0.34, 'negative': 0.33}
    
    async def generate_market_report(self) -> Dict[str, Any]:
        """시장 종합 리포트 생성"""
        logger.info("=== 시장 종합 리포트 생성 시작 ===")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'korean_stocks': {},
            'us_stocks': {},
            'news_summary': {},
            'market_sentiment': {},
            'recommendations': []
        }
        
        try:
            # Collect all data in parallel
            tasks = [
                self.collect_korean_stock_data(),
                self.collect_us_stock_data(),
                self.collect_news_data()
            ]
            
            korean_data, us_data, news_data = await asyncio.gather(*tasks)
            
            # Process Korean stocks
            report['korean_stocks'] = self._process_stock_data(korean_data, 'KOSPI/KOSDAQ')
            
            # Process US stocks
            report['us_stocks'] = self._process_stock_data(us_data, 'NYSE/NASDAQ')
            
            # Process news
            if news_data:
                report['news_summary'] = {
                    'total_articles': len(news_data),
                    'latest_article': news_data[0].title if news_data else None,
                    'sources': list(set(article.source for article in news_data[:10]))
                }
                
                # Sentiment analysis
                if self.sentiment_processor:
                    sentiments = self.analyze_sentiment(news_data)
                    report['market_sentiment'] = sentiments
                    
                    # Generate recommendations based on sentiment
                    if sentiments['positive'] > 0.5:
                        report['recommendations'].append("시장 심리 긍정적 - 매수 고려")
                    elif sentiments['negative'] > 0.5:
                        report['recommendations'].append("시장 심리 부정적 - 관망 권장")
                    else:
                        report['recommendations'].append("시장 심리 중립 - 선별적 접근")
            
            # Find top movers
            top_gainers = self._find_top_movers(korean_data, us_data, 'gainers')
            top_losers = self._find_top_movers(korean_data, us_data, 'losers')
            
            report['top_movers'] = {
                'gainers': top_gainers[:5],
                'losers': top_losers[:5]
            }
            
        except Exception as e:
            logger.error(f"리포트 생성 실패: {e}")
            report['error'] = str(e)
        
        return report
    
    def _process_stock_data(self, stock_data: Dict, market: str) -> Dict:
        """주식 데이터 처리"""
        processed = {
            'market': market,
            'stocks': [],
            'average_change': 0,
            'total_volume': 0
        }
        
        total_change = 0
        valid_count = 0
        
        for name, data in stock_data.items():
            if data and data.get('aggregated'):
                agg = data['aggregated']
                processed['stocks'].append({
                    'name': name,
                    'price': agg.get('current_price', 0),
                    'change': agg.get('change', 0),
                    'change_percent': agg.get('change_percent', 0),
                    'volume': agg.get('volume', 0)
                })
                
                if agg.get('change_percent'):
                    total_change += agg['change_percent']
                    valid_count += 1
                
                processed['total_volume'] += agg.get('volume', 0)
        
        if valid_count > 0:
            processed['average_change'] = total_change / valid_count
        
        return processed
    
    def _find_top_movers(self, korean_data: Dict, us_data: Dict, type: str = 'gainers') -> List[Dict]:
        """상승/하락 종목 찾기"""
        all_stocks = []
        
        # Combine all stock data
        for name, data in {**korean_data, **us_data}.items():
            if data and data.get('aggregated'):
                agg = data['aggregated']
                all_stocks.append({
                    'name': name,
                    'change_percent': agg.get('change_percent', 0),
                    'price': agg.get('current_price', 0)
                })
        
        # Sort by change percentage
        if type == 'gainers':
            sorted_stocks = sorted(all_stocks, key=lambda x: x['change_percent'], reverse=True)
        else:
            sorted_stocks = sorted(all_stocks, key=lambda x: x['change_percent'])
        
        return sorted_stocks
    
    async def run_monitoring(self, interval_minutes: int = 30):
        """
        주기적 모니터링 실행
        
        Args:
            interval_minutes: 업데이트 간격 (분)
        """
        logger.info(f"모니터링 시작 (간격: {interval_minutes}분)")
        
        while True:
            try:
                # Generate report
                report = await self.generate_market_report()
                
                # Save report
                report_file = self.cache_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(report_file, 'w', encoding='utf-8') as f:
                    json.dump(report, f, ensure_ascii=False, indent=2, default=str)
                
                logger.info(f"리포트 저장: {report_file}")
                
                # Print summary
                self._print_report_summary(report)
                
                # Wait for next update
                await asyncio.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("모니터링 중단")
                break
            except Exception as e:
                logger.error(f"모니터링 오류: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    def _print_report_summary(self, report: Dict):
        """리포트 요약 출력"""
        print("\n" + "="*60)
        print(f"📊 시장 리포트 - {report['timestamp']}")
        print("="*60)
        
        # Korean market
        kr_data = report.get('korean_stocks', {})
        if kr_data:
            print(f"\n🇰🇷 한국 시장 (평균 변동: {kr_data.get('average_change', 0):.2f}%)")
            for stock in kr_data.get('stocks', [])[:5]:
                sign = "📈" if stock['change'] > 0 else "📉"
                print(f"  {sign} {stock['name']}: {stock['price']:,.0f}원 ({stock['change_percent']:+.2f}%)")
        
        # US market
        us_data = report.get('us_stocks', {})
        if us_data:
            print(f"\n🇺🇸 미국 시장 (평균 변동: {us_data.get('average_change', 0):.2f}%)")
            for stock in us_data.get('stocks', [])[:5]:
                sign = "📈" if stock['change'] > 0 else "📉"
                print(f"  {sign} {stock['name']}: ${stock['price']:.2f} ({stock['change_percent']:+.2f}%)")
        
        # Market sentiment
        sentiment = report.get('market_sentiment', {})
        if sentiment:
            print(f"\n😊 시장 심리")
            print(f"  긍정: {sentiment.get('positive', 0)*100:.1f}%")
            print(f"  중립: {sentiment.get('neutral', 0)*100:.1f}%")
            print(f"  부정: {sentiment.get('negative', 0)*100:.1f}%")
        
        # Recommendations
        recs = report.get('recommendations', [])
        if recs:
            print(f"\n💡 추천사항")
            for rec in recs:
                print(f"  • {rec}")
        
        print("="*60)


# Example usage and testing
async def main():
    """테스트 및 예제"""
    system = IntegratedFreeDataSystem()
    
    # Generate a single report
    print("단일 리포트 생성 중...")
    report = await system.generate_market_report()
    
    # Save report
    with open('market_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    
    print("리포트가 market_report.json에 저장되었습니다.")
    
    # Uncomment to run continuous monitoring
    # await system.run_monitoring(interval_minutes=30)


if __name__ == "__main__":
    asyncio.run(main())