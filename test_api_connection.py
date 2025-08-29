#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.token_auto_refresher import TokenAutoRefresher
from support.authoritative_register_key_loader import get_authoritative_loader

async def test_api_connections():
    """API 연결 및 토큰 발급 테스트"""
    print("=" * 50)
    print("API 연결 상태 검증")
    print("=" * 50)
    
    try:
        # 1. API 설정 로드
        print("\n1. API 설정 로드...")
        loader = get_authoritative_loader()
        
        real_config = loader.get_fresh_config("REAL")
        mock_config = loader.get_fresh_config("MOCK")
        urls = loader.get_fresh_urls()
        
        print(f"   실전투자 APP KEY: {'OK' if real_config.get('app_key') else 'MISSING'}")
        print(f"   모의투자 APP KEY: {'OK' if mock_config.get('app_key') else 'MISSING'}")
        print(f"   API URLs: {'OK' if urls else 'MISSING'}")
        
        # 2. TokenAutoRefresher 초기화
        print("\n2. 토큰 시스템 초기화...")
        refresher = TokenAutoRefresher()
        refresher.api_urls = {
            'real': urls.get('real_rest'),
            'mock': urls.get('mock_rest')
        }
        
        # 3. 4개 토큰 발급 시도
        print("\n3. 토큰 발급 시도...")
        success = await refresher.refresh_all_tokens(force_refresh=True)
        
        # 4. 결과 확인
        readiness = refresher.validate_system_readiness()
        print(f"\n4. 결과: {readiness['readiness_ratio']}")
        
        if readiness['ready']:
            print("API 연결 성공")
            return True
        else:
            print(f"API 연결 실패: {readiness['missing_tokens']}")
            return False
            
    except Exception as e:
        print(f"API 테스트 오류: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_api_connections())
    print("API 테스트 완료" if success else "API 테스트 실패")