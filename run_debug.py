#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tideWise 자동매매 시스템 - 디버그 모드
GPT-5 AI 통합 버전

Features:
- 시스템 진단 및 테스트
- API 연결 테스트
- 알고리즘 검증
- 데이터 수집 테스트
- GPT-5 AI 기능 테스트
"""

import sys
import os
import asyncio
from pathlib import Path

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.menu_manager import MenuManager
from support.system_manager import SystemManager

def show_main_menu():
    """메인 메뉴 표시"""
    print("\n" + "="*60)
    print("🔧 tideWise 디버그 모드 (GPT-5 통합)")
    print("="*60)
    print("1. 시스템 상태 확인")
    print("2. API 연결 테스트")
    print("3. 데이터 수집 테스트")
    print("4. 알고리즘 로딩 테스트")
    print("5. GPT-5 AI 기능 테스트")
    print("6. 종합 시스템 진단")
    print("7. 모의투자 거래 테스트")
    print("8. 실계좌 거래 테스트")
    print("9. 프로그램 종료")
    print("="*60)

async def main():
    """메인 함수"""
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).parent
    system_manager = SystemManager(PROJECT_ROOT)
    
    while True:
        show_main_menu()
        
        try:
            choice = input("\n선택하세요 (1-9): ").strip()
            
            if choice == "1":
                await system_manager.check_system_status()
            elif choice == "2":
                await system_manager.test_api_connection()
            elif choice == "3":
                await system_manager.test_data_collection()
            elif choice == "4":
                await system_manager.test_algorithm_loading()
            elif choice == "5":
                await system_manager.test_gpt5_functions()
            elif choice == "6":
                await system_manager.run_comprehensive_diagnosis()
            elif choice == "7":
                await system_manager.test_mock_trading()
            elif choice == "8":
                await system_manager.test_real_trading()
            elif choice == "9":
                print("프로그램을 종료합니다.")
                break
            else:
                print("잘못된 선택입니다. 다시 선택해주세요.")
                
        except KeyboardInterrupt:
            print("\n프로그램이 중단되었습니다.")
            break
        except Exception as e:
            print(f"오류 발생: {str(e)}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())