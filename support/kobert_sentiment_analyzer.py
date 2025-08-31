#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KoBERT 기반 한국어 금융 감성분석 모델
- Hugging Face Transformers 활용
- 한국어 금융 뉴스 특화 감성분석
- 무료 사전훈련 모델 활용
"""

import torch
import torch.nn as nn
from transformers import (
    AutoTokenizer, AutoModel, 
    pipeline, AutoModelForSequenceClassification
)
import numpy as np
import json
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import re
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SentimentResult:
    """감성분석 결과 클래스"""
    text: str
    sentiment: str  # positive, negative, neutral
    confidence: float
    score: float  # -1.0 ~ 1.0
    details: Dict[str, float]
    financial_keywords: List[str]
    timestamp: datetime

class KoFinBERTAnalyzer:
    """KoBERT 기반 한국어 금융 감성분석기"""
    
    def __init__(self, model_name: str = "klue/bert-base"):
        """
        KoBERT 감성분석기 초기화
        - klue/bert-base: KLUE 사전훈련 모델 (무료)
        - snunlp/KR-FinBert: 한국어 금융 특화 모델 (무료)
        """
        self.model_name = model_name
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"사용 디바이스: {self.device}")
        
        # 토크나이저와 모델 로드
        self._load_model()
        
        # 금융 감성 키워드 사전
        self.sentiment_keywords = {
            'positive': [
                '상승', '급등', '호조', '개선', '성장', '증가', '확대', '호실적',
                '수익', '이익', '흑자', '플러스', '매수', '투자', '전망', '좋은',
                '상향', '추천', '긍정', '기대', '돌파', '신고점', '최고',
                '호재', '기회', '강세', '회복', '반등'
            ],
            'negative': [
                '하락', '급락', '부진', '악화', '감소', '축소', '저조', '부실적',
                '손실', '적자', '마이너스', '매도', '위험', '우려', '나쁜',
                '하향', '주의', '부정', '불안', '붕괴', '신저점', '최저',
                '악재', '위기', '약세', '침체', '폭락'
            ]
        }
        
        # 사전 기반 감성분석을 위한 점수 매핑
        self.keyword_scores = {}
        for keyword in self.sentiment_keywords['positive']:
            self.keyword_scores[keyword] = 1.0
        for keyword in self.sentiment_keywords['negative']:
            self.keyword_scores[keyword] = -1.0
    
    def _load_model(self):
        """모델 로드"""
        try:
            logger.info(f"모델 로드 중: {self.model_name}")
            
            # 토크나이저 로드
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # 사전훈련된 감성분석 파이프라인 시도
            try:
                self.pipeline = pipeline(
                    "sentiment-analysis",
                    model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                    tokenizer="cardiffnlp/twitter-roberta-base-sentiment-latest"
                )
                logger.info("사전훈련된 감성분석 파이프라인 로드 성공")
                self.use_pipeline = True
            except:
                # 파이프라인 로드 실패시 기본 BERT 모델 사용
                self.model = AutoModel.from_pretrained(self.model_name)
                self.model.to(self.device)
                self.use_pipeline = False
                logger.info("기본 BERT 모델로 로드")
                
        except Exception as e:
            logger.error(f"모델 로드 실패: {e}")
            # 폴백: 사전 기반 분석만 사용
            self.use_pipeline = False
            self.model = None
            logger.warning("사전 기반 분석만 사용")
    
    def _preprocess_text(self, text: str) -> str:
        """텍스트 전처리"""
        # 불필요한 문자 제거
        text = re.sub(r'[^\w\s가-힣]', ' ', text)
        # 여러 공백을 하나로
        text = re.sub(r'\s+', ' ', text).strip()
        # 길이 제한 (BERT 토큰 제한)
        return text[:500]
    
    def _extract_financial_keywords(self, text: str) -> List[str]:
        """금융 키워드 추출"""
        found_keywords = []
        text_lower = text.lower()
        
        for sentiment, keywords in self.sentiment_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    found_keywords.append(keyword)
        
        return found_keywords
    
    def _dictionary_sentiment(self, text: str, keywords: List[str]) -> Tuple[str, float, Dict]:
        """사전 기반 감성분석"""
        positive_score = 0.0
        negative_score = 0.0
        
        for keyword in keywords:
            if keyword in self.sentiment_keywords['positive']:
                positive_score += 1.0
            elif keyword in self.sentiment_keywords['negative']:
                negative_score += 1.0
        
        # 점수 정규화
        total_keywords = len(keywords) if keywords else 1
        positive_score /= total_keywords
        negative_score /= total_keywords
        
        # 감성 결정
        net_score = positive_score - negative_score
        
        if net_score > 0.1:
            sentiment = "positive"
            confidence = min(positive_score * 2, 1.0)
        elif net_score < -0.1:
            sentiment = "negative" 
            confidence = min(negative_score * 2, 1.0)
        else:
            sentiment = "neutral"
            confidence = 0.5
        
        details = {
            'positive': positive_score,
            'negative': negative_score,
            'neutral': 1.0 - positive_score - negative_score
        }
        
        return sentiment, confidence, details
    
    def _transformer_sentiment(self, text: str) -> Tuple[str, float, Dict]:
        """Transformer 기반 감성분석"""
        if not self.use_pipeline or not hasattr(self, 'pipeline'):
            return "neutral", 0.5, {'positive': 0.33, 'negative': 0.33, 'neutral': 0.34}
        
        try:
            # 파이프라인으로 감성분석
            result = self.pipeline(text)
            
            # 결과 매핑
            label_mapping = {
                'LABEL_0': 'negative',
                'LABEL_1': 'neutral', 
                'LABEL_2': 'positive',
                'NEGATIVE': 'negative',
                'NEUTRAL': 'neutral',
                'POSITIVE': 'positive'
            }
            
            sentiment = label_mapping.get(result[0]['label'], 'neutral')
            confidence = result[0]['score']
            
            # 상세 점수 생성
            if sentiment == 'positive':
                details = {'positive': confidence, 'negative': (1-confidence)/2, 'neutral': (1-confidence)/2}
            elif sentiment == 'negative':
                details = {'negative': confidence, 'positive': (1-confidence)/2, 'neutral': (1-confidence)/2}
            else:
                details = {'neutral': confidence, 'positive': (1-confidence)/2, 'negative': (1-confidence)/2}
            
            return sentiment, confidence, details
            
        except Exception as e:
            logger.warning(f"Transformer 감성분석 실패: {e}")
            return "neutral", 0.5, {'positive': 0.33, 'negative': 0.33, 'neutral': 0.34}
    
    def analyze_sentiment(self, text: str) -> SentimentResult:
        """감성분석 실행"""
        # 전처리
        processed_text = self._preprocess_text(text)
        
        # 금융 키워드 추출
        financial_keywords = self._extract_financial_keywords(processed_text)
        
        # 사전 기반 분석
        dict_sentiment, dict_confidence, dict_details = self._dictionary_sentiment(processed_text, financial_keywords)
        
        # Transformer 기반 분석
        trans_sentiment, trans_confidence, trans_details = self._transformer_sentiment(processed_text)
        
        # 두 결과 결합 (사전 기반에 더 큰 가중치)
        if financial_keywords:  # 금융 키워드가 있으면 사전 기반 중시
            final_sentiment = dict_sentiment
            final_confidence = (dict_confidence * 0.7 + trans_confidence * 0.3)
            final_details = {
                'positive': dict_details['positive'] * 0.7 + trans_details['positive'] * 0.3,
                'negative': dict_details['negative'] * 0.7 + trans_details['negative'] * 0.3,
                'neutral': dict_details['neutral'] * 0.7 + trans_details['neutral'] * 0.3
            }
        else:  # 금융 키워드가 없으면 Transformer 기반 중시
            final_sentiment = trans_sentiment
            final_confidence = (trans_confidence * 0.8 + dict_confidence * 0.2)
            final_details = {
                'positive': trans_details['positive'] * 0.8 + dict_details['positive'] * 0.2,
                'negative': trans_details['negative'] * 0.8 + dict_details['negative'] * 0.2,
                'neutral': trans_details['neutral'] * 0.8 + dict_details['neutral'] * 0.2
            }
        
        # 점수 계산 (-1.0 ~ 1.0)
        score = final_details['positive'] - final_details['negative']
        
        return SentimentResult(
            text=text,
            sentiment=final_sentiment,
            confidence=final_confidence,
            score=score,
            details=final_details,
            financial_keywords=financial_keywords,
            timestamp=datetime.now()
        )
    
    def batch_analyze(self, texts: List[str]) -> List[SentimentResult]:
        """배치 감성분석"""
        results = []
        
        logger.info(f"배치 감성분석 시작: {len(texts)}개 텍스트")
        
        for i, text in enumerate(texts):
            try:
                result = self.analyze_sentiment(text)
                results.append(result)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"진행률: {i + 1}/{len(texts)}")
                    
            except Exception as e:
                logger.error(f"텍스트 {i} 분석 실패: {e}")
                # 기본값으로 결과 추가
                results.append(SentimentResult(
                    text=text,
                    sentiment="neutral",
                    confidence=0.5,
                    score=0.0,
                    details={'positive': 0.33, 'negative': 0.33, 'neutral': 0.34},
                    financial_keywords=[],
                    timestamp=datetime.now()
                ))
        
        logger.info("배치 감성분석 완료")
        return results

class NewssentimentProcessor:
    """뉴스 감성분석 통합 처리기"""
    
    def __init__(self):
        self.analyzer = KoFinBERTAnalyzer()
    
    def process_news_articles(self, articles) -> List[Dict]:
        """뉴스 기사들의 감성분석 처리"""
        # 제목과 내용을 결합하여 분석할 텍스트 준비
        texts = []
        for article in articles:
            combined_text = f"{article.title} {article.content}"
            texts.append(combined_text)
        
        # 배치 감성분석
        sentiment_results = self.analyzer.batch_analyze(texts)
        
        # 결과를 기사 정보와 결합
        processed_articles = []
        for article, sentiment in zip(articles, sentiment_results):
            article.sentiment_score = sentiment.score
            
            # 추가 메타데이터
            article_data = {
                'title': article.title,
                'content': article.content,
                'url': article.url,
                'published_date': article.published_date.isoformat(),
                'source': article.source,
                'category': article.category,
                'keywords': article.keywords,
                'sentiment': {
                    'sentiment': sentiment.sentiment,
                    'confidence': sentiment.confidence,
                    'score': sentiment.score,
                    'details': sentiment.details,
                    'financial_keywords': sentiment.financial_keywords
                },
                'relevance_score': getattr(article, 'relevance_score', 0.0),
                'hash_id': article.hash_id
            }
            
            processed_articles.append(article_data)
        
        return processed_articles
    
    def get_market_sentiment_summary(self, processed_articles: List[Dict]) -> Dict:
        """시장 전체 감성 요약"""
        if not processed_articles:
            return {
                'overall_sentiment': 'neutral',
                'sentiment_score': 0.0,
                'confidence': 0.0,
                'article_count': 0,
                'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0}
            }
        
        # 감성 점수들 수집
        scores = [article['sentiment']['score'] for article in processed_articles]
        confidences = [article['sentiment']['confidence'] for article in processed_articles]
        sentiments = [article['sentiment']['sentiment'] for article in processed_articles]
        
        # 전체 감성 계산
        avg_score = np.mean(scores)
        avg_confidence = np.mean(confidences)
        
        # 전체 감성 결정
        if avg_score > 0.1:
            overall_sentiment = 'positive'
        elif avg_score < -0.1:
            overall_sentiment = 'negative'
        else:
            overall_sentiment = 'neutral'
        
        # 감성 분포
        sentiment_counts = {
            'positive': sentiments.count('positive'),
            'negative': sentiments.count('negative'),
            'neutral': sentiments.count('neutral')
        }
        
        return {
            'overall_sentiment': overall_sentiment,
            'sentiment_score': avg_score,
            'confidence': avg_confidence,
            'article_count': len(processed_articles),
            'sentiment_distribution': sentiment_counts,
            'top_positive_articles': [
                art for art in processed_articles 
                if art['sentiment']['sentiment'] == 'positive'
            ][:3],
            'top_negative_articles': [
                art for art in processed_articles 
                if art['sentiment']['sentiment'] == 'negative' 
            ][:3]
        }

# 테스트 함수
def test_sentiment_analyzer():
    """감성분석기 테스트"""
    analyzer = KoFinBERTAnalyzer()
    
    test_texts = [
        "삼성전자 주가가 급등하며 신고점을 돌파했다.",
        "코스피 지수가 급락하며 투자자들의 우려가 커지고 있다.",
        "한국경제의 성장률이 예상을 상회했다.",
        "반도체 업계의 전망이 불확실해지고 있다.",
        "SK하이닉스의 분기 실적이 크게 개선되었다."
    ]
    
    print("\n=== KoBERT 감성분석 테스트 ===")
    for text in test_texts:
        result = analyzer.analyze_sentiment(text)
        print(f"\n텍스트: {text}")
        print(f"감성: {result.sentiment}")
        print(f"신뢰도: {result.confidence:.3f}")
        print(f"점수: {result.score:.3f}")
        print(f"키워드: {result.financial_keywords}")
        print(f"세부: {result.details}")

if __name__ == "__main__":
    test_sentiment_analyzer()