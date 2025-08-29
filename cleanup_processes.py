#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tideWise 프로세스 정리 유틸리티
실행 중인 모든 tideWise 관련 프로세스를 안전하게 종료
"""

import sys
import os
from pathlib import Path

# 프로젝트 경로 설정
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'support'))


def main():
    """프로세스 정리 메인 함수"""
    print("="*60)
    print("tideWise 프로세스 정리 유틸리티")
    print("="*60)
    
    try:
        from support.process_cleanup_manager import ProcessCleanupManager
        
        # 프로세스 정리 관리자 초기화
        cleanup_manager = ProcessCleanupManager()
        
        print("\n모든 tideWise 관련 프로세스를 종료합니다...")
        print("(현재 실행 중인 자동매매, 단타매매, 백그라운드 작업 포함)")
        
        # 사용자 확인
        try:
            response = input("\n계속하시겠습니까? (Y/N): ").strip().upper()
            if response != 'Y':
                print("취소되었습니다.")
                return 0
        except (KeyboardInterrupt, EOFError):
            print("\n취소되었습니다.")
            return 0
        
        # 프로세스 정리 실행
        result = cleanup_manager.cleanup_all_processes(include_self=False)
        
        # 결과 상세 출력
        print("\n" + "="*60)
        print("정리 결과 상세")
        print("="*60)
        
        if result['details']:
            print("\n[처리된 프로세스]")
            for proc_info in result['details']:
                status_icon = {
                    'terminated': '✓',
                    'failed': '✗',
                    'skipped_self': '○'
                }.get(proc_info['status'], '?')
                
                print(f"  {status_icon} PID {proc_info['pid']:6d} - {proc_info['name']:20s} - {proc_info['status']}")
        
        # 성공/실패 요약
        print("\n" + "="*60)
        if result['failed_processes'] == 0:
            print("[성공] 모든 프로세스가 정상적으로 종료되었습니다.")
            return 0
        else:
            print(f"[경고] {result['failed_processes']}개의 프로세스 종료 실패")
            print("       관리자 권한으로 다시 시도하거나 작업 관리자를 사용하세요.")
            return 1
            
    except ImportError as e:
        print(f"\n[오류] 필요한 모듈을 찾을 수 없습니다: {e}")
        print("      psutil 설치 확인: pip install psutil")
        return 1
    except Exception as e:
        print(f"\n[오류] 프로세스 정리 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    
    # 종료 전 대기 (배치 파일에서 실행 시 창이 바로 닫히지 않도록)
    try:
        input("\nEnter를 눌러 종료...")
    except (KeyboardInterrupt, EOFError):
        pass
    
    sys.exit(exit_code)