#!/usr/bin/env python3
"""
Enhanced Token Manager 통합 테스트 (간소화 버전)
기본 연결과 토큰 발급만 테스트
"""

import sys
import asyncio
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

async def test_basic_api_connection():
    """기본 API 연결 및 토큰 테스트"""
    print("=== Enhanced Token Manager 기본 연결 테스트 ===")
    
    try:
        # API Connector 초기화 (모의투자)
        from support.api_connector import KISAPIConnector
        
        print("[STEP 1] API Connector 초기화 중...")
        api = KISAPIConnector(is_mock=True)
        print("[OK] API Connector 초기화 성공")
        
        # Enhanced Token Manager 사용 확인
        if hasattr(api, '_using_enhanced_manager') and api._using_enhanced_manager:
            print("[OK] Enhanced Token Manager 활성화됨")
            
            # 토큰 매니저 건강 상태 확인
            if hasattr(api, 'get_token_health_status'):
                try:
                    health_status = api.get_token_health_status()
                    print(f"[OK] 토큰 매니저 상태: {health_status}")
                except Exception as health_error:
                    print(f"[WARN] 건강 상태 확인 오류: {health_error}")
        else:
            print("[WARN] Enhanced Token Manager 비활성화 (기존 토큰 매니저 사용)")
        
        print("\n[STEP 2] 토큰 발급 테스트...")
        try:
            # 토큰 획득 시도 (짧은 타임아웃)
            token = api.get_access_token()
            if token:
                print(f"[OK] 토큰 발급 성공: {token[:20]}...")
                
                # 성능 통계 확인
                if hasattr(api, 'log_token_performance'):
                    try:
                        performance_stats = api.log_token_performance()
                        if performance_stats:
                            print(f"[STATS] 성능 통계: {performance_stats}")
                    except Exception:
                        pass
                
                return True
            else:
                print("[FAIL] 토큰 발급 실패: 빈 토큰")
                return False
                
        except Exception as token_error:
            print(f"[FAIL] 토큰 발급 오류: {token_error}")
            return False
            
    except Exception as e:
        print(f"[FAIL] API 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    try:
        result = asyncio.run(test_basic_api_connection())
        
        print("\n" + "="*50)
        if result:
            print("[SUCCESS] Enhanced Token Manager 통합 테스트 성공!")
            print("시스템이 정상적으로 작동합니다.")
            sys.exit(0)
        else:
            print("[FAILED] Enhanced Token Manager 통합 테스트 실패!")
            print("문제를 확인하고 수정이 필요합니다.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n사용자에 의해 테스트가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"테스트 실행 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()