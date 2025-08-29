# -*- coding: utf-8 -*-
"""
tideWise 전날잔고 처리 통합 모듈
기존 분산된 로직을 하나의 독립된 객체로 통합

작성자: Claude-Optimizer 적용
작성일: 2025-08-18
버전: 1.0.0
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Dict, Any, List, Optional
from enum import Enum

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class TradingStrategy(Enum):
    """매매 전략 타입"""
    PRODUCTION = "production"     # 고급 매매 시스템
    SIMPLE = "simple"            # 단순 매매 시스템  
    MINIMAL = "minimal"          # 최소 매매 시스템
    DAY_TRADING = "day_trading"  # 단타매매 시스템


@dataclass
class StrategyConfig:
    """전략별 설정"""
    stop_loss_rate: float = -0.05      # 손절 기준
    take_profit_rate: float = 0.07     # 익절 기준
    use_david_paul: bool = False       # David Paul 분석 사용 여부
    use_user_designated: bool = False  # 사용자 지정종목 제외 여부
    volume_analysis: bool = False      # 거래량 분석 사용 여부
    

@dataclass
class FlowCache:
    """심볼별 흐름 스냅샷(이전 상태)"""
    ts: float = 0.0
    ask_total: float = 0.0   # 예약 매도물량(상위 N호가 합)
    bid_total: float = 0.0   # 예약 매수물량(상위 N호가 합)
    buy_vol: float = 0.0     # 실제 매수체결 누적
    sell_vol: float = 0.0    # 실제 매도체결 누적


def _safe_float(x, default: float = 0.0) -> float:
    """안전한 float 변환"""
    try:
        return float(x)
    except Exception:
        return default


def _pct_change(new: Optional[float], base: Optional[float]) -> float:
    """안전한 퍼센트 변화율 계산"""
    if new is None or base is None:
        return 0.0
    b = base if base != 0 else 1e-9
    return (new - base) / b


class PreviousDayBalanceHandler:
    """
    전날잔고 처리 통합 클래스
    
    기존 4개 시스템(production, simple, minimal, day_trading)의 
    전날잔고 처리 로직을 하나로 통합하여 일관성과 유지보수성 향상
    """

    def __init__(self, api_connector, account_type: str = "REAL", strategy: TradingStrategy = TradingStrategy.PRODUCTION):
        """
        초기화
        
        Args:
            api_connector: KISAPIConnector 인스턴스
            account_type: "REAL" 또는 "MOCK"
            strategy: 매매 전략 타입
        """
        self.api = api_connector
        self.account_type = account_type
        self.strategy = strategy
        self.account_display = "실계좌" if account_type == "REAL" else "모의계좌"

        # 실행 시간(장 개시 직후)
        self.liquidation_start_time = time(9, 5)
        self.liquidation_end_time = time(9, 6)

        # 전략별 설정 로드
        self.config = self._load_strategy_config(strategy)
        
        # 정책 임계값 (샘플코드 기반)
        self.ask_increase_threshold = 0.10     # 예약매도 증가 10%↑
        self.sell_increase_threshold = 0.15    # 실제 매도체결 15%↑
        self.buy_increase_threshold = 0.10     # 실제 매수체결 10%↑
        self.price_non_decreasing_window = 5   # 최근 N캔들 내 비하락
        self.buy_vs_prevday_vol_mult = 1.00    # 전일매수물량 비교 불가 시 20일 평균 대비

        # 상태 캐시
        self._flow_cache: Dict[str, FlowCache] = {}
        
        # 사용자 지정종목 관리
        self._user_designated_codes: set = set()

        logger.info(f"전날잔고 처리기 초기화: {self.account_display} ({strategy.value} 전략)")

    def _load_strategy_config(self, strategy: TradingStrategy) -> StrategyConfig:
        """전략별 설정 로드"""
        configs = {
            TradingStrategy.PRODUCTION: StrategyConfig(
                stop_loss_rate=-0.05,
                take_profit_rate=0.07,
                use_david_paul=True,
                use_user_designated=True,
                volume_analysis=True
            ),
            TradingStrategy.SIMPLE: StrategyConfig(
                stop_loss_rate=-0.04,
                take_profit_rate=0.06,
                use_david_paul=False,
                use_user_designated=False,
                volume_analysis=True
            ),
            TradingStrategy.MINIMAL: StrategyConfig(
                stop_loss_rate=-0.03,
                take_profit_rate=0.05,
                use_david_paul=False,
                use_user_designated=False,
                volume_analysis=False
            ),
            TradingStrategy.DAY_TRADING: StrategyConfig(
                stop_loss_rate=-0.03,
                take_profit_rate=0.02,
                use_david_paul=False,
                use_user_designated=True,
                volume_analysis=False
            )
        }
        return configs.get(strategy, StrategyConfig())

    def is_premarket_liquidation_time(self, now: Optional[datetime] = None) -> bool:
        """장 개시 직후 전날 보유 잔고 매도 시간인지 확인 (09:05-09:06)"""
        now = now or datetime.now()
        current_time = now.time()
        return self.liquidation_start_time <= current_time <= self.liquidation_end_time

    async def execute_previous_day_balance_cleanup(self) -> Dict[str, Any]:
        """
        전날잔고 정리 실행 메인 함수
        
        Returns:
            Dict: 정리 결과
        """
        try:
            logger.info(f"[{self.account_display}] 전날잔고 정리 시작 ({self.strategy.value} 전략)")
            print(f"\n[{self.account_display}] 전날 보유종목 정리를 시작합니다... ({self.strategy.value})")

            # 1) 시간 확인
            if not self.is_premarket_liquidation_time():
                return {
                    "success": False,
                    "message": "전날잔고 정리 시간이 아닙니다 (09:05-09:06)",
                    "processed_count": 0,
                    "sold_count": 0,
                    "kept_count": 0,
                    "strategy": self.strategy.value
                }

            # 2) 사용자 지정종목 로드 (전략에 따라)
            if self.config.use_user_designated:
                await self._load_user_designated_stocks()

            # 3) 포지션 조회
            positions = await self._get_current_positions()
            if not positions:
                return {
                    "success": True,
                    "message": "보유 종목이 없습니다",
                    "processed_count": 0,
                    "sold_count": 0,
                    "kept_count": 0,
                    "strategy": self.strategy.value
                }

            # 4) 포지션별 처리
            results = await self._process_all_positions(positions)

            # 5) 결과 요약
            summary = self._generate_summary(results)
            logger.info(f"[{self.account_display}] 전날잔고 정리 완료: {summary['message']}")
            return summary

        except Exception as e:
            msg = f"전날잔고 정리 실행 실패: {e}"
            logger.error(f"[{self.account_display}] {msg}")
            return {
                "success": False,
                "message": msg,
                "processed_count": 0,
                "sold_count": 0,
                "kept_count": 0,
                "error": str(e),
                "strategy": self.strategy.value
            }

    async def _load_user_designated_stocks(self):
        """사용자 지정종목 로드"""
        try:
            from support.user_designated_stocks import get_user_designated_stock_manager
            user_manager = get_user_designated_stock_manager(self.api)
            self._user_designated_codes = set(user_manager.get_designated_stock_codes())
            if self._user_designated_codes:
                logger.info(f"사용자 지정종목 {len(self._user_designated_codes)}개는 잔고처리에서 제외됩니다")
        except Exception as e:
            logger.warning(f"사용자 지정종목 조회 실패: {e}")
            self._user_designated_codes = set()

    async def _get_current_positions(self) -> List[Dict[str, Any]]:
        """현재 보유 포지션 조회"""
        try:
            balance_data = await self.api.get_account_balance(force_refresh=True)
            if not balance_data:
                logger.error("계좌 정보 조회 실패")
                return []

            positions = []
            for item in balance_data.get('output1', []):
                qty = int(item.get('hldg_qty', '0'))
                if qty <= 0:
                    continue
                
                stock_code = item.get('pdno', '')
                
                # 사용자 지정종목 제외 (전략에 따라)
                if self.config.use_user_designated and stock_code in self._user_designated_codes:
                    logger.info(f"사용자 지정종목 제외: {stock_code}")
                    continue
                
                positions.append({
                    'stock_code': stock_code,
                    'stock_name': (item.get('prdt_name', '') or '').strip(),
                    'quantity': qty,
                    'avg_price': _safe_float(item.get('pchs_avg_pric', '0')),
                    'current_price': _safe_float(item.get('prpr', '0')),
                    'evaluation': _safe_float(item.get('evlu_amt', '0')),
                    'profit_loss': _safe_float(item.get('evlu_pfls_amt', '0')),
                    'profit_rate': _safe_float(item.get('evlu_pfls_rt', '0')) / 100.0
                })
            
            logger.info(f"현재 보유종목 {len(positions)}개 조회 완료")
            return positions
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []

    async def _process_all_positions(self, positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """모든 포지션 처리"""
        results = []
        for p in positions:
            try:
                res = await self._process_single_position(p)
                results.append(res)
                nm, cd, act, why = p['stock_name'], p['stock_code'], res['action'], res['reason']
                print(("  ✓ 매도: " if act == 'SELL' else "  ○ 보유: ") + f"{nm}({cd}) - {why}")
            except Exception as e:
                logger.error(f"포지션 처리 중 오류 ({p.get('stock_code')}): {e}")
                results.append({
                    'stock_code': p.get('stock_code'),
                    'stock_name': p.get('stock_name'),
                    'action': 'ERROR',
                    'reason': f"처리 오류: {str(e)}",
                    'success': False
                })
        return results

    async def _process_single_position(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """
        단일 포지션 처리 - 전략별 로직 적용
        
        샘플코드의 정책 우선/보조 후순위 구조 적용
        """
        code = position['stock_code']
        name = position['stock_name']

        # 전략별 분석 수행
        if self.strategy == TradingStrategy.PRODUCTION:
            return await self._process_production_strategy(position)
        elif self.strategy == TradingStrategy.SIMPLE:
            return await self._process_simple_strategy(position)
        elif self.strategy == TradingStrategy.MINIMAL:
            return await self._process_minimal_strategy(position)
        elif self.strategy == TradingStrategy.DAY_TRADING:
            return await self._process_day_trading_strategy(position)
        else:
            # 기본 전략 (샘플코드 로직)
            return await self._process_default_strategy(position)

    async def _process_production_strategy(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """고급 매매 시스템 전략 (샘플코드 기반)"""
        code = position['stock_code']
        name = position['stock_name']

        # 데이터 수집
        vi = await self._check_vi_status(code)
        ob = await self._fetch_orderbook(code)
        flow = await self._fetch_trade_flow(code)
        ctx = await self._get_price_context(code)
        prevday = await self._get_prevday_metrics(code)

        # 1) 하락 VI 즉시 매도
        if vi.get('down_vi_active', False):
            sell_result = await self._execute_sell_order(position)
            return {
                'stock_code': code, 'stock_name': name,
                'action': 'SELL',
                'reason': '하락 VI 발생 - 즉시 전량 시장가',
                **sell_result
            }

        # 2) 정책 판단 (샘플코드 로직)
        policy = self._policy_decision(position, ob, flow, ctx, prevday)
        if policy['action'] == 'SELL':
            sell_result = await self._execute_sell_order(position)
            policy.update(sell_result)
            return policy

        if policy['action'] == 'HOLD':
            # 3) 보조(세이프가드)
            guard = self._safeguard(position, ctx)
            if guard['action'] == 'SELL' and not policy.get('buy_pressure_holds', False):
                sell_result = await self._execute_sell_order(position)
                guard.update(sell_result)
                return guard
            policy['success'] = True
            return policy

        # 폴백
        return {'stock_code': code, 'stock_name': name, 'action': 'HOLD', 'reason': '데이터 부족', 'success': True}

    async def _process_simple_strategy(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """단순 매매 시스템 전략"""
        code = position['stock_code']
        name = position['stock_name']
        profit_rate = position.get('profit_rate', 0.0)

        # 기본 손절/익절 기준
        if profit_rate <= self.config.stop_loss_rate:
            sell_result = await self._execute_sell_order(position)
            return {
                'stock_code': code, 'stock_name': name,
                'action': 'SELL',
                'reason': f'손절매 ({profit_rate*100:.1f}%)',
                **sell_result
            }
        elif profit_rate >= self.config.take_profit_rate:
            sell_result = await self._execute_sell_order(position)
            return {
                'stock_code': code, 'stock_name': name,
                'action': 'SELL',
                'reason': f'익절매 ({profit_rate*100:.1f}%)',
                **sell_result
            }
        else:
            return {
                'stock_code': code, 'stock_name': name,
                'action': 'HOLD',
                'reason': f'보유유지 ({profit_rate*100:.1f}%)',
                'success': True
            }

    async def _process_minimal_strategy(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """최소 매매 시스템 전략"""
        code = position['stock_code']
        name = position['stock_name']
        profit_rate = position.get('profit_rate', 0.0)

        # 보수적 기준 적용
        if profit_rate <= self.config.stop_loss_rate:
            sell_result = await self._execute_sell_order(position)
            return {
                'stock_code': code, 'stock_name': name,
                'action': 'SELL',
                'reason': f'최소전략 손절 ({profit_rate*100:.1f}%)',
                **sell_result
            }
        elif profit_rate >= self.config.take_profit_rate:
            sell_result = await self._execute_sell_order(position)
            return {
                'stock_code': code, 'stock_name': name,
                'action': 'SELL',
                'reason': f'최소전략 익절 ({profit_rate*100:.1f}%)',
                **sell_result
            }
        else:
            return {
                'stock_code': code, 'stock_name': name,
                'action': 'HOLD',
                'reason': '최소전략 보유',
                'success': True
            }

    async def _process_day_trading_strategy(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """단타매매 시스템 전략"""
        code = position['stock_code']
        name = position['stock_name']
        profit_rate = position.get('profit_rate', 0.0)

        # 단타 기준 (빠른 손절/익절)
        if profit_rate <= self.config.stop_loss_rate:
            sell_result = await self._execute_sell_order(position)
            return {
                'stock_code': code, 'stock_name': name,
                'action': 'SELL',
                'reason': f'단타 손절 ({profit_rate*100:.1f}%)',
                **sell_result
            }
        elif profit_rate >= self.config.take_profit_rate:
            sell_result = await self._execute_sell_order(position)
            return {
                'stock_code': code, 'stock_name': name,
                'action': 'SELL',
                'reason': f'단타 익절 ({profit_rate*100:.1f}%)',
                **sell_result
            }
        else:
            return {
                'stock_code': code, 'stock_name': name,
                'action': 'HOLD',
                'reason': '단타 관망',
                'success': True
            }

    async def _process_default_strategy(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """기본 전략 (샘플코드 전체 로직)"""
        return await self._process_production_strategy(position)

    def _policy_decision(
        self,
        position: Dict[str, Any],
        ob: Dict[str, Any],
        flow: Dict[str, Any],
        ctx: Dict[str, Any],
        prevday: Dict[str, Any]
    ) -> Dict[str, Any]:
        """정책 판단 (샘플코드 로직)"""
        sym = position['stock_code']

        # 이전 스냅샷
        prev = self._flow_cache.get(sym, FlowCache())

        # 현재 스냅샷
        ask_total = _safe_float(ob.get('ask_total', prev.ask_total))
        bid_total = _safe_float(ob.get('bid_total', prev.bid_total))
        buy_vol   = _safe_float(flow.get('buy_volume', prev.buy_vol))
        sell_vol  = _safe_float(flow.get('sell_volume', prev.sell_vol))

        # 증가율 판정
        ask_inc  = _pct_change(ask_total, prev.ask_total) >= self.ask_increase_threshold
        sell_inc = _pct_change(sell_vol, prev.sell_vol)   >= self.sell_increase_threshold
        buy_inc  = _pct_change(buy_vol, prev.buy_vol)     >= self.buy_increase_threshold

        # 상태 캐시 갱신
        self._flow_cache[sym] = FlowCache(
            ts=datetime.now().timestamp(),
            ask_total=ask_total, bid_total=bid_total,
            buy_vol=buy_vol, sell_vol=sell_vol
        )

        # 가격 비하락/완만상승
        price_ok = self._is_price_non_decreasing(ctx)

        # 전일 매수물량 대비(가능 시) 또는 평균 대비
        prev_buy = _safe_float(prevday.get('buy_volume', 0.0))
        cur_vol  = _safe_float(ctx.get('current_volume', 0.0))
        avg20    = max(1.0, _safe_float(ctx.get('avg20_volume', 1.0)))
        buy_vs_prev = (buy_vol >= prev_buy) if prev_buy > 0 else (cur_vol >= self.buy_vs_prevday_vol_mult * avg20)

        # ===== SELL (정책) =====
        if sell_inc and ask_inc:
            return {
                'stock_code': sym, 'stock_name': position['stock_name'],
                'action': 'SELL',
                'reason': '실제 매도체결 증가 + 예약매도 증가 → 가격 무관 전량 시장가(정책)',
                'priority': 'POLICY'
            }

        # ===== HOLD (정책) =====
        if (buy_inc or buy_vs_prev) and (not ask_inc) and price_ok:
            return {
                'stock_code': sym, 'stock_name': position['stock_name'],
                'action': 'HOLD',
                'reason': '매수우위 유지 & 예약매도 증가 없음 & 가격 비하락(정책)',
                'priority': 'POLICY',
                'buy_pressure_holds': True
            }

        # 중립
        return {
            'stock_code': sym, 'stock_name': position['stock_name'],
            'action': 'HOLD',
            'reason': '정책 기준 중립(관망)',
            'priority': 'NEUTRAL'
        }

    def _safeguard(self, position: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        """보조(세이프가드) - 샘플코드 로직"""
        pr = position.get('profit_rate', 0.0)
        # 손절: 손실 과다 시 보조 개입(단, 정책 HOLD가 우선)
        if pr <= self.config.stop_loss_rate:
            return {
                'stock_code': position['stock_code'], 
                'stock_name': position['stock_name'],
                'action': 'SELL', 
                'reason': f'보조 손절({pr*100:.1f}%)', 
                'priority': 'SAFE'
            }
        # 익절: 이익 충분 + 모멘텀 약화 동반 시
        if pr >= self.config.take_profit_rate and ctx.get('momentum_weak', False):
            return {
                'stock_code': position['stock_code'], 
                'stock_name': position['stock_name'],
                'action': 'SELL', 
                'reason': '보조 익절(+모멘텀 약화)', 
                'priority': 'SAFE'
            }
        return {
            'stock_code': position['stock_code'], 
            'stock_name': position['stock_name'],
            'action': 'HOLD', 
            'reason': '보조: 유지', 
            'priority': 'SAFE'
        }

    # === 데이터 수집 메서드들 (샘플코드 기반) ===

    async def _fetch_orderbook(self, stock_code: str) -> Dict[str, Any]:
        """호가창 상위 N(기본 5) 합산"""
        try:
            ob = await self.api.get_orderbook(stock_code)
            asks = ob.get('asks', [])
            bids = ob.get('bids', [])
            ask_total = sum(_safe_float(a.get('qty', 0)) for a in asks[:5])
            bid_total = sum(_safe_float(b.get('qty', 0)) for b in bids[:5])
            return {'ask_total': ask_total, 'bid_total': bid_total}
        except Exception as e:
            logger.debug(f"호가 조회 실패 {stock_code}: {e}")
            return {'ask_total': None, 'bid_total': None}

    async def _fetch_trade_flow(self, stock_code: str) -> Dict[str, Any]:
        """실제 체결 흐름(매수/매도) — 없으면 uptick/downtick 근사"""
        try:
            ticks = await self.api.get_recent_trades(stock_code)
            buy_vol, sell_vol = 0.0, 0.0
            prev_price = None
            for t in ticks:
                px = _safe_float(t.get('price', 0))
                qty = _safe_float(t.get('qty', 0))
                side = t.get('side')
                if side == 'B':
                    buy_vol += qty
                elif side == 'S':
                    sell_vol += qty
                else:
                    if prev_price is None:
                        prev_price = px
                    if px >= prev_price:
                        buy_vol += qty
                    else:
                        sell_vol += qty
                    prev_price = px
            return {'buy_volume': buy_vol, 'sell_volume': sell_vol}
        except Exception as e:
            logger.debug(f"체결 조회 실패 {stock_code}: {e}")
            return {'buy_volume': None, 'sell_volume': None}

    async def _check_vi_status(self, stock_code: str) -> Dict[str, Any]:
        """VI(변동성완화장치) 상태 — 없으면 False"""
        try:
            vi = await self.api.get_vi_status(stock_code)
            return {'down_vi_active': bool(vi.get('down', False))}
        except Exception:
            return {'down_vi_active': False}

    async def _get_price_context(self, stock_code: str) -> Dict[str, Any]:
        """가격/거래량 컨텍스트: 비하락·모멘텀 약화 판정"""
        try:
            k = await self.api.get_ohlcv(stock_code, limit=60)
            if not k:
                return {}
            df = pd.DataFrame(k)
            for c in ['open','high','low','close','volume']:
                if c not in df:
                    df[c] = np.nan
            last = float(df['close'].iloc[-1])
            # VWAP 근사(20)
            tp = (df['high'] + df['low'] + df['close']) / 3.0
            v20 = df['volume'].rolling(20).sum().replace(0, np.nan)
            vwap20 = (tp * df['volume']).rolling(20).sum() / v20
            ema5 = df['close'].ewm(span=5, adjust=False).mean().iloc[-1]
            ema20 = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
            non_decreasing = True
            win = min(self.price_non_decreasing_window, max(2, len(df)-1))
            if win >= 2:
                non_decreasing = (last >= float(df['close'].iloc[-win:-1].min()))
            momentum_weak = (last < float(vwap20.iloc[-1] if pd.notna(vwap20.iloc[-1]) else last)) or (ema5 < ema20)
            return {
                'last_price': last,
                'vwap': float(vwap20.iloc[-1]) if pd.notna(vwap20.iloc[-1]) else last,
                'current_volume': float(df['volume'].iloc[-1]),
                'avg20_volume': float(df['volume'].rolling(20).mean().iloc[-1]),
                'non_decreasing': bool(non_decreasing),
                'momentum_weak': bool(momentum_weak)
            }
        except Exception:
            return {}

    async def _get_prevday_metrics(self, stock_code: str) -> Dict[str, Any]:
        """전일 매수/매도 물량(가능 시)"""
        try:
            m = await self.api.get_prevday_buy_sell(stock_code)
            return {
                'buy_volume': _safe_float(m.get('buy_volume', 0.0)),
                'sell_volume': _safe_float(m.get('sell_volume', 0.0))
            }
        except Exception:
            return {'buy_volume': 0.0, 'sell_volume': 0.0}

    def _is_price_non_decreasing(self, ctx: Dict[str, Any]) -> bool:
        """가격 비하락 판정"""
        return True if not ctx else bool(ctx.get('non_decreasing', True))

    async def _execute_sell_order(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """시장가 전량 매도"""
        try:
            res = await self.api.place_sell_order(
                stock_code=position['stock_code'],
                quantity=position['quantity'],
                price=0,
                order_type="market"
            )
            if res and res.get('success'):
                return {
                    'success': True, 
                    'order_id': res.get('order_id'),
                    'message': f"매도 주문 성공: {position['stock_name']}"
                }
            msg = (res.get('error') if res else '응답 없음') or '매도 주문 실패'
            return {
                'success': False, 
                'error': msg, 
                'message': f"매도 주문 실패: {position['stock_name']}"
            }
        except Exception as e:
            logger.error(f"매도 주문 오류: {e}")
            return {
                'success': False, 
                'error': str(e), 
                'message': f"매도 주문 오류: {position['stock_name']}"
            }

    def _generate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """결과 요약 생성"""
        n = len(results)
        sold = sum(1 for r in results if r['action'] == 'SELL' and r.get('success', True))
        kept = sum(1 for r in results if r['action'] == 'HOLD')
        err  = sum(1 for r in results if r['action'] == 'ERROR')
        rate = (sold + kept) / n if n > 0 else 0.0

        msg = f"처리완료 {n}개 - 매도 {sold}개, 보유 {kept}개" + (f", 오류 {err}개" if err else "")
        print(f"\n[{self.account_display}] 전날잔고 정리 완료:")
        print(f"  - 총 처리: {n}개")
        print(f"  - 매도 실행: {sold}개")
        print(f"  - 보유 유지: {kept}개")
        if err:
            print(f"  - 처리 오류: {err}개")
        print(f"  - 성공률: {rate*100:.1f}%")
        print(f"  - 사용 전략: {self.strategy.value}")

        return {
            'success': True, 
            'message': msg,
            'processed_count': n, 
            'sold_count': sold, 
            'kept_count': kept,
            'error_count': err, 
            'success_rate': rate, 
            'details': results,
            'strategy': self.strategy.value
        }


# === 팩토리 함수들 ===

def get_previous_day_balance_handler(api_connector, account_type: str = "REAL", strategy: TradingStrategy = TradingStrategy.PRODUCTION) -> PreviousDayBalanceHandler:
    """PreviousDayBalanceHandler 인스턴스 생성 팩토리 함수"""
    return PreviousDayBalanceHandler(api_connector, account_type, strategy)


async def execute_previous_day_cleanup(account_type: str = "REAL", strategy: TradingStrategy = TradingStrategy.PRODUCTION) -> Dict[str, Any]:
    """
    전날잔고 정리 실행 함수 (독립 실행용)
    
    Args:
        account_type: "REAL" 또는 "MOCK"
        strategy: 매매 전략 타입
        
    Returns:
        Dict: 정리 결과
    """
    try:
        from support.api_connector import KISAPIConnector
        api = KISAPIConnector(is_mock=(account_type == "MOCK"))
        handler = PreviousDayBalanceHandler(api, account_type, strategy)
        return await handler.execute_previous_day_balance_cleanup()
    except Exception as e:
        msg = f"전날잔고 정리 실행 실패: {e}"
        logger.error(msg)
        return {
            "success": False, 
            "message": msg,
            "processed_count": 0, 
            "sold_count": 0, 
            "kept_count": 0, 
            "error": str(e),
            "strategy": strategy.value if strategy else "unknown"
        }


def is_premarket_liquidation_time(now: Optional[datetime] = None) -> bool:
    """전날잔고 정리 시간인지 확인 (09:05-09:06) - 유틸리티 함수"""
    now = now or datetime.now()
    return time(9, 5) <= now.time() <= time(9, 6)


if __name__ == "__main__":
    # 테스트 실행
    asyncio.run(execute_previous_day_cleanup("MOCK", TradingStrategy.PRODUCTION))