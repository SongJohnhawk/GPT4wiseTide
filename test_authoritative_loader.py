#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AuthoritativeRegisterKeyLoader 테스트 스크립트
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_authoritative_loader():
    """AuthoritativeRegisterKeyLoader 기본 테스트"""
    print("=== AuthoritativeRegisterKeyLoader 테스트 시작 ===")
    
    try:
        from support.authoritative_register_key_loader import get_authoritative_loader
        
        # 로더 인스턴스 생성
        loader = get_authoritative_loader()
        print("[SUCCESS] AuthoritativeRegisterKeyLoader 인스턴스 생성 성공")
        
        # 캐시 상태 확인
        cache_info = loader.get_cache_info()
        print(f"[INFO] 캐시 정보: {cache_info}")
        
        # 실전투자 설정 로드 테스트
        try:
            real_config = loader.get_fresh_config("REAL")
            print(f"[SUCCESS] 실전투자 설정 로드 성공 (APP_KEY: {real_config.get('app_key', '')[:8]}...)")
        except Exception as e:
            print(f"[ERROR] 실전투자 설정 로드 실패: {e}")
        
        # 모의투자 설정 로드 테스트  
        try:
            mock_config = loader.get_fresh_config("MOCK")
            print(f"[SUCCESS] 모의투자 설정 로드 성공 (APP_KEY: {mock_config.get('app_key', '')[:8]}...)")
        except Exception as e:
            print(f"[ERROR] 모의투자 설정 로드 실패: {e}")
        
        # URL 설정 로드 테스트
        try:
            urls = loader.get_fresh_urls()
            print(f"[SUCCESS] URL 설정 로드 성공")
            print(f"   실전투자 REST: {urls.get('real_rest')}")
            print(f"   모의투자 REST: {urls.get('mock_rest')}")
        except Exception as e:
            print(f"[ERROR] URL 설정 로드 실패: {e}")
        
        # 텔레그램 설정 로드 테스트
        try:
            telegram = loader.get_fresh_telegram_config() 
            bot_token = telegram.get('bot_token', '')
            chat_id = telegram.get('chat_id', '')
            if bot_token and chat_id:
                print(f"[SUCCESS] 텔레그램 설정 로드 성공 (Bot Token: {bot_token[:10]}...)")
            else:
                print(f"[WARNING] 텔레그램 설정 없음 (선택사항)")
        except Exception as e:
            print(f"[ERROR] 텔레그램 설정 로드 실패: {e}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] AuthoritativeRegisterKeyLoader 테스트 실패: {e}")
        return False

def test_server_connectivity():
    """서버 연결 상태 테스트"""
    print("\n=== 서버 연결 상태 테스트 시작 ===")
    
    try:
        from support.authoritative_register_key_loader import get_authoritative_loader
        
        loader = get_authoritative_loader()
        
        # 실전투자 서버 연결 테스트
        print("\n[실전투자 서버 연결 테스트]")
        real_result = loader.test_server_connectivity("REAL")
        if real_result["success"]:
            print(f"[SUCCESS] 실전투자 서버 연결 성공 ({real_result['response_time']}ms)")
        else:
            error_type = real_result["error_type"]
            error_msg = real_result["error_message"]
            if error_type == "config":
                print(f"[CONFIG ERROR] 설정 오류: {error_msg}")
            elif error_type == "server":
                print(f"[SERVER ERROR] 서버 오류: {error_msg}")
            elif error_type == "network":
                print(f"[NETWORK ERROR] 네트워크 오류: {error_msg}")
            else:
                print(f"[ERROR] 알 수 없는 오류: {error_msg}")
        
        # 모의투자 서버 연결 테스트  
        print("\n[모의투자 서버 연결 테스트]")
        mock_result = loader.test_server_connectivity("MOCK")
        if mock_result["success"]:
            print(f"[SUCCESS] 모의투자 서버 연결 성공 ({mock_result['response_time']}ms)")
        else:
            error_type = mock_result["error_type"]
            error_msg = mock_result["error_message"]
            if error_type == "config":
                print(f"[CONFIG ERROR] 설정 오류: {error_msg}")
            elif error_type == "server":
                print(f"[SERVER ERROR] 서버 오류: {error_msg}")
            elif error_type == "network":
                print(f"[NETWORK ERROR] 네트워크 오류: {error_msg}")
            else:
                print(f"[ERROR] 알 수 없는 오류: {error_msg}")
        
        return real_result["success"] or mock_result["success"]
        
    except Exception as e:
        print(f"[ERROR] 서버 연결 테스트 실패: {e}")
        return False

def test_api_connector_integration():
    """API Connector와 AuthoritativeRegisterKeyLoader 통합 테스트"""
    print("\n=== API Connector 통합 테스트 시작 ===")
    
    try:
        from support.api_connector import KISAPIConnector
        
        # 모의투자 API 커넥터 생성 테스트
        try:
            mock_connector = KISAPIConnector(is_mock=True)
            print(f"[SUCCESS] 모의투자 API Connector 생성 성공")
            print(f"   Base URL: {mock_connector.base_url}")
        except Exception as e:
            print(f"[ERROR] 모의투자 API Connector 생성 실패: {e}")
            return False
        
        # 실전투자 API 커넥터 생성 테스트  
        try:
            real_connector = KISAPIConnector(is_mock=False)
            print(f"[SUCCESS] 실전투자 API Connector 생성 성공")
            print(f"   Base URL: {real_connector.base_url}")
        except Exception as e:
            print(f"[ERROR] 실전투자 API Connector 생성 실패: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] API Connector 통합 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    success1 = test_authoritative_loader()
    success2 = test_api_connector_integration()
    success3 = test_server_connectivity()
    
    if success1 and success2:
        print(f"\n[SUCCESS] 핵심 테스트 성공! (서버 연결: {'성공' if success3 else '실패'})")
        sys.exit(0)
    else:
        print("\n[ERROR] 핵심 테스트 실패!")
        sys.exit(1)