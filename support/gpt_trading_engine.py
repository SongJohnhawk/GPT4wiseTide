#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT Trading Decision Engine
GPT-5 기반 거래 결정 엔진 - 기존 알고리즘 대체

핵심 기능:
- GPT-5 API를 통한 거래 신호 생성 (BUY/SELL/HOLD)
- David Paul 거래량 검증 통합
- 7% 수익목표, -1.5% 손절점 적용
- VI(변동성완화장치) 처리 로직
- API 비용 최적화 (캐싱, 배치 처리)
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import hashlib

try:
    import openai
except ImportError:
    openai = None

from support.david_paul_volume_validator import get_david_paul_validator

logger = logging.getLogger(__name__)

@dataclass
class TradingDecision:
    """GPT 거래 결정 결과"""
    signal: str                # 'BUY', 'SELL', 'HOLD'
    confidence: float          # 신뢰도 (0.0-1.0)
    reasoning: str            # GPT 판단 근거
    target_price: Optional[float] = None    # 목표가 (매수시)
    stop_loss: Optional[float] = None       # 손절가
    position_size_ratio: float = 0.07       # 포지션 크기 비율 (7%)
    risk_level: str = 'MEDIUM'              # 리스크 레벨
    volume_validation: Optional[Dict] = None # David Paul 검증 결과
    api_cost: float = 0.0                   # API 호출 비용 (USD)

