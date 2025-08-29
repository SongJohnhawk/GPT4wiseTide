#!/usr/bin/env python3
"""
DayTradingAccountManager - 단타매매 세션 계좌 정보 관리
매매 세션 동안만 임시로 계좌 정보를 보관하여 성능과 실시간성을 균형있게 관리
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

# 로그 매니저를 통한 로거 설정
from support.log_manager import get_log_manager
log_manager = get_log_manager()
logger = log_manager.setup_logger('system', __name__)


class DayTradingAccountManager:
    """단타매매 세션 전용 계좌 정보 관리자"""
    
    def __init__(self, api_connector):
        """
        단타매매 세션용 계좌 관리자 초기화
        
        Args:
            api_connector: KIS API 커넥터 인스턴스
        """
        self.api_connector = api_connector
        
        # 세션 기반 임시 계좌 정보
        self._session_account_info = None
        self._last_updated = None
        self._session_active = False
        
        # 매매 후 자동 갱신 플래그
        self._auto_refresh_after_trade = True
        
        logger.info(f"단타매매 계좌 관리자 초기화: {'모의투자' if api_connector.is_mock else '실전투자'}")
    
    def start_session(self):
        """단타매매 세션 시작"""
        self._session_active = True
        self._session_account_info = None
        self._last_updated = None
        logger.info("단타매매 세션 시작 - 계좌 정보 초기화")
    
    def end_session(self):
        """단타매매 세션 종료"""
        self._session_active = False
        last_update_time = self._last_updated.strftime("%H:%M:%S") if self._last_updated else "없음"
        logger.info(f"단타매매 세션 종료 - 마지막 계좌 갱신: {last_update_time}")
        
        # 세션 종료 시에는 정보를 즉시 정리하지 않음 (다음날까지 유지)
        # self._session_account_info = None  # 주석 처리
    
    async def get_account_info(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        계좌 정보 조회 (세션 기반 최적화)
        
        Args:
            force_refresh: 강제 갱신 여부
            
        Returns:
            계좌 정보 또는 None
        """
        # 세션이 비활성화된 경우 또는 강제 갱신인 경우 실시간 조회
        if not self._session_active or force_refresh:
            logger.debug("세션 비활성화 또는 강제 갱신 - 실시간 계좌 조회")
            return await self._refresh_account_info()
        
        # 세션 중이고 임시 정보가 있는 경우 사용
        if self._session_account_info is not None:
            age = datetime.now() - self._last_updated if self._last_updated else timedelta(0)
            logger.debug(f"세션 계좌 정보 사용 (갱신 후 {age.total_seconds():.1f}초 경과)")
            return self._session_account_info
        
        # 세션 중이지만 정보가 없는 경우 최초 조회
        logger.debug("세션 중 최초 계좌 정보 조회")
        return await self._refresh_account_info()
    
    async def update_account_info(self) -> Optional[Dict[str, Any]]:
        """계좌 정보 강제 업데이트 (외부 호출용)"""
        return await self._refresh_account_info()
    
    async def _refresh_account_info(self) -> Optional[Dict[str, Any]]:
        """계좌 정보 실시간 조회 및 세션 정보 갱신"""
        try:
            # 실시간 계좌 조회 (캐시 사용 안 함)
            account_info = await self.api_connector.get_account_balance(force_refresh=True)
            
            if account_info:
                # 세션 정보 갱신
                self._session_account_info = account_info
                self._last_updated = datetime.now()
                
                # 주요 계좌 정보 로깅 및 검증
                if 'dnca_tot_amt' not in account_info:
                    raise Exception("API 응답에 예수금 정보(dnca_tot_amt)가 없습니다")
                if 'ord_psbl_cash' not in account_info:
                    raise Exception("API 응답에 주문가능금액 정보(ord_psbl_cash)가 없습니다")
                    
                cash_balance = float(account_info['dnca_tot_amt'])
                available_cash = float(account_info['ord_psbl_cash'])
                holdings_count = len([h for h in account_info.get('output1', []) 
                                    if int(h.get('hldg_qty', '0')) > 0])
                
                logger.info(f"계좌 정보 갱신 완료: 예수금 {cash_balance:,.0f}원, "
                           f"주문가능금액 {available_cash:,.0f}원, 보유종목 {holdings_count}개")
                
                return account_info
            else:
                logger.warning("계좌 정보 조회 실패")
                return None
                
        except Exception as e:
            logger.error(f"계좌 정보 갱신 중 오류: {e}")
            return None
    
    async def notify_trade_completed(self, trade_type: str, symbol: str, result: bool):
        """
        매매 완료 알림 및 자동 계좌 갱신
        
        Args:
            trade_type: 매매 유형 ("BUY" 또는 "SELL")
            symbol: 종목코드
            result: 매매 성공 여부
        """
        if not self._auto_refresh_after_trade or not result:
            return
        
        logger.info(f"{trade_type} 매매 완료 ({symbol}) - 계좌 정보 자동 갱신 시작")
        
        # 매매 완료 후 잠시 대기 (서버 반영 시간)
        await asyncio.sleep(2)
        
        # 계좌 정보 갱신
        await self._refresh_account_info()
    
    def get_session_status(self) -> Dict[str, Any]:
        """세션 상태 정보 반환"""
        return {
            'session_active': self._session_active,
            'has_account_info': self._session_account_info is not None,
            'last_updated': self._last_updated.isoformat() if self._last_updated else None,
            'auto_refresh': self._auto_refresh_after_trade
        }
    
    def is_session_active(self) -> bool:
        """세션 활성 상태 확인"""
        return self._session_active
    
    def has_valid_account_info(self) -> bool:
        """유효한 계좌 정보 보유 여부 확인"""
        return self._session_account_info is not None


# 전역 인스턴스 관리
_day_trading_account_manager = None


def get_day_trading_account_manager(api_connector=None):
    """단타매매 계좌 관리자 인스턴스 반환 (싱글톤)"""
    global _day_trading_account_manager
    
    if _day_trading_account_manager is None:
        if api_connector is None:
            raise ValueError("최초 호출 시 api_connector가 필요합니다")
        _day_trading_account_manager = DayTradingAccountManager(api_connector)
    
    return _day_trading_account_manager


def reset_day_trading_account_manager():
    """단타매매 계좌 관리자 리셋 (다음날 시작 시 호출)"""
    global _day_trading_account_manager
    _day_trading_account_manager = None
    logger.info("단타매매 계좌 관리자 리셋 완료")