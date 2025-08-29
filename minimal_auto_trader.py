"""
최소화된 자동매매 엔진 - 순수 매매 로직만
"""

import asyncio
import logging
from datetime import datetime, time as datetime_time
from typing import Dict, List

from support.api_connector import KISAPIConnector
from support.step_display_utils import print_step_start, print_step_end, step_delay, print_algorithm_start, print_algorithm_end
from support.previous_day_balance_handler import PreviousDayBalanceHandler, TradingStrategy
# 필요한 모듈만 import

logger = logging.getLogger(__name__)

class MinimalAutoTrader:
    def __init__(self, account_type: str = "MOCK", algorithm=None, skip_market_hours: bool = False):
        self.account_type = account_type
        self.algorithm = algorithm
        self.skip_market_hours = skip_market_hours
        
        # 기본 상태
        self.is_running = False
        self.stop_requested = False
        
        # API 지연 초기화 (블로킹 방지)
        self.api = None
        self._api_initialized = False
        
        # 파일 기반 중단 핸들러 사용
        from pathlib import Path
        self.stop_signal_file = Path("STOP_TRADING.signal")
        
        # keyboard_handler 추가 (STOP 신호 파일 정리용)
        from support.keyboard_handler import get_keyboard_handler
        self.keyboard_handler = get_keyboard_handler()
        
        # 포지션 관리
        self.positions: Dict[str, Dict] = {}
        
        # 계좌 정보 캐시
        self.account_info = None
        self.previous_holdings = {}
        
        # 사용자 지정종목 관리자
        self.user_stock_manager = None
        
        # 종목 리스트 (프로그램 시작시 수집된 데이터에서 로드)
        self.theme_stocks = []
        self.load_cached_stocks()
        
        # 텔레그램 알림 시스템
        self.telegram_notifier = None
        
        # 계좌 유형 표시 문자열
        self.account_display = "실제계좌" if account_type == "REAL" else "모의투자계좌"
        
    async def run(self):
        """완전한 자동매매 워크플로우 실행"""
        print_step_start("자동매매 시스템")
        logger.info(f"[{self.account_display}] 자동매매 시작")
        self.is_running = True
        self.stop_requested = False
        
        # API 초기화 (지연 로딩)
        if not self._api_initialized:
            await self.initialize_api()
        
        # 텔레그램 알림 시스템 초기화
        await self.initialize_telegram()
        
        # 1. 시작 메시지 전송
        await self.send_telegram_message(
            f"[{self.account_display}] 자동매매 시작\n"
            f"알고리즘: {getattr(self.algorithm, 'get_name', lambda: '기본 알고리즘')()}\n"
            f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # 2. 초기 계좌 정보 조회 및 메모리 저장
        await self.initial_account_inquiry()
        await step_delay(3)
        
        # 3. 전날 보유 종목 확인
        print_step_start("전날잔고처리")
        await self.check_previous_day_holdings()
        print_step_end("전날잔고처리")
        await step_delay(3)
        
        # 1) 시작 시 모든 신호 파일 정리 (잔여 신호 파일로 인한 즉시 종료 방지)
        self.keyboard_handler.clear_stop_signal_files()
        
        # 2) ESC 감지 설정 적용 (trading_config.json 기반)
        from support.trading_config_manager import TradingConfigManager
        try:
            cfg = TradingConfigManager()
            use_esc = cfg.get("enable_esc_stop", False)
            if not use_esc:
                self.keyboard_handler.disable_esc_listening = True
                logger.info("[CONFIG] ESC detection disabled - using file-based signals only")
            else:
                logger.info("[CONFIG] ESC detection enabled")
        except Exception as e:
            logger.warning(f"[CONFIG] Failed to load ESC config, using default: {e}")
        
        # 기존 개별 파일 처리 (호환성 유지)
        if self.stop_signal_file.exists():
            self.stop_signal_file.unlink()
            logger.info(f"[CLEANUP] Removed individual stop signal file: {self.stop_signal_file}")
        
        # keyboard_handler 중단 콜백 설정
        self.keyboard_handler.set_stop_callback(self.request_stop)
        self.keyboard_handler.set_force_exit_callback(self.request_force_exit)
        
        cycle_count = 0
        try:
            while self.is_running and not self.stop_requested:
                now = datetime.now()
                current_time = now.strftime('%H:%M:%S')
                logger.info(f"[{self.account_display}] [{current_time}] 매매 사이클 {cycle_count + 1} 시작")
                
                # 중단 신호 확인 (파일 기반)
                if self.stop_signal_file.exists():
                    # 파일 내용을 확인하여 안전 종료 vs 강제 종료 구분
                    try:
                        with open(self.stop_signal_file, 'r', encoding='utf-8') as f:
                            signal_content = f.read().strip().upper()
                    except:
                        signal_content = "SAFE_STOP"  # 기본값
                    
                    if signal_content == "FORCE_EXIT":
                        termination_reason = "FILE_SIGNAL_FORCE_EXIT"
                        logger.info(f"[{current_time}] 파일 강제 종료 신호 감지 - 즉시 종료")
                        await self.send_telegram_message(
                            f"[{self.account_display}] 파일 강제 종료 신호 감지\n"
                            f"즉시 종료합니다."
                        )
                    else:
                        termination_reason = "FILE_SIGNAL_SAFE_STOP"
                        logger.info(f"[{current_time}] 파일 안전 종료 신호 감지 - 자동매매 종료")
                        await self.send_telegram_message(
                            f"[{self.account_display}] 파일 안전 종료 신호 감지\n"
                            f"자동매매를 안전하게 종료합니다."
                        )
                    
                    # 종료 사유 로깅
                    if cfg.is_termination_reason_logging_enabled():
                        logger.info(f"[TERMINATION] 사유: {termination_reason}")
                    
                    self.stop_signal_file.unlink()
                    break
                
                # 장 마감 시간 체크 및 마감 임박 제어 (TradingConfigManager 기준)
                from support.trading_config_manager import TradingConfigManager
                from support.utils_time_gate import TimeGateManager
                
                cfg = TradingConfigManager()
                market_close = cfg.get_market_close_time()
                guard_minutes = cfg.get_close_guard_minutes()
                now_time = now.time()
                
                # TimeGateManager 초기화
                if not hasattr(self, '_time_gate_manager'):
                    self._time_gate_manager = TimeGateManager(market_close, guard_minutes)
                
                # 거래 상태 확인
                trading_status = self._time_gate_manager.check_trading_status(now_time)
                
                # 마감 임박 경고 처리
                if (trading_status["is_close_guard_window"] and 
                    cfg.is_countdown_warning_enabled() and 
                    self._time_gate_manager.should_send_warning(now_time)):
                    
                    remaining_time = trading_status["remaining_time"]
                    logger.warning(f"[CLOSE_GUARD] 마감 임박 - {remaining_time['formatted_string']} 남음")
                    
                    await self.send_telegram_message(
                        f"[{self.account_display}] 장 마감 임박 알림\n\n"
                        f"현재 시각: {current_time}\n"
                        f"설정 마감: {market_close.strftime('%H:%M')}\n"
                        f"남은 시간: {remaining_time['formatted_string']}\n"
                        f"신규 진입 금지 - 포지션 관리 모드 전환({guard_minutes}분 전)"
                    )
                    
                    # 거래 정책 업데이트
                    if cfg.is_new_entry_block_before_close_enabled():
                        if not hasattr(self, 'trading_policy'):
                            self.trading_policy = {}
                        self.trading_policy.update(trading_status["trading_policy"])
                        logger.info(f"[CLOSE_GUARD] 신규 진입 차단 활성화")
                
                # 장 마감 시간 도달 시 종료
                if trading_status["remaining_time"]["is_past_close"]:
                    termination_reason = "MARKET_CLOSE_TIME_REACHED"
                    if cfg.is_termination_reason_logging_enabled():
                        logger.info(f"[TERMINATION] 사유: {termination_reason}")
                    
                    logger.info(f"[{current_time}] 장 마감({market_close.strftime('%H:%M')}) 도달 — 자동매매 종료")
                    await self.send_telegram_message(
                        f"[{self.account_display}] 장 마감으로 인한 종료\n\n"
                        f"종료 시각: {current_time}\n"
                        f"설정 마감: {market_close.strftime('%H:%M')}\n"
                        f"종료 사유: {termination_reason}\n"
                        f"안전하게 종료되었습니다."
                    )
                    
                    logger.info(f"[TERMINATION] {termination_reason} - 안전한 종료 프로세스 시작")
                    self.stop_requested = True
                    self.is_running = False
                    break
                    
                # 기존 하드코딩된 종장 시간 체크 제거 (위의 TradingConfigManager 기반 체크로 통일)
                
                # 매매 사이클 실행
                try:
                    await self.send_telegram_message(
                        f"[{self.account_display}] 매매 사이클 {cycle_count + 1} 시작"
                    )
                    
                    trading_result = await self.complete_trading_cycle(cycle_count)
                    
                    # 결과 전송
                    result_message = self.format_trading_result(trading_result, cycle_count + 1)
                    await self.send_telegram_message(result_message)
                    
                    logger.info(f"[{current_time}] 매매 사이클 {cycle_count + 1} 완료")
                    
                    # TODO: 테스트 완료 후 원래 간격으로 복원 (3분 = 180초)
                    # 테스트용 30초 대기 (중단 신호 반응성 향상을 위해 5초씩 분할)
                    logger.info(f"[{current_time}] 30초 후 다음 매매 사이클 (테스트용, 원래: 180초)")
                    
                    # 중단 신호에 대한 반응성을 높이기 위해 5초씩 6번 대기
                    for sleep_cycle in range(6):  # 6 x 5초 = 30초 (원래: 18 x 10초 = 180초)
                        # 사이클 도중 중단 신호 확인
                        if self.stop_signal_file.exists():
                            try:
                                with open(self.stop_signal_file, 'r', encoding='utf-8') as f:
                                    signal_content = f.read().strip().upper()
                            except:
                                signal_content = "SAFE_STOP"
                            
                            termination_reason = "FILE_SIGNAL_FORCE_EXIT" if signal_content == "FORCE_EXIT" else "FILE_SIGNAL_SAFE_STOP"
                            logger.info(f"[대기중 중단] 파일 중단 신호 감지")
                            
                            # 종료 사유 로깅
                            if cfg.is_termination_reason_logging_enabled():
                                logger.info(f"[TERMINATION] 사유: {termination_reason}")
                            break
                        
                        if not self.is_running or self.stop_requested:
                            logger.info(f"[대기중 중단] 상태 변경 감지")
                            break
                            
                        await asyncio.sleep(5)   # 5초 대기 (테스트용, 원래: 10초)
                    
                except Exception as e:
                    logger.error(f"매매 사이클 오류: {e}")
                    # 중대 오류 알림 전송
                    await self.send_critical_error_alert(
                        error_type="매매 사이클 실행 오류",
                        error_message=str(e),
                        location=f"매매 사이클 {cycle_count + 1}"
                    )
                    await self.send_telegram_message(
                        f"[{self.account_display}] 매매 사이클 오류\n"
                        f"오류: {str(e)[:100]}\n"
                        f"30초 후 재시도합니다."
                    )
                    # 30초 대기 (중단 신호 확인 포함)
                    for error_sleep in range(6):  # 6 x 5초 = 30초
                        if self.stop_signal_file.exists():
                            try:
                                with open(self.stop_signal_file, 'r', encoding='utf-8') as f:
                                    signal_content = f.read().strip().upper()
                            except:
                                signal_content = "SAFE_STOP"
                            
                            termination_reason = "FILE_SIGNAL_FORCE_EXIT" if signal_content == "FORCE_EXIT" else "FILE_SIGNAL_SAFE_STOP"
                            logger.info(f"[오류 대기중 중단] 파일 중단 신호 감지")
                            
                            # 종료 사유 로깅
                            try:
                                cfg = TradingConfigManager()
                                if cfg.is_termination_reason_logging_enabled():
                                    logger.info(f"[TERMINATION] 사유: {termination_reason}")
                            except Exception:
                                pass  # 설정 로드 실패 시 무시
                            break
                        elif not self.is_running or self.stop_requested:
                            logger.info(f"[오류 대기중 중단] 상태 변경 감지")
                            break
                        await asyncio.sleep(5)
                
                cycle_count += 1
                
        except KeyboardInterrupt:
            termination_reason = "USER_KEYBOARD_INTERRUPT"
            logger.info("사용자에 의한 중단 요청 (Ctrl+C)")
            
            # 종료 사유 로깅
            cfg = TradingConfigManager()
            if cfg.is_termination_reason_logging_enabled():
                logger.info(f"[TERMINATION] 사유: {termination_reason}")
            
            # 중단 상태 설정
            self.is_running = False
            self.stop_requested = True
            
            # 중단 메시지 전송 (비동기 전송 실패 시 무시)
            try:
                await asyncio.wait_for(
                    self.send_telegram_message(
                        f"[{self.account_display}] 사용자에 의한 중단 요청 (Ctrl+C)\n"
                        f"종료 사유: {termination_reason}\n"
                        f"자동매매를 안전하게 종료합니다."
                    ),
                    timeout=2.0  # 2초 타임아웃
                )
            except (asyncio.TimeoutError, Exception) as telegram_error:
                logger.warning(f"중단 메시지 전송 실패 무시: {telegram_error}")
        
        except Exception as unexpected_error:
            termination_reason = "SYSTEM_UNEXPECTED_ERROR"
            logger.error(f"예상치 못한 오류: {unexpected_error}")
            
            # 종료 사유 로깅
            try:
                cfg = TradingConfigManager()
                if cfg.is_termination_reason_logging_enabled():
                    logger.info(f"[TERMINATION] 사유: {termination_reason}")
            except Exception:
                pass  # 설정 로드 실패 시 무시
            
            # 예상치 못한 오류 시도 중단 신호 설정
            self.is_running = False
            self.stop_requested = True
            
            try:
                await asyncio.wait_for(
                    self.send_telegram_message(
                        f"[{self.account_display}] 시스템 오류 발생\n"
                        f"종료 사유: {termination_reason}\n"
                        f"오류: {str(unexpected_error)[:100]}\n"
                        f"자동매매를 종료합니다."
                    ),
                    timeout=2.0
                )
            except Exception:
                pass  # 오류 전송 실패 무시
        
        finally:
            # 모든 상황에서 정리 작업 수행
            self.is_running = False
            self.stop_requested = True
            
            try:
                await asyncio.wait_for(
                    self.finalize_trading(),
                    timeout=5.0  # 정리 작업 최대 5초
                )
            except (asyncio.TimeoutError, Exception) as finalize_error:
                logger.warning(f"정리 작업 시간 초과 또는 오류: {finalize_error}")
            
            logger.info(f"[{self.account_display}] 자동매매 종료 (안전 정리 완료)")

    async def complete_trading_cycle(self, cycle_number: int) -> Dict:
        """완전한 매매 사이클 - 실제 워크플로우 구현"""
        try:
            current_time = datetime.now().strftime('%H:%M:%S')
            logger.info(f"[{self.account_display}] [{current_time}] 매매 사이클 시작")
            
            # 1. 계좌 정보 조회 및 메모리 갱신
            await self.update_account_info()
            
            # 2. 전날 보유 종목 잔고 처리
            await self.process_previous_holdings()
            
            # 3. 자동매매 로직 시작
            print_algorithm_start("자동매매")
            auto_trade_results = await self.execute_auto_trading()
            print_algorithm_end("자동매매")
            await step_delay(3)
            
            # 4. 사용자 지정종목 매수/매도 조건 로딩 및 처리
            user_trade_results = await self.process_user_designated_stocks()
            
            # 5. 결과 종합
            trading_result = {
                'cycle_number': cycle_number + 1,
                'account_type': self.account_type,
                'timestamp': current_time,
                'auto_trade': auto_trade_results,
                'user_trade': user_trade_results,
                'account_balance': self.account_info.get('cash_balance', 0) if self.account_info else 0,
                'total_positions': len(self.positions)
            }
            
            return trading_result
                
        except Exception as e:
            logger.error(f"매매 사이클 오류: {e}")
            raise

    async def initialize_api(self):
        """API 초기화"""
        try:
            if not self.api:
                logger.info(f"API 연결 초기화 중... ({self.account_type})")
                is_mock = (self.account_type == "MOCK")
                from support.api_connector import KISAPIConnector
                self.api = KISAPIConnector(is_mock=is_mock)
                
                # 텔레그램 연동 확인
                if hasattr(self.api, 'telegram'):
                    logger.info("텔레그램 연동 확인됨")
                else:
                    logger.info("텔레그램 연동 없음")
                    
            self._api_initialized = True
            logger.info("API 초기화 완료")
        except Exception as e:
            logger.error(f"API 초기화 오류: {e}")
            # 중대 오류 텔레그램 알림
            try:
                await self.send_critical_error_alert(
                    error_type="API 초기화 실패", 
                    error_message=str(e),
                    location="initialize_api()"
                )
            except:
                pass  # 텔레그램 알림 실패해도 계속 진행
            raise

    def load_cached_stocks(self):
        """캐시된 종목 데이터 로드"""
        try:
            from stock_data_collector import stock_data_collector
            self.theme_stocks = stock_data_collector.get_theme_stocks()
            logger.info(f"종목 데이터 로드 완료: {len(self.theme_stocks)}개")
        except Exception as e:
            logger.warning(f"종목 데이터 로드 실패, 빈 리스트 사용: {e}")
            self.theme_stocks = []

    async def initialize_telegram(self):
        """텔레그램 알림 시스템 초기화"""
        try:
            from support.telegram_notifier import get_telegram_notifier
            self.telegram_notifier = get_telegram_notifier()
            logger.info("텔레그램 알림 시스템 초기화 완료")
        except Exception as e:
            logger.warning(f"텔레그램 초기화 실패: {e}")
            self.telegram_notifier = None
    
    async def send_telegram_message(self, message: str):
        """텔레그램 메시지 전송 (계정 유형 포함)"""
        try:
            if self.telegram_notifier:
                await self.telegram_notifier.send_message(message)
        except Exception as e:
            logger.warning(f"텔레그램 메시지 전송 실패: {e}")
    
    async def send_critical_error_alert(self, error_type: str, error_message: str, location: str = ""):
        """중대한 오류 시 텔레그램 알림 전송"""
        try:
            if self.telegram_notifier:
                alert_message = f"""
<b>[{self.account_display}] 시스템 중대 오류</b>

<b>오류 유형:</b> {error_type}
<b>발생 위치:</b> {location or 'tideWise System'}
<b>오류 내용:</b> {error_message}
<b>발생 시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[긴급] 즉시 시스템을 확인해주세요.
                """.strip()
                await self.telegram_notifier.send_error_alert(error_type, error_message)
                logger.info(f"중대 오류 텔레그램 알림 전송 완료: {error_type}")
        except Exception as e:
            logger.error(f"중대 오류 텔레그램 알림 전송 실패: {e}")
    
    async def initial_account_inquiry(self):
        """초기 계좌 정보 조회 및 메모리 저장"""
        try:
            # 계좌 조회 중 메시지만 표시
            from support.account_display_utils import show_account_inquiry_message, display_account_info
            show_account_inquiry_message()
            
            logger.info(f"[{self.account_display}] 초기 계좌 정보 조회 시작")
            
            # 계좌 잔고 조회
            account_balance = await self.api.get_account_balance(force_refresh=True)
            
            if account_balance:
                self.account_info = {
                    'cash_balance': account_balance.get('output2', [{}])[0].get('dnca_tot_amt', '0'),
                    'holdings': account_balance.get('output1', []),
                    'last_updated': datetime.now()
                }
                
                cash_balance = float(self.account_info['cash_balance'])
                holdings = self.account_info['holdings']
                holdings_count = len([h for h in holdings if int(h.get('hldg_qty', '0')) > 0])
                
                # 표준화된 계좌 정보 표시
                account_data = {
                    'account_number': getattr(self.api, 'account_number', self.api.config.get("CANO", 'Unknown')),
                    'total_cash': cash_balance,
                    'buyable_cash': cash_balance,  # 미니멀 버전에서는 동일하게 처리
                    'profit_rate': 0.0,  # 미니멀 버전에서는 수익률 계산 없음
                    'holdings': [h for h in holdings if int(h.get('hldg_qty', '0')) > 0]  # 보유수량이 있는 종목만
                }
                
                display_account_info(account_data, "MOCK")
                
                await self.send_telegram_message(
                    f"[{self.account_display}] 계좌 정보 조회 완료\\n"
                    f"예수금: {cash_balance:,.0f}원\\n"
                    f"보유종목: {holdings_count}개"
                )
                
                logger.info(f"계좌 정보 조회 완료 - 예수금: {cash_balance:,.0f}원, 보유종목: {holdings_count}개")
            else:
                logger.warning("계좌 정보 조회 실패")
                await self.send_telegram_message(
                    f"[{self.account_display}] 계좌 정보 조회 실패\\n"
                    f"기본값으로 진행합니다."
                )
                
        except Exception as e:
            logger.error(f"초기 계좌 조회 오류: {e}")
            await self.send_telegram_message(
                f"[{self.account_display}] 계좌 조회 오류\\n"
                f"오류: {str(e)[:100]}"
            )
    
    async def check_previous_day_holdings(self):
        """통합된 전날 보유 종목 잔고 처리"""
        try:
            logger.info(f"[{self.account_display}] 전날 보유 종목 잔고 처리 시작")
            
            # 통합 전날잔고 처리기 생성 (MINIMAL 전략 사용)
            balance_handler = PreviousDayBalanceHandler(
                self.api, 
                self.account_type, 
                TradingStrategy.MINIMAL
            )
            
            # 전날잔고 정리 실행
            cleanup_result = await balance_handler.execute_previous_day_balance_cleanup()
            
            # 결과 처리
            if cleanup_result.get('success'):
                sold_count = cleanup_result.get('sold_count', 0)
                kept_count = cleanup_result.get('kept_count', 0)
                
                if sold_count > 0 or kept_count > 0:
                    await self.send_telegram_message(
                        f"[{self.account_display}] 전날 잔고 처리 완료\\n"
                        f"매도: {sold_count}개, 보유: {kept_count}개\\n"
                        f"전략: MINIMAL"
                    )
                else:
                    await self.send_telegram_message(
                        f"[{self.account_display}] 전날 보유종목 없음\\n"
                        f"바로 자동매매 로직으로 진행합니다."
                    )
                
                logger.info(f"전날 잔고 처리 완료: {cleanup_result.get('message')}")
            else:
                logger.warning(f"전날 잔고 처리 실패: {cleanup_result.get('message')}")
                await self.send_telegram_message(
                    f"[{self.account_display}] 전날 잔고 처리 실패\\n"
                    f"오류: {cleanup_result.get('message', '알 수 없음')}"
                )
                
        except Exception as e:
            logger.error(f"통합 전날 잔고 처리 오류: {e}")
            await self.send_telegram_message(
                f"[{self.account_display}] 전날 잔고 처리 오류\\n"
                f"오류: {str(e)[:100]}"
            )
    
    async def update_account_info(self):
        """계좌 정보 갱신 (테스트용 30초마다 실행, 원래: 3분마다)"""
        try:
            logger.info(f"[{self.account_display}] 계좌 정보 갱신")
            
            # 계좌 잔고 조회
            account_balance = await self.api.get_account_balance(force_refresh=True)
            
            if account_balance:
                self.account_info = {
                    'cash_balance': account_balance.get('output2', [{}])[0].get('dnca_tot_amt', '0'),
                    'holdings': account_balance.get('output1', []),
                    'last_updated': datetime.now()
                }
                
                logger.info("계좌 정보 갱신 완료")
            else:
                logger.warning("계좌 정보 갱신 실패")
                
        except Exception as e:
            logger.error(f"계좌 정보 갱신 오류: {e}")
    
    async def process_previous_holdings(self):
        """레거시 메서드 - check_previous_day_holdings에서 통합 처리"""
        # 이제 check_previous_day_holdings에서 통합 PreviousDayBalanceHandler로 처리하므로
        # 이 메서드는 더 이상 필요하지 않음
        logger.info("전날 잔고 처리는 check_previous_day_holdings에서 통합 처리됨")
        pass
    
    async def execute_auto_trading(self):
        """자동매매 로직 실행"""
        try:
            logger.info(f"[{self.account_display}] 자동매매 로직 시작")
            
            # 현재 포지션 수 확인
            current_positions = len(self.positions)
            max_positions = 3
            
            buy_results = []
            sell_results = []
            
            # 매수 로직 (포지션이 최대 미만일 때)
            if current_positions < max_positions:
                # TODO: 실제 매수 로직 구현
                logger.info(f"매수 기회 탐색 중... (현재 {current_positions}/{max_positions})")
                pass
            
            # 매도 로직 
            # TODO: 실제 매도 로직 구현
            logger.info("매도 조건 검사 중...")
            
            result = {
                'buy_count': len(buy_results),
                'sell_count': len(sell_results),
                'buy_results': buy_results,
                'sell_results': sell_results
            }
            
            return result
                
        except Exception as e:
            logger.error(f"자동매매 실행 오류: {e}")
            return {'buy_count': 0, 'sell_count': 0, 'buy_results': [], 'sell_results': []}
    
    async def process_user_designated_stocks(self):
        """사용자 지정종목 매수/매도 조건 로딩 및 처리"""
        try:
            logger.info(f"[{self.account_display}] 사용자 지정종목 처리 시작")
            
            # 사용자 지정종목 관리자 초기화
            if not self.user_stock_manager:
                from support.user_designated_stocks import get_user_designated_stock_manager
                self.user_stock_manager = get_user_designated_stock_manager(self.api)
            
            # 사용자 지정종목 조건 로딩
            user_stocks = self.user_stock_manager.get_all_designated_stocks()
            
            if not user_stocks:
                logger.info("사용자 지정종목이 없습니다")
                return {'processed_count': 0, 'results': []}
            
            # 사용자 지정종목 매수/매도 처리
            results = []
            for stock_code, stock_info in user_stocks.items():
                # TODO: 실제 사용자 지정종목 매매 로직 구현
                logger.info(f"사용자 지정종목 처리: {stock_info.name}({stock_code})")
            
            result = {
                'processed_count': len(user_stocks),
                'results': results
            }
            
            return result
                
        except Exception as e:
            logger.error(f"사용자 지정종목 처리 오류: {e}")
            return {'processed_count': 0, 'results': []}
    
    async def check_sell_conditions(self, stock_code: str, holding_info: Dict) -> bool:
        """매도 조건 검사"""
        try:
            # TODO: 실제 매도 조건 로직 구현
            # 예시: 손절, 익절, 시간 기반 매도 등
            return False  # 임시로 매도하지 않음
        except Exception as e:
            logger.error(f"매도 조건 검사 오류 {stock_code}: {e}")
            return False
    
    async def execute_market_sell(self, stock_code: str, holding_info: Dict) -> bool:
        """시중가 매도 실행"""
        try:
            # TODO: 실제 매도 주문 API 호출 구현
            logger.info(f"시중가 매도 실행: {holding_info['name']} ({stock_code})")
            return True  # 임시 성공 반환
        except Exception as e:
            logger.error(f"시중가 매도 실행 오류 {stock_code}: {e}")
            return False
    
    def format_trading_result(self, trading_result: Dict, cycle_number: int) -> str:
        """매매 결과 메시지 포맷팅"""
        try:
            auto_trade = trading_result.get('auto_trade', {})
            user_trade = trading_result.get('user_trade', {})
            
            message = f"[{self.account_display}] 매매 사이클 {cycle_number} 완료\\n"
            message += f"시간: {trading_result.get('timestamp', 'Unknown')}\\n"
            message += f"\\n=== 자동매매 결과 ===\\n"
            message += f"매수: {auto_trade.get('buy_count', 0)}건\\n"
            message += f"매도: {auto_trade.get('sell_count', 0)}건\\n"
            message += f"\\n=== 사용자 지정종목 ===\\n"
            message += f"처리: {user_trade.get('processed_count', 0)}건\\n"
            message += f"\\n총 포지션: {trading_result.get('total_positions', 0)}개"
            
            return message
        except Exception as e:
            return f"[{self.account_display}] 매매 사이클 {cycle_number} 완료 (결과 포맷 오류: {str(e)[:50]})"
    
    async def finalize_trading(self):
        """매매 종료 시 정리 작업"""
        try:
            logger.info(f"[{self.account_display}] 자동매매 종료 정리 시작")
            
            # 최종 계좌 상태 조회
            if self.api:
                final_balance = await self.api.get_account_balance(force_refresh=True)
                if final_balance:
                    cash_balance = final_balance.get('output2', [{}])[0].get('dnca_tot_amt', '0')
                    holdings_count = len([h for h in final_balance.get('output1', []) if int(h.get('hldg_qty', '0')) > 0])
                    
                    await self.send_telegram_message(
                        f"[{self.account_display}] 자동매매 종료\\n"
                        f"종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n"
                        f"최종 예수금: {float(cash_balance):,.0f}원\\n"
                        f"최종 보유종목: {holdings_count}개\\n"
                        f"\\n자동매매가 안전하게 종료되었습니다."
                    )
            
            logger.info(f"[{self.account_display}] 자동매매 정리 완료")
            
        except Exception as e:
            logger.error(f"매매 종료 정리 오류: {e}")
            await self.send_telegram_message(
                f"[{self.account_display}] 자동매매 종료\\n"
                f"정리 작업 중 오류 발생: {str(e)[:100]}"
            )
    
    def request_stop(self):
        """안전한 중단 요청 (keyboard_handler 콜백용)"""
        logger.info(f"[{self.account_display}] 안전한 자동매매 중단 요청")
        self.stop_requested = True
        self.is_running = False
    
    def request_force_exit(self):
        """강제 종료 요청 (keyboard_handler 콜백용)"""
        logger.info(f"[{self.account_display}] 강제 종료 요청")
        self.stop_requested = True
        self.is_running = False
        # 강제 종료의 경우 추가 정리 없이 즉시 종료
        import sys
        sys.exit(0)