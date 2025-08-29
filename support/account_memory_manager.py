#!/usr/bin/env python3
"""
AccountMemoryManager - 계좌 정보 메모리 관리 시스템
백그라운드에서 계좌 정보를 조회하고 메모리에 저장/관리
실시간 계좌 업데이트 및 동기화 담당
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


@dataclass
class AccountSnapshot:
    """계좌 스냅샷 데이터 클래스"""
    timestamp: datetime
    account_type: str  # "REAL" or "MOCK"
    account_number: str = ""  # 계좌번호
    cash_balance: float = 0.0  # 예수금
    available_cash: float = 0.0  # 주문가능금액
    total_evaluation: float = 0.0  # 총평가금액
    profit_loss: float = 0.0  # 총손익
    profit_rate: float = 0.0  # 수익률
    holdings: List[Dict] = field(default_factory=list)  # 보유종목 리스트
    pending_orders: List[Dict] = field(default_factory=list)  # 미체결 주문
    raw_data: Dict = field(default_factory=dict)  # 원본 API 응답 데이터
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'account_type': self.account_type,
            'account_number': self.account_number,
            'cash_balance': self.cash_balance,
            'available_cash': self.available_cash,
            'total_evaluation': self.total_evaluation,
            'profit_loss': self.profit_loss,
            'profit_rate': self.profit_rate,
            'holdings_count': len(self.holdings),
            'pending_orders_count': len(self.pending_orders)
        }


class AccountMemoryManager:
    """계좌 정보 메모리 관리자"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """초기화"""
        if not self._initialized:
            self.real_account: Optional[AccountSnapshot] = None
            self.mock_account: Optional[AccountSnapshot] = None
            self.update_lock = asyncio.Lock()
            self.background_task: Optional[asyncio.Task] = None
            self.is_running = False
            self.update_interval = 300  # 5분 주기 백그라운드 업데이트
            self.last_update_time = {
                "REAL": None,
                "MOCK": None
            }
            self.update_callbacks = []  # 업데이트 시 호출할 콜백 함수들
            self._initialized = True
            logger.info("AccountMemoryManager 초기화 완료")
    
    async def initialize_accounts(self, api_real=None, api_mock=None):
        """계좌 초기화 및 백그라운드 작업 시작
        
        Args:
            api_real: 실계좌 API 인스턴스
            api_mock: 모의계좌 API 인스턴스
        """
        try:
            logger.info("계좌 정보 초기화 시작")
            
            # 실계좌 정보 조회
            if api_real:
                await self.update_account("REAL", api_real)
                logger.info("계좌 정보 초기화 완료")
            
            # 모의계좌 정보 조회
            if api_mock:
                await self.update_account("MOCK", api_mock)
                logger.info("계좌 정보 초기화 완료")
            
            # 백그라운드 업데이트 태스크 시작
            if not self.background_task or self.background_task.done():
                self.background_task = asyncio.create_task(
                    self._background_update_loop(api_real, api_mock)
                )
                logger.info("백그라운드 계좌 업데이트 시작")
            
        except Exception as e:
            logger.error(f"계좌 초기화 오류: {e}")
            raise
    
    async def update_account(self, account_type: str, api_instance, force: bool = False):
        """계좌 정보 업데이트
        
        Args:
            account_type: "REAL" or "MOCK"
            api_instance: KISAPIConnector 인스턴스
            force: 강제 업데이트 여부
        """
        async with self.update_lock:
            try:
                # 최근 업데이트 체크 (1초 이내 재요청 방지)
                if not force and self.last_update_time.get(account_type):
                    time_diff = (datetime.now() - self.last_update_time[account_type]).total_seconds()
                    if time_diff < 1:
                        logger.debug(f"계좌 업데이트 스킵 (최근 업데이트: {time_diff:.1f}초 전)")
                        return
                
                logger.info("계좌 정보 업데이트 시작")
                
                # API 호출하여 계좌 정보 조회
                account_data = await api_instance.get_account_balance(force_refresh=True)
                
                if not account_data:
                    logger.warning(f"{account_type} 계좌 정보 조회 실패")
                    return
                
                # AccountSnapshot 생성
                snapshot = self._create_snapshot(account_type, account_data, api_instance)
                
                # 메모리에 저장
                if account_type == "REAL":
                    self.real_account = snapshot
                else:
                    self.mock_account = snapshot
                
                self.last_update_time[account_type] = datetime.now()
                
                # 콜백 함수 호출
                await self._notify_callbacks(account_type, snapshot)
                
                logger.info(f"계좌 업데이트 완료 - 잔고: {snapshot.cash_balance:,.0f}원")
                
            except Exception as e:
                logger.error(f"계좌 업데이트 오류: {e}")
    
    def _create_snapshot(self, account_type: str, account_data: Dict, api_instance=None) -> AccountSnapshot:
        """API 응답 데이터로부터 AccountSnapshot 생성"""
        try:
            # 계좌번호 추출
            account_number = ""
            if api_instance:
                account_number = getattr(api_instance, 'account_number', api_instance.config.get("CANO", ""))
            
            # 예수금 정보 검증 및 추출
            if 'dnca_tot_amt' not in account_data:
                raise Exception("API 응답에 예수금(dnca_tot_amt) 정보가 없습니다")
            if 'ord_psbl_cash' not in account_data:
                raise Exception("API 응답에 주문가능현금(ord_psbl_cash) 정보가 없습니다")
                
            cash_balance = float(account_data['dnca_tot_amt'])
            available_cash = float(account_data['ord_psbl_cash'])
            
            # 보유종목 정보
            holdings = []
            output1 = account_data.get('output1', [])
            
            total_evaluation = cash_balance
            total_profit_loss = 0.0
            
            for item in output1:
                if 'hldg_qty' not in item:
                    continue  # 보유수량 정보가 없는 경우 건너뛰기
                    
                quantity = int(item['hldg_qty'])
                if quantity > 0:
                    if 'pdno' not in item:
                        raise Exception("보유종목에 종목코드(pdno) 정보가 없습니다")
                    if 'prdt_name' not in item:
                        raise Exception("보유종목에 종목명(prdt_name) 정보가 없습니다")
                        
                    holding = {
                        'stock_code': item['pdno'],
                        'stock_name': item['prdt_name'],
                        'quantity': quantity,
                        'avg_price': float(item.get('pchs_avg_pric', '0')),
                        'current_price': float(item.get('prpr', '0')),
                        'evaluation': float(item.get('evlu_amt', '0')),
                        'profit_loss': float(item.get('evlu_pfls_amt', '0')),
                        'profit_rate': float(item.get('evlu_pfls_rt', '0'))
                    }
                    holdings.append(holding)
                    total_evaluation += holding['evaluation']
                    total_profit_loss += holding['profit_loss']
            
            # 수익률 계산
            profit_rate = 0.0
            if total_evaluation > 0:
                profit_rate = (total_profit_loss / (total_evaluation - total_profit_loss)) * 100
            
            return AccountSnapshot(
                timestamp=datetime.now(),
                account_type=account_type,
                account_number=account_number,
                cash_balance=cash_balance,
                available_cash=available_cash,
                total_evaluation=total_evaluation,
                profit_loss=total_profit_loss,
                profit_rate=profit_rate,
                holdings=holdings,
                pending_orders=[],  # 미체결 주문은 별도 API 필요
                raw_data=account_data
            )
            
        except Exception as e:
            logger.error(f"스냅샷 생성 오류: {e}")
            # 오류 시 기본 스냅샷 반환
            account_number = ""
            if api_instance:
                account_number = getattr(api_instance, 'account_number', api_instance.config.get("CANO", ""))
            
            return AccountSnapshot(
                timestamp=datetime.now(),
                account_type=account_type,
                account_number=account_number,
                raw_data=account_data
            )
    
    async def _background_update_loop(self, api_real=None, api_mock=None):
        """백그라운드 계좌 업데이트 루프"""
        self.is_running = True
        logger.info("백그라운드 계좌 업데이트 루프 시작")
        
        while self.is_running:
            try:
                # 5분마다 업데이트
                await asyncio.sleep(self.update_interval)
                
                if api_real:
                    await self.update_account("REAL", api_real)
                
                if api_mock:
                    await self.update_account("MOCK", api_mock)
                
                logger.debug("백그라운드 계좌 업데이트 완료")
                
            except asyncio.CancelledError:
                logger.info("백그라운드 업데이트 취소됨")
                break
            except Exception as e:
                logger.error(f"백그라운드 업데이트 오류: {e}")
                await asyncio.sleep(30)  # 오류 시 30초 대기
    
    async def update_after_trade(self, account_type: str, api_instance, trade_type: str, trade_info: Dict):
        """매수/매도 후 즉시 계좌 업데이트
        
        Args:
            account_type: "REAL" or "MOCK"
            api_instance: API 인스턴스
            trade_type: "BUY" or "SELL"
            trade_info: 거래 정보
        """
        logger.info(f"{account_type} {trade_type} 거래 후 계좌 업데이트")
        
        # 거래 직후 짧은 대기 (체결 처리 시간)
        await asyncio.sleep(0.5)
        
        # 계좌 정보 강제 업데이트
        await self.update_account(account_type, api_instance, force=True)
        
        # 거래 로그 기록
        self._log_trade(account_type, trade_type, trade_info)
    
    def _log_trade(self, account_type: str, trade_type: str, trade_info: Dict):
        """거래 로그 기록"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'account_type': account_type,
                'trade_type': trade_type,
                'stock_code': trade_info.get('stock_code'),
                'stock_name': trade_info.get('stock_name'),
                'quantity': trade_info.get('quantity'),
                'price': trade_info.get('price'),
                'amount': trade_info.get('amount')
            }
            logger.info(f"거래 기록: {json.dumps(log_entry, ensure_ascii=False)}")
        except Exception as e:
            logger.error(f"거래 로그 기록 오류: {e}")
    
    def get_account(self, account_type: str) -> Optional[AccountSnapshot]:
        """계좌 정보 조회
        
        Args:
            account_type: "REAL" or "MOCK"
            
        Returns:
            AccountSnapshot or None
        """
        if account_type == "REAL":
            return self.real_account
        elif account_type == "MOCK":
            return self.mock_account
        return None
    
    def get_holdings(self, account_type: str) -> List[Dict]:
        """보유종목 조회"""
        account = self.get_account(account_type)
        return account.holdings if account else []
    
    def get_cash_balance(self, account_type: str) -> float:
        """예수금 조회"""
        account = self.get_account(account_type)
        return account.cash_balance if account else 0.0
    
    def get_available_cash(self, account_type: str) -> float:
        """주문가능금액 조회"""
        account = self.get_account(account_type)
        return account.available_cash if account else 0.0
    
    def register_callback(self, callback):
        """업데이트 콜백 등록"""
        if callback not in self.update_callbacks:
            self.update_callbacks.append(callback)
            logger.debug(f"콜백 등록: {callback.__name__}")
    
    async def _notify_callbacks(self, account_type: str, snapshot: AccountSnapshot):
        """등록된 콜백 함수들 호출"""
        for callback in self.update_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(account_type, snapshot)
                else:
                    callback(account_type, snapshot)
            except Exception as e:
                logger.error(f"콜백 실행 오류: {e}")
    
    async def stop(self):
        """백그라운드 작업 중지"""
        self.is_running = False
        if self.background_task and not self.background_task.done():
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
        logger.info("AccountMemoryManager 중지됨")
    
    def get_summary(self) -> Dict:
        """계좌 요약 정보 반환"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'real_account': None,
            'mock_account': None
        }
        
        if self.real_account:
            summary['real_account'] = self.real_account.to_dict()
        
        if self.mock_account:
            summary['mock_account'] = self.mock_account.to_dict()
        
        return summary
    
    def get_pending_orders_count(self, account_type: str) -> int:
        """미체결 주문 수 반환
        
        Args:
            account_type: "REAL" or "MOCK"
            
        Returns:
            미체결 주문 수
        """
        account = self.get_account(account_type)
        if account and account.pending_orders:
            return len(account.pending_orders)
        return 0
    
    def get_positions(self, account_type: str) -> List[Dict]:
        """보유 포지션(종목) 정보 반환
        
        Args:
            account_type: "REAL" or "MOCK"
            
        Returns:
            보유종목 리스트
        """
        account = self.get_account(account_type)
        if account and account.holdings:
            return account.holdings
        return []
    
    def has_position(self, account_type: str, stock_code: str) -> bool:
        """특정 종목 보유 여부 확인
        
        Args:
            account_type: "REAL" or "MOCK"
            stock_code: 종목코드
            
        Returns:
            보유 여부
        """
        positions = self.get_positions(account_type)
        for position in positions:
            if position.get('stock_code') == stock_code:
                return True
        return False
    
    def get_position_quantity(self, account_type: str, stock_code: str) -> int:
        """특정 종목 보유 수량 반환
        
        Args:
            account_type: "REAL" or "MOCK"
            stock_code: 종목코드
            
        Returns:
            보유 수량
        """
        positions = self.get_positions(account_type)
        for position in positions:
            if position.get('stock_code') == stock_code:
                return position.get('quantity', 0)
        return 0


# 싱글톤 인스턴스 getter
def get_account_memory_manager() -> AccountMemoryManager:
    """AccountMemoryManager 싱글톤 인스턴스 반환"""
    return AccountMemoryManager()