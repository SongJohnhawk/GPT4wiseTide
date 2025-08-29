#!/usr/bin/env python3
"""
사용자 지정종목 관리 시스템 (NumPy 최적화)
무조건 매수해야 하는 종목들을 관리하고 수익률 모니터링 - 벡터화 처리로 성능 향상
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import asyncio
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Numba 제거 - 표준 Python 사용
NUMBA_AVAILABLE = False

# Numba 제거된 더미 데코레이터
def njit(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

def jit(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

# 로깅 설정
import logging
from support.log_manager import get_log_manager

# 깔끔한 콘솔 로거 사용
from support.clean_console_logger import (
    get_clean_logger, Phase, log as clean_log
)

# 로그 매니저를 통한 로거 설정
log_manager = get_log_manager()
logger = log_manager.setup_logger('system', __name__)

@dataclass
class UserStock:
    """사용자 지정 종목 정보"""
    symbol: str
    name: str
    target_quantity: int = 0  # 목표 매수 수량
    current_quantity: int = 0  # 현재 보유 수량
    avg_price: float = 0.0  # 평균 매수가
    total_cost: float = 0.0  # 총 매수 금액
    profit_rate: float = 0.0  # 수익률
    current_price: float = 0.0  # 현재 가격
    last_profit_notification: Optional[datetime] = None  # 마지막 수익률 알림 시간
    # 수익률별 알림 추적
    profit_20_notified: bool = False  # 20% 알림 전송 여부
    profit_50_notified: bool = False  # 50% 알림 전송 여부  
    profit_100_notified: bool = False  # 100% 알림 전송 여부

class UserDesignatedStockManager:
    """사용자 지정종목 관리자"""
    
    def __init__(self, api_connector):
        self.api = api_connector
        
        # 가격대별 수량 기준 (먼저 정의)
        self.PRICE_THRESHOLDS = {
            "high": 200000,    # 20만원 이상 -> 10주
            "low": 100000,     # 10만원 이하 -> 50주
            "default": 20      # 기타 -> 20주
        }
        
        # 수익률 알림 기준
        self.PROFIT_THRESHOLDS = {
            "20%": 0.20,
            "50%": 0.50, 
            "100%": 1.00
        }
        
        # 사용자 지정종목 목록 (외부 파일에서 로드)
        self.designated_stocks = {}
        self.stock_list_file = Path(__file__).parent / "menual_StokBuyList.md"
        
        # 사용자 지정종목 파일에서 로드 (PRICE_THRESHOLDS 정의 후)
        self._load_user_designated_stocks()
    
    def _load_user_designated_stocks(self):
        """menual_StokBuyList.md 파일에서 사용자 지정종목 로드"""
        try:
            if not self.stock_list_file.exists():
                clean_log(f"사용자 지정종목 파일이 없음: {self.stock_list_file}", "WARNING")
                self._create_default_stock_list_file()
                return
            
            with open(self.stock_list_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 마크다운에서 종목 정보 추출
            lines = content.split('\n')
            loaded_count = 0
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # 빈 줄이나 주석 줄, 마크다운 헤더 건너뛰기
                if not line or line.startswith('#') or line.startswith('```') or line.startswith('-'):
                    continue
                
                # 종목 코드 패턴 찾기 (6자리 숫자)
                import re
                stock_code_match = re.search(r'\b(\d{6})\b', line)
                
                if stock_code_match:
                    stock_code = stock_code_match.group(1)
                    
                    # 종목명을 API로 조회
                    stock_name = self._get_stock_name_from_api(stock_code)
                    
                    if stock_name and stock_name != "Unknown":
                        self.designated_stocks[stock_code] = UserStock(
                            symbol=stock_code,
                            name=stock_name
                        )
                        loaded_count += 1
            
            clean_log(f"사용자 지정종목 {loaded_count}개 로드 완료", "SUCCESS")
            
        except Exception as e:
            clean_log(f"사용자 지정종목 로딩 실패: {e}", "ERROR")
    
    def _get_stock_name_from_api(self, stock_code: str) -> Optional[str]:
        """API를 통해 종목명 조회"""
        try:
            # 종목 기본정보 조회
            stock_info = self.api.get_stock_info(stock_code)
            
            if stock_info and stock_info.get('rt_cd') == '0':
                output = stock_info.get('output', {})
                stock_name = output.get('hts_kor_isnm', '').strip()
                
                if stock_name:
                    return stock_name
            
            return None
            
        except Exception as e:
            clean_log(f"종목명 조회 실패 {stock_code}: {e}", "ERROR")
            return None
    
    async def get_display_summary(self) -> str:
        """지정종목 표시용 요약 정보 생성 - 종목명(종목코드)/보유수량/현재상태(수익률) 형식"""
        try:
            if not self.designated_stocks:
                return "사용자 지정종목: 없음"
            
            summary_lines = []
            
            for symbol, stock in self.designated_stocks.items():
                # 현재 가격 및 보유 정보 업데이트
                await self._update_stock_current_data(stock)
                
                # 수익률 계산 및 상태 표시
                if stock.current_quantity > 0 and stock.avg_price > 0:
                    profit_rate = ((stock.current_price - stock.avg_price) / stock.avg_price) * 100
                    status = f"{profit_rate:+.1f}%" if profit_rate != 0 else "0.0%"
                    quantity_info = f"{stock.current_quantity}주"
                else:
                    status = "미보유"
                    quantity_info = "0주"
                
                # 표시 형식: 종목명(종목코드)/보유수량/현재상태
                display_line = f"{stock.name}({symbol})/{quantity_info}/{status}"
                summary_lines.append(display_line)
            
            result = f"사용자 지정종목({len(self.designated_stocks)}개): " + " | ".join(summary_lines)
            return result
            
        except Exception as e:
            clean_log(f"지정종목 요약 생성 실패: {e}", "ERROR")
            return f"사용자 지정종목({len(self.designated_stocks)}개): 정보 조회 실패"
    
    async def _update_stock_current_data(self, stock: UserStock):
        """종목의 현재 가격 및 보유 정보 업데이트"""
        try:
            # 현재 가격 조회
            price_data = self.api.get_stock_price(stock.symbol)
            if price_data and price_data.get('rt_cd') == '0':
                current_price = float(price_data.get('output', {}).get('stck_prpr', 0))
                stock.current_price = current_price
            
            # 보유 수량 및 평균 가격 조회
            positions = await self.api.get_positions()
            if positions:
                for position in positions:
                    if position.get('stock_code') == stock.symbol:
                        stock.current_quantity = int(position.get('quantity', 0))
                        stock.avg_price = float(position.get('avg_price', 0))
                        break
        except Exception as e:
            clean_log(f"종목 정보 업데이트 실패 {stock.symbol}: {e}", "WARNING")
    
    def _create_default_stock_list_file(self):
        """기본 사용자 지정종목 파일 생성"""
        default_content = """# 사용자 지정종목 리스트

