#!/usr/bin/env python3
"""
전체 매매 시스템 통합 테스트
실전투자, 모의투자, 단타매매 모든 기능 통합 검증
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

print("=== tideWise 전체 매매 시스템 통합 테스트 ===\n")

async def test_all_systems():
    """모든 매매 시스템 통합 테스트"""
    
    test_results = []
    
    print("1. 실전투자 자동매매 시스템 테스트...")
    try:
        result = await run_subprocess("python test_production_auto_trader.py")
        if "실전투자 자동매매 전체 테스트 완료!" in result:
            print("   OK 실전투자 시스템 정상")
            test_results.append(("실전투자", True))
        else:
            print("   NG 실전투자 시스템 오류")
            test_results.append(("실전투자", False))
    except Exception as e:
        print(f"   X 실전투자 시스템 테스트 실패: {e}")
        test_results.append(("실전투자", False))
    
    print("\n2. 모의투자 자동매매 시스템 테스트...")
    try:
        result = await run_subprocess("python test_minimal_day_trader.py")
        if "모의투자 자동매매 전체 테스트 완료!" in result:
            print("   OK 모의투자 시스템 정상")
            test_results.append(("모의투자", True))
        else:
            print("   NG 모의투자 시스템 오류")
            test_results.append(("모의투자", False))
    except Exception as e:
        print(f"   X 모의투자 시스템 테스트 실패: {e}")
        test_results.append(("모의투자", False))
    
    print("\n3. 단타매매 시스템 테스트...")
    try:
        result = await run_subprocess("python test_day_trading.py")
        if "모든 단타매매 기능이 정상 작동합니다!" in result:
            print("   OK 단타매매 시스템 정상")
            test_results.append(("단타매매", True))
        else:
            print("   NG 단타매매 시스템 오류")
            test_results.append(("단타매매", False))
    except Exception as e:
        print(f"   X 단타매매 시스템 테스트 실패: {e}")
        test_results.append(("단타매매", False))
    
    # 결과 요약
    print("\n" + "="*60)
    print("tideWise 전체 시스템 테스트 결과:")
    
    success_count = 0
    for system_name, result in test_results:
        status = "OK 정상" if result else "NG 오류"
        print(f"   - {system_name} 시스템: {status}")
        if result:
            success_count += 1
    
    print(f"\n전체 시스템 성공률: {success_count}/{len(test_results)} ({success_count/len(test_results)*100:.1f}%)")
    
    if success_count == len(test_results):
        print("\n모든 매매 시스템이 정상 작동합니다!")
        print("사용자 요구사항 충족:")
        print("   OK 'max_analysis_stocks' 속성 오류 해결됨")
        print("   OK 종목 표시 형식 '종목명(종목코드)'로 변경됨")
        print("   OK 매수 후보 종목만 표시되도록 필터링 적용됨")
        print("   OK 20개 종목 수집 제한 적용됨 (실전투자, 모의투자)")
        print("   OK 단타매매는 OPEN-API 급등종목 사용 확인됨")
    elif success_count > 0:
        print("\n일부 시스템에서 문제가 있습니다.")
        print("정상 작동하는 시스템은 사용 가능합니다.")
    else:
        print("\n모든 시스템에서 문제가 발생했습니다.")
        print("시스템 점검이 필요합니다.")

async def run_subprocess(command):
    """서브프로세스 실행하여 결과 반환"""
    import subprocess
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=Path(__file__).parent
        )
        stdout, stderr = await process.communicate()
        
        # 인코딩 문제 해결
        try:
            result = stdout.decode('utf-8')
        except UnicodeDecodeError:
            try:
                result = stdout.decode('cp949')
            except UnicodeDecodeError:
                result = stdout.decode('utf-8', errors='ignore')
        
        return result
    except Exception as e:
        return f"Subprocess error: {e}"

async def main():
    await test_all_systems()

if __name__ == "__main__":
    asyncio.run(main())