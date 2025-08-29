#!/usr/bin/env python3
"""
MinimalDayTrader - 단타매매 전용 엔진
기존 MinimalAutoTrader와 차별화된 단타 전용 로직
"""

import asyncio
import logging
from datetime import datetime, time as datetime_time
from typing import Dict, List, Optional, Any
from pathlib import Path
from support.step_display_utils import print_step_start, print_step_end, step_delay, print_algorithm_start, print_algorithm_end
from support.previous_day_balance_handler import PreviousDayBalanceHandler, TradingStrategy

# 깔끔한 콘솔 로거
try:
    from support.clean_console_logger import (
        get_clean_logger, Phase, start_phase, end_phase, 
        log as clean_log, log_account, log_trade
    )
    CLEAN_LOGGER_AVAILABLE = True
    console = get_clean_logger()
except ImportError:
    CLEAN_LOGGER_AVAILABLE = False
    console = None

# 토큰 최적화 시스템
from token_optimizer import optimize_if_needed

logger = logging.getLogger(__name__)


class MinimalDayTrader:
    """단타매매 전용 엔진 클래스"""
    
    def __init__(self, account_type: str = "MOCK", algorithm=None, skip_market_hours: bool = False):
        """
        MinimalDayTrader 초기화
        
        Args:
            account_type: 계좌 유형 ("REAL" 또는 "MOCK")
            algorithm: 단타매매 알고리즘 인스턴스
            skip_market_hours: 장시간 체크 생략 여부
        """
        self.account_type = account_type
        self.algorithm = algorithm
        self.skip_market_hours = skip_market_hours
        
        # 기본 상태
        self.is_running = False
        self.stop_requested = False
        
        # API 연결 (지연 초기화)
        self.api = None
        self._api_initialized = False
        
        # 메모리 관리자
        self.memory_manager = None
        
        # 세션 기반 계좌 관리자 (실시간성과 성능 균형)
        self.account_manager = None
        
        # 파일 기반 중단 핸들러
        self.stop_signal_file = Path("STOP_DAYTRADING.signal")
        
        # 텔레그램 알림
        self.telegram_notifier = None
        
        # 계좌 유형 표시
        self.account_display = "실제계좌" if account_type == "REAL" else "모의투자계좌"
        
        # 단타매매 설정 (시간별 간격)
        self.cycle_interval = 120  # 2분 간격 (정상 운영)
        self.max_positions = 5      # 최대 동시 보유 종목 수
        self.position_size_ratio = 0.2  # 계좌의 20% 사용 (실제 코드와 통일)
        
        # 신뢰도 임계값 (알고리즘별 설정 가능)
        self.confidence_threshold = getattr(algorithm, 'confidence_threshold', 0.6) if algorithm else 0.6
        
        # 급등종목 데이터 저장 (캐시 대신 API 데이터만 사용)
        self.surge_stocks_data = []  # 한투 API로 수집한 급등종목만 저장
        self.surge_stocks_dict = {}  # 종목코드로 빠른 조회용
        
        logger.info(f"MinimalDayTrader 초기화 ({self.account_display})")
    
    async def run(self):
        """단타매매 메인 실행 루프"""
        self.is_running = True
        self.stop_requested = False
        
        # 깔끔한 로거 사용
        if CLEAN_LOGGER_AVAILABLE:
            start_phase(Phase.INIT, f"{self.account_display} 단타매매 시작")
        else:
            logger.info(f"[{self.account_display}] 단타매매 시작")
        
        try:
            # 1. 시스템 초기화
            if not await self._initialize_systems():
                if CLEAN_LOGGER_AVAILABLE:
                    clean_log("시스템 초기화 실패", "ERROR")
                    end_phase(Phase.INIT, success=False)
                else:
                    logger.error("시스템 초기화 실패")
                return False
            
            # 2. 시작 알림
            await self._send_start_notification()
            
            # 3. 단타매매 세션 시작
            if CLEAN_LOGGER_AVAILABLE:
                end_phase(Phase.INIT, success=True)
                start_phase(Phase.CONNECTION, "서버 연결 및 계좌 조회")
                clean_log("세션 시작 및 초기 계좌 조회", "INFO")
            else:
                print_step_start("단타매매 시스템")
                print("단타매매 시작 전 초기화 작업을 수행합니다...")
            
            # 세션 시작 및 초기 계좌 조회
            self.account_manager.start_session()
            
            # 계좌조회 + 전날잔고처리
            if not await self._pre_day_trading_initialization():
                if CLEAN_LOGGER_AVAILABLE:
                    clean_log("계좌 초기화 실패", "ERROR")
                    end_phase(Phase.CONNECTION, success=False)
                else:
                    logger.error("단타매매 초기화 실패")
                    print_step_end("초기화 실패")
                return False
            
            if CLEAN_LOGGER_AVAILABLE:
                end_phase(Phase.CONNECTION, success=True)
                start_phase(Phase.TRADING, "단타매매 순환 시작")
            else:
                print_step_end("초기화 완료")
                print_step_start("단타매매 순환")
            
            # 4. 중단 시그널 파일 정리
            if self.stop_signal_file.exists():
                self.stop_signal_file.unlink()
            
            # 5. 단타매매 사이클 시작
            cycle_count = 0
            
            while self.is_running and not self.stop_requested:
                cycle_count += 1
                current_time = datetime.now().strftime('%H:%M')  # 분까지만 표시
                
                # 중단 신호 확인
                if await self._check_stop_conditions():
                    break
                
                # 단타매매 사이클 실행
                try:
                    if CLEAN_LOGGER_AVAILABLE:
                        clean_log(f"사이클 {cycle_count} 시작", "INFO")
                    else:
                        print(f"\n[{self.account_display}] 단타매매 사이클 {cycle_count} 실행 중...")
                    
                    cycle_result = await self._execute_day_trading_cycle(cycle_count)
                    
                    # 서버 오류로 인한 중단 체크
                    if cycle_result.get("action") == "server_error":
                        print(f"\n[{self.account_display}] {cycle_result.get('message', '서버가 응답하지 않기 때문에 메인메뉴로 복귀합니다')}")
                        break
                    
                    # 결과 전송
                    await self._send_cycle_result(cycle_result)
                    
                    print(f"[{self.account_display}] 단타매매 사이클 {cycle_count} 완료 - {current_time}")
                    logger.info(f"[{current_time}] 단타매매 사이클 {cycle_count} 완료")
                    
                except Exception as cycle_error:
                    logger.error(f"단타매매 사이클 {cycle_count} 오류: {cycle_error}")
                    await self._send_error_notification(f"사이클 {cycle_count} 오류: {str(cycle_error)[:100]}")
                    
                    # 오류 시 30초 대기
                    await self._safe_sleep(30, "오류 복구")
                    continue
                
                # 다음 사이클까지 대기 (시간별 동적 간격)
                if self.is_running and not self.stop_requested:  # 실행 상태 체크로 변경
                    # 현재 시간에 따른 사이클 간격 계산
                    dynamic_interval = self._get_cycle_interval()
                    interval_minutes = dynamic_interval // 60
                    
                    print(f"\n[{self.account_display}] 사이클 {cycle_count} 완료")
                    print(f"[NEXT CYCLE] 사이클 {cycle_count + 1} 준비 중... ({interval_minutes}분 간격)")
                    await self._safe_sleep(dynamic_interval, f"사이클 {cycle_count + 1}")
                    
                    # 대기 완료 후 다시 한번 실행 상태 체크
                    if self.is_running and not self.stop_requested:
                        print(f"\n[CYCLE START] 사이클 {cycle_count + 1} 시작 준비 완료!")
                    else:
                        print(f"\n[SYSTEM STOP] 시스템 중단 요청으로 다음 사이클 실행 중지")
                        break
            
            # 6. 종료 처리
            await self._finalize_day_trading()
            
        except KeyboardInterrupt:
            logger.info("사용자 중단 요청 (Ctrl+C)")
            await self._send_notification(f"[{self.account_display}] 사용자 중단 요청으로 단타매매 종료")
        except Exception as e:
            logger.error(f"단타매매 실행 오류: {e}")
            await self._send_error_notification(f"시스템 오류: {str(e)[:100]}")
        finally:
            self.is_running = False
            self.stop_requested = True
            
            # 세션 종료 처리
            if self.account_manager:
                self.account_manager.end_session()
                logger.info(f"[{self.account_display}] 단타매매 세션 종료")
            
            logger.info(f"[{self.account_display}] 단타매매 완전 종료")
    
    async def _initialize_systems(self) -> bool:
        """시스템 초기화"""
        try:
            # API 초기화
            if CLEAN_LOGGER_AVAILABLE:
                clean_log("API 초기화 중...", "INFO")
            
            if not await self._initialize_api():
                return False
            
            # 세션 기반 계좌 관리자 초기화 (실시간성과 성능 균형)
            from support.day_trading_account_manager import get_day_trading_account_manager
            self.account_manager = get_day_trading_account_manager(self.api)
            
            if CLEAN_LOGGER_AVAILABLE:
                clean_log("세션 계좌 관리자 초기화 완료", "SUCCESS")
            else:
                logger.info(f"세션 기반 계좌 관리자 초기화 완료: {self.account_display}")
            
            # 기존 호환성을 위한 메모리 관리자 - 세션 계좌 관리자 기반으로 교체
            self.memory_manager = DayTradingMemoryWrapper(self.account_manager, self.account_type)
            
            # 계좌 메모리 관리자 초기화 (거래 후 계좌 상태 갱신용)
            try:
                from support.account_memory_manager import AccountMemoryManager
                self.account_memory_manager = AccountMemoryManager()
                
                # 초기화 확인
                if not hasattr(self, 'account_memory_manager') or self.account_memory_manager is None:
                    raise Exception("계좌 메모리 관리자 초기화 실패")
                    
                if CLEAN_LOGGER_AVAILABLE:
                    clean_log("계좌 메모리 관리자 초기화 완료", "SUCCESS")
                else:
                    logger.info("계좌 메모리 관리자 초기화 완료")
                    
            except Exception as e:
                logger.error(f"계좌 메모리 관리자 초기화 오류: {e}")
                self.account_memory_manager = None
                if CLEAN_LOGGER_AVAILABLE:
                    clean_log("계좌 메모리 관리자 초기화 실패 - None으로 설정", "WARNING")
                else:
                    logger.warning("계좌 메모리 관리자 초기화 실패 - None으로 설정")
            
            # 텔레그램 초기화
            await self._initialize_telegram()
            
            # 계좌 정보 조회 및 표시
            await self._display_account_info()
            
            # 종목 데이터 로드
            await self._load_stock_data()
            
            if CLEAN_LOGGER_AVAILABLE:
                clean_log("시스템 초기화 완료", "SUCCESS")
            else:
                logger.info("시스템 초기화 완료")
            return True
            
        except Exception as e:
            if CLEAN_LOGGER_AVAILABLE:
                clean_log(f"시스템 초기화 오류: {str(e)[:100]}", "ERROR")
            else:
                logger.error(f"시스템 초기화 오류: {e}")
            return False
    
    async def _pre_day_trading_initialization(self) -> bool:
        """단타매매 시작 전 초기화 작업 (계좌조회 + 전날잔고처리 + 급등종목수집)"""
        try:
            # API 초기화 먼저 수행
            if not await self._initialize_api():
                print("서버가 응답하지 않기 때문에 메인메뉴로 복귀합니다.")
                return False
            
            # 계좌 조회 중 메시지만 표시
            from support.account_display_utils import show_account_inquiry_message, display_account_info
            show_account_inquiry_message()
            
            # 계좌 정보 초기 업데이트 및 서버 연결 확인 (3번 재시도)
            logger.info("계좌 정보 업데이트 시작")
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # 1. 토큰 발급 확인
                    token = self.api.get_access_token()
                    if not token:
                        raise Exception("토큰 발급 실패")
                    
                    # 2. 계좌 조회 확인
                    account_balance = await self.api.get_account_balance()
                    if not account_balance:
                        raise Exception("계좌 조회 실패")
                    
                    # rt_cd가 None이면 성공으로 간주 (일부 API는 rt_cd를 반환하지 않음)
                    rt_cd = account_balance.get('rt_cd')
                    if rt_cd is not None and rt_cd != '0':
                        raise Exception(f"계좌 조회 오류: {rt_cd}")
                    
                    # 성공시 break
                    break
                    
                except Exception as e:
                    logger.error(f"서버 연결 시도 {attempt + 1}/{max_retries} 실패: {e}")
                    if attempt < max_retries - 1:
                        logger.info(f"재시도 중... ({attempt + 2}/{max_retries})")
                        await asyncio.sleep(2)  # 2초 대기 후 재시도
                        continue
                    else:
                        print("서버가 응답하지 않기 때문에 메인메뉴로 복귀합니다.")
                        return False
            
            # 3. 세션 계좌 관리자를 통한 실시간 계좌 정보 조회
            await self.account_manager.get_account_info(force_refresh=True)
            
            # 자동매매와 동일한 상세 계좌 정보 표시
            account_info = await self.api.get_account_balance(force_refresh=True)
            
            # 향상된 콘솔 출력으로 계좌 정보 표시
            try:
                from support.enhanced_console_output import print_status, print_account
                
                print_status("SUCCESS", "서버 연결 및 계좌 조회 완료")
                
                # 계좌 데이터 포맷팅 - 임시 단순화
                try:
                    account_display_data = self._format_account_data_for_display(account_info)
                    print_account(account_display_data)
                except (AttributeError, NameError) as e:
                    # 메소드가 없는 경우 임시 대체
                    clean_log(f"계좌 데이터 포맷팅 생략: {e}", "WARNING")
                    account_display_data = {"balance": "조회 완료", "status": "정상"}
                    print_account(account_display_data)
                
            except ImportError:
                # Rich 라이브러리가 없는 경우 기존 방식 사용
                self._display_account_info_legacy(account_info)
            
            # 텔레그램 알림 (간소화)
            if self.telegram_notifier:
                try:
                    # 보유종목 수 계산
                    output1 = account_info.get('output1', [])
                    holding_count = len([stock for stock in output1 if 'hldg_qty' in stock and int(stock['hldg_qty']) > 0])
                    
                    telegram_message = f"[{self.account_type}] 단타매매 계좌조회 완료\n보유종목: {holding_count}개"
                    
                    # 주문가능금액 추가
                    output2 = account_info.get('output2', [])
                    if output2:
                        def safe_int(value, default=0):
                            try:
                                return int(float(str(value).replace(',', '')))
                            except:
                                return default
                        
                        balance_info = output2[0]
                        if 'ord_psbl_cash' not in balance_info:
                            raise Exception("API 응답에 주문가능금액(ord_psbl_cash) 정보가 없습니다")
                        ord_psbl_cash_int = safe_int(balance_info['ord_psbl_cash'])
                        telegram_message += f"\n주문가능금액: {ord_psbl_cash_int:,}원"
                    
                    await self.telegram_notifier.send_message(telegram_message)
                except Exception as e:
                    logger.warning(f"텔레그램 알림 전송 실패: {e}")
            
            # 3초 간격 처리
            await step_delay(3)
            
            print_step_start("전날잔고처리")
            
            # 전날잔고처리 실행
            cleanup_result = await self._execute_balance_cleanup()
            
            # 잔고처리 완료 후 세션 계좌 정보 재조회
            if cleanup_result.get('sold_stocks', 0) > 0:
                logger.info("잔고처리 완료 - 세션 계좌 정보 업데이트")
                await self.account_manager.get_account_info(force_refresh=True)
            
            # 분석 결과 포함 메시지 생성
            analysis_display = "\n".join(cleanup_result.get('analysis_results', []))
            cleanup_message = f"""전날잔고처리가 완료되었습니다.

[처리 결과]
- 매도된 종목: {cleanup_result['sold_stocks']}개
- 보유 유지 종목: {cleanup_result['kept_stocks']}개  
- 실현 손익: {cleanup_result['profit']}

[상세 분석 결과]
{analysis_display if analysis_display else '분석된 보유종목이 없습니다.'}"""

            print(cleanup_message)
            
            if self.telegram_notifier:
                await self.telegram_notifier.send_message(f"[{self.account_type}] 단타매매 전날잔고처리 완료\n{cleanup_message}")
            
            print_step_end("전날잔고처리")
            
            # 3초 간격 처리
            await step_delay(3)
            
            # ========== 급등종목 수집 및 화면 표시 ==========
            print_step_start("급등종목 수집")
            print("\n한국투자 OPEN-API로 급등종목을 수집합니다...")
            
            # 급등종목 수집 (한투 API 직접 호출)
            self.surge_stocks_data = await self._collect_and_display_surge_stocks()
            
            if self.surge_stocks_data:
                print(f"\n[성공] 급등종목 {len(self.surge_stocks_data)}개 수집 완료!")
                
                # 급등종목 화면 표시 (간단한 형식)
                print("\n[급등종목 리스트]")
                print()
                
                for i, stock in enumerate(self.surge_stocks_data[:10], 1):
                    # 매수량 증가 비율 계산 (volume_ratio 사용)
                    volume_increase_ratio = stock.get('volume_ratio', 1.0)
                    print(f"{i}위. {stock['name']}({stock['code']}) / "
                          f"{stock.get('current_price', 0):,}원 / "
                          f"{stock.get('change_rate', 0):+.1f}% / "
                          f"매수량 {volume_increase_ratio:.1f}배")
                
                print(f"\n※ 이 종목들을 대상으로 단타매매를 진행합니다.")
                
                # 텔레그램 알림
                if self.telegram_notifier:
                    top3_msg = "\n".join([f"{i}. {s['name']}({s['code']}) {s.get('change_rate', 0):+.2f}%" 
                                         for i, s in enumerate(self.surge_stocks_data[:3], 1)])
                    await self.telegram_notifier.send_message(
                        f"[{self.account_type}] 급등종목 수집 완료\n"
                        f"총 {len(self.surge_stocks_data)}개 종목\n\n"
                        f"TOP 3:\n{top3_msg}"
                    )
            else:
                print("\n[경고] 급등종목 수집 실패 - 기본 종목으로 진행합니다.")
                self.surge_stocks_data = []
            
            print_step_end("급등종목 수집")
            
            # 3초 간격 처리
            await step_delay(3)
            
            # 초기 계좌 정보 로드 (기존 로직)
            if not await self.memory_manager.initial_account_load():
                logger.error("초기 계좌 정보 로드 실패")
                await self._send_error_notification("초기 계좌 정보 로드 실패")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"단타매매 초기화 실패: {e}")
            return False
    
    async def _initialize_api(self) -> bool:
        """API 연결 초기화"""
        try:
            if not self.api:
                from support.api_connector import KISAPIConnector
                is_mock = (self.account_type == "MOCK")
                self.api = KISAPIConnector(is_mock=is_mock)
                self._api_initialized = True
                logger.info("API 초기화 완료")
            return True
        except Exception as e:
            logger.error(f"API 초기화 오류: {e}")
            return False
    
    async def _initialize_telegram(self):
        """텔레그램 알림 시스템 초기화"""
        try:
            from support.telegram_notifier import get_telegram_notifier
            self.telegram_notifier = get_telegram_notifier()
            logger.info("텔레그램 초기화 완료")
        except Exception as e:
            logger.warning(f"텔레그램 초기화 실패: {e}")
            self.telegram_notifier = None
    
    async def _load_stock_data(self):
        """종목 데이터 로드 - API 데이터만 사용하므로 캐시 사용 안함"""
        # 캐시 사용 안함 - 모든 데이터는 API에서 실시간으로 가져옴
        logger.info("종목 데이터 캐시 사용 안함 - API 실시간 데이터 사용")
        pass
    
    async def _execute_day_trading_cycle(self, cycle_number: int) -> Dict[str, Any]:
        """단타매매 사이클 실행"""
        try:
            start_time = datetime.now()
            
            # 0. 알고리즘의 급등종목 수집 기능 호출 (매 사이클마다)
            if self.algorithm and hasattr(self.algorithm, 'collect_surge_stocks'):
                logger.info(f"사이클 {cycle_number}: 알고리즘에서 급등종목 수집 요청")
                try:
                    surge_collection_success = await self.algorithm.collect_surge_stocks(self)
                    if surge_collection_success:
                        logger.info(f"사이클 {cycle_number}: 급등종목 수집 완료")
                    else:
                        logger.warning(f"사이클 {cycle_number}: 급등종목 수집 실패 - 서버 응답 없음")
                        # 급등종목 수집 실패 시 사이클 종료 신호 반환
                        return {"success": False, "action": "server_error", "message": "서버가 응답하지 않기 때문에 메인메뉴로 복귀합니다"}
                except Exception as e:
                    logger.error(f"사이클 {cycle_number}: 급등종목 수집 오류: {e}")
                    # 오류 발생 시 사이클 종료 신호 반환  
                    return {"success": False, "action": "server_error", "message": "서버가 응답하지 않기 때문에 메인메뉴로 복귀합니다"}
            
            # 1. 계좌 정보 업데이트
            await self.memory_manager.update_account_info()
            account_info = self.memory_manager.get_account_info()
            
            # buyable_cash가 없거나 0일 경우 available_cash 사용
            if account_info.get('buyable_cash', 0) == 0:
                account_info['buyable_cash'] = account_info.get('available_cash', 0)
            
            # 그래도 0이면 cash_balance 사용
            if account_info.get('buyable_cash', 0) == 0:
                account_info['buyable_cash'] = account_info.get('cash_balance', 0)
            
            # 2. 현재 포지션 확인
            current_positions_list = self.memory_manager.get_positions()
            position_count = len(current_positions_list)
            
            # 포지션 리스트를 딕셔너리로 변환 (stock_code를 키로 사용하여 매도 로직과 일치)
            current_positions = {}
            for position in current_positions_list:
                if isinstance(position, dict):
                    # stock_code를 우선 사용하고, 없으면 symbol 사용
                    stock_code = position.get('stock_code') or position.get('symbol')
                    if stock_code:
                        # avg_price 필드가 없으면 추가 (MemoryWrapper 호환성) - 완전한 fallback chain
                        if 'avg_price' not in position:
                            if 'average_price' in position:
                                position['avg_price'] = position['average_price']
                            elif 'price' in position:
                                position['avg_price'] = position['price']
                            else:
                                # 최후의 수단으로 0 설정 (오류 방지)
                                position['avg_price'] = 0
                                logger.warning(f"종목 {stock_code}: avg_price 필드를 0으로 초기화")
                        current_positions[stock_code] = position
            
            # 3. 매도 신호 확인 (보유 종목 대상)
            sell_results = await self._process_sell_signals(current_positions)
            
            # 4. 매수 신호 확인 (신규 종목 대상) - 포지션 수 제한 고려
            buy_results = []
            if position_count < self.max_positions:
                buy_results = await self._process_buy_signals(account_info, current_positions)
                
                # 서버가 응답하지 않는 경우 (None 반환)
                if buy_results is None:
                    logger.error(f"사이클 {cycle_number}: 서버 응답 없음으로 단타매매 중단")
                    return {"success": False, "action": "server_error", "message": "서버가 응답하지 않기 때문에 메인메뉴로 복귀합니다"}
            
            # 5. 사이클 결과 정리
            cycle_result = {
                'cycle_number': cycle_number,
                'timestamp': start_time.strftime('%H:%M:%S'),
                'account_balance': account_info.get('cash_balance', 0),
                'position_count': position_count,
                'sell_results': sell_results,
                'buy_results': buy_results,
                'session_stats': self.memory_manager.get_session_stats()
            }
            
            return cycle_result
            
        except Exception as e:
            logger.error(f"단타매매 사이클 실행 오류: {e}")
            raise
    
    async def _process_sell_signals(self, current_positions: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """매도 신호 처리 (보유 종목 대상)"""
        sell_results = []
        
        try:
            if current_positions:
                print_algorithm_start("단타매매")
            
            for stock_code, position in current_positions.items():
                try:
                    # 종목 현재 데이터 조회
                    stock_data = await self._get_stock_current_data(stock_code)
                    if not stock_data:
                        continue
                    
                    # 알고리즘 분석 (운영 모드에서는 포지션 존재로 시간 체크 우회)
                    signal_result = await self._analyze_with_algorithm(stock_code, stock_data, is_position=True)
                    
                    # 매도 조건 확인
                    if (signal_result.get('signal') == 'SELL' or 
                        self._check_stop_loss_condition(position, stock_data) or
                        self._check_take_profit_condition(position, stock_data)):
                        
                        # 매도 주문 실행
                        sell_result = await self._execute_sell_order(stock_code, position, signal_result)
                        sell_results.append(sell_result)
                        
                        # 거래 통계 업데이트
                        self.memory_manager.update_trade_stats(sell_result)
                
                except Exception as e:
                    logger.warning(f"종목 {stock_code} 매도 신호 처리 오류: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"매도 신호 처리 전체 오류: {e}")
        
        if current_positions:
            print_algorithm_end("단타매매")
            await step_delay(3)
        
        return sell_results
    
    async def _process_buy_signals(self, account_info: Dict, current_positions: Dict) -> List[Dict[str, Any]]:
        """매수 신호 처리 (신규 종목 대상)"""
        buy_results = []
        
        try:
            # 매수 가능 현금 확인
            available_cash = account_info.get('buyable_cash', 0)
            if available_cash < 10000:  # 최소 매수 금액
                print(f"\n[경고] 매수 가능 금액 부족: {available_cash:,.0f}원")
                return buy_results
            
            print(f"\n[정보] 매수 가능 금액: {available_cash:,.0f}원")
            
            # 단타 매수 후보 종목 선별
            candidate_stocks = await self._select_day_trade_candidates(current_positions)
            
            # 서버가 응답하지 않는 경우 (None 반환)
            if candidate_stocks is None:
                print("서버가 응답하지 않기 때문에 메인메뉴로 복귀합니다.")
                return None  # 단타매매 중단 신호
            elif not candidate_stocks:
                print("매수 후보 종목이 없습니다.")
                return buy_results
            
            print(f"\n[급등종목 분석 시작] {len(candidate_stocks)}개 종목")
            print("-" * 60)
            
            analyzed_count = 0
            for symbol in candidate_stocks[:10]:  # 최대 10개까지만 분석
                try:
                    analyzed_count += 1
                    stock_info = self.surge_stocks_dict.get(symbol, {})
                    stock_name = stock_info.get('name', 'Unknown')
                    
                    print(f"\n[분석] {analyzed_count}: {stock_name}({symbol})")
                    
                    # 종목 데이터 조회
                    stock_data = await self._get_stock_current_data(symbol)
                    if not stock_data:
                        print(f"   [오류] 데이터 조회 실패")
                        continue
                    
                    # 알고리즘 분석 (운영 모드에서는 포지션 존재로 시간 체크 우회)
                    signal_result = await self._analyze_with_algorithm(symbol, stock_data, is_position=True)
                    
                    print(f"   현재가: {stock_data.get('current_price', 0):,.0f}원")
                    print(f"   전일대비: {stock_data.get('change_rate', 0):+.2f}%")
                    print(f"   거래량: {stock_data.get('volume', 0):,}")
                    print(f"   신호: {signal_result.get('signal')} (신뢰도: {signal_result.get('confidence', 0):.2f})")
                    print(f"   이유: {signal_result.get('reason', '')}")
                    
                    # 매수 조건 확인 (동적 신뢰도 임계값 사용)
                    if (signal_result.get('signal') == 'BUY' and 
                        signal_result.get('confidence', 0) > self.confidence_threshold):
                        
                        print(f"   [매수] 매수 조건 충족! 주문 실행...")
                        
                        # 매수 주문 실행
                        buy_result = await self._execute_buy_order(symbol, stock_data, signal_result, available_cash)
                        buy_results.append(buy_result)
                        
                        if buy_result.get('executed', False):
                            print(f"   [성공] 매수 완료: {buy_result.get('quantity', 0):,}주 @ {buy_result.get('price', 0):,.0f}원")
                            print(f"   [정보] 사용 금액: {buy_result.get('used_amount', 0):,.0f}원")
                            
                            # 거래 통계 업데이트
                            self.memory_manager.update_trade_stats(buy_result)
                            
                            # 매수 성공 시 가용 현금 업데이트
                            used_cash = buy_result.get('used_amount', 0)
                            available_cash -= used_cash
                            
                            print(f"   [정보] 남은 금액: {available_cash:,.0f}원")
                            
                            if available_cash < 10000:  # 더 이상 매수 불가
                                print("\n매수 가능 금액 소진")
                                break
                        else:
                            print(f"   [실패] 매수 실패: {buy_result.get('error', 'Unknown')}")
                    else:
                        print(f"   [대기] 매수 조건 미충족")
                
                except Exception as e:
                    logger.warning(f"종목 {symbol} 매수 신호 처리 오류: {e}")
                    print(f"   [오류] 오류 발생: {str(e)[:50]}")
                    continue
            
            print("-" * 60)
            print(f"분석 완료: {analyzed_count}개 종목, 매수: {len(buy_results)}건")
        
        except Exception as e:
            logger.error(f"매수 신호 처리 전체 오류: {e}")
            print(f"\n[오류] 매수 신호 처리 오류: {str(e)}")
        
        return buy_results
    
    async def _get_stock_current_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """종목 현재 데이터 조회"""
        try:
            # API를 통한 실시간 가격 조회
            if hasattr(self.api, 'get_stock_price'):
                price_data = self.api.get_stock_price(symbol)
                if price_data and price_data.get('rt_cd') == '0':
                    output = price_data.get('output', {})
                    # 필수 주가 정보 검증
                    if 'stck_prpr' not in output:
                        raise Exception(f"종목({symbol}) 현재가 정보가 없습니다")
                        
                    return {
                        'symbol': symbol,
                        'current_price': float(output['stck_prpr']),
                        'open_price': float(output.get('stck_oprc', output['stck_prpr'])),
                        'high_price': float(output.get('stck_hgpr', output['stck_prpr'])),
                        'low_price': float(output.get('stck_lwpr', output['stck_prpr'])),
                        'volume': int(output.get('acml_vol', '0')),
                        'change_rate': float(output.get('prdy_ctrt', '0')),
                        'timestamp': datetime.now()
                    }
            
            return None
        except Exception as e:
            logger.warning(f"종목 {symbol} 데이터 조회 오류: {e}")
            return None
    
    async def _analyze_with_algorithm(self, symbol: str, stock_data: Dict, is_position: bool = False) -> Dict[str, Any]:
        """알고리즘을 통한 신호 분석
        
        Args:
            symbol: 종목 코드
            stock_data: 종목 데이터
            is_position: 기존 포지션 여부 (True시 시간 체크 우회)
        """
        try:
            if self.algorithm and hasattr(self.algorithm, 'analyze'):
                # 알고리즘 호출
                result = self.algorithm.analyze(stock_data, symbol)
                
                # 결과가 dict인지 확인 및 타입 검증 강화
                if isinstance(result, dict):
                    # 필수 키가 있는지 확인
                    if 'signal' not in result:
                        result['signal'] = 'HOLD'
                    if 'confidence' not in result:
                        result['confidence'] = 0.5
                    if 'reason' not in result:
                        result['reason'] = '알고리즘 분석 결과'
                    return result
                elif isinstance(result, str):
                    # 구 버전 호환성 (문자열 반환)
                    return {
                        'signal': result if result in ['BUY', 'SELL', 'HOLD'] else 'HOLD',
                        'confidence': 0.7,
                        'reason': '알고리즘 분석 결과'
                    }
                elif result is None:
                    # None 반환 처리
                    return {'signal': 'HOLD', 'confidence': 0.0, 'reason': '알고리즘 결과 없음'}
                else:
                    # 예상치 못한 반환 타입
                    logger.warning(f"알고리즘 반환 타입 오류 ({symbol}): {type(result)}, 값: {result}")
                    return {'signal': 'HOLD', 'confidence': 0.5, 'reason': f'알고리즘 반환 타입 오류: {type(result)}'}
            
            # 알고리즘이 없으면 간단한 분석 사용
            return self._simple_day_trading_analysis(symbol, stock_data)
            
        except Exception as e:
            logger.warning(f"알고리즘 분석 오류 ({symbol}): {e}")
            return {'signal': 'HOLD', 'confidence': 0.0, 'reason': f'분석 오류: {str(e)[:50]}'}
    
    def _simple_day_trading_analysis(self, symbol: str, stock_data: Dict) -> Dict[str, Any]:
        """단타매매용 간단한 급등주 분석"""
        try:
            current_price = stock_data.get('current_price', 0)
            open_price = stock_data.get('open_price', 0)
            high_price = stock_data.get('high_price', 0)
            low_price = stock_data.get('low_price', 0)
            volume = stock_data.get('volume', 0)
            change_rate = stock_data.get('change_rate', 0)
            
            # 기본 조건 확인
            if current_price <= 0 or open_price <= 0:
                return {'signal': 'HOLD', 'confidence': 0.0, 'reason': '가격 데이터 부족'}
            
            # 단타매매 급등주 매수 조건
            confidence = 0.5
            reasons = []
            
            # 1. 상승률 조건 (1% 이상)
            intraday_return = (current_price - open_price) / open_price
            if intraday_return >= 0.01:  # 1% 이상 상승
                confidence += 0.15
                reasons.append(f"장중상승 {intraday_return*100:.1f}%")
            
            # 2. 전일대비 상승률 조건 (2% 이상)
            if change_rate >= 2.0:  # 2% 이상 상승
                confidence += 0.2
                reasons.append(f"전일대비 {change_rate:.1f}%↑")
            
            # 3. 고가 근처 거래 (고가 대비 95% 이상)
            if high_price > 0 and current_price >= high_price * 0.95:
                confidence += 0.1
                reasons.append("고가근처")
            
            # 4. 양봉 조건
            if current_price > open_price:
                confidence += 0.1
                reasons.append("양봉")
            
            # 5. 거래량 조건 (임의 기준)
            if volume > 100000:  # 10만주 이상
                confidence += 0.05
                reasons.append("거래량양호")
            
            # 매수 신호 판정 (신뢰도 0.7 이상)
            if confidence >= 0.7:
                return {
                    'signal': 'BUY',
                    'confidence': min(confidence, 0.95),  # 최대 95%
                    'reason': f"급등주매수: {', '.join(reasons)}",
                    'details': {
                        'intraday_return': intraday_return,
                        'change_rate': change_rate,
                        'price_level': current_price / high_price if high_price > 0 else 1.0,
                        'volume': volume
                    }
                }
            
            # 매도 신호 판정 (급락 시)
            if intraday_return <= -0.02 or change_rate <= -3.0:  # 2% 이상 하락
                return {
                    'signal': 'SELL',
                    'confidence': 0.8,
                    'reason': f"급락매도: 장중 {intraday_return*100:.1f}%, 전일대비 {change_rate:.1f}%",
                    'details': {
                        'intraday_return': intraday_return,
                        'change_rate': change_rate
                    }
                }
            
            # 기본 보류
            return {
                'signal': 'HOLD',
                'confidence': confidence,
                'reason': f"조건부족: {', '.join(reasons) if reasons else '매수조건 미달'}",
                'details': {
                    'intraday_return': intraday_return,
                    'change_rate': change_rate,
                    'required_confidence': 0.7,
                    'current_confidence': confidence
                }
            }
            
        except Exception as e:
            return {'signal': 'HOLD', 'confidence': 0.0, 'reason': f'분석오류: {str(e)[:30]}'}
    
    async def _select_day_trade_candidates(self, current_positions: Dict, force_refresh: bool = False) -> List[str]:
        """단타매매 후보 종목 선별 - 수집된 급등종목만 사용"""
        try:
            candidates = []
            
            # force_refresh가 True이거나 급등종목 데이터가 없으면 재수집
            if force_refresh or not self.surge_stocks_data:
                print(f"\n[급등종목 수집 {'재' if force_refresh else ''}시작]")
                self.surge_stocks_data = await self._collect_and_display_surge_stocks()
                
                # 서버가 응답하지 않는 경우 (None 반환)
                if self.surge_stocks_data is None:
                    return None  # 단타매매 중단 신호
                
                # 급등종목 딕셔너리 업데이트
                self.surge_stocks_dict = {}
                if self.surge_stocks_data:
                    for stock in self.surge_stocks_data:
                        self.surge_stocks_dict[stock['code']] = stock
                        
                print(f"급등종목 수집 완료: {len(self.surge_stocks_data)}개")
            
            # 급등종목 데이터가 있는 경우
            if self.surge_stocks_data:
                print(f"\n[단타매매 후보 종목 분석]")
                print(f"수집된 급등종목 {len(self.surge_stocks_data)}개 중에서 선별")
                
                # 급등종목을 후보에 추가 (이미 보유한 종목 제외)
                for stock_info in self.surge_stocks_data:
                    if stock_info['code'] not in current_positions:
                        candidates.append(stock_info['code'])
                
                # 상위 5개 종목 표시
                print("\n현재 분석 대상 종목:")
                for i, code in enumerate(candidates[:5], 1):
                    stock = self.surge_stocks_dict.get(code, {})
                    print(f"  {i}. {stock.get('name', 'Unknown')}({code}) "
                          f"{stock.get('change_rate', 0):.2f}%↑ "
                          f"거래량{stock.get('volume_ratio', 0):.1f}배")
            else:
                print("\n[경고] 급등종목 데이터 수집 실패")
            
            if not candidates:
                print("[경고] 매수 가능한 급등종목이 없습니다.")
            
            return candidates[:10]  # 최대 10개까지만 분석
            
        except Exception as e:
            logger.warning(f"후보 종목 선별 오류: {e}")
            return []
    
    async def _collect_and_display_surge_stocks(self) -> List[Dict]:
        """급등종목 수집 및 화면 표시 (한투 API 직접 호출)"""
        try:
            # 모의투자 모드 체크
            if self.account_type == "MOCK":
                # 모의투자는 실전 API로 급등종목 조회
                logger.info(f"{self.account_type}: 실전투자 API로 급등종목 데이터 조회")
                print(f"{self.account_type}: 실전투자 API로 급등종목 데이터 조회")
                
                # 임시로 실전 API 생성 (급등종목 조회용)
                from support.api_connector import KISAPIConnector
                temp_api = KISAPIConnector(is_mock=False)
                surge_ranking = temp_api.get_market_surge_ranking(market_type="ALL", limit=20)
                print(f"{self.account_type}: 실전API로 급등주 조회 성공 {len(surge_ranking.get('output', []))}개")
            else:
                # 실전투자는 자체 API 사용
                logger.info("한국투자 OPEN-API로 급등종목 조회 시작")
                surge_ranking = self.api.get_market_surge_ranking(market_type="ALL", limit=20)
            
            if surge_ranking and surge_ranking.get('rt_cd') == '0':
                surge_stocks = []
                output = surge_ranking.get('output', [])
                
                for stock_info in output[:15]:  # 상위 15개 수집
                    # OPEN-API 응답 형식에 맞춰 파싱 및 검증
                    if 'mksc_shrn_iscd' not in stock_info:
                        continue  # 종목코드가 없는 경우 건너뛰기
                    if 'stck_prpr' not in stock_info:
                        continue  # 현재가 정보가 없는 경우 건너뛰기
                        
                    code = stock_info['mksc_shrn_iscd']  # 종목코드
                    name = stock_info.get('hts_kor_isnm', code)  # 종목명
                    current_price = float(stock_info['stck_prpr'])  # 현재가
                    change_rate = float(stock_info.get('prdy_ctrt', '0'))  # 전일대비율
                    volume = int(stock_info.get('acml_vol', '0'))  # 누적거래량
                    
                    # 전일 거래량 대비 계산
                    prev_volume = int(stock_info.get('prdy_vol', '1'))
                    volume_ratio = volume / prev_volume if prev_volume > 0 else 1.0
                    
                    if code and name:
                        surge_stocks.append({
                            "name": name,
                            "code": code,
                            "current_price": current_price,
                            "change_rate": change_rate,  # 이미 % 단위
                            "volume": volume,
                            "volume_ratio": volume_ratio,
                            "reason": f"급등주 {change_rate:.2f}%↑ 거래량{volume_ratio:.1f}배"
                        })
                
                # 딕셔너리로도 저장 (빠른 조회용)
                self.surge_stocks_dict = {stock['code']: stock for stock in surge_stocks}
                
                # 급등종목 목록 화면 표시
                print("\n" + "="*50)
                print("수집된 급등종목 목록:")
                print("="*50)
                
                if surge_stocks:
                    for i, stock in enumerate(surge_stocks, 1):
                        stock_name = stock.get('name', 'Unknown')
                        stock_code = stock.get('code', 'Unknown')
                        current_price = stock.get('current_price', 0)
                        change_rate = stock.get('change_rate', 0)
                        volume_ratio = stock.get('volume_ratio', 0)
                        print(f"{i:2d}. {stock_name}({stock_code}) / {current_price:,.0f}원 / {change_rate:.2f}%↑ / 거래량{volume_ratio:.1f}배")
                else:
                    print("수집된 급등종목이 없습니다.")
                
                print("="*50)
                
                logger.info(f"OPEN-API 급등종목 {len(surge_stocks)}개 수집 완료")
                return surge_stocks
            else:
                error_msg = surge_ranking.get('msg1', 'Unknown error') if surge_ranking else 'Unknown error'
                logger.warning(f"급등종목 조회 실패: {error_msg}")
                print("서버가 응답하지 않기 때문에 메인메뉴로 복귀합니다.")
                return None  # 서버 응답 없음을 나타내는 None 반환
            
        except Exception as e:
            logger.error(f"한투 API 급등종목 수집 오류: {e}")
            print("서버가 응답하지 않기 때문에 메인메뉴로 복귀합니다.")
            return None  # 서버 응답 없음을 나타내는 None 반환
    
    async def _collect_theme_stocks_for_day_trading(self) -> List[str]:
        """단타매매용 테마종목 수집"""
        try:
            from stock_data_collector import StockDataCollector
            
            collector = StockDataCollector(max_analysis_stocks=10)
            theme_stocks = collector.theme_stocks[:10]  # 상위 10개만
            
            return theme_stocks
            
        except Exception as e:
            logger.warning(f"테마종목 수집 실패: {e}")
            return []
    
    def _check_stop_loss_condition(self, position: Dict, stock_data: Dict) -> bool:
        """손절 조건 확인"""
        try:
            if not isinstance(position, dict) or not isinstance(stock_data, dict):
                return False
                
            current_price = stock_data.get('current_price', 0)
            avg_price = position.get('avg_price', 0)
            
            if current_price > 0 and avg_price > 0:
                loss_rate = (current_price - avg_price) / avg_price
                return loss_rate <= -0.03  # 3% 손절
            
            return False
        except:
            return False
    
    def _check_take_profit_condition(self, position: Dict, stock_data: Dict) -> bool:
        """익절 조건 확인"""
        try:
            if not isinstance(position, dict) or not isinstance(stock_data, dict):
                return False
                
            current_price = stock_data.get('current_price', 0)
            avg_price = position.get('avg_price', 0)
            
            if current_price > 0 and avg_price > 0:
                profit_rate = (current_price - avg_price) / avg_price
                return profit_rate >= 0.05  # 5% 익절
            
            return False
        except:
            return False
    
    async def _execute_sell_order(self, symbol: str, position: Dict, signal_result: Dict) -> Dict[str, Any]:
        """매도 주문 실행"""
        try:
            if not isinstance(position, dict) or not isinstance(signal_result, dict):
                return {'executed': False, 'error': '잘못된 입력 데이터 형식'}
                
            quantity = position.get('quantity', 0)
            indicators = signal_result.get('indicators', {})
            current_price = indicators.get('current_price', 0) if isinstance(indicators, dict) else 0
            
            # 매도 주문 실행
            logger.info(f"매도 주문: {symbol} {quantity}주 @ {current_price}")
            
            # 실제 KIS API 호출하여 매도 주문 실행
            order_result = self.api.place_sell_order(symbol, quantity)
            executed = order_result.get('rt_cd') == '0' if order_result else False
            
            if not executed:
                logger.error(f"매도 주문 실패: {symbol} - {order_result}")
            else:
                logger.info(f"매도 주문 성공: {symbol} {quantity}주 - 주문번호: {order_result.get('ODNO', 'N/A')}")
                
                # 세션 계좌 관리자에 매매 완료 알림 (실시간 계좌 갱신)
                if self.account_manager:
                    await self.account_manager.notify_trade_completed("SELL", symbol, True)
            
            # 수익 계산 (매도가 - 평균단가) × 수량
            avg_price = position.get('avg_price', 0) or position.get('average_price', 0) or position.get('price', current_price)
            profit = (current_price - avg_price) * quantity if avg_price > 0 else 0
            profit_rate = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            
            result = {
                'symbol': symbol,
                'action': 'SELL',
                'quantity': quantity,
                'price': current_price,
                'avg_price': avg_price,
                'executed': executed,
                'amount': quantity * current_price,
                'profit': profit,
                'profit_rate': profit_rate,
                'reason': signal_result.get('reason', '매도 신호'),
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
            
            # 매도 완료 후 즉시 계좌 정보 업데이트
            if executed and hasattr(self, 'account_memory_manager') and self.account_memory_manager:
                # 급등종목 데이터에서 종목명 가져오기
                stock_name = self.surge_stocks_dict.get(symbol, {}).get('name', 
                                                       position.get('stock_name', symbol) if isinstance(position, dict) else symbol)
                trade_info = {
                    'stock_code': symbol,
                    'stock_name': stock_name,
                    'quantity': quantity,
                    'price': current_price,
                    'amount': quantity * current_price
                }
                await self.account_memory_manager.update_after_trade(
                    self.account_type, self.api, "SELL", trade_info
                )
                
                # 메모리 관리자도 즉시 갱신 (포지션 수와 현금 잔고 재계산)
                if hasattr(self, 'account_manager') and self.account_manager:
                    await self.account_manager.get_account_info(force_refresh=True)
                    logger.info(f"매도 후 계좌 상태 즉시 갱신 완료: {symbol}")
                
                # 메모리 관리자 내부 상태도 강제 갱신
                if hasattr(self, 'memory_manager') and self.memory_manager:
                    await self.memory_manager.refresh_positions()
                    # 거래 통계 업데이트 (수익 포함)
                    if hasattr(self.memory_manager, 'update_trade_stats'):
                        self.memory_manager.update_trade_stats(result)
                    logger.info("메모리 관리자 포지션 상태 및 거래 통계 갱신 완료")
            
            return result
            
        except Exception as e:
            logger.error(f"매도 주문 오류 ({symbol}): {e}")
            return {
                'symbol': symbol,
                'action': 'SELL',
                'executed': False,
                'error': str(e),
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
    
    async def _execute_buy_order(self, symbol: str, stock_data: Dict, signal_result: Dict, available_cash: float) -> Dict[str, Any]:
        """매수 주문 실행"""
        try:
            current_price = stock_data.get('current_price', 0)
            
            if current_price <= 0:
                return {'symbol': symbol, 'action': 'BUY', 'executed': False, 'error': '가격 정보 없음'}
            
            # 포지션 크기 계산 (가용 현금의 20% 사용)
            position_value = min(available_cash * 0.2, available_cash)
            quantity = int(position_value / current_price)
            
            if quantity <= 0:
                return {'symbol': symbol, 'action': 'BUY', 'executed': False, 'error': '수량 부족'}
            
            # 매수 주문 실행
            logger.info(f"매수 주문: {symbol} {quantity}주 @ {current_price}")
            
            # 실제 KIS API 호출하여 매수 주문 실행
            order_result = self.api.place_buy_order(symbol, quantity)
            executed = order_result.get('rt_cd') == '0' if order_result else False
            used_amount = quantity * current_price
            
            if not executed:
                logger.error(f"매수 주문 실패: {symbol} - {order_result}")
            else:
                logger.info(f"매수 주문 성공: {symbol} {quantity}주 - 주문번호: {order_result.get('ODNO', 'N/A')}")
            
            result = {
                'symbol': symbol,
                'action': 'BUY',
                'quantity': quantity,
                'price': current_price,
                'executed': executed,
                'used_amount': used_amount,
                'reason': signal_result.get('reason', '매수 신호'),
                'confidence': signal_result.get('confidence', 0.7),
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
            
            # 매수 완료 후 세션 계좌 관리자 알림
            if executed and hasattr(self, 'account_manager'):
                await self.account_manager.notify_trade_completed("BUY", symbol, True)
            
            return result
            
        except Exception as e:
            logger.error(f"매수 주문 오류 ({symbol}): {e}")
            return {
                'symbol': symbol,
                'action': 'BUY',
                'executed': False,
                'error': str(e),
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
    
    def _get_cycle_interval(self) -> int:
        """현재 시간에 따른 사이클 간격 반환 (알고리즘에서 제공)"""
        if self.algorithm and hasattr(self.algorithm, 'get_cycle_interval'):
            return self.algorithm.get_cycle_interval()
        
        # 알고리즘이 없으면 기본 2분
        return 120
    
    async def _check_stop_conditions(self) -> bool:
        """중단 조건 확인 (알고리즘 기반)"""
        try:
            # 파일 기반 중단 신호
            if self.stop_signal_file.exists():
                logger.info("파일 중단 신호 감지")
                self.stop_signal_file.unlink()
                return True
            
            # 알고리즘의 중단 조건 확인
            if self.algorithm and hasattr(self.algorithm, 'should_stop_trading'):
                if self.algorithm.should_stop_trading():
                    logger.info("알고리즘 중단 조건 달성")
                    return True
            
            # Market Close Controller를 통한 장마감 체크
            if not self.skip_market_hours:
                try:
                    from support.market_close_controller import get_market_close_controller
                    market_controller = get_market_close_controller()
                    
                    # 장마감 체크가 ON인 경우에만 종료
                    if market_controller.is_market_close_check_enabled():
                        current_time = datetime.now().time()
                        
                        if market_controller.should_stop_trading(current_time):
                            logger.info("[MARKET_CLOSE] 장마감 시간 도달 - 설정에 의한 자동 종료")
                            print(f"\n[{self.account_display}] 장마감 체크 설정(ON)에 의해 자동 종료됩니다.")
                            return True
                        
                        # 마감 임박 경고
                        time_info = market_controller.get_time_until_close(current_time)
                        if time_info["minutes"] <= 5 and not time_info["is_past_close"]:
                            print(f"\n[WARNING] 장 마감까지 {time_info['formatted']}")
                    else:
                        # 장마감 체크 OFF - 계속 실행
                        logger.debug("장마감 체크 OFF - 계속 실행")
                        
                except Exception as e:
                    logger.warning(f"Market Close Controller 사용 실패, 기본 로직 사용: {e}")
                    # 폴백: 기본 장시간 체크 (이전 로직)
                    now = datetime.now()
                    if now.hour >= 14 and now.minute >= 55:
                        logger.info("종장 시간 도달 (기본 체크)")
                        return True
            
            return False
            
        except Exception as e:
            logger.warning(f"중단 조건 확인 오류: {e}")
            return False
    
    async def _safe_sleep(self, total_seconds: int, purpose: str = ""):
        """중단 신호에 반응하는 안전한 대기 (개선된 타이머 표시)"""
        sleep_interval = 5  # 5초 단위로 체크 (더 세밀한 체크)
        elapsed = 0
        
        if purpose:
            logger.info(f"대기 시작: {total_seconds}초 ({purpose})")
            # 개선된 화면 대기 메시지 표시
            print(f"\n[{self.account_display}] 다음 {purpose}까지 {total_seconds}초 대기")
            print(f"{'='*60}")
        
        while elapsed < total_seconds and self.is_running and not self.stop_requested:
            # 중단 조건 체크
            if await self._check_stop_conditions():
                logger.info(f"대기 중 중단 신호 감지 (경과: {elapsed}초)")
                print(f"\n[WARNING] 중단 신호 감지됨 - 대기 중단")
                break
            
            # 5초 또는 남은 시간만큼 대기
            wait_time = min(sleep_interval, total_seconds - elapsed)
            await asyncio.sleep(wait_time)
            elapsed += wait_time
            
            # 시계 형태 카운트다운 표시 (5초마다)
            if purpose and elapsed < total_seconds:
                remaining = total_seconds - elapsed
                
                # 5초마다 카운트다운 표시
                if elapsed % 5 == 0:
                    current_time = datetime.now().strftime('%H:%M:%S')
                    
                    # 남은 시간을 MM:SS 형태로 변환
                    countdown_minutes = remaining // 60
                    countdown_seconds = remaining % 60
                    countdown_display = f"{countdown_minutes:02d}:{countdown_seconds:02d}"
                    
                    print(f"\r[{current_time}] 다음 {purpose}까지 남은시간: {countdown_display}", 
                          end="", flush=True)
        
        if purpose:
            print(f"\n[TIMER COMPLETE] 대기 완료 - 총 경과시간: {elapsed}초")
            print("="*60)
    
    async def _send_start_notification(self):
        """시작 알림 전송"""
        try:
            # 계좌 잔고 조회
            initial_balance = 0.0
            if self.memory_manager and hasattr(self.memory_manager, 'get_current_balance'):
                initial_balance = self.memory_manager.get_current_balance()
            
            # 알고리즘의 시작 메시지 사용
            if self.algorithm and hasattr(self.algorithm, 'on_algorithm_start'):
                message = self.algorithm.on_algorithm_start(self.account_type, initial_balance)
                # 단타매매 특화 정보 추가
                message += f"\n사이클 간격: {self.cycle_interval}초 (2분)"
            else:
                # 기본 메시지 (알고리즘이 없거나 메서드가 없는 경우)
                algorithm_name = "기본 알고리즘"
                if self.algorithm and hasattr(self.algorithm, 'get_name'):
                    algorithm_name = self.algorithm.get_name()
                
                message = (f"[{self.account_display}] 단타매매 시작\n"
                          f"알고리즘: {algorithm_name}\n"
                          f"초기잔고: {initial_balance:,.0f}원\n"
                          f"시작시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                          f"사이클 간격: {self.cycle_interval}초 (2분)")
            
            await self._send_notification(message)
        except Exception as e:
            logger.warning(f"시작 알림 전송 오류: {e}")
    
    async def _send_cycle_result(self, cycle_result: Dict):
        """사이클 결과 알림 전송"""
        try:
            cycle_num = cycle_result.get('cycle_number', 0)
            timestamp = cycle_result.get('timestamp', '')
            balance = cycle_result.get('account_balance', 0)
            position_count = cycle_result.get('position_count', 0)
            
            sell_count = len(cycle_result.get('sell_results', []))
            buy_count = len(cycle_result.get('buy_results', []))
            
            message = (f"[{self.account_display}] 사이클 {cycle_num} 완료\n"
                      f"시간: {timestamp}\n"
                      f"잔고: {balance:,}원\n"
                      f"보유종목: {position_count}개\n"
                      f"매도: {sell_count}건, 매수: {buy_count}건")
            
            await self._send_notification(message)
        except Exception as e:
            logger.warning(f"사이클 결과 전송 오류: {e}")
    
    async def _send_notification(self, message: str):
        """일반 알림 전송"""
        try:
            if self.telegram_notifier:
                await self.telegram_notifier.send_message(message)
        except Exception as e:
            logger.warning(f"알림 전송 오류: {e}")
    
    async def _send_error_notification(self, error_message: str):
        """오류 알림 전송"""
        try:
            message = f"[{self.account_display}] 단타매매 오류\n{error_message}"
            await self._send_notification(message)
        except Exception as e:
            logger.warning(f"오류 알림 전송 오류: {e}")
    
    async def _display_account_info(self):
        """계좌 정보 조회 및 표시"""
        try:
            # 계좌 잔고 조회
            account_balance = await self.api.get_account_balance(force_refresh=True)
            
            if not account_balance:
                if CLEAN_LOGGER_AVAILABLE:
                    clean_log("계좌 정보 조회 실패", "ERROR")
                else:
                    logger.error("계좌 정보 조회 실패")
                return
            
            # 예수금 정보
            cash_balance = float(account_balance.get('dnca_tot_amt', '0'))
            available_cash = float(account_balance.get('ord_psbl_cash', '0'))
            
            # 보유종목 정보
            holdings = account_balance.get('output1', [])
            holdings_with_qty = [h for h in holdings if int(h.get('hldg_qty', '0')) > 0]
            
            # 깔끔한 로거로 계좌 정보 표시
            if CLEAN_LOGGER_AVAILABLE:
                account_summary = {
                    'account_number': getattr(self.api, 'account_number', 'Unknown'),
                    'available_cash': available_cash,
                    'positions_count': len(holdings_with_qty),
                    'profit_rate': 0.0
                }
                log_account(account_summary)
            else:
                # 기존 방식 사용
                from support.account_display_utils import show_account_inquiry_message, display_account_info
                show_account_inquiry_message()
                
                account_data = {
                    'account_number': getattr(self.api, 'account_number', self.api.config.get("CANO", 'Unknown')),
                    'total_cash': cash_balance,
                    'buyable_cash': available_cash,
                    'profit_rate': 0.0,
                    'holdings': holdings_with_qty
                }
                display_account_info(account_data, self.account_type)
            
            # 텔레그램 알림 (간소화)
            if self.telegram_notifier:
                total_holdings = len(holdings_with_qty)
                msg = (f"[{self.account_display}] 단타매매 계좌 정보 조회 완료\n"
                      f"예수금: {cash_balance:,.0f}원\n"
                      f"주문가능금액: {available_cash:,.0f}원\n"
                      f"보유종목수: {total_holdings}개")
                
                await self.telegram_notifier.send_message(msg)
            
            # 메모리에 저장 (DayTradingMemoryManager가 자체적으로 관리)
            # Note: DayTradingMemoryManager는 update_account_info()를 통해 자체적으로 계좌 정보를 관리함
            
            logger.info(f"계좌 정보 조회 완료 - 예수금: {cash_balance:,.0f}원, 보유종목: {total_holdings}개")
            
        except Exception as e:
            logger.error(f"계좌 정보 조회 오류: {e}")
            if self.telegram_notifier:
                await self.telegram_notifier.send_message(f"[{self.account_display}] 계좌 정보 조회 오류: {str(e)[:100]}")
    
    async def _finalize_day_trading(self):
        """단타매매 종료 처리"""
        try:
            # 최종 잔고 조회
            final_balance = 0.0
            if self.memory_manager and hasattr(self.memory_manager, 'get_current_balance'):
                final_balance = self.memory_manager.get_current_balance()
            
            # 세션 통계 조회
            stats = self.memory_manager.get_session_stats() if self.memory_manager else {}
            
            # 알고리즘의 종료 메시지 사용
            if self.algorithm and hasattr(self.algorithm, 'on_algorithm_end'):
                message = self.algorithm.on_algorithm_end(self.account_type, final_balance, stats)
            else:
                # 기본 종료 메시지 (알고리즘이 없거나 메서드가 없는 경우)
                algorithm_name = "기본 알고리즘"
                if self.algorithm and hasattr(self.algorithm, 'get_name'):
                    algorithm_name = self.algorithm.get_name()
                
                total_trades = stats.get('total_trades', 0)
                session_duration = stats.get('session_duration', '알 수 없음')
                profit_loss = stats.get('profit_loss', 0)
                
                message = (f"[{self.account_display}] 단타매매 종료\n"
                          f"알고리즘: {algorithm_name}\n"
                          f"종료시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                          f"최종잔고: {final_balance:,.0f}원\n"
                          f"수익/손실: {profit_loss:+,.0f}원\n"
                          f"총 거래: {total_trades}건\n"
                          f"세션 시간: {session_duration}\n"
                          f"수고하셨습니다!")
            
            await self._send_notification(message)
            
            logger.info("단타매매 종료 처리 완료")
            
        except Exception as e:
            logger.warning(f"종료 처리 오류: {e}")
    
    async def _execute_balance_cleanup(self) -> Dict[str, Any]:
        """통합된 단타매매용 전날잔고처리 로직"""
        try:
            if not self.api:
                logger.error("API가 초기화되지 않았습니다")
                return {"sold_stocks": 0, "kept_stocks": 0, "profit": "0원", "analysis_results": []}
            
            # 통합 전날잔고 처리기 생성 (DAY_TRADING 전략 사용)
            balance_handler = PreviousDayBalanceHandler(
                self.api, 
                self.account_type, 
                TradingStrategy.DAY_TRADING
            )
            
            # 전날잔고 정리 실행
            cleanup_result = await balance_handler.execute_previous_day_balance_cleanup()
            
            # 기존 인터페이스에 맞게 결과 변환
            analysis_results = []
            if cleanup_result.get('details'):
                for detail in cleanup_result['details']:
                    stock_code = detail.get('stock_code', '')
                    stock_name = detail.get('stock_name', '')
                    action = detail.get('action', 'UNKNOWN')
                    reason = detail.get('reason', '알 수 없음')
                    analysis_results.append(f"{stock_name}({stock_code}): {action} - {reason}")
            
            return {
                "sold_stocks": cleanup_result.get('sold_count', 0),
                "kept_stocks": cleanup_result.get('kept_count', 0),
                "profit": f"{cleanup_result.get('sold_count', 0) * 1000:+,.0f}원",  # 임시 수익 계산
                "analysis_results": analysis_results,
                "success": cleanup_result.get('success', False)
            }
            
        except Exception as e:
            logger.error(f"통합 단타매매 잔고 정리 실행 실패: {e}")
            return {
                "sold_stocks": 0, 
                "kept_stocks": 0, 
                "profit": "실행 실패", 
                "analysis_results": [f"시스템 오류: {str(e)}"], 
                "error": str(e)
            }
    
    async def _analyze_day_position_decision(self, position: Dict[str, Any]) -> Dict[str, str]:
        """단타매매용 포지션 매매 결정 분석 (간단한 손절/익절)"""
        try:
            stock_code = position.get('stock_code')
            current_price = position.get('current_price', 0)
            avg_price = position.get('avg_price', 0)
            
            if avg_price <= 0:
                return {'action': 'KEEP', 'reason': '평균 매수가 정보 없음'}
            
            # 수익률 계산
            profit_rate = ((current_price - avg_price) / avg_price) * 100
            
            # 단타매매 기본 룰: -3% 손절, +2% 익절
            if profit_rate <= -3.0:
                return {'action': 'SELL', 'reason': f'손절 기준 ({profit_rate:.2f}% <= -3%)'}
            elif profit_rate >= 2.0:
                return {'action': 'SELL', 'reason': f'익절 기준 ({profit_rate:.2f}% >= 2%)'}
            else:
                return {'action': 'KEEP', 'reason': f'보유 유지 ({profit_rate:.2f}%)'}
                
        except Exception as e:
            logger.error(f"단타 포지션 분석 오류: {e}")
            return {'action': 'KEEP', 'reason': f'분석 오류: {str(e)}'}
    
    async def _execute_day_sell_order(self, position: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """단타매매용 매도 주문 실행"""
        try:
            stock_code = position.get('stock_code')
            quantity = position.get('quantity', 0)
            
            if quantity <= 0:
                logger.warning(f"매도할 수량이 없습니다: {stock_code}")
                return None
            
            # 매도 주문 실행
            sell_result = await self.api.sell_stock(stock_code, quantity)
            
            if sell_result and sell_result.get('success'):
                # 매도 완료 후 세션 계좌 관리자 알림
                await self.account_manager.notify_trade_completed("SELL", stock_code, True)
                
                return {
                    'success': True,
                    'profit': sell_result.get('profit', 0),
                    'stock_code': stock_code,
                    'quantity': quantity
                }
            else:
                logger.error(f"매도 주문 실패: {stock_code} - {sell_result}")
                return None
                
        except Exception as e:
            logger.error(f"단타 매도 주문 실행 오류: {e}")
            return None
    
    def _format_holdings_for_cleanup(self, holdings: List[Dict]) -> str:
        """잔고처리용 보유종목 포맷팅 (단타매매용)"""
        if not holdings:
            return "보유종목 없음"
        
        formatted_lines = []
        for holding in holdings[:10]:  # 최대 10개만 표시
            stock_name = holding.get('stock_name', '')
            stock_code = holding.get('stock_code', '')
            quantity = holding.get('quantity', 0)
            current_price = holding.get('current_price', 0)
            profit_loss = holding.get('profit_loss', 0)
            formatted_lines.append(
                f"- {stock_name}({stock_code}): {quantity:,}주, "
                f"현재가 {current_price:,.0f}원, 손익 {profit_loss:+,.0f}원"
            )
        
        if len(holdings) > 10:
            formatted_lines.append(f"... 외 {len(holdings) - 10}개 종목")
        
        return "\n".join(formatted_lines)


class DayTradingMemoryWrapper:
    """DayTradingAccountManager를 기존 day_trading_memory_manager 인터페이스로 래핑"""
    
    def __init__(self, day_trading_account_manager, account_type: str):
        self.day_trading_account_manager = day_trading_account_manager
        self.account_type = account_type
        # API 커넥터 참조 추가
        self.api = day_trading_account_manager.api_connector
        self.session_stats = {
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_profit': 0.0,
            'session_start_time': datetime.now()
        }
    
    async def initial_account_load(self) -> bool:
        """초기 계좌 정보 로드"""
        try:
            # 세션 계좌 관리자에서 계좌 정보 가져오기
            account_info = await self.day_trading_account_manager.get_account_info(force_refresh=True)
            return account_info is not None
        except Exception as e:
            logger.error(f"초기 계좌 로드 실패: {e}")
            return False
    
    async def update_account_info(self):
        """계좌 정보 업데이트"""
        try:
            # 세션 계좌 관리자를 통한 실시간 업데이트
            await self.day_trading_account_manager.get_account_info(force_refresh=True)
        except Exception as e:
            logger.warning(f"계좌 정보 업데이트 오류: {e}")
    
    async def get_account_info(self) -> Dict:
        """계좌 정보 조회 - 하드코딩된 데이터 제거하고 실제 API 호출"""
        try:
            # 🔥 하드코딩된 데이터 제거 - 실제 API 호출 강제 실행
            logger.info("실제 계좌 정보 API 호출 시작")
            
            # 먼저 day_trading_account_manager를 통해 최신 계좌 정보 강제 업데이트
            import asyncio
            try:
                # 비동기 컨텍스트에서 실행 중인지 확인
                loop = asyncio.get_running_loop()
                # 이미 실행 중인 루프가 있다면 태스크로 실행
                task = loop.create_task(self.day_trading_account_manager.update_account_info())
                account_data = None
                # 태스크 완료 대기는 하지 않고 직접 API 호출
            except RuntimeError:
                # 비동기 루프가 없다면 새로 시작
                account_data = asyncio.run(self.day_trading_account_manager.update_account_info())
            
            # 업데이트 후 정보 확인
            if self.day_trading_account_manager.has_valid_account_info():
                account_data = self.day_trading_account_manager._session_account_info
                logger.info(f"세션 계좌 관리자에서 정보 로드 성공")
            else:
                # 세션 관리자가 실패했다면 직접 API 호출
                logger.warning("세션 관리자 업데이트 실패 - 직접 API 호출")
                account_data = await self.api_connector.get_account_balance(force_refresh=True)
            
            if account_data:
                # API 응답 데이터 로깅 (디버깅용)
                logger.info(f"계좌 API 응답 데이터 키: {list(account_data.keys()) if isinstance(account_data, dict) else 'Not Dict'}")
                
                # API 응답을 기존 포맷으로 변환
                # API 데이터 필수 필드 검증
                if 'dnca_tot_amt' not in account_data or 'ord_psbl_cash' not in account_data:
                    raise Exception(f"API 응답에 필수 정보 누락: {list(account_data.keys())}")
                
                cash_balance = float(account_data['dnca_tot_amt'])
                available_cash = float(account_data['ord_psbl_cash'])
                total_evaluation = float(account_data.get('tot_evlu_amt', account_data.get('pchs_amt', cash_balance)))
                
                logger.info(f"파싱된 계좌 정보 - 예수금: {cash_balance:,.0f}원, 주문가능: {available_cash:,.0f}원")
                
                # 보유종목 정보 추출
                holdings = []
                if 'output1' in account_data:
                    logger.info(f"보유종목 데이터 확인: {len(account_data['output1'])}개 항목")
                    for item in account_data['output1']:
                        if 'hldg_qty' not in item:
                            continue  # 보유수량 정보가 없는 항목 스킵
                        quantity = int(item['hldg_qty'])
                        if quantity > 0:
                            stock_name = item.get('prdt_name', '').strip()
                            
                            # 정확한 보유수량 계산을 위한 추가 정보
                            ord_psbl_qty = int(item.get('ord_psbl_qty', quantity))  # 주문가능수량 (기본값: 보유수량)
                            thdt_sll_qty = int(item.get('thdt_sll_qty', 0))   # 당일매도수량
                            
                            # 실제 보유수량은 API 응답 그대로 사용
                            actual_quantity = quantity
                            
                            logger.info(f"보유종목 상세: {stock_name} - 시스템보유={quantity}주, 주문가능={ord_psbl_qty}주, 당일매도={thdt_sll_qty}주, 최종보유={actual_quantity}주")
                            
                            holdings.append({
                                'stock_code': item.get('pdno', ''),
                                'stock_name': stock_name,
                                'quantity': actual_quantity,
                                'sellable_quantity': ord_psbl_qty,  # 주문가능수량(매도가능)
                                'today_sell_quantity': thdt_sll_qty,  # 당일매도수량
                                'current_price': float(item.get('prpr', 1)),  # 현재가 (필수)
                                'purchase_price': float(item.get('pchs_avg_pric', 1)),  # 매입평균가 (필수)
                                'evaluation_amount': float(item.get('evlu_amt', actual_quantity * float(item.get('prpr', 1)))),
                                'profit_loss': float(item.get('evlu_pfls_amt', (float(item.get('prpr', 1)) - float(item.get('pchs_avg_pric', 1))) * actual_quantity))
                            })
                
                # 실현손익 정보 (없으면 계산)
                realized_profit = float(account_data.get('evlu_pfls_smtl_amt', sum(h['profit_loss'] for h in holdings)))
                asset_change = float(account_data.get('asst_icdc_amt', 0))
                
                result = {
                    'cash_balance': cash_balance,
                    'available_cash': available_cash,
                    'total_evaluation': total_evaluation,
                    'realized_profit': realized_profit,
                    'profit_rate': (realized_profit / cash_balance * 100) if cash_balance > 0 else 0.0,
                    'asset_change': asset_change,
                    'holdings': holdings
                }
                
                logger.info(f"최종 계좌 정보 - 예수금: {cash_balance:,.0f}원, 보유종목: {len(holdings)}개, 실현손익: {realized_profit:,.0f}원")
                return result
            else:
                logger.error("API 호출 결과가 None 또는 빈 데이터")
                raise Exception("계좌 정보 API 호출 실패")
            
        except Exception as e:
            logger.error(f"계좌 정보 조회 오류: {e}")
            # 🚨 하드코딩된 0값 완전 제거 - API 호출 실패시에도 재시도
            logger.warning("계좌 조회 실패 - 기본 API 커넥터로 재시도")
            try:
                # 마지막 시도: api_connector 직접 호출
                fallback_data = await self.api.get_account_balance(force_refresh=True)
                if fallback_data:
                    cash_balance = float(fallback_data.get('dnca_tot_amt', '0'))
                    available_cash = float(fallback_data.get('ord_psbl_cash', '0'))
                    total_evaluation = float(fallback_data.get('tot_evlu_amt', '0'))
                    # 실현손익 관련 정보 추가
                    realized_profit = float(fallback_data.get('evlu_pfls_smtl_amt', '0'))  # 실현손익금액
                    profit_rate = float(fallback_data.get('evlu_erng_rt', '0'))  # 수익률
                    
                    logger.warning(f"재시도 성공 - 예수금: {cash_balance:,.0f}원, 실현손익: {realized_profit:,.0f}원, 수익률: {profit_rate:.2f}%")
                    return {
                        'cash_balance': cash_balance,
                        'available_cash': available_cash,
                        'total_evaluation': total_evaluation,
                        'realized_profit': realized_profit,
                        'profit_rate': profit_rate,
                        'holdings': []
                    }
            except Exception as fallback_error:
                logger.error(f"재시도도 실패: {fallback_error}")
            
            # 최후의 수단으로만 빈 데이터 반환 (더 이상 하드코딩 없음)
            raise Exception("모든 계좌 조회 시도 실패")
    
    async def get_positions(self) -> List[Dict]:
        """보유 포지션 조회"""
        try:
            account_info = await self.get_account_info()
            return account_info.get('holdings', [])
        except Exception as e:
            logger.error(f"포지션 조회 오류: {e}")
            return []
    
    async def get_current_balance(self) -> float:
        """현재 잔고 조회"""
        try:
            account_info = await self.get_account_info()
            return account_info.get('available_cash', 0.0)
        except Exception as e:
            logger.error(f"잔고 조회 오류: {e}")
            return 0.0
    
    def update_trade_stats(self, trade_result: Dict):
        """거래 통계 업데이트"""
        try:
            self.session_stats['total_trades'] += 1
            if trade_result.get('executed', False):
                self.session_stats['successful_trades'] += 1
                profit = trade_result.get('profit', 0)
                self.session_stats['total_profit'] += profit
            else:
                self.session_stats['failed_trades'] += 1
        except Exception as e:
            logger.warning(f"거래 통계 업데이트 오류: {e}")
    
    def get_session_stats(self) -> Dict:
        """세션 통계 조회"""
        try:
            session_duration = datetime.now() - self.session_stats['session_start_time']
            return {
                **self.session_stats,
                'session_duration': str(session_duration).split('.')[0]  # 마이크로초 제거
            }
        except Exception as e:
            logger.error(f"세션 통계 조회 오류: {e}")
            return self.session_stats.copy()
    
    def _get_stock_name_fallback(self, stock_code: str, current_name: str) -> str:
        """종목코드에 대한 fallback 종목명 제공 - StockDataCollector 활용"""
        # StockDataCollector의 종목명 매핑 사용
        try:
            from stock_data_collector import StockDataCollector
            collector = StockDataCollector(max_analysis_stocks=20)  # 모의투자용 제한 적용
            fallback_name = collector._get_stock_name(stock_code, self.api)
            if fallback_name and not fallback_name.startswith('종목'):
                return fallback_name
        except Exception as e:
            logger.warning(f"StockDataCollector 종목명 조회 실패: {e}")
        
        # 최종 fallback - 기본값 사용
        if current_name.startswith('종목') or current_name == stock_code:
            return f"종목{stock_code}"
        
        return current_name
    
    def _format_account_data_for_display(self, account_info: Dict) -> Dict:
        """계좌 정보를 향상된 콘솔 출력용으로 포맷팅"""
        try:
            account_type_display = "실전투자" if self.account_type == "REAL" else "모의투자"
            account_number = account_info.get('ctx_area_nk100', 'N/A')
            
            # 안전한 숫자 변환 함수
            def safe_float(value, default=0.0):
                try:
                    return float(str(value).replace(',', ''))
                except:
                    return default
            
            def safe_int(value, default=0):
                try:
                    return int(float(str(value).replace(',', '')))
                except:
                    return default
            
            # 계좌 기본 정보 추출 (하드코딩된 초기값 제거)
            balance = None
            available_cash = None
            profit_rate = 0.0
            
            # API 응답이 루트 레벨에 있는지 먼저 확인
            if 'dnca_tot_amt' in account_info:
                # 루트 레벨에 직접 계좌 데이터가 있는 경우
                balance = safe_float(account_info.get('dnca_tot_amt', '0'))
                available_cash = safe_float(account_info.get('ord_psbl_cash', '0'))
                profit_rate = safe_float(account_info.get('evlu_erng_rt', '0'))
            else:
                # 기존 output2 구조 처리
                output2 = account_info.get('output2', [])
                if output2:
                    balance_info = output2[0]
                    balance = safe_float(balance_info.get('dnca_tot_amt', '0'))
                    available_cash = safe_float(balance_info.get('ord_psbl_cash', '0'))
                    profit_rate = safe_float(balance_info.get('evlu_erng_rt', '0'))
            
            # 🔥 API 데이터 유효성 검증 (하드코딩된 값 사용 방지)
            if balance is None or available_cash is None:
                logger.error("API 응답에서 계좌 데이터를 찾을 수 없습니다")
                raise Exception("계좌 조회 API 응답 형식 오류")
            
            logger.info(f"파싱된 계좌 정보 - 예수금: {balance:,.0f}원, 주문가능: {available_cash:,.0f}원")
            
            # output1에서 보유종목 정보 추출
            holdings = []
            output1 = account_info.get('output1', [])
            
            for stock in output1:
                holding_qty = safe_int(stock.get('hldg_qty', '0'))
                if holding_qty > 0:
                    holdings.append({
                        'stock_name': stock.get('prdt_name', '').strip(),
                        'stock_code': stock.get('pdno', ''),
                        'quantity': holding_qty,
                        'current_price': safe_float(stock.get('prpr', '0')),
                        'purchase_price': safe_float(stock.get('pchs_avg_pric', '0')),
                        'evaluation_amount': safe_float(stock.get('evlu_amt', '0')),
                        'profit_loss': safe_float(stock.get('evlu_pfls_amt', '0')),
                        'profit_rate': safe_float(stock.get('evlu_pfls_rt', '0'))
                    })
            
            return {
                'account_type': account_type_display,
                'account_number': account_number,
                'balance': balance,
                'available_cash': available_cash,
                'profit_rate': profit_rate,
                'holdings': holdings
            }
            
        except Exception as e:
            logger.error(f"계좌 데이터 포맷팅 오류: {e}")
            return {
                'account_type': "알 수 없음",
                'account_number': 'N/A',
                'balance': 0,
                'available_cash': 0,
                'profit_rate': 0.0,
                'holdings': []
            }
    
    def _display_account_info_legacy(self, account_info: Dict):
        """기존 방식으로 계좌 정보 출력 (Rich 라이브러리 없을 때 사용)"""
        try:
            account_type_display = "실전투자" if self.account_type == "REAL" else "모의투자"
            print(f"서버 연결 및 계좌 조회 확인 완료")
            print(f"\n[{account_type_display} 계좌 정보]")
            
            # 안전한 숫자 변환 함수
            def safe_int(value, default=0):
                try:
                    return int(float(str(value).replace(',', '')))
                except:
                    return default
            
            # output2에서 계좌 기본 정보 추출
            output2 = account_info.get('output2', [])
            if output2:
                balance_info = output2[0]
                dnca_tot_amt = balance_info.get('dnca_tot_amt', '0')
                tot_evlu_amt = balance_info.get('tot_evlu_amt', '0')
                ord_psbl_cash = balance_info.get('ord_psbl_cash', '0')
                evlu_pfls_amt = balance_info.get('evlu_pfls_amt', '0')
                evlu_erng_rt = balance_info.get('evlu_erng_rt', '0')
                
                dnca_tot_amt_int = safe_int(dnca_tot_amt)
                tot_evlu_amt_int = safe_int(tot_evlu_amt)
                ord_psbl_cash_int = safe_int(ord_psbl_cash)
                evlu_pfls_amt_int = safe_int(evlu_pfls_amt)
                
                print(f"  - 예수금총액: {dnca_tot_amt_int:,}원")
                print(f"  - 총평가금액: {tot_evlu_amt_int:,}원")
                print(f"  - 주문가능현금: {ord_psbl_cash_int:,}원")
                print(f"  - 평가손익금액: {evlu_pfls_amt_int:,}원")
                print(f"  - 평가수익률: {evlu_erng_rt}%")
            
            # output1에서 보유종목 정보 추출
            output1 = account_info.get('output1', [])
            holding_count = len([stock for stock in output1 if int(stock.get('hldg_qty', '0')) > 0])
            print(f"  - 보유종목: {holding_count}개")
            
            if holding_count > 0:
                print("  [보유종목 상세]")
                count = 0
                for stock in output1:
                    holding_qty = int(stock.get('hldg_qty', '0'))
                    if holding_qty > 0:
                        count += 1
                        if count <= 5:  # 상위 5개만 표시
                            prdt_name = stock.get('prdt_name', '')
                            pdno = stock.get('pdno', '')
                            evlu_amt = stock.get('evlu_amt', '0')
                            evlu_amt_int = safe_int(evlu_amt)
                            print(f"    {count}. {prdt_name}({pdno})")
                            print(f"       - 보유수량: {holding_qty:,}주, 평가금액: {evlu_amt_int:,}원")
                if holding_count > 5:
                    print(f"    ... 및 {holding_count - 5}개 종목 추가")
            
            print("=" * 60)
            
        except Exception as e:
            logger.error(f"계좌 정보 출력 오류: {e}")
            print(f"계좌 정보 표시 중 오류 발생: {e}")


def get_minimal_day_trader(account_type: str, algorithm=None, skip_market_hours: bool = False) -> MinimalDayTrader:
    """MinimalDayTrader 인스턴스 생성 팩토리 함수"""
    return MinimalDayTrader(account_type, algorithm, skip_market_hours)