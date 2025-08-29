#!/usr/bin/env python3
"""
사용자 지정종목 독립 매매 실행기
- 일반 단타매매와 분리하여 사용자 지정종목만 매매
- 필요할 때 독립적으로 실행 가능
- 점심시간(12:00-12:30) 자동 실행 기능 포함
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# UTF-8 인코딩 설정
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


async def main():
    """사용자 지정종목 독립 매매 메인 함수"""
    try:
        # 깔끔한 콘솔 출력 시스템
        from support.clean_console_logger import (
            start_phase, end_phase, clean_log, Phase
        )
        
        start_phase(Phase.INIT, "사용자 지정종목 독립 매매 시스템")
        clean_log("tideWise v11.0 분리 모듈", "INFO")
        
        # 로그 매니저 초기화
        from support.log_manager import get_log_manager
        log_manager = get_log_manager()
        logger = log_manager.setup_logger('user_designated', __name__)
        
        clean_log("시스템 로거 초기화 완료", "SUCCESS")
        
        # 계좌 유형 선택
        print("[ 계좌 유형 선택 ]")
        print("1. 실전투자")
        print("2. 모의투자")
        print("-" * 40)
        
        while True:
            choice = input("계좌 유형을 선택하세요 (1 또는 2): ").strip()
            if choice == "1":
                account_type = "REAL"
                account_display = "실전투자"
                break
            elif choice == "2":
                account_type = "MOCK"
                account_display = "모의투자"
                break
            else:
                print("잘못된 선택입니다. 1 또는 2를 입력하세요.")
        
        print(f"\n선택된 계좌: {account_display}")
        print("=" * 80)
        
        # 초기화 완료
        end_phase(Phase.INIT, True)
        
        # API 커넥터 초기화
        start_phase(Phase.CONNECTION, f"{account_display} API 연결")
        from support.api_connector import get_api_connector
        api = await get_api_connector(account_type)
        
        if not api:
            clean_log("API 연결 실패", "ERROR")
            end_phase(Phase.CONNECTION, False)
            return
        
        clean_log("API 연결 성공", "SUCCESS")
        end_phase(Phase.CONNECTION, True)
        
        # 분리된 매매 조정자 초기화
        from support.separated_trading_coordinator import get_separated_trading_coordinator
        coordinator = get_separated_trading_coordinator(api, account_type)
        
        # 실행 유형 선택
        print(f"\n[ {account_display} 사용자 지정종목 매매 ]")
        print("1. 수동 실행 (즉시)")
        print("2. 점심시간 실행 (12:00-12:30)")
        print("3. 상태 확인만")
        print("-" * 40)
        
        while True:
            exec_choice = input("실행 유형을 선택하세요 (1, 2, 또는 3): ").strip()
            if exec_choice in ["1", "2", "3"]:
                break
            else:
                print("잘못된 선택입니다. 1, 2, 또는 3을 입력하세요.")
        
        if exec_choice == "1":
            # 수동 즉시 실행
            print(f"\n[{account_display}] 사용자 지정종목 수동 매매를 시작합니다...")
            result = await coordinator.execute_user_designated_trading_only("MANUAL")
            
            if result['success']:
                print("✅ 사용자 지정종목 매매 완료!")
                trading_result = result.get('result', {})
                print(f"📊 분석된 종목: {trading_result.get('analyzed_stocks', 0)}개")
                print(f"💰 실행된 거래: {trading_result.get('executed_trades', 0)}건")
                print(f"⏳ 대기 주문: {trading_result.get('pending_orders', 0)}건")
            else:
                print(f"❌ 매매 실행 실패: {result.get('error', 'Unknown')}")
        
        elif exec_choice == "2":
            # 점심시간 실행
            is_lunch = await coordinator.is_lunch_time_for_user_designated()
            if is_lunch:
                print(f"\n[{account_display}] 점심시간 사용자 지정종목 매매를 시작합니다...")
                result = await coordinator.execute_user_designated_trading_only("LUNCH")
                
                if result['success']:
                    print("✅ 점심시간 매매 완료!")
                    trading_result = result.get('result', {})
                    print(f"📊 분석된 종목: {trading_result.get('analyzed_stocks', 0)}개")
                    print(f"💰 실행된 거래: {trading_result.get('executed_trades', 0)}건")
                    print(f"⏳ 대기 주문: {trading_result.get('pending_orders', 0)}건")
                else:
                    print(f"❌ 점심시간 매매 실패: {result.get('error', 'Unknown')}")
            else:
                print("⚠️  현재 점심시간(12:00-12:30)이 아닙니다.")
                print("점심시간에 다시 실행해주세요.")
        
        elif exec_choice == "3":
            # 상태 확인
            status = await coordinator.get_trading_status()
            print(f"\n[{account_display}] 매매 시스템 상태:")
            print(f"- 일반 단타매매 활성: {'✅' if status['day_trading_active'] else '❌'}")
            print(f"- 사용자 지정종목 활성: {'✅' if status['user_designated_active'] else '❌'}")
            
            if status['last_user_designated_time']:
                print(f"- 마지막 사용자 지정종목 실행: {status['last_user_designated_time']}")
            else:
                print("- 마지막 사용자 지정종목 실행: 없음")
        
        # 리소스 정리
        await coordinator.cleanup_resources()
        
        print("\n" + "=" * 80)
        print("사용자 지정종목 독립 매매 시스템 종료")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n시스템 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())