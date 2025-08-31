#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tideWise 시스템 통합 어댑터
- 기존 tideWise와 새로운 GPT 시스템 간 브릿지
- 기존 API와 데이터 구조 호환성 유지
- 점진적 마이그레이션 지원
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 기존 tideWise 컴포넌트들
try:
    from support.api_connector import APIConnector
    from support.minimal_day_trader import MinimalDayTrader  
    from support.system_manager import SystemManager
    from support.telegram_notifier import TelegramNotifier
    from support.previous_day_balance_handler import PreviousDayBalanceHandler
    from support.balance_cleanup_manager import BalanceCleanupManager
except ImportError as e:
    logger.warning(f"기존 tideWise 컴포넌트 import 실패: {e}")

# 새로운 GPT 시스템 컴포넌트들
from .event_bus_system import EventBusSystem, EventType, Event, Priority
from .ai_service_manager import AIServiceManager
from .trading_decision import TradingDecision
from .integrated_gpt_trader import IntegratedGPTTrader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TideWiseIntegrationAdapter:
    """tideWise 시스템 통합 어댑터"""
    
    def __init__(
        self,
        account_type: str = "REAL",
        use_gpt_system: bool = True,
        migration_mode: str = "hybrid"  # hybrid, full_gpt, legacy_only
    ):
        self.account_type = account_type
        self.use_gpt_system = use_gpt_system
        self.migration_mode = migration_mode
        
        # 기존 시스템 컴포넌트들
        self.legacy_trader = None
        self.api_connector = None
        self.telegram_notifier = None
        self.system_manager = None
        
        # 새로운 GPT 시스템 컴포넌트들
        self.event_bus = None
        self.ai_service_manager = None
        self.gpt_trader = None
        
        # 통합 상태
        self.is_initialized = False
        self.active_system = None  # "legacy", "gpt", "hybrid"
        
        logger.info(f"tideWise 통합 어댑터 생성 - 모드: {migration_mode}, GPT: {use_gpt_system}")
    
    async def initialize(self) -> bool:
        """시스템 초기화"""
        try:
            logger.info("=== tideWise 시스템 통합 어댑터 초기화 ===")
            
            # 1. 기존 시스템 초기화 (필수 컴포넌트들)
            await self._initialize_legacy_system()
            
            # 2. GPT 시스템 초기화 (활성화된 경우)
            if self.use_gpt_system:
                await self._initialize_gpt_system()
            
            # 3. 통합 모드 설정
            await self._setup_integration_mode()
            
            self.is_initialized = True
            logger.info(f"tideWise 통합 어댑터 초기화 완료 - 활성 시스템: {self.active_system}")
            return True
            
        except Exception as e:
            logger.error(f"tideWise 통합 어댑터 초기화 실패: {e}")
            return False
    
    async def _initialize_legacy_system(self):
        """기존 시스템 초기화"""
        try:
            # API 커넥터 초기화
            self.api_connector = APIConnector(account_type=self.account_type)
            await self.api_connector.initialize()
            
            # 시스템 매니저 초기화
            self.system_manager = SystemManager()
            
            # 텔레그램 알림 시스템 초기화
            try:
                self.telegram_notifier = TelegramNotifier()
                await self.telegram_notifier.initialize()
            except Exception as e:
                logger.warning(f"텔레그램 초기화 실패: {e}")
                self.telegram_notifier = None
            
            # 기존 거래 시스템 초기화 (백업용)
            if self.migration_mode in ["hybrid", "legacy_only"]:
                self.legacy_trader = MinimalDayTrader(account_type=self.account_type)
                await self.legacy_trader.initialize()
            
            logger.info("기존 tideWise 시스템 초기화 완료")
            
        except Exception as e:
            logger.error(f"기존 시스템 초기화 실패: {e}")
            raise
    
    async def _initialize_gpt_system(self):
        """GPT 시스템 초기화"""
        try:
            from .event_bus_system import EventBusConfig, create_default_event_bus
            from .ai_service_manager import create_ai_service_manager
            
            # 이벤트 버스 초기화
            self.event_bus = create_default_event_bus()
            async with self.event_bus.lifespan():
                await self.event_bus.start_workers()
            
            # AI 서비스 매니저 초기화
            self.ai_service_manager = await create_ai_service_manager(self.event_bus)
            
            # 통합 GPT 트레이더 초기화
            self.gpt_trader = IntegratedGPTTrader(
                event_bus=self.event_bus,
                ai_service_manager=self.ai_service_manager
            )
            await self.gpt_trader.initialize()
            
            logger.info("GPT 시스템 초기화 완료")
            
        except Exception as e:
            logger.error(f"GPT 시스템 초기화 실패: {e}")
            raise
    
    async def _setup_integration_mode(self):
        """통합 모드 설정"""
        if self.migration_mode == "full_gpt" and self.gpt_trader:
            self.active_system = "gpt"
            logger.info("전체 GPT 모드로 설정")
            
        elif self.migration_mode == "legacy_only":
            self.active_system = "legacy"
            logger.info("레거시 전용 모드로 설정")
            
        elif self.migration_mode == "hybrid":
            if self.gpt_trader and self.legacy_trader:
                self.active_system = "hybrid"
                logger.info("하이브리드 모드로 설정")
            elif self.gpt_trader:
                self.active_system = "gpt"
                logger.info("GPT 전용 모드로 폴백")
            else:
                self.active_system = "legacy"
                logger.info("레거시 전용 모드로 폴백")
        else:
            self.active_system = "legacy"
            logger.warning("기본 레거시 모드로 설정")
    
    async def run_trading_session(self) -> bool:
        """거래 세션 실행"""
        if not self.is_initialized:
            logger.error("시스템이 초기화되지 않음")
            return False
        
        try:
            logger.info(f"=== {self.active_system.upper()} 거래 세션 시작 ===")
            
            # 사전 초기화 작업
            await self._pre_session_setup()
            
            # 활성 시스템에 따른 거래 실행
            if self.active_system == "gpt":
                success = await self._run_gpt_session()
            elif self.active_system == "legacy":
                success = await self._run_legacy_session()
            elif self.active_system == "hybrid":
                success = await self._run_hybrid_session()
            else:
                logger.error(f"알 수 없는 시스템 모드: {self.active_system}")
                return False
            
            # 사후 정리 작업
            await self._post_session_cleanup()
            
            logger.info(f"거래 세션 완료: {'성공' if success else '실패'}")
            return success
            
        except Exception as e:
            logger.error(f"거래 세션 실행 오류: {e}")
            return False
    
    async def _pre_session_setup(self):
        """세션 시작 전 설정"""
        try:
            # 계좌 정보 업데이트
            if self.api_connector:
                account_info = await self.api_connector.get_account_balance()
                logger.info(f"계좌 잔고: {account_info.get('total_balance', 0):,}원")
            
            # 전날 잔고 처리 (기존 시스템 호환)
            if hasattr(self, 'legacy_trader') and self.legacy_trader:
                await self.legacy_trader.handle_previous_day_balance()
            
            # 세션 시작 알림
            if self.telegram_notifier:
                message = f"[{self.account_type}] 거래 세션 시작\n"
                message += f"활성 시스템: {self.active_system.upper()}\n"
                message += f"시작 시간: {datetime.now().strftime('%H:%M:%S')}"
                await self.telegram_notifier.send_message(message)
            
        except Exception as e:
            logger.warning(f"사전 설정 중 오류: {e}")
    
    async def _run_gpt_session(self) -> bool:
        """GPT 시스템 전용 세션"""
        try:
            if not self.gpt_trader:
                raise ValueError("GPT 트레이더가 초기화되지 않음")
            
            await self.gpt_trader.enable_trading()
            
            # GPT 시스템 실행
            # 실제 구현에서는 시장 데이터 스트림을 이벤트로 발행
            await self._simulate_market_data_stream()
            
            return True
            
        except Exception as e:
            logger.error(f"GPT 세션 실행 오류: {e}")
            return False
    
    async def _run_legacy_session(self) -> bool:
        """레거시 시스템 전용 세션"""
        try:
            if not self.legacy_trader:
                raise ValueError("레거시 트레이더가 초기화되지 않음")
            
            # 기존 MinimalDayTrader 실행
            return await self.legacy_trader.run()
            
        except Exception as e:
            logger.error(f"레거시 세션 실행 오류: {e}")
            return False
    
    async def _run_hybrid_session(self) -> bool:
        """하이브리드 세션 (GPT + 레거시 병행)"""
        try:
            # GPT 시스템을 메인으로, 레거시를 백업으로 사용
            logger.info("하이브리드 모드: GPT 메인, 레거시 백업")
            
            # GPT 시스템 활성화
            if self.gpt_trader:
                await self.gpt_trader.enable_trading()
            
            # 레거시 시스템을 모니터링 모드로 실행
            tasks = []
            
            if self.gpt_trader:
                tasks.append(self._monitor_gpt_system())
            
            if self.legacy_trader:
                tasks.append(self._monitor_legacy_system())
            
            # 병렬 실행
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 확인
            success_count = sum(1 for r in results if r is True)
            return success_count > 0
            
        except Exception as e:
            logger.error(f"하이브리드 세션 실행 오류: {e}")
            return False
    
    async def _monitor_gpt_system(self) -> bool:
        """GPT 시스템 모니터링"""
        try:
            # GPT 시스템 상태 모니터링 및 실행
            await self._simulate_market_data_stream()
            return True
        except Exception as e:
            logger.error(f"GPT 시스템 모니터링 오류: {e}")
            return False
    
    async def _monitor_legacy_system(self) -> bool:
        """레거시 시스템 모니터링"""
        try:
            # 레거시 시스템을 백업 모드로 실행
            # 실제로는 모니터링만 하고 필요시에만 활성화
            logger.info("레거시 시스템 백업 모드 실행")
            return True
        except Exception as e:
            logger.error(f"레거시 시스템 모니터링 오류: {e}")
            return False
    
    async def _simulate_market_data_stream(self):
        """시장 데이터 스트림 시뮬레이션"""
        # 실제 구현에서는 실시간 데이터를 이벤트로 발행
        # 여기서는 테스트용 시뮬레이션
        
        test_symbols = ["005930", "000660", "035420"]  # 삼성전자, SK하이닉스, NAVER
        
        for symbol in test_symbols:
            try:
                # 시장 데이터 이벤트 생성
                market_data_event = await self.event_bus.create_event(
                    event_type=EventType.MARKET_DATA_UPDATE,
                    source_service="tidewise_adapter",
                    payload={
                        'symbol': symbol,
                        'market_data': {
                            'current_price': 100000,
                            'volume': 1000000,
                            'change_rate': 0.02
                        }
                    }
                )
                
                # 이벤트 발행
                await self.event_bus.publish(market_data_event)
                
                # 처리 시간 간격
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"시장 데이터 이벤트 발행 오류 ({symbol}): {e}")
    
    async def _post_session_cleanup(self):
        """세션 종료 후 정리"""
        try:
            # GPT 시스템 비활성화
            if self.gpt_trader:
                await self.gpt_trader.disable_trading()
            
            # 성능 통계 수집
            performance_stats = await self._collect_performance_stats()
            
            # 종료 알림
            if self.telegram_notifier:
                message = f"[{self.account_type}] 거래 세션 종료\n"
                message += f"활성 시스템: {self.active_system.upper()}\n"
                message += f"종료 시간: {datetime.now().strftime('%H:%M:%S')}\n"
                
                if performance_stats:
                    message += f"성능 통계:\n{json.dumps(performance_stats, indent=2, ensure_ascii=False)}"
                
                await self.telegram_notifier.send_message(message)
            
        except Exception as e:
            logger.warning(f"사후 정리 중 오류: {e}")
    
    async def _collect_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 수집"""
        stats = {
            'session_end_time': datetime.now().isoformat(),
            'active_system': self.active_system
        }
        
        try:
            # GPT 시스템 통계
            if self.gpt_trader:
                gpt_status = await self.gpt_trader.get_system_status()
                stats['gpt_system'] = gpt_status
            
            # AI 서비스 통계
            if self.ai_service_manager:
                ai_stats = self.ai_service_manager.get_system_metrics()
                stats['ai_services'] = ai_stats
            
            # 레거시 시스템 통계
            if self.legacy_trader and hasattr(self.legacy_trader, 'get_performance_stats'):
                legacy_stats = self.legacy_trader.get_performance_stats()
                stats['legacy_system'] = legacy_stats
            
        except Exception as e:
            logger.warning(f"성능 통계 수집 중 오류: {e}")
            stats['collection_error'] = str(e)
        
        return stats
    
    async def shutdown(self):
        """시스템 종료"""
        try:
            logger.info("tideWise 통합 어댑터 종료 시작")
            
            # GPT 시스템 종료
            if self.gpt_trader:
                await self.gpt_trader.disable_trading()
            
            if self.ai_service_manager:
                await self.ai_service_manager.shutdown()
            
            if self.event_bus:
                await self.event_bus.shutdown()
            
            # 레거시 시스템 종료
            if self.legacy_trader and hasattr(self.legacy_trader, 'shutdown'):
                await self.legacy_trader.shutdown()
            
            logger.info("tideWise 통합 어댑터 종료 완료")
            
        except Exception as e:
            logger.error(f"시스템 종료 중 오류: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태 조회"""
        return {
            'is_initialized': self.is_initialized,
            'active_system': self.active_system,
            'migration_mode': self.migration_mode,
            'account_type': self.account_type,
            'components': {
                'event_bus': self.event_bus is not None,
                'ai_service_manager': self.ai_service_manager is not None,
                'gpt_trader': self.gpt_trader is not None,
                'legacy_trader': self.legacy_trader is not None,
                'telegram_notifier': self.telegram_notifier is not None
            }
        }

# 편의 함수들
async def create_integration_adapter(
    account_type: str = "REAL",
    migration_mode: str = "hybrid",
    use_gpt: bool = True
) -> TideWiseIntegrationAdapter:
    """통합 어댑터 생성 및 초기화"""
    adapter = TideWiseIntegrationAdapter(
        account_type=account_type,
        use_gpt_system=use_gpt,
        migration_mode=migration_mode
    )
    
    success = await adapter.initialize()
    if not success:
        raise RuntimeError("통합 어댑터 초기화 실패")
    
    return adapter

async def run_integrated_trading_session(
    account_type: str = "REAL",
    migration_mode: str = "hybrid"
) -> bool:
    """통합 거래 세션 실행"""
    adapter = None
    try:
        adapter = await create_integration_adapter(
            account_type=account_type,
            migration_mode=migration_mode
        )
        
        return await adapter.run_trading_session()
        
    except Exception as e:
        logger.error(f"통합 거래 세션 실행 실패: {e}")
        return False
    finally:
        if adapter:
            await adapter.shutdown()