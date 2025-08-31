#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
통합 뉴스 분석 시스템
- 무료 뉴스 크롤링 + KoBERT 감성분석 + Alpha Vantage 데이터 통합
- GPT-5 거래 결정을 위한 시장 감성 및 뉴스 분석 제공
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import pandas as pd

# 내부 모듈 임포트
from .free_news_crawler import FreeKoreanNewsCrawler, NewsDataManager
from .kobert_sentiment_analyzer import NewssentimentProcessor
from .alpha_vantage_connector import FreeDataAggregator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntegratedNewsAnalyzer:
    """통합 뉴스 분석 시스템"""
    
    def __init__(self, alpha_vantage_key: str = "demo", cache_dir: str = "news_analysis_cache"):
        """
        통합 뉴스 분석기 초기화
        
        Args:
            alpha_vantage_key: Alpha Vantage API 키 (무료 계정)
            cache_dir: 캐시 디렉토리 경로
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # 컴포넌트 초기화
        self.news_manager = NewsDataManager(str(self.cache_dir / "korean_news_cache.json"))
        self.sentiment_processor = NewssentimentProcessor()
        self.data_aggregator = FreeDataAggregator(alpha_vantage_key)
        
        # 분석 설정
        self.update_interval_hours = 1  # 1시간마다 업데이트
        self.max_news_age_hours = 24    # 24시간 이내 뉴스만 사용
        
        logger.info("통합 뉴스 분석기 초기화 완료")
    
    async def update_all_data(self) -> Dict[str, Any]:
        """모든 데이터 소스 업데이트"""
        logger.info("=== 통합 데이터 업데이트 시작 ===")
        
        update_results = {
            'timestamp': datetime.now().isoformat(),
            'korean_news': {},
            'market_data': {},
            'sentiment_analysis': {},
            'errors': []
        }
        
        try:
            # 1. 한국 뉴스 업데이트
            logger.info("1. 한국 뉴스 크롤링 시작")
            korean_articles = await self.news_manager.update_news_cache()
            update_results['korean_news'] = {
                'article_count': len(korean_articles),
                'sources': list(set(article.source for article in korean_articles)),
                'latest_article': korean_articles[0].published_date.isoformat() if korean_articles else None
            }
            logger.info(f"한국 뉴스 {len(korean_articles)}개 업데이트 완료")
            
        except Exception as e:
            error_msg = f"한국 뉴스 업데이트 실패: {e}"
            logger.error(error_msg)
            update_results['errors'].append(error_msg)
            korean_articles = []
        
        try:
            # 2. 시장 데이터 업데이트
            logger.info("2. Alpha Vantage 시장 데이터 수집")
            market_data = self.data_aggregator.get_comprehensive_market_data()
            update_results['market_data'] = {
                'market_sentiment': market_data['market_summary']['market_sentiment'],
                'stocks_analyzed': len(market_data['market_summary']['stocks']),
                'international_news': len(market_data['market_news']),
                'api_requests_remaining': market_data['api_status']['requests_remaining']
            }
            logger.info("시장 데이터 수집 완료")
            
        except Exception as e:
            error_msg = f"시장 데이터 수집 실패: {e}"
            logger.error(error_msg)
            update_results['errors'].append(error_msg)
            market_data = {'market_summary': {}, 'market_news': []}
        
        try:
            # 3. 감성분석 수행
            if korean_articles:
                logger.info("3. KoBERT 감성분석 수행")
                processed_articles = self.sentiment_processor.process_news_articles(korean_articles)
                sentiment_summary = self.sentiment_processor.get_market_sentiment_summary(processed_articles)
                
                update_results['sentiment_analysis'] = {
                    'overall_sentiment': sentiment_summary['overall_sentiment'],
                    'sentiment_score': sentiment_summary['sentiment_score'],
                    'confidence': sentiment_summary['confidence'],
                    'positive_articles': sentiment_summary['sentiment_distribution']['positive'],
                    'negative_articles': sentiment_summary['sentiment_distribution']['negative'],
                    'neutral_articles': sentiment_summary['sentiment_distribution']['neutral']
                }
                logger.info("감성분석 완료")
            else:
                processed_articles = []
                sentiment_summary = {}
                
        except Exception as e:
            error_msg = f"감성분석 실패: {e}"
            logger.error(error_msg)
            update_results['errors'].append(error_msg)
            processed_articles = []
            sentiment_summary = {}
        
        # 4. 통합 분석 데이터 저장
        try:
            integrated_data = {
                'update_time': datetime.now().isoformat(),
                'korean_articles': processed_articles,
                'market_data': market_data,
                'sentiment_summary': sentiment_summary,
                'update_results': update_results
            }
            
            # JSON으로 저장
            with open(self.cache_dir / "integrated_analysis.json", 'w', encoding='utf-8') as f:
                json.dump(integrated_data, f, ensure_ascii=False, indent=2)
            
            logger.info("통합 분석 데이터 저장 완료")
            
        except Exception as e:
            error_msg = f"데이터 저장 실패: {e}"
            logger.error(error_msg)
            update_results['errors'].append(error_msg)
        
        logger.info("=== 통합 데이터 업데이트 완료 ===")
        return update_results
    
    def get_trading_decision_data(self, symbol: str = None) -> Dict[str, Any]:
        """
        거래 결정을 위한 분석 데이터 제공
        GPT-5 거래 알고리즘에서 사용할 수 있는 형태로 가공
        """
        try:
            # 저장된 통합 데이터 로드
            with open(self.cache_dir / "integrated_analysis.json", 'r', encoding='utf-8') as f:
                integrated_data = json.load(f)
        except FileNotFoundError:
            logger.warning("통합 데이터 없음 - 새로 수집 필요")
            return {'error': '데이터 없음', 'recommendation': '데이터 업데이트 필요'}
        
        # 데이터 신선도 체크
        update_time = datetime.fromisoformat(integrated_data['update_time'])
        hours_old = (datetime.now() - update_time).total_seconds() / 3600
        
        if hours_old > self.update_interval_hours:
            logger.warning(f"데이터가 {hours_old:.1f}시간 오래됨 - 업데이트 권장")
        
        # 거래 결정용 데이터 구성
        decision_data = {
            'timestamp': integrated_data['update_time'],
            'data_freshness_hours': hours_old,
            'market_sentiment': self._extract_market_sentiment(integrated_data),
            'news_analysis': self._extract_news_analysis(integrated_data, symbol),
            'technical_data': self._extract_technical_data(integrated_data, symbol),
            'risk_factors': self._extract_risk_factors(integrated_data),
            'confidence_score': self._calculate_confidence_score(integrated_data)
        }
        
        return decision_data
    
    def _extract_market_sentiment(self, data: Dict) -> Dict[str, Any]:
        """시장 감성 추출"""
        sentiment_summary = data.get('sentiment_summary', {})
        market_data = data.get('market_data', {}).get('market_summary', {})
        
        return {
            'korean_news_sentiment': sentiment_summary.get('overall_sentiment', 'neutral'),
            'korean_sentiment_score': sentiment_summary.get('sentiment_score', 0.0),
            'korean_sentiment_confidence': sentiment_summary.get('confidence', 0.5),
            'international_sentiment': market_data.get('market_sentiment', 'neutral'),
            'major_stocks_change': market_data.get('average_change_percent', 0.0),
            'sentiment_distribution': sentiment_summary.get('sentiment_distribution', {}),
        }
    
    def _extract_news_analysis(self, data: Dict, symbol: str = None) -> Dict[str, Any]:
        """뉴스 분석 추출"""
        korean_articles = data.get('korean_articles', [])
        international_news = data.get('market_data', {}).get('market_news', [])
        
        # 심볼별 관련 뉴스 필터링
        relevant_korean = []
        if symbol and korean_articles:
            symbol_keywords = {
                '005930': ['삼성전자', '삼성', '반도체', '메모리'],
                '000660': ['SK하이닉스', 'SK', '하이닉스', '반도체'],
                '035420': ['네이버', 'NAVER', '인터넷', '플랫폼'],
                '051910': ['LG화학', 'LG', '화학', '배터리'],
                '005380': ['현대차', '현대', '자동차', '전기차']
            }
            
            keywords = symbol_keywords.get(symbol, [])
            for article in korean_articles:
                if any(keyword in article.get('title', '') or keyword in str(article.get('keywords', [])) for keyword in keywords):
                    relevant_korean.append(article)
        
        return {
            'korean_news_count': len(korean_articles),
            'relevant_korean_news': relevant_korean[:5],  # 상위 5개
            'international_news_count': len(international_news),
            'top_international_news': international_news[:3],  # 상위 3개
            'key_topics': self._extract_key_topics(korean_articles + international_news)
        }
    
    def _extract_technical_data(self, data: Dict, symbol: str = None) -> Dict[str, Any]:
        """기술적 데이터 추출"""
        market_summary = data.get('market_data', {}).get('market_summary', {})
        stocks_data = market_summary.get('stocks', {})
        
        if symbol and symbol in stocks_data:
            stock_data = stocks_data[symbol]
            return {
                'current_price': stock_data.get('price'),
                'price_change': stock_data.get('change'),
                'price_change_percent': stock_data.get('change_percent'),
                'volume': stock_data.get('volume'),
                'relative_performance': self._calculate_relative_performance(stock_data, market_summary)
            }
        else:
            return {
                'market_average_change': market_summary.get('average_change_percent', 0.0),
                'market_sentiment': market_summary.get('market_sentiment', 'neutral'),
                'data_available': False
            }
    
    def _extract_risk_factors(self, data: Dict) -> List[Dict[str, Any]]:
        """리스크 요인 추출"""
        risk_factors = []
        
        # 데이터 신선도 리스크
        update_time = datetime.fromisoformat(data['update_time'])
        hours_old = (datetime.now() - update_time).total_seconds() / 3600
        if hours_old > 2:
            risk_factors.append({
                'type': 'data_freshness',
                'severity': 'medium' if hours_old < 6 else 'high',
                'description': f'데이터가 {hours_old:.1f}시간 오래됨'
            })
        
        # API 한도 리스크
        api_status = data.get('market_data', {}).get('api_status', {})
        remaining_requests = api_status.get('requests_remaining', 500)
        if remaining_requests < 50:
            risk_factors.append({
                'type': 'api_limit',
                'severity': 'high' if remaining_requests < 20 else 'medium',
                'description': f'Alpha Vantage API 잔여 요청: {remaining_requests}개'
            })
        
        # 감성 신뢰도 리스크
        sentiment_confidence = data.get('sentiment_summary', {}).get('confidence', 0.5)
        if sentiment_confidence < 0.6:
            risk_factors.append({
                'type': 'sentiment_confidence',
                'severity': 'medium',
                'description': f'감성분석 신뢰도 낮음: {sentiment_confidence:.2f}'
            })
        
        return risk_factors
    
    def _calculate_confidence_score(self, data: Dict) -> float:
        """전체 신뢰도 점수 계산"""
        scores = []
        
        # 데이터 신선도 (0-1)
        update_time = datetime.fromisoformat(data['update_time'])
        hours_old = (datetime.now() - update_time).total_seconds() / 3600
        freshness_score = max(0, 1 - (hours_old / 24))  # 24시간 기준
        scores.append(freshness_score * 0.3)
        
        # 뉴스 데이터 품질 (0-1)
        korean_count = len(data.get('korean_articles', []))
        news_score = min(1.0, korean_count / 20)  # 20개 기준
        scores.append(news_score * 0.3)
        
        # 감성분석 신뢰도 (0-1)
        sentiment_confidence = data.get('sentiment_summary', {}).get('confidence', 0.5)
        scores.append(sentiment_confidence * 0.2)
        
        # 시장 데이터 품질 (0-1)
        market_stocks = len(data.get('market_data', {}).get('market_summary', {}).get('stocks', {}))
        market_score = min(1.0, market_stocks / 5)  # 5개 종목 기준
        scores.append(market_score * 0.2)
        
        return sum(scores)
    
    def _extract_key_topics(self, articles: List[Dict]) -> List[str]:
        """주요 토픽 추출"""
        all_keywords = []
        for article in articles:
            keywords = article.get('keywords', [])
            if isinstance(keywords, list):
                all_keywords.extend(keywords)
        
        # 키워드 빈도 계산
        keyword_freq = {}
        for keyword in all_keywords:
            keyword_freq[keyword] = keyword_freq.get(keyword, 0) + 1
        
        # 상위 키워드 반환
        sorted_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)
        return [keyword for keyword, freq in sorted_keywords[:10]]
    
    def _calculate_relative_performance(self, stock_data: Dict, market_summary: Dict) -> float:
        """상대적 성과 계산"""
        stock_change = stock_data.get('change_percent', 0.0)
        market_change = market_summary.get('average_change_percent', 0.0)
        return stock_change - market_change
    
    def generate_analysis_report(self) -> str:
        """분석 리포트 생성"""
        decision_data = self.get_trading_decision_data()
        
        if 'error' in decision_data:
            return f"분석 리포트 생성 불가: {decision_data['error']}"
        
        report = []
        report.append("=== GPT4wiseTide 통합 뉴스 분석 리포트 ===\n")
        
        # 시장 감성
        market_sentiment = decision_data['market_sentiment']
        report.append(f"🎯 시장 감성 분석:")
        report.append(f"   • 한국 뉴스 감성: {market_sentiment['korean_news_sentiment']} (점수: {market_sentiment['korean_sentiment_score']:.2f})")
        report.append(f"   • 국제 시장 감성: {market_sentiment['international_sentiment']}")
        report.append(f"   • 주요 종목 평균 변화: {market_sentiment['major_stocks_change']:+.2f}%\n")
        
        # 뉴스 분석
        news_analysis = decision_data['news_analysis']
        report.append(f"📰 뉴스 분석:")
        report.append(f"   • 한국 뉴스: {news_analysis['korean_news_count']}개")
        report.append(f"   • 국제 뉴스: {news_analysis['international_news_count']}개")
        report.append(f"   • 주요 토픽: {', '.join(news_analysis['key_topics'][:5])}\n")
        
        # 리스크 요인
        risk_factors = decision_data['risk_factors']
        if risk_factors:
            report.append(f"⚠️ 리스크 요인:")
            for risk in risk_factors:
                report.append(f"   • [{risk['severity'].upper()}] {risk['description']}")
            report.append("")
        
        # 신뢰도
        confidence = decision_data['confidence_score']
        report.append(f"🔍 전체 신뢰도: {confidence:.2f}/1.00")
        report.append(f"📅 데이터 업데이트: {decision_data['data_freshness_hours']:.1f}시간 전")
        
        return "\n".join(report)

# 스케줄러 및 자동화 클래스
class NewsAnalysisScheduler:
    """뉴스 분석 스케줄러"""
    
    def __init__(self, analyzer: IntegratedNewsAnalyzer, update_interval_minutes: int = 60):
        self.analyzer = analyzer
        self.update_interval = update_interval_minutes * 60  # 초 단위
        self.running = False
        
    async def start_scheduler(self):
        """스케줄러 시작"""
        self.running = True
        logger.info(f"뉴스 분석 스케줄러 시작 (간격: {self.update_interval/60:.0f}분)")
        
        while self.running:
            try:
                logger.info("스케줄된 데이터 업데이트 시작")
                await self.analyzer.update_all_data()
                logger.info("스케줄된 데이터 업데이트 완료")
                
                # 다음 업데이트까지 대기
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"스케줄러 실행 중 오류: {e}")
                await asyncio.sleep(300)  # 5분 후 재시도
    
    def stop_scheduler(self):
        """스케줄러 중지"""
        self.running = False
        logger.info("뉴스 분석 스케줄러 중지")

# 테스트 및 실행 함수
async def main():
    """메인 테스트 함수"""
    print("=== 통합 뉴스 분석 시스템 테스트 ===\n")
    
    # 분석기 초기화
    analyzer = IntegratedNewsAnalyzer()
    
    # 데이터 업데이트
    print("1. 데이터 업데이트 중...")
    update_results = await analyzer.update_all_data()
    print(f"업데이트 결과: {json.dumps(update_results, indent=2, ensure_ascii=False)}\n")
    
    # 거래 결정 데이터 생성
    print("2. 거래 결정 데이터 생성...")
    decision_data = analyzer.get_trading_decision_data('005930')  # 삼성전자
    print(f"삼성전자 분석 데이터 생성 완료\n")
    
    # 리포트 생성
    print("3. 분석 리포트 생성...")
    report = analyzer.generate_analysis_report()
    print(report)

if __name__ == "__main__":
    asyncio.run(main())