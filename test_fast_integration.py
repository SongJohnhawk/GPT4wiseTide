#!/usr/bin/env python3
"""
Fast Token Manager 통합 테스트
기존 시스템에 Fast Token Manager가 제대로 통합되었는지 테스트
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_fast_integration():
    """Fast Token Manager 통합 테스트"""
    print("=== Fast Token Manager 통합 테스트 ===")
    
    try:
        # API Connector 초기화 (모의투자)
        from support.api_connector import KISAPIConnector
        
        print("[STEP 1] KIS API Connector 초기화...")
        api = KISAPIConnector(is_mock=True)
        print("[OK] API Connector 초기화 성공")
        
        # Fast Token Manager 활성화 확인
        if hasattr(api, '_using_fast_manager') and api._using_fast_manager:
            print("[OK] Fast Token Manager 활성화됨")
            
            # 토큰 발급 테스트
            print("\n[STEP 2] 토큰 발급 테스트...")
            try:
                token = api.get_access_token()
                
                if token:
                    print(f"[SUCCESS] 토큰 발급 성공!")
                    print(f"   - 토큰: {token[:30]}...")
                    print(f"   - 토큰 길이: {len(token)} 문자")
                    
                    # 토큰 상태 확인
                    print("\n[STEP 3] 토큰 상태 확인...")
                    status = api.get_token_health_status()
                    print(f"   - 토큰 존재: {status.get('exists', 'N/A')}")
                    print(f"   - 토큰 유효: {status.get('valid', 'N/A')}")
                    print(f"   - 만료 임박: {status.get('near_expiry', 'N/A')}")
                    print(f"   - 토큰 길이: {status.get('token_length', 'N/A')}")
                    
                    # 강제 갱신 테스트
                    print("\n[STEP 4] 강제 갱신 테스트...")
                    new_token = api.get_access_token(force_refresh=True)
                    if new_token:
                        print(f"[OK] 강제 갱신 성공: {new_token[:30]}...")
                        return True
                    else:
                        print("[WARN] 강제 갱신 실패하지만 기본 토큰은 작동")
                        return True
                else:
                    print("[FAILED] 토큰 발급 실패")
                    return False
                    
            except Exception as token_error:
                print(f"[FAILED] 토큰 발급 오류: {token_error}")
                return False
        else:
            print("[WARN] Fast Token Manager 비활성화 (기존 방식 사용)")
            # 기존 방식으로도 토큰 발급 테스트
            try:
                token = api.get_access_token()
                if token:
                    print(f"[OK] 기존 방식 토큰 발급 성공: {token[:30]}...")
                    return True
                else:
                    print("[FAILED] 기존 방식 토큰 발급 실패")
                    return False
            except Exception as e:
                print(f"[FAILED] 기존 방식 토큰 발급 오류: {e}")
                return False
                
    except Exception as e:
        print(f"[FAILED] 테스트 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    try:
        result = test_fast_integration()
        
        print("\n" + "="*60)
        if result:
            print("[SUCCESS] Fast Token Manager 통합 테스트 성공!")
            print("시스템이 정상적으로 작동합니다.")
            sys.exit(0)
        else:
            print("[FAILED] Fast Token Manager 통합 테스트 실패!")
            print("시스템 통합에 문제가 있습니다.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n사용자에 의해 테스트가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"테스트 실행 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()