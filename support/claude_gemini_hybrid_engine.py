#!/usr/bin/env python3
"""
Claude + Gemini 하이브리드 매매 결정 엔진
- 모든 API 키는 오직 Register_Key.md에서만 관리
- Fallback 시스템 없음 (실패시 즉시 HOLD)
- 투명하고 단순한 아키텍처

**아키텍처:**
1. Claude: 정성적 펀더멘털 분석 (뉴스, 공시, 감정 분석)
2. Gemini: 정량적 기술적 분석 (차트, 지표, 실시간 데이터)
3. 융합 로직: 두 분석 결과 가중 평균으로 최종 결정
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import asdict

from .gpt_interfaces import (
    GPTDecisionEngine, MarketContext, DecisionResult, 
    TradingPerformance, TradingRiskManager
)
from .ai_api_manager import get_ai_api_manager
from .clean_console_logger import clean_log

logger = logging.getLogger(__name__)

class ClaudeGeminiHybridEngine(GPTDecisionEngine):
    """Claude + Gemini 하이브리드 매매 결정 엔진"""
    
    def __init__(self):
        """초기화 - Register_Key.md에서 설정 로드"""
        self.engine_name = "Claude+Gemini 하이브리드 엔진"
        
        # AI API 관리자 초기화
        self.ai_manager = get_ai_api_manager()
        
        # 설정 검증
        if not self.ai_manager.validate_hybrid_requirements():
            raise ValueError(
                "하이브리드 모드 필요 조건이 충족되지 않았습니다.\n"
                "메뉴 3. Setup → 1. Register_Key에서 Claude와 Gemini API 키를 모두 설정하세요."
            )
        
        # 설정 로드
        self.claude_config = self.ai_manager.get_claude_config()
        self.gemini_config = self.ai_manager.get_gemini_config()
        self.hybrid_config = self.ai_manager.get_hybrid_config()
        
        # 성능 추적
        self.performance = TradingPerformance()
        self.risk_manager = TradingRiskManager()
        
        # 결정 히스토리
        self.decision_history: List[Dict[str, Any]] = []
        
        clean_log(f"하이브리드 엔진 초기화: Claude({self.claude_config['model']}) + Gemini({self.gemini_config['model']})", "SUCCESS")
        
    async def make_decision(self, context: MarketContext, trading_rules: Dict[str, Any] = None) -> DecisionResult:
        """
        하이브리드 매매 결정 생성
        
        Args:
            context: 시장 컨텍스트
            trading_rules: 매매 규칙
            
        Returns:
            매매 결정 결과
        """
        try:
            start_time = datetime.now()
            
            # 병렬로 두 AI 분석 실행
            claude_task = self._analyze_with_claude(context)
            gemini_task = self._analyze_with_gemini(context)
            
            # 둘 다 성공해야 진행 (하나라도 실패시 예외 발생)
            claude_result, gemini_result = await asyncio.gather(
                claude_task, gemini_task,
                return_exceptions=False  # 실패시 즉시 예외
            )
            
            # 결과 융합
            decision = self._fuse_decisions(claude_result, gemini_result, context)
            
            # 처리 시간 기록
            processing_time = (datetime.now() - start_time).total_seconds()
            decision.metadata = decision.metadata or {}
            decision.metadata['processing_time'] = processing_time
            decision.metadata['claude_confidence'] = claude_result.get('confidence', 0.0)
            decision.metadata['gemini_confidence'] = gemini_result.get('confidence', 0.0)
            
            # 히스토리 기록
            self._record_decision(decision, claude_result, gemini_result)
            
            return decision
            
        except Exception as e:
            error_msg = f"하이브리드 엔진 분석 실패: {str(e)}"
            logger.error(error_msg)
            clean_log(f"[HYBRID_ENGINE] ❌ {error_msg}", "ERROR")
            
            # 안전 모드 결정 반환
            return self._create_safe_decision(context, error_msg)
    
    async def _analyze_with_claude(self, context: MarketContext) -> Dict[str, Any]:
        """Claude를 이용한 정성적 펀더멘털 분석"""
        
        # Claude 전용 프롬프트 (정성적 분석 특화)
        prompt = self._build_claude_prompt(context)
        
        # Claude API 호출
        headers = {
            "x-api-key": self.claude_config['api_key'],
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": self.claude_config['model'],
            "max_tokens": self.claude_config['max_tokens'],
            "temperature": self.claude_config['temperature'],
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        timeout = aiohttp.ClientTimeout(total=self.hybrid_config['timeout_seconds'])
        
        for attempt in range(self.hybrid_config['max_retries']):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=headers,
                        json=payload
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            content = result['content'][0]['text']
                            
                            # JSON 파싱
                            analysis = json.loads(content)
                            analysis['source'] = 'claude'
                            analysis['attempt'] = attempt + 1
                            
                            return analysis
                        else:
                            error_text = await response.text()
                            raise Exception(f"Claude API 오류 {response.status}: {error_text}")
                            
            except asyncio.TimeoutError:
                if attempt < self.hybrid_config['max_retries'] - 1:
                    await asyncio.sleep(1)
                    continue
                raise Exception(f"Claude API 타임아웃 (시도: {attempt + 1})")
            
            except Exception as e:
                if attempt < self.hybrid_config['max_retries'] - 1:
                    await asyncio.sleep(1)
                    continue
                raise Exception(f"Claude API 호출 실패: {e}")
        
        raise Exception(f"Claude API {self.hybrid_config['max_retries']}회 시도 모두 실패")
    
    async def _analyze_with_gemini(self, context: MarketContext) -> Dict[str, Any]:
        """Gemini를 이용한 정량적 기술적 분석"""
        
        # Gemini 전용 프롬프트 (기술적 분석 특화)
        prompt = self._build_gemini_prompt(context)
        
        # Gemini API 호출
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_config['model']}:generateContent"
        params = {"key": self.gemini_config['api_key']}
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": self.gemini_config['temperature'],
                "maxOutputTokens": self.gemini_config['max_tokens']
            }
        }
        
        timeout = aiohttp.ClientTimeout(total=self.hybrid_config['timeout_seconds'])
        
        for attempt in range(self.hybrid_config['max_retries']):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, params=params, json=payload, timeout=timeout) as response:
                        if response.status == 200:
                            result = await response.json()
                            content = result['candidates'][0]['content']['parts'][0]['text']
                            
                            # JSON 파싱
                            analysis = json.loads(content)
                            analysis['source'] = 'gemini'
                            analysis['attempt'] = attempt + 1
                            
                            return analysis
                        else:
                            error_text = await response.text()
                            raise Exception(f"Gemini API 오류 {response.status}: {error_text}")
                            
            except asyncio.TimeoutError:
                if attempt < self.hybrid_config['max_retries'] - 1:
                    await asyncio.sleep(1)
                    continue
                raise Exception(f"Gemini API 타임아웃 (시도: {attempt + 1})")
            
            except Exception as e:
                if attempt < self.hybrid_config['max_retries'] - 1:
                    await asyncio.sleep(1)
                    continue
                raise Exception(f"Gemini API 호출 실패: {e}")
        
        raise Exception(f"Gemini API {self.hybrid_config['max_retries']}회 시도 모두 실패")
    
    def _build_claude_prompt(self, context: MarketContext) -> str:
        """Claude용 정성적 분석 프롬프트 생성"""
        return f"""당신은 한국 주식시장의 펀더멘털 분석 전문가입니다.

