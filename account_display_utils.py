#!/usr/bin/env python3
"""
계좌 정보 표시 유틸리티
모든 거래 시스템에서 통일된 계좌 정보 표시를 위한 공통 함수
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# ANSI 색상 코드
class AccountColors:
    LIGHT_GREEN = '\033[92m'    # Light Green - 계좌번호, 예수금액
    RED = '\033[91m'            # Red - 양수 수익률
    BLUE = '\033[94m'           # Blue - 음수 수익률
    RESET = '\033[0m'           # 색상 리셋
    BOLD = '\033[1m'            # 굵게


def display_account_info(account_data: Dict[str, Any], account_type: str = "REAL") -> None:
    """
    표준화된 계좌 정보 표시
    
    Args:
        account_data: 계좌 정보 딕셔너리
        account_type: "REAL" 또는 "MOCK"
    """
    try:
        # 계좌 타입에 따른 표시 문구
        account_type_text = "실전투자" if account_type == "REAL" else "모의투자"
        
        # 계좌번호 (전체 표시)
        account_number = account_data.get('account_number', 'Unknown')
        
        # 잔고 정보
        total_cash = account_data.get('total_cash', 0)
        buyable_cash = account_data.get('buyable_cash', 0)
        
        # 수익률 정보
        profit_rate = account_data.get('profit_rate', 0.0)
        if isinstance(profit_rate, str):
            try:
                profit_rate = float(profit_rate)
            except:
                profit_rate = 0.0
        
        # 보유종목 정보
        holdings = account_data.get('holdings', [])
        holdings_count = len(holdings) if holdings else 0
        
        # 수익률 색상 결정
        if profit_rate > 0:
            profit_color = AccountColors.RED
        elif profit_rate < 0:
            profit_color = AccountColors.BLUE
        else:
            profit_color = ''
        
        # 계좌 정보 표시
        print(f"[{account_type_text} 연동계좌 번호: '{AccountColors.LIGHT_GREEN}{account_number}{AccountColors.RESET}']")
        print(f"-총 보유 예수금= {AccountColors.LIGHT_GREEN}{total_cash:,}{AccountColors.RESET} 원")
        print(f"-주문가능금액= {AccountColors.LIGHT_GREEN}{buyable_cash:,}{AccountColors.RESET} 원")
        print(f"-계좌 총 수익률 = {profit_color}{profit_rate:+.2f}{AccountColors.RESET} %")
        print(f"-보유종목 : {holdings_count}개")
        
        # 보유종목이 있는 경우 상세 표시
        if holdings and holdings_count > 0:
            for holding in holdings:
                # 다양한 데이터 형식 지원
                symbol = holding.get('symbol', holding.get('pdno', ''))
                name = holding.get('name', holding.get('prdt_name', ''))
                quantity = holding.get('quantity', holding.get('hldg_qty', 0))
                total_amount = holding.get('evaluation', holding.get('evlu_amt', 0))
                stock_profit_rate = holding.get('profit_rate', holding.get('evlu_pfls_rt', 0.0))
                
                # 데이터 타입 변환
                try:
                    quantity = int(quantity) if quantity else 0
                    total_amount = float(total_amount) if total_amount else 0
                    stock_profit_rate = float(stock_profit_rate) if stock_profit_rate else 0.0
                except:
                    quantity = 0
                    total_amount = 0
                    stock_profit_rate = 0.0
                
                # 보유수량이 0보다 큰 종목만 표시
                if quantity > 0:
                    # 종목별 수익률 색상
                    if stock_profit_rate > 0:
                        stock_color = AccountColors.RED
                    elif stock_profit_rate < 0:
                        stock_color = AccountColors.BLUE
                    else:
                        stock_color = ''
                    
                    print(f"  {name}({symbol})/{quantity}개/{total_amount:,.0f}원/{stock_color}{stock_profit_rate:+.2f}%{AccountColors.RESET}")
        
        print("계좌 잔고 및 보유종목 캐시 업데이트 완료")
        
    except Exception as e:
        logger.error(f"계좌 정보 표시 중 오류: {e}")
        print(f"[ERROR] 계좌 정보 표시 실패: {e}")


def show_account_inquiry_message() -> None:
    """계좌 조회 중 메시지 표시"""
    print("계좌조회 중입니다.")


def format_currency(amount: Any) -> str:
    """통화 형식으로 포맷팅"""
    try:
        if isinstance(amount, str):
            amount = float(amount.replace(',', ''))
        return f"{amount:,.0f}"
    except:
        return str(amount)


def format_percentage(rate: Any) -> str:
    """퍼센트 형식으로 포맷팅"""
    try:
        if isinstance(rate, str):
            rate = float(rate)
        return f"{rate:+.2f}"
    except:
        return str(rate)


def get_account_type_display(account_type: str) -> str:
    """계좌 타입에 따른 표시 문구 반환"""
    return "실전투자" if account_type == "REAL" else "모의투자"


def extract_account_summary(account_data: Dict[str, Any]) -> Dict[str, Any]:
    """계좌 데이터에서 요약 정보 추출"""
    try:
        return {
            'account_number': account_data.get('account_number', 'Unknown'),
            'total_cash': account_data.get('total_cash', 0),
            'buyable_cash': account_data.get('buyable_cash', 0),
            'profit_rate': account_data.get('profit_rate', 0.0),
            'holdings_count': len(account_data.get('holdings', [])),
            'holdings': account_data.get('holdings', [])
        }
    except Exception as e:
        logger.error(f"계좌 요약 정보 추출 중 오류: {e}")
        return {
            'account_number': 'Unknown',
            'total_cash': 0,
            'buyable_cash': 0,
            'profit_rate': 0.0,
            'holdings_count': 0,
            'holdings': []
        }