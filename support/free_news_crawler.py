#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
무료 한국어 뉴스 크롤링 시스템
- 연합뉴스, 조선일보, 코리아헤럴드 등 RSS 피드 활용
- BeautifulSoup을 이용한 웹 크롤링
- 비용 없는 무료 뉴스 데이터 수집
"""

import asyncio
import aiohttp
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import time
import logging
from dataclasses import dataclass
import re
from urllib.parse import urljoin, urlparse
import hashlib

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NewsArticle:
    """뉴스 기사 데이터 클래스"""
    title: str
    content: str
    url: str
    published_date: datetime
    source: str
    category: str
    keywords: List[str]
    sentiment_score: Optional[float] = None
    relevance_score: Optional[float] = None
    hash_id: Optional[str] = None
    
    def __post_init__(self):
        # 기사 고유 해시 생성
        self.hash_id = hashlib.md5(f"{self.url}_{self.title}".encode()).hexdigest()

class FreeKoreanNewsCrawler:
    """무료 한국어 뉴스 크롤러"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 무료 RSS 피드 소스들
        self.rss_sources = {
            'yonhap_economy': {
                'url': 'https://www.yna.co.kr/rss/economy.xml',
                'category': 'economy',
                'source': '연합뉴스'
            },
            'yonhap_stock': {
                'url': 'https://www.yna.co.kr/rss/stock.xml', 
                'category': 'stock',
                'source': '연합뉴스'
            },
            'chosun_economy': {
                'url': 'https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml',
                'category': 'economy',
                'source': '조선일보'
            },
            'korea_herald': {
                'url': 'http://www.koreaherald.com/rss/business.xml',
                'category': 'business',
                'source': 'Korea Herald'
            },
            'hankyung': {
                'url': 'https://www.hankyung.com/feed/economy',
                'category': 'economy', 
                'source': '한국경제'
            }
        }
        
        # 금융 관련 키워드
        self.financial_keywords = [
            '주식', '증시', '코스피', '코스닥', '삼성전자', 'SK하이닉스', 'NAVER',
            '금리', '환율', '달러', '투자', '기업', '실적', '매출', '영업이익',
            '상장', '공모', 'IPO', 'M&A', '인수합병', '배당', '주주',
            '반도체', 'IT', '바이오', '자동차', '화학', '금융', '부동산'
        ]
        
    async def fetch_rss_feeds(self) -> List[NewsArticle]:
        """RSS 피드에서 뉴스 수집"""
        articles = []
        
        for source_name, source_info in self.rss_sources.items():
            try:
                logger.info(f"RSS 피드 수집 중: {source_info['source']}")
                
                # RSS 피드 파싱
                feed = feedparser.parse(source_info['url'])
                
                for entry in feed.entries[:20]:  # 최신 20개 기사만
                    try:
                        # 날짜 파싱
                        if hasattr(entry, 'published_parsed'):
                            pub_date = datetime(*entry.published_parsed[:6])
                        else:
                            pub_date = datetime.now()
                        
                        # 최근 24시간 이내 기사만
                        if pub_date < datetime.now() - timedelta(days=1):
                            continue
                            
                        # 기사 내용 추출
                        content = self._extract_article_content(entry.link)
                        
                        # 금융 관련 키워드 추출
                        keywords = self._extract_keywords(entry.title + " " + content)
                        
                        # 금융 관련 기사만 필터링
                        if not keywords:
                            continue
                            
                        article = NewsArticle(
                            title=entry.title,
                            content=content,
                            url=entry.link,
                            published_date=pub_date,
                            source=source_info['source'],
                            category=source_info['category'],
                            keywords=keywords
                        )
                        
                        articles.append(article)
                        
                    except Exception as e:
                        logger.warning(f"기사 처리 오류 ({entry.link}): {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"RSS 피드 처리 오류 ({source_name}): {e}")
                continue
                
        logger.info(f"총 {len(articles)}개 기사 수집 완료")
        return articles
    
    def _extract_article_content(self, url: str) -> str:
        """기사 본문 추출"""
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 다양한 뉴스 사이트 본문 추출 패턴
            content_selectors = [
                'div.article-body',
                'div.news-content', 
                'div.article-content',
                'div.content-body',
                'div.story-body',
                'article',
                'div.article_body',
                'div.view-content',
                'div.article-text'
            ]
            
            content = ""
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content = ' '.join([elem.get_text().strip() for elem in elements])
                    break
            
            # 본문이 없으면 요약이나 리드 문구 사용
            if not content:
                summary = soup.find('meta', attrs={'name': 'description'})
                if summary:
                    content = summary.get('content', '')
            
            # 불필요한 문자 제거 및 정리
            content = re.sub(r'\s+', ' ', content).strip()
            return content[:1000]  # 최대 1000자
            
        except Exception as e:
            logger.warning(f"본문 추출 실패 ({url}): {e}")
            return ""
    
    def _extract_keywords(self, text: str) -> List[str]:
        """금융 관련 키워드 추출"""
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in self.financial_keywords:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords[:10]  # 최대 10개 키워드
    
    async def get_latest_financial_news(self, hours: int = 24) -> List[NewsArticle]:
        """최신 금융 뉴스 수집"""
        logger.info(f"최근 {hours}시간 금융 뉴스 수집 시작")
        
        # RSS 피드에서 뉴스 수집
        articles = await self.fetch_rss_feeds()
        
        # 시간 필터링
        cutoff_time = datetime.now() - timedelta(hours=hours)
        filtered_articles = [
            article for article in articles 
            if article.published_date > cutoff_time
        ]
        
        # 중복 제거 (해시 기반)
        seen_hashes = set()
        unique_articles = []
        for article in filtered_articles:
            if article.hash_id not in seen_hashes:
                seen_hashes.add(article.hash_id)
                unique_articles.append(article)
        
        logger.info(f"중복 제거 후 {len(unique_articles)}개 기사")
        
        # 관련도 점수 계산
        for article in unique_articles:
            article.relevance_score = self._calculate_relevance_score(article)
        
        # 관련도 순으로 정렬
        unique_articles.sort(key=lambda x: x.relevance_score or 0, reverse=True)
        
        return unique_articles[:50]  # 상위 50개만 반환
    
    def _calculate_relevance_score(self, article: NewsArticle) -> float:
        """기사 관련도 점수 계산"""
        score = 0.0
        
        # 키워드 개수에 따른 기본 점수
        score += len(article.keywords) * 0.1
        
        # 중요 키워드 가중치
        important_keywords = ['삼성전자', 'SK하이닉스', 'NAVER', '코스피', '코스닥']
        for keyword in article.keywords:
            if keyword in important_keywords:
                score += 0.3
        
        # 제목에 중요 키워드가 있으면 가중치
        for keyword in important_keywords:
            if keyword in article.title:
                score += 0.5
        
        return min(score, 10.0)  # 최대 10점

class NewsDataManager:
    """뉴스 데이터 관리 클래스"""
    
    def __init__(self, cache_file: str = "news_cache.json"):
        self.cache_file = cache_file
        self.crawler = FreeKoreanNewsCrawler()
    
    def save_articles(self, articles: List[NewsArticle]) -> None:
        """기사 데이터 저장"""
        data = []
        for article in articles:
            data.append({
                'title': article.title,
                'content': article.content,
                'url': article.url,
                'published_date': article.published_date.isoformat(),
                'source': article.source,
                'category': article.category,
                'keywords': article.keywords,
                'sentiment_score': article.sentiment_score,
                'relevance_score': article.relevance_score,
                'hash_id': article.hash_id
            })
        
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"{len(articles)}개 기사 저장 완료: {self.cache_file}")
    
    def load_articles(self) -> List[NewsArticle]:
        """저장된 기사 데이터 로드"""
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            articles = []
            for item in data:
                article = NewsArticle(
                    title=item['title'],
                    content=item['content'], 
                    url=item['url'],
                    published_date=datetime.fromisoformat(item['published_date']),
                    source=item['source'],
                    category=item['category'],
                    keywords=item['keywords'],
                    sentiment_score=item.get('sentiment_score'),
                    relevance_score=item.get('relevance_score'),
                    hash_id=item.get('hash_id')
                )
                articles.append(article)
            
            return articles
            
        except FileNotFoundError:
            return []
    
    async def update_news_cache(self) -> List[NewsArticle]:
        """뉴스 캐시 업데이트"""
        logger.info("뉴스 캐시 업데이트 시작")
        
        # 최신 뉴스 수집
        new_articles = await self.crawler.get_latest_financial_news()
        
        # 기존 캐시 로드
        existing_articles = self.load_articles()
        existing_hashes = {article.hash_id for article in existing_articles}
        
        # 신규 기사만 필터링
        unique_new_articles = [
            article for article in new_articles
            if article.hash_id not in existing_hashes
        ]
        
        # 전체 기사 리스트 (최근 48시간 이내만 유지)
        cutoff_time = datetime.now() - timedelta(hours=48)
        all_articles = existing_articles + unique_new_articles
        recent_articles = [
            article for article in all_articles
            if article.published_date > cutoff_time
        ]
        
        # 저장
        self.save_articles(recent_articles)
        
        logger.info(f"신규 {len(unique_new_articles)}개 기사 추가, 총 {len(recent_articles)}개 기사 유지")
        return recent_articles

# 테스트 및 실행 함수
async def main():
    """테스트 실행"""
    manager = NewsDataManager()
    
    # 뉴스 수집 및 업데이트
    articles = await manager.update_news_cache()
    
    print(f"\n=== 최신 금융 뉴스 ({len(articles)}개) ===")
    for i, article in enumerate(articles[:5], 1):
        print(f"\n{i}. [{article.source}] {article.title}")
        print(f"   키워드: {', '.join(article.keywords)}")
        print(f"   관련도: {article.relevance_score:.2f}")
        print(f"   시간: {article.published_date.strftime('%Y-%m-%d %H:%M')}")
        if article.content:
            print(f"   요약: {article.content[:100]}...")

if __name__ == "__main__":
    asyncio.run(main())