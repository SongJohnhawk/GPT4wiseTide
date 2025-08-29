"""
알고리즘 인터페이스
모든 알고리즘이 상속해야 하는 기본 클래스
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAlgorithm(ABC):
    """알고리즘 기본 인터페이스"""
    
    @abstractmethod
    def analyze(self, stock_data: Dict[str, Any]) -> str:
        """
        주식 데이터를 분석하여 매매 신호 생성
        
        Args:
            stock_data: 주식 데이터 딕셔너리
                - symbol: 종목코드
                - current_price: 현재가
                - prices: 가격 리스트
                - volume: 거래량
                - change_rate: 변화율
                - timestamp: 시간
        
        Returns:
            str: 매매 신호 ('BUY', 'SELL', 'HOLD')
        """
        pass
    
    def calculate_position_size(self, current_price: float, account_balance: float) -> int:
        """
        포지션 크기 계산 (선택적 구현)
        
        Args:
            current_price: 현재가
            account_balance: 계좌 잔고
            
        Returns:
            int: 매수 수량
        """
        # 기본값: 계좌의 10%
        position_value = account_balance * 0.1
        return int(position_value / current_price)
    
    def get_stop_loss(self, entry_price: float, position_type: str) -> float:
        """
        손절가 계산 (선택적 구현)
        
        Args:
            entry_price: 진입가
            position_type: 포지션 타입 ('LONG', 'SHORT')
            
        Returns:
            float: 손절가
        """
        if position_type == 'LONG':
            return entry_price * 0.95  # 5% 손절
        else:
            return entry_price * 1.05
    
    def get_take_profit(self, entry_price: float, position_type: str) -> float:
        """
        익절가 계산 (선택적 구현)
        
        Args:
            entry_price: 진입가
            position_type: 포지션 타입 ('LONG', 'SHORT')
            
        Returns:
            float: 익절가
        """
        if position_type == 'LONG':
            return entry_price * 1.05  # 5% 익절
        else:
            return entry_price * 0.95
    
    def get_name(self) -> str:
        """알고리즘 이름"""
        return "기본 알고리즘"
    
    def get_version(self) -> str:
        """알고리즘 버전"""
        return "1.0"
    
    def get_description(self) -> str:
        """알고리즘 설명"""
        return "기본 알고리즘"
    
    def on_algorithm_start(self, account_type: str = "MOCK", initial_balance: float = 0.0) -> str:
        """
        알고리즘 시작 시 호출되는 메서드
        
        Args:
            account_type: 계좌 유형 ("REAL" 또는 "MOCK")
            initial_balance: 초기 잔고
            
        Returns:
            str: 시작 메시지
        """
        from datetime import datetime
        
        account_display = "실계좌" if account_type == "REAL" else "모의계좌"
        message = (
            f"[{account_display}] {self.get_name()} 시작\n"
            f"알고리즘: {self.get_name()}\n"
            f"버전: {self.get_version()}\n"
            f"초기잔고: {initial_balance:,.0f}원\n"
            f"시작시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"설명: {self.get_description()}"
        )
        return message
    
    def on_algorithm_end(self, account_type: str = "MOCK", final_balance: float = 0.0, 
                        session_stats: Dict[str, Any] = None) -> str:
        """
        알고리즘 종료 시 호출되는 메서드
        
        Args:
            account_type: 계좌 유형 ("REAL" 또는 "MOCK") 
            final_balance: 최종 잔고
            session_stats: 세션 통계 정보
            
        Returns:
            str: 종료 메시지
        """
        from datetime import datetime
        
        account_display = "실계좌" if account_type == "REAL" else "모의계좌"
        
        if session_stats:
            total_trades = session_stats.get('total_trades', 0)
            session_duration = session_stats.get('session_duration', '알 수 없음')
            profit_loss = session_stats.get('profit_loss', 0)
            success_rate = session_stats.get('success_rate', 0)
        else:
            total_trades = 0
            session_duration = '알 수 없음'
            profit_loss = 0
            success_rate = 0
        
        message = (
            f"[{account_display}] {self.get_name()} 종료\n"
            f"알고리즘: {self.get_name()}\n"
            f"종료시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"최종잔고: {final_balance:,.0f}원\n"
            f"수익/손실: {profit_loss:+,.0f}원\n"
            f"총 거래수: {total_trades}건\n"
            f"성공률: {success_rate:.1f}%\n"
            f"운영시간: {session_duration}\n"
            f"수고하셨습니다!"
        )
        return message