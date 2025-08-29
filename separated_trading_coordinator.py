#!/usr/bin/env python3
"""
분리된 매매 시스템 조정자 (Separated Trading Coordinator)
- 일반 단타매매와 사용자 지정종목 매매를 분리하여 관리
- 각각 독립적으로 실행 가능하도록 조정
- 실시간성과 성능을 보장하면서 매매 시스템 관리
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, time
from pathlib import Path

logger = logging.getLogger(__name__)


class SeparatedTradingCoordinator:
    """분리된 매매 시스템 조정자"""
    
    def __init__(self, api_connector, account_type: str = "REAL"):
        """
        SeparatedTradingCoordinator 초기화
        
        Args:
            api_connector: API 연결 객체
            account_type: 계좌 유형 ("REAL" 또는 "MOCK")
        """
        self.api = api_connector
        self.account_type = account_type
        self.account_display = "실전투자" if account_type == "REAL" else "모의투자"
        
        # 매매 상태 추적
        self.day_trading_active = False
        self.user_designated_active = False
        
        # 마지막 실행 시간
        self.last_day_trading_time = None
        self.last_user_designated_time = None
        
        logger.info(f"분리된 매매 조정자 초기화: {self.account_display}")
    
    async def start_day_trading_session(self) -> bool:
        """일반 단타매매 세션 시작"""
        try:
            logger.info(f"[{self.account_display}] 일반 단타매매 세션 시작")
            
            # 세션 기반 계좌 관리자 초기화
            from support.day_trading_account_manager import get_day_trading_account_manager
            account_manager = get_day_trading_account_manager(self.api)
            account_manager.start_session()
            
            self.day_trading_active = True
            self.last_day_trading_time = datetime.now()
            
            logger.info(f"[{self.account_display}] 일반 단타매매 세션 시작 완료")
            return True
            
        except Exception as e:
            logger.error(f"일반 단타매매 세션 시작 실패: {e}")
            return False
    
    async def stop_day_trading_session(self) -> bool:
        """일반 단타매매 세션 종료"""
        try:
            logger.info(f"[{self.account_display}] 일반 단타매매 세션 종료")
            
            # 세션 기반 계좌 관리자 종료
            from support.day_trading_account_manager import get_day_trading_account_manager
            account_manager = get_day_trading_account_manager(self.api)
            account_manager.end_session()
            
            self.day_trading_active = False
            
            logger.info(f"[{self.account_display}] 일반 단타매매 세션 종료 완료")
            return True
            
        except Exception as e:
            logger.error(f"일반 단타매매 세션 종료 실패: {e}")
            return False
    
    async def execute_user_designated_trading_only(self, execution_type: str = "MANUAL") -> Dict[str, Any]:
        """
        사용자 지정종목 매매만 독립 실행
        
        Args:
            execution_type: 실행 유형 ("MANUAL", "LUNCH", "AUTO")
            
        Returns:
            Dict: 실행 결과
        """
        try:
            logger.info(f"[{self.account_display}] 사용자 지정종목 독립 매매 시작 ({execution_type})")
            
            # 사용자 지정종목 매매 관리자 로드
            from support.user_designated_trading_manager import UserDesignatedTradingManager
            user_trading_manager = UserDesignatedTradingManager(self.api, self.account_type)
            
            # 사용자 지정종목 매매 실행
            result = await user_trading_manager.execute_user_designated_trading(execution_type)
            
            self.user_designated_active = True
            self.last_user_designated_time = datetime.now()
            
            # 결과 리포트
            success_message = f"[{self.account_display}] 사용자 지정종목 독립 매매 완료"
            print(success_message)
            logger.info(success_message)
            
            return {
                'success': True,
                'execution_type': execution_type,
                'trading_type': 'user_designated_only',
                'result': result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            error_message = f"사용자 지정종목 독립 매매 실패: {e}"
            logger.error(error_message)
            return {
                'success': False,
                'execution_type': execution_type,
                'trading_type': 'user_designated_only', 
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def is_lunch_time_for_user_designated(self) -> bool:
        """사용자 지정종목 점심시간 실행 여부 확인"""
        now = datetime.now()
        current_time = now.time()
        
        lunch_start = time(12, 0)  # 12:00
        lunch_end = time(12, 30)   # 12:30
        
        return lunch_start <= current_time <= lunch_end
    
    async def get_trading_status(self) -> Dict[str, Any]:
        """현재 매매 시스템 상태 조회"""
        return {
            'day_trading_active': self.day_trading_active,
            'user_designated_active': self.user_designated_active,
            'last_day_trading_time': self.last_day_trading_time.isoformat() if self.last_day_trading_time else None,
            'last_user_designated_time': self.last_user_designated_time.isoformat() if self.last_user_designated_time else None,
            'account_type': self.account_type,
            'account_display': self.account_display
        }
    
    async def execute_combined_trading(self) -> Dict[str, Any]:
        """통합 매매 실행 (기존 방식과 호환)"""
        try:
            logger.info(f"[{self.account_display}] 통합 매매 실행")
            
            results = {
                'day_trading': None,
                'user_designated': None,
                'success': False,
                'timestamp': datetime.now().isoformat()
            }
            
            # 일반 단타매매 실행
            if not self.day_trading_active:
                await self.start_day_trading_session()
            
            # 사용자 지정종목이 점심시간인지 확인
            if await self.is_lunch_time_for_user_designated():
                user_result = await self.execute_user_designated_trading_only("LUNCH")
                results['user_designated'] = user_result
            
            results['success'] = True
            return results
            
        except Exception as e:
            logger.error(f"통합 매매 실행 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def cleanup_resources(self):
        """리소스 정리"""
        try:
            logger.info(f"[{self.account_display}] 매매 조정자 리소스 정리")
            
            if self.day_trading_active:
                await self.stop_day_trading_session()
            
            self.user_designated_active = False
            
            logger.info(f"[{self.account_display}] 매매 조정자 리소스 정리 완료")
            
        except Exception as e:
            logger.error(f"매매 조정자 리소스 정리 실패: {e}")


# 전역 인스턴스 관리
_separated_trading_coordinator = None


def get_separated_trading_coordinator(api_connector=None, account_type="REAL"):
    """분리된 매매 조정자 인스턴스 반환 (싱글톤)"""
    global _separated_trading_coordinator
    
    if _separated_trading_coordinator is None:
        if api_connector is None:
            raise ValueError("최초 호출 시 api_connector가 필요합니다")
        _separated_trading_coordinator = SeparatedTradingCoordinator(api_connector, account_type)
    
    return _separated_trading_coordinator


def reset_separated_trading_coordinator():
    """분리된 매매 조정자 리셋"""
    global _separated_trading_coordinator
    _separated_trading_coordinator = None
    logger.info("분리된 매매 조정자 리셋 완료")