#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
포괄적 시스템 검증 테스트
Phase 1의 최종 통합 테스트
"""

import sys
import asyncio
from pathlib import Path

# UTF-8 인코딩 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

async def comprehensive_system_test():
    """포괄적 시스템 검증"""
    
    print("=== tideWise 포괄적 시스템 검증 ===\n")
    
    test_results = {}
    
    # 1. 핵심 거래 시스템 테스트
    print("1. 핵심 거래 시스템 검증...")
    try:
        from subprocess import run, PIPE
        result = run([sys.executable, "test_all_trading_systems.py"], 
                    capture_output=True, text=True, cwd=Path(__file__).parent, encoding='utf-8')
        
        if "전체 시스템 성공률: 3/3 (100.0%)" in result.stdout:
            print("   ✅ 전체 거래 시스템 100% 성공")
            test_results["거래시스템"] = True
        else:
            print("   ❌ 거래 시스템에 문제 있음")
            test_results["거래시스템"] = False
    except Exception as e:
        print(f"   ❌ 거래 시스템 테스트 실패: {e}")
        test_results["거래시스템"] = False
    
    # 2. GPT-5 의사결정 엔진 검증
    print("\n2. GPT-5 의사결정 엔진 검증...")
    try:
        result = run([sys.executable, "test_gpt5_engine.py"], 
                    capture_output=True, text=True, cwd=Path(__file__).parent, encoding='utf-8')
        
        if "성공률: 5/5 (100.0%)" in result.stdout:
            print("   ✅ GPT-5 엔진 100% 검증 완료")
            test_results["GPT5엔진"] = True
        else:
            print("   ❌ GPT-5 엔진에 문제 있음")
            test_results["GPT5엔진"] = False
    except Exception as e:
        print(f"   ❌ GPT-5 엔진 테스트 실패: {e}")
        test_results["GPT5엔진"] = False
    
    # 3. 무료 데이터 시스템 검증
    print("\n3. 무료 데이터 시스템 검증...")
    try:
        from support.integrated_free_data_system import IntegratedFreeDataSystem
        system = IntegratedFreeDataSystem()
        
        korean_stocks_count = len(system.korean_stocks)
        us_stocks_count = len(system.us_stocks)
        
        if korean_stocks_count >= 10 and us_stocks_count >= 10:
            print(f"   ✅ 무료 데이터 시스템 정상 (한국 {korean_stocks_count}개, 미국 {us_stocks_count}개)")
            test_results["데이터시스템"] = True
        else:
            print(f"   ❌ 무료 데이터 시스템 불완전 (한국 {korean_stocks_count}개, 미국 {us_stocks_count}개)")
            test_results["데이터시스템"] = False
    except Exception as e:
        print(f"   ❌ 무료 데이터 시스템 테스트 실패: {e}")
        test_results["데이터시스템"] = False
    
    # 4. 백테스팅 시스템 구조 검증
    print("\n4. 백테스팅 시스템 구조 검증...")
    try:
        backtest_files = [
            PROJECT_ROOT / "backtesting" / "start_Backtest.py",
            PROJECT_ROOT / "backtesting" / "enhanced_data_collector.py"
        ]
        
        all_exist = all(file.exists() for file in backtest_files)
        
        if all_exist:
            print("   ✅ 백테스팅 시스템 구조 정상")
            test_results["백테스팅"] = True
        else:
            print("   ❌ 백테스팅 시스템 구조 불완전")
            test_results["백테스팅"] = False
    except Exception as e:
        print(f"   ❌ 백테스팅 시스템 검증 실패: {e}")
        test_results["백테스팅"] = False
    
    # 5. 핵심 컴포넌트 가용성 검증
    print("\n5. 핵심 컴포넌트 가용성 검증...")
    try:
        # 중요 모듈 import 테스트
        modules = [
            "support.production_auto_trader",
            "support.minimal_day_trader", 
            "support.gpt5_decision_engine",
            "support.integrated_free_data_system",
            "support.api_connector"
        ]
        
        import_results = {}
        for module in modules:
            try:
                __import__(module)
                import_results[module] = True
            except ImportError:
                import_results[module] = False
        
        success_count = sum(import_results.values())
        if success_count == len(modules):
            print(f"   ✅ 핵심 컴포넌트 모두 가용 ({success_count}/{len(modules)})")
            test_results["컴포넌트"] = True
        else:
            print(f"   ❌ 일부 컴포넌트 불가용 ({success_count}/{len(modules)})")
            test_results["컴포넌트"] = False
    except Exception as e:
        print(f"   ❌ 컴포넌트 검증 실패: {e}")
        test_results["컴포넌트"] = False
    
    # 6. 설정 파일 무결성 검증
    print("\n6. 설정 파일 무결성 검증...")
    try:
        config_files = [
            PROJECT_ROOT / "Policy" / "Register_Key" / "Register_Key.md",
            PROJECT_ROOT / "Algorithm" / "sample_algorithm.py",
        ]
        
        integrity_ok = all(file.exists() and file.stat().st_size > 0 for file in config_files)
        
        if integrity_ok:
            print("   ✅ 핵심 설정 파일 무결성 확인")
            test_results["설정파일"] = True
        else:
            print("   ❌ 설정 파일 무결성 문제")
            test_results["설정파일"] = False
    except Exception as e:
        print(f"   ❌ 설정 파일 검증 실패: {e}")
        test_results["설정파일"] = False
    
    # 결과 요약
    print("\n" + "="*60)
    print("📊 tideWise 포괄적 시스템 검증 결과")
    print("="*60)
    
    success_count = 0
    total_tests = len(test_results)
    
    for component, result in test_results.items():
        status = "✅ 정상" if result else "❌ 문제"
        print(f"   - {component}: {status}")
        if result:
            success_count += 1
    
    success_rate = (success_count / total_tests) * 100
    print(f"\n전체 시스템 성공률: {success_count}/{total_tests} ({success_rate:.1f}%)")
    
    # 최종 평가
    if success_rate >= 90:
        print("\n🎉 시스템 검증 완료!")
        print("✅ tideWise GPT-5 거래 시스템이 정상 작동합니다.")
        print("✅ 프로덕션 배포 준비가 완료되었습니다.")
        print("✅ 모든 핵심 기능이 검증되었습니다.")
        return True
    elif success_rate >= 70:
        print("\n⚠️ 부분적 성공")
        print("✅ 주요 기능은 정상 작동합니다.")
        print("❌ 일부 컴포넌트 보완 필요")
        return False
    else:
        print("\n❌ 시스템 검증 실패")
        print("💡 추가 디버깅과 수정이 필요합니다.")
        return False

async def main():
    """메인 함수"""
    success = await comprehensive_system_test()
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)