## 무조건 매수해야 하는 종목들
- 247540 (에코프로비엠)
- 373220 (LG에너지솔루션)  
- 005930 (삼성전자)
- 000660 (SK하이닉스)
- 035420 (NAVER)
- 035720 (카카오)

## 사용 방법
- 각 줄에 종목코드(6자리)를 포함하여 작성
- 종목명은 자동으로 API에서 조회됩니다
- # 으로 시작하는 줄은 주석으로 처리됩니다
"""
        
        try:
            with open(self.stock_list_file, 'w', encoding='utf-8') as f:
                f.write(default_content)
            logger.info(f"기본 사용자 지정종목 파일 생성: {self.stock_list_file}")
        except Exception as e:
            logger.error(f"기본 파일 생성 실패: {e}")
    
    def apply_seven_percent_rule(self, symbol: str, account_balance: float, is_additional_buy: bool = False) -> int:
        """사용자 지정종목 7% 원칙 적용"""
        try:
            if symbol not in self.designated_stocks:
                logger.warning(f"사용자 지정종목이 아님: {symbol}")
                return 0
            
            stock = self.designated_stocks[symbol]
            
            # 현재 주가 조회
            price_data = self.api.get_stock_price(symbol)
            if not price_data or price_data.get('rt_cd') != '0':
                logger.error(f"주가 조회 실패: {symbol}")
                return 0
            
            current_price = float(price_data.get('output', {}).get('stck_prpr', 0))
            if current_price <= 0:
                logger.error(f"유효하지 않은 주가: {symbol} - {current_price}")
                return 0
            
            # 7% 원칙에 따른 수량 계산
            final_quantity = self._calculate_user_designated_quantity(
                account_balance, 
                current_price, 
                budget_ratio=0.07
            )
            
            # 추매의 경우 절반 수량
            if is_additional_buy:
                final_quantity = max(1, final_quantity // 2)
            
            logger.info(f"사용자 지정종목 7% 원칙 적용: {symbol}, {'추매' if is_additional_buy else '신규매수'}: {final_quantity}주")
            
            return final_quantity
            
        except Exception as e:
            logger.error(f"7% 원칙 적용 실패: {symbol} - {e}")
            return 10 if not is_additional_buy else 5
    
    def _calculate_user_designated_quantity(self, account_balance: float, stock_price: float, budget_ratio: float = 0.07) -> int:
        """사용자 지정종목 전용 수량 계산 (최저가격 제한 없음)"""
        try:
            # 예수금의 7%로 최대 매수 가능 금액 계산
            max_budget = account_balance * budget_ratio
            
            # 수수료 및 마진 고려 (0.2% 추가)
            margin_rate = 1.002
            adjusted_budget = max_budget / margin_rate
            
            # 최대 매수 가능 수량 계산 (최저가격 제한 없음)
            max_quantity = int(adjusted_budget / stock_price)
            
            return max_quantity
            
        except Exception as e:
            logger.error(f"사용자 지정종목 수량 계산 실패: {e}")
            return 0
    
    def get_all_designated_stocks(self) -> Dict[str, UserStock]:
        """모든 사용자 지정종목 반환"""
        return self.designated_stocks.copy()
    
    def get_user_stocks(self) -> List[str]:
        """사용자 지정종목 심볼 리스트 반환"""
        return list(self.designated_stocks.keys())
    
    def get_designated_stock_codes(self) -> List[str]:
        """사용자 지정종목 코드 리스트 반환 (호환성을 위한 메서드)"""
        return list(self.designated_stocks.keys())
    
    def is_user_designated_stock(self, symbol: str) -> bool:
        """사용자 지정종목 여부 확인"""
        return symbol in self.designated_stocks
    
    def get_stock_info(self, symbol: str) -> Optional[UserStock]:
        """특정 종목 정보 반환"""
        return self.designated_stocks.get(symbol)

# 전역 인스턴스
_user_designated_stock_manager = None

def get_user_designated_stock_manager(api_connector=None):
    """사용자 지정종목 관리자 싱글톤 인스턴스 반환"""
    global _user_designated_stock_manager
    if _user_designated_stock_manager is None and api_connector is not None:
        _user_designated_stock_manager = UserDesignatedStockManager(api_connector)
    return _user_designated_stock_manager