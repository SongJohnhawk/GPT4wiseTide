#!/usr/bin/env python3
"""
파일 기반 중단 시스템 - Claude CLI 환경 호환
ESC 키 대신 파일 생성/삭제로 자동매매 중단 제어
"""

import os
import time
from pathlib import Path
from enum import Enum
from typing import Optional, Callable

class StopMode(Enum):
    """중단 모드"""
    SAFE_RETURN = "safe_return"      # 안전한 Main 복귀
    FORCE_EXIT = "force_exit"        # 강제 프로그램 종료

class FileStopHandler:
    """파일 기반 중단 처리 클래스"""
    
    def __init__(self, project_root: str = None):
        """
        Args:
            project_root: 프로젝트 루트 디렉토리 (None이면 현재 디렉토리)
        """
        if project_root:
            self.project_root = Path(project_root)
        else:
            self.project_root = Path(__file__).parent.parent
        
        # 중단 신호 파일 경로 (다양한 신호 파일 지원)
        self.stop_file = self.project_root / "STOP_TRADING.signal"
        self.force_exit_file = self.project_root / "FORCE_EXIT.signal"
        
        # 추가 신호 파일들 (레거시 지원)
        self.legacy_signal_files = [
            "SAFE_STOP", "FORCE_EXIT", "AUTO_TRADE_STOP", "AUTO_TRADE_FORCE_EXIT",
            "STOP_TRADING.signal", "FORCE_EXIT.signal"
        ] 
        
        # 상태 관리
        self.stop_requested = False
        self.stop_mode = StopMode.SAFE_RETURN
        self.stop_callback: Optional[Callable] = None
        self.force_exit_callback: Optional[Callable] = None
        
        # 모니터링 상태
        self._is_monitoring = False
        self._last_check_time = 0
        self._check_interval = 0.5  # 0.5초마다 파일 확인
        
        # 알림 메시지 상태
        self._help_message_shown = False
        
        # ESC 감지 비활성화 옵션 (파일 기반 시스템에서는 기본 비활성)
        self.disable_esc_listening = True
        
    def set_stop_callback(self, callback: Callable):
        """안전한 중단 콜백 설정 (Main 복귀)"""
        self.stop_callback = callback
        
    def set_force_exit_callback(self, callback: Callable):
        """강제 종료 콜백 설정 (프로그램 완전 종료)"""
        self.force_exit_callback = callback
    
    def start_listening(self):
        """파일 모니터링 시작"""
        self._is_monitoring = True
        self.stop_requested = False
        self.stop_mode = StopMode.SAFE_RETURN
        
        # 기존 신호 파일들 삭제 (초기화)
        self._cleanup_signal_files()
        
        # 사용자에게 중단 방법 안내
        if not self._help_message_shown:
            print("\n" + "="*60)
            print("[INFO] Auto Trading Stop Methods:")
            print(f"  1. Safe Stop (Return to Main): Create {self.stop_file.name} file")
            print(f"  2. Force Exit: Create {self.force_exit_file.name} file")
            print("="*60)
            self._help_message_shown = True
        
    def stop_listening(self):
        """파일 모니터링 중지"""
        self._is_monitoring = False
        self._cleanup_signal_files()
        
    def check_stop_signals(self) -> Optional[str]:
        """중단 신호 파일 확인 (모든 신호 파일 타입 지원)"""
        if not self._is_monitoring:
            return None
            
        current_time = time.time()
        
        # 체크 간격 준수
        if current_time - self._last_check_time < self._check_interval:
            return None
            
        self._last_check_time = current_time
        
        # 강제 종료 신호 확인 (최우선) - 모든 강제 종료 파일 타입 체크
        force_exit_files = [
            self.force_exit_file,
            self.project_root / "FORCE_EXIT",
            self.project_root / "AUTO_TRADE_FORCE_EXIT"
        ]
        
        for exit_file in force_exit_files:
            if exit_file.exists():
                print(f"\n[FORCE EXIT] Force exit signal detected: {exit_file.name}")
                print(f"[DEBUG] Signal file path: {exit_file}")
                self.stop_requested = True
                self.stop_mode = StopMode.FORCE_EXIT
                
                # 신호 파일 삭제
                self._cleanup_signal_files()
                
                # 강제 종료 콜백 실행
                if self.force_exit_callback:
                    try:
                        self.force_exit_callback()
                    except Exception as e:
                        print(f"[ERROR] Force exit callback execution error: {e}")
                        import sys
                        sys.exit(0)
                else:
                    import sys
                    sys.exit(0)
                
                return 'FORCE_EXIT'
        
        # 안전 중단 신호 확인 - 모든 안전 중단 파일 타입 체크
        safe_stop_files = [
            self.stop_file,
            self.project_root / "SAFE_STOP",
            self.project_root / "AUTO_TRADE_STOP"
        ]
        
        for stop_file in safe_stop_files:
            if stop_file.exists():
                print(f"\n[SAFE STOP] Safe stop signal detected: {stop_file.name}")
                print(f"[DEBUG] Signal file path: {stop_file}")
                print("Auto trading will safely stop and return to Main menu...")
                
                self.stop_requested = True
                self.stop_mode = StopMode.SAFE_RETURN
                
                # 신호 파일 삭제
                self._cleanup_signal_files()
                
                # 안전 중단 콜백 실행
                if self.stop_callback:
                    try:
                        self.stop_callback()
                    except Exception as e:
                        print(f"[ERROR] Safe stop callback execution error: {e}")
                
                return 'SAFE_STOP'
        
        return None
    
    def check_esc_action(self) -> Optional[str]:
        """키보드 핸들러 호환성을 위한 별칭 메서드"""
        return self.check_stop_signals()
    
    def _cleanup_signal_files(self):
        """중단 신호 파일들 정리 (모든 신호 파일 타입 지원)"""
        cleaned_files = []
        try:
            # 기본 신호 파일들
            if self.stop_file.exists():
                self.stop_file.unlink()
                cleaned_files.append(self.stop_file.name)
            if self.force_exit_file.exists():
                self.force_exit_file.unlink()
                cleaned_files.append(self.force_exit_file.name)
            
            # 레거시 신호 파일들 정리
            for signal_name in self.legacy_signal_files:
                signal_path = self.project_root / signal_name
                if signal_path.exists():
                    signal_path.unlink()
                    cleaned_files.append(signal_name)
            
            if cleaned_files:
                print(f"[CLEANUP] Removed signal files: {', '.join(cleaned_files)}")
                
        except Exception as e:
            print(f"[WARNING] Error cleaning signal files: {e}")
    
    def force_stop(self):
        """강제 중단 (비상 상황용)"""
        print("\n[EMERGENCY STOP] Auto trading will stop immediately and return to Main...")
        self.stop_requested = True
        self.stop_mode = StopMode.SAFE_RETURN
        if self.stop_callback:
            self.stop_callback()
    
    def force_exit_program(self):
        """프로그램 완전 종료"""
        print("\n[PROGRAM EXIT] Program will exit completely by user request...")
        self.stop_requested = True  
        self.stop_mode = StopMode.FORCE_EXIT
        if self.force_exit_callback:
            self.force_exit_callback()
        else:
            import sys
            sys.exit(0)
    
    def is_stop_requested(self) -> bool:
        """중단 요청 여부 확인"""
        return self.stop_requested
        
    def get_stop_mode(self) -> StopMode:
        """현재 중단 모드 반환"""
        return self.stop_mode
    
    def clear_stop_signal_files(self):
        """시작 시점에 모든 중단 신호 파일 정리 (외부 호출용)"""
        print("[STARTUP] Clearing any existing stop signal files...")
        self._cleanup_signal_files()
        
    def reset(self):
        """상태 완전 리셋"""
        self.stop_requested = False
        self.stop_mode = StopMode.SAFE_RETURN
        self._cleanup_signal_files()
        
    def get_help_message(self) -> str:
        """사용자 도움말 메시지 반환"""
        return f"""
[INFO] Auto Trading Stop Methods:
  
  Method 1. Safe Stop (Return to Main Menu):
  Execute command: echo. > {self.stop_file.name}
  
  Method 2. Force Exit (Complete Program Exit):
  Execute command: echo. > {self.force_exit_file.name}
  
  Run these commands in Windows Command Prompt.
"""

# 전역 핸들러 인스턴스 (키보드 핸들러와 호환성 유지)
_global_handler = None

def get_file_stop_handler(project_root: str = None) -> FileStopHandler:
    """전역 파일 중단 핸들러 반환"""
    global _global_handler
    if _global_handler is None:
        _global_handler = FileStopHandler(project_root)
    return _global_handler

# 키보드 핸들러 호환성을 위한 별칭
def get_keyboard_handler() -> FileStopHandler:
    """키보드 핸들러 호환성을 위한 별칭"""
    return get_file_stop_handler()