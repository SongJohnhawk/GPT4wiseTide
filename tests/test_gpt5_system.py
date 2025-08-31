#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT-5 기반 지능형 단타 거래 시스템 통합 테스트
"""

import sys
import os
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import GPT-5 system components
try:
    from support.integrated_free_data_system import IntegratedFreeDataSystem
    from support.gpt5_decision_engine import GPT5DecisionEngine, MarketContext
    from support.event_bus_system import EventBusSystem, Event, EventType, Priority
    from support.ai_service_manager import AIServiceManager, ServiceType, AIService
    from support.tidewise_integration_adapter import TideWiseIntegrationAdapter
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    print(f"모듈 임포트 실패: {e}")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GPT5SystemTester:
    """GPT-5 시스템 통합 테스터"""
    
    def __init__(self):
        self.test_results = {}
        self.total_tests = 0
        self.passed_tests = 0
        
    async def run_all_tests(self):
        """모든 테스트 실행"""
        logger.info("=== GPT-5 시스템 통합 테스트 시작 ===")
        
        # 테스트 항목들
        test_methods = [
            ("모듈 가용성 테스트", self.test_module_availability),
            ("데이터 시스템 테스트", self.test_data_system),
            ("이벤트 버스 테스트", self.test_event_bus),
            ("AI 서비스 매니저 테스트", self.test_ai_service_manager),
            ("GPT-5 결정 엔진 테스트", self.test_gpt5_decision_engine),
            ("통합 어댑터 테스트", self.test_integration_adapter),
        ]
        
        for test_name, test_method in test_methods:
            self.total_tests += 1
            logger.info(f"{self.total_tests}. {test_name}...")
            
            try:
                if asyncio.iscoroutinefunction(test_method):
                    result = await test_method()
                else:
                    result = test_method()
                
                if result:
                    self.passed_tests += 1
                    logger.info(f"   ✅ {test_name} 성공")
                    self.test_results[test_name] = "성공"
                else:
                    logger.error(f"   ❌ {test_name} 실패")
                    self.test_results[test_name] = "실패"
            except Exception as e:
                logger.error(f"   ❌ {test_name} 오류: {e}")
                self.test_results[test_name] = f"오류: {e}"
        
        # 결과 출력
        self.print_test_summary()
        return self.passed_tests == self.total_tests
    
    def test_module_availability(self) -> bool:
        """모듈 가용성 테스트"""
        return MODULES_AVAILABLE
    
    async def test_data_system(self) -> bool:
        """데이터 시스템 테스트"""
        try:
            if not MODULES_AVAILABLE:
                return False
                
            data_system = IntegratedFreeDataSystem()
            
            # 기본 초기화 확인
            if not hasattr(data_system, 'cache_dir'):
                return False
            
            if not hasattr(data_system, 'news_manager'):
                return False
            
            if not hasattr(data_system, 'stock_manager'):
                return False
            
            logger.info("   - 데이터 시스템 초기화 성공")
            return True
            
        except Exception as e:
            logger.error(f"   - 데이터 시스템 테스트 실패: {e}")
            return False
    
    async def test_event_bus(self) -> bool:
        """이벤트 버스 테스트"""
        try:
            if not MODULES_AVAILABLE:
                return False
            
            # 메모리 기반 테스트 (Redis 없이)
            event = Event(
                event_id="test-001",
                event_type=EventType.MARKET_DATA_UPDATE,
                priority=Priority.NORMAL,
                timestamp=datetime.now(),
                data={"symbol": "TEST", "price": 100.0},
                source="test"
            )
            
            # 이벤트 객체 생성 확인
            if not hasattr(event, 'event_type'):
                return False
            
            if not hasattr(event, 'data'):
                return False
            
            logger.info("   - 이벤트 버스 객체 생성 성공")
            return True
            
        except Exception as e:
            logger.error(f"   - 이벤트 버스 테스트 실패: {e}")
            return False
    
    async def test_ai_service_manager(self) -> bool:
        """AI 서비스 매니저 테스트"""
        try:
            if not MODULES_AVAILABLE:
                return False
            
            service_manager = AIServiceManager()
            
            # 기본 속성 확인
            if not hasattr(service_manager, 'services'):
                return False
            
            if not hasattr(service_manager, 'load_balancer'):
                return False
            
            logger.info("   - AI 서비스 매니저 초기화 성공")
            return True
            
        except Exception as e:
            logger.error(f"   - AI 서비스 매니저 테스트 실패: {e}")
            return False
    
    async def test_gpt5_decision_engine(self) -> bool:
        """GPT-5 결정 엔진 테스트"""
        try:
            if not MODULES_AVAILABLE:
                return False
            
            # 테스트용 설정 (API 키 없이 테스트)
            config = {
                "model": "gpt-4",  # 테스트용
                "api_base": None,
                "max_retries": 1,
                "timeout": 10
            }
            
            engine = GPT5DecisionEngine(config)
            
            # 기본 속성 확인
            if not hasattr(engine, 'config'):
                return False
            
            if not hasattr(engine, 'decision_cache'):
                return False
            
            logger.info("   - GPT-5 결정 엔진 초기화 성공")
            return True
            
        except Exception as e:
            logger.error(f"   - GPT-5 결정 엔진 테스트 실패: {e}")
            return False
    
    async def test_integration_adapter(self) -> bool:
        """통합 어댑터 테스트"""
        try:
            if not MODULES_AVAILABLE:
                return False
            
            adapter = TideWiseIntegrationAdapter()
            
            # 기본 속성 확인
            if not hasattr(adapter, 'active_system'):
                return False
            
            if not hasattr(adapter, 'config'):
                return False
            
            logger.info("   - 통합 어댑터 초기화 성공")
            return True
            
        except Exception as e:
            logger.error(f"   - 통합 어댑터 테스트 실패: {e}")
            return False
    
    def print_test_summary(self):
        """테스트 결과 요약 출력"""
        logger.info("=" * 60)
        logger.info("GPT-5 시스템 테스트 결과:")
        
        for test_name, result in self.test_results.items():
            status_icon = "✅" if result == "성공" else "❌"
            logger.info(f"   {status_icon} {test_name}: {result}")
        
        success_rate = (self.passed_tests / self.total_tests) * 100
        logger.info(f"\n전체 시스템 성공률: {self.passed_tests}/{self.total_tests} ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            logger.info("🎉 GPT-5 시스템이 성공적으로 구축되었습니다!")
        elif success_rate >= 60:
            logger.warning("⚠️  GPT-5 시스템에 일부 문제가 있지만 기본 기능은 작동합니다.")
        else:
            logger.error("🚨 GPT-5 시스템에 심각한 문제가 있습니다.")


async def main():
    """메인 테스트 함수"""
    tester = GPT5SystemTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n✅ 모든 테스트가 성공적으로 완료되었습니다!")
        return 0
    else:
        print("\n❌ 일부 테스트에서 문제가 발생했습니다.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)