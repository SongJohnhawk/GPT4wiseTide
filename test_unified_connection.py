#!/usr/bin/env python3
"""
통합 연결 관리자 테스트
4가지 매매 모드 모두 테스트:
1. 자동매매 - 실전
2. 자동매매 - 모의
3. 단타매매 - 실전
4. 단타매매 - 모의
"""

import sys
from pathlib import Path
import asyncio
import logging
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedConnectionTest:
    """통합 연결 관리자 테스트"""
    
    def __init__(self):
        self.test_results = {
            'auto_real': None,
            'auto_mock': None,
            'day_real': None,
            'day_mock': None
        }
        
    async def test_connection_manager(self, account_type: str) -> bool:
        """연결 관리자 테스트"""
        try:
            logger.info(f"=== {account_type} 연결 관리자 테스트 시작 ===")
            
            from support.unified_connection_manager import TradingConnectionManager
            
            # 연결 관리자 생성
            manager = TradingConnectionManager(account_type)
            
            # 초기화
            init_result = await manager.initialize()
            if not init_result:
                logger.error(f"{account_type} 연결 관리자 초기화 실패")
                return False
                
            # 상태 확인
            logger.info(f"연결 상태: {manager.connection_state.is_connected}")
            logger.info(f"서버 응답: {manager.connection_state.server_responsive}")
            
            # 계좌 정보 확인
            account_info = await manager.get_account_info()
            if account_info:
                logger.info(f"계좌 번호: {account_info.get('account_number', 'N/A')}")
                logger.info(f"잔고: {account_info.get('balance', 0):,.0f}")
                
            # 정리
            await manager.shutdown()
            
            logger.info(f"{account_type} 연결 관리자 테스트 성공")
            return True
            
        except Exception as e:
            logger.error(f"{account_type} 연결 관리자 테스트 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_auto_trading_modes(self):
        """자동매매 모드 테스트 (실전/모의)"""
        logger.info("\n=== 자동매매 모드 테스트 ===")
        
        # 모의투자 테스트
        self.test_results['auto_mock'] = await self.test_connection_manager("MOCK")
        
        # 실전투자 테스트 (주의: 실제 계좌 연결)
        # self.test_results['auto_real'] = await self.test_connection_manager("REAL")
        self.test_results['auto_real'] = "SKIPPED"  # 안전을 위해 기본적으로 스킵
        
    async def test_day_trading_modes(self):
        """단타매매 모드 테스트 (실전/모의)"""
        logger.info("\n=== 단타매매 모드 테스트 ===")
        
        # 모의투자 테스트
        self.test_results['day_mock'] = await self.test_connection_manager("MOCK")
        
        # 실전투자 테스트 (주의: 실제 계좌 연결)
        # self.test_results['day_real'] = await self.test_connection_manager("REAL")
        self.test_results['day_real'] = "SKIPPED"  # 안전을 위해 기본적으로 스킵
    
    async def test_unified_behavior(self):
        """통합 동작 테스트 - 싱글톤 패턴 확인"""
        logger.info("\n=== 통합 동작 테스트 ===")
        
        try:
            from support.unified_connection_manager import TradingConnectionManager
            
            # 같은 account_type으로 여러 번 생성해도 같은 인스턴스인지 확인
            manager1 = TradingConnectionManager("MOCK")
            manager2 = TradingConnectionManager("MOCK")
            
            if manager1 is manager2:
                logger.info("싱글톤 패턴 정상 작동 - 같은 인스턴스 반환")
            else:
                logger.error("싱글톤 패턴 실패 - 다른 인스턴스 생성됨")
                return False
                
            # 다른 account_type은 다른 인스턴스인지 확인
            manager3 = TradingConnectionManager("REAL")
            
            if manager1 is not manager3:
                logger.info("다른 account_type에 대해 다른 인스턴스 생성됨")
            else:
                logger.error("다른 account_type인데 같은 인스턴스 반환됨")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"통합 동작 테스트 실패: {e}")
            return False
    
    async def run_all_tests(self):
        """모든 테스트 실행"""
        logger.info("=" * 60)
        logger.info("통합 연결 관리자 테스트 시작")
        logger.info("=" * 60)
        
        # 1. 통합 동작 테스트
        unified_ok = await self.test_unified_behavior()
        
        # 2. 자동매매 모드 테스트
        await self.test_auto_trading_modes()
        
        # 3. 단타매매 모드 테스트
        await self.test_day_trading_modes()
        
        # 결과 출력
        logger.info("\n" + "=" * 60)
        logger.info("테스트 결과 요약")
        logger.info("=" * 60)
        
        logger.info(f"통합 동작: {'성공' if unified_ok else '실패'}")
        logger.info(f"자동매매-실전: {self.test_results['auto_real']}")
        logger.info(f"자동매매-모의: {'성공' if self.test_results['auto_mock'] else '실패'}")
        logger.info(f"단타매매-실전: {self.test_results['day_real']}")
        logger.info(f"단타매매-모의: {'성공' if self.test_results['day_mock'] else '실패'}")
        
        # 전체 성공 여부
        all_success = (
            unified_ok and 
            (self.test_results['auto_real'] == "SKIPPED" or self.test_results['auto_real']) and
            self.test_results['auto_mock'] and
            (self.test_results['day_real'] == "SKIPPED" or self.test_results['day_real']) and
            self.test_results['day_mock']
        )
        
        if all_success:
            logger.info("\n[성공] 모든 테스트 통과")
        else:
            logger.error("\n[실패] 일부 테스트 실패")
            
        return all_success


async def main():
    """메인 테스트 실행"""
    tester = UnifiedConnectionTest()
    success = await tester.run_all_tests()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)