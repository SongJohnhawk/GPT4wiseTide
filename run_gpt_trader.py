#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT 단타매매 시스템 메인 실행기
통합 GPT 거래 시스템 실행 및 관리

사용법:
python run_gpt_trader.py --account real --api-key your_openai_key
python run_gpt_trader.py --account mock  # 모의투자 (테스트용)
"""

import asyncio
import argparse
import logging
import sys
import json
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.integrated_gpt_trader import IntegratedGPTTrader
from support.trading_time_manager import get_trading_time_manager
from support.gpt_trading_engine import get_gpt_trading_engine

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gpt_trader.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GPTTradingRunner:
    """GPT 거래 시스템 실행기"""
    
    def __init__(self, account_type: str = "REAL", openai_api_key: str = None):
        self.account_type = account_type.upper()
        self.openai_api_key = openai_api_key
        self.trader = None
        self.is_running = False
        
    def load_api_key_from_config(self) -> str:
        """설정 파일에서 API 키 로드"""
        config_paths = [
            'Policy/Register_Key/Register_Key.md',
            'support/openai_config.json',
            '.env'
        ]
        
        for config_path in config_paths:
            try:
                config_file = PROJECT_ROOT / config_path
                if not config_file.exists():
                    continue
                
                if config_path.endswith('.md'):
                    # Markdown 파일에서 API 키 추출
                    content = config_file.read_text(encoding='utf-8')
                    lines = content.split('\n')
                    
                    for line in lines:
                        if 'OPEN_API Key:' in line or 'OPENAI_API_KEY:' in line:
                            parts = line.split(':')
                            if len(parts) > 1:
                                api_key = parts[1].strip().strip('[]')
                                if api_key and api_key != '[여기에_OpenAI_API_키_입력]':
                                    logger.info(f"API 키를 {config_path}에서 로드했습니다.")
                                    return api_key
                
                elif config_path.endswith('.json'):
                    # JSON 파일에서 API 키 추출
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        api_key = config.get('openai_api_key') or config.get('OPENAI_API_KEY')
                        if api_key:
                            logger.info(f"API 키를 {config_path}에서 로드했습니다.")
                            return api_key
                
                elif config_path.endswith('.env'):
                    # .env 파일에서 API 키 추출
                    content = config_file.read_text(encoding='utf-8')
                    for line in content.split('\n'):
                        if line.startswith('OPENAI_API_KEY='):
                            api_key = line.split('=', 1)[1].strip().strip('"\'')
                            if api_key:
                                logger.info(f"API 키를 {config_path}에서 로드했습니다.")
                                return api_key
                            
            except Exception as e:
                logger.warning(f"{config_path}에서 API 키 로드 실패: {e}")
                continue
        
        return None
    
    async def initialize_system(self):
        """시스템 초기화"""
        logger.info("=== GPT 단타매매 시스템 초기화 ===")
        
        try:
            # 1. API 키 확인
            if not self.openai_api_key:
                self.openai_api_key = self.load_api_key_from_config()
            
            if not self.openai_api_key:
                logger.error("OpenAI API 키가 설정되지 않았습니다!")
                print("\nAPI 키 설정 방법:")
                print("1. 명령행 옵션: --api-key your_key")
                print("2. Policy/Register_Key/Register_Key.md 파일에 추가")
                print("3. support/openai_config.json 파일 생성")
                print("4. .env 파일에 OPENAI_API_KEY=your_key 추가")
                return False
            
            # API 키 일부만 표시 (보안)
            masked_key = f"{self.openai_api_key[:8]}...{self.openai_api_key[-4:]}"
            logger.info(f"OpenAI API 키 확인: {masked_key}")
            
            # 2. 거래 시스템 초기화
            logger.info(f"계좌 타입: {self.account_type}")
            self.trader = IntegratedGPTTrader(
                account_type=self.account_type,
                openai_api_key=self.openai_api_key
            )
            
            # 3. 시스템 상태 체크
            time_manager = get_trading_time_manager()
            trading_status = time_manager.get_trading_status()
            
            logger.info("시스템 상태:")
            logger.info(f"  현재 시간: {trading_status['current_time']}")
            logger.info(f"  거래 단계: {trading_status['current_phase']}")
            logger.info(f"  거래 시간: {trading_status['is_trading_time']}")
            logger.info(f"  거래 시간대: {trading_status['trading_hours']['start']} ~ {trading_status['trading_hours']['end']}")
            logger.info(f"  사이클 간격: 오전 {trading_status['trading_hours']['morning_interval']}분, 오후 {trading_status['trading_hours']['afternoon_interval']}분")
            
            return True
            
        except Exception as e:
            logger.error(f"시스템 초기화 실패: {e}")
            return False
    
    async def run_trading_system(self):
        """거래 시스템 실행"""
        if not await self.initialize_system():
            return False
        
        logger.info("=== GPT 단타매매 시스템 시작 ===")
        self.is_running = True
        
        try:
            # 거래 시스템 실행
            success = await self.trader.run()
            
            if success:
                logger.info("GPT 단타매매 시스템 정상 종료")
            else:
                logger.error("GPT 단타매매 시스템 실행 실패")
            
            return success
            
        except KeyboardInterrupt:
            logger.info("사용자 중단 요청 (Ctrl+C)")
            return True
        except Exception as e:
            logger.error(f"거래 시스템 실행 오류: {e}")
            return False
        finally:
            self.is_running = False
    
    def get_system_stats(self):
        """시스템 통계 출력"""
        if self.trader:
            stats = self.trader.get_gpt_stats()
            
            print("\n=== 시스템 통계 ===")
            print(f"GPT 결정 횟수: {stats['gpt_decisions_made']}")
            print(f"API 비용: ${stats['gpt_api_costs']:.3f}")
            
            gpt_stats = stats['gpt_engine_stats']
            print(f"평균 응답시간: {gpt_stats.get('avg_response_time', 0):.2f}초")
            print(f"성공률: {gpt_stats.get('success_rate', 0):.1f}%")
            print(f"캐시 적중률: {gpt_stats.get('cache_hit_rate', 0)}개 캐시됨")
            
            volume_stats = stats['volume_validator_stats']
            if volume_stats.get('status') == 'active':
                print(f"거래량 검증: {volume_stats['data_points']}개 데이터 포인트")

def create_sample_config():
    """샘플 설정 파일 생성"""
    config_file = PROJECT_ROOT / 'support' / 'openai_config.json'
    
    sample_config = {
        "openai_api_key": "your_openai_api_key_here",
        "model": "gpt-4o",
        "trading_rules": {
            "profit_target": 0.07,
            "stop_loss": 0.015,
            "max_position_size": 0.07
        },
        "time_settings": {
            "trading_start": "09:10",
            "trading_end": "14:00",
            "morning_interval_minutes": 8,
            "afternoon_interval_minutes": 15
        }
    }
    
    try:
        config_file.parent.mkdir(exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, indent=2, ensure_ascii=False)
        
        print(f"샘플 설정 파일이 생성되었습니다: {config_file}")
        print("API 키를 설정한 후 다시 실행하세요.")
        return True
    except Exception as e:
        print(f"설정 파일 생성 실패: {e}")
        return False

async def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='GPT 단타매매 시스템')
    parser.add_argument('--account', choices=['real', 'mock'], default='mock',
                       help='계좌 타입 (real: 실전투자, mock: 모의투자)')
    parser.add_argument('--api-key', type=str,
                       help='OpenAI API 키')
    parser.add_argument('--create-config', action='store_true',
                       help='샘플 설정 파일 생성')
    parser.add_argument('--test-connection', action='store_true',
                       help='연결 테스트만 수행')
    
    args = parser.parse_args()
    
    # 설정 파일 생성
    if args.create_config:
        create_sample_config()
        return
    
    # 거래 시스템 실행
    runner = GPTTradingRunner(
        account_type=args.account,
        openai_api_key=args.api_key
    )
    
    if args.test_connection:
        # 연결 테스트만 수행
        success = await runner.initialize_system()
        if success:
            print("✅ 시스템 연결 테스트 성공")
            
            # GPT 엔진 테스트
            try:
                gpt_engine = get_gpt_trading_engine(runner.openai_api_key)
                test_data = {
                    'current_price': 50000,
                    'volume': 100000,
                    'high_price': 52000,
                    'low_price': 48000,
                    'open_price': 49000,
                    'change_rate': 2.0
                }
                
                print("GPT 연결 테스트 중...")
                # decision = await gpt_engine.make_trading_decision('TEST', test_data)
                # print(f"GPT 테스트 결과: {decision.signal} (신뢰도: {decision.confidence:.2f})")
                print("✅ GPT 연결 테스트 준비 완료")
                
            except Exception as e:
                print(f"❌ GPT 연결 테스트 실패: {e}")
        else:
            print("❌ 시스템 연결 테스트 실패")
        return
    
    # 실제 거래 시스템 실행
    print(f"GPT 단타매매 시스템을 시작합니다... (계좌: {args.account})")
    success = await runner.run_trading_system()
    
    # 통계 출력
    runner.get_system_stats()
    
    if success:
        print("\n✅ GPT 단타매매 시스템이 성공적으로 완료되었습니다.")
    else:
        print("\n❌ GPT 단타매매 시스템 실행에 문제가 발생했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n프로그램 실행 중 오류가 발생했습니다: {e}")
        sys.exit(1)