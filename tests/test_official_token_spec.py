#!/usr/bin/env python3
"""
KIS 공식 API 스펙 토큰 발급 테스트
한국투자증권 공식 OAuth 스펙에 맞는 토큰 발급 테스트
"""

import sys
import asyncio
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "KIS_API_Test"))

async def test_official_token_spec():
    """KIS 공식 API 스펙으로 토큰 발급 테스트"""
    print("=== KIS 공식 API 스펙 토큰 발급 테스트 ===")
    
    try:
        # Enhanced Token Manager import (KIS_API_Test 폴더에서)
        from enhanced_token_manager import create_enhanced_token_manager
        
        print("[STEP 1] Enhanced Token Manager 생성 (MOCK 계정)...")
        
        # 모의투자용 Enhanced Token Manager 생성
        token_manager = create_enhanced_token_manager("MOCK")
        
        print("[OK] Enhanced Token Manager 생성 성공")
        print(f"   - 계정 타입: {token_manager.account_type}")
        print(f"   - 서버 URL: {token_manager.base_url}")
        
        print("\n[STEP 2] 토큰 발급 테스트...")
        
        # 비동기 토큰 발급 테스트
        try:
            token = await token_manager.get_valid_token_async()
            
            if token:
                print(f"[SUCCESS] 토큰 발급 성공!")
                print(f"   - 토큰: {token[:20]}...")
                print(f"   - 토큰 길이: {len(token)} 문자")
                
                # 건강 상태 확인
                health_status = token_manager.get_health_status()
                
                print(f"\n[STEP 3] 토큰 매니저 상태 확인...")
                print(f"   - 토큰 존재: {health_status['token_status']['exists']}")
                print(f"   - 토큰 유효: {health_status['token_status']['valid']}")
                print(f"   - 성공률: {health_status['performance_stats']['success_rate']}")
                print(f"   - 총 요청: {health_status['performance_stats']['total_requests']}")
                
                return True
            else:
                print("[FAILED] 토큰 발급 실패: 빈 응답")
                return False
                
        except Exception as token_error:
            print(f"[FAILED] 토큰 발급 오류: {token_error}")
            
            # 상세 오류 확인을 위한 건강 상태 체크
            try:
                health_status = token_manager.get_health_status()
                print(f"   - 마지막 오류: {health_status['performance_stats']['last_error']}")
            except Exception:
                pass
                
            return False
            
    except ImportError as import_error:
        print(f"[FAILED] 모듈 import 실패: {import_error}")
        print("KIS_API_Test 폴더의 Enhanced Token Manager를 찾을 수 없습니다.")
        return False
    except Exception as e:
        print(f"[FAILED] 테스트 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    try:
        result = asyncio.run(test_official_token_spec())
        
        print("\n" + "="*50)
        if result:
            print("[SUCCESS] KIS 공식 API 스펙 토큰 발급 테스트 성공!")
            print("Enhanced Token Manager가 정상적으로 작동합니다.")
            sys.exit(0)
        else:
            print("[FAILED] KIS 공식 API 스펙 토큰 발급 테스트 실패!")
            print("토큰 발급에 문제가 있습니다. 설정을 확인하세요.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n사용자에 의해 테스트가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"테스트 실행 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()