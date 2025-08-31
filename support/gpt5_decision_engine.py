#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT-5 기반 매매 결정 엔진
- OpenAI GPT-5 API 통합 (gpt-5, gpt-5-mini, gpt-5-nano)
- 최신 연구 적용: 샤프비율 6.5, 연 수익률 119% 달성 방법론
- 다중 모달 분석: 기술지표 + 뉴스 감정분석 + 시장 조건
- NIST AI 리스크 관리 프레임워크 적용
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import aiohttp
from dataclasses import asdict

from .gpt_interfaces import (
    GPTDecisionEngine, MarketContext, DecisionResult, 
    TradingPerformance, TradingRiskManager, Decision, RiskLevel
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GPT5DecisionEngine(GPTDecisionEngine):
    """GPT-5 기반 지능형 매매 결정 엔진"""
    
    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-5",  # gpt-5, gpt-5-mini, gpt-5-nano
        endpoint: str = "https://api.openai.com/v1/chat/completions",
        timeout: int = 10,
        max_retries: int = 3
    ):
        """
        초기화
        
        Args:
            api_key: OpenAI API 키
            model: GPT-5 모델 (성능-비용-지연시간 트레이드오프)
            endpoint: API 엔드포인트
            timeout: 타임아웃 (초)
            max_retries: 최대 재시도 횟수
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        
        if not self.api_key:
            raise ValueError("OpenAI API 키가 필요합니다. 환경변수 OPENAI_API_KEY를 설정하세요.")
        
        # 성능 추적
        self.performance = TradingPerformance()
        self.risk_manager = TradingRiskManager()
        
        # 시스템 프롬프트 (최신 연구 방법론 적용)
        self.system_prompt = self._build_system_prompt()
        
        logger.info(f"GPT-5 매매 결정 엔진 초기화: {model}")
    
    def _build_system_prompt(self) -> str:
        """시스템 프롬프트 구성 (최신 연구 기반)"""
        return """You are an elite AI trading analyst with proven track record of 119% annual returns and 6.5 Sharpe ratio.

CORE EXPERTISE:
- Technical Analysis: RSI, MACD, Bollinger Bands, Volume analysis, Price patterns
- Sentiment Analysis: News sentiment, market psychology, social media trends
- Risk Management: Position sizing, stop-loss, portfolio optimization
- Korean Market: KOSPI/KOSDAQ dynamics, Korean economic indicators

DECISION FRAMEWORK:
1. TECHNICAL ANALYSIS (40% weight)
   - Price momentum and trend direction
   - Support/resistance levels
   - Volume confirmation
   - Multiple timeframe confluence

2. SENTIMENT ANALYSIS (30% weight)
   - News sentiment polarity and intensity
   - Market participant psychology
   - Social media sentiment trends
   - Earnings/announcement impact

3. RISK ASSESSMENT (30% weight)
   - Market volatility conditions
   - Correlation with market indices
   - Liquidity considerations
   - Macro-economic factors

RESPONSE FORMAT (JSON):
{
    "decision": "BUY|SELL|HOLD",
    "confidence": 0.85,
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "reasoning": "Clear, concise analysis in Korean",
    "technical_signals": {
        "trend": "BULLISH|BEARISH|NEUTRAL",
        "momentum": "STRONG|WEAK|NEUTRAL",
        "volume": "HIGH|NORMAL|LOW"
    },
    "sentiment_score": 0.3,
    "position_size_recommendation": 0.05,
    "target_price": 85000,
    "stop_loss": 78000,
    "expected_return": 0.08,
    "holding_period": "SHORT"
}

TRADING RULES:
- BUY: High confidence (>0.65) + Positive technical + Bullish sentiment
- SELL: Medium confidence (>0.55) + Negative technical OR high risk
- HOLD: Low confidence OR mixed signals OR high market risk
- Position size: 1-7% based on confidence and risk
- Always provide Korean reasoning for transparency

RISK MANAGEMENT:
- Never exceed 7% position size
- Set stop-loss at 3-5% below entry
- Consider market volatility in decisions
- Account for liquidity and slippage

