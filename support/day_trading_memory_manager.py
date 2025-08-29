#!/usr/bin/env python3
"""
DayTradingMemoryManager - 단타매매 전용 메모리 기반 계좌 관리
API 호출을 최소화하고 메모리 기반으로 계좌 정보를 관리
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class DayTradingMemoryManager:
    """단타매매용 메모리 기반 계좌 정보 관리"""
    
    def __init__(self, api_connector, account_type: str):
        """
        DayTradingMemoryManager 초기화
        
        Args:
            api_connector: API 연결 객체
            account_type: 계좌 유형 ("REAL" 또는 "MOCK")
        """
        self.api = api_connector
        self.account_type = account_type
        
        # 메모리 저장소
        self.account_memory = {
            'cash_balance': 0,                    # 현금 잔고
            'total_balance': 0,                   # 총 자산
            'buyable_cash': 0,                    # 매수 가능 현금
            'positions': {},                      # 보유 종목 {종목코드: {수량, 평균단가, 평가손익}}
            'last_update': None,                  # 마지막 업데이트 시간
            'cycle_count': 0                      # 사이클 카운트
        }
        
        # 단타매매 세션 통계
        self.session_stats = {
            'total_trades': 0,                    # 총 거래 수
            'successful_trades': 0,               # 성공한 거래
            'total_profit': 0,                    # 총 손익
            'start_balance': 0,                   # 시작 잔고
            'max_positions': 0,                   # 최대 동시 보유 종목 수
            'session_start': datetime.now()       # 세션 시작 시간
        }
        
        # 캐시 유효성 관리
        self.cache_duration = 30  # 캐시 유효 시간 (초)
        
        logger.info(f"DayTradingMemoryManager 초기화 ({account_type})")
    
    async def initial_account_load(self) -> bool:
        """초기 계좌 정보 로드 및 메모리 저장"""
        try:
            logger.info("초기 계좌 정보 로드 시작")
            
            # 계좌 잔고 정보 조회
            balance_info = await self._fetch_account_balance()
            if not balance_info:
                logger.error("계좌 잔고 정보 조회 실패")
                return False
            
            # 보유 종목 정보 조회
            positions_info = await self._fetch_positions()
            
            # 메모리에 저장
            self.account_memory.update({
                'cash_balance': balance_info.get('cash_balance', 0),
                'total_balance': balance_info.get('total_balance', 0),
                'buyable_cash': balance_info.get('buyable_cash', 0),
                'positions': positions_info or {},
                'last_update': datetime.now(),
                'cycle_count': 0
            })
            
            # 세션 시작 잔고 기록
            self.session_stats['start_balance'] = self.account_memory['cash_balance']
            
            logger.info(f"초기 계좌 로드 완료 - 현금잔고: {self.account_memory['cash_balance']:,}원")
            logger.info(f"보유 종목 수: {len(self.account_memory['positions'])}")
            
            return True
            
        except Exception as e:
            logger.error(f"초기 계좌 로드 오류: {e}")
            return False
    
    async def update_account_info(self) -> bool:
        """계좌 정보 업데이트 (사이클마다 실행)"""
        try:
            logger.info(f"계좌 정보 업데이트 시작 (사이클 {self.account_memory['cycle_count'] + 1})")
            
            # 최신 계좌 잔고 조회
            balance_info = await self._fetch_account_balance()
            if balance_info:
                self.account_memory.update({
                    'cash_balance': balance_info.get('cash_balance', self.account_memory['cash_balance']),
                    'total_balance': balance_info.get('total_balance', self.account_memory['total_balance']),
                    'buyable_cash': balance_info.get('buyable_cash', self.account_memory['buyable_cash'])
                })
            
            # 보유 종목 정보 업데이트
            positions_info = await self._fetch_positions()
            if positions_info is not None:
                self.account_memory['positions'] = positions_info
            
            # 업데이트 시간 갱신
            self.account_memory['last_update'] = datetime.now()
            self.account_memory['cycle_count'] += 1
            
            # 통계 업데이트
            current_positions = len(self.account_memory['positions'])
            if current_positions > self.session_stats['max_positions']:
                self.session_stats['max_positions'] = current_positions
            
            logger.info(f"계좌 정보 업데이트 완료 - 현금: {self.account_memory['cash_balance']:,}원, 종목수: {current_positions}")
            
            return True
            
        except Exception as e:
            logger.error(f"계좌 정보 업데이트 오류: {e}")
            return False
    
    def get_account_info(self) -> Dict[str, Any]:
        """메모리에서 계좌 정보 조회"""
        return self.account_memory.copy()
    
    def get_cash_balance(self) -> float:
        """현금 잔고 조회"""
        return self.account_memory.get('cash_balance', 0)
    
    def get_buyable_cash(self) -> float:
        """매수 가능 현금 조회"""
        return self.account_memory.get('buyable_cash', 0)
    
    def get_positions(self) -> Dict[str, Dict]:
        """보유 종목 정보 조회"""
        return self.account_memory.get('positions', {}).copy()
    
    def get_position_count(self) -> int:
        """보유 종목 수 조회"""
        return len(self.account_memory.get('positions', {}))
    
    def has_position(self, symbol: str) -> bool:
        """특정 종목 보유 여부 확인"""
        return symbol in self.account_memory.get('positions', {})
    
    def get_session_stats(self) -> Dict[str, Any]:
        """세션 통계 정보 조회"""
        current_stats = self.session_stats.copy()
        
        # 현재 수익률 계산
        current_balance = self.account_memory.get('cash_balance', 0)
        start_balance = self.session_stats.get('start_balance', 1)
        
        if start_balance > 0:
            current_stats['return_rate'] = ((current_balance - start_balance) / start_balance) * 100
            current_stats['net_profit'] = current_balance - start_balance
        else:
            current_stats['return_rate'] = 0
            current_stats['net_profit'] = 0
        
        # 세션 경과 시간
        session_elapsed = datetime.now() - self.session_stats['session_start']
        current_stats['session_duration'] = str(session_elapsed).split('.')[0]  # 소수점 제거
        
        return current_stats
    
    def update_trade_stats(self, trade_result: Dict[str, Any]):
        """거래 통계 업데이트"""
        try:
            if trade_result.get('executed', False):
                self.session_stats['total_trades'] += 1
                
                if trade_result.get('profit', 0) > 0:
                    self.session_stats['successful_trades'] += 1
                
                profit = trade_result.get('profit', 0)
                self.session_stats['total_profit'] += profit
                
                logger.info(f"거래 통계 업데이트 - 총 거래: {self.session_stats['total_trades']}, "
                          f"성공: {self.session_stats['successful_trades']}, 누적손익: {self.session_stats['total_profit']:,}")
        except Exception as e:
            logger.warning(f"거래 통계 업데이트 오류 (무시): {e}")
    
    async def _fetch_account_balance(self) -> Optional[Dict[str, Any]]:
        """API를 통해 계좌 잔고 조회"""
        try:
            if hasattr(self.api, 'get_account_balance'):
                balance_data = await self.api.get_account_balance()
                
                if balance_data:
                    # API 응답 필수 데이터 검증
                    if 'dnca_tot_amt' not in balance_data:
                        raise Exception("API 응답에 예수금총액(dnca_tot_amt) 정보가 없습니다")
                    if 'ord_psbl_cash' not in balance_data:
                        raise Exception("API 응답에 주문가능현금(ord_psbl_cash) 정보가 없습니다")
                    
                    # KISAPIConnector의 get_account_balance는 이미 처리된 데이터를 반환
                    return {
                        'cash_balance': float(balance_data['dnca_tot_amt']),  # 예수금총액
                        'total_balance': float(balance_data.get('tot_evlu_amt', balance_data['dnca_tot_amt'])),  # 총평가금액
                        'buyable_cash': float(balance_data['ord_psbl_cash'])   # 주문가능현금
                    }
            
            logger.warning("잔고 조회 API 응답이 올바르지 않음")
            return None
            
        except Exception as e:
            logger.error(f"잔고 조회 API 오류: {e}")
            return None
    
    async def _fetch_positions(self) -> Optional[Dict[str, Dict]]:
        """API를 통해 보유 종목 조회"""
        try:
            positions = {}
            
            if hasattr(self.api, 'get_account_balance'):
                balance_data = await self.api.get_account_balance()
                
                if balance_data:
                    # KISAPIConnector의 get_account_balance는 output1 데이터도 포함
                    output1_list = balance_data.get('output1', [])
                    
                    for position in output1_list:
                        if 'pdno' not in position or 'hldg_qty' not in position:
                            continue  # 필수 정보가 없는 경우 건너뛰기
                            
                        symbol = position['pdno']
                        quantity = int(position['hldg_qty'])
                        
                        if symbol and quantity > 0:
                            positions[symbol] = {
                                'quantity': quantity,
                                'avg_price': float(position.get('pchs_avg_pric', '0')),
                                'current_price': float(position.get('prpr', '0')),
                                'eval_profit': float(position.get('evlu_pfls_amt', '0')),
                                'name': position.get('prdt_name', symbol)
                            }
            
            return positions
            
        except Exception as e:
            logger.error(f"보유 종목 조회 오류: {e}")
            return None
    
    def is_cache_valid(self) -> bool:
        """캐시 유효성 확인"""
        if not self.account_memory.get('last_update'):
            return False
        
        elapsed = (datetime.now() - self.account_memory['last_update']).total_seconds()
        return elapsed < self.cache_duration
    
    def clear_cache(self):
        """캐시 초기화"""
        logger.info("메모리 캐시 초기화")
        self.account_memory.update({
            'cash_balance': 0,
            'total_balance': 0,
            'buyable_cash': 0,
            'positions': {},
            'last_update': None,
            'cycle_count': 0
        })


def get_day_trading_memory_manager(api_connector, account_type: str) -> DayTradingMemoryManager:
    """DayTradingMemoryManager 인스턴스 생성 팩토리 함수"""
    return DayTradingMemoryManager(api_connector, account_type)