class GPTTradingEngine:
    """GPT 기반 거래 결정 엔진"""
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        """
        초기화
        
        Args:
            api_key: OpenAI API 키
            model: 사용할 GPT 모델 (gpt-4o 권장)
        """
        self.api_key = api_key
        self.model = model
        self.client = None
        
        # 거래 규칙 (사용자 요구사항)
        self.PROFIT_TARGET = 0.07   # 7% 수익목표
        self.STOP_LOSS = 0.015      # -1.5% 손절점
        self.MAX_POSITION_SIZE = 0.07  # 7% 포지션 크기
        
        # David Paul 검증기
        self.volume_validator = get_david_paul_validator()
        
        # 캐싱 시스템 (API 비용 절약)
        self.decision_cache = {}
        self.cache_ttl = 300  # 5분 캐시
        
        # API 사용량 추적
        self.api_calls_today = 0
        self.api_cost_today = 0.0
        self.last_reset_date = datetime.now().date()
        
        # 성능 메트릭
        self.response_times = []
        self.success_rate = {'total': 0, 'success': 0}
        
        self._initialize_openai_client()
        
        logger.info(f"GPT Trading Engine 초기화 완료 (모델: {model})")
        logger.info(f"거래 규칙: 수익목표 {self.PROFIT_TARGET*100}%, 손절점 {self.STOP_LOSS*100}%")
    
    def _initialize_openai_client(self):
        """OpenAI 클라이언트 초기화"""
        if not openai:
            logger.error("OpenAI 라이브러리가 설치되지 않음. pip install openai 실행 필요")
            return
            
        if not self.api_key:
            logger.warning("OpenAI API 키가 설정되지 않음. 환경변수 또는 설정 파일 확인 필요")
            return
            
        try:
            openai.api_key = self.api_key
            self.client = openai.OpenAI(api_key=self.api_key)
            logger.info("OpenAI 클라이언트 초기화 완료")
        except Exception as e:
            logger.error(f"OpenAI 클라이언트 초기화 실패: {e}")
    
    async def make_trading_decision(self, symbol: str, stock_data: Dict[str, Any], 
                                  position_info: Dict[str, Any] = None) -> TradingDecision:
        """
        거래 결정 생성
        
        Args:
            symbol: 종목 코드
            stock_data: 종목 현재 데이터
            position_info: 기존 포지션 정보 (있는 경우)
            
        Returns:
            TradingDecision: 거래 결정 결과
        """
        start_time = time.time()
        
        try:
            # 1. 일일 API 사용량 초기화
            self._reset_daily_counters()
            
            # 2. 입력 데이터 검증
            if not self._validate_input_data(stock_data):
                return self._create_error_decision("입력 데이터 부족")
            
            # 3. 캐시 확인
            cache_key = self._generate_cache_key(symbol, stock_data, position_info)
            cached_decision = self._get_cached_decision(cache_key)
            if cached_decision:
                logger.debug(f"{symbol}: 캐시된 결정 사용")
                return cached_decision
            
            # 4. David Paul 거래량 검증
            volume_validation = self.volume_validator.validate_price_volume_relationship(stock_data)
            
            # 5. VI(변동성완화장치) 체크
            vi_status = self._check_vi_status(stock_data)
            if vi_status['is_vi_triggered']:
                return self._create_vi_decision(symbol, vi_status, volume_validation)
            
            # 6. GPT 호출 및 결정 생성
            gpt_response = await self._call_gpt_api(symbol, stock_data, position_info, volume_validation)
            
            if not gpt_response:
                return self._create_error_decision("GPT API 호출 실패")
            
            # 7. 결정 생성 및 검증
            decision = self._parse_gpt_response(gpt_response, stock_data, volume_validation, position_info)
            
            # 8. 안전장치 적용
            decision = self._apply_safety_checks(decision, stock_data, position_info)
            
            # 9. 캐시 저장
            self._cache_decision(cache_key, decision)
            
            # 10. 성능 메트릭 업데이트
            response_time = time.time() - start_time
            self.response_times.append(response_time)
            self.success_rate['total'] += 1
            self.success_rate['success'] += 1
            
            logger.info(f"{symbol}: GPT 결정 완료 - {decision.signal} (신뢰도: {decision.confidence:.2f}, "
                       f"응답시간: {response_time:.2f}초)")
            
            return decision
            
        except Exception as e:
            logger.error(f"{symbol} GPT 거래 결정 오류: {e}")
            self.success_rate['total'] += 1
            return self._create_error_decision(f"처리 오류: {str(e)[:50]}")
    
    def _validate_input_data(self, stock_data: Dict[str, Any]) -> bool:
        """입력 데이터 유효성 검증"""
        required_fields = ['current_price', 'volume', 'high_price', 'low_price', 'open_price']
        
        for field in required_fields:
            if field not in stock_data or stock_data[field] <= 0:
                logger.warning(f"필수 데이터 부족: {field}")
                return False
        
        # 가격 논리 검증
        current = float(stock_data['current_price'])
        high = float(stock_data['high_price'])
        low = float(stock_data['low_price'])
        
        if not (low <= current <= high):
            logger.warning(f"가격 논리 오류: low({low}) <= current({current}) <= high({high})")
            return False
            
        return True
    
    def _check_vi_status(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """VI(변동성완화장치) 상태 체크"""
        current_price = float(stock_data['current_price'])
        open_price = float(stock_data.get('open_price', current_price))
        
        # 가격 변화율 계산
        if open_price > 0:
            change_rate = abs((current_price - open_price) / open_price)
        else:
            change_rate = 0
        
        # VI 발동 임계값 (일반적으로 ±10%)
        vi_threshold = 0.10
        is_vi_triggered = change_rate >= vi_threshold
        
        # VI 관련 추가 지표
        volume_spike = stock_data.get('volume', 0) > stock_data.get('avg_volume', 1) * 3
        
        return {
            'is_vi_triggered': is_vi_triggered,
            'change_rate': change_rate,
            'vi_threshold': vi_threshold,
            'volume_spike': volume_spike,
            'risk_level': 'CRITICAL' if is_vi_triggered else 'NORMAL'
        }
    
    async def _call_gpt_api(self, symbol: str, stock_data: Dict[str, Any], 
                           position_info: Dict[str, Any], volume_validation) -> Optional[Dict]:
        """GPT API 호출"""
        if not self.client:
            logger.error("OpenAI 클라이언트가 초기화되지 않음")
            return None
        
        try:
            # 프롬프트 생성
            prompt = self._create_trading_prompt(symbol, stock_data, position_info, volume_validation)
            
            # API 호출
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3,  # 일관성을 위해 낮은 값
                response_format={"type": "json_object"}
            )
            
            # API 사용량 추적
            self._track_api_usage(response)
            
            # 응답 파싱
            content = response.choices[0].message.content
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"GPT 응답 JSON 파싱 오류: {e}")
            return None
        except Exception as e:
            logger.error(f"GPT API 호출 오류: {e}")
            return None
    
    def _get_system_prompt(self) -> str:
        """GPT 시스템 프롬프트"""
        return f"""당신은 한국 주식시장 전문 단타매매 시스템입니다.

핵심 원칙:
1. 수익목표: {self.PROFIT_TARGET*100}% (도달시 무조건 매도)
2. 손절점: {self.STOP_LOSS*100}% (도달시 무조건 매도)
3. David Paul 거래량 검증 결과를 반드시 고려
4. VI(변동성완화장치) 발동시 즉시 매도
5. 위험도가 높으면 보수적 판단

응답 형식 (JSON):
{{
    "signal": "BUY|SELL|HOLD",
    "confidence": 0.0-1.0,
    "reasoning": "판단 근거 (한국어, 100자 내외)",
    "target_price": 예상 목표가 (매수시에만),
    "risk_assessment": "LOW|MEDIUM|HIGH"
}}

중요: 반드시 JSON 형식으로만 응답하세요."""
    
    def _create_trading_prompt(self, symbol: str, stock_data: Dict[str, Any], 
                              position_info: Dict[str, Any], volume_validation) -> str:
        """거래 결정용 프롬프트 생성"""
        current_price = stock_data['current_price']
        volume = stock_data['volume']
        change_rate = stock_data.get('change_rate', 0)
        
        # 기본 정보
        prompt = f"""종목분석 요청:
종목코드: {symbol}
현재가: {current_price:,}원
거래량: {volume:,}주
등락률: {change_rate:+.2f}%
고가: {stock_data['high_price']:,}원
저가: {stock_data['low_price']:,}원
시가: {stock_data['open_price']:,}원

David Paul 거래량 검증:
- 검증결과: {volume_validation.signal_type}
- 신뢰도: {volume_validation.confidence:.2f}
- 판단근거: {volume_validation.reason}
- 리스크: {volume_validation.risk_level}
"""
        
        # 포지션 정보 (보유중인 경우)
        if position_info:
            avg_price = position_info.get('avg_price', 0)
            quantity = position_info.get('quantity', 0)
            profit_rate = ((current_price - avg_price) / avg_price) if avg_price > 0 else 0
            
            prompt += f"""
현재 포지션:
- 평균단가: {avg_price:,}원
- 보유수량: {quantity:,}주
- 수익률: {profit_rate*100:+.2f}%
- 수익목표 도달여부: {'YES' if profit_rate >= self.PROFIT_TARGET else 'NO'}
- 손절선 도달여부: {'YES' if profit_rate <= -self.STOP_LOSS else 'NO'}
"""
        
        prompt += f"""
거래 규칙:
- 수익목표: {self.PROFIT_TARGET*100}% (도달시 즉시 매도)
- 손절점: -{self.STOP_LOSS*100}% (도달시 즉시 매도)
- 포지션 크기: 계좌의 {self.MAX_POSITION_SIZE*100}%

지금 이 종목에 대한 거래 결정을 내려주세요."""
        
        return prompt
    
    def _parse_gpt_response(self, gpt_response: Dict, stock_data: Dict, 
                           volume_validation, position_info: Dict = None) -> TradingDecision:
        """GPT 응답 파싱 및 TradingDecision 생성"""
        try:
            signal = gpt_response.get('signal', 'HOLD').upper()
            confidence = float(gpt_response.get('confidence', 0.5))
            reasoning = gpt_response.get('reasoning', 'GPT 분석 결과')
            risk_assessment = gpt_response.get('risk_assessment', 'MEDIUM')
            
            # 신호 검증
            if signal not in ['BUY', 'SELL', 'HOLD']:
                signal = 'HOLD'
                confidence = 0.3
                reasoning = f"유효하지 않은 신호 감지 - 보류로 변경: {reasoning}"
            
            # 신뢰도 범위 체크
            confidence = max(0.0, min(1.0, confidence))
            
            # 목표가 계산 (매수시)
            target_price = None
            stop_loss = None
            current_price = float(stock_data['current_price'])
            
            if signal == 'BUY':
                target_price = current_price * (1 + self.PROFIT_TARGET)
                stop_loss = current_price * (1 - self.STOP_LOSS)
            elif signal == 'SELL' and position_info:
                avg_price = position_info.get('avg_price', current_price)
                stop_loss = avg_price * (1 - self.STOP_LOSS)
            
            return TradingDecision(
                signal=signal,
                confidence=confidence,
                reasoning=reasoning,
                target_price=target_price,
                stop_loss=stop_loss,
                position_size_ratio=self.MAX_POSITION_SIZE,
                risk_level=risk_assessment,
                volume_validation=volume_validation.__dict__,
                api_cost=self._estimate_api_cost()
            )
            
        except Exception as e:
            logger.error(f"GPT 응답 파싱 오류: {e}")
            return self._create_error_decision(f"응답 파싱 실패: {str(e)[:30]}")
    
    def _apply_safety_checks(self, decision: TradingDecision, stock_data: Dict, 
                           position_info: Dict = None) -> TradingDecision:
        """안전장치 적용"""
        current_price = float(stock_data['current_price'])
        
        # 1. 포지션 보유시 수익목표/손절점 강제 적용
        if position_info and position_info.get('avg_price'):
            avg_price = float(position_info['avg_price'])
            profit_rate = (current_price - avg_price) / avg_price
            
            # 수익목표 달성시 강제 매도
            if profit_rate >= self.PROFIT_TARGET:
                decision.signal = 'SELL'
                decision.confidence = 0.95
                decision.reasoning = f"수익목표 {self.PROFIT_TARGET*100}% 달성 - 강제 매도"
                decision.risk_level = 'LOW'
            
            # 손절점 달성시 강제 매도
            elif profit_rate <= -self.STOP_LOSS:
                decision.signal = 'SELL'
                decision.confidence = 0.95
                decision.reasoning = f"손절점 -{self.STOP_LOSS*100}% 도달 - 강제 매도"
                decision.risk_level = 'HIGH'
        
        # 2. David Paul 검증 결과 반영
        if hasattr(decision, 'volume_validation') and decision.volume_validation:
            vol_validation = decision.volume_validation
            
            # NON_VALIDATION 신호시 신뢰도 감소
            if vol_validation.get('signal_type') == 'NON_VALIDATION':
                decision.confidence *= 0.7
                decision.reasoning += " [거래량 비검증]"
            
            # DIVERGENCE 신호시 보수적 접근
            elif vol_validation.get('divergence_detected'):
                if decision.signal == 'BUY':
                    decision.confidence *= 0.6
                    decision.reasoning += " [다이버전스 감지]"
        
        # 3. 극단적 변동시 신뢰도 조정
        change_rate = abs(stock_data.get('change_rate', 0))
        if change_rate > 5.0:  # 5% 이상 변동
            decision.confidence *= 0.8
            decision.reasoning += f" [큰 변동: {change_rate:.1f}%]"
        
        # 4. 최종 신뢰도 임계값 적용
        if decision.confidence < 0.3:
            decision.signal = 'HOLD'
            decision.reasoning += " [낮은 신뢰도로 보류]"
        
        return decision
    
    def _create_error_decision(self, error_msg: str) -> TradingDecision:
        """오류 상황 결정 생성"""
        return TradingDecision(
            signal='HOLD',
            confidence=0.0,
            reasoning=f"오류: {error_msg}",
            risk_level='HIGH'
        )
    
    def _create_vi_decision(self, symbol: str, vi_status: Dict, volume_validation) -> TradingDecision:
        """VI 발동시 결정 생성"""
        return TradingDecision(
            signal='SELL' if vi_status['change_rate'] > 0.1 else 'HOLD',
            confidence=0.9,
            reasoning=f"VI 발동 감지 (변동률: {vi_status['change_rate']*100:.1f}%)",
            risk_level='CRITICAL',
            volume_validation=volume_validation.__dict__
        )
    
    # 캐싱 관련 메서드들
    def _generate_cache_key(self, symbol: str, stock_data: Dict, position_info: Dict = None) -> str:
        """캐시 키 생성"""
        key_data = {
            'symbol': symbol,
            'price': stock_data['current_price'],
            'volume': stock_data['volume'],
            'change_rate': stock_data.get('change_rate', 0),
            'has_position': bool(position_info)
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cached_decision(self, cache_key: str) -> Optional[TradingDecision]:
        """캐시된 결정 조회"""
        if cache_key in self.decision_cache:
            cached_data = self.decision_cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.cache_ttl:
                return cached_data['decision']
            else:
                del self.decision_cache[cache_key]
        return None
    
    def _cache_decision(self, cache_key: str, decision: TradingDecision):
        """결정 캐싱"""
        self.decision_cache[cache_key] = {
            'decision': decision,
            'timestamp': time.time()
        }
    
    # API 사용량 및 비용 관리
    def _reset_daily_counters(self):
        """일일 카운터 초기화"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.api_calls_today = 0
            self.api_cost_today = 0.0
            self.last_reset_date = today
            logger.info(f"일일 API 사용량 초기화: {today}")
    
    def _track_api_usage(self, response):
        """API 사용량 추적"""
        if hasattr(response, 'usage'):
            self.api_calls_today += 1
            # GPT-4 대략적인 비용 계산 (실제는 토큰 기반)
            estimated_cost = 0.002  # $0.002 per call 추정
            self.api_cost_today += estimated_cost
    
    def _estimate_api_cost(self) -> float:
        """API 호출 예상 비용"""
        return 0.002  # GPT-4 기준 대략적인 호출당 비용
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 반환"""
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        success_rate = (self.success_rate['success'] / self.success_rate['total'] * 100) if self.success_rate['total'] > 0 else 0
        
        return {
            'api_calls_today': self.api_calls_today,
            'api_cost_today': self.api_cost_today,
            'avg_response_time': avg_response_time,
            'success_rate': success_rate,
            'cache_hit_rate': len(self.decision_cache),
            'model_used': self.model
        }

# 전역 인스턴스 (싱글톤)
_gpt_engine_instance = None

def get_gpt_trading_engine(api_key: str = None) -> GPTTradingEngine:
    """GPT Trading Engine 인스턴스 반환 (싱글톤)"""
    global _gpt_engine_instance
    if _gpt_engine_instance is None:
        _gpt_engine_instance = GPTTradingEngine(api_key=api_key)
    return _gpt_engine_instance

def reset_gpt_engine():
    """GPT Engine 인스턴스 초기화 (테스트용)"""
    global _gpt_engine_instance
    _gpt_engine_instance = None

if __name__ == "__main__":
    # 테스트 코드
    import asyncio
    
    async def test_gpt_engine():
        engine = get_gpt_trading_engine()
        
        # 샘플 데이터
        test_stock_data = {
            'current_price': 50000,
            'volume': 200000,
            'high_price': 52000,
            'low_price': 48000,
            'open_price': 49000,
            'change_rate': 2.04
        }
        
        decision = await engine.make_trading_decision('005930', test_stock_data)
        print(f"테스트 결과: {decision.signal} (신뢰도: {decision.confidence:.2f})")
        print(f"근거: {decision.reasoning}")
        print(f"목표가: {decision.target_price}")
        print(f"손절가: {decision.stop_loss}")
    
    # asyncio.run(test_gpt_engine())