**종목 정보:**
- 종목코드: {context.symbol}
- 현재가: {context.current_price:,.0f}원
- 등락률: {context.price_change_pct:+.2f}%

**뉴스 감정 분석:**
- 긍정: {context.news_sentiment.get('positive', 0):.2f}
- 중립: {context.news_sentiment.get('neutral', 0):.2f} 
- 부정: {context.news_sentiment.get('negative', 0):.2f}

**시장 상황:**
{json.dumps(context.market_conditions, ensure_ascii=False)}

**분석 요청:**
1. 뉴스와 시장 감정을 바탕으로 이 종목의 펀더멘털 상태 평가
2. 급등/급락의 근본 원인 분석
3. 지속 가능성 평가
4. 리스크 요인 식별

다음 JSON 형태로만 응답하세요:
{{
    "decision": "BUY|SELL|HOLD",
    "confidence": 0.75,
    "fundamental_score": 0.8,
    "sustainability": "HIGH|MEDIUM|LOW",
    "risk_factors": ["위험요인1", "위험요인2"],
    "reasoning": "한국어로 상세 분석 내용"
}}"""

    def _build_gemini_prompt(self, context: MarketContext) -> str:
        """Gemini용 정량적 분석 프롬프트 생성"""
        tech_indicators = ", ".join([f"{k}={v:.2f}" for k, v in context.technical_indicators.items()])
        
        return f"""당신은 한국 주식시장의 기술적 분석 전문가입니다.

**종목 정보:**
- 종목코드: {context.symbol}
- 현재가: {context.current_price:,.0f}원
- 거래량: {context.volume:,}
- 등락률: {context.price_change_pct:+.2f}%

**기술적 지표:**
{tech_indicators}

**분석 요청:**
1. 기술적 지표를 바탕으로 현재 추세 분석
2. 매수/매도 신호 강도 평가
3. 지지/저항 수준 분석
4. 단기 모멘텀 평가

