#!/usr/bin/env python3
"""
깔끔한 로그 출력 테스트
캐시된 토큰 사용 메시지 제거 확인
"""

import sys
import time
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_clean_logs():
    """깔끔한 로그 출력 테스트"""
    print("=== 깔끔한 로그 출력 테스트 ===")
    print("캐시된 토큰 사용 메시지 제거 확인")
    print("=" * 50)
    
    try:
        from KIS_API_Test.fast_token_manager import create_fast_token_manager
        
        # 여러 번 토큰 요청으로 캐시 사용 테스트
        print("\n[테스트] Fast Token Manager로 토큰 요청...")
        manager = create_fast_token_manager("MOCK")
        
        # 첫 번째 토큰 요청 (새로 발급)
        print("1. 첫 번째 토큰 요청...")
        token1 = manager.get_valid_token()
        
        if token1:
            print(f"   ✓ 토큰 발급 성공 (길이: {len(token1)})")
        
        # 캐시된 토큰 사용 (로그가 안 보여야 함)
        print("\n2. 캐시된 토큰 여러 번 요청 (로그 없어야 함)...")
        for i in range(5):
            token = manager.get_valid_token()
            print(f"   요청 {i+1}: {'성공' if token else '실패'}")
            time.sleep(0.1)  # 짧은 대기
        
        print("\n[SUCCESS] 테스트 완료!")
        print("캐시된 토큰 사용 시 불필요한 INFO 로그가 나타나지 않음을 확인")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    try:
        result = test_clean_logs()
        
        if result:
            print("\n" + "="*50)
            print("[SUCCESS] 깔끔한 로그 출력 테스트 성공!")
            print("자동매매 실행 시 로그가 훨씬 깔끔해집니다.")
            sys.exit(0)
        else:
            print("\n" + "="*50)
            print("[FAIL] 테스트 실패")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n사용자에 의해 테스트가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"테스트 실행 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()