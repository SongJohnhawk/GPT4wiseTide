#!/usr/bin/env python3
"""
모의투자 자동매매 시스템 통합 테스트
Enhanced Token Manager 적용 후 실제 동작 테스트
"""

import sys
import asyncio
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from run import run_mock_trading

async def test_mock_trading_system():
    """모의투자 시스템 테스트"""
    print("=== 모의투자 자동매매 시스템 통합 테스트 ===")
    print("Enhanced Token Manager 적용 후 실제 동작 테스트")
    print("=" * 60)
    
    try:
        # 모의투자 실행 테스트
        result = await run_mock_trading()
        
        if result:
            print("\n[SUCCESS] 모의투자 시스템 테스트 성공!")
            print("Enhanced Token Manager가 정상적으로 작동합니다.")
        else:
            print("\n[FAILED] 모의투자 시스템 테스트 실패")
            print("오류가 발생했습니다.")
        
        return result
        
    except Exception as e:
        print(f"\n[ERROR] 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    try:
        result = asyncio.run(test_mock_trading_system())
        
        if result:
            print("\n=== 테스트 결과: 성공 ===")
            sys.exit(0)
        else:
            print("\n=== 테스트 결과: 실패 ===")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n사용자에 의해 테스트가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"테스트 실행 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()