다음 JSON 형태로만 응답하세요:
{{
    "decision": "BUY|SELL|HOLD",
    "confidence": 0.85,
    "technical_score": 0.7,
    "trend": "BULLISH|BEARISH|NEUTRAL",
    "momentum": "STRONG|WEAK|NEUTRAL",
    "entry_timing": "EXCELLENT|GOOD|POOR",
    "reasoning": "한국어로 기술적 분석 내용"
}}"""

    def _fuse_decisions(self, claude_result: Dict, gemini_result: Dict, context: MarketContext) -> DecisionResult:
        """Claude와 Gemini 분석 결과 융합"""
        
        # 가중치 적용 신뢰도 계산
        claude_weight = self.hybrid_config['claude_weight']
        gemini_weight = self.hybrid_config['gemini_weight']
        
        weighted_confidence = (
            claude_result['confidence'] * claude_weight +
            gemini_result['confidence'] * gemini_weight
        )
        
        # 점수 융합
        fundamental_score = claude_result.get('fundamental_score', 0.5)
        technical_score = gemini_result.get('technical_score', 0.5)
        
        combined_score = fundamental_score * claude_weight + technical_score * gemini_weight
        
        # 결정 융합 로직
        claude_decision = claude_result['decision']
        gemini_decision = gemini_result['decision']
        
        if claude_decision == gemini_decision:
            # 일치하는 경우
            final_decision = claude_decision
        elif claude_decision == 'HOLD' or gemini_decision == 'HOLD':
            # 하나라도 HOLD면 안전하게 HOLD
            final_decision = 'HOLD'
            weighted_confidence *= 0.7  # 신뢰도 감소
        elif (claude_decision == 'BUY' and gemini_decision == 'SELL') or \
             (claude_decision == 'SELL' and gemini_decision == 'BUY'):
            # 상반된 경우 보수적으로 HOLD
            final_decision = 'HOLD'
            weighted_confidence *= 0.5  # 신뢰도 크게 감소
        else:
            # 기타 경우 높은 신뢰도 쪽 선택
            if claude_result['confidence'] > gemini_result['confidence']:
                final_decision = claude_decision
            else:
                final_decision = gemini_decision
        
        # 융합된 분석 내용
        combined_reasoning = f"""
🤖 Claude 펀더멘털 분석:
{claude_result.get('reasoning', 'N/A')}

🔍 Gemini 기술적 분석:  
{gemini_result.get('reasoning', 'N/A')}

⚖️ 하이브리드 결론:
- Claude 신뢰도: {claude_result['confidence']:.2f}
- Gemini 신뢰도: {gemini_result['confidence']:.2f}
- 가중 평균 신뢰도: {weighted_confidence:.2f}
- 종합 점수: {combined_score:.2f}
"""
        
        return DecisionResult(
            symbol=context.symbol,
            decision=final_decision,
            confidence=weighted_confidence,
            confidence_level="MEDIUM",
            risk_level="MEDIUM",
            reasoning=combined_reasoning.strip(),
            technical_signals={
                "claude_decision": claude_decision,
                "gemini_decision": gemini_decision,
                "fundamental_score": fundamental_score,
                "technical_score": technical_score
            },
            sentiment_score=(claude_result.get('fundamental_score', 0.5) + 
                           gemini_result.get('technical_score', 0.5)) / 2,
            position_size_recommendation=min(0.07, combined_score * 0.1),
            metadata={
                "engine": "Claude+Gemini Hybrid",
                "claude_model": self.claude_config['model'],
                "gemini_model": self.gemini_config['model'],
                "claude_weight": claude_weight,
                "gemini_weight": gemini_weight
            }
        )
    
    def _create_safe_decision(self, context: MarketContext, error_msg: str) -> DecisionResult:
        """안전 모드 결정 생성 (API 실패시)"""
        return DecisionResult(
            symbol=context.symbol,
            decision="HOLD",
            confidence=0.0,
            confidence_level="LOW",
            risk_level="HIGH",
            reasoning=f"하이브리드 엔진 오류로 안전 모드 진입: {error_msg}",
            technical_signals={"error": True},
            sentiment_score=0.0,
            position_size_recommendation=0.0,
            metadata={"engine": "Safe Mode", "error": error_msg}
        )
    
    def _record_decision(self, decision: DecisionResult, claude_result: Dict, gemini_result: Dict):
        """결정 히스토리 기록"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "symbol": decision.symbol,
            "decision": decision.decision,
            "confidence": decision.confidence,
            "claude_decision": claude_result['decision'],
            "claude_confidence": claude_result['confidence'],
            "gemini_decision": gemini_result['decision'],
            "gemini_confidence": gemini_result['confidence']
        }
        
        self.decision_history.append(record)
        
        # 최대 100개 기록만 유지
        if len(self.decision_history) > 100:
            self.decision_history = self.decision_history[-100:]
    
    def get_engine_info(self) -> Dict[str, Any]:
        """엔진 정보 반환"""
        availability = self.ai_manager.get_available_engines()
        
        return {
            "name": self.engine_name,
            "version": "1.0",
            "type": "hybrid",
            "claude_model": self.claude_config['model'],
            "gemini_model": self.gemini_config['model'],
            "hybrid_enabled": availability['hybrid'],
            "claude_weight": self.hybrid_config['claude_weight'],
            "gemini_weight": self.hybrid_config['gemini_weight'],
            "decision_count": len(self.decision_history)
        }
    
    def get_decision_history(self) -> List[Dict[str, Any]]:
        """결정 히스토리 반환"""
        return self.decision_history.copy()
    
    def validate_decision(self, decision: DecisionResult) -> bool:
        """결정 유효성 검증"""
        # 기본 유효성 검사
        if not decision.symbol or decision.decision not in ["BUY", "SELL", "HOLD"]:
            return False
        
        if not 0 <= decision.confidence <= 1:
            return False
        
        if decision.position_size_recommendation < 0 or decision.position_size_recommendation > 0.07:
            return False
        
        return True