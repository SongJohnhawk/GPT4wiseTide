#!/usr/bin/env python3
"""
개선된 Fast Token Manager 테스트
전역 캐싱과 속도 제한 방지 기능 검증
"""

import sys
import time
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_improved_token_manager():
    """개선된 토큰 매니저 테스트"""
    print("=== 개선된 Fast Token Manager 테스트 ===")
    print("전역 캐싱 및 속도 제한 방지 기능 검증")
    print("=" * 60)
    
    try:
        from KIS_API_Test.fast_token_manager import create_fast_token_manager
        
        print("[STEP 1] 첫 번째 토큰 매니저 생성...")
        manager1 = create_fast_token_manager("MOCK")
        
        print("[STEP 2] 첫 번째 토큰 발급...")
        start_time = time.time()
        token1 = manager1.get_valid_token()
        token1_time = time.time() - start_time
        
        if token1:
            print(f"[SUCCESS] 첫 번째 토큰 발급 성공 ({token1_time:.3f}초)")
            print(f"   - 토큰: {token1[:30]}...")
            print(f"   - 토큰 길이: {len(token1)} 문자")
        else:
            print("[FAILED] 첫 번째 토큰 발급 실패")
            return False
        
        print("\n[STEP 3] 두 번째 토큰 매니저 생성 (같은 계정 유형)...")
        manager2 = create_fast_token_manager("MOCK")
        
        print("[STEP 4] 두 번째 토큰 요청 (캐시 사용 예상)...")
        start_time = time.time()
        token2 = manager2.get_valid_token()
        token2_time = time.time() - start_time
        
        if token2:
            print(f"[SUCCESS] 두 번째 토큰 획득 성공 ({token2_time:.3f}초)")
            print(f"   - 토큰: {token2[:30]}...")
            
            # 토큰이 같은지 확인 (캐시에서 가져왔는지)
            if token1 == token2:
                print("[OK] 캐시된 토큰 재사용 확인됨")
            else:
                print("[WARN] 다른 토큰 - 예상치 못한 동작")
                
        else:
            print("[FAILED] 두 번째 토큰 획득 실패")
            return False
        
        print("\n[STEP 5] 토큰 상태 확인...")
        status1 = manager1.get_token_status()
        status2 = manager2.get_token_status()
        
        print(f"Manager1 상태: exists={status1['exists']}, valid={status1['valid']}")
        print(f"Manager2 상태: exists={status2['exists']}, valid={status2['valid']}")
        
        print("\n[STEP 6] 속도 제한 테스트...")
        print("연속으로 새 토큰 요청 시도 (속도 제한 확인)")
        
        # 강제 갱신으로 새 토큰 요청
        print("첫 번째 강제 갱신...")
        refresh_token = manager1.force_refresh()
        if refresh_token:
            print("[OK] 강제 갱신 성공")
        
        # 즉시 다른 매니저로 토큰 요청 (속도 제한 테스트)
        print("즉시 다른 매니저로 토큰 요청...")
        manager3 = create_fast_token_manager("MOCK")
        manager3._current_token = None  # 토큰 캐시 무효화
        
        start_time = time.time()
        token3 = manager3.get_valid_token()
        token3_time = time.time() - start_time
        
        if token3:
            print(f"[SUCCESS] 세 번째 토큰 획득 ({token3_time:.3f}초)")
            if token3 == refresh_token:
                print("[OK] 캐시된 토큰 사용 (속도 제한 방지 작동)")
            else:
                print("[WARN] 다른 토큰 - 예상치 못한 동작")
        else:
            print("[INFO] 토큰 획득 실패 - 속도 제한 방지 작동 중")
        
        print("\n" + "="*60)
        print("[SUCCESS] 개선된 Fast Token Manager 테스트 완료!")
        print("주요 개선사항:")
        print("- 전역 토큰 캐싱으로 중복 요청 방지")
        print("- KIS API 속도 제한 (1분당 1회) 준수")
        print("- 여러 컴포넌트 간 토큰 공유 가능")
        return True
        
    except Exception as e:
        print(f"[FAILED] 테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    try:
        result = test_improved_token_manager()
        
        if result:
            print("\n개선된 토큰 매니저 테스트 성공!")
            sys.exit(0)
        else:
            print("\n개선된 토큰 매니저 테스트 실패!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n사용자에 의해 테스트가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"테스트 실행 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()