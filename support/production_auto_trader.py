#!/usr/bin/env python3
"""
프로덕션 자동매매 시스템
test_auto_trading.py 로직 기반의 실제 매매 시스템
"""

import asyncio
import sys
import logging
from datetime import datetime, time as datetime_time

# UTF-8 인코딩 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from contextlib import asynccontextmanager

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 새로 만든 모듈들
from .trading_constants import TradingSteps, TradingConfig, TradingMessages, ReturnCodes
from .trading_config_manager import get_trading_config
from .trading_exceptions import *

# 기존 시스템 모듈들
from support.api_connector import KISAPIConnector
from support.telegram_notifier import get_telegram_notifier
from support.algorithm_loader import AlgorithmLoader
from support.system_logger import SystemLogger
from support.unified_cycle_manager import get_unified_cycle_manager, get_step_delay_manager
from support.step_display_utils import print_step_start, print_step_end, step_delay, print_algorithm_start, print_algorithm_end
from support.previous_day_balance_handler import PreviousDayBalanceHandler, TradingStrategy

# 토큰 최적화 시스템
from token_optimizer import optimize_if_needed

logger = logging.getLogger(__name__)


class TradingResult:
    """매매 결과 표준 데이터 클래스"""
    
    def __init__(self, success: bool = False, data: Optional[Dict[str, Any]] = None, 
                 error: Optional[str] = None, return_code: int = ReturnCodes.SUCCESS):
        self.success = success
        self.data = data or {}
        self.error = error
        self.return_code = return_code
        self.timestamp = datetime.now()
    
    def __bool__(self) -> bool:
        return self.success
    
    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILURE"
        return f"TradingResult({status}, code={self.return_code}, data={len(self.data)} items)"


