#!/usr/bin/env python3
"""
User Designated Trading Manager - 사용자 지정종목 매매 전용 모듈
자동매매와 분리되어 독립적으로 실행되는 사용자 지정종목 매매 시스템
정오 12:00-12:30 및 계좌조회 후 1회 실행
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, time
from pathlib import Path

logger = logging.getLogger(__name__)


class UserDesignatedTradingManager:
    """사용자 지정종목 매매 전용 관리 클래스"""
    
    def __init__(self, api_connector, account_type: str = "REAL"):
        """
        UserDesignatedTradingManager 초기화
        
        Args:
            api_connector: API 연결 객체
            account_type: 계좌 유형 ("REAL" 또는 "MOCK")
        """
        self.api = api_connector
        self.account_type = account_type
        self.account_display = "실계좌" if account_type == "REAL" else "모의계좌"
        
        # 마지막 실행 시간 추적
        self.last_execution_time = None
        self.lunch_execution_done = False  # 점심시간 실행 완료 플래그
        
        logger.info(f"UserDesignatedTradingManager 초기화: {self.account_display}")
    
    def should_execute_lunch_trading(self) -> bool:
        """정오 12:00-12:30 실행 여부 확인"""
        now = datetime.now()
        current_time = now.time()
        
        lunch_start = time(12, 0)  # 12:00
        lunch_end = time(12, 30)   # 12:30
        
        # 시간대 확인
        in_lunch_time = lunch_start <= current_time <= lunch_end
        
        # 같은 날 이미 실행되었는지 확인
        today = now.date()
        if (self.last_execution_time and 
            self.last_execution_time.date() == today and 
            self.lunch_execution_done):
            return False
        
        # 점심시간이고 아직 실행되지 않았으면 실행
        if in_lunch_time and not self.lunch_execution_done:
            return True
        
        # 점심시간이 지나면 플래그 리셋 (다음날을 위해)
        if current_time > lunch_end:
            self.lunch_execution_done = False
        
        return False
    
    async def execute_user_designated_trading(self, execution_type: str = "NORMAL") -> Dict[str, Any]:
        """
        사용자 지정종목 매매 실행
        
        Args:
            execution_type: 실행 유형 ("INITIAL", "LUNCH", "NORMAL")
            
        Returns:
            Dict: 매매 실행 결과
        """
        try:
            logger.info(f"[{self.account_display}] 사용자 지정종목 매매 시작 ({execution_type})")
            print(f"\n[{self.account_display}] 사용자 지정종목 매매를 시작합니다... ({execution_type})")
            
            # 사용자 지정종목 매니저 로드
            user_manager = await self._get_user_designated_manager()
            if not user_manager:
                result = {
                    "success": False,
                    "analyzed_stocks": 0,
                    "executed_trades": 0,
                    "pending_orders": 0,
                    "message": "사용자 지정종목 매니저 로드 실패",
                    "execution_type": execution_type
                }
                print(f"[{self.account_display}] 사용자 지정종목 매니저 로드 실패")
                return result
            
            # 지정종목 목록 조회
            designated_stocks = user_manager.designated_stocks
            if not designated_stocks:
                result = {
                    "success": True,
                    "analyzed_stocks": 0,
                    "executed_trades": 0,
                    "pending_orders": 0,
                    "message": "사용자 지정종목이 없습니다.",
                    "execution_type": execution_type
                }
                print(f"[{self.account_display}] 사용자 지정종목이 없습니다.")
                return result
            
            analyzed_count = 0
            executed_count = 0
            pending_count = 0
            trade_results = []
            
            print(f"[{self.account_display}] {len(designated_stocks)}개 지정종목 분석 중...")
            
            # 각 지정종목에 대해 매매 분석 및 실행
            for stock_code, user_stock in designated_stocks.items():
                try:
                    analyzed_count += 1
                    
                    # 종목별 매매 분석
                    trade_decision = await self._analyze_user_stock_trade(user_stock)
                    
                    if trade_decision['action'] == 'BUY':
                        # 매수 실행
                        buy_result = await self._execute_user_stock_buy(user_stock, trade_decision)
                        if buy_result['success']:
                            executed_count += 1
                            trade_results.append(f"✓ 매수: {user_stock.name}({stock_code}) - {trade_decision['reason']}")
                            print(f"  ✓ 매수: {user_stock.name}({stock_code}) - {trade_decision['reason']}")
                        else:
                            pending_count += 1
                            trade_results.append(f"! 매수실패: {user_stock.name}({stock_code}) - {buy_result.get('error', 'Unknown')}")
                            print(f"  ! 매수실패: {user_stock.name}({stock_code}) - {buy_result.get('error', 'Unknown')}")
                    else:
                        trade_results.append(f"○ 분석완료: {user_stock.name}({stock_code}) - {trade_decision['reason']}")
                        print(f"  ○ 분석완료: {user_stock.name}({stock_code}) - {trade_decision['reason']}")
                        
                except Exception as e:
                    logger.warning(f"종목 처리 중 오류 ({stock_code}): {e}")
                    trade_results.append(f"! 오류: {user_stock.name if hasattr(user_stock, 'name') else stock_code} - {str(e)}")
                    print(f"  ! 오류: {user_stock.name if hasattr(user_stock, 'name') else stock_code} - {str(e)}")
            
            # 실행 시간 및 플래그 업데이트
            self.last_execution_time = datetime.now()
            if execution_type == "LUNCH":
                self.lunch_execution_done = True
            
            # 결과 요약
            result = {
                "success": True,
                "analyzed_stocks": analyzed_count,
                "executed_trades": executed_count,
                "pending_orders": pending_count,
                "message": f"분석 {analyzed_count}개, 매수 {executed_count}개, 대기 {pending_count}개",
                "execution_type": execution_type,
                "trade_results": trade_results
            }
            
            print(f"\n[{self.account_display}] 사용자 지정종목 매매 완료:")
            print(f"  - 분석된 종목: {analyzed_count}개")
            print(f"  - 실행된 매수: {executed_count}개")
            print(f"  - 대기 주문: {pending_count}개")
            
            logger.info(f"[{self.account_display}] 사용자 지정종목 매매 완료: 분석 {analyzed_count}개, 매수 {executed_count}개")
            
            return result
            
        except Exception as e:
            error_msg = f"사용자 지정종목 매매 실행 실패: {e}"
            logger.error(f"[{self.account_display}] {error_msg}")
            print(f"\n[{self.account_display}] {error_msg}")
            
            return {
                "success": False,
                "analyzed_stocks": 0,
                "executed_trades": 0,
                "pending_orders": 0,
                "message": error_msg,
                "execution_type": execution_type,
                "error": str(e)
            }
    
    async def _get_user_designated_manager(self):
        """사용자 지정종목 매니저 로드"""
        try:
            from support.user_designated_stocks import get_user_designated_stock_manager
            user_manager = get_user_designated_stock_manager(self.api)
            return user_manager
        except Exception as e:
            logger.error(f"사용자 지정종목 매니저 로드 실패: {e}")
            return None
    
    async def _analyze_user_stock_trade(self, user_stock) -> Dict[str, str]:
        """사용자 지정종목 매매 분석 (-5% 추매 로직)"""
        try:
            stock_code = user_stock.symbol
            
            # 장 운영시간 체크
            if not self._is_market_hours():
                return {"action": "HOLD", "reason": "장 운영시간 외 (09:00-15:30)"}
            
            # 현재가 조회
            current_price = await self._get_current_price(stock_code)
            if not current_price:
                return {"action": "HOLD", "reason": "현재가 조회 실패"}
            
            # 계좌 잔고에서 현재 보유량 확인
            current_holdings = await self._get_current_holdings(stock_code)
            current_quantity = current_holdings.get('quantity', 0)
            avg_price = current_holdings.get('avg_price', 0)
            
            # 예수금 확인
            available_cash = await self._get_available_cash()
            if not available_cash or available_cash < 100000:  # 10만원 미만
                return {"action": "HOLD", "reason": "예수금 부족"}
            
            # 1. 신규 매수 조건 (아직 보유하지 않은 종목)
            if current_quantity == 0:
                # 목표 수량 계산
                target_quantity = self._calculate_target_quantity(current_price, available_cash)
                if target_quantity > 0:
                    return {"action": "BUY", "reason": f"신규매수 {target_quantity}주", "quantity": target_quantity}
                else:
                    return {"action": "HOLD", "reason": "예산 부족으로 신규매수 불가"}
            
            # 2. 추매 조건 (-5% 이상 하락시)
            if avg_price > 0:
                price_drop_rate = (current_price - avg_price) / avg_price
                
                # -5% 이상 하락시 추매
                if price_drop_rate <= -0.05:
                    # 보유수량의 10% 범위에서 추매
                    additional_quantity = max(1, int(current_quantity * 0.1))
                    
                    # 추매 예산 확인
                    required_budget = additional_quantity * current_price
                    if available_cash >= required_budget:
                        return {
                            "action": "BUY", 
                            "reason": f"추매 {additional_quantity}주 (하락률 {price_drop_rate*100:.1f}%)",
                            "quantity": additional_quantity
                        }
                    else:
                        return {"action": "HOLD", "reason": f"추매 예산 부족 (필요: {required_budget:,.0f}원)"}
                else:
                    return {"action": "HOLD", "reason": f"추매 조건 미달 (하락률 {price_drop_rate*100:.1f}%)"}
            
            return {"action": "HOLD", "reason": "매매 조건 없음"}
            
        except Exception as e:
            logger.warning(f"사용자 종목 분석 오류 ({user_stock.symbol}): {e}")
            return {"action": "HOLD", "reason": f"분석 오류: {str(e)}"}
    
    async def _execute_user_stock_buy(self, user_stock, trade_decision: Dict[str, Any]) -> Dict[str, Any]:
        """사용자 지정종목 매수 실행"""
        try:
            stock_code = user_stock.symbol
            quantity = trade_decision.get('quantity', 0)
            
            if quantity <= 0:
                return {"success": False, "error": "매수 수량이 0입니다"}
            
            # 현재가 조회
            current_price = await self._get_current_price(stock_code)
            if not current_price:
                return {"success": False, "error": "현재가 조회 실패"}
            
            # 지정가 매수 주문 (현재가 기준)
            buy_result = self.api.place_buy_order(
                symbol=stock_code,
                quantity=quantity,
                price=int(current_price),
                order_type="00"  # 지정가 주문
            )
            
            if buy_result and buy_result.get('success', False):
                return {
                    "success": True,
                    "stock_code": stock_code,
                    "stock_name": user_stock.name,
                    "quantity": quantity,
                    "price": current_price,
                    "total_amount": quantity * current_price
                }
            else:
                error_msg = buy_result.get('error', '매수 주문 실패') if buy_result else '매수 주문 응답 없음'
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            logger.error(f"사용자 종목 매수 실행 중 오류: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_current_price(self, stock_code: str) -> Optional[float]:
        """현재가 조회"""
        try:
            price_data = self.api.get_stock_price(stock_code)
            if price_data and price_data.get('rt_cd') == '0':
                return float(price_data['output']['stck_prpr'])
            return None
        except Exception as e:
            logger.warning(f"현재가 조회 실패 ({stock_code}): {e}")
            return None
    
    async def _get_current_holdings(self, stock_code: str) -> Dict[str, Any]:
        """현재 보유량 조회"""
        try:
            positions = await self.api.get_positions()
            if positions:
                for position in positions:
                    if position.get('stock_code') == stock_code:
                        return {
                            'quantity': int(position.get('quantity', 0)),
                            'avg_price': float(position.get('avg_price', 0))
                        }
            return {'quantity': 0, 'avg_price': 0}
        except Exception as e:
            logger.warning(f"보유량 조회 실패 ({stock_code}): {e}")
            return {'quantity': 0, 'avg_price': 0}
    
    async def _get_available_cash(self) -> Optional[float]:
        """주문가능금액 조회 (AccountInfoManager 사용)"""
        try:
            from support.account_info_manager import get_account_info_manager
            
            account_manager = get_account_info_manager(self.api, self.account_type)
            return await account_manager.get_available_cash()
        except Exception as e:
            logger.warning(f"예수금 조회 실패: {e}")
            return None
    
    def _calculate_target_quantity(self, current_price: float, available_cash: float) -> int:
        """목표 매수 수량 계산 (예수금의 7% 내에서)"""
        try:
            # 예수금의 7% 사용
            max_budget = available_cash * 0.07
            
            # 수수료 고려 (0.2%)
            adjusted_budget = max_budget / 1.002
            
            # 매수 가능 수량
            target_quantity = int(adjusted_budget / current_price)
            
            return max(0, target_quantity)
            
        except Exception:
            return 0
    
    def _is_market_hours(self) -> bool:
        """장 운영시간 체크 (평일 09:00-15:30)"""
        now = datetime.now()
        
        # 주말 체크
        if now.weekday() >= 5:  # 토요일(5), 일요일(6)
            return False
        
        # 시간 체크 (09:00-15:30)
        current_time = now.time()
        market_open = time(9, 0)
        market_close = time(15, 30)
        
        return market_open <= current_time <= market_close


# 전역 인스턴스 관리
_user_designated_trading_manager = None

def get_user_designated_trading_manager(api_connector, account_type: str = "REAL") -> UserDesignatedTradingManager:
    """UserDesignatedTradingManager 인스턴스 반환"""
    global _user_designated_trading_manager
    if _user_designated_trading_manager is None or _user_designated_trading_manager.account_type != account_type:
        _user_designated_trading_manager = UserDesignatedTradingManager(api_connector, account_type)
    return _user_designated_trading_manager


async def execute_standalone_user_designated_trading(account_type: str = "REAL", execution_type: str = "NORMAL") -> Dict[str, Any]:
    """
    독립적인 사용자 지정종목 매매 실행 함수
    
    Args:
        account_type: 계좌 유형 ("REAL" 또는 "MOCK")
        execution_type: 실행 유형 ("INITIAL", "LUNCH", "NORMAL")
        
    Returns:
        Dict: 매매 실행 결과
    """
    try:
        from support.api_connector import KISAPIConnector
        
        # API 연결
        api = KISAPIConnector(is_mock=(account_type == "MOCK"))
        
        # 사용자 지정종목 매매 매니저 생성 및 실행
        trading_manager = get_user_designated_trading_manager(api, account_type)
        result = await trading_manager.execute_user_designated_trading(execution_type)
        
        return result
        
    except Exception as e:
        error_msg = f"독립적 사용자 지정종목 매매 실행 실패: {e}"
        logger.error(error_msg)
        
        return {
            "success": False,
            "analyzed_stocks": 0,
            "executed_trades": 0,
            "pending_orders": 0,
            "message": error_msg,
            "execution_type": execution_type,
            "error": str(e)
        }


def check_lunch_trading_time() -> bool:
    """정오 12:00-12:30 매매 시간 확인"""
    now = datetime.now()
    current_time = now.time()
    
    lunch_start = time(12, 0)  # 12:00
    lunch_end = time(12, 30)   # 12:30
    
    return lunch_start <= current_time <= lunch_end