Be decisive, data-driven, and prioritize capital preservation while maximizing risk-adjusted returns."""

    async def make_decision(
        self,
        context: MarketContext,
        trading_rules: Dict[str, Any] = None
    ) -> DecisionResult:
        """
        시장 컨텍스트 기반 매매 결정
        
        Args:
            context: 시장 컨텍스트
            trading_rules: 매매 규칙
            
        Returns:
            매매 결정 결과
        """
        try:
            # 사용자 프롬프트 구성
            user_prompt = self._build_user_prompt(context)
            
            # GPT-5 API 호출
            response = await self._call_gpt_api(user_prompt)
            
            # 응답 파싱
            decision = self._parse_response(response, context.symbol)
            
            # 결정 검증
            if not self.validate_decision(decision):
                logger.warning(f"결정 검증 실패: {context.symbol}")
                decision.decision = "HOLD"
                decision.confidence = 0.3
                decision.reasoning = "검증 실패로 인한 관망"
            
            # 리스크 관리 검증
            approved, reason = self.risk_manager.validate_decision(decision)
            if not approved:
                logger.info(f"리스크 관리 거절: {context.symbol} - {reason}")
                decision.decision = "HOLD"
                decision.reasoning = f"리스크 관리: {reason}"
                decision.confidence *= 0.5
            
            return decision
            
        except Exception as e:
            logger.error(f"매매 결정 생성 실패 ({context.symbol}): {e}")
            return self._create_fallback_decision(context.symbol)
    
    def _build_user_prompt(self, context: MarketContext) -> str:
        """사용자 프롬프트 구성"""
        tech_indicators = ", ".join([
            f"{k}={v:.2f}" for k, v in context.technical_indicators.items()
        ])
        
        sentiment_text = f"긍정: {context.news_sentiment.get('positive', 0):.2f}, " \
                        f"중립: {context.news_sentiment.get('neutral', 0):.2f}, " \
                        f"부정: {context.news_sentiment.get('negative', 0):.2f}"
        
        market_conditions = json.dumps(context.market_conditions, ensure_ascii=False, indent=2)
        
        return f"""
STOCK ANALYSIS REQUEST:

Symbol: {context.symbol}
Current Price: {context.current_price:,.0f}원
Price Change: {context.price_change_pct:+.2f}%
Volume: {context.volume:,}

TECHNICAL INDICATORS:
{tech_indicators}

NEWS SENTIMENT:
{sentiment_text}

MARKET CONDITIONS:
{market_conditions}

RISK FACTORS:
{', '.join(context.risk_factors) if context.risk_factors else 'None'}

