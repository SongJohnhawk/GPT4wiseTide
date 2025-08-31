#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
통합 GPT 거래 엔진
- 이벤트 기반 매매 결정 시스템
- 다중 AI 서비스 통합
- 실시간 시장 데이터 처리
- 리스크 관리 및 포지션 관리
"""

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid

from .event_bus_system import EventBusSystem, EventType, Event, Priority, EventHandler
from .ai_service_manager import AIServiceManager, ServiceType
from .intelligent_context_builder import IntelligentContextBuilder
from .integrated_free_data_system import IntegratedFreeDataSystem
from .gpt_interfaces import MarketContext, DecisionResult
from .david_paul_volume_validator import DavidPaulVolumeValidator
from .trading_time_manager import TradingTimeManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntegratedGPTTrader(EventHandler):
    """통합 GPT 단타매매 시스템"""
    
    def __init__(self, account_type: str = "REAL", openai_api_key: str = None):
        """
        초기화
        
        Args:
            account_type: 계좌 타입 ("REAL" or "MOCK")
            openai_api_key: OpenAI API 키
        """
        # 부모 클래스 초기화
        super().__init__(account_type)
        
        # GPT 거래 엔진 초기화
        self.gpt_engine = get_gpt_trading_engine(openai_api_key)
        
        # 시간 관리자 초기화
        self.time_manager = get_trading_time_manager()
        
        # David Paul 검증기 (이미 gpt_engine에서 사용하지만 직접 접근용)
        self.volume_validator = get_david_paul_validator()
        
        # GPT 관련 설정
        self.enable_pre_trading_wait = True  # 거래 시작 전 대기 활성화
        self.gpt_decision_cache = {}         # GPT 결정 캐싱
        
        # 성능 추적
        self.gpt_decisions_made = 0
        self.gpt_api_costs = 0.0
        self.decision_accuracy = {'correct': 0, 'total': 0}
        
        logger.info(f"통합 GPT 단타매매 시스템 초기화 완료 ({account_type})")
        logger.info("기존 알고리즘 → GPT 기반 의사결정으로 완전 대체")
    
    async def run(self):
        """
        통합 GPT 거래 시스템 실행
        기존 MinimalDayTrader.run()을 오버라이드하여 GPT 기능 통합
        """
        try:
            logger.info("=== 통합 GPT 단타매매 시스템 시작 ===")
            
            # 1. 시스템 초기화
            if not await self._initialize_systems():
                logger.error("시스템 초기화 실패")
                return False
            
            # 2. 거래 시작 대기 (옵션)
            if self.enable_pre_trading_wait and not self.time_manager.is_trading_time():
                logger.info("거래 시간이 아닙니다. 대기 모드로 전환합니다.")
                
                wait_result = await self.time_manager.wait_for_trading_start(
                    self._on_waiting_update
                )
                
                if not wait_result:
                    logger.info("거래 시작 대기가 취소됨")
                    return False
                
                logger.info("거래 시간 도달 - 거래 시작!")
            
            # 3. 거래 세션 시작 알림
            await self._send_start_notification()
            
            # 4. 사전 초기화 (계좌 조회, 전날 잔고 처리 등)
            if not await self._pre_day_trading_initialization():
                logger.error("거래 전 초기화 실패")
                return False
            
            # 5. GPT 기반 거래 세션 시작
            await self.time_manager.monitor_trading_session(
                on_cycle=self._execute_gpt_trading_cycle,
                on_end=self._on_trading_session_end
            )
            
            # 6. 거래 세션 종료 처리
            await self._finalize_day_trading()
            
            logger.info("통합 GPT 단타매매 시스템 정상 종료")
            return True
            
        except Exception as e:
            logger.error(f"통합 GPT 거래 시스템 실행 오류: {e}")
            return False
    
    async def _on_waiting_update(self, wait_info: Dict[str, Any]):
        """거래 시작 대기 중 상태 업데이트"""
        phase_korean = {
            'before_market': '장 시작 전',
            'waiting': '거래 시작 대기',
            'lunch_break': '점심시간'
        }
        
        phase_name = phase_korean.get(wait_info['current_phase'], wait_info['current_phase'])
        
        print(f"\n[{wait_info['current_time']}] 📊 {phase_name}")
        print(f"거래 시작 시간: {wait_info['trading_start_time']}")
        print(f"남은 시간: {wait_info['time_until_start']}")
        print(f"대기 지속 시간: {wait_info['wait_duration']}")
        
        # 5분마다 텔레그램 알림
        if hasattr(self, 'telegram_notifier') and self.telegram_notifier:
            wait_duration_parts = wait_info['wait_duration'].split(':')
            if len(wait_duration_parts) >= 2:
                wait_minutes = int(wait_duration_parts[1])
                if wait_minutes % 5 == 0 and wait_minutes > 0:
                    message = f"[{self.account_type}] 거래 시작 대기 중\n"
                    message += f"현재 상태: {phase_name}\n"
                    message += f"거래 시작까지: {wait_info['time_until_start']}"
                    
                    try:
                        await self.telegram_notifier.send_message(message)
                    except Exception as e:
                        logger.warning(f"대기 중 텔레그램 알림 실패: {e}")
    
    async def _execute_gpt_trading_cycle(self, cycle_info: Dict[str, Any]):
        """
        GPT 기반 거래 사이클 실행
        기존 _execute_day_trading_cycle()을 완전 대체
        """
        cycle_number = cycle_info['cycle_number']
        phase = cycle_info['phase']
        start_time = cycle_info['start_time']
        
        logger.info(f"=== GPT 거래 사이클 {cycle_number} 시작 ({phase.value}) ===")
        
        try:
            # 1. 계좌 정보 업데이트
            await self.memory_manager.update_account_info()
            account_info = self.memory_manager.get_account_info()
            
            # 2. 현재 포지션 확인
            current_positions = self._get_current_positions()
            position_count = len(current_positions)
            
            logger.info(f"현재 포지션: {position_count}개, 가용자금: {account_info.get('buyable_cash', 0):,}원")
            
            # 3. GPT 기반 매도 신호 처리 (보유 종목)
            sell_results = await self._process_gpt_sell_signals(current_positions)
            
            # 4. GPT 기반 매수 신호 처리 (신규 종목)
            buy_results = []
            if position_count < self.max_positions:
                buy_results = await self._process_gpt_buy_signals(account_info, current_positions)
            else:
                logger.info(f"최대 포지션 수({self.max_positions}) 도달 - 신규 매수 생략")
            
            # 5. 사이클 결과 정리 및 알림
            cycle_result = {
                'cycle_number': cycle_number,
                'phase': phase.value,
                'timestamp': start_time.strftime('%H:%M:%S'),
                'account_balance': account_info.get('cash_balance', 0),
                'position_count': len(current_positions),
                'sell_count': len([r for r in sell_results if r.get('executed', False)]),
                'buy_count': len([r for r in buy_results if r.get('executed', False)]),
                'gpt_decisions': self.gpt_decisions_made,
                'api_costs': self.gpt_api_costs
            }
            
            await self._send_cycle_result(cycle_result)
            
            logger.info(f"GPT 거래 사이클 {cycle_number} 완료 - "
                       f"매도: {cycle_result['sell_count']}, 매수: {cycle_result['buy_count']}")
            
            return cycle_result
            
        except Exception as e:
            logger.error(f"GPT 거래 사이클 {cycle_number} 실행 오류: {e}")
            raise
    
    async def _process_gpt_sell_signals(self, current_positions: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """GPT 기반 매도 신호 처리"""
        sell_results = []
        
        for stock_code, position in current_positions.items():
            try:
                # 종목 현재 데이터 조회
                stock_data = await self._get_stock_current_data(stock_code)
                if not stock_data:
                    logger.warning(f"{stock_code}: 종목 데이터 조회 실패")
                    continue
                
                # GPT 거래 결정 요청
                gpt_decision = await self.gpt_engine.make_trading_decision(
                    symbol=stock_code,
                    stock_data=stock_data,
                    position_info=position
                )
                
                self.gpt_decisions_made += 1
                self.gpt_api_costs += gpt_decision.api_cost
                
                logger.info(f"{stock_code}: GPT 매도 결정 - {gpt_decision.signal} "
                           f"(신뢰도: {gpt_decision.confidence:.2f})")
                
                # 매도 신호 처리
                if gpt_decision.signal == 'SELL':
                    sell_result = await self._execute_gpt_sell_order(stock_code, position, gpt_decision)
                    sell_results.append(sell_result)
                else:
                    sell_results.append({
                        'stock_code': stock_code,
                        'action': 'HOLD',
                        'reason': gpt_decision.reasoning,
                        'confidence': gpt_decision.confidence,
                        'executed': False
                    })
                
            except Exception as e:
                logger.error(f"{stock_code} GPT 매도 분석 오류: {e}")
                sell_results.append({
                    'stock_code': stock_code,
                    'action': 'ERROR',
                    'reason': f'분석 오류: {str(e)[:50]}',
                    'executed': False
                })
        
        return sell_results
    
    async def _process_gpt_buy_signals(self, account_info: Dict, current_positions: Dict) -> List[Dict[str, Any]]:
        """GPT 기반 매수 신호 처리"""
        buy_results = []
        
        # 급등종목 후보 선별
        candidate_stocks = await self._select_day_trade_candidates(current_positions)
        
        if not candidate_stocks:
            logger.info("매수 후보 종목 없음")
            return buy_results
        
        available_cash = account_info.get('buyable_cash', 0)
        
        for stock_code in candidate_stocks[:10]:  # 상위 10개만 분석
            try:
                # 이미 보유 중인 종목 제외
                if stock_code in current_positions:
                    continue
                
                # 종목 데이터 조회
                stock_data = await self._get_stock_current_data(stock_code)
                if not stock_data:
                    continue
                
                # GPT 거래 결정 요청
                gpt_decision = await self.gpt_engine.make_trading_decision(
                    symbol=stock_code,
                    stock_data=stock_data,
                    position_info=None
                )
                
                self.gpt_decisions_made += 1
                self.gpt_api_costs += gpt_decision.api_cost
                
                logger.info(f"{stock_code}: GPT 매수 결정 - {gpt_decision.signal} "
                           f"(신뢰도: {gpt_decision.confidence:.2f})")
                
                # 매수 신호 처리
                if gpt_decision.signal == 'BUY' and gpt_decision.confidence >= 0.7:
                    buy_result = await self._execute_gpt_buy_order(stock_code, stock_data, gpt_decision, available_cash)
                    buy_results.append(buy_result)
                    
                    # 매수 성공시 가용자금 차감
                    if buy_result.get('executed', False):
                        used_amount = buy_result.get('order_amount', 0)
                        available_cash = max(0, available_cash - used_amount)
                        
                        # 가용자금 부족시 중단
                        if available_cash < 100000:  # 10만원 미만
                            logger.info("가용자금 부족 - 추가 매수 중단")
                            break
                else:
                    buy_results.append({
                        'stock_code': stock_code,
                        'action': 'HOLD',
                        'reason': gpt_decision.reasoning,
                        'confidence': gpt_decision.confidence,
                        'executed': False
                    })
                
            except Exception as e:
                logger.error(f"{stock_code} GPT 매수 분석 오류: {e}")
                buy_results.append({
                    'stock_code': stock_code,
                    'action': 'ERROR',
                    'reason': f'분석 오류: {str(e)[:50]}',
                    'executed': False
                })
        
        return buy_results
    
    async def _execute_gpt_sell_order(self, stock_code: str, position: Dict, 
                                     gpt_decision: TradingDecision) -> Dict[str, Any]:
        """GPT 결정 기반 매도 주문 실행"""
        try:
            quantity = int(position.get('quantity', 0))
            current_price = float(position.get('current_price', 0))
            
            if quantity <= 0:
                return {
                    'stock_code': stock_code,
                    'action': 'SELL_FAILED',
                    'reason': '매도 수량 부족',
                    'executed': False
                }
            
            # 매도 주문 실행 (기존 로직 활용)
            order_result = await self.api.sell_stock(
                stock_code=stock_code,
                quantity=quantity,
                price=int(current_price)
            )
            
            if order_result and order_result.get('rt_cd') == '0':
                # 매도 성공
                result = {
                    'stock_code': stock_code,
                    'action': 'SELL_SUCCESS',
                    'reason': gpt_decision.reasoning,
                    'confidence': gpt_decision.confidence,
                    'quantity': quantity,
                    'price': current_price,
                    'order_amount': quantity * current_price,
                    'gpt_target_price': gpt_decision.target_price,
                    'gpt_stop_loss': gpt_decision.stop_loss,
                    'executed': True
                }
                
                logger.info(f"{stock_code}: GPT 매도 주문 성공 - {quantity:,}주 x {current_price:,}원")
                return result
            else:
                # 매도 실패
                error_msg = order_result.get('msg1', '알 수 없는 오류') if order_result else 'API 호출 실패'
                return {
                    'stock_code': stock_code,
                    'action': 'SELL_FAILED',
                    'reason': f'주문 실패: {error_msg}',
                    'confidence': gpt_decision.confidence,
                    'executed': False
                }
                
        except Exception as e:
            logger.error(f"{stock_code} GPT 매도 주문 실행 오류: {e}")
            return {
                'stock_code': stock_code,
                'action': 'SELL_ERROR',
                'reason': f'실행 오류: {str(e)[:50]}',
                'executed': False
            }
    
    async def _execute_gpt_buy_order(self, stock_code: str, stock_data: Dict, 
                                    gpt_decision: TradingDecision, available_cash: float) -> Dict[str, Any]:
        """GPT 결정 기반 매수 주문 실행"""
        try:
            current_price = float(stock_data['current_price'])
            
            # 포지션 크기 계산 (GPT 추천 비율 적용)
            position_amount = available_cash * gpt_decision.position_size_ratio
            position_amount = min(position_amount, available_cash * 0.1)  # 최대 10% 제한
            
            # 매수 수량 계산
            quantity = int(position_amount // current_price)
            
            if quantity <= 0:
                return {
                    'stock_code': stock_code,
                    'action': 'BUY_FAILED',
                    'reason': '매수 수량 부족',
                    'executed': False
                }
            
            # 매수 주문 실행
            order_result = await self.api.buy_stock(
                stock_code=stock_code,
                quantity=quantity,
                price=int(current_price)
            )
            
            if order_result and order_result.get('rt_cd') == '0':
                # 매수 성공
                order_amount = quantity * current_price
                
                result = {
                    'stock_code': stock_code,
                    'action': 'BUY_SUCCESS',
                    'reason': gpt_decision.reasoning,
                    'confidence': gpt_decision.confidence,
                    'quantity': quantity,
                    'price': current_price,
                    'order_amount': order_amount,
                    'gpt_target_price': gpt_decision.target_price,
                    'gpt_stop_loss': gpt_decision.stop_loss,
                    'position_ratio': gpt_decision.position_size_ratio,
                    'executed': True
                }
                
                logger.info(f"{stock_code}: GPT 매수 주문 성공 - {quantity:,}주 x {current_price:,}원 "
                           f"(목표가: {gpt_decision.target_price:,.0f}원)")
                
                return result
            else:
                # 매수 실패
                error_msg = order_result.get('msg1', '알 수 없는 오류') if order_result else 'API 호출 실패'
                return {
                    'stock_code': stock_code,
                    'action': 'BUY_FAILED',
                    'reason': f'주문 실패: {error_msg}',
                    'confidence': gpt_decision.confidence,
                    'executed': False
                }
                
        except Exception as e:
            logger.error(f"{stock_code} GPT 매수 주문 실행 오류: {e}")
            return {
                'stock_code': stock_code,
                'action': 'BUY_ERROR',
                'reason': f'실행 오류: {str(e)[:50]}',
                'executed': False
            }
    
    def _get_current_positions(self) -> Dict[str, Dict]:
        """현재 포지션 정보 조회"""
        positions_list = self.memory_manager.get_positions()
        positions_dict = {}
        
        for position in positions_list:
            if isinstance(position, dict):
                stock_code = position.get('stock_code') or position.get('symbol')
                if stock_code:
                    positions_dict[stock_code] = position
        
        return positions_dict
    
    async def _send_cycle_result(self, cycle_result: Dict[str, Any]):
        """사이클 결과 전송 (텔레그램 등)"""
        try:
            if hasattr(self, 'telegram_notifier') and self.telegram_notifier:
                message = f"[{self.account_type}] GPT 거래 사이클 {cycle_result['cycle_number']} 완료\n"
                message += f"시간: {cycle_result['timestamp']} ({cycle_result['phase']})\n"
                message += f"잔고: {cycle_result['account_balance']:,}원\n"
                message += f"포지션: {cycle_result['position_count']}개\n"
                message += f"매도/매수: {cycle_result['sell_count']}/{cycle_result['buy_count']}\n"
                message += f"GPT 결정: {cycle_result['gpt_decisions']}회 (비용: ${cycle_result['api_costs']:.3f})"
                
                await self.telegram_notifier.send_message(message)
                
        except Exception as e:
            logger.warning(f"사이클 결과 알림 전송 실패: {e}")
    
    async def _on_trading_session_end(self, session_info: Dict[str, Any]):
        """거래 세션 종료 처리"""
        logger.info(f"GPT 거래 세션 종료 - 총 {session_info['total_cycles']}개 사이클 완료")
        
        # GPT 사용 통계
        gpt_stats = self.gpt_engine.get_performance_stats()
        
        final_message = f"[{self.account_type}] GPT 단타매매 세션 종료\n"
        final_message += f"총 사이클: {session_info['total_cycles']}회\n"
        final_message += f"GPT 결정: {self.gpt_decisions_made}회\n"
        final_message += f"API 비용: ${self.gpt_api_costs:.3f}\n"
        final_message += f"평균 응답시간: {gpt_stats.get('avg_response_time', 0):.1f}초\n"
        final_message += f"성공률: {gpt_stats.get('success_rate', 0):.1f}%"
        
        if hasattr(self, 'telegram_notifier') and self.telegram_notifier:
            try:
                await self.telegram_notifier.send_message(final_message)
            except Exception as e:
                logger.warning(f"세션 종료 알림 전송 실패: {e}")
    
    def get_gpt_stats(self) -> Dict[str, Any]:
        """GPT 사용 통계 반환"""
        gpt_engine_stats = self.gpt_engine.get_performance_stats()
        time_manager_stats = self.time_manager.get_trading_status()
        
        return {
            'gpt_decisions_made': self.gpt_decisions_made,
            'gpt_api_costs': self.gpt_api_costs,
            'gpt_engine_stats': gpt_engine_stats,
            'time_manager_stats': time_manager_stats,
            'volume_validator_stats': self.volume_validator.get_volume_analysis_summary()
        }

# 편의 함수
async def run_integrated_gpt_trader(account_type: str = "REAL", openai_api_key: str = None):
    """통합 GPT 거래 시스템 실행 함수"""
    trader = IntegratedGPTTrader(account_type=account_type, openai_api_key=openai_api_key)
    return await trader.run()

if __name__ == "__main__":
    # 테스트 실행
    import asyncio
    
    async def test_gpt_trader():
        # 환경변수나 설정 파일에서 API 키 로드 필요
        api_key = "your_openai_api_key_here"
        
        success = await run_integrated_gpt_trader(
            account_type="MOCK",  # 테스트는 모의투자로
            openai_api_key=api_key
        )
        
        print(f"GPT 거래 시스템 실행 결과: {'성공' if success else '실패'}")
    
    # asyncio.run(test_gpt_trader())