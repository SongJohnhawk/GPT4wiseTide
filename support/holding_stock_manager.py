"""
보유종목 선택매도 관리자
- 보유종목 현황 조회
- 선택된 종목 일괄 매도
- 모의투자 전용 기능
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class HoldingStockManager:
    """보유종목 선택매도 관리 클래스"""
    
    def __init__(self, api_connector):
        """
        Args:
            api_connector: KISAPIConnector 인스턴스 (모의투자 모드)
        """
        self.api = api_connector
        if not api_connector.is_mock:
            raise ValueError("보유종목 선택매도는 모의투자 전용 기능입니다")
    
    def get_current_holdings(self) -> List[Dict]:
        """현재 보유종목 현황 조회"""
        try:
            logger.info("보유종목 현황 조회 시작")
            
            # 실시간 계좌 조회 (캐시 사용 안 함)
            
            # 계좌잔고 조회 (보유종목 포함, 강제 갱신)
            balance_data = self.api.get_account_balance(force_refresh=True)
            if not balance_data:
                logger.error("계좌 정보 조회 실패")
                return []
            
            # 보유종목 정보 추출
            holdings = []
            
            # output1에서 보유종목 정보 확인
            if 'output1' in balance_data:
                output1_data = balance_data['output1']
                
                for item in balance_data['output1']:
                    # 보유수량이 0보다 큰 종목만 추가
                    quantity = self._safe_int(item.get('hldg_qty', '0'))
                    if quantity > 0:
                        stock_code = item.get('pdno', '')
                        stock_name = item.get('prdt_name', '').strip()
                        current_price = self._safe_float(item.get('prpr', '0'))
                        purchase_price = self._safe_float(item.get('pchs_avg_pric', '0'))
                        evaluation_amount = self._safe_float(item.get('evlu_amt', '0'))
                        profit_loss = self._safe_float(item.get('evlu_pfls_amt', '0'))
                        profit_rate = self._safe_float(item.get('evlu_pfls_rt', '0'))
                        
                        holdings.append({
                            'stock_code': stock_code,
                            'stock_name': stock_name,
                            'quantity': quantity,
                            'current_price': current_price,
                            'purchase_price': purchase_price,
                            'evaluation_amount': evaluation_amount,
                            'profit_loss': profit_loss,
                            'profit_rate': profit_rate
                        })
            
            logger.info(f"보유종목 {len(holdings)}개 조회 완료")
            return holdings
            
        except Exception as e:
            logger.error(f"보유종목 조회 실패: {e}")
            return []
    
    def display_holdings_menu(self) -> Optional[str]:
        """보유종목 목록을 메뉴 형태로 출력하고 사용자 선택 받기"""
        try:
            holdings = self.get_current_holdings()
            
            if not holdings:
                print("\n보유중인 종목이 없습니다.")
                return None
            
            print("\n[ 보유종목 현황 ]")
            print("-" * 90)
            print(f"{'번호':<5} {'종목명':<20} {'보유수량':>10} {'현재가':>12} {'평가손익':>15} {'수익률':>10}")
            print("-" * 90)
            
            for i, holding in enumerate(holdings, 1):
                # 종목명 길이 조정 (한글 고려)
                stock_name = holding['stock_name']
                if self._get_display_width(stock_name) > 18:
                    stock_name = stock_name[:9] + "..."
                
                # 포맷팅
                quantity = f"{holding['quantity']:,}주"
                current_price = f"{holding['current_price']:,.0f}원"
                profit_loss = holding['profit_loss']
                profit_sign = "+" if profit_loss >= 0 else ""
                profit_loss_str = f"{profit_sign}{profit_loss:,.0f}원"
                profit_rate_str = f"{holding['profit_rate']:+.2f}%"
                
                # 정렬을 위한 패딩 계산
                name_padding = 20 - self._get_display_width(stock_name)
                stock_name_padded = stock_name + " " * name_padding
                
                print(f"{i:<5} {stock_name_padded} {quantity:>10} {current_price:>12} {profit_loss_str:>15} {profit_rate_str:>10}")
            
            print("-" * 90)
            print("0. 뒤로 가기")
            print("-" * 90)
            
            while True:
                try:
                    choice = input("\n매도할 종목 번호를 선택하세요: ").strip()
                    
                    if choice == '0':
                        return None
                    
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(holdings):
                        selected_holding = holdings[choice_num - 1]
                        return selected_holding['stock_code']
                    else:
                        print(f"1~{len(holdings)} 사이의 번호를 입력하세요.")
                        
                except ValueError:
                    print("올바른 번호를 입력하세요.")
                except KeyboardInterrupt:
                    print("\n사용자 취소")
                    return None
                    
        except Exception as e:
            logger.error(f"보유종목 메뉴 표시 실패: {e}")
            return None
    
    def sell_all_holdings(self, stock_code: str) -> bool:
        """선택된 종목을 일괄 매도"""
        try:
            logger.info(f"종목 일괄매도 시작: {stock_code}")
            
            # 해당 종목의 보유수량 확인
            holdings = self.get_current_holdings()
            target_holding = None
            
            for holding in holdings:
                if holding['stock_code'] == stock_code:
                    target_holding = holding
                    break
            
            if not target_holding:
                logger.error(f"보유종목에서 찾을 수 없음: {stock_code}")
                print(f"해당 종목을 보유하고 있지 않습니다: {stock_code}")
                return False
            
            stock_name = target_holding['stock_name']
            quantity = target_holding['quantity']
            current_price = target_holding['current_price']
            
            # 매도 확인
            print(f"\n[ 매도 확인 ]")
            print(f"종목명: {stock_name}")
            print(f"종목코드: {stock_code}")
            print(f"보유수량: {quantity:,}주")
            print(f"현재가: {current_price:,.0f}원")
            print(f"예상 매도금액: {quantity * current_price:,.0f}원")
            
            confirm = input(f"\n{stock_name} 전량을 시장가로 매도하시겠습니까? (y/yes 입력): ").strip().upper()
            
            if confirm not in ['Y', 'YES']:
                print("매도가 취소되었습니다.")
                return False
            
            # 시장가 매도 주문 실행
            logger.info(f"시장가 매도 주문 실행: {stock_code}, {quantity}주")
            
            order_result = self.api.place_sell_order(
                symbol=stock_code,  # place_sell_order는 symbol 파라미터를 사용
                quantity=quantity,
                price=0,  # 시장가 주문
                order_type="01"  # 시장가
            )
            
            if order_result and order_result.get('rt_cd') == '0':
                order_no = order_result.get('output', {}).get('ODNO', 'N/A')
                print(f"\nOK 매도 주문 성공!")
                print(f"주문번호: {order_no}")
                print(f"종목: {stock_name} ({stock_code})")
                print(f"수량: {quantity:,}주")
                print(f"주문유형: 시장가 매도")
                
                # 텔레그램 알림 전송
                self._send_telegram_sell_notification(
                    stock_code, stock_name, quantity, current_price, order_no
                )
                
                logger.info(f"매도 주문 성공: {stock_code}, 주문번호: {order_no}")
                return True
            else:
                error_msg = order_result.get('msg1', '알 수 없는 오류') if order_result else '주문 실패'
                print(f"\nERR 매도 주문 실패: {error_msg}")
                logger.error(f"매도 주문 실패: {stock_code}, 오류: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"일괄매도 실패: {e}")
            print(f"매도 중 오류가 발생했습니다: {e}")
            return False
    
    def run_holding_stock_menu(self):
        """보유종목 선택매도 메뉴 실행"""
        try:
            print("\n[ 보유종목 선택매도 ]")
            print("-" * 50)
            print("※ 선택한 종목을 시장가로 전량 매도합니다")
            print("-" * 50)
            
            # 보유종목 메뉴 표시 및 선택
            selected_stock_code = self.display_holdings_menu()
            
            if selected_stock_code:
                # 선택된 종목 일괄 매도
                success = self.sell_all_holdings(selected_stock_code)
                
                if success:
                    print("\n매도 주문이 완료되었습니다.")
                    print("체결 확인은 계좌 조회에서 확인 가능합니다.")
                else:
                    print("\n매도 주문에 실패했습니다.")
            else:
                print("\n메뉴로 돌아갑니다.")
                
        except Exception as e:
            logger.error(f"보유종목 메뉴 실행 실패: {e}")
            print(f"오류가 발생했습니다: {e}")
    
    def _safe_float(self, value, default: float = 0.0) -> float:
        """안전한 float 변환"""
        try:
            if value is None or value == '' or value == '-':
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def _safe_int(self, value, default: int = 0) -> int:
        """안전한 int 변환"""
        try:
            if value is None or value == '' or value == '-':
                return default
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def _get_display_width(self, text: str) -> int:
        """문자열의 표시 너비 계산 (한글은 2, 영문/숫자는 1)"""
        width = 0
        for char in text:
            if ord(char) > 127:  # ASCII가 아닌 문자 (주로 한글)
                width += 2
            else:
                width += 1
        return width
    
    def _send_telegram_sell_notification(self, stock_code: str, stock_name: str, 
                                       quantity: int, price: float, order_no: str):
        """텔레그램 매도 알림 전송 (동기 방식)"""
        try:
            import requests
            import json
            
            # 설정에서 텔레그램 정보 로드 (Register_Key.md 우선)
            try:
                from .authoritative_register_key_loader import get_authoritative_loader
                reader = get_authoritative_loader()
                telegram_config = reader.get_fresh_telegram_config()
                
                bot_token = telegram_config.get('bot_token')
                chat_id = telegram_config.get('chat_id')
                
                if not bot_token or not chat_id:
                    logger.debug("Register_Key.md에 텔레그램 설정이 없음")
                    return
                    
            except Exception as e:
                logger.debug(f"텔레그램 설정 로드 실패: {e}")
                return
            
            # 매도 금액 계산
            sell_amount = quantity * price
            
            # 알림 메시지 생성 (HTML 형식)
            message = f"<b>보유종목 일괄매도 완료</b>\n\n"
            message += f"<b>종목:</b> {stock_name} ({stock_code})\n"
            message += f"<b>수량:</b> {quantity:,}주\n"
            message += f"<b>매도가:</b> {price:,.0f}원\n"
            message += f"<b>매도금액:</b> {sell_amount:,.0f}원\n"
            message += f"<b>주문번호:</b> {order_no}\n"
            message += f"<b>시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"<b>주문유형:</b> 시장가 매도 (전량)"
            
            # 동기 HTTP 요청으로 텔레그램 전송
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                data = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }
                
                response = requests.post(url, json=data, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"텔레그램 매도 알림 전송: {stock_name}({stock_code}) {quantity}주")
                    print("OK 텔레그램 알림 전송 완료")
                else:
                    logger.error(f"텔레그램 전송 실패: HTTP {response.status_code}")
                    print("WARN 텔레그램 알림 전송 실패 (매도는 정상 완료)")
                    
            except requests.RequestException as e:
                logger.error(f"텔레그램 요청 실패: {e}")
                print("WARN 텔레그램 알림 전송 실패 (매도는 정상 완료)")
                
        except Exception as e:
            logger.error(f"텔레그램 알림 시스템 오류: {e}")
            print("WARN 텔레그램 알림 시스템 오류 (매도는 정상 완료)")


# 글로벌 인스턴스 관리
_holding_stock_manager = None

def get_holding_stock_manager(api_connector):
    """HoldingStockManager 인스턴스 반환"""
    global _holding_stock_manager
    if _holding_stock_manager is None or _holding_stock_manager.api != api_connector:
        _holding_stock_manager = HoldingStockManager(api_connector)
    return _holding_stock_manager