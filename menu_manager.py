#!/usr/bin/env python3
"""
MenuManager - tideWise 메뉴 시스템 관리 클래스
run.py에서 분리된 메뉴 관련 기능들을 통합 관리
"""

import asyncio
from typing import Optional, List, Dict
from support.market_close_controller import get_market_close_controller


class MenuManager:
    """메뉴 시스템을 관리하는 클래스"""
    
    def __init__(self, selected_algorithm: dict):
        """
        MenuManager 초기화
        
        Args:
            selected_algorithm: 현재 선택된 알고리즘 정보를 담은 딕셔너리
        """
        self.selected_algorithm = selected_algorithm
    
    def _is_debug_mode(self) -> bool:
        """디버그 모드 확인"""
        import os
        return os.environ.get('K_AUTOTRADE_DEBUG', '').lower() in ['true', '1', 'yes']
    
    def print_banner(self):
        """프로그램 배너 출력"""
        print("=" * 80)
        print("                         tideWise v11.0")
        print("                    한국투자증권 자동매매 시스템")
        print("=" * 80)
        print("  알고리즘 기반 지능형 자동매매 | 실시간 시장 분석 | 리스크 관리")
        print("=" * 80)
    
    def show_main_menu(self, loading_results: Optional[List[str]] = None):
        """메인 메뉴 표시"""
        print("\n[ 메인 메뉴 ]")
        print("-" * 50)
        print("1. 단타매매")
        print("2. 단타매매 알고리즘변경")
        print("3. Setup")
        print("0. 종료")
        print("-" * 50)
        # 파일명이 있으면 파일명을 우선 표시, 없으면 이름 표시
        algorithm_display = self.selected_algorithm['info'].get('filename', self.selected_algorithm['info']['name'])
        print(f"현재 선택된 알고리즘: {algorithm_display}")
        
        # 자동로딩결과 표시 (디버그 모드에서만)
        if loading_results and self._is_debug_mode():
            print("\n[ 자동로딩결과 ]")
            print("-" * 30)
            for result in loading_results:
                print(result)
    
    def show_scalping_submenu(self):
        """단타매매 서브메뉴 표시"""
        print("\n[ 단타매매 메뉴 ]")
        print("-" * 50)
        print("1. 실전단타매매")
        print("2. 모의단타매매")
        print("0. 메인 메뉴로 돌아가기")
        print("-" * 50)
    
    async def handle_scalping_submenu(self):
        """단타매매 서브메뉴 처리"""
        while True:
            try:
                self.show_scalping_submenu()
                choice = self._safe_input("\n선택: ")
                
                if choice == '0':
                    print("\n메인 메뉴로 돌아갑니다.")
                    break
                elif choice == '1':
                    # 실전단타매매 실행
                    await self._run_real_scalping()
                elif choice == '2':
                    # 모의단타매매 실행
                    await self._run_mock_scalping()
                else:
                    print("\n잘못된 선택입니다. 다시 입력해주세요.")
                    
            except KeyboardInterrupt:
                print("\n\n[INTERRUPT] 단타매매 서브메뉴에서 중단되었습니다.")
                break
            except Exception as e:
                print(f"\n[ERROR] 단타매매 서브메뉴 처리 중 예상치 못한 오류: {e}")
    
    async def _run_real_scalping(self):
        """실전단타매매 실행"""
        try:
            # 장마감 체크 - ON일 때 시간 후 실행 방지
            from support.market_close_controller import get_market_close_controller
            from datetime import datetime
            
            market_controller = get_market_close_controller()
            if market_controller.is_market_close_check_enabled():
                current_time = datetime.now().time()
                if market_controller.should_stop_trading(current_time):
                    print("\n[MARKET_CLOSE] 장마감 체크 설정이 ON이고 마감 시간이 지났습니다.")
                    print("설정을 변경하려면 메뉴 3번(Setup) → 4번(장마감 체크 설정)에서 OFF로 변경하세요.")
                    return
                elif market_controller.should_enter_guard_mode(current_time):
                    time_info = market_controller.get_time_until_close(current_time)
                    print(f"\n[WARNING] 장 마감까지 {time_info['formatted']} - 신규 진입이 제한됩니다.")
            
            # 엄격한 알고리즘 검증 - 실전단타매매 시작 전 필수 확인
            from support.algorithm_selector import get_algorithm_selector
            from pathlib import Path
            
            algorithm_selector = get_algorithm_selector(Path.cwd())
            algorithm_selector.load_algorithm_state()
            
            if not algorithm_selector.ensure_algorithm_available():
                print("\n[FAILED] 실전단타매매를 시작할 수 없습니다.")
                print("알고리즘이 선택되지 않았습니다.")
                print("\n해결방법:")
                print("1. 메뉴 4번에서 단타매매 알고리즘을 먼저 선택하세요")
                print("2. day_trade_Algorithm 폴더에 알고리즘 파일이 있는지 확인하세요")
                return
            
            from support.day_trading_runner import DayTradingRunner
            from support.telegram_notifier import get_telegram_notifier
            
            # 텔레그램 알림 시스템 초기화
            telegram = get_telegram_notifier()
            
            print("\n실전단타매매를 시작합니다...")
            
            # 시작 알림
            if telegram:
                start_msg = "[실계좌] 단타매매 메뉴 선택 - 실행 준비 중"
                await telegram.send_message(start_msg)
            
            day_trader = DayTradingRunner(
                account_type="REAL",
                selected_algorithm=self.selected_algorithm
            )
            
            # 실행 시작 알림
            if telegram:
                exec_msg = "[실계좌] 단타매매 알고리즘 실행 시작"
                await telegram.send_message(exec_msg)
            
            result = await day_trader.run()
            
            # 완료 알림
            if result:
                success_msg = "[실계좌] 실전단타매매가 성공적으로 완료되었습니다"
                print(f"\n[SUCCESS] {success_msg}")
                if telegram:
                    await telegram.send_message(success_msg)
            else:
                warning_msg = "[실계좌] 실전단타매매가 중단되었습니다"
                print(f"\n[WARNING] {warning_msg}")
                if telegram:
                    await telegram.send_message(warning_msg)
                
        except Exception as e:
            error_msg = f"[실계좌] 실전단타매매 실행 중 오류: {str(e)[:100]}"
            print(f"\n[ERROR] {error_msg}")
            
            # 오류 알림
            try:
                from support.telegram_notifier import get_telegram_notifier
                telegram = get_telegram_notifier()
                if telegram:
                    await telegram.send_message(error_msg)
            except:
                pass
    
    async def _run_mock_scalping(self):
        """모의단타매매 실행"""
        try:
            # 장마감 체크 - ON일 때 시간 후 실행 방지
            from support.market_close_controller import get_market_close_controller
            from datetime import datetime
            
            market_controller = get_market_close_controller()
            if market_controller.is_market_close_check_enabled():
                current_time = datetime.now().time()
                if market_controller.should_stop_trading(current_time):
                    print("\n[MARKET_CLOSE] 장마감 체크 설정이 ON이고 마감 시간이 지났습니다.")
                    print("설정을 변경하려면 메뉴 3번(Setup) → 4번(장마감 체크 설정)에서 OFF로 변경하세요.")
                    return
                elif market_controller.should_enter_guard_mode(current_time):
                    time_info = market_controller.get_time_until_close(current_time)
                    print(f"\n[WARNING] 장 마감까지 {time_info['formatted']} - 신규 진입이 제한됩니다.")
            
            # 엄격한 알고리즘 검증 - 모의단타매매 시작 전 필수 확인
            from support.algorithm_selector import get_algorithm_selector
            from pathlib import Path
            
            algorithm_selector = get_algorithm_selector(Path.cwd())
            algorithm_selector.load_algorithm_state()
            
            if not algorithm_selector.ensure_algorithm_available():
                print("\n[FAILED] 모의단타매매를 시작할 수 없습니다.")
                print("알고리즘이 선택되지 않았습니다.")
                print("\n해결방법:")
                print("1. 메뉴 4번에서 단타매매 알고리즘을 먼저 선택하세요")
                print("2. day_trade_Algorithm 폴더에 알고리즘 파일이 있는지 확인하세요")
                return
            
            from support.day_trading_runner import DayTradingRunner
            from support.telegram_notifier import get_telegram_notifier
            
            # 텔레그램 알림 시스템 초기화
            telegram = get_telegram_notifier()
            
            print("\n모의단타매매를 시작합니다...")
            
            # 시작 알림
            if telegram:
                start_msg = "[모의계좌] 단타매매 메뉴 선택 - 실행 준비 중"
                await telegram.send_message(start_msg)
            
            day_trader = DayTradingRunner(
                account_type="MOCK",
                selected_algorithm=self.selected_algorithm
            )
            
            # 실행 시작 알림
            if telegram:
                exec_msg = "[모의계좌] 단타매매 알고리즘 실행 시작"
                await telegram.send_message(exec_msg)
            
            result = await day_trader.run()
            
            # 완료 알림
            if result:
                success_msg = "[모의계좌] 모의단타매매가 성공적으로 완료되었습니다"
                print(f"\n[SUCCESS] {success_msg}")
                if telegram:
                    await telegram.send_message(success_msg)
            else:
                warning_msg = "[모의계좌] 모의단타매매가 중단되었습니다"
                print(f"\n[WARNING] {warning_msg}")
                if telegram:
                    await telegram.send_message(warning_msg)
                
        except Exception as e:
            error_msg = f"[모의계좌] 모의단타매매 실행 중 오류: {str(e)[:100]}"
            print(f"\n[ERROR] {error_msg}")
            
            # 오류 알림
            try:
                from support.telegram_notifier import get_telegram_notifier
                telegram = get_telegram_notifier()
                if telegram:
                    await telegram.send_message(error_msg)
            except:
                pass
    
    async def _get_and_display_account_info(self, account_type: str) -> Dict:
        """계좌 정보 조회 및 표시"""
        try:
            from support.api_connector import KISAPIConnector
            from support.telegram_notifier import get_telegram_notifier
            
            # API 연결
            is_mock = (account_type == "MOCK")
            api = KISAPIConnector(is_mock=is_mock)
            account_display = "모의계좌" if is_mock else "실계좌"
            
            print(f"\n[{account_display}] 계좌 정보를 조회 중...")
            
            # 텔레그램 알림
            telegram = get_telegram_notifier()
            if telegram:
                await telegram.send_message(f"[{account_display}] 계좌 정보 조회 시작")
            
            # 계좌 잔고 조회
            account_balance = await api.get_account_balance(force_refresh=True)
            
            if not account_balance:
                print(f"\n[ERROR] 계좌 정보 조회 실패")
                return None
            
            # 예수금 정보 검증 및 추출
            if 'dnca_tot_amt' not in account_balance:
                raise Exception("API 응답에 예수금 정보(dnca_tot_amt)가 없습니다")
            if 'ord_psbl_cash' not in account_balance:
                raise Exception("API 응답에 주문가능금액 정보(ord_psbl_cash)가 없습니다")
                
            cash_balance = float(account_balance['dnca_tot_amt'])
            available_cash = float(account_balance['ord_psbl_cash'])
            
            # 보유종목 정보
            holdings = account_balance.get('output1', [])
            holdings_with_qty = [h for h in holdings if int(h.get('hldg_qty', '0')) > 0]
            total_holdings = len(holdings_with_qty)
            
            # 계좌 정보 출력
            print(f"\n{'='*50}")
            print(f"[{account_display}] 계좌 정보")
            print(f"{'='*50}")
            print(f"예수금 잔고: {cash_balance:,.0f}원")
            print(f"주문가능금액: {available_cash:,.0f}원")
            print(f"총 보유종목수: {total_holdings}개")
            
            if holdings_with_qty:
                print(f"\n[보유종목 상세]")
                print(f"{'종목명':<20} {'코드':<8} {'보유수량':<10} {'현재가':<12}")
                print("-" * 60)
                
                for holding in holdings_with_qty[:10]:  # 상위 10개만 표시
                    stock_name = holding.get('prdt_name', '')
                    stock_code = holding.get('pdno', '')
                    if 'hldg_qty' not in holding:
                        raise Exception(f"보유종목({stock_name})에 보유수량 정보가 없습니다")
                    if 'prpr' not in holding:
                        raise Exception(f"보유종목({stock_name})에 현재가 정보가 없습니다")
                        
                    quantity = int(holding['hldg_qty'])
                    current_price = float(holding['prpr'])
                    
                    print(f"{stock_name:<20} {stock_code:<8} {quantity:,}주{'':<4} {current_price:,.0f}원")
                
                if len(holdings_with_qty) > 10:
                    print(f"... 외 {len(holdings_with_qty) - 10}개 종목")
            else:
                print("보유종목 없음")
            
            print("=" * 50)
            
            # 텔레그램 알림
            if telegram:
                msg = (f"[{account_display}] 계좌 정보 조회 완료\n"
                      f"예수금: {cash_balance:,.0f}원\n"
                      f"주문가능금액: {available_cash:,.0f}원\n"
                      f"보유종목수: {total_holdings}개")
                await telegram.send_message(msg)
            
            return {
                'account_type': account_type,
                'cash_balance': cash_balance,
                'available_cash': available_cash,
                'holdings': holdings_with_qty,
                'total_holdings': total_holdings,
                'api_instance': api
            }
            
        except Exception as e:
            error_msg = f"계좌 정보 조회 중 오류: {e}"
            print(f"\n[ERROR] {error_msg}")
            
            try:
                telegram = get_telegram_notifier()
                if telegram:
                    await telegram.send_message(f"[{account_display}] {error_msg}")
            except:
                pass
            
            return None
    
    def _safe_input(self, prompt: str) -> str:
        """안전한 입력 받기 (KeyboardInterrupt 처리)"""
        try:
            return input(prompt).strip()
        except KeyboardInterrupt:
            print("\n\n[INTERRUPT] 사용자에 의해 중단되었습니다.")
            raise
        except EOFError:
            print("\n입력 스트림이 종료되었습니다.")
            return "0"  # 종료 선택으로 처리
    
    def update_selected_algorithm(self, selected_algorithm: dict):
        """선택된 알고리즘 정보 업데이트"""
        self.selected_algorithm = selected_algorithm


def get_menu_manager(selected_algorithm: dict) -> MenuManager:
    """MenuManager 인스턴스를 생성하여 반환"""
    return MenuManager(selected_algorithm)