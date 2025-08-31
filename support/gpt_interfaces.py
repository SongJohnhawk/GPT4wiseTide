#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT 기반 매매 결정 인터페이스
- GPT-5 API 통합을 위한 표준 인터페이스
- 최신 연구 결과 적용 (StockGPT 샤프비율 6.5, 연 수익률 119% 달성 방법론)
- 다중 모달 데이터 통합 (기술지표 + 뉴스 감정분석)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Protocol, Dict, Any, Optional, List
from datetime import datetime
import json

# 매매 결정 타입
Decision = Literal["BUY", "SELL", "HOLD"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ConfidenceLevel = Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"]

@dataclass
class MarketContext:
    """시장 컨텍스트 데이터"""
    symbol: str
    current_price: float
    price_change_pct: float
    volume: int
    technical_indicators: Dict[str, float]
    news_sentiment: Dict[str, float]  # positive, neutral, negative scores
    market_conditions: Dict[str, Any]
    risk_factors: List[str]
    timestamp: datetime

@dataclass
class DecisionResult:
    """GPT 매매 결정 결과"""
    symbol: str
    decision: Decision
    confidence: float  # 0.0 - 1.0
    confidence_level: ConfidenceLevel
    risk_level: RiskLevel
    reasoning: str
    technical_signals: Dict[str, str]  # 기술적 분석 신호
    sentiment_score: float  # -1.0 (매우 부정) ~ 1.0 (매우 긍정)
    position_size_recommendation: float  # 0.0 - 1.0 (권장 포지션 크기)
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    expected_return: Optional[float] = None
    holding_period: Optional[str] = None  # "SHORT", "MEDIUM", "LONG"
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        
        # 신뢰도 레벨 자동 설정
        if self.confidence >= 0.85:
            self.confidence_level = "VERY_HIGH"
        elif self.confidence >= 0.7:
            self.confidence_level = "HIGH"
        elif self.confidence >= 0.5:
            self.confidence_level = "MEDIUM"
        elif self.confidence >= 0.3:
            self.confidence_level = "LOW"
        else:
            self.confidence_level = "VERY_LOW"
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "symbol": self.symbol,
            "decision": self.decision,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level,
            "risk_level": self.risk_level,
            "reasoning": self.reasoning,
            "technical_signals": self.technical_signals,
            "sentiment_score": self.sentiment_score,
            "position_size_recommendation": self.position_size_recommendation,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "expected_return": self.expected_return,
            "holding_period": self.holding_period,
            "timestamp": self.timestamp.isoformat()
        }

class GPTDecisionEngine(Protocol):
    """GPT 매매 결정 엔진 인터페이스"""
    
    async def make_decision(
        self, 
        context: MarketContext, 
        trading_rules: Dict[str, Any] = None
    ) -> DecisionResult:
        """
        시장 컨텍스트를 바탕으로 매매 결정 생성
        
        Args:
            context: 시장 컨텍스트 (가격, 지표, 뉴스 등)
            trading_rules: 매매 규칙 (리스크 한도, 포지션 크기 등)
        
        Returns:
            매매 결정 결과
        """
        ...
    
    async def batch_decisions(
        self, 
        contexts: List[MarketContext],
        trading_rules: Dict[str, Any] = None
    ) -> List[DecisionResult]:
        """
        여러 종목에 대한 일괄 매매 결정
        
        Args:
            contexts: 시장 컨텍스트 리스트
            trading_rules: 매매 규칙
        
        Returns:
            매매 결정 결과 리스트
        """
        ...
    
    def validate_decision(self, decision: DecisionResult) -> bool:
        """
        매매 결정 검증
        
        Args:
            decision: 검증할 결정
        
        Returns:
            유효성 여부
        """
        ...
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        성능 지표 조회
        
        Returns:
            성능 지표 딕셔너리
        """
        ...

@dataclass
class TradingPerformance:
    """매매 성과 추적"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_holding_period: float = 0.0  # hours
    avg_confidence: float = 0.0
    accuracy: float = 0.0  # 예측 정확도
    
    def win_rate(self) -> float:
        """승률 계산"""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades
    
    def update_trade(self, decision: DecisionResult, actual_return: float):
        """거래 결과 업데이트"""
        self.total_trades += 1
        self.total_return += actual_return
        self.avg_confidence = (
            (self.avg_confidence * (self.total_trades - 1) + decision.confidence) 
            / self.total_trades
        )
        
        if actual_return > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
            
        self.accuracy = self.win_rate()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate(),
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "avg_holding_period": self.avg_holding_period,
            "avg_confidence": self.avg_confidence,
            "accuracy": self.accuracy
        }

class TradingRiskManager:
    """리스크 관리자"""
    
    def __init__(self, max_position_size: float = 0.07, max_daily_loss: float = 0.05):
        self.max_position_size = max_position_size  # 7%
        self.max_daily_loss = max_daily_loss  # 5%
        self.daily_loss = 0.0
        self.active_positions = 0
        self.max_positions = 5
    
    def validate_decision(self, decision: DecisionResult) -> tuple[bool, str]:
        """
        리스크 관리 규칙에 따른 결정 검증
        
        Args:
            decision: 검증할 결정
            
        Returns:
            (승인여부, 사유)
        """
        # 일일 손실 한도 확인
        if self.daily_loss >= self.max_daily_loss:
            return False, f"일일 손실 한도 초과: {self.daily_loss:.2%}"
        
        # 포지션 크기 확인
        if decision.position_size_recommendation > self.max_position_size:
            return False, f"포지션 크기 초과: {decision.position_size_recommendation:.2%}"
        
        # 최대 포지션 수 확인
        if decision.decision == "BUY" and self.active_positions >= self.max_positions:
            return False, f"최대 포지션 수 초과: {self.active_positions}/{self.max_positions}"
        
        # 신뢰도 임계값 확인
        min_confidence = {
            "BUY": 0.65,
            "SELL": 0.55,
            "HOLD": 0.3
        }
        
        if decision.confidence < min_confidence[decision.decision]:
            return False, f"신뢰도 부족: {decision.confidence:.2f} < {min_confidence[decision.decision]:.2f}"
        
        # 고위험 상황에서 매수 금지
        if decision.decision == "BUY" and decision.risk_level == "CRITICAL":
            return False, "고위험 상황에서 매수 금지"
        
        return True, "승인"
    
    def update_daily_loss(self, loss: float):
        """일일 손실 업데이트"""
        self.daily_loss += loss
        if self.daily_loss < 0:
            self.daily_loss = 0
    
    def update_positions(self, change: int):
        """포지션 수 업데이트"""
        self.active_positions += change
        if self.active_positions < 0:
            self.active_positions = 0
    
    def reset_daily_metrics(self):
        """일일 메트릭 리셋"""
        self.daily_loss = 0.0