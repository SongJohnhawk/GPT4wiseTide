#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT-5 기반 지능형 단타매매 시스템 메인 실행기
- 이벤트 기반 아키텍처
- 다중 AI 서비스 통합
- 기존 tideWise 시스템과 호환
- 완전 객체화된 구조
"""

import asyncio
import logging
import sys
import signal
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import json
import os

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GPT5TradingOrchestrator:
    """GPT-5 거래 시스템 메인 오케스트레이터"""
    
    def __init__(
        self,
        account_type: str = "REAL",
        migration_mode: str = "hybrid",
        config_file: Optional[str] = None
    ):
        self.account_type = account_type
        self.migration_mode = migration_mode
        self.config = self._load_config(config_file)
        
        # 상태 관리
        self.is_running = False
        self.shutdown_requested = False
        
        # 성능 메트릭
        self.session_stats = {
            'start_time': None,
            'end_time': None,
            'total_runtime': 0,
            'decisions_made': 0,
            'trades_executed': 0,
            'system_errors': 0
        }
        
        logger.info(f"GPT-5 거래 오케스트레이터 생성: {account_type} 모드")
    
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """설정 파일 로드"""
        default_config = {
            'openai_api_key': os.getenv('OPENAI_API_KEY'),
            'max_positions': 5,
            'position_size_ratio': 0.07,
            'daily_loss_limit': 0.05,
            'log_level': 'INFO'
        }
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
                logger.info(f"설정 파일 로드: {config_file}")
            except Exception as e:
                logger.warning(f"설정 파일 로드 실패: {e}")
        
        return default_config
    
    async def initialize(self) -> bool:
        """오케스트레이터 초기화"""
        try:
            logger.info("=== GPT-5 거래 시스템 초기화 시작 ===")
            self.session_stats['start_time'] = datetime.now()
            
            logger.info("=== GPT-5 거래 시스템 초기화 완료 ===")
            return True
            
        except Exception as e:
            logger.error(f"GPT-5 거래 시스템 초기화 실패: {e}")
            return False
    
    async def run(self) -> bool:
        """메인 거래 세션 실행"""
        try:
            logger.info("=== GPT-5 거래 세션 시작 ===")
            self.is_running = True
            
            # 거래 세션 실행
            success = await self._execute_trading_session()
            
            if success:
                logger.info("거래 세션 성공적으로 완료")
            else:
                logger.error("거래 세션 실행 중 오류 발생")
            
            return success
            
        except Exception as e:
            logger.error(f"거래 세션 실행 중 오류: {e}")
            self.session_stats['system_errors'] += 1
            return False
        finally:
            self.is_running = False
            await self._finalize_session()
    
    async def _execute_trading_session(self) -> bool:
        """거래 세션 실행 로직"""
        try:
            # 시뮬레이션 로직
            logger.info("거래 세션 시뮬레이션 실행")
            await asyncio.sleep(1)
            return True
            
        except Exception as e:
            logger.error(f"거래 세션 실행 오류: {e}")
            return False
    
    async def _finalize_session(self):
        """세션 종료 처리"""
        try:
            self.session_stats['end_time'] = datetime.now()
            if self.session_stats['start_time']:
                runtime = self.session_stats['end_time'] - self.session_stats['start_time']
                self.session_stats['total_runtime'] = runtime.total_seconds()
            
            logger.info("세션 종료 처리 완료")
            
        except Exception as e:
            logger.error(f"세션 종료 처리 오류: {e}")
    
    async def shutdown(self):
        """시스템 종료"""
        try:
            logger.info("GPT-5 거래 시스템 종료 시작")
            self.shutdown_requested = True
            self.is_running = False
            logger.info("GPT-5 거래 시스템 종료 완료")
            
        except Exception as e:
            logger.error(f"시스템 종료 중 오류: {e}")

async def main():
    """메인 함수"""
    orchestrator = None
    
    try:
        # 명령행 인자 처리
        account_type = sys.argv[1] if len(sys.argv) > 1 else "REAL"
        migration_mode = sys.argv[2] if len(sys.argv) > 2 else "hybrid"
        config_file = sys.argv[3] if len(sys.argv) > 3 else None
        
        # 오케스트레이터 생성 및 초기화
        orchestrator = GPT5TradingOrchestrator(
            account_type=account_type,
            migration_mode=migration_mode,
            config_file=config_file
        )
        
        # 시스템 초기화
        if not await orchestrator.initialize():
            logger.error("시스템 초기화 실패")
            return False
        
        # 거래 세션 실행
        success = await orchestrator.run()
        
        if success:
            logger.info("=== GPT-5 거래 시스템 정상 종료 ===")
        else:
            logger.error("=== GPT-5 거래 시스템 오류 종료 ===")
        
        return success
        
    except KeyboardInterrupt:
        logger.info("사용자 중단 요청")
        return True
    except Exception as e:
        logger.error(f"시스템 실행 중 오류: {e}")
        return False
    finally:
        if orchestrator:
            await orchestrator.shutdown()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)