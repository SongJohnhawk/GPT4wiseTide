#!/usr/bin/env python3
"""
Account Info Manager - 통합 계좌정보 관리 시스템
독립된 계좌정보 객체로 계좌 데이터 조회, 표시, 저장을 통합 관리
"""

import asyncio
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AccountInfoData:
    """계좌 정보 데이터 클래스"""
    
    def __init__(self, raw_data: Dict[str, Any], account_type: str):
        """
        계좌 정보 데이터 초기화
        
        Args:
            raw_data: API에서 받은 원시 계좌 데이터
            account_type: 계좌 유형 ("REAL" 또는 "MOCK")
        """
        self.account_type = account_type
        self.account_display = "실계좌" if account_type == "REAL" else "모의계좌"
        self.updated_at = datetime.now()
        
        # 원시 데이터 저장
        self.raw_data = raw_data
        
        # 주요 계좌 정보 파싱 (안전한 형변환)
        self.cash_balance = self._safe_float_convert(raw_data.get('dnca_tot_amt', '0'))  # 예수금
        self.available_cash = self._safe_float_convert(raw_data.get('ord_psbl_cash', '0'))  # 주문가능금액
        self.total_asset = self._safe_float_convert(raw_data.get('tot_evlu_amt', '0'))  # 총평가액
        self.total_profit_loss = self._safe_float_convert(raw_data.get('evlu_pfls_smtl_amt', '0'))  # 평가손익
        
        # 수익률 계산
        if self.cash_balance > 0:
            self.profit_rate = (self.total_profit_loss / self.cash_balance) * 100
        else:
            self.profit_rate = 0.0
        
        # 보유종목 파싱
        self.holdings = self._parse_holdings(raw_data.get('output1', []))
        self.stock_count = len([h for h in self.holdings if h['quantity'] > 0])
        
        # 표시용 포맷팅
        self._format_display_data()
        
        logger.info(f"[{self.account_display}] 계좌 정보 파싱 완료 - 예수금: {self.cash_balance:,.0f}원, 보유종목: {self.stock_count}개")
    
    def _safe_float_convert(self, value) -> float:
        """안전한 float 형변환"""
        try:
            if value is None or value == '':
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Float 변환 실패: {value}, 기본값 0.0 사용")
            return 0.0
    
    def _parse_holdings(self, holdings_data: List[Dict]) -> List[Dict[str, Any]]:
        """보유종목 데이터 파싱"""
        parsed_holdings = []
        
        for holding in holdings_data:
            try:
                quantity = int(self._safe_float_convert(holding.get('hldg_qty', '0')))
                if quantity > 0:  # 보유 수량이 있는 종목만
                    stock_code = holding.get('pdno', '')
                    stock_name = holding.get('prdt_name', '').strip()
                    current_price = self._safe_float_convert(holding.get('prpr', '0'))
                    avg_price = self._safe_float_convert(holding.get('pchs_avg_pric', '0'))
                    profit_loss = self._safe_float_convert(holding.get('evlu_pfls_amt', '0'))
                    
                    # 수익률 계산
                    profit_rate = 0.0
                    if avg_price > 0:
                        profit_rate = ((current_price - avg_price) / avg_price) * 100
                    
                    parsed_holdings.append({
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'quantity': quantity,
                        'current_price': current_price,
                        'avg_price': avg_price,
                        'profit_loss': profit_loss,
                        'profit_rate': profit_rate,
                        'total_value': quantity * current_price
                    })
            except (ValueError, TypeError) as e:
                logger.warning(f"보유종목 파싱 오류: {e}")
                continue
        
        # 평가금액 기준 내림차순 정렬
        parsed_holdings.sort(key=lambda x: x['total_value'], reverse=True)
        return parsed_holdings
    
    def _format_display_data(self):
        """표시용 데이터 포맷팅"""
        self.cash_balance_formatted = f"{self.cash_balance:,.0f}원"
        self.available_cash_formatted = f"{self.available_cash:,.0f}원"
        self.total_asset_formatted = f"{self.total_asset:,.0f}원"
        self.total_profit_loss_formatted = f"{self.total_profit_loss:+,.0f}원"
        self.profit_rate_formatted = f"{self.profit_rate:+.2f}%"
        
        # 보유종목 표시용 문자열 생성
        self.holdings_display = self._generate_holdings_display()
    
    def _generate_holdings_display(self) -> str:
        """보유종목 표시용 문자열 생성 - 상세 리스트 형태"""
        if not self.holdings:
            return "보유종목 없음"
        
        display_lines = []
        display_lines.append("보유종목 목록:")
        
        for holding in self.holdings:  # 모든 보유종목 표시
            stock_name = holding['stock_name']
            stock_code = holding['stock_code']
            quantity = holding['quantity']
            total_value = holding['total_value']
            profit_rate = holding['profit_rate']
            
            # 상세 리스트 형태: 종목명(코드)/수량주/총금액원/수익률%
            line = f"  • {stock_name}({stock_code})/{quantity}주/{total_value:,.0f}원/{profit_rate:+.1f}%"
            display_lines.append(line)
        
        return "\n".join(display_lines)
    
    def get_summary_dict(self) -> Dict[str, Any]:
        """계좌 정보 요약을 딕셔너리로 반환"""
        return {
            'account_type': self.account_type,
            'account_display': self.account_display,
            'cash_balance': self.cash_balance,
            'available_cash': self.available_cash,
            'total_asset': self.total_asset,
            'total_profit_loss': self.total_profit_loss,
            'profit_rate': self.profit_rate,
            'stock_count': self.stock_count,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class AccountInfoManager:
    """통합 계좌정보 관리 클래스"""
    
    def __init__(self, api_connector, account_type: str = "REAL"):
        """
        AccountInfoManager 초기화
        
        Args:
            api_connector: API 연결 객체
            account_type: 계좌 유형 ("REAL" 또는 "MOCK")
        """
        self.api = api_connector
        self.account_type = account_type
        self.account_display = "실계좌" if account_type == "REAL" else "모의계좌"
        
        # 계좌 번호 정보 (API에서 가져오기)
        self.account_number = self._get_account_number()
        
        # 계좌 정보 캐시
        self._cached_account_info: Optional[AccountInfoData] = None
        self._last_update_time: Optional[datetime] = None
        
        # 텔레그램 알림 객체 (지연 로딩)
        self._telegram_notifier = None
        
        logger.info(f"AccountInfoManager 초기화: {self.account_display} ({self.account_number})")
    
    def _get_account_number(self) -> str:
        """API에서 계좌번호 가져오기 (전체 번호 표시)"""
        try:
            # API 커넥터에서 계좌번호 정보 추출
            if hasattr(self.api, 'config'):
                account_number = self.api.config.get('CANO', '')
                if account_number:
                    return account_number  # 전체 계좌번호 반환
            
            # AuthoritativeRegisterKeyLoader를 통한 계좌번호 조회
            try:
                from support.authoritative_register_key_loader import get_authoritative_loader
                reader = get_authoritative_loader()
                
                if self.account_type == "MOCK":
                    config = reader.get_fresh_config("MOCK")
                else:
                    config = reader.get_fresh_config("REAL")
                
                account_number = config.get('account_number', '')
                if account_number:
                    return account_number  # 전체 계좌번호 반환
            except Exception:
                pass
            
            return "계좌번호 조회 실패"
            
        except Exception as e:
            logger.warning(f"계좌번호 조회 오류: {e}")
            return "Unknown"
    
    async def retrieve_account_info(self, force_refresh: bool = False) -> Optional[AccountInfoData]:
        """
        계좌 정보 조회 및 메모리 저장
        
        Args:
            force_refresh: 강제 새로고침 여부
            
        Returns:
            AccountInfoData: 계좌 정보 객체, 실패시 None
        """
        try:
            logger.info(f"[{self.account_display}] 계좌 정보 조회 시작")
            
            # 캐시 확인 (force_refresh가 False이고 캐시가 유효한 경우)
            if not force_refresh and self._is_cache_valid():
                logger.info(f"[{self.account_display}] 캐시된 계좌 정보 반환")
                return self._cached_account_info
            
            # API를 통한 계좌 정보 조회
            raw_balance_data = await self.api.get_account_balance(force_refresh=True)
            
            if not raw_balance_data:
                logger.error(f"[{self.account_display}] 계좌 정보 조회 실패")
                return None
            
            # AccountInfoData 객체 생성 및 캐시
            account_info = AccountInfoData(raw_balance_data, self.account_type)
            self._cached_account_info = account_info
            self._last_update_time = datetime.now()
            
            logger.info(f"[{self.account_display}] 계좌 정보 조회 완료")
            return account_info
            
        except Exception as e:
            logger.error(f"[{self.account_display}] 계좌 정보 조회 중 오류: {e}")
            return None
    
    async def display_account_info(self, account_info: Optional[AccountInfoData] = None) -> bool:
        """
        계좌 정보를 콘솔에 상세 표시
        
        Args:
            account_info: 표시할 계좌 정보 (None시 새로 조회)
            
        Returns:
            bool: 표시 성공 여부
        """
        try:
            # 계좌 정보 확보
            if account_info is None:
                account_info = await self.retrieve_account_info()
                if account_info is None:
                    print(f"\n[ERROR] {self.account_display} 계좌 정보 조회 실패")
                    return False
            
            # 계좌 정보 헤더
            print(f"\n{'='*60}")
            print(f"[{self.account_display}] 계좌 정보")
            print(f"{'='*60}")
            
            # 기본 계좌 정보 (계좌번호 전체 표시)
            full_account_number = f"{self.api.config['CANO']}-{self.api.config['ACNT_PRDT_CD']}"
            print(f"계좌 번호:       {full_account_number:>15}")
            print(f"예수금 잔고:     {account_info.cash_balance_formatted:>15}")
            print(f"주문가능금액:    {account_info.available_cash_formatted:>15}")
            print(f"총 평가액:       {account_info.total_asset_formatted:>15}")
            print(f"평가손익:        {account_info.total_profit_loss_formatted:>15}")
            print(f"수익률:          {account_info.profit_rate_formatted:>15}")
            print(f"보유종목수:      {account_info.stock_count:>15}개")
            print(f"조회시간:        {account_info.updated_at.strftime('%H:%M:%S'):>15}")
            
            # 보유종목 상세 정보
            print(f"\n{account_info.holdings_display}")
            
            print("=" * 60)
            
            logger.info(f"[{self.account_display}] 계좌 정보 화면 표시 완료")
            return True
            
        except Exception as e:
            logger.error(f"[{self.account_display}] 계좌 정보 표시 중 오류: {e}")
            print(f"\n[ERROR] {self.account_display} 계좌 정보 표시 실패: {e}")
            return False
    
    async def send_telegram_notification(self, account_info: Optional[AccountInfoData] = None) -> bool:
        """
        계좌 정보를 텔레그램으로 전송
        
        Args:
            account_info: 전송할 계좌 정보 (None시 새로 조회)
            
        Returns:
            bool: 전송 성공 여부
        """
        try:
            # 텔레그램 알림 객체 초기화
            if self._telegram_notifier is None:
                from support.telegram_notifier import get_telegram_notifier
                self._telegram_notifier = get_telegram_notifier()
            
            if self._telegram_notifier is None:
                logger.warning(f"[{self.account_display}] 텔레그램 알림 시스템 비활성화")
                return False
            
            # 계좌 정보 확보
            if account_info is None:
                account_info = await self.retrieve_account_info()
                if account_info is None:
                    logger.error(f"[{self.account_display}] 텔레그램 전송용 계좌 정보 조회 실패")
                    return False
            
            # 텔레그램 메시지 구성
            message = self._generate_telegram_message(account_info)
            
            # 텔레그램 전송
            await self._telegram_notifier.send_message(message)
            
            logger.info(f"[{self.account_display}] 텔레그램 계좌 정보 전송 완료")
            return True
            
        except Exception as e:
            logger.warning(f"[{self.account_display}] 텔레그램 전송 오류: {e}")
            return False
    
    def _generate_telegram_message(self, account_info: AccountInfoData) -> str:
        """텔레그램 메시지 생성"""
        message = f"[{self.account_display}] 계좌 정보 조회 완료\n"
        # 계좌번호 전체 표시 (CANO-ACNT_PRDT_CD 형식)
        if 'CANO' not in self.api.config or 'ACNT_PRDT_CD' not in self.api.config:
            raise Exception("API 설정에 계좌번호 정보가 없습니다")
            
        full_account_number = f"{self.api.config['CANO']}-{self.api.config['ACNT_PRDT_CD']}"
        message += f"계좌번호: {full_account_number}\n"
        message += f"예수금: {account_info.cash_balance_formatted}\n"
        message += f"주문가능금액: {account_info.available_cash_formatted}\n"
        message += f"총 평가액: {account_info.total_asset_formatted}\n"
        message += f"평가손익: {account_info.total_profit_loss_formatted}\n"
        message += f"수익률: {account_info.profit_rate_formatted}\n"
        message += f"보유종목수: {account_info.stock_count}개"
        
        # 보유종목 목록 추가 (모든 종목)
        if account_info.holdings:
            message += "\n\n[보유종목 목록]"
            for i, holding in enumerate(account_info.holdings, 1):
                stock_name = holding['stock_name']
                stock_code = holding['stock_code']
                quantity = holding['quantity']
                total_value = holding['total_value']
                message += f"\n{i}. {stock_name}({stock_code}), {quantity:,}주, {total_value:,.0f}원"
        
        return message
    
    def get_cached_account_info(self) -> Optional[AccountInfoData]:
        """캐시된 계좌 정보 반환"""
        return self._cached_account_info
    
    def _is_cache_valid(self, cache_duration_minutes: int = 5) -> bool:
        """캐시 유효성 확인 (기본 5분)"""
        if self._cached_account_info is None or self._last_update_time is None:
            return False
        
        elapsed = datetime.now() - self._last_update_time
        return elapsed.total_seconds() < (cache_duration_minutes * 60)
    
    async def get_available_cash(self) -> float:
        """주문가능금액 조회 (간편 메서드)"""
        account_info = await self.retrieve_account_info()
        return account_info.available_cash if account_info else 0.0
    
    async def get_stock_quantity(self, stock_code: str) -> int:
        """특정 종목 보유 수량 조회"""
        account_info = await self.retrieve_account_info()
        if not account_info:
            return 0
        
        for holding in account_info.holdings:
            if holding['stock_code'] == stock_code:
                return holding['quantity']
        return 0
    
    async def full_account_process(self, display: bool = True, telegram: bool = True) -> Optional[AccountInfoData]:
        """
        계좌 정보 전체 프로세스 (조회 → 표시 → 텔레그램)
        
        Args:
            display: 콘솔 표시 여부
            telegram: 텔레그램 전송 여부
            
        Returns:
            AccountInfoData: 계좌 정보 객체
        """
        try:
            # 1. 계좌 정보 조회
            account_info = await self.retrieve_account_info(force_refresh=True)
            if not account_info:
                logger.error(f"[{self.account_display}] 전체 프로세스: 계좌 정보 조회 실패")
                return None
            
            # 2. 콘솔 표시
            if display:
                await self.display_account_info(account_info)
            
            # 3. 텔레그램 전송
            if telegram:
                await self.send_telegram_notification(account_info)
            
            logger.info(f"[{self.account_display}] 계좌 정보 전체 프로세스 완료")
            return account_info
            
        except Exception as e:
            logger.error(f"[{self.account_display}] 전체 프로세스 오류: {e}")
            return None


# 전역 인스턴스 관리
_account_info_managers: Dict[str, AccountInfoManager] = {}


def get_account_info_manager(api_connector, account_type: str = "REAL") -> AccountInfoManager:
    """
    AccountInfoManager 인스턴스 반환 (싱글톤 패턴)
    
    Args:
        api_connector: API 연결 객체
        account_type: 계좌 유형 ("REAL" 또는 "MOCK")
        
    Returns:
        AccountInfoManager: 계좌 정보 관리자 인스턴스
    """
    global _account_info_managers
    
    cache_key = f"{account_type}_{id(api_connector)}"
    
    if cache_key not in _account_info_managers:
        _account_info_managers[cache_key] = AccountInfoManager(api_connector, account_type)
        logger.info(f"새로운 AccountInfoManager 인스턴스 생성: {account_type}")
    
    return _account_info_managers[cache_key]


async def quick_account_check(account_type: str = "REAL", display: bool = True, telegram: bool = False) -> Optional[Dict[str, Any]]:
    """
    빠른 계좌 확인 함수 (독립 실행용)
    
    Args:
        account_type: 계좌 유형 ("REAL" 또는 "MOCK")
        display: 콘솔 표시 여부
        telegram: 텔레그램 전송 여부
        
    Returns:
        Dict: 계좌 정보 요약
    """
    try:
        from support.api_connector import KISAPIConnector
        
        # API 연결
        api = KISAPIConnector(is_mock=(account_type == "MOCK"))
        
        # 계좌 정보 관리자 생성 및 실행
        account_manager = get_account_info_manager(api, account_type)
        account_info = await account_manager.full_account_process(display=display, telegram=telegram)
        
        return account_info.get_summary_dict() if account_info else None
        
    except Exception as e:
        logger.error(f"빠른 계좌 확인 실패 ({account_type}): {e}")
        return None