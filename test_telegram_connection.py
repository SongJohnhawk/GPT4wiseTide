#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
텔레그램 연결 테스트 스크립트
실제 메시지 발송으로 연결 상태 확인
"""

import sys
import asyncio
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.telegram_notifier import TelegramNotifier
from support.authoritative_register_key_loader import get_authoritative_loader


async def test_telegram_connection():
    """텔레그램 연결 테스트"""
    print("=" * 60)
    print("텔레그램 연결 테스트 시작")
    print("=" * 60)
    
    try:
        # 1. Register_Key.md에서 텔레그램 설정 로드
        print("\n1. 텔레그램 설정 로드 중...")
        loader = get_authoritative_loader()
        telegram_config = loader.get_fresh_telegram_config()
        
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('chat_id')
        
        print(f"   봇 토큰: {'설정됨' if bot_token and not bot_token.startswith('[여기에') else '설정되지 않음'}")
        print(f"   채팅 ID: {'설정됨' if chat_id and not chat_id.startswith('[여기에') else '설정되지 않음'}")
        
        if not bot_token or bot_token.startswith('[여기에'):
            print("\n[ERROR] 텔레그램 봇 토큰이 설정되지 않았습니다.")
            print("Policy/Register_Key/Register_Key.md 파일에서 텔레그램 설정을 확인하세요.")
            return False
        
        if not chat_id or chat_id.startswith('[여기에'):
            print("\n[ERROR] 텔레그램 채팅 ID가 설정되지 않았습니다.")
            print("Policy/Register_Key/Register_Key.md 파일에서 텔레그램 설정을 확인하세요.")
            return False
        
        # 2. TelegramNotifier 초기화
        print("\n2. 텔레그램 알림기 초기화 중...")
        notifier = TelegramNotifier()
        
        init_success = await notifier.initialize()
        if not init_success:
            print("[ERROR] 텔레그램 알림기 초기화 실패")
            return False
        
        print(f"   초기화 상태: {'성공' if notifier.enabled else '실패'}")
        
        # 3. 테스트 메시지 발송
        print("\n3. 테스트 메시지 발송 중...")
        print("   [TELEGRAM] 텔레그램으로 테스트 메시지를 발송합니다...")
        
        test_message = """<b>tideWise 시스템 테스트</b>
        
시간: 2025-08-23 03:30:00 KST
테스트 유형: 텔레그램 연결 테스트
상태: 정상 작동

이 메시지가 수신되면 텔레그램 연결이 정상적으로 작동하고 있습니다."""

        send_success = await notifier.send_message(test_message)
        
        if send_success:
            print("   [OK] 텔레그램 메시지 발송 성공!")
            print("\n" + "=" * 60)
            print("[TELEGRAM] 핸드폰에서 텔레그램 메시지를 확인해주세요.")
            print("메시지를 받으셨으면 'y' 또는 'yes'를 입력하세요.")
            print("메시지를 받지 못하셨으면 'n' 또는 'no'를 입력하세요.")
            print("=" * 60)
            
            user_input = input("텔레그램 메시지를 받으셨나요? (y/n): ").strip().lower()
            
            if user_input in ['y', 'yes', 'ㅇ']:
                print("\n[SUCCESS] 텔레그램 연결 테스트 성공!")
                print("tideWise 시스템의 텔레그램 알림이 정상적으로 작동합니다.")
                return True
            else:
                print("\n[FAILED] 텔레그램 메시지 수신 실패")
                print("다음 사항들을 확인해주세요:")
                print("1. 텔레그램 봇과 채팅방 설정")
                print("2. 네트워크 연결 상태")
                print("3. Register_Key.md 파일의 텔레그램 설정")
                return False
        else:
            print("   [ERROR] 텔레그램 메시지 발송 실패")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] 텔레그램 테스트 중 오류 발생: {e}")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(test_telegram_connection())
        if success:
            print("\n텔레그램 시스템이 정상적으로 작동합니다.")
        else:
            print("\n텔레그램 시스템에 문제가 있습니다.")
            print("설정을 확인하고 다시 시도해주세요.")
    except KeyboardInterrupt:
        print("\n테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n예상치 못한 오류: {e}")