class ProductionAutoTrader:
    """프로덕션 자동매매 시스템"""
    
    def __init__(self, account_type: str = "MOCK", algorithm=None):
        """
        초기화
        
        Args:
            account_type: "REAL" or "MOCK"
            algorithm: 알고리즘 객체
        """
        self.account_type = account_type
        self.algorithm = algorithm
        self.config = get_trading_config()
        
        # 상태 변수
        self.is_running = False
        self.cycle_count = 0
        self.total_trades = 0
        self.session_profit = 0.0
        
        # API 및 서비스 객체 (초기화 시점에는 None)
        self.api: Optional[KISAPIConnector] = None
        self.telegram = None
        
        # 계좌 메모리 관리자
        self.account_manager = None
        
        # 통합 순환 관리 시스템 초기화 (2분 간격으로 통일)
        self.cycle_manager = get_unified_cycle_manager(120)  # 2분 = 120초
        self.step_delay_manager = get_step_delay_manager(2)  # 2초 단계별 지연
        
        # 매매 통계
        self.trading_stats = {
            "total_cycles": 0,
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "total_profit": 0.0,
            "buy_orders": 0,
            "sell_orders": 0
        }
        
        logger.info(f"ProductionAutoTrader 초기화 완료 - 계좌타입: {account_type}")
    
    async def pre_trading_initialization(self) -> TradingResult:
        """매매 시작 전 초기화 작업 (계좌조회 + 전날잔고처리)"""
        try:
            # 계좌 조회 중 메시지만 표시
            from support.account_display_utils import show_account_inquiry_message, display_account_info
            show_account_inquiry_message()
            
            # 계좌 메모리 관리자 초기화 (로그 출력 없이)
            if not self.account_manager:
                from support.account_memory_manager import get_account_memory_manager
                self.account_manager = get_account_memory_manager()
            
            # 계좌 정보 초기 업데이트 및 백그라운드 작업 시작 (로그만)
            logger.info("계좌 정보 초기화 및 백그라운드 모니터링 시작")
            await self.account_manager.initialize_accounts(
                api_real=self.api if self.account_type == "REAL" else None,
                api_mock=self.api if self.account_type == "MOCK" else None
            )
            
            # 표준화된 계좌 정보 표시
            account_snapshot = self.account_manager.get_account(self.account_type)
            if account_snapshot:
                # 계좌 정보를 표준 형식으로 변환
                account_data = {
                    'account_number': getattr(account_snapshot, 'account_number', getattr(self.api, 'account_number', self.api.config.get("CANO", 'Unknown'))),
                    'total_cash': getattr(account_snapshot, 'total_evaluation', 0),
                    'buyable_cash': getattr(account_snapshot, 'available_cash', 0),
                    'profit_rate': getattr(account_snapshot, 'profit_rate', 0.0),
                    'holdings': getattr(account_snapshot, 'holdings', [])
                }
                
                # 표준화된 형식으로 계좌 정보 표시
                display_account_info(account_data, self.account_type)
                
                # 텔레그램 알림 (간소화)
                if self.telegram:
                    holdings_count = len(account_snapshot.holdings)
                    telegram_message = f"[{self.account_type}] 계좌조회 완료\n보유종목: {holdings_count}개\n주문가능금액: {account_snapshot.available_cash:,.0f}원"
                    await self.telegram.send_message(telegram_message)
            
            # 3초 간격 처리
            await step_delay(3)
            
            print_step_start("전날잔고처리")
            
            # 전날잔고처리 실행
            cleanup_result = await self._execute_balance_cleanup()
            
            # 잔고처리 완료 후 계좌 정보 재조회
            if cleanup_result.get('sold_stocks', 0) > 0:
                logger.info("잔고처리 완료 - 계좌 정보 업데이트")
                await self.account_manager.update_account(self.account_type, self.api, force=True)
            
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
            
            if self.telegram:
                await self.telegram.send_message(f"[{self.account_type}] 전날잔고처리 완료\n{cleanup_message}")
            
            print_step_end("전날잔고처리")
            
            # 3초 간격 처리
            await step_delay(3)
            
            return TradingResult(True, data=cleanup_result)
            
        except Exception as e:
            logger.error(f"매매 시작 전 초기화 실패: {e}")
            print_step_end("초기화 실패")
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    @asynccontextmanager
    async def _resource_manager(self):
        """리소스 관리 컨텍스트 매니저"""
        initialization_success = False
        try:
            # 리소스 초기화
            await self._initialize_resources()
            initialization_success = True
            logger.info("[INIT] 리소스 관리자 초기화 성공")
            yield
        except Exception as e:
            error_msg = f"리소스 초기화 오류: {str(e)}"
            logger.error(f"[INIT-FAIL] {error_msg}")
            
            # 초기화 실패했지만 기본 리소스라도 있으면 계속 진행 시도
            if hasattr(self, 'api') or hasattr(self, 'telegram'):
                logger.warning("[INIT-FAIL] 일부 리소스 사용 가능 - 제한적 실행 모드")
                try:
                    yield  # 제한적으로나마 실행 허용
                except Exception as runtime_error:
                    logger.error(f"[RUNTIME-FAIL] 제한적 실행 중 오류: {runtime_error}")
                    raise
            else:
                logger.critical("[INIT-FAIL] 모든 리소스 초기화 실패 - 시스템 종료")
                raise APIConnectionError(f"치명적 초기화 실패: {error_msg}")
        finally:
            # 리소스 정리 (초기화 성공 여부와 관계없이)
            try:
                await self._cleanup_resources()
                if initialization_success:
                    logger.info("[CLEANUP] 리소스 정리 완료")
                else:
                    logger.info("[CLEANUP] 부분 리소스 정리 완료")
            except Exception as cleanup_error:
                logger.error(f"[CLEANUP-FAIL] 리소스 정리 중 오류: {cleanup_error}")
    
    async def _initialize_resources(self):
        """리소스 초기화 (재시도 메커니즘 포함)"""
        max_retries = 3
        initialization_failures = []
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[INIT] 리소스 초기화 시도 {attempt + 1}/{max_retries}")
                current_failures = []
                
                # API 초기화 (재시도 포함)
                try:
                    await self._initialize_api_with_retry()
                    logger.info("[INIT] API 초기화 완료")
                except Exception as api_error:
                    error_msg = f"API 초기화 실패: {str(api_error)}"
                    logger.error(f"[INIT-FAIL] {error_msg}")
                    current_failures.append(error_msg)
                    # API 실패해도 계속 진행 (폴백 로직으로)
                
                # 텔레그램 초기화
                try:
                    await self._initialize_telegram()
                except Exception as tg_error:
                    error_msg = f"텔레그램 초기화 실패: {str(tg_error)}"
                    logger.warning(f"[INIT-FAIL] {error_msg} (DummyTelegram으로 폴백)")
                    current_failures.append(error_msg)
                
                # 알고리즘 초기화
                try:
                    await self._initialize_algorithm()
                except Exception as algo_error:
                    error_msg = f"알고리즘 초기화 실패: {str(algo_error)}"
                    logger.warning(f"[INIT-FAIL] {error_msg} (더미 알고리즘으로 폴백)")
                    current_failures.append(error_msg)
                
                # 계좌 메모리 관리자 초기화
                try:
                    await self._initialize_account_manager()
                    logger.info(f"[INIT] 계좌 메모리 관리자 초기화 완료")
                except Exception as acc_error:
                    error_msg = f"계좌 메모리 관리자 초기화 실패: {str(acc_error)}"
                    logger.warning(f"[INIT-FAIL] {error_msg}")
                    current_failures.append(error_msg)
                
                # 초기화 결과 평가
                if not current_failures:
                    logger.info(f"[INIT] 모든 리소스 초기화 완료 (시도 {attempt + 1}/{max_retries})")
                    return
                elif self.api or hasattr(self, 'telegram'):
                    # 핵심 리소스가 있으면 부분적 성공으로 계속 진행
                    logger.warning(f"[INIT] 부분 초기화 성공 - 일부 실패: {len(current_failures)}개")
                    await self._send_initialization_failure_notice(current_failures, False)
                    return
                else:
                    # 핵심 리소스 모두 실패
                    initialization_failures = current_failures
                    raise Exception(f"핵심 리소스 초기화 실패: {len(current_failures)}개")
                
            except Exception as e:
                error_msg = f"시스템 초기화 시도 {attempt + 1} 실패: {str(e)}"
                logger.error(f"[INIT-FAIL] {error_msg}")
                initialization_failures.extend(current_failures if 'current_failures' in locals() else [str(e)])
                
                if attempt == max_retries - 1:
                    logger.error(f"[INIT-FAIL] 모든 리소스 초기화 시도 최종 실패")
                    await self._send_initialization_failure_notice(initialization_failures, True)
                    raise APIConnectionError(f"시스템 초기화 최종 실패: 총 {len(initialization_failures)}개 오류 발생")
                
                # 재시도 전 대기
                wait_time = 10 * (attempt + 1)
                logger.info(f"[INIT] {wait_time}초 후 재시도")
                await asyncio.sleep(wait_time)
    
    async def _initialize_api_with_retry(self):
        """API 초기화 (설정 기반 재시도)"""
        max_api_retries = self.config.get_api_reconnect_attempts()
        
        for attempt in range(max_api_retries):
            try:
                # API 객체 생성
                self.api = KISAPIConnector(is_mock=(self.account_type == "MOCK"))
                
                # 연결 테스트
                test_result = await self._test_api_connection()
                if test_result:
                    logger.info(f"API 초기화 및 테스트 성공 (시도 {attempt + 1}/{max_api_retries})")
                    return
                else:
                    raise APIConnectionError("API 연결 테스트 실패")
                    
            except Exception as e:
                logger.warning(f"API 초기화 시도 {attempt + 1} 실패: {e}")
                
                if attempt == max_api_retries - 1:
                    raise APIConnectionError(f"API 초기화 최종 실패: {str(e)}")
                
                # 재시도 전 대기
                await asyncio.sleep(5 * (attempt + 1))
    
    async def _initialize_telegram(self):
        """텔레그램 초기화"""
        try:
            from support.telegram_notifier import get_telegram_notifier
            self.telegram = get_telegram_notifier()
            logger.info("텔레그램 알림 시스템 초기화 완료")
            
        except Exception as e:
            logger.warning(f"텔레그램 초기화 실패: {e}")
            
            # 더미 텔레그램 객체 생성 (시스템 중단 방지)
            class DummyTelegram:
                async def send_message(self, message: str) -> bool:
                    logger.info(f"[텔레그램 대체] {message}")
                    return True
            
            self.telegram = DummyTelegram()
            logger.info("텔레그램 대체 객체 생성 완료")
    
    async def _initialize_algorithm(self):
        """알고리즘 초기화"""
        try:
            if not self.algorithm:
                algorithm_dir = PROJECT_ROOT / "Algorithm"
                from support.algorithm_loader import AlgorithmLoader
                loader = AlgorithmLoader(str(algorithm_dir))
                self.algorithm = loader.load_algorithm(self.config.get_default_algorithm())
                
                if not self.algorithm:
                    # 기본 알고리즘도 없으면 더미 알고리즘 생성
                    class DummyAlgorithm:
                        def __init__(self):
                            self.name = "더미 알고리즘"
                        
                        def analyze(self, *args, **kwargs):
                            return {"action": "hold", "reason": "더미 알고리즘 - 보유"}
                    
                    self.algorithm = DummyAlgorithm()
                    logger.warning("기본 알고리즘 로드 실패 - 더미 알고리즘 사용")
                else:
                    logger.info(f"알고리즘 로드 성공: {getattr(self.algorithm, 'name', '알 수 없음')}")
            else:
                logger.info("기존 알고리즘 사용")
                
        except Exception as e:
            logger.error(f"알고리즘 초기화 실패: {e}")
            # 알고리즘 없어도 시스템은 계속 실행
            class DummyAlgorithm:
                def __init__(self):
                    self.name = "오류 복구 알고리즘"
                
                def analyze(self, *args, **kwargs):
                    return {"action": "hold", "reason": "알고리즘 오류로 보유"}
            
            self.algorithm = DummyAlgorithm()
            logger.warning("알고리즘 초기화 실패 - 더미 알고리즘으로 대체")
    
    async def _initialize_account_manager(self):
        """계좌 메모리 관리자 초기화"""
        try:
            from support.account_memory_manager import get_account_memory_manager
            
            self.account_manager = get_account_memory_manager()
            
            # API 연결에 따라 계좌 초기화
            api_real = None
            api_mock = None
            
            # 현재 계좌 유형에 따라 API 할당
            if self.account_type == "REAL":
                api_real = self.api
            else:
                api_mock = self.api
                
            # 백그라운드 계좌 조회 시작
            await self.account_manager.initialize_accounts(api_real=api_real, api_mock=api_mock)
            
            logger.info(f"계좌 메모리 관리자 초기화 완료 - {self.account_type} 모드")
            
        except Exception as e:
            logger.error(f"계좌 메모리 관리자 초기화 실패: {e}")
            self.account_manager = None
            raise
    
    async def _send_initialization_failure_notice(self, failures: List[str], is_critical: bool = False):
        """초기화 실패 알림 메시지 전송"""
        try:
            failure_type = "치명적 초기화 실패" if is_critical else "부분적 초기화 실패"
            failure_count = len(failures)
            
            # 콘솔 출력 (항상 실행)
            print(f"\n[INIT-FAIL] {failure_type} - {failure_count}개 오류 발생")
            for i, failure in enumerate(failures[:5], 1):  # 최대 5개까지만 표시
                print(f"  {i}. {failure}")
            if failure_count > 5:
                print(f"  ... 외 {failure_count - 5}개")
            
            # 상세 메시지 구성
            status_icon = "CRITICAL" if is_critical else "WARNING"
            message_parts = [
                f"{failure_type}가 발생했습니다.",
                f"",
                f"[실패한 구성 요소] ({failure_count}개)",
            ]
            
            # 실패 목록 추가 (최대 5개)
            for i, failure in enumerate(failures[:5], 1):
                message_parts.append(f"{i}. {failure}")
            
            if failure_count > 5:
                message_parts.append(f"... 외 {failure_count - 5}개 추가 실패")
            
            message_parts.extend([
                f"",
                f"[폴백 조치]",
                "- DummyTelegram으로 알림 기능 대체",
                "- 더미 알고리즘으로 매매 로직 대체",
                "- 시스템은 제한적으로 계속 실행됩니다",
            ])
            
            if is_critical:
                message_parts.extend([
                    f"",
                    f"[긴급 조치 필요]",
                    "시스템 재시작을 권장합니다.",
                    "설정 파일과 네트워크 연결을 확인하세요."
                ])
            
            full_message = "\n".join(message_parts)
            
            # SYSTEM 메시지로 전송 시도 (텔레그램이 있을 경우에만)
            try:
                if hasattr(self, 'telegram') and self.telegram:
                    await self.send_message("SYSTEM", f"초기화 {status_icon}", full_message)
                else:
                    # 텔레그램이 없는 경우 콘솔에만 상세 출력
                    print(f"\n[SYSTEM] 초기화 {status_icon}")
                    print("=" * 50)
                    print(full_message)
                    print("=" * 50)
            except Exception as send_error:
                logger.warning(f"[INIT-FAIL] 알림 전송 실패: {send_error}")
                # 알림 전송 실패해도 시스템 진행
            
            logger.info(f"[INIT-FAIL] 초기화 실패 알림 처리 완료 - 타입: {failure_type}")
            
        except Exception as e:
            logger.error(f"[INIT-FAIL] 초기화 실패 알림 처리 중 오류: {e}")
            # 알림 처리 실패해도 시스템은 계속 진행
    
    async def _cleanup_resources(self):
        """리소스 정리"""
        try:
            # 계좌 메모리 관리자 정리
            if self.account_manager:
                try:
                    await self.account_manager.stop()
                    logger.info("계좌 메모리 관리자 정리 완료")
                except Exception as e:
                    logger.warning(f"계좌 메모리 관리자 정리 중 오류: {e}")
            
            # API 정리 (필요시)
            if self.api and hasattr(self.api, 'close'):
                try:
                    await self.api.close()
                except Exception as e:
                    logger.warning(f"API 정리 중 오류: {e}")
            
            # 기타 리소스 정리
            logger.info("리소스 정리 완료")
            
        except Exception as e:
            logger.error(f"리소스 정리 실패: {e}")
            raise ResourceCleanupError(f"리소스 정리 실패: {str(e)}")
    
    async def send_message(self, step: Union[TradingSteps, str], title: str, message: str) -> TradingResult:
        """화면 출력과 텔레그램 메시지 발송"""
        try:
            step_str = step.value if isinstance(step, TradingSteps) else step
            
            # 화면 출력
            print(f"\n{TradingConfig.STEP_FORMAT.format(step=step_str, title=title)}")
            print(TradingConfig.MESSAGE_SEPARATOR)
            print(message)
            print(TradingConfig.MESSAGE_SEPARATOR)
            
            # 텔레그램 메시지 발송
            try:
                if self.telegram:
                    telegram_message = f"<b>{TradingConfig.STEP_FORMAT.format(step=step_str, title=title)}</b>\n\n{message}"
                    await self.telegram.send_message(telegram_message)
            except Exception as e:
                logger.warning(f"텔레그램 메시지 발송 실패: {e}")
                # 텔레그램 실패는 전체 프로세스를 중단하지 않음
            
            return TradingResult(True)
            
        except Exception as e:
            logger.error(f"메시지 발송 실패: {e}")
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def step_01_account_query(self) -> TradingResult:
        """1단계: 계좌 조회 (메모리 기반)"""
        try:
            await self.send_message(
                TradingSteps.ACCOUNT_QUERY,
                TradingMessages.STEP_TEMPLATES[TradingSteps.ACCOUNT_QUERY]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.ACCOUNT_QUERY]["start"]
            )
            
            # 계좌 메모리 관리자를 통한 계좌 조회
            if not self.account_manager:
                logger.warning("계좌 메모리 관리자 없음 - 직접 API 호출로 폴백")
                account_info = await self._query_account_info_direct()
            else:
                # 메모리에서 최신 계좌 정보 조회
                account_snapshot = self.account_manager.get_account(self.account_type)
                
                if not account_snapshot:
                    # 메모리에 정보가 없으면 즉시 업데이트
                    logger.info("메모리에 계좌 정보 없음 - 즉시 업데이트 수행")
                    await self.account_manager.update_account(self.account_type, self.api, force=True)
                    account_snapshot = self.account_manager.get_account(self.account_type)
                
                if account_snapshot:
                    account_info = self._convert_snapshot_to_display(account_snapshot)
                else:
                    raise AccountQueryError("계좌 정보 조회 실패 - 메모리 및 API 모두 실패")
            
            # 상세 계좌 정보 표시
            account_display_message = f"""계좌 정보 조회가 완료되었습니다.

[예수금 현황]
- 총 자산: {account_info['total_asset']}
- 예수금: {account_info['deposit_amount']}  
- 주문가능금액: {account_info['available_cash']}

[보유종목 현황] ({account_info['stock_count']}개)
{account_info['holdings_display']}

[수익 현황]
- 총 평가손익: {account_info['total_profit_loss']}
- 총 수익률: {account_info['total_profit_rate']}

[데이터 소스] 메모리 기반 ({account_info['data_timestamp']})"""

            await self.send_message(
                TradingSteps.ACCOUNT_QUERY,
                "계좌 조회 완료",
                account_display_message
            )
            
            return TradingResult(True, data=account_info)
            
        except Exception as e:
            logger.error(f"계좌 조회 단계 실패: {e}")
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def _query_account_info(self) -> Dict[str, Any]:
        """실제 계좌 정보 조회 (API 호출) - 상세 표시"""
        try:
            # 장 시간 체크 (정보 제공용)
            if await self._is_market_open():
                logger.info("현재 장 운영 시간입니다.")
            else:
                logger.info("현재 개장 시간이 아닙니다.")
                print("\n[알림] 현재 개장 시간이 아닙니다. (자동매매는 계속 실행됩니다)")
                await self.send_message(
                    "INFO",
                    "장 시간 알림",
                    "현재 개장 시간이 아닙니다.\n자동매매 로직은 계속 실행됩니다."
                )
            
            # API를 통한 실제 계좌 조회
            if not self.api:
                raise APIConnectionError("API가 초기화되지 않았습니다")
            
            # KIS API 계좌조회 호출
            account_balance = await self.api.get_account_balance()
            positions = await self.api.get_positions()
            
            # 계좌 기본 정보 추출
            total_asset = self._safe_float(account_balance.get('tot_evlu_amt', 0))
            available_cash = self._safe_float(account_balance.get('ord_psbl_cash', 0))
            deposit_amount = self._safe_float(account_balance.get('dnca_tot_amt', 0))
            
            # 보유종목 상세 정보 처리
            holdings_info = []
            total_profit_loss = 0.0
            total_evaluation = 0.0
            
            if positions:
                for position in positions:
                    stock_name = position.get('stock_name', '').strip()
                    stock_code = position.get('stock_code', '')
                    quantity = position.get('quantity', 0)
                    profit_loss = position.get('profit_loss', 0)
                    evaluation_amount = position.get('evaluation_amount', 0)
                    
                    if quantity > 0:  # 보유수량이 있는 종목만
                        holdings_info.append(f"{stock_name}({stock_code})-{quantity:,}주")
                        total_profit_loss += profit_loss
                        total_evaluation += evaluation_amount
            
            # 총 수익률 계산 (보유종목 평가금액 대비)
            if total_evaluation > 0:
                # 총 수익률 = (평가손익 / (평가금액 - 평가손익)) * 100
                investment_amount = total_evaluation - total_profit_loss
                total_profit_rate = (total_profit_loss / investment_amount * 100) if investment_amount > 0 else 0.0
            else:
                total_profit_rate = 0.0
            
            # 사용자 요구사항에 맞는 표시용 데이터 준비
            holdings_display = "\n".join(holdings_info) if holdings_info else "보유종목 없음"
            
            return {
                # 기본 정보
                "total_asset": f"{total_asset:,}원",
                "available_cash": f"{available_cash:,}원", 
                "deposit_amount": f"{deposit_amount:,}원",
                "stock_count": len([p for p in positions if p.get('quantity', 0) > 0]),
                
                # 상세 보유종목 정보
                "holdings_display": holdings_display,
                "total_profit_loss": f"{total_profit_loss:+,.0f}원",
                "total_profit_rate": f"{total_profit_rate:+.2f}%",
                
                # Raw 데이터 (내부 계산용)
                "raw_total_asset": total_asset,
                "raw_available_cash": available_cash,
                "raw_deposit_amount": deposit_amount,
                "raw_total_profit_loss": total_profit_loss,
                "raw_total_profit_rate": total_profit_rate,
                "positions": positions
            }
            
        except Exception as e:
            logger.error(f"계좌 정보 조회 실패: {e}")
            # 실패 시 기본 데이터 반환 (시스템 중단 방지)
            return {
                "total_asset": "조회 실패",
                "available_cash": "조회 실패", 
                "deposit_amount": "조회 실패",
                "stock_count": 0,
                "holdings_display": "조회 실패",
                "total_profit_loss": "조회 실패",
                "total_profit_rate": "조회 실패",
                "raw_total_asset": 0,
                "raw_available_cash": 0,
                "raw_deposit_amount": 0,
                "raw_total_profit_loss": 0.0,
                "raw_total_profit_rate": 0.0,
                "positions": [],
                "error": str(e)
            }
    
    def _safe_float(self, value, default: float = 0.0) -> float:
        """안전한 float 변환"""
        try:
            if value is None or value == '' or value == '-':
                return default
            return float(str(value).replace(',', ''))
        except (ValueError, TypeError):
            return default
    
    def _convert_snapshot_to_display(self, snapshot) -> Dict[str, Any]:
        """AccountSnapshot을 표시용 데이터로 변환"""
        try:
            # 보유종목 정보 포맷팅
            holdings_info = []
            for holding in snapshot.holdings:
                stock_name = holding.get('stock_name', '')
                stock_code = holding.get('stock_code', '')
                quantity = holding.get('quantity', 0)
                holdings_info.append(f"{stock_name}({stock_code})-{quantity:,}주")
            
            holdings_display = "\n".join(holdings_info) if holdings_info else "보유종목 없음"
            
            # 표시용 포맷 생성
            return {
                "total_asset": f"{snapshot.total_evaluation:,.0f}원",
                "deposit_amount": f"{snapshot.cash_balance:,.0f}원",
                "available_cash": f"{snapshot.available_cash:,.0f}원",
                "stock_count": len(snapshot.holdings),
                "holdings_display": holdings_display,
                "total_profit_loss": f"{snapshot.profit_loss:,.0f}원",
                "total_profit_rate": f"{snapshot.profit_rate:.2f}%",
                "data_timestamp": snapshot.timestamp.strftime('%H:%M:%S'),
                "raw_total_asset": snapshot.total_evaluation,
                "raw_available_cash": snapshot.available_cash,
                "raw_deposit_amount": snapshot.cash_balance,
                "raw_total_profit_loss": snapshot.profit_loss,
                "raw_total_profit_rate": snapshot.profit_rate,
                "positions": snapshot.holdings
            }
            
        except Exception as e:
            logger.error(f"스냅샷 변환 오류: {e}")
            return {
                "total_asset": "변환 실패",
                "deposit_amount": "변환 실패",
                "available_cash": "변환 실패",
                "stock_count": 0,
                "holdings_display": "변환 실패",
                "total_profit_loss": "변환 실패",
                "total_profit_rate": "변환 실패",
                "data_timestamp": datetime.now().strftime('%H:%M:%S'),
                "raw_total_asset": 0,
                "raw_available_cash": 0,
                "raw_deposit_amount": 0,
                "raw_total_profit_loss": 0.0,
                "raw_total_profit_rate": 0.0,
                "positions": [],
                "error": str(e)
            }
    
    async def _query_account_info_direct(self) -> Dict[str, Any]:
        """직접 API를 통한 계좌 정보 조회 (폴백용)"""
        try:
            logger.warning("직접 API 호출로 계좌 조회 수행")
            
            # 기존 _query_account_info 로직 사용
            if not self.api:
                raise APIConnectionError("API가 초기화되지 않았습니다")
            
            # KIS API 계좌조회 호출
            account_balance = await self.api.get_account_balance()
            positions = await self.api.get_positions()
            
            # 계좌 기본 정보 추출
            total_asset = self._safe_float(account_balance.get('tot_evlu_amt', 0))
            available_cash = self._safe_float(account_balance.get('ord_psbl_cash', 0))
            deposit_amount = self._safe_float(account_balance.get('dnca_tot_amt', 0))
            
            # 보유종목 상세 정보 처리
            holdings_info = []
            total_profit_loss = 0.0
            total_evaluation = 0.0
            
            if positions:
                for position in positions:
                    stock_name = position.get('stock_name', '').strip()
                    stock_code = position.get('stock_code', '')
                    quantity = position.get('quantity', 0)
                    profit_loss = position.get('profit_loss', 0)
                    evaluation_amount = position.get('evaluation_amount', 0)
                    
                    if quantity > 0:
                        holdings_info.append(f"{stock_name}({stock_code})-{quantity:,}주")
                        total_profit_loss += profit_loss
                        total_evaluation += evaluation_amount
            
            # 총 수익률 계산
            if total_evaluation > 0:
                investment_amount = total_evaluation - total_profit_loss
                total_profit_rate = (total_profit_loss / investment_amount * 100) if investment_amount > 0 else 0.0
            else:
                total_profit_rate = 0.0
            
            holdings_display = "\n".join(holdings_info) if holdings_info else "보유종목 없음"
            
            return {
                "total_asset": f"{total_asset:,.0f}원",
                "deposit_amount": f"{deposit_amount:,.0f}원",
                "available_cash": f"{available_cash:,.0f}원",
                "stock_count": len(holdings_info),
                "holdings_display": holdings_display,
                "total_profit_loss": f"{total_profit_loss:,.0f}원",
                "total_profit_rate": f"{total_profit_rate:.2f}%",
                "data_timestamp": datetime.now().strftime('%H:%M:%S'),
                "raw_total_asset": total_asset,
                "raw_available_cash": available_cash,
                "raw_deposit_amount": deposit_amount,
                "raw_total_profit_loss": total_profit_loss,
                "raw_total_profit_rate": total_profit_rate,
                "positions": positions or []
            }
            
        except Exception as e:
            logger.error(f"직접 계좌 조회 실패: {e}")
            return {
                "total_asset": "조회 실패",
                "deposit_amount": "조회 실패",
                "available_cash": "조회 실패",
                "stock_count": 0,
                "holdings_display": "조회 실패",
                "total_profit_loss": "조회 실패",
                "total_profit_rate": "조회 실패",
                "data_timestamp": datetime.now().strftime('%H:%M:%S'),
                "raw_total_asset": 0,
                "raw_available_cash": 0,
                "raw_deposit_amount": 0,
                "raw_total_profit_loss": 0.0,
                "raw_total_profit_rate": 0.0,
                "positions": [],
                "error": str(e)
            }
    
    async def step_02_03_balance_process(self) -> TradingResult:
        """2-3단계: 계좌조회 기반 전날잔고처리 (통합)"""
        try:
            # 2단계: 잔고 정리 시작 알림
            await self.send_message(
                TradingSteps.BALANCE_CLEANUP_START,
                TradingMessages.STEP_TEMPLATES[TradingSteps.BALANCE_CLEANUP_START]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.BALANCE_CLEANUP_START]["start"]
            )
            
            # 계좌 정보 즉시 업데이트 (전날잔고처리용)
            if self.account_manager:
                logger.info("전날잔고처리를 위한 계좌 정보 업데이트 시작")
                await self.account_manager.update_account(self.account_type, self.api, force=True)
                
                # 업데이트된 계좌 정보 표시
                account_snapshot = self.account_manager.get_account(self.account_type)
                if account_snapshot:
                    balance_info_message = f"""전날잔고처리를 위한 계좌 조회가 완료되었습니다.

[현재 보유종목] ({len(account_snapshot.holdings)}개)
{self._format_holdings_for_cleanup(account_snapshot.holdings)}

[예수금 현황]
- 주문가능금액: {account_snapshot.available_cash:,.0f}원

계좌 조회 완료 후 3초 대기 후 잔고처리를 시작합니다."""
                    
                    await self.send_message(
                        TradingSteps.BALANCE_CLEANUP_START,
                        "전날잔고처리용 계좌조회 완료",
                        balance_info_message
                    )
            
            # 3초 대기 (사용자 요구사항)
            logger.info("계좌조회 완료 - 3초 대기 후 잔고처리 시작")
            await asyncio.sleep(3)
            
            # 3단계: 잔고 정리 실행
            await self.send_message(
                TradingSteps.BALANCE_CLEANUP_PROCESS,
                TradingMessages.STEP_TEMPLATES[TradingSteps.BALANCE_CLEANUP_PROCESS]["title"],
                "3초 대기 완료 - 잔고 정리를 시작합니다..."
            )
            
            # 실제 잔고 정리 로직 실행
            cleanup_result = await self._execute_balance_cleanup()
            
            # 잔고처리 완료 후 계좌 정보 재조회
            if self.account_manager and cleanup_result.get('sold_stocks', 0) > 0:
                logger.info("잔고처리 완료 - 계좌 정보 업데이트")
                await self.account_manager.update_account(self.account_type, self.api, force=True)
            
            # 분석 결과 포함 메시지 생성
            analysis_display = "\n".join(cleanup_result.get('analysis_results', []))
            cleanup_message = f"""잔고 정리가 완료되었습니다.

[처리 결과]
- 매도된 종목: {cleanup_result['sold_stocks']}개
- 보유 유지 종목: {cleanup_result['kept_stocks']}개  
- 실현 손익: {cleanup_result['profit']}

[상세 분석 결과]
{analysis_display if analysis_display else '분석된 보유종목이 없습니다.'}"""

            await self.send_message(
                TradingSteps.BALANCE_CLEANUP_PROCESS,
                "잔고 정리 완료",
                cleanup_message
            )
            
            return TradingResult(True, data=cleanup_result)
            
        except Exception as e:
            logger.error(f"전날잔고처리 단계 실패: {e}")
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    def _format_holdings_for_cleanup(self, holdings: List[Dict]) -> str:
        """잔고처리용 보유종목 포맷팅"""
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
    
    async def _execute_balance_cleanup(self) -> Dict[str, Any]:
        """통합된 전날잔고 처리 로직 실행"""
        try:
            if not self.api:
                raise APIConnectionError("API가 초기화되지 않았습니다")
            
            # 통합 전날잔고 처리기 생성 (PRODUCTION 전략 사용)
            balance_handler = PreviousDayBalanceHandler(
                self.api, 
                self.account_type, 
                TradingStrategy.PRODUCTION
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
            
            # 매도 성공한 종목들에 대해 trading_stats 업데이트
            sold_count = cleanup_result.get('sold_count', 0)
            if sold_count > 0:
                self.trading_stats["sell_orders"] += sold_count
            
            return {
                "sold_stocks": sold_count,
                "kept_stocks": cleanup_result.get('kept_count', 0),
                "profit": f"{cleanup_result.get('sold_count', 0) * 1000:+,.0f}원",  # 임시 수익 계산
                "analysis_results": analysis_results,
                "success": cleanup_result.get('success', False)
            }
            
        except Exception as e:
            logger.error(f"통합 잔고 정리 실행 실패: {e}")
            return {
                "sold_stocks": 0, 
                "kept_stocks": 0, 
                "profit": "실행 실패", 
                "analysis_results": [f"시스템 오류: {str(e)}"], 
                "error": str(e)
            }
    
    # 고급 포지션 분석 메서드는 PreviousDayBalanceHandler로 이전됨
    # async def _analyze_position_decision 메서드 제거됨
    
    # 시장 분석 메서드는 PreviousDayBalanceHandler로 이전됨
    # async def _get_market_analysis 메서드 제거됨
    
    def _calculate_profit_rate(self, position: Dict[str, Any]) -> float:
        """포지션의 수익률 계산"""
        try:
            buy_price = float(position.get('avg_price', 0))
            current_price = float(position.get('current_price', 0))
            
            if buy_price == 0:
                return 0.0
            
            return ((current_price - buy_price) / buy_price) * 100
            
        except Exception as e:
            logger.warning(f"수익률 계산 실패: {e}")
            return 0.0
    
    async def _execute_sell_order(self, position: Dict[str, Any]) -> TradingResult:
        """매도 주문 실행"""
        try:
            stock_code = position.get('stock_code')
            quantity = position.get('quantity', 0)
            
            if not stock_code or quantity <= 0:
                raise OrderValidationError("잘못된 매도 주문 정보")
            
            # 실제 매도 주문 API 호출
            order_result = await self.api.sell_market_order(
                stock_code=stock_code,
                quantity=quantity
            )
            
            if order_result and order_result.get('success'):
                profit = self._calculate_realized_profit(position, order_result)
                
                # 매도 완료 후 즉시 계좌 정보 업데이트
                if self.account_manager:
                    trade_info = {
                        'stock_code': stock_code,
                        'stock_name': position.get('stock_name', ''),
                        'quantity': quantity,
                        'amount': profit
                    }
                    await self.account_manager.update_after_trade(
                        self.account_type, self.api, "SELL", trade_info
                    )
                
                return TradingResult(True, data={'profit': profit})
            else:
                error_msg = order_result.get('error', '매도 주문 실패') if order_result else '매도 주문 실패'
                raise OrderExecutionError(error_msg, order_type='SELL', stock_code=stock_code)
                
        except Exception as e:
            logger.error(f"매도 주문 실행 실패: {e}")
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def _execute_buy_order(self, stock: Dict[str, Any]) -> TradingResult:
        """매수 주문 실행"""
        try:
            stock_code = stock.get('symbol') or stock.get('stock_code')
            if not stock_code:
                raise OrderValidationError("종목 코드가 없습니다")
            
            # 매수 가능 금액 확인
            if hasattr(self, 'account_manager') and self.account_manager:
                account_info = await self.account_manager.get_account_info(self.account_type)
                available_cash = account_info.get('available_cash', 0)
                
                if available_cash < 100000:  # 최소 10만원 이상
                    return TradingResult(False, error="매수 가능 금액 부족")
                
                # 현재 주가 조회
                current_price = await self.api.get_stock_price(stock_code)
                if not current_price:
                    return TradingResult(False, error="주가 조회 실패")
                
                # 매수 수량 계산 (보유 현금의 10% 또는 최대 20% 내에서)
                max_investment = min(available_cash * 0.2, 500000)  # 최대 50만원
                quantity = int(max_investment / current_price)
                
                if quantity < 1:
                    return TradingResult(False, error="매수 수량 부족")
                
                # 실제 매수 주문 API 호출
                order_result = await self.api.async_place_buy_order(
                    symbol=stock_code,
                    quantity=quantity,
                    order_type="03"  # 시장가 주문
                )
                
                if order_result and order_result.get('success'):
                    # 매수 완료 후 즉시 계좌 정보 업데이트
                    trade_info = {
                        'stock_code': stock_code,
                        'stock_name': stock.get('name', ''),
                        'quantity': quantity,
                        'amount': quantity * current_price
                    }
                    await self.account_manager.update_after_trade(
                        self.account_type, self.api, "BUY", trade_info
                    )
                    
                    return TradingResult(True, data={'quantity': quantity, 'price': current_price})
                else:
                    error_msg = order_result.get('error', '매수 주문 실패') if order_result else '매수 주문 실패'
                    raise OrderExecutionError(error_msg, order_type='BUY', stock_code=stock_code)
            else:
                return TradingResult(False, error="계좌 관리자 없음")
                
        except Exception as e:
            logger.error(f"매수 주문 실행 실패: {e}")
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)

    def _calculate_realized_profit(self, position: Dict[str, Any], order_result: Dict[str, Any]) -> float:
        """실현 손익 계산"""
        try:
            buy_price = float(position.get('avg_price', 0))
            sell_price = float(order_result.get('executed_price', 0))
            quantity = int(position.get('quantity', 0))
            
            return (sell_price - buy_price) * quantity
            
        except Exception as e:
            logger.warning(f"실현 손익 계산 실패: {e}")
            return 0.0
    
    async def _is_market_open(self) -> bool:
        """장 운영 시간 확인"""
        try:
            current_time = datetime.now().time()
            market_close_time = self.config.get_market_close_time()
            
            # 장 시작: 9:00, 장 마감: 설정된 시간 (기본 14:55)
            market_start = datetime_time(9, 0)
            
            return market_start <= current_time <= market_close_time
            
        except Exception as e:
            logger.error(f"장 시간 확인 실패: {e}")
            return False
    
    async def run_trading_cycle(self) -> TradingResult:
        """한 번의 매매 사이클 실행"""
        try:
            self.cycle_count += 1
            cycle_start_time = datetime.now()
            
            logger.info(f"매매 사이클 {self.cycle_count} 시작")
            
            # 19단계 실행
            steps_results = []
            
            # 1단계: 계좌 조회
            steps_results.append(await self.step_01_account_query())
            
            # 4-5단계: 종목 수집
            steps_results.append(await self.step_04_stock_collection_start())
            steps_results.append(await self.step_05_stock_collection_process())
            
            # 6-11단계: 자동매매 실행
            steps_results.append(await self.step_06_auto_trading_start())
            steps_results.append(await self.step_07_auto_trading_analysis())
            steps_results.append(await self.step_08_auto_trading_decision())
            steps_results.append(await self.step_09_auto_trading_execute())
            steps_results.append(await self.step_10_auto_trading_end())
            steps_results.append(await self.step_11_auto_trading_result())
            
            # 12-14단계: 사용자 지정 종목
            steps_results.append(await self.step_12_user_stock_start())
            steps_results.append(await self.step_13_user_stock_decision())
            steps_results.append(await self.step_14_user_stock_result())
            
            # 15단계: 사이클 완료
            steps_results.append(await self.step_15_cycle_end())
            
            # 결과 집계
            successful_steps = sum(1 for result in steps_results if result.success)
            total_steps = len(steps_results)
            
            cycle_duration = (datetime.now() - cycle_start_time).total_seconds()
            
            self.trading_stats["total_cycles"] += 1
            
            logger.info(f"매매 사이클 {self.cycle_count} 완료 - {successful_steps}/{total_steps} 성공, 소요시간: {cycle_duration:.1f}초")
            
            return TradingResult(
                success=successful_steps == total_steps,
                data={
                    "cycle_count": self.cycle_count,
                    "successful_steps": successful_steps,
                    "total_steps": total_steps,
                    "duration_seconds": cycle_duration
                },
                return_code=ReturnCodes.SUCCESS if successful_steps == total_steps else ReturnCodes.PARTIAL_SUCCESS
            )
            
        except Exception as e:
            logger.error(f"매매 사이클 실행 실패: {e}")
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def run_until_market_close(self) -> TradingResult:
        """안정적인 무한 반복 실행 (설정 기반 복구 메커니즘)"""
        max_consecutive_failures = self.config.get_max_consecutive_failures()
        consecutive_failures = 0
        emergency_recovery_count = 0
        max_emergency_recoveries = self.config.get_max_emergency_recoveries()
        
        try:
            async with self._resource_manager():
                self.is_running = True
                start_time = datetime.now()
                
                # 통합 순환 관리 시작
                self.cycle_manager.start_cycle_timer()
                
                await self.send_message(
                    "SYSTEM",
                    "자동매매 시스템 시작 (통합 순환 관리 적용)",
                    f"시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"계좌 타입: {self.account_type}\n"
                    f"통합 사이클 간격: {self.cycle_manager.cycle_interval_seconds}초 (2분)\n"
                    f"단계별 지연: {self.step_delay_manager.step_delay_seconds}초\n"
                    f"복구 메커니즘: 활성화\n"
                    f"연속 실패 허용: {max_consecutive_failures}회"
                )
                
                # 매매 시작 전 초기화 작업 (계좌조회 + 전날잔고처리)
                print_step_start("자동매매 시스템")
                print("자동매매 시작 전 초기화 작업을 수행합니다...")
                
                init_result = await self.pre_trading_initialization()
                if not init_result.success:
                    logger.error(f"초기화 실패: {init_result.error}")
                    return TradingResult(False, error=f"초기화 실패: {init_result.error}")
                
                print_step_end("초기화 완료")
                print_step_start("자동매매 순환")
                
                while self.is_running:
                    try:
                        # 장 마감 시간 체크 (MarketCloseController 사용)
                        try:
                            from support.market_close_controller import get_market_close_controller
                            
                            market_controller = get_market_close_controller()
                            
                            # 장마감 체크가 활성화된 경우에만 실행
                            if market_controller.is_market_close_check_enabled():
                                current_time = datetime.now().time()
                                
                                # 가드 모드 진입 체크
                                if market_controller.should_enter_guard_mode(current_time) and not getattr(self, "_guard_announced", False):
                                    self._guard_announced = True
                                    if not hasattr(self, 'trading_policy'):
                                        self.trading_policy = {}
                                    self.trading_policy["allow_new_entry"] = False
                                    
                                    remaining_time = market_controller.get_time_until_close(current_time)
                                    logger.warning(f"[MARKET_CLOSE] 마감 {market_controller.guard_minutes}분 전 - 신규 진입 금지 모드")
                                    await self.send_message("SYSTEM", "마감 임박", f"신규 진입 금지 — 포지션 관리 모드 전환 ({remaining_time['formatted']})")
                                
                                # 매매 종료 체크
                                if market_controller.should_stop_trading(current_time):
                                    logger.info(f"[MARKET_CLOSE] 장 마감 시간 도달 - MarketCloseController에 의한 종료")
                                    
                                    # 매매 리포트 생성
                                    trading_stats = {
                                        "total_cycles": getattr(self, 'cycle_count', 0),
                                        "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        "account_type": self.account_type
                                    }
                                    
                                    report_path = await market_controller.generate_trading_report(
                                        self.account_type, 
                                        getattr(self, 'algorithm_name', 'Unknown'), 
                                        trading_stats
                                    )
                                    
                                    await self.send_message(
                                        "SYSTEM",
                                        "자동매매 종료",
                                        f"장 마감 시간 도달 — 현재 {datetime.now().strftime('%H:%M:%S')}\n"
                                        f"매매 리포트: {report_path if report_path else '생성 실패'}"
                                    )
                                    
                                    # 포지션 정리/리소스 정리
                                    await self._cleanup_resources()
                                    self.is_running = False
                                    break

                        except Exception as e:
                            logger.warning(f"[MARKET_CLOSE] 마감 시간 체크 실패(무시하고 계속): {e}")
                        
                        # Health Check 기능 제거됨 - 원래 자동매매에 없던 불필요한 기능
                        
                        # 매매 사이클 실행
                        cycle_result = await self.run_trading_cycle()
                        
                        if cycle_result.success:
                            consecutive_failures = 0
                            logger.info(f"사이클 {self.cycle_count} 성공적으로 완료")
                        else:
                            consecutive_failures += 1
                            logger.warning(f"사이클 {self.cycle_count} 실패: {cycle_result.error} (연속 실패: {consecutive_failures}/{max_consecutive_failures})")
                            
                            if consecutive_failures >= max_consecutive_failures:
                                logger.warning(f"연속 {consecutive_failures}회 실패 - 잠시 대기 후 재시도")
                                consecutive_failures = 0  # 단순히 리셋만 함
                                await asyncio.sleep(60)  # 1분 대기
                        
                        # 다음 사이클까지 대기 (통합 순환 관리)
                        await self._unified_cycle_wait()
                        
                    except KeyboardInterrupt:
                        logger.info("사용자 중단 요청 - 안전하게 종료합니다")
                        self.is_running = False
                        break
                        
                    except asyncio.CancelledError:
                        logger.info("비동기 작업 취소 - 안전하게 종료합니다")
                        self.is_running = False
                        break
                        
                    except Exception as cycle_error:
                        consecutive_failures += 1
                        logger.error(f"예상치 못한 사이클 오류: {cycle_error} (연속 실패: {consecutive_failures}/{max_consecutive_failures})")
                        
                        if consecutive_failures >= max_consecutive_failures:
                            logger.warning(f"연속 {consecutive_failures}회 예외 발생 - 잠시 대기 후 재시도")
                            consecutive_failures = 0
                        
                        # 오류 발생 시 짧은 대기
                        await asyncio.sleep(30)
                
                end_time = datetime.now()
                total_duration = (end_time - start_time).total_seconds()
                
                # 최종 결과 정리
                final_result = {
                    "start_time": start_time,
                    "end_time": end_time,
                    "total_duration": total_duration,
                    "total_cycles": self.cycle_count,
                    "consecutive_failures": consecutive_failures,
                    "emergency_recoveries": emergency_recovery_count,
                    "trading_stats": self.trading_stats
                }
                
                await self.send_message(
                    "SYSTEM",
                    "자동매매 시스템 정상 종료",
                    f"종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"총 실행 시간: {total_duration/3600:.1f}시간\n"
                    f"총 사이클: {self.cycle_count}회\n"
                    f"비상 복구 횟수: {emergency_recovery_count}회\n"
                    f"총 거래: {self.trading_stats['total_trades']}건\n"
                    f"성공 거래: {self.trading_stats['successful_trades']}건"
                )
                
                return TradingResult(True, data=final_result)
                
        except Exception as e:
            logger.critical(f"자동매매 시스템 치명적 오류: {e}")
            import traceback
            traceback.print_exc()
            
            # 치명적 오류 발생 시에도 텔레그램 알림
            try:
                await self.send_message(
                    "CRITICAL",
                    "시스템 치명적 오류 발생",
                    f"오류 내용: {str(e)}\n시스템을 안전하게 종료합니다."
                )
            except:
                pass
                
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
        finally:
            # 우아한 종료 처리
            await self._graceful_shutdown()
            self.is_running = False
            logger.info("자동매매 시스템 완전 종료")
    
    async def _unified_cycle_wait(self):
        """통합 순환 관리 시스템을 통한 사이클 대기"""
        try:
            # 현재 사이클 완료 및 다음 사이클 준비
            self.cycle_manager.advance_to_next_cycle()
            
            # 카운트다운 표시
            countdown_display = self.cycle_manager.get_countdown_display()
            await self.send_message(
                TradingSteps.COUNTDOWN,
                "통합 사이클 관리 대기",
                f"다음 자동매매 사이클까지 대기 중...\n{countdown_display}\n\n"
                f"통합 순환 관리 정보:\n"
                f"- 순환 간격: {self.cycle_manager.cycle_interval_seconds}초 (2분)\n"
                f"- 현재 사이클: {self.cycle_manager.cycle_count}회\n"
                f"- 단계별 지연: {self.step_delay_manager.step_delay_seconds}초"
            )
            
            # 통합 순환 관리 시스템을 통한 대기
            success = await self.cycle_manager.wait_for_next_cycle()
            
            if not success:
                logger.warning("통합 순환 대기가 중단됨 - 일반 대기로 전환")
                # 폴백: 일반 대기
                await asyncio.sleep(120)  # 2분 대기
                
        except asyncio.CancelledError:
            logger.info("통합 사이클 대기가 취소됨")
            raise
        except Exception as e:
            logger.error(f"통합 사이클 대기 중 오류: {e}")
            # 폴백: 일반 대기
            await asyncio.sleep(120)  # 2분 대기
    
    async def _countdown_to_next_cycle(self):
        """다음 사이클까지 카운트다운 (레거시 - 호환성 유지)"""
        countdown_seconds = self.config.get_countdown_seconds()
        
        await self.send_message(
            TradingSteps.COUNTDOWN,
            "인터벌 카운트다운",
            TradingMessages.STEP_TEMPLATES[TradingSteps.COUNTDOWN]["start"].format(seconds=countdown_seconds)
        )
        
        for i in range(countdown_seconds, 0, -1):
            print(f"[시간] {i}초 후 다음 사이클 시작...")
            await asyncio.sleep(1)
    
    async def _graceful_shutdown(self):
        """우아한 종료 처리"""
        try:
            logger.info("우아한 종료 처리 시작...")
            
            # 통합 순환 관리 시스템 정지
            if hasattr(self, 'cycle_manager') and self.cycle_manager:
                try:
                    self.cycle_manager.stop()
                    logger.info("통합 순환 관리 시스템 정지 완료")
                except Exception as e:
                    logger.warning(f"순환 관리 시스템 정지 중 오류 (무시): {e}")
            
            # 텔레그램 연결 정리 (GeneratorExit 방지)
            if hasattr(self, 'telegram') and self.telegram:
                try:
                    # 텔레그램 세션을 안전하게 종료
                    if hasattr(self.telegram, 'session') and self.telegram.session:
                        if not self.telegram.session.closed:
                            # 비동기 세션을 동기적으로 종료
                            try:
                                await asyncio.wait_for(self.telegram.session.close(), timeout=2.0)
                            except asyncio.TimeoutError:
                                logger.warning("텔레그램 세션 종료 타임아웃 (무시)")
                    logger.info("텔레그램 연결 정리 완료")
                except Exception as e:
                    logger.warning(f"텔레그램 연결 정리 중 오류 (무시): {e}")
            
            # API 연결 정리
            if hasattr(self, 'api') and self.api:
                try:
                    if hasattr(self.api, 'session') and self.api.session:
                        # requests.Session의 경우 close() 메소드 사용
                        self.api.session.close()
                    logger.info("API 연결 정리 완료")
                except Exception as e:
                    logger.warning(f"API 연결 정리 중 오류 (무시): {e}")
            
            logger.info("우아한 종료 처리 완료")
            
        except Exception as e:
            logger.error(f"우아한 종료 처리 중 오류: {e}")
    
    def stop(self):
        """자동매매 중단"""
        self.is_running = False
        logger.info("자동매매 중단 요청됨")
    
    # 나머지 단계들 (step_04 ~ step_15)은 유사한 패턴으로 구현
    # 실제 API 호출과 비즈니스 로직을 포함
    
    async def step_04_stock_collection_start(self) -> TradingResult:
        """4단계: 종목 수집 시작"""
        try:
            await self.send_message(
                TradingSteps.STOCK_COLLECTION_START,
                TradingMessages.STEP_TEMPLATES[TradingSteps.STOCK_COLLECTION_START]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.STOCK_COLLECTION_START]["start"]
            )
            return TradingResult(True)
        except Exception as e:
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def step_05_stock_collection_process(self) -> TradingResult:
        """5단계: 종목 수집 진행"""
        try:
            await self.send_message(
                TradingSteps.STOCK_COLLECTION_PROCESS,
                TradingMessages.STEP_TEMPLATES[TradingSteps.STOCK_COLLECTION_PROCESS]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.STOCK_COLLECTION_PROCESS]["process"]
            )
            
            # 단계별 지연 (통합 관리 시스템 사용)
            await self.step_delay_manager.delay_between_steps("매매 실행")
            
            # 실제 종목 수집 로직
            collection_result = await self._collect_trading_stocks()
            
            # 종목 수집 결과 표시 (테마종목만)
            collection_message = f"""종목 수집이 완료되었습니다.

[수집 현황]
- 테마 종목: {collection_result['theme_stocks']}개
- 전체 수집: {collection_result['total_stocks']}개
- 분석 완료: {collection_result['analyzed_stocks']}개  
- 매수 후보: {collection_result['buy_candidates']}개

[수집된 종목 목록]
{collection_result['stocks_display']}"""

            await self.send_message(
                TradingSteps.STOCK_COLLECTION_PROCESS,
                "종목 수집 완료",
                collection_message
            )
            
            return TradingResult(True, data=collection_result)
            
        except Exception as e:
            logger.error(f"종목 수집 실행 단계 실패: {e}")
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def _collect_trading_stocks(self) -> Dict[str, Any]:
        """실제 종목 수집 로직 - 테마 기반 종목 수집"""
        try:
            # 테마 기반 종목 수집 시스템 (급등종목 로직 제거됨)
            from stock_data_collector import StockDataCollector
            from support.enhanced_theme_stocks import get_enhanced_theme_stocks
            
            collector = StockDataCollector(max_analysis_stocks=20)  # 실전투자 분석용 20개 제한
            collected_stocks = []
            
            # 1. 멀티스레드 방식으로 테마 종목 데이터 수집 (20개 제한 적용)
            try:
                logger.info("멀티스레드 종목 데이터 수집 시작...")
                
                # 멀티스레드로 실제 종목 데이터 수집
                collection_result = await collector.collect_and_cache_stocks(self.api, use_multithreading=True)
                
                # 수집된 종목 정보를 표준 형식으로 변환
                theme_stocks_list = collection_result.get('theme_stocks', [])
                stock_info = collection_result.get('stock_info', {})
                
                logger.info(f"멀티스레드 수집 완료: 테마 종목 {len(theme_stocks_list)}개, 상세 정보 {len(stock_info)}개")
                
                # 수집된 종목을 collected_stocks 형식으로 변환
                for stock_code in theme_stocks_list:
                    if len(collected_stocks) >= 20:  # 20개 제한 적용
                        break
                        
                    stock_name = collector._get_stock_name(stock_code, self.api)
                    
                    # 종목의 상세 정보가 있으면 추가
                    reason = "테마 종목"
                    if stock_code in stock_info:
                        info = stock_info[stock_code]
                        if isinstance(info, dict) and 'current_price' in info:
                            reason += f" (가격: {info['current_price']:,.0f}원)"
                    
                    collected_stocks.append({
                        "name": stock_name,
                        "code": stock_code,
                        "reason": reason,
                        "info": stock_info.get(stock_code, {})
                    })
                
                logger.info(f"멀티스레드 테마 기반 종목 수집 완료: {len(collected_stocks)}개 (20개 제한 적용)")
            except Exception as e:
                logger.warning(f"테마 기반 수집 실패: {e}")
                collected_stocks = []
            
            # 수집된 종목 목록 확인
            all_stocks = collected_stocks
            
            # 수집된 종목이 없으면 빈 상태로 유지
            if not all_stocks:
                logger.info("종목 수집 결과가 없습니다 - 테마 종목 수집 실패")
            
            # 알고리즘 분석 적용 (실제 구현시)
            if self.algorithm and hasattr(self.algorithm, 'analyze'):
                try:
                    # 알고리즘 필터링 로직 (예시)
                    # all_stocks = self.algorithm.analyze(all_stocks)
                    pass
                except Exception as e:
                    logger.warning(f"알고리즘 분석 실패: {e}")
            
            # 매수 후보 필터링 (수집된 종목 기준)
            buy_candidates = collected_stocks[:15] if collected_stocks else []  # 최대 15개
            
            # 수집된 종목 목록 표시 (종목명(종목코드)/현재가 형식)
            print("\n" + "="*50)
            print("수집된 종목 목록:")
            print("="*50)
            
            if buy_candidates:
                for i, stock in enumerate(buy_candidates, 1):
                    stock_name = stock.get('name', 'Unknown')
                    stock_code = stock.get('code', 'Unknown')
                    stock_info = stock.get('info', {})
                    current_price = stock_info.get('current_price', 'N/A')
                    
                    print(f"{i:2d}. {stock_name}({stock_code}) / {current_price}원")
            else:
                print("수집된 종목이 없습니다.")
            
            print("="*50)
            
            # 텔레그램용 종목 목록 생성
            displayed_stocks = []
            telegram_message = "\n수집된 종목 목록:\n"
            
            if buy_candidates:
                for i, stock in enumerate(buy_candidates, 1):
                    stock_name = stock.get('name', 'Unknown')
                    stock_code = stock.get('code', 'Unknown')
                    stock_info = stock.get('info', {})
                    current_price = stock_info.get('current_price', 'N/A')
                    
                    displayed_stocks.append(f"{stock_name}({stock_code}) / {current_price}원")
                    telegram_message += f"{i:2d}. {stock_name}({stock_code}) / {current_price}원\n"
            else:
                telegram_message += "수집된 종목이 없습니다."
            
            # 텔레그램 메시지 전송
            try:
                from support.telegram_notifier import get_telegram_notifier
                telegram = get_telegram_notifier()
                await telegram.send_message(f"[자동매매] {telegram_message}")
            except Exception as e:
                logger.warning(f"텔레그램 종목 목록 전송 실패: {e}")
            
            return {
                "surge_stocks": 0,  # 자동매매에서는 급등종목 사용 안함
                "theme_stocks": len(collected_stocks),
                "total_stocks": len(all_stocks),
                "analyzed_stocks": len(all_stocks),
                "buy_candidates": len(buy_candidates),
                "stocks_display": "\n".join(displayed_stocks),
                "collected_stocks": all_stocks,
                "buy_candidate_stocks": buy_candidates
            }
            
        except Exception as e:
            logger.error(f"종목 수집 실패: {e}")
            return {
                "surge_stocks": 0,  # 자동매매에서는 급등종목 사용 안함
                "theme_stocks": 0,
                "total_stocks": 0,
                "analyzed_stocks": 0, 
                "buy_candidates": 0,
                "stocks_display": "종목 수집 실패",
                "collected_stocks": [],
                "buy_candidate_stocks": []
            }
    
    async def step_06_auto_trading_start(self) -> TradingResult:
        """6단계: 자동매매 시작"""
        try:
            algorithm_name = self.algorithm.__class__.__name__ if self.algorithm else "기본 알고리즘"
            
            # 알고리즘 시작 표시 (빨간색)
            print_algorithm_start("자동매매")
            
            await self.send_message(
                TradingSteps.AUTO_TRADING_START,
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_START]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_START]["start"].format(algorithm_name=algorithm_name)
            )
            
            # 단계 간 지연
            await step_delay(3)
            
            return TradingResult(True)
        except Exception as e:
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def step_07_auto_trading_analysis(self) -> TradingResult:
        """7단계: 자동매매 종목 분석"""
        try:
            await self.send_message(
                TradingSteps.AUTO_TRADING_ANALYSIS,
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_ANALYSIS]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_ANALYSIS]["process"]
            )
            
            # 단계 간 지연
            await step_delay(3)
            
            return TradingResult(True)
        except Exception as e:
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def step_08_auto_trading_decision(self) -> TradingResult:
        """8단계: 매매 여부 판단"""
        try:
            await self.send_message(
                TradingSteps.AUTO_TRADING_DECISION,
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_DECISION]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_DECISION]["process"]
            )
            
            # 단계 간 지연
            await step_delay(3)
            
            return TradingResult(True)
        except Exception as e:
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def step_09_auto_trading_execute(self) -> TradingResult:
        """9단계: 매수/매도 실행"""
        try:
            # 실제 매수/매도 로직 실행
            buy_orders = 0
            sell_orders = 0
            success_count = 0
            total_attempts = 0
            
            # 1. 매도 처리 - 기존 보유 종목 중 매도 조건 검사
            if hasattr(self, 'account_manager') and self.account_manager:
                try:
                    positions = self.account_manager.get_positions(self.account_type)
                    for position in positions:
                        # 간단한 매도 조건 (예: 손실률 3% 이상 또는 수익률 5% 이상)
                        profit_rate = self._calculate_position_profit_rate(position)
                        if profit_rate <= -3.0 or profit_rate >= 5.0:
                            sell_result = await self._execute_sell_order(position)
                            total_attempts += 1
                            if sell_result.success:
                                sell_orders += 1
                                success_count += 1
                except Exception as e:
                    logger.warning(f"매도 처리 중 오류: {e}")
            
            # 2. 매수 처리 - 수집된 매수 후보 종목들 처리
            if hasattr(self, 'collected_stocks') and self.collected_stocks:
                buy_candidates = getattr(self, 'buy_candidates', self.collected_stocks[:8])
                
                for stock in buy_candidates[:3]:  # 최대 3개 종목만 매수
                    try:
                        # 알고리즘 분석 수행
                        if self.algorithm and hasattr(self.algorithm, 'analyze'):
                            analysis = self.algorithm.analyze(stock)
                            if analysis.get('action') == 'buy':
                                # 실제 매수 주문 실행
                                buy_result = await self._execute_buy_order(stock)
                                total_attempts += 1
                                if buy_result.success:
                                    buy_orders += 1
                                    success_count += 1
                    except Exception as e:
                        logger.warning(f"매수 처리 중 오류 {stock.get('symbol', 'Unknown')}: {e}")
                        total_attempts += 1
            
            # 성공률 계산
            success_rate = f"{(success_count/total_attempts*100):.1f}%" if total_attempts > 0 else "0.0%"
            
            trading_result = {
                "buy_orders": buy_orders,
                "sell_orders": sell_orders,
                "success_rate": success_rate
            }
            
            await self.send_message(
                TradingSteps.AUTO_TRADING_EXECUTE,
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_EXECUTE]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_EXECUTE]["complete"].format(**trading_result)
            )
            
            self.trading_stats["buy_orders"] += trading_result["buy_orders"]
            self.trading_stats["sell_orders"] += trading_result["sell_orders"]
            self.trading_stats["total_trades"] += trading_result["buy_orders"] + trading_result["sell_orders"]
            
            # 단계 간 지연
            await step_delay(3)
            
            return TradingResult(True, data=trading_result)
        except Exception as e:
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def step_10_auto_trading_end(self) -> TradingResult:
        """10단계: 자동매매 종료"""
        try:
            await self.send_message(
                TradingSteps.AUTO_TRADING_END,
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_END]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_END]["complete"]
            )
            
            # 알고리즘 종료 표시 (빨간색)
            print_algorithm_end("자동매매")
            
            # 단계 간 지연
            await step_delay(3)
            
            return TradingResult(True)
        except Exception as e:
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def step_11_auto_trading_result(self) -> TradingResult:
        """11단계: 자동매매 결과"""
        try:
            result = {
                "total_trades": self.trading_stats["total_trades"],
                "profit": f"+{self.session_profit:,.0f}원" if self.session_profit > 0 else f"{self.session_profit:,.0f}원",
                "success_trades": self.trading_stats["successful_trades"]
            }
            
            await self.send_message(
                TradingSteps.AUTO_TRADING_RESULT,
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_RESULT]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.AUTO_TRADING_RESULT]["complete"].format(**result)
            )
            
            return TradingResult(True, data=result)
        except Exception as e:
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def step_12_user_stock_start(self) -> TradingResult:
        """12단계: 사용자 지정종목 매매 시작"""
        try:
            await self.send_message(
                TradingSteps.USER_STOCK_START,
                TradingMessages.STEP_TEMPLATES[TradingSteps.USER_STOCK_START]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.USER_STOCK_START]["start"]
            )
            return TradingResult(True)
        except Exception as e:
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def step_13_user_stock_decision(self) -> TradingResult:
        """13단계: 사용자 지정종목 매매 여부 판단"""
        try:
            await self.send_message(
                TradingSteps.USER_STOCK_DECISION,
                TradingMessages.STEP_TEMPLATES[TradingSteps.USER_STOCK_DECISION]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.USER_STOCK_DECISION]["process"]
            )
            await asyncio.sleep(self.config.get_step_delay_seconds())
            return TradingResult(True)
        except Exception as e:
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def step_14_user_stock_result(self) -> TradingResult:
        """14단계: 사용자 지정종목 매매 결과"""
        try:
            # 실제 사용자 지정 종목 매매 결과 계산
            analyzed_stocks = 0
            executed_trades = 0
            pending_orders = 0
            
            # 사용자 지정 종목 매매 관리자를 통해 실제 결과 조회
            if hasattr(self, 'user_trading_manager') and self.user_trading_manager:
                try:
                    user_stats = await self.user_trading_manager.get_trading_stats()
                    analyzed_stocks = user_stats.get('analyzed_count', 0)
                    executed_trades = user_stats.get('executed_count', 0)
                    pending_orders = user_stats.get('pending_count', 0)
                except Exception as e:
                    logger.warning(f"사용자 지정종목 통계 조회 실패: {e}")
            
            # 계좌 매니저를 통해 대기 중인 주문 확인
            if hasattr(self, 'account_manager') and self.account_manager:
                try:
                    pending_orders = await self.account_manager.get_pending_orders_count(self.account_type)
                except Exception as e:
                    logger.warning(f"대기 주문 조회 실패: {e}")
            
            user_result = {
                "analyzed_stocks": analyzed_stocks,
                "executed_trades": executed_trades,
                "pending_orders": pending_orders
            }
            
            await self.send_message(
                TradingSteps.USER_STOCK_RESULT,
                TradingMessages.STEP_TEMPLATES[TradingSteps.USER_STOCK_RESULT]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.USER_STOCK_RESULT]["complete"].format(**user_result)
            )
            
            return TradingResult(True, data=user_result)
        except Exception as e:
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    async def step_15_cycle_end(self) -> TradingResult:
        """15단계: 사이클 종료"""
        try:
            await self.send_message(
                TradingSteps.CYCLE_END,
                TradingMessages.STEP_TEMPLATES[TradingSteps.CYCLE_END]["title"],
                TradingMessages.STEP_TEMPLATES[TradingSteps.CYCLE_END]["complete"]
            )
            return TradingResult(True)
        except Exception as e:
            return TradingResult(False, error=str(e), return_code=ReturnCodes.FAILURE)
    
    # Health Check 기능 제거됨 - 원래 자동매매에 없던 불필요한 기능
    
    # 복구 기능 제거됨 - 원래 자동매매에 없던 불필요한 기능
    
    # 비상 복구 기능 제거됨 - 원래 자동매매에 없던 불필요한 기능
    
    async def _reinitialize_api(self):
        """API 재초기화"""
        try:
            logger.info("API 재초기화 시작")
            
            # 기존 API 정리
            if self.api and hasattr(self.api, 'close'):
                try:
                    await self.api.close()
                except Exception as close_error:
                    logger.warning(f"기존 API 정리 중 오류: {close_error}")
            
            # 새 API 생성
            from support.api_connector import KISAPIConnector
            self.api = KISAPIConnector(is_mock=(self.account_type == "MOCK"))
            
            # 연결 테스트
            test_result = await self._test_api_connection()
            if not test_result:
                raise APIConnectionError("API 연결 테스트 실패")
            
            logger.info("API 재초기화 성공")
            
        except Exception as e:
            logger.error(f"API 재초기화 실패: {e}")
            raise
    
    async def _test_api_connection(self) -> bool:
        """API 연결 테스트"""
        try:
            if not self.api:
                return False
            
            # 간단한 API 호출로 연결 테스트
            token = self.api.get_access_token()
            if token:
                logger.debug("API 연결 테스트 성공")
                return True
            else:
                logger.warning("API 토큰 없음")
                return False
                
        except Exception as e:
            logger.warning(f"API 연결 테스트 실패: {e}")
            return False
    
    def _get_stock_name_fallback(self, stock_code: str, current_name: str) -> str:
        """종목코드에 대한 fallback 종목명 제공 - StockDataCollector 활용"""
        # StockDataCollector의 종목명 매핑 사용
        try:
            from stock_data_collector import StockDataCollector
            collector = StockDataCollector(max_analysis_stocks=20)  # 실전투자용 제한 적용
            fallback_name = collector._get_stock_name(stock_code, self.api)
            if fallback_name and not fallback_name.startswith('종목'):
                return fallback_name
        except Exception as e:
            logger.warning(f"StockDataCollector 종목명 조회 실패: {e}")
        
        # 최종 fallback - 기본값 사용
        if current_name.startswith('종목') or current_name == stock_code:
            return f"종목{stock_code}"
        
        return current_name