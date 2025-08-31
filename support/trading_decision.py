#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
거래 결정 데이터 클래스
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

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
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            'symbol': self.symbol,
            'decision': self.decision,
            'confidence': self.confidence,
            'quantity': self.quantity,
            'target_price': self.target_price,
            'stop_loss': self.stop_loss,
            'reasoning': self.reasoning,
            'risk_level': self.risk_level,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TradingDecision':
        """딕셔너리에서 생성"""
        if 'timestamp' in data and data['timestamp']:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)