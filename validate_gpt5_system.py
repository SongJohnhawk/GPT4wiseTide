#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT-5 시스템 검증 스크립트
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_imports():
    """모듈 임포트 테스트"""
    print("=== GPT-5 시스템 모듈 검증 ===")
    
    modules_to_test = [
        ("무료 데이터 시스템", "support.integrated_free_data_system", "IntegratedFreeDataSystem"),
        ("GPT-5 결정 엔진", "support.gpt5_decision_engine", "GPT5DecisionEngine"),
        ("이벤트 버스", "support.event_bus_system", "EventBusSystem"),
        ("AI 서비스 매니저", "support.ai_service_manager", "AIServiceManager"),
        ("통합 어댑터", "support.tidewise_integration_adapter", "TideWiseIntegrationAdapter"),
        ("뉴스 크롤러", "support.free_news_crawler", "FreeKoreanNewsCrawler"),
        ("감성 분석기", "support.kobert_sentiment_analyzer", "NewssentimentProcessor")
    ]
    
    success_count = 0
    total_count = len(modules_to_test)
    
    for name, module_path, class_name in modules_to_test:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"✓ {name}: 성공")
            success_count += 1
        except ImportError as e:
            print(f"✗ {name}: 실패 - {e}")
        except AttributeError as e:
            print(f"✗ {name}: 클래스 없음 - {e}")
        except Exception as e:
            print(f"✗ {name}: 오류 - {e}")
    
    print(f"\n모듈 검증 결과: {success_count}/{total_count} 성공")
    return success_count, total_count

def test_file_structure():
    """파일 구조 검증"""
    print("\n=== 파일 구조 검증 ===")
    
    required_files = [
        "run_gpt5_trading.py",
        "support/integrated_free_data_system.py",
        "support/gpt5_decision_engine.py",
        "support/event_bus_system.py",
        "support/ai_service_manager.py",
        "support/tidewise_integration_adapter.py",
        "support/free_news_crawler.py",
        "support/kobert_sentiment_analyzer.py",
        "requirements_free_news.txt",
        "README_FREE_NEWS_SYSTEM.md"
    ]
    
    success_count = 0
    total_count = len(required_files)
    
    for file_path in required_files:
        full_path = PROJECT_ROOT / file_path
        if full_path.exists():
            print(f"✓ {file_path}: 존재")
            success_count += 1
        else:
            print(f"✗ {file_path}: 없음")
    
    print(f"\n파일 구조 검증 결과: {success_count}/{total_count} 성공")
    return success_count, total_count

def test_basic_functionality():
    """기본 기능 테스트"""
    print("\n=== 기본 기능 테스트 ===")
    
    tests = []
    
    try:
        from support.integrated_free_data_system import IntegratedFreeDataSystem
        data_system = IntegratedFreeDataSystem()
        tests.append(("데이터 시스템 초기화", True))
    except Exception as e:
        tests.append(("데이터 시스템 초기화", False))
    
    try:
        from support.event_bus_system import Event, EventType, Priority
        from datetime import datetime
        event = Event(
            event_id="test",
            event_type=EventType.MARKET_DATA_UPDATE,
            priority=Priority.NORMAL,
            timestamp=datetime.now(),
            data={"test": "data"},
            source="test"
        )
        tests.append(("이벤트 객체 생성", True))
    except Exception as e:
        tests.append(("이벤트 객체 생성", False))
    
    try:
        from support.gpt5_decision_engine import GPT5DecisionEngine
        config = {"model": "gpt-4", "api_base": None}
        engine = GPT5DecisionEngine(config)
        tests.append(("GPT-5 엔진 초기화", True))
    except Exception as e:
        tests.append(("GPT-5 엔진 초기화", False))
    
    success_count = sum(1 for _, success in tests if success)
    total_count = len(tests)
    
    for test_name, success in tests:
        status = "✓" if success else "✗"
        result = "성공" if success else "실패"
        print(f"{status} {test_name}: {result}")
    
    print(f"\n기본 기능 테스트 결과: {success_count}/{total_count} 성공")
    return success_count, total_count

def main():
    """메인 검증 함수"""
    print("GPT-5 지능형 단타 거래 시스템 검증 시작")
    print("=" * 50)
    
    # 각 테스트 실행
    import_success, import_total = test_imports()
    file_success, file_total = test_file_structure()
    func_success, func_total = test_basic_functionality()
    
    # 전체 결과
    total_success = import_success + file_success + func_success
    total_tests = import_total + file_total + func_total
    
    print("\n" + "=" * 50)
    print("전체 검증 결과:")
    print(f"- 모듈 임포트: {import_success}/{import_total}")
    print(f"- 파일 구조: {file_success}/{file_total}")
    print(f"- 기본 기능: {func_success}/{func_total}")
    print(f"- 전체: {total_success}/{total_tests}")
    
    success_rate = (total_success / total_tests) * 100
    print(f"- 성공률: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("\n🎉 GPT-5 시스템이 성공적으로 구축되었습니다!")
        status = "성공"
    elif success_rate >= 60:
        print("\n⚠️  GPT-5 시스템에 일부 문제가 있지만 기본 기능은 작동합니다.")
        status = "부분 성공"
    else:
        print("\n🚨 GPT-5 시스템에 심각한 문제가 있습니다.")
        status = "실패"
    
    return status, success_rate

if __name__ == "__main__":
    try:
        status, rate = main()
        print(f"\n최종 상태: {status} ({rate:.1f}%)")
    except Exception as e:
        print(f"검증 중 오류 발생: {e}")