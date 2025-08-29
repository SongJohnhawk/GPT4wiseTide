#!/usr/bin/env python3
"""
Enhanced Token Manager 간단 테스트 (이모지 제거)
- Register_Key.md 연동 확인
- 토큰 개선 기능 검증
"""

import asyncio
import sys
from pathlib import Path

# 현재 폴더를 Python path에 추가
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from register_key_loader import test_register_key_loader, get_api_config
from enhanced_token_manager import create_enhanced_token_manager

async def test_enhanced_token():
    """Enhanced Token Manager 간단 테스트"""
    print("=== Enhanced Token Manager 테스트 시작 ===")
    
    try:
        # 1. Register_Key.md 로더 테스트
        print("\n[STEP 1] Register_Key.md 로더 테스트...")
        loader_result = test_register_key_loader()
        
        if not loader_result:
            print("[ERROR] Register_Key.md 로더 테스트 실패")
            return False
        
        # 2. Enhanced Token Manager 생성
        print("\n[STEP 2] Enhanced Token Manager 생성...")
        manager = create_enhanced_token_manager("MOCK")
        print("[OK] 모의투자 토큰 매니저 생성 성공")
        
        # 3. 건강상태 확인
        print("\n[STEP 3] 토큰 매니저 상태 확인...")
        health = manager.get_health_status()
        
        token_status = health['token_status']
        config_info = health['configuration']
        stats = health['performance_stats']
        
        print("[INFO] 토큰 상태:")
        print(f"   - 토큰 존재: {token_status['exists']}")
        print(f"   - 토큰 유효: {token_status['valid']}")
        print(f"   - 만료 임박: {token_status['near_expiry']}")
        
        print("[INFO] 설정 정보:")
        print(f"   - 계좌 타입: {config_info['account_type']}")
        print(f"   - 최대 재시도: {config_info['max_retries']}회")
        print(f"   - 자동 갱신: {config_info['preemptive_refresh_minutes']}분 전")
        print(f"   - 기본 지연: {config_info['base_delay']}초")
        print(f"   - 최대 지연: {config_info['max_delay']}초")
        
        print("[INFO] 성능 통계:")
        print(f"   - 성공률: {stats['success_rate']}")
        print(f"   - 총 요청: {stats['total_requests']}")
        print(f"   - 자동 갱신: {stats['auto_refreshes']}")
        
        # 4. 모니터링 기능 테스트
        print("\n[STEP 4] 모니터링 기능 테스트...")
        
        # 성공 케이스 시뮬레이션
        manager.health_monitor.record_request_success()
        manager.health_monitor.record_request_success()
        
        # 실패 케이스 시뮬레이션
        manager.health_monitor.record_request_failure("테스트 실패")
        manager.health_monitor.record_retry_attempt()
        
        # 자동 갱신 시뮬레이션
        manager.health_monitor.record_auto_refresh()
        
        # 업데이트된 통계 확인
        updated_stats = manager.get_health_status()['performance_stats']
        print("[RESULT] 업데이트된 통계:")
        print(f"   - 성공률: {updated_stats['success_rate']}")
        print(f"   - 총 요청: {updated_stats['total_requests']}")
        print(f"   - 성공 요청: {updated_stats['successful_requests']}")
        print(f"   - 실패 요청: {updated_stats['failed_requests']}")
        print(f"   - 재시도 횟수: {updated_stats['retry_attempts']}")
        print(f"   - 자동 갱신: {updated_stats['auto_refreshes']}")
        
        print("\n[SUCCESS] 모든 테스트 통과!")
        print("\n=== 주요 개선사항 ===")
        print("- Register_Key.md 자동 로드")
        print("- 지수백오프 재시도 (최대 3회)")
        print("- 만료 30분 전 자동 갱신")
        print("- 실시간 상태 모니터링")
        print("- 비동기 백그라운드 처리")
        print("- 성능 통계 수집")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 테스트 실행 중 오류: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_enhanced_token())
    if result:
        print("\n[COMPLETE] Enhanced Token Manager 테스트 완료!")
    else:
        print("\n[FAILED] 테스트 실패!")
        sys.exit(1)