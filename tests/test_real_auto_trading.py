#!/usr/bin/env python3
"""
실제 자동매매 시스템 실행 테스트
Fast Token Manager 적용된 실제 자동매매 시스템 완전 테스트
"""

import sys
import asyncio
import time
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

async def test_real_auto_trading():
    """실제 자동매매 시스템 실행 테스트"""
    print("=== 실제 자동매매 시스템 실행 테스트 ===")
    print("Fast Token Manager 적용된 완전한 자동매매 실행")
    print("=" * 60)
    
    try:
        # run.py의 모의투자 함수 직접 호출
        from run import run_mock_trading
        
        print("[실행] 모의투자 자동매매 시작...")
        print("주의: 실제 매매 로직이 실행됩니다. 모의투자 계정 사용.")
        print("-" * 60)
        
        start_time = time.time()
        
        # 실제 자동매매 실행 (타임아웃 5분)
        try:
            result = await asyncio.wait_for(run_mock_trading(), timeout=300.0)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            print(f"\n실행 시간: {execution_time:.1f}초")
            
            if result:
                print("\n[SUCCESS] 자동매매 시스템 정상 실행 완료!")
                return True
            else:
                print("\n[FAILED] 자동매매 시스템 실행 실패")
                return False
                
        except asyncio.TimeoutError:
            print("\n[TIMEOUT] 자동매매 시스템 5분 타임아웃")
            print("장기 실행 중이거나 무한 루프 가능성")
            return False
        except KeyboardInterrupt:
            print("\n[INTERRUPTED] 사용자에 의한 중단")
            return True  # 정상 중단은 성공으로 간주
        except Exception as trading_error:
            print(f"\n[ERROR] 자동매매 실행 중 오류: {trading_error}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"[FAILED] 테스트 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    try:
        print("자동매매 시스템 실행을 시작합니다...")
        print("Ctrl+C를 눌러 안전하게 중단할 수 있습니다.")
        print()
        
        result = asyncio.run(test_real_auto_trading())
        
        print("\n" + "="*60)
        if result:
            print("[SUCCESS] 실제 자동매매 시스템 테스트 성공!")
            print("시스템이 정상적으로 작동합니다.")
        else:
            print("[FAILED] 실제 자동매매 시스템 테스트 실패!")
            print("오류가 발생했습니다. 로그를 확인하세요.")
            
        # 백그라운드 프로세스 정리는 별도로 수행
        return result
            
    except KeyboardInterrupt:
        print("\n사용자에 의해 테스트가 중단되었습니다.")
        return True
    except Exception as e:
        print(f"테스트 실행 오류: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)