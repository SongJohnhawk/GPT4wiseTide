#!/usr/bin/env python3
"""
시스템 레벨 거래 결정 엔진
3분봉 단타 거래량·가격 결합 단일 판단로직을 시스템 레벨에서 구현
"""

import pandas as pd
import numpy as np
from datetime import datetime, time as datetime_time
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
sys.path.append(str(Path(__file__).parent.parent))

from support.unified_cycle_manager import get_step_delay_manager

# 깔끔한 콘솔 로거 사용
from support.clean_console_logger import (
    get_clean_logger, Phase, log as clean_log
)


class SystemLevelDecisionEngine:
    """시스템 레벨 거래 결정 엔진 - 3분봉 단타 로직"""
    
    def __init__(self):
        """초기화"""
        self.engine_name = "3분봉 단타 거래량·가격 결합 시스템"
        self.version = "1.0"
        
        # 핵심 파라미터 (3분봉 단타 로직 기준)
        self.params = {
            # 기간 지표
            "ema_fast": 5,          # EMA_fast = 5
            "ema_slow": 20,         # EMA_slow = 20  
            "rsi_length": 7,        # RSI_len = 7
            "volume_avg_length": 20, # V_avg_len = 20 (3분봉 20개 ≈ 60분)
            
            # 임계치
            "volume_surge_multiplier": 2.2,  # K_buy = 2.2 (거래량 급등 배수)
            "rsi_buy_zone_min": 55,         # RSI_buy_zone = [55, 75]
            "rsi_buy_zone_max": 75,
            "volume_fade_multiplier": 0.5,   # Vol_fade = 0.5 (거래량 소멸)
            
            # 리스크 관리
            "stop_loss_pct": 2.0,     # SL = -2.0% (진입가 기준 손절)
            "take_profit1_pct": 3.0,  # TP1 = +3.0% (1차 익절, 50% 청산)
            "trailing_trigger_pct": 2.0,  # TS_trigger = +2.0% 이후 Trailing
            
            # 시간 규칙
            "new_entry_cutoff": "14:30:00",  # 신규 진입 금지: 14:30 이후
            "force_close_time": "14:55:00",  # 전량 청산: 14:55
        }
        
        # 포지션 상태 관리 (상태머신)
        self.position_state = "FLAT"  # FLAT, LONG
        self.entry_price: Optional[float] = None
        self.half_taken: bool = False
        self.position_quantity: int = 0
        
        # 지표 캐시
        self.indicators_cache: Dict[str, Any] = {}
        
        # 결정 히스토리
        self.decision_history: List[Dict[str, Any]] = []
        
        # 단계별 지연 관리자
        self.step_delay_manager = get_step_delay_manager(2)
        
        clean_log(f"시스템 레벨 결정 엔진 준비 완료: {self.engine_name}", "SUCCESS")
    
    def get_engine_info(self) -> Dict[str, Any]:
        """엔진 정보 반환"""
        return {
            "name": self.engine_name,
            "version": self.version,
            "parameters": self.params.copy(),
            "position_state": self.position_state,
            "entry_price": self.entry_price,
            "half_taken": self.half_taken
        }
    
    async def make_trading_decision(self, market_data: pd.DataFrame, stock_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        시스템 레벨 거래 결정 수행
        
        Args:
            market_data: 3분봉 OHLCV 데이터 (최소 20봉 이상)
            stock_info: 종목 정보 (stock_code, stock_name 등)
            
        Returns:
            Dict: 거래 결정 정보
        """
        try:
            decision_time = datetime.now()
            # 거래 결정 시작 (로그 제거 - 중복 메시지 방지)
            
            # 1단계: 데이터 검증 및 전처리
            if not self._validate_market_data(market_data):
                return self._generate_hold_decision("데이터 부족 또는 검증 실패")
            
            await self.step_delay_manager.delay_between_steps("데이터 검증")
            
            # 2단계: 기술적 지표 계산
            indicators = self._calculate_technical_indicators(market_data)
            self.indicators_cache = indicators
            
            await self.step_delay_manager.delay_between_steps("지표 계산")
            
            # 3단계: 시간 규칙 확인
            time_check = self._check_time_rules(decision_time)
            
            await self.step_delay_manager.delay_between_steps("시간 규칙 확인")
            
            # 4단계: 상태머신 기반 거래 결정
            decision = await self._execute_state_machine_decision(
                indicators, time_check, stock_info, decision_time
            )
            
            # 5단계: 결정 히스토리 저장
            self._save_decision_history(decision, stock_info, decision_time)
            
            # 거래 결정 완료 (로그 제거 - 중복 메시지 방지)
            return decision
            
        except Exception as e:
            clean_log(f"시스템 레벨 거래 결정 오류: {e}", "ERROR")
            return self._generate_hold_decision(f"결정 오류: {str(e)}")
    
    def _validate_market_data(self, data: pd.DataFrame) -> bool:
        """시장 데이터 검증"""
        try:
            if data is None or len(data) == 0:
                clean_log("시장 데이터 없음", "WARNING")
                return False
            
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            missing_columns = [col for col in required_columns if col not in data.columns]
            
            if missing_columns:
                clean_log(f"필수 컬럼 누락: {missing_columns}", "WARNING")
                return False
            
            # 최소 데이터 길이 확인 (V20 계산을 위해 20개 이상 필요)
            min_required_length = max(
                self.params["ema_slow"],
                self.params["volume_avg_length"],
                self.params["rsi_length"]
            )
            
            if len(data) < min_required_length:
                clean_log(f"데이터 길이 부족: {len(data)} < {min_required_length}", "WARNING")
                return False
            
            return True
            
        except Exception as e:
            clean_log(f"데이터 검증 오류: {e}", "ERROR")
            return False
    
    def _calculate_technical_indicators(self, data: pd.DataFrame) -> Dict[str, Any]:
        """기술적 지표 계산"""
        try:
            # 현재봉 정보
            current_idx = len(data) - 1
            current_bar = data.iloc[current_idx]
            
            # EMA 계산
            ema_fast = data['close'].ewm(span=self.params["ema_fast"]).mean()
            ema_slow = data['close'].ewm(span=self.params["ema_slow"]).mean()
            
            # VWAP 계산 (당일 VWAP - 간단 구현)
            typical_price = (data['high'] + data['low'] + data['close']) / 3
            vwap = (typical_price * data['volume']).cumsum() / data['volume'].cumsum()
            
            # RSI 계산
            rsi = self._calculate_rsi(data['close'], self.params["rsi_length"])
            
            # 거래량 평균 계산 (V20)
            volume_avg = data['volume'].rolling(window=self.params["volume_avg_length"]).mean()
            
            # 스윙 하이 돌파 확인 (최근 20봉 고점)
            lookback_high = data['high'].rolling(window=20).max().shift(1)
            swing_high_break = current_bar['close'] > lookback_high.iloc[current_idx]
            
            # 긴 윗꼬리 확인 (캔들 전체의 50% 이상)
            candle_total_range = current_bar['high'] - current_bar['low']
            upper_shadow = current_bar['high'] - max(current_bar['close'], current_bar['open'])
            long_upper_shadow = (upper_shadow >= 0.5 * candle_total_range) if candle_total_range > 0 else False
            
            # 현재 값들 추출
            current_indicators = {
                # 가격 정보
                "current_open": float(current_bar['open']),
                "current_high": float(current_bar['high']),
                "current_low": float(current_bar['low']),
                "current_close": float(current_bar['close']),
                "current_volume": float(current_bar['volume']),
                
                # 지표 값들
                "ema_fast": float(ema_fast.iloc[current_idx]),
                "ema_slow": float(ema_slow.iloc[current_idx]),
                "vwap": float(vwap.iloc[current_idx]),
                "rsi": float(rsi.iloc[current_idx]),
                "volume_avg": float(volume_avg.iloc[current_idx]),
                
                # 거래량 비율
                "volume_ratio": float(current_bar['volume'] / volume_avg.iloc[current_idx]) if volume_avg.iloc[current_idx] > 0 else 1.0,
                
                # 패턴 확인
                "is_green_candle": current_bar['close'] > current_bar['open'],
                "swing_high_break": swing_high_break,
                "long_upper_shadow": long_upper_shadow,
                
                # 필터 조건들
                "vwap_filter_ok": current_bar['close'] > vwap.iloc[current_idx],
                "trend_ok": ema_fast.iloc[current_idx] > ema_slow.iloc[current_idx],
                "trend_break": (current_bar['close'] < ema_fast.iloc[current_idx] or 
                               ema_fast.iloc[current_idx] < ema_slow.iloc[current_idx] or 
                               current_bar['close'] < vwap.iloc[current_idx])
            }
            
            return current_indicators
            
        except Exception as e:
            clean_log(f"지표 계산 오류: {e}", "ERROR")
            return {}
    
    def _calculate_rsi(self, prices: pd.Series, length: int) -> pd.Series:
        """RSI 계산"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.fillna(50)  # NaN 값을 중성값 50으로 채움
            
        except Exception as e:
            clean_log(f"RSI 계산 오류: {e}", "ERROR")
            return pd.Series([50] * len(prices), index=prices.index)
    
    def _check_time_rules(self, current_time: datetime) -> Dict[str, bool]:
        """시간 규칙 확인"""
        try:
            current_time_str = current_time.strftime("%H:%M:%S")
            
            # 신규 진입 허용 시간 (14:30 이전)
            allow_new_entry = current_time_str < self.params["new_entry_cutoff"]
            
            # 강제 청산 시간 (14:55 이후)
            force_close = current_time_str >= self.params["force_close_time"]
            
            # 주말 확인
            is_weekend = current_time.weekday() >= 5
            
            # 장시간 확인 (대략적)
            market_hours = ("09:00:00" <= current_time_str <= "15:30:00") and not is_weekend
            
            return {
                "allow_new_entry": allow_new_entry,
                "force_close": force_close,
                "is_weekend": is_weekend,
                "market_hours": market_hours
            }
            
        except Exception as e:
            clean_log(f"시간 규칙 확인 오류: {e}", "ERROR")
            return {
                "allow_new_entry": False,
                "force_close": True,
                "is_weekend": True,
                "market_hours": False
            }
    
    async def _execute_state_machine_decision(self, indicators: Dict[str, Any], 
                                            time_check: Dict[str, bool],
                                            stock_info: Dict[str, Any],
                                            decision_time: datetime) -> Dict[str, Any]:
        """상태머신 기반 거래 결정 실행"""
        try:
            # 강제 청산 시간 확인
            if time_check["force_close"] and self.position_state == "LONG":
                return await self._execute_force_close(indicators, "강제 청산 시간")
            
            # 상태별 결정 로직
            if self.position_state == "FLAT":
                return await self._handle_flat_state(indicators, time_check, stock_info)
            
            elif self.position_state == "LONG":
                return await self._handle_long_state(indicators, time_check, stock_info)
            
            else:
                clean_log(f"알 수 없는 포지션 상태: {self.position_state}", "WARNING")
                return self._generate_hold_decision("알 수 없는 포지션 상태")
                
        except Exception as e:
            clean_log(f"상태머신 실행 오류: {e}", "ERROR")
            return self._generate_hold_decision(f"상태머신 오류: {str(e)}")
    
    async def _handle_flat_state(self, indicators: Dict[str, Any], 
                                time_check: Dict[str, bool],
                                stock_info: Dict[str, Any]) -> Dict[str, Any]:
        """FLAT 상태 처리 - 매수 신호 확인"""
        try:
            # 신규 진입 시간 확인
            if not time_check["allow_new_entry"]:
                return self._generate_hold_decision("신규 진입 시간 아님")
            
            # 핵심 매수 조건 확인 ("진짜 돌파" 단일 조건군)
            buy_conditions = {
                "volume_explosion": indicators.get("volume_ratio", 0) >= self.params["volume_surge_multiplier"],
                "swing_high_break": indicators.get("swing_high_break", False),
                "vwap_filter": indicators.get("vwap_filter_ok", False),
                "trend_alignment": indicators.get("trend_ok", False),
                "rsi_zone": (self.params["rsi_buy_zone_min"] <= indicators.get("rsi", 50) <= self.params["rsi_buy_zone_max"]),
                "green_candle": indicators.get("is_green_candle", False)
            }
            
            # 모든 조건 만족 시 매수 신호
            all_conditions_met = all(buy_conditions.values())
            
            if all_conditions_met:
                await self.step_delay_manager.delay_between_steps("매수 신호 생성")
                
                # 포지션 상태 업데이트
                self.position_state = "LONG"
                self.entry_price = indicators.get("current_close", 0)
                self.half_taken = False
                
                # 신뢰도 계산
                confidence = self._calculate_buy_confidence(indicators)
                
                reason_parts = []
                if buy_conditions["volume_explosion"]:
                    reason_parts.append(f"거래량폭발({indicators.get('volume_ratio', 0):.1f}배)")
                if buy_conditions["swing_high_break"]:
                    reason_parts.append("고점돌파")
                if buy_conditions["vwap_filter"]:
                    reason_parts.append("VWAP상방")
                if buy_conditions["trend_alignment"]:
                    reason_parts.append("추세정렬")
                if buy_conditions["rsi_zone"]:
                    reason_parts.append(f"RSI적정({indicators.get('rsi', 50):.1f})")
                
                reason = "진짜돌파: " + "+".join(reason_parts)
                
                return {
                    "signal": "BUY",
                    "confidence": confidence,
                    "reason": reason,
                    "entry_price": self.entry_price,
                    "position_state": self.position_state,
                    "conditions_met": buy_conditions,
                    "indicators": indicators,
                    "risk_management": {
                        "stop_loss": self.entry_price * (1 - self.params["stop_loss_pct"] / 100),
                        "take_profit_1": self.entry_price * (1 + self.params["take_profit1_pct"] / 100)
                    }
                }
            else:
                # 조건 미충족
                failed_conditions = [k for k, v in buy_conditions.items() if not v]
                reason = f"매수 조건 미충족: {', '.join(failed_conditions)}"
                
                return self._generate_hold_decision(reason, indicators)
                
        except Exception as e:
            clean_log(f"FLAT 상태 처리 오류: {e}", "ERROR")
            return self._generate_hold_decision(f"FLAT 상태 오류: {str(e)}")
    
    async def _handle_long_state(self, indicators: Dict[str, Any], 
                               time_check: Dict[str, bool],
                               stock_info: Dict[str, Any]) -> Dict[str, Any]:
        """LONG 상태 처리 - 매도 신호 확인"""
        try:
            if not self.entry_price:
                clean_log("진입가 미설정 오류", "ERROR")
                return self._generate_hold_decision("진입가 정보 없음")
            
            current_price = indicators.get("current_close", 0)
            profit_loss_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            
            # ① 하드 스톱 (-2%)
            if profit_loss_pct <= -self.params["stop_loss_pct"]:
                return await self._execute_stop_loss(indicators, profit_loss_pct)
            
            # ② 1차 익절 (+3%, 50% 청산)
            if (not self.half_taken) and (profit_loss_pct >= self.params["take_profit1_pct"]):
                return await self._execute_partial_take_profit(indicators, profit_loss_pct)
            
            # ③ 트레일링 (수익 2%↑ 구간에서 추세/VWAP 이탈 시)
            if (profit_loss_pct >= self.params["trailing_trigger_pct"]) and indicators.get("trend_break", False):
                return await self._execute_trailing_stop(indicators, profit_loss_pct)
            
            # ④ 경고성 즉시 청산
            emergency_conditions = self._check_emergency_exit_conditions(indicators)
            if emergency_conditions["should_exit"]:
                return await self._execute_emergency_exit(indicators, emergency_conditions["reason"])
            
            # 보유 지속
            return {
                "signal": "HOLD",
                "confidence": 0.7,
                "reason": f"포지션 유지 (수익률: {profit_loss_pct:.1f}%)",
                "position_state": self.position_state,
                "entry_price": self.entry_price,
                "current_price": current_price,
                "profit_loss_pct": profit_loss_pct,
                "half_taken": self.half_taken,
                "indicators": indicators
            }
            
        except Exception as e:
            clean_log(f"LONG 상태 처리 오류: {e}", "ERROR")
            return self._generate_hold_decision(f"LONG 상태 오류: {str(e)}")
    
    def _check_emergency_exit_conditions(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """긴급 청산 조건 확인"""
        try:
            conditions = []
            
            # 고점 대량 + 긴 윗꼬리 (세력 분배)
            if (indicators.get("long_upper_shadow", False) and 
                indicators.get("volume_ratio", 0) >= 2.0):
                conditions.append("세력분배신호")
            
            # 거래량 소멸 + 약세 캔들 (EMA5 하회)
            if (indicators.get("volume_ratio", 0) <= self.params["volume_fade_multiplier"] and
                indicators.get("current_close", 0) <= indicators.get("ema_fast", 0)):
                conditions.append("거래량소멸+약세")
            
            return {
                "should_exit": len(conditions) > 0,
                "reason": " & ".join(conditions) if conditions else "",
                "conditions": conditions
            }
            
        except Exception as e:
            clean_log(f"긴급 청산 조건 확인 오류: {e}", "ERROR")
            return {"should_exit": False, "reason": "확인 오류", "conditions": []}
    
    async def _execute_stop_loss(self, indicators: Dict[str, Any], profit_loss_pct: float) -> Dict[str, Any]:
        """손절 실행"""
        await self.step_delay_manager.delay_between_steps("손절 실행")
        
        self.position_state = "FLAT"
        self.entry_price = None
        self.half_taken = False
        
        return {
            "signal": "SELL_ALL",
            "confidence": 1.0,
            "reason": f"하드 스톱 (-{self.params['stop_loss_pct']:.1f}%, 실제: {profit_loss_pct:.1f}%)",
            "position_state": self.position_state,
            "profit_loss_pct": profit_loss_pct,
            "sell_type": "STOP_LOSS",
            "indicators": indicators
        }
    
    async def _execute_partial_take_profit(self, indicators: Dict[str, Any], profit_loss_pct: float) -> Dict[str, Any]:
        """부분 익절 실행 (50%)"""
        await self.step_delay_manager.delay_between_steps("부분 익절 실행")
        
        self.half_taken = True
        
        return {
            "signal": "SELL_HALF",
            "confidence": 0.9,
            "reason": f"1차 익절 (+{self.params['take_profit1_pct']:.1f}%, 실제: {profit_loss_pct:.1f}%)",
            "position_state": self.position_state,
            "profit_loss_pct": profit_loss_pct,
            "sell_type": "PARTIAL_PROFIT",
            "sell_ratio": 0.5,
            "half_taken": self.half_taken,
            "indicators": indicators
        }
    
    async def _execute_trailing_stop(self, indicators: Dict[str, Any], profit_loss_pct: float) -> Dict[str, Any]:
        """트레일링 스톱 실행"""
        await self.step_delay_manager.delay_between_steps("트레일링 스톱 실행")
        
        self.position_state = "FLAT"
        self.entry_price = None
        self.half_taken = False
        
        return {
            "signal": "SELL_ALL",
            "confidence": 0.9,
            "reason": f"트레일링 스톱 (수익: {profit_loss_pct:.1f}%, 추세이탈)",
            "position_state": self.position_state,
            "profit_loss_pct": profit_loss_pct,
            "sell_type": "TRAILING_STOP",
            "indicators": indicators
        }
    
    async def _execute_emergency_exit(self, indicators: Dict[str, Any], exit_reason: str) -> Dict[str, Any]:
        """긴급 청산 실행"""
        await self.step_delay_manager.delay_between_steps("긴급 청산 실행")
        
        current_price = indicators.get("current_close", 0)
        profit_loss_pct = ((current_price - self.entry_price) / self.entry_price) * 100 if self.entry_price else 0
        
        self.position_state = "FLAT"
        self.entry_price = None
        self.half_taken = False
        
        return {
            "signal": "SELL_ALL",
            "confidence": 1.0,
            "reason": f"긴급 청산: {exit_reason} (수익률: {profit_loss_pct:.1f}%)",
            "position_state": self.position_state,
            "profit_loss_pct": profit_loss_pct,
            "sell_type": "EMERGENCY_EXIT",
            "exit_reason": exit_reason,
            "indicators": indicators
        }
    
    async def _execute_force_close(self, indicators: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """강제 청산 실행"""
        await self.step_delay_manager.delay_between_steps("강제 청산 실행")
        
        current_price = indicators.get("current_close", 0)
        profit_loss_pct = ((current_price - self.entry_price) / self.entry_price) * 100 if self.entry_price else 0
        
        self.position_state = "FLAT"
        self.entry_price = None
        self.half_taken = False
        
        return {
            "signal": "SELL_ALL",
            "confidence": 1.0,
            "reason": f"{reason} (수익률: {profit_loss_pct:.1f}%)",
            "position_state": self.position_state,
            "profit_loss_pct": profit_loss_pct,
            "sell_type": "FORCE_CLOSE",
            "indicators": indicators
        }
    
    def _calculate_buy_confidence(self, indicators: Dict[str, Any]) -> float:
        """매수 신뢰도 계산"""
        try:
            base_confidence = 0.7
            
            # 거래량 가중치 (거래량이 클수록 신뢰도 증가)
            volume_weight = min(0.2, (indicators.get("volume_ratio", 2.2) - 2.2) * 0.1)
            
            # RSI 가중치 (중간값에 가까울수록 좋음)
            rsi = indicators.get("rsi", 50)
            rsi_optimal = 65  # 최적 RSI 값
            rsi_weight = max(0, 0.1 - abs(rsi - rsi_optimal) * 0.002)
            
            # 추세 강도 가중치
            ema_fast = indicators.get("ema_fast", 0)
            ema_slow = indicators.get("ema_slow", 0)
            trend_strength = (ema_fast - ema_slow) / ema_slow if ema_slow > 0 else 0
            trend_weight = min(0.1, trend_strength * 10)
            
            total_confidence = base_confidence + volume_weight + rsi_weight + trend_weight
            return min(0.95, total_confidence)  # 최대 95%
            
        except Exception as e:
            clean_log(f"신뢰도 계산 오류: {e}", "ERROR")
            return 0.7
    
    def _generate_hold_decision(self, reason: str, indicators: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """보유 결정 생성"""
        return {
            "signal": "HOLD",
            "confidence": 0.5,
            "reason": reason,
            "position_state": self.position_state,
            "entry_price": self.entry_price,
            "indicators": indicators or {}
        }
    
    def _save_decision_history(self, decision: Dict[str, Any], stock_info: Dict[str, Any], decision_time: datetime) -> None:
        """결정 히스토리 저장"""
        try:
            history_entry = {
                "timestamp": decision_time.strftime('%Y-%m-%d %H:%M:%S'),
                "stock_code": stock_info.get("stock_code", ""),
                "stock_name": stock_info.get("stock_name", ""),
                "signal": decision["signal"],
                "confidence": decision["confidence"],
                "reason": decision["reason"],
                "position_state": decision["position_state"]
            }
            
            # 최대 100개 기록만 유지
            self.decision_history.append(history_entry)
            if len(self.decision_history) > 100:
                self.decision_history.pop(0)
                
        except Exception as e:
            clean_log(f"결정 히스토리 저장 오류: {e}", "ERROR")
    
    def get_decision_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 결정 히스토리 반환"""
        return self.decision_history[-limit:] if self.decision_history else []
    
    def get_current_position_info(self) -> Dict[str, Any]:
        """현재 포지션 정보 반환"""
        return {
            "position_state": self.position_state,
            "entry_price": self.entry_price,
            "half_taken": self.half_taken,
            "position_quantity": self.position_quantity
        }
    
    def reset_position(self) -> None:
        """포지션 초기화"""
        self.position_state = "FLAT"
        self.entry_price = None
        self.half_taken = False
        self.position_quantity = 0
        # 포지션 상태 초기화 (로그 제거)
    
    def update_parameters(self, new_params: Dict[str, Any]) -> bool:
        """파라미터 업데이트"""
        try:
            for key, value in new_params.items():
                if key in self.params:
                    old_value = self.params[key]
                    self.params[key] = value
                    # 파라미터 업데이트 (로그 제거)
                else:
                    clean_log(f"알 수 없는 파라미터: {key}", "WARNING")
            
            return True
            
        except Exception as e:
            clean_log(f"파라미터 업데이트 오류: {e}", "ERROR")
            return False


# 전역 인스턴스 (싱글톤 패턴)
_system_decision_engine: Optional[SystemLevelDecisionEngine] = None


def get_system_decision_engine() -> SystemLevelDecisionEngine:
    """시스템 레벨 결정 엔진 인스턴스 반환 (싱글톤)"""
    global _system_decision_engine
    if _system_decision_engine is None:
        _system_decision_engine = SystemLevelDecisionEngine()
    return _system_decision_engine


async def make_system_level_decision(market_data: pd.DataFrame, stock_info: Dict[str, Any]) -> Dict[str, Any]:
    """시스템 레벨 거래 결정 수행 (편의 함수)"""
    engine = get_system_decision_engine()
    return await engine.make_trading_decision(market_data, stock_info)


if __name__ == "__main__":
    # 테스트 실행
    import asyncio
    
    async def test_decision_engine():
        print("=== 시스템 레벨 결정 엔진 테스트 ===")
        
        # 테스트용 시장 데이터 생성 (3분봉 30개)
        dates = pd.date_range(start='2024-01-01 09:00:00', periods=30, freq='3min')
        test_data = pd.DataFrame({
            'open': np.random.uniform(10000, 11000, 30),
            'high': np.random.uniform(10500, 11500, 30),
            'low': np.random.uniform(9500, 10500, 30),
            'close': np.random.uniform(10000, 11000, 30),
            'volume': np.random.uniform(50000, 300000, 30)
        }, index=dates)
        
        # 급등 상황 시뮬레이션 (마지막 몇 개 봉)
        test_data.loc[test_data.index[-3:], 'volume'] *= 3  # 거래량 3배 증가
        test_data.loc[test_data.index[-2:], 'close'] *= 1.05  # 5% 상승
        
        stock_info = {
            "stock_code": "000001",
            "stock_name": "테스트종목"
        }
        
        # 결정 엔진 테스트
        engine = SystemLevelDecisionEngine()
        
        print(f"엔진 정보: {engine.get_engine_info()}")
        
        # 첫 번째 결정 (FLAT 상태에서 매수 신호 확인)
        decision1 = await engine.make_trading_decision(test_data, stock_info)
        print(f"\n첫 번째 결정: {decision1}")
        
        # 두 번째 결정 (LONG 상태에서 보유/매도 신호 확인)
        if decision1['signal'] == 'BUY':
            decision2 = await engine.make_trading_decision(test_data, stock_info)
            print(f"\n두 번째 결정: {decision2}")
        
        # 포지션 정보 확인
        print(f"\n현재 포지션: {engine.get_current_position_info()}")
        
        # 결정 히스토리 확인
        print(f"\n결정 히스토리: {engine.get_decision_history()}")
    
    # 테스트 실행
    asyncio.run(test_decision_engine())