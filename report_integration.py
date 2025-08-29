"""
tideWise 리포팅 시스템 통합 모듈
기존 매매 시스템과 리포팅 연동
"""
import asyncio
from typing import Dict, Any, Optional
import logging
from .trade_reporter import trade_reporter
from .holiday_provider import holiday_provider

class ReportingIntegration:
    """리포팅 시스템 통합 관리자"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session_active = False
        self.initial_balance = 0.0
        
    async def start_trading_session(self, account_type: str = 'MOCK') -> bool:
        """거래 세션 시작 및 리포팅 초기화"""
        try:
            # 휴장일 정보 업데이트 (매월 첫 실행시)
            current_year = holiday_provider.seoul_tz.localize(
                holiday_provider.seoul_tz.normalize(
                    holiday_provider.seoul_tz.localize(
                        holiday_provider.seoul_tz.normalize(
                            holiday_provider.seoul_tz.now()
                        ).replace(tzinfo=None)
                    ).astimezone().replace(tzinfo=None)
                ).replace(tzinfo=None)
            ).year if hasattr(holiday_provider.seoul_tz, 'now') else 2025
            
            if holiday_provider._need_update(current_year):
                self.logger.info("휴장일 정보 업데이트 중...")
                holiday_provider.update_holidays(current_year)
            
            # 리포팅 세션 시작
            trade_reporter.start_session()
            self.session_active = True
            
            # 초기 잔고 기록 (실제 API에서 가져와야 함)
            self.initial_balance = await self._get_account_balance(account_type)
            
            self.logger.info(f"리포팅 세션 시작: {account_type}, 초기잔고: {self.initial_balance:,.0f}원")
            return True
            
        except Exception as e:
            self.logger.error(f"리포팅 세션 시작 실패: {e}")
            return False
    
    async def record_trade(self, trade_info: Dict[str, Any]) -> bool:
        """거래 기록 추가"""
        if not self.session_active:
            self.logger.warning("리포팅 세션이 활성화되지 않음")
            return False
        
        try:
            trade_reporter.add_trade(trade_info)
            return True
            
        except Exception as e:
            self.logger.error(f"거래 기록 실패: {e}")
            return False
    
    async def end_trading_session(self, account_type: str = 'MOCK') -> bool:
        """거래 세션 종료 및 리포트 생성"""
        if not self.session_active:
            self.logger.warning("활성화된 리포팅 세션이 없음")
            return False
        
        try:
            # 최종 잔고 조회
            final_balance = await self._get_account_balance(account_type)
            
            # 세션 종료 및 리포트 생성
            trade_reporter.end_session(self.initial_balance, final_balance)
            self.session_active = False
            
            self.logger.info(f"리포팅 세션 종료: 최종잔고: {final_balance:,.0f}원")
            return True
            
        except Exception as e:
            self.logger.error(f"리포팅 세션 종료 실패: {e}")
            return False
    
    async def _get_account_balance(self, account_type: str) -> float:
        """계좌 잔고 조회 (실제 API 연동 필요)"""
        try:
            # 실제 구현에서는 KISAPIConnector를 통해 잔고 조회
            # 현재는 더미 데이터 반환
            if account_type == 'MOCK':
                return 100000000.0  # 모의투자 초기 잔고
            else:
                return 1000000.0    # 실전투자 예시 잔고
                
        except Exception as e:
            self.logger.error(f"계좌 잔고 조회 실패: {e}")
            return 0.0
    
    def create_trade_record(self, symbol: str, action: str, quantity: int, 
                          price: float, amount: float, algorithm: str,
                          account_type: str = 'MOCK', trading_mode: str = 'AUTO',
                          commission: float = 0.0, profit_loss: float = 0.0) -> Dict[str, Any]:
        """거래 기록 생성 헬퍼"""
        return {
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'price': price,
            'amount': amount,
            'commission': commission,
            'profit_loss': profit_loss,
            'account_type': account_type,
            'trading_mode': trading_mode,
            'algorithm': algorithm
        }
    
    def is_report_generation_day(self) -> Dict[str, bool]:
        """리포트 생성 시점인지 확인"""
        from datetime import date
        today = date.today()
        
        weekly_day = holiday_provider.last_trading_day_of_iso_week(today)
        monthly_day = holiday_provider.last_trading_day_of_month(today.year, today.month)
        
        return {
            'is_weekly_report_day': today == weekly_day,
            'is_monthly_report_day': today == monthly_day,
            'weekly_report_date': weekly_day.strftime('%Y-%m-%d'),
            'monthly_report_date': monthly_day.strftime('%Y-%m-%d')
        }


# 전역 인스턴스
reporting_integration = ReportingIntegration()


# 기존 매매 시스템과의 통합을 위한 데코레이터
def with_reporting(func):
    """매매 함수에 리포팅 기능 추가하는 데코레이터"""
    async def wrapper(*args, **kwargs):
        # 세션 시작
        account_type = kwargs.get('account_type', 'MOCK')
        await reporting_integration.start_trading_session(account_type)
        
        try:
            # 원래 함수 실행
            result = await func(*args, **kwargs)
            return result
            
        finally:
            # 세션 종료
            await reporting_integration.end_trading_session(account_type)
    
    return wrapper


# 거래 기록 추가를 위한 헬퍼 함수들
async def log_buy_order(symbol: str, quantity: int, price: float, 
                       algorithm: str, account_type: str = 'MOCK'):
    """매수 주문 기록"""
    trade_record = reporting_integration.create_trade_record(
        symbol=symbol,
        action='BUY',
        quantity=quantity,
        price=price,
        amount=quantity * price,
        algorithm=algorithm,
        account_type=account_type,
        commission=quantity * price * 0.00015  # 수수료 0.015%
    )
    
    await reporting_integration.record_trade(trade_record)


async def log_sell_order(symbol: str, quantity: int, price: float, 
                        buy_price: float, algorithm: str, account_type: str = 'MOCK'):
    """매도 주문 기록"""
    amount = quantity * price
    buy_amount = quantity * buy_price
    profit_loss = amount - buy_amount
    commission = amount * 0.00015 + amount * 0.0023  # 수수료 + 세금
    
    trade_record = reporting_integration.create_trade_record(
        symbol=symbol,
        action='SELL',
        quantity=quantity,
        price=price,
        amount=amount,
        algorithm=algorithm,
        account_type=account_type,
        commission=commission,
        profit_loss=profit_loss - commission
    )
    
    await reporting_integration.record_trade(trade_record)


# 리포트 상태 확인 함수
def get_reporting_status() -> Dict[str, Any]:
    """현재 리포팅 상태 반환"""
    report_days = reporting_integration.is_report_generation_day()
    
    return {
        'session_active': reporting_integration.session_active,
        'initial_balance': reporting_integration.initial_balance,
        'report_generation_info': report_days,
        'report_directory': str(trade_reporter.report_dir.absolute())
    }