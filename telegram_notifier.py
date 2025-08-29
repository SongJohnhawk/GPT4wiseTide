"""
Telegram 알림 모듈
tideWise 자동매매 시스템의 실시간 상태 및 거래 알림 전송
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# aiohttp는 선택적 의존성
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

from support.log_manager import get_log_manager

# 로그 매니저를 통한 로거 설정
log_manager = get_log_manager()
logger = log_manager.setup_logger('system', __name__)


class TelegramNotifier:
    """텔레그램 알림 전송 클래스"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        """
        텔레그램 알림 초기화
        
        Args:
            bot_token: 텔레그램 봇 토큰
            chat_id: 채팅방 ID
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp 모듈이 없어서 텔레그램 알림이 비활성화됩니다.")
            self.enabled = False
            self.bot_token = None
            self.chat_id = None
            self.base_url = None
            return
        
        # 설정에서 봇 토큰과 채팅 ID 로드
        self.bot_token = bot_token or self._load_bot_token()
        self.chat_id = chat_id or self._load_chat_id()
        
        # 텔레그램 연동 정보 검증
        if not self.bot_token or not self.chat_id:
            logger.warning("텔레그램 연동을 위한 정보가 없어 텔레그램은 작동하지 않습니다.")
            self.enabled = False
            self.base_url = None
        else:
            self.enabled = True
            self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
    def get_account_display_name(self, account_type: str) -> str:
        """계좌 타입을 한국어 표시명으로 변환"""
        return "실제계좌" if account_type == "REAL" else "모의투자계좌"
    
    async def initialize(self) -> bool:
        """텔레그램 알리미 초기화 (비동기 호환성)
        
        Returns:
            bool: 초기화 성공 여부
        """
        try:
            if not self.enabled:
                if not AIOHTTP_AVAILABLE:
                    logger.info("텔레그램 알림 비활성화됨 (aiohttp 모듈 없음)")
                else:
                    logger.info("텔레그램 연동을 위한 정보가 없어 텔레그램은 작동하지 않습니다.")
                return True  # 비활성화 상태도 정상으로 간주
            
            # 연결 테스트 (선택사항)
            logger.info("텔레그램 알리미 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"텔래그램 알리미 초기화 오류: {e}")
            return False
    
    def _load_chat_id(self) -> Optional[str]:
        """설정 파일에서 채팅 ID 로드"""
        try:
            # Register_Key.md에서 채팅 ID 로드 시도 (최우선, 실시간)
            from .authoritative_register_key_loader import get_authoritative_loader
            reader = get_authoritative_loader()
            telegram_config = reader.get_fresh_telegram_config()
            chat_id = telegram_config.get('chat_id')
            if chat_id and chat_id.strip() and not chat_id.startswith('[여기에'):
                logger.info("Register_Key.md에서 텔레그램 채팅 ID 로드 성공")
                return chat_id.strip()
        except Exception as e:
            logger.debug("Register_Key.md에서 채팅 ID 로드 실패")
        
        # Single Source-of-Truth: Register_Key.md만 사용, 백업 파일 접근 금지
        return None
    
    def _load_bot_token(self) -> Optional[str]:
        """설정 파일에서 봇 토큰 로드"""
        try:
            # Register_Key.md에서 봇 토큰 로드 시도 (최우선)
            from .authoritative_register_key_loader import get_authoritative_loader
            reader = get_authoritative_loader()
            telegram_config = reader.get_fresh_telegram_config()
            bot_token = telegram_config.get('bot_token')
            if bot_token and bot_token.strip() and not bot_token.startswith('[여기에'):
                logger.info("Register_Key.md에서 텔레그램 봇 토큰 로드 성공")
                return bot_token.strip()
        except Exception as e:
            logger.debug(f"Register_Key.md에서 봇 토큰 로드 실패: {e}")
        
        # Single Source-of-Truth: Register_Key.md만 사용, 백업 파일 접근 금지
        return None
    
    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        텔레그램 메시지 전송 (개선된 오류 처리)
        
        Args:
            message: 전송할 메시지
            parse_mode: 메시지 파싱 모드 (HTML, Markdown)
            
        Returns:
            전송 성공 여부
        """
        if not self.enabled:
            logger.debug("텔레그램 연동을 위한 정보가 없어 텔레그램은 작동하지 않습니다.")
            return False
            
        if not self.chat_id or not self.bot_token:
            logger.debug("텔레그램 연동을 위한 정보가 없어 텔레그램은 작동하지 않습니다.")
            return False
        
        # 매 요청마다 새로운 세션 사용 (세션 누수 방지)
        session = None
        try:
            # KeyboardInterrupt 및 shutdown 예외 처리 개선
            try:
                session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
            except (KeyboardInterrupt, SystemExit):
                # 프로그램 종료 중이면 조용히 반환
                return False
            except Exception as e:
                logger.debug(f"세션 생성 실패 (종료 중일 수 있음): {e}")
                return False
            
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    logger.debug("텔레그램 메시지 전송 성공")
                    return True
                else:
                    logger.error(f"텔레그램 메시지 전송 실패: {response.status}")
                    return False
                    
        except (KeyboardInterrupt, SystemExit):
            # 프로그램 종료 중이면 조용히 반환
            return False
        except Exception as e:
            # 비동기 작업 취소 및 기타 오류 방어적 처리
            import asyncio
            if hasattr(asyncio, 'CancelledError') and isinstance(e, asyncio.CancelledError):
                return False
            # 기타 오류는 디버그 로그로 처리
            logger.debug(f"텔레그램 메시지 전송 오류: {e}")
            return False
        finally:
            # 반드시 세션 닫기
            if session and not session.closed:
                try:
                    await session.close()
                    # 세션이 완전히 닫힐 때까지 잠시 대기 (시간 단축)
                    import asyncio
                    await asyncio.sleep(0.05)
                except (KeyboardInterrupt, SystemExit) as exit_error:
                    # 프로그램 종료 중이면 세션 닫기 생략
                    pass
                except Exception as close_error:
                    # 방어적으로 asyncio.CancelledError 체크
                    import asyncio
                    if hasattr(asyncio, 'CancelledError') and isinstance(close_error, asyncio.CancelledError):
                        pass
                    # 기타 세션 닫기 오류 무시
                    pass
    
    async def send_connection_info(self, account_type: str, account_number: str, balance_info: dict = None, positions: list = None) -> bool:
        """계좌 연결 정보 전송"""
        if not self.enabled:
            return False
        message = f"""
<b>tideWise 계좌 연결</b>

<b>계좌 타입:</b> {account_type}
<b>계좌 번호:</b> {account_number}
<b>연결 시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[성공] API 연결이 성공적으로 완료되었습니다.
        """
        
        # 잔고 정보 추가
        if balance_info:
            try:
                ord_psbl_cash = int(balance_info.get('ord_psbl_cash', 0))
                dnca_tot_amt = int(balance_info.get('dnca_tot_amt', 0))
                tot_evlu_amt = int(balance_info.get('tot_evlu_amt', 0))
                
                message += f"""

<b>계좌 잔고 현황:</b>
• 주문가능금액: {ord_psbl_cash:,}원
• 예수금: {dnca_tot_amt:,}원
• 총평가금액: {tot_evlu_amt:,}원"""
                
                # 수익률 계산
                if tot_evlu_amt > 0 and dnca_tot_amt > 0:
                    profit_loss = tot_evlu_amt - dnca_tot_amt
                    profit_rate = (profit_loss / dnca_tot_amt) * 100
                    message += f"""
• 평가손익: {profit_loss:,}원 ({profit_rate:+.2f}%)"""
                    
            except (ValueError, TypeError) as e:
                message += f"\n\n[오류] 잔고 정보 처리 실패: {e}"
        
        # 보유종목 정보 추가
        if positions and len(positions) > 0:
            message += f"""

<b>보유종목 현황:</b> 총 {len(positions)}개"""
            
            # 모든 보유 종목 표시 (사용자 요청에 따라 제한 없이 전체 표시)
            for i, stock in enumerate(positions):
                try:
                    stock_name = stock.get('prdt_name', '알 수 없음')
                    stock_code = stock.get('pdno', '')
                    hldg_qty = int(stock.get('hldg_qty', 0))
                    evlu_pfls_rt = float(stock.get('evlu_pfls_rt', 0))
                    
                    # 사용자 요청 형식: '종목명(종목코드), 보유수량, 조회시점에서 수익률'
                    message += f"""
• {stock_name}({stock_code}), {hldg_qty:,}주, {evlu_pfls_rt:+.2f}%"""
                    
                except (ValueError, TypeError) as e:
                    message += f"\n• 종목 정보 처리 오류: {e}"
        
        return await self.send_message(message.strip())
    
    async def send_trading_start(self, account_type: str, algorithm_name: str) -> bool:
        """자동매매 시작 알림 (계좌 유형 구분)"""
        if not self.enabled:
            return False
        
        account_display = "실제계좌" if account_type == "REAL" else "모의투자계좌"
        message = f"""
<b>[{account_display}] 자동매매 시작</b>

<b>계좌 타입:</b> {account_display}
<b>알고리즘:</b> {algorithm_name}
<b>시작 시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[시작] 자동매매가 시작되었습니다.
        """
        return await self.send_message(message.strip())
    
    async def send_trading_stop(self, reason: str = "사용자 요청", account_type: str = None) -> bool:
        """자동매매 중지 알림 (계좌 유형 구분)"""
        if not self.enabled:
            return False
        
        account_prefix = ""
        if account_type:
            account_display = "실제계좌" if account_type == "REAL" else "모의투자계좌"
            account_prefix = f"[{account_display}] "
        
        message = f"""
<b>{account_prefix}자동매매 중지</b>

<b>중지 사유:</b> {reason}
<b>중지 시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[중지] 자동매매가 중지되었습니다.
        """
        return await self.send_message(message.strip())
    
    async def send_trade_signal(self, symbol: str, signal: str, price: float, reason: str = "", api_connector=None, account_type: str = None) -> bool:
        """매매 신호 알림 (계좌 유형 구분)"""
        if not self.enabled:
            return False
        signal_text = {
            'BUY': '[매수]',
            'SELL': '[매도]',
            'HOLD': '[보유]'
        }
        
        # 계좌 타입 표시
        account_prefix = ""
        if account_type:
            account_display = self.get_account_display_name(account_type)
            account_prefix = f"[{account_display}] "
        
        # 종목명(코드) 형태로 표시
        display_name = symbol
        if api_connector:
            try:
                display_name = api_connector.get_stock_display_name(symbol)
            except Exception as e:
                logger.debug(f"종목명 조회 실패: {symbol} - {e}")
        
        message = f"""
{signal_text.get(signal, '[대기]')} <b>{account_prefix}매매 신호</b>

<b>종목:</b> {display_name}
<b>신호:</b> {signal}
<b>현재가:</b> {price:,}원
<b>사유:</b> {reason or '알고리즘 분석'}
<b>시간:</b> {datetime.now().strftime('%H:%M:%S')}
        """
        return await self.send_message(message.strip())
    
    async def send_order_result(self, symbol: str, order_type: str, quantity: int, 
                              price: float, result: str, order_id: str = "",
                              balance_info: Dict = None, profit_rate: float = None, 
                              api_connector=None, avg_buy_price: float = None,
                              account_type: str = None) -> bool:
        """주문 결과 알림 (상세 정보 포함, 계좌 유형 구분)"""
        if not self.enabled:
            return False
        result_text = "[성공]" if result == "성공" else "[실패]"
        
        # 계좌 타입 표시
        account_prefix = ""
        if account_type:
            account_display = self.get_account_display_name(account_type)
            account_prefix = f"[{account_display}] "
        
        # 종목명(코드) 형태로 표시
        display_name = symbol
        if api_connector:
            try:
                display_name = api_connector.get_stock_display_name(symbol)
            except Exception as e:
                logger.debug(f"종목명 조회 실패: {symbol} - {e}")
        
        # 총 금액 계산
        total_amount = quantity * price
        
        message = f"""
{result_text} <b>{account_prefix}주문 결과</b>

<b>종목:</b> {display_name}
<b>주문:</b> {order_type}
<b>수량:</b> {quantity:,}주
<b>1주당 가격:</b> {price:,}원
<b>총 거래금액:</b> {total_amount:,}원
<b>결과:</b> {result}
<b>주문번호:</b> {order_id or 'N/A'}
<b>시간:</b> {datetime.now().strftime('%H:%M:%S')}
        """
        
        # 매수 시 잔고 현황 추가
        if order_type == "매수" and result == "성공" and balance_info:
            cash = int(balance_info.get('ord_psbl_cash', 0))
            total_eval_amount = int(balance_info.get('tot_evlu_amt', 0))
            deposit = int(balance_info.get('dnca_tot_amt', 0))
            
            message += f"""
            
[계좌] <b>매수 후 계좌 현황</b>
<b>1주당 매수가격:</b> {price:,}원
<b>매수 수량:</b> {quantity:,}주
<b>총 매수금액:</b> {total_amount:,}원
<b>총 예수금 잔고:</b> {deposit:,}원
<b>주문가능금액:</b> {cash:,}원
<b>총 평가금액:</b> {total_eval_amount:,}원
            """
        
        # 매도 시 수익률 및 수익금 상세 표시
        elif order_type == "매도" and result == "성공":
            if profit_rate is not None:
                profit_text = f"+{profit_rate:.2f}%" if profit_rate > 0 else f"{profit_rate:.2f}%"
                profit_emoji = "[수익]" if profit_rate > 0 else "[손실]"
                
                # 수익금 계산
                if avg_buy_price and avg_buy_price > 0:
                    profit_per_share = price - avg_buy_price
                    total_profit = profit_per_share * quantity
                    profit_amount_text = f"+{total_profit:,}원" if total_profit > 0 else f"{total_profit:,}원"
                    
                    message += f"""
                    
{profit_emoji} <b>매도 상세 수익</b>
<b>1주당 매도가격:</b> {price:,}원
<b>총 매도가격:</b> {total_amount:,}원
<b>총 매도 수익률:</b> {profit_text}
<b>총 매도 수익금액:</b> {profit_amount_text}
<b>평균매수가:</b> {avg_buy_price:,}원
<b>주당수익:</b> {profit_per_share:+,}원
                    """
                else:
                    message += f"""
                    
{profit_emoji} <b>매도 수익률</b>
<b>수익률:</b> {profit_text}
                    """
            
            if balance_info:
                cash = int(balance_info.get('ord_psbl_cash', 0))
                deposit = int(balance_info.get('dnca_tot_amt', 0))
                total_eval_amount = int(balance_info.get('tot_evlu_amt', 0))
                message += f"""
                
[계좌] <b>매도 후 계좌 현황</b>
<b>총 예수금 잔고:</b> {deposit:,}원
<b>주문가능금액:</b> {cash:,}원
<b>총 평가금액:</b> {total_eval_amount:,}원
                """
        return await self.send_message(message.strip())
    
    async def send_error_alert(self, error_type: str, error_message: str) -> bool:
        """에러 알림"""
        if not self.enabled:
            return False
        message = f"""
<b>시스템 에러</b>

<b>에러 타입:</b> {error_type}
<b>에러 내용:</b> {error_message}
<b>발생 시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[알림] 시스템을 확인해주세요.
        """
        return await self.send_message(message.strip())
    
    async def send_daily_summary(self, summary_data: Dict[str, Any]) -> bool:
        """일일 매매 요약"""
        if not self.enabled:
            return False
        message = f"""
<b>일일 매매 요약</b>

<b>총 수익:</b> {summary_data.get('total_profit', 0):,}원
<b>매수 횟수:</b> {summary_data.get('buy_count', 0)}회
<b>매도 횟수:</b> {summary_data.get('sell_count', 0)}회
<b>승률:</b> {summary_data.get('win_rate', 0):.1f}%
<b>요약 시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return await self.send_message(message.strip())
    
    async def close(self):
        """세션 종료 (더 이상 필요 없음 - 각 요청마다 세션을 닫기 때문)"""
        # 각 메시지 전송마다 새 세션을 사용하고 즉시 닫기 때문에 별도 정리 불필요
        pass


# 전역 텔레그램 알림 인스턴스
_telegram_notifier = None

def get_telegram_notifier() -> TelegramNotifier:
    """텔레그램 알림 싱글톤 인스턴스 반환"""
    global _telegram_notifier
    if _telegram_notifier is None:
        _telegram_notifier = TelegramNotifier()
    return _telegram_notifier

async def send_telegram_message(message: str) -> bool:
    """간편 텔레그램 메시지 전송"""
    notifier = get_telegram_notifier()
    if not notifier.enabled:
        return False
    return await notifier.send_message(message)