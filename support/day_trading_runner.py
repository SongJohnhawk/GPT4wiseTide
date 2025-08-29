#!/usr/bin/env python3
"""
DayTradingRunner - 단타매매 실행 관리 클래스
메뉴에서 호출되어 단타매매 전체 프로세스를 관리
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# 깔끔한 콘솔 로거 - 필수 사용
from support.clean_console_logger import (
    get_clean_logger, Phase, start_phase, end_phase, 
    log as clean_log, set_verbose
)
CLEAN_LOGGER_AVAILABLE = True

# 새로운 성능 최적화 시스템 추가
from support.premarket_data_collector import get_premarket_collector, start_premarket_collection
from support.system_level_decision_engine import get_system_decision_engine
from support.unified_cycle_manager import get_unified_cycle_manager, start_unified_cycles
from support.log_manager import get_log_manager

# 로그 매니저를 통한 로거 설정
log_manager = get_log_manager()
logger = log_manager.setup_logger('system', __name__)

# 기본 로깅 레벨을 WARNING으로 설정하여 불필요한 메시지 줄이기
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger('support').setLevel(logging.WARNING)


class DayTradingRunner:
    """단타매매 실행을 관리하는 클래스"""
    
    def __init__(self, account_type: str, selected_algorithm: Dict):
        """
        DayTradingRunner 초기화
        
        Args:
            account_type: 계좌 유형 ("REAL" 또는 "MOCK")
            selected_algorithm: 선택된 알고리즘 정보
        """
        self.account_type = account_type
        self.selected_algorithm = selected_algorithm
        self.project_root = Path(__file__).parent.parent
        
        # 단타매매 전용 알고리즘 로드 여부 확인
        self.day_trade_algorithm = None
        self.use_day_trade_algorithm = False
        
        # 계정 타입 표시 문자열
        self.account_display = "실제계좌" if account_type == "REAL" else "모의투자계좌"
        
        # 성능 최적화 시스템 통합
        self.use_premarket_collection = False  # 백그라운드 급등종목 수집 비활성화 (API 조회 방식 사용)
        self.use_system_decision_engine = True  # 시스템 레벨 결정 엔진 사용
        self.use_unified_cycle_management = True  # 통합 순환 관리 사용
        
        start_phase(Phase.INIT, f"{self.account_display} 단타매매 시스템 준비")
        clean_log(f"{self.account_display} 성능 최적화 시스템 적용됨", "SUCCESS")
    
    async def run(self) -> bool:
        """
        단타매매 전체 실행 프로세스 (성능 최적화 통합)
        
        Returns:
            bool: 성공 여부
        """
        start_phase(Phase.TRADING, f"{self.account_display} 단타매매 시작")
        
        try:
            # 0. 성능 최적화 시스템 초기화
            clean_log("성능 최적화 시스템 초기화 중...", "INFO")
            await self._initialize_optimization_systems()
            
            # 1. 백그라운드 급등종목 수집 비활성화 (API 조회 방식 사용)
            premarket_task = None
            if self.use_premarket_collection:
                premarket_task = asyncio.create_task(self._run_premarket_collection())
                # 로그 메시지 제거 - 백그라운드 수집 대신 API 조회 방식 사용
            
            # 2. 단타매매 알고리즘 확인 및 로드
            clean_log("알고리즘 로드 중...", "INFO")
            if not await self._prepare_algorithm():
                clean_log("알고리즘 파일이 없어서 단타매매를 시작할 수 없습니다", "ERROR")
                clean_log("메뉴 4번에서 단타매매 알고리즘을 먼저 선택하세요", "WARNING")
                end_phase(Phase.TRADING, False)
                return False
            
            # 3. 단타매매 엔진 초기화 (최적화된 버전)
            from support.minimal_day_trader import MinimalDayTrader
            
            # MinimalDayTrader에 누락된 메소드 동적 추가
            def _format_account_data_for_display(self, account_info):
                """계좌 정보를 향상된 콘솔 출력용으로 포맷팅"""
                try:
                    account_type_display = "실전투자" if self.account_type == "REAL" else "모의투자"
                    account_number = account_info.get('ctx_area_nk100', 'N/A')
                    
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
                    
                    # 🔥 하드코딩된 초기값 제거 - API 데이터만 사용
                    # API 응답이 루트 레벨에 데이터가 있음 (output2 구조 아님)
                    if 'dnca_tot_amt' in account_info:
                        # 루트 레벨에 직접 계좌 데이터가 있는 경우
                        balance = safe_float(account_info['dnca_tot_amt']) if 'dnca_tot_amt' in account_info else None
                        available_cash = safe_float(account_info['ord_psbl_cash']) if 'ord_psbl_cash' in account_info else None
                        profit_rate = safe_float(account_info.get('evlu_erng_rt', 0))
                        
                        if balance is None or available_cash is None:
                            raise Exception("계좌 조회 API 응답에 필수 데이터가 없습니다")
                    else:
                        # 기존 output2 구조 처리
                        output2 = account_info.get('output2', [])
                        if not output2:
                            logger.error("계좌 조회 응답에 계좌 데이터가 없습니다")
                            raise Exception("잘못된 계좌 조회 응답 형식")
                            
                        balance_info = output2[0]
                        balance = safe_float(balance_info['dnca_tot_amt']) if 'dnca_tot_amt' in balance_info else None
                        available_cash = safe_float(balance_info['ord_psbl_cash']) if 'ord_psbl_cash' in balance_info else None
                        profit_rate = safe_float(balance_info.get('evlu_erng_rt', 0))
                        
                        if balance is None or available_cash is None:
                            raise Exception("계좌 조회 API 응답에 필수 데이터가 없습니다")
                    
                    # 예수금이 정말 0원인지 확인 (이경우 정상)
                    logger.info(f"실제 계좌 조회 결과: 예수금 {balance:,.0f}원, 주문가능 {available_cash:,.0f}원")
                    if balance == 0 and available_cash == 0:
                        logger.info("API 응답: 예수금과 주문가능금액이 모두 0원 - 정상 상태일 수 있음")
                        logger.warning(f"원본 API 응답 데이터: {balance_info}")
                        # API 호출이 실패했을 가능성이 높으므로 재시도
                        logger.info("계좌 정보 재조회 시도")
                        account_info_retry = self.api_connector.get_account_balance(force_refresh=True)
                        if account_info_retry and 'output2' in account_info_retry:
                            retry_balance_info = account_info_retry['output2'][0]
                            balance = safe_float(retry_balance_info.get('dnca_tot_amt', balance))
                            available_cash = safe_float(retry_balance_info.get('ord_psbl_cash', available_cash))
                            logger.info(f"재조회 결과 - 예수금: {balance:,.0f}원, 주문가능: {available_cash:,.0f}원")
                    
                    holdings = []
                    output1 = account_info.get('output1', [])
                    
                    for stock in output1:
                        if 'hldg_qty' not in stock:
                            continue  # 보유수량 정보가 없는 경우 건너뛰기
                            
                        holding_qty = safe_int(stock['hldg_qty'])
                        if holding_qty > 0:
                            if 'pdno' not in stock:
                                raise Exception("보유종목에 종목코드(pdno) 정보가 없습니다")
                            if 'prdt_name' not in stock:
                                raise Exception("보유종목에 종목명(prdt_name) 정보가 없습니다")
                                
                            holdings.append({
                                'stock_name': stock['prdt_name'].strip(),
                                'stock_code': stock['pdno'],
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
            
            # 메소드 동적 추가 (로그 메시지 제거 - 사용자 경험 개선)
            if not hasattr(MinimalDayTrader, '_format_account_data_for_display'):
                MinimalDayTrader._format_account_data_for_display = _format_account_data_for_display
            
            # 시스템 레벨 결정 엔진 사용 여부에 따른 알고리즘 선택
            selected_algorithm = await self._get_optimized_algorithm()
            
            day_trader = MinimalDayTrader(
                account_type=self.account_type,
                algorithm=selected_algorithm,
                skip_market_hours=True  # 개발/테스트 시 장시간 무시
            )
            
            # 4. 통합 순환 관리 시작
            if self.use_unified_cycle_management:
                start_unified_cycles(120)  # 2분 간격
                logger.info("통합 순환 관리 시작 (2분 간격)")
            
            # 5. 단타매매 실행
            await day_trader.run()
            
            # 6. 백그라운드 작업 정리
            if premarket_task:
                premarket_task.cancel()
                try:
                    await premarket_task
                except asyncio.CancelledError:
                    logger.info("백그라운드 수집 작업 정리 완료")
            
            logger.info(f"[{self.account_display}] 단타매매 완료")
            return True
            
        except KeyboardInterrupt:
            print(f"\n[{self.account_display}] 사용자에 의해 단타매매가 중단되었습니다.")
            return False
        except Exception as e:
            logger.error(f"단타매매 실행 오류: {e}")
            print(f"\n[ERROR] 단타매매 실행 중 오류: {e}")
            return False
        finally:
            # 단타매매 종료 시 백그라운드 프로세스 정리
            try:
                from support.process_cleanup_manager import get_cleanup_manager
                cleanup_manager = get_cleanup_manager()
                print(f"\n[{self.account_display}] 단타매매 종료 - 백그라운드 프로세스 정리 중...")
                cleanup_result = cleanup_manager.cleanup_all_processes(include_self=False)
                if cleanup_result['terminated_processes'] > 0:
                    print(f"  - {cleanup_result['terminated_processes']}개의 백그라운드 프로세스 종료됨")
            except Exception as cleanup_error:
                logger.warning(f"프로세스 정리 중 오류: {cleanup_error}")
    
    async def _prepare_algorithm(self) -> bool:
        """단타매매 알고리즘 준비"""
        try:
            # 1. 먼저 단타매매 전용 알고리즘이 있는지 확인
            day_trade_dir = self.project_root / "day_trade_Algorithm"
            
            if day_trade_dir.exists():
                # Python 및 Pine Script 파일 찾기
                day_trade_files = []
                # Python 파일 스캔
                for f in day_trade_dir.glob("*.py"):
                    if f.name not in ["__init__.py", "__pycache__"]:
                        day_trade_files.append(f)
                # Pine Script 파일 스캔  
                for f in day_trade_dir.glob("*.pine"):
                    day_trade_files.append(f)
                
                if day_trade_files:
                    # New_DayTrading.py를 우선으로 로드 시도
                    algorithm_file = None
                    for f in day_trade_files:
                        if f.name == "New_DayTrading.py":
                            algorithm_file = f
                            break
                    
                    # New_DayTrading.py가 없으면 첫 번째 파일 사용
                    if algorithm_file is None:
                        algorithm_file = day_trade_files[0]
                    
                    # 사용자가 특별히 단타매매 알고리즘을 선택한 경우 그것을 우선 사용
                    if (self.selected_algorithm.get('filename') and 
                        self.selected_algorithm['filename'] in [f.name for f in day_trade_files]):
                        
                        selected_file = day_trade_dir / self.selected_algorithm['filename']
                        if selected_file.exists():
                            algorithm_file = selected_file
                    
                    # 단타매매 알고리즘 로드
                    self.day_trade_algorithm = await self._load_day_trade_algorithm(algorithm_file)
                    if self.day_trade_algorithm:
                        self.use_day_trade_algorithm = True
                        print(f"단타매매 알고리즘 로드: {algorithm_file.name}")
                        print(f"알고리즘 이름: {self.day_trade_algorithm.get_name()}")
                        return True
            
            # 2. 단타매매 전용 알고리즘이 없으면 기본 선택 알고리즘 사용
            if self.selected_algorithm.get('algorithm_instance'):
                # 파일명이 있으면 파일명을 우선 표시, 없으면 이름 표시
                algorithm_display = self.selected_algorithm['info'].get('filename', self.selected_algorithm['info']['name'])
                print(f"기본 알고리즘 사용: {algorithm_display}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"알고리즘 준비 오류: {e}")
            return False
    
    async def _load_day_trade_algorithm(self, algorithm_file: Path):
        """단타매매 알고리즘 파일 로드"""
        try:
            import importlib.util
            import sys
            
            # 모듈 스펙 생성
            spec = importlib.util.spec_from_file_location(
                algorithm_file.stem, 
                algorithm_file
            )
            
            if spec is None or spec.loader is None:
                logger.error(f"알고리즘 스펙 생성 실패: {algorithm_file}")
                return None
            
            # 모듈 로드
            module = importlib.util.module_from_spec(spec)
            sys.modules[algorithm_file.stem] = module
            spec.loader.exec_module(module)
            
            # 알고리즘 클래스 찾기
            algorithm_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    hasattr(attr, 'analyze') and 
                    hasattr(attr, 'get_name') and
                    attr_name != 'BaseAlgorithm'):
                    algorithm_class = attr
                    break
            
            if algorithm_class:
                return algorithm_class()
            else:
                logger.error(f"유효한 알고리즘 클래스를 찾을 수 없음: {algorithm_file}")
                return None
                
        except Exception as e:
            logger.error(f"알고리즘 로드 오류 ({algorithm_file}): {e}")
            return None
    
    async def _initialize_optimization_systems(self) -> bool:
        """성능 최적화 시스템 초기화"""
        try:
            logger.info("성능 최적화 시스템 초기화 시작")
            
            # 백그라운드 급등종목 수집기 초기화
            if self.use_premarket_collection:
                collector = get_premarket_collector(self.account_type)
                # Note: 실제 초기화는 백그라운드 작업에서 수행
                logger.info("백그라운드 수집기 준비 완료")
            
            # 시스템 레벨 결정 엔진 초기화
            if self.use_system_decision_engine:
                decision_engine = get_system_decision_engine()
                logger.info(f"시스템 레벨 결정 엔진 준비 완료: {decision_engine.get_engine_info()['name']}")
            
            # 통합 순환 관리자 초기화
            if self.use_unified_cycle_management:
                cycle_manager = get_unified_cycle_manager(120)  # 2분 간격
                logger.info("통합 순환 관리자 준비 완료")
            
            logger.info("성능 최적화 시스템 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"최적화 시스템 초기화 오류: {e}")
            return False
    
    async def _run_premarket_collection(self) -> None:
        """백그라운드 급등종목 수집 실행"""
        try:
            logger.info("백그라운드 급등종목 수집 비동기 작업 시작")
            await start_premarket_collection(self.account_type)
        except asyncio.CancelledError:
            logger.info("백그라운드 수집 작업 취소됨")
        except Exception as e:
            logger.error(f"백그라운드 수집 작업 오류: {e}")
    
    async def _get_optimized_algorithm(self):
        """최적화된 알고리즘 반환"""
        try:
            # 시스템 레벨 결정 엔진 사용 시 - 기존 알고리즘 그대로 사용
            if self.use_system_decision_engine:
                base_algorithm = (self.day_trade_algorithm if self.use_day_trade_algorithm 
                                else self.selected_algorithm['algorithm_instance'])
                
                logger.info("시스템 레벨 결정 엔진 준비 완료 - 기존 알고리즘과 병행 사용")
                return base_algorithm
            
            # 기존 방식 사용
            return (self.day_trade_algorithm if self.use_day_trade_algorithm 
                   else self.selected_algorithm['algorithm_instance'])
                   
        except Exception as e:
            logger.error(f"최적화된 알고리즘 생성 오류: {e}")
            # 오류 시 기존 알고리즘 반환
            return (self.day_trade_algorithm if self.use_day_trade_algorithm 
                   else self.selected_algorithm['algorithm_instance'])


def get_day_trading_runner(account_type: str, selected_algorithm: Dict) -> DayTradingRunner:
    """DayTradingRunner 인스턴스 생성 팩토리 함수"""
    return DayTradingRunner(account_type, selected_algorithm)