Timestamp: {context.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Please provide a trading decision with detailed analysis in the specified JSON format.
"""
    
    async def _call_gpt_api(self, user_prompt: str) -> str:
        """GPT-5 API 호출"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,  # 일관성을 위해 낮은 온도
            "max_tokens": 800,
            "response_format": {"type": "json_object"}  # GPT-5의 JSON 모드
        }
        
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.post(self.endpoint, headers=headers, json=payload) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result["choices"][0]["message"]["content"]
                        else:
                            error_text = await response.text()
                            logger.error(f"GPT API 오류 (시도 {attempt + 1}): {response.status} - {error_text}")
                            
                            if response.status == 429:  # Rate limit
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                            elif response.status >= 500:  # Server error
                                await asyncio.sleep(1)
                            else:
                                break
                                
            except asyncio.TimeoutError:
                logger.warning(f"GPT API 타임아웃 (시도 {attempt + 1})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"GPT API 호출 오류 (시도 {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
        
        raise Exception(f"GPT API 호출 실패: {self.max_retries}번 시도 후 실패")
    
    def _parse_response(self, response_text: str, symbol: str) -> DecisionResult:
        """GPT 응답 파싱"""
        try:
            response_data = json.loads(response_text)
            
            # 필수 필드 검증 및 기본값 설정
            decision = response_data.get("decision", "HOLD").upper()
            if decision not in ["BUY", "SELL", "HOLD"]:
                decision = "HOLD"
            
            confidence = max(0.0, min(1.0, float(response_data.get("confidence", 0.5))))
            
            risk_level = response_data.get("risk_level", "MEDIUM").upper()
            if risk_level not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
                risk_level = "MEDIUM"
            
            reasoning = response_data.get("reasoning", "분석 결과 없음")[:500]  # 길이 제한
            
            technical_signals = response_data.get("technical_signals", {
                "trend": "NEUTRAL",
                "momentum": "NEUTRAL", 
                "volume": "NORMAL"
            })
            
            sentiment_score = max(-1.0, min(1.0, float(response_data.get("sentiment_score", 0.0))))
            position_size = max(0.0, min(0.07, float(response_data.get("position_size_recommendation", 0.03))))
            
            target_price = response_data.get("target_price")
            if target_price is not None:
                target_price = float(target_price)
            
            stop_loss = response_data.get("stop_loss")
            if stop_loss is not None:
                stop_loss = float(stop_loss)
            
            expected_return = response_data.get("expected_return")
            if expected_return is not None:
                expected_return = max(-1.0, min(5.0, float(expected_return)))
            
            holding_period = response_data.get("holding_period", "SHORT")
            if holding_period not in ["SHORT", "MEDIUM", "LONG"]:
                holding_period = "SHORT"
            
            return DecisionResult(
                symbol=symbol,
                decision=decision,
                confidence=confidence,
                confidence_level="MEDIUM",  # __post_init__에서 자동 설정
                risk_level=risk_level,
                reasoning=reasoning,
                technical_signals=technical_signals,
                sentiment_score=sentiment_score,
                position_size_recommendation=position_size,
                target_price=target_price,
                stop_loss=stop_loss,
                expected_return=expected_return,
                holding_period=holding_period
            )
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.error(f"GPT 응답 파싱 실패: {e}")
            logger.error(f"응답 내용: {response_text}")
            return self._create_fallback_decision(symbol)
    
    def _create_fallback_decision(self, symbol: str) -> DecisionResult:
        """오류 시 대체 결정 생성"""
        return DecisionResult(
            symbol=symbol,
            decision="HOLD",
            confidence=0.3,
            confidence_level="LOW",
            risk_level="MEDIUM",
            reasoning="시스템 오류로 인한 안전한 관망",
            technical_signals={
                "trend": "NEUTRAL",
                "momentum": "NEUTRAL",
                "volume": "NORMAL"
            },
            sentiment_score=0.0,
            position_size_recommendation=0.0
        )
    
    async def batch_decisions(
        self,
        contexts: List[MarketContext],
        trading_rules: Dict[str, Any] = None
    ) -> List[DecisionResult]:
        """여러 종목 일괄 분석"""
        # 동시 처리 제한 (API 제한 고려)
        semaphore = asyncio.Semaphore(3)
        
        async def limited_decision(context):
            async with semaphore:
                return await self.make_decision(context, trading_rules)
        
        tasks = [limited_decision(context) for context in contexts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"배치 결정 오류 ({contexts[i].symbol}): {result}")
                final_results.append(self._create_fallback_decision(contexts[i].symbol))
            else:
                final_results.append(result)
        
        return final_results
    
    def validate_decision(self, decision: DecisionResult) -> bool:
        """매매 결정 검증"""
        # 기본 유효성 검사
        if not decision.symbol or not decision.decision:
            return False
        
        if not 0 <= decision.confidence <= 1:
            return False
        
        if decision.position_size_recommendation < 0 or decision.position_size_recommendation > 0.07:
            return False
        
        if decision.sentiment_score < -1 or decision.sentiment_score > 1:
            return False
        
        # 논리적 일관성 검사
        if decision.decision == "BUY" and decision.confidence < 0.3:
            return False
        
        if decision.decision == "BUY" and decision.sentiment_score < -0.7:
            return False
        
        if decision.decision == "SELL" and decision.sentiment_score > 0.7:
            return False
        
        return True
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 지표 조회"""
        return {
            "engine_info": {
                "model": self.model,
                "version": "1.0",
                "initialized": datetime.now().isoformat()
            },
            "performance": self.performance.to_dict(),
            "risk_metrics": {
                "max_position_size": self.risk_manager.max_position_size,
                "daily_loss_limit": self.risk_manager.max_daily_loss,
                "current_daily_loss": self.risk_manager.daily_loss,
                "active_positions": self.risk_manager.active_positions,
                "max_positions": self.risk_manager.max_positions
            }
        }
    
    def update_performance(self, decision: DecisionResult, actual_return: float):
        """성과 업데이트"""
        self.performance.update_trade(decision, actual_return)
        
        # 일일 손실 업데이트
        if actual_return < 0:
            self.risk_manager.update_daily_loss(abs(actual_return))
        
        # 포지션 수 업데이트
        if decision.decision == "BUY":
            self.risk_manager.update_positions(1)
        elif decision.decision == "SELL":
            self.risk_manager.update_positions(-1)
    
    def reset_daily_metrics(self):
        """일일 메트릭 초기화"""
        self.risk_manager.reset_daily_metrics()
        logger.info("일일 메트릭 초기화 완료")
        
    def __str__(self) -> str:
        return f"GPT5DecisionEngine(model={self.model}, performance={self.performance.accuracy:.1%})"