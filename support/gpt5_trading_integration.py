#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT-5 거래 결정 통합 시스템
- 기존 tideWise 시스템과 통합
- 무료 뉴스 분석 + GPT-5 거래 결정
- 개선된 OpenAI API 연동
"""

import openai
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import asyncio
from pathlib import Path
import sys

# 기존 시스템 모듈 임포트
sys.path.append(str(Path(__file__).parent.parent))
from support.integrated_news_analyzer import IntegratedNewsAnalyzer
from support.api_connector import KISApiConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TradingDecision:
    """거래 결정 결과"""
    symbol: str
    decision: str  # BUY, SELL, HOLD
    confidence: float  # 0.0 - 1.0
    quantity: Optional[int] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    reasoning: str = ""
    risk_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class GPT5TradingEngine:
    """GPT-5 기반 거래 결정 엔진"""
    
    def __init__(self, openai_api_key: str, alpha_vantage_key: str = "demo"):
        """
        GPT-5 거래 엔진 초기화
        
        Args:
            openai_api_key: OpenAI API 키
            alpha_vantage_key: Alpha Vantage API 키 (무료)
        """
        # OpenAI 클라이언트 초기화
        openai.api_key = openai_api_key
        self.client = openai.OpenAI(api_key=openai_api_key)
        
        # 뉴스 분석기 초기화
        self.news_analyzer = IntegratedNewsAnalyzer(alpha_vantage_key)
        
        # 거래 설정
        self.trading_config = {
            'max_position_size': 0.07,  # 7% per position
            'max_positions': 5,
            'risk_tolerance': 'MEDIUM',
            'trading_hours': {
                'start': '09:05',
                'end': '15:20'
            }
        }
        
        # GPT-5 프롬프트 템플릿
        self.system_prompt = """
        You are an expert Korean stock trading AI with deep knowledge of:
        - Korean financial markets (KOSPI, KOSDAQ)
        - Technical analysis and fundamental analysis
        - Risk management and portfolio optimization
        - Korean economic indicators and news sentiment
        
        Make trading decisions based on:
        1. Current market sentiment from Korean and international news
        2. Technical indicators and price movements
        3. Risk management principles
        4. Korean market trading hours and regulations
        
        Always provide:
        - Clear BUY/SELL/HOLD decision
        - Confidence level (0.0-1.0)
        - Detailed reasoning
        - Risk assessment
        - Suggested position size and price levels
        
        Be conservative with high-risk decisions and always consider downside protection.
        """
        
        logger.info("GPT-5 거래 엔진 초기화 완료")
    
    async def make_trading_decision(self, symbol: str, current_price: float = None) -> TradingDecision:
        """
        특정 종목에 대한 거래 결정 생성
        
        Args:
            symbol: 종목 코드 (예: '005930')
            current_price: 현재가 (선택사항)
            
        Returns:
            TradingDecision: 거래 결정 결과
        """
        logger.info(f"거래 결정 생성 시작: {symbol}")
        
        try:
            # 1. 뉴스 및 시장 데이터 수집
            decision_data = self.news_analyzer.get_trading_decision_data(symbol)
            
            if 'error' in decision_data:
                logger.warning(f"뉴스 데이터 부족: {decision_data['error']}")
                # 기본 결정 반환
                return TradingDecision(
                    symbol=symbol,
                    decision="HOLD",
                    confidence=0.3,
                    reasoning="뉴스 데이터 부족으로 보수적 홀드",
                    risk_level="HIGH"
                )
            
            # 2. 종목 정보 조회 (기존 API 연동)
            stock_info = await self._get_stock_info(symbol, current_price)
            
            # 3. GPT-5에 전달할 컨텍스트 구성
            trading_context = self._build_trading_context(decision_data, stock_info, symbol)
            
            # 4. GPT-5 호출
            gpt_response = await self._call_gpt5(trading_context)
            
            # 5. 응답 파싱 및 검증
            trading_decision = self._parse_gpt_response(gpt_response, symbol)
            
            logger.info(f"거래 결정 완료: {symbol} -> {trading_decision.decision} ({trading_decision.confidence:.2f})")
            return trading_decision
            
        except Exception as e:
            logger.error(f"거래 결정 생성 실패 ({symbol}): {e}")
            # 안전한 기본 결정
            return TradingDecision(
                symbol=symbol,
                decision="HOLD",
                confidence=0.2,
                reasoning=f"시스템 오류로 인한 보수적 홀드: {str(e)}",
                risk_level="HIGH"
            )
    
    async def _get_stock_info(self, symbol: str, current_price: float = None) -> Dict[str, Any]:
        """종목 정보 조회"""
        stock_info = {
            'symbol': symbol,
            'current_price': current_price,
            'company_name': self._get_company_name(symbol),
            'sector': self._get_sector(symbol),
            'market_cap': None,
            'pe_ratio': None
        }
        
        # 추가 정보는 Alpha Vantage에서 보완
        try:
            alpha_data = self.news_analyzer.data_aggregator.get_stock_analysis_data(symbol)
            if alpha_data.get('data_quality') == 'good':
                current_data = alpha_data.get('current_data', {})
                stock_info.update({
                    'current_price': current_data.get('price') or current_price,
                    'price_change': current_data.get('change'),
                    'price_change_percent': current_data.get('change_percent'),
                    'volume': current_data.get('volume')
                })
        except Exception as e:
            logger.warning(f"Alpha Vantage 데이터 보완 실패: {e}")
        
        return stock_info
    
    def _get_company_name(self, symbol: str) -> str:
        """종목 코드에서 회사명 반환"""
        company_map = {
            '005930': '삼성전자',
            '000660': 'SK하이닉스',
            '035420': 'NAVER',
            '051910': 'LG화학',
            '005380': '현대차',
            '207940': '삼성바이오로직스',
            '068270': '셀트리온',
            '035720': '카카오'
        }
        return company_map.get(symbol, f'종목_{symbol}')
    
    def _get_sector(self, symbol: str) -> str:
        """종목 코드에서 섹터 반환"""
        sector_map = {
            '005930': '반도체',
            '000660': '반도체', 
            '035420': 'IT서비스',
            '051910': '화학',
            '005380': '자동차',
            '207940': '바이오',
            '068270': '바이오',
            '035720': 'IT서비스'
        }
        return sector_map.get(symbol, '기타')
    
    def _build_trading_context(self, decision_data: Dict, stock_info: Dict, symbol: str) -> str:
        """GPT-5에 전달할 거래 컨텍스트 구성"""
        context_parts = [
            "=== KOREAN STOCK TRADING DECISION REQUEST ===\n",
            
            f"TARGET STOCK: {stock_info['company_name']} ({symbol})",
            f"SECTOR: {stock_info['sector']}",
            f"CURRENT PRICE: {stock_info.get('current_price', 'N/A')} KRW",
            f"PRICE CHANGE: {stock_info.get('price_change_percent', 'N/A')}%\n",
            
            "=== MARKET SENTIMENT ANALYSIS ===",
            f"Korean News Sentiment: {decision_data['market_sentiment']['korean_news_sentiment']}",
            f"Sentiment Score: {decision_data['market_sentiment']['korean_sentiment_score']:.3f}",
            f"Confidence: {decision_data['market_sentiment']['korean_sentiment_confidence']:.3f}",
            f"International Sentiment: {decision_data['market_sentiment']['international_sentiment']}",
            f"Market Average Change: {decision_data['market_sentiment']['major_stocks_change']:+.2f}%\n",
            
            "=== NEWS ANALYSIS ===",
            f"Korean News Count: {decision_data['news_analysis']['korean_news_count']}",
            f"Key Topics: {', '.join(decision_data['news_analysis']['key_topics'][:5])}"
        ]
        
        # 관련 뉴스 추가
        relevant_news = decision_data['news_analysis'].get('relevant_korean_news', [])
        if relevant_news:
            context_parts.append("\nRELEVANT NEWS HEADLINES:")
            for i, news in enumerate(relevant_news[:3], 1):
                sentiment = news.get('sentiment', {})
                context_parts.append(f"{i}. {news.get('title', '')} (감성: {sentiment.get('sentiment', 'neutral')})")
        
        # 리스크 요인
        risk_factors = decision_data.get('risk_factors', [])
        if risk_factors:
            context_parts.append("\n=== RISK FACTORS ===")
            for risk in risk_factors:
                context_parts.append(f"- [{risk['severity'].upper()}] {risk['description']}")
        
        # 신뢰도 및 데이터 품질
        context_parts.extend([
            f"\n=== DATA QUALITY ===",
            f"Overall Confidence: {decision_data['confidence_score']:.2f}/1.00",
            f"Data Freshness: {decision_data['data_freshness_hours']:.1f} hours old",
            
            f"\n=== TRADING PARAMETERS ===",
            f"Max Position Size: {self.trading_config['max_position_size']:.1%}",
            f"Risk Tolerance: {self.trading_config['risk_tolerance']}",
            f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            
            f"\n=== DECISION REQUEST ===",
            "Based on the above analysis, please provide a trading decision in this exact JSON format:",
            '''
            {
                "decision": "BUY|SELL|HOLD",
                "confidence": 0.0-1.0,
                "reasoning": "detailed explanation",
                "risk_level": "LOW|MEDIUM|HIGH",
                "quantity_percent": 0.0-7.0,
                "target_price": price_or_null,
                "stop_loss": price_or_null
            }
            '''
        ])
        
        return "\n".join(context_parts)
    
    async def _call_gpt5(self, context: str) -> str:
        """GPT-5 API 호출"""
        try:
            # GPT-5 모델 사용 (실제 사용 시 모델명 확인 필요)
            response = self.client.chat.completions.create(
                model="gpt-4o",  # GPT-5 출시 시 "gpt-5"로 변경
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": context}
                ],
                max_tokens=1000,
                temperature=0.1,  # 일관된 결정을 위해 낮은 값
                response_format={"type": "json_object"}  # JSON 응답 강제
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"GPT-5 API 호출 실패: {e}")
            # 안전한 기본 응답
            return json.dumps({
                "decision": "HOLD",
                "confidence": 0.3,
                "reasoning": f"API 호출 실패로 인한 보수적 홀드: {str(e)}",
                "risk_level": "HIGH",
                "quantity_percent": 0.0,
                "target_price": None,
                "stop_loss": None
            })
    
    def _parse_gpt_response(self, gpt_response: str, symbol: str) -> TradingDecision:
        """GPT 응답 파싱 및 검증"""
        try:
            response_data = json.loads(gpt_response)
            
            # 필수 필드 검증
            decision = response_data.get('decision', 'HOLD').upper()
            if decision not in ['BUY', 'SELL', 'HOLD']:
                decision = 'HOLD'
            
            confidence = float(response_data.get('confidence', 0.5))
            confidence = max(0.0, min(1.0, confidence))  # 0-1 범위로 제한
            
            quantity_percent = float(response_data.get('quantity_percent', 0.0))
            quantity_percent = max(0.0, min(7.0, quantity_percent))  # 0-7% 제한
            
            risk_level = response_data.get('risk_level', 'MEDIUM').upper()
            if risk_level not in ['LOW', 'MEDIUM', 'HIGH']:
                risk_level = 'MEDIUM'
            
            return TradingDecision(
                symbol=symbol,
                decision=decision,
                confidence=confidence,
                reasoning=response_data.get('reasoning', ''),
                risk_level=risk_level,
                target_price=response_data.get('target_price'),
                stop_loss=response_data.get('stop_loss')
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"GPT 응답 파싱 실패: {e}")
            return TradingDecision(
                symbol=symbol,
                decision="HOLD", 
                confidence=0.2,
                reasoning=f"응답 파싱 실패로 인한 보수적 홀드: {str(e)}",
                risk_level="HIGH"
            )

class TidewiseGPTIntegration:
    """기존 tideWise 시스템과 GPT-5 통합"""
    
    def __init__(self, config_path: str = None):
        """
        통합 시스템 초기화
        
        Args:
            config_path: 설정 파일 경로 (선택사항)
        """
        self.config = self._load_config(config_path)
        
        # GPT-5 엔진 초기화
        openai_key = self.config.get('openai_api_key', '')
        alpha_key = self.config.get('alpha_vantage_key', 'demo')
        
        if not openai_key:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다")
            
        self.gpt_engine = GPT5TradingEngine(openai_key, alpha_key)
        
        # 기존 KIS API 커넥터 (필요시)
        self.kis_connector = None
        
        logger.info("TideWise-GPT 통합 시스템 초기화 완료")
    
    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """설정 로드"""
        if config_path and Path(config_path).exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 기본 설정에서 API 키 로드 시도
        try:
            register_key_path = Path(__file__).parent.parent / "Policy" / "Register_Key" / "Register_Key.md"
            if register_key_path.exists():
                content = register_key_path.read_text(encoding='utf-8')
                
                # OpenAI API 키 추출
                import re
                openai_match = re.search(r'OPEN_API Key: \[([^\]]+)\]', content)
                openai_key = openai_match.group(1) if openai_match else ''
                
                return {
                    'openai_api_key': openai_key,
                    'alpha_vantage_key': 'demo'  # 무료 키
                }
                
        except Exception as e:
            logger.warning(f"설정 로드 실패: {e}")
        
        return {'openai_api_key': '', 'alpha_vantage_key': 'demo'}
    
    async def process_trading_signal(self, symbol: str, current_price: float = None) -> Dict[str, Any]:
        """
        거래 신호 처리 (기존 시스템과 통합 포인트)
        
        Args:
            symbol: 종목 코드
            current_price: 현재가
            
        Returns:
            Dict: 거래 신호 및 메타데이터
        """
        logger.info(f"거래 신호 처리 시작: {symbol}")
        
        # GPT-5로 거래 결정 생성
        decision = await self.gpt_engine.make_trading_decision(symbol, current_price)
        
        # 기존 시스템 형식으로 변환
        trading_signal = {
            'symbol': symbol,
            'action': decision.decision,
            'confidence': decision.confidence,
            'quantity_percent': 7.0 if decision.decision == 'BUY' else 0.0,  # 기본 포지션 사이즈
            'target_price': decision.target_price,
            'stop_loss': decision.stop_loss,
            'reasoning': decision.reasoning,
            'risk_level': decision.risk_level,
            'timestamp': decision.timestamp.isoformat(),
            'source': 'GPT5_AI',
            'news_analysis': True,  # 뉴스 분석 포함됨
            'api_status': 'success'
        }
        
        logger.info(f"거래 신호 생성: {symbol} -> {decision.decision} ({decision.confidence:.2f})")
        return trading_signal
    
    async def batch_analysis(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        여러 종목 일괄 분석
        
        Args:
            symbols: 종목 코드 리스트
            
        Returns:
            Dict: 종목별 거래 신호
        """
        results = {}
        
        # 뉴스 데이터 먼저 업데이트
        await self.gpt_engine.news_analyzer.update_all_data()
        
        # 각 종목별 분석
        for symbol in symbols:
            try:
                signal = await self.process_trading_signal(symbol)
                results[symbol] = signal
            except Exception as e:
                logger.error(f"종목 {symbol} 분석 실패: {e}")
                results[symbol] = {
                    'symbol': symbol,
                    'action': 'HOLD',
                    'confidence': 0.2,
                    'error': str(e),
                    'api_status': 'error'
                }
        
        return results

# 테스트 함수
async def test_gpt5_integration():
    """GPT-5 통합 시스템 테스트"""
    print("=== GPT-5 거래 통합 시스템 테스트 ===\n")
    
    try:
        # 통합 시스템 초기화
        integration = TidewiseGPTIntegration()
        
        # 테스트 종목들
        test_symbols = ['005930', '000660', '035420']
        
        print("1. 개별 종목 분석 테스트:")
        for symbol in test_symbols[:1]:  # API 한도 고려하여 1개만
            signal = await integration.process_trading_signal(symbol)
            print(f"{symbol}: {signal['action']} (신뢰도: {signal['confidence']:.2f})")
            print(f"   이유: {signal['reasoning'][:100]}...")
        
        print(f"\n2. 시스템 상태:")
        print(f"   OpenAI API: {'설정됨' if integration.config.get('openai_api_key') else '미설정'}")
        print(f"   Alpha Vantage: {'설정됨' if integration.config.get('alpha_vantage_key') else '미설정'}")
        
    except Exception as e:
        print(f"테스트 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_gpt5_integration())