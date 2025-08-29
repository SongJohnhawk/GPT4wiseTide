"""
키보드 입력 처리 모듈
ESC 키 감지를 통한 우아한 자동매매 중단 및 Main 복귀
Universal Algorithm Controller 시스템 기반 안전 종료
"""

import asyncio
import threading
import sys
import time
import queue
from enum import Enum
from typing import Callable, Optional

class StopMode(Enum):
    """중단 모드"""
    SAFE_RETURN = "safe_return"      # 안전한 Main 복귀
    FORCE_EXIT = "force_exit"        # 강제 프로그램 종료

class KeyboardHandler:
    """키보드 입력 처리 클래스 - Universal Algorithm Controller 기반"""
    
    def __init__(self):
        self.stop_requested = False
        self.stop_mode = StopMode.SAFE_RETURN
        self.stop_callback: Optional[Callable] = None
        self.force_exit_callback: Optional[Callable] = None
        self.listener_thread = None
        
        # ESC 키 처리 개선
        self._key_queue = queue.Queue()
        self._esc_count = 0
        self._last_esc_time = 0
        self._esc_timeout = 3.0  # ESC 키 타임아웃 3초
        self._esc_cooldown = 0.5  # ESC 키 쿨다운 0.5초
        
        # 상태 관리
        self._is_monitoring = False
        
        # ESC 감지 비활성화 옵션 (환경/설정 기반)
        self.disable_esc_listening = getattr(self, "disable_esc_listening", False)
        
    def set_stop_callback(self, callback: Callable):
        """안전한 중단 콜백 설정 (Main 복귀)"""
        self.stop_callback = callback
        
    def set_force_exit_callback(self, callback: Callable):
        """강제 종료 콜백 설정 (프로그램 완전 종료)"""
        self.force_exit_callback = callback
        
    def force_stop(self):
        """강제 중단 (비상 상황용)"""
        print("\n\n[긴급 중단] 자동매매를 즉시 중단하고 Main으로 복귀합니다...")
        self.stop_requested = True
        self.stop_mode = StopMode.SAFE_RETURN
        if self.stop_callback:
            self.stop_callback()
    
    def force_exit_program(self):
        """프로그램 완전 종료"""
        print("\n\n[프로그램 종료] 사용자 요청으로 프로그램을 완전히 종료합니다...")
        self.stop_requested = True  
        self.stop_mode = StopMode.FORCE_EXIT
        if self.force_exit_callback:
            self.force_exit_callback()
        else:
            # 콜백이 없으면 직접 종료
            import sys
            sys.exit(0)
        
    def start_listening(self):
        """키보드 리스닝 시작 - Universal Algorithm Controller 방식"""
        if self._is_monitoring:
            return
            
        # ESC 감지 비활성화 옵션 확인
        if getattr(self, "disable_esc_listening", False):
            print("[INFO] ESC listening disabled - file-based signals only")
            self._is_monitoring = True
            return
            
        self.stop_requested = False
        self.stop_mode = StopMode.SAFE_RETURN
        self._esc_count = 0
        self._last_esc_time = 0
        
        # 기존 스레드가 살아있다면 중지
        if self.listener_thread and self.listener_thread.is_alive():
            self._is_monitoring = False
            self.listener_thread.join(timeout=1.0)
        
        # 키 큐 초기화
        while not self._key_queue.empty():
            try:
                self._key_queue.get_nowait()
            except queue.Empty:
                break
        
        # Windows에서 ESC 키 감지를 위한 스레드
        if sys.platform == "win32":
            self._is_monitoring = True
            self.listener_thread = threading.Thread(target=self._windows_key_listener, daemon=True)
            self.listener_thread.start()
            
            # 스레드 시작 확인
            time.sleep(0.1)
            if not self.listener_thread.is_alive():
                print("[ERROR] 키보드 리스너 스레드 시작 실패!")
                self._is_monitoring = False
        else:
            print(f"[WARNING] 현재 플랫폼 ({sys.platform})에서는 ESC 키 감지를 지원하지 않습니다.")
        
    def stop_listening(self):
        """키보드 리스닝 중지"""
        self._is_monitoring = False
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=1.0)
            
    def _windows_key_listener(self):
        """Windows ESC 키 감지 - Universal Algorithm Controller 방식"""
        try:
            import msvcrt
            
            while self._is_monitoring:
                try:
                    # 강제 종료 처리 중이면 스레드 종료
                    if hasattr(self, '_force_exit_executed'):
                        break
                        
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        
                        if key == b'\x1b':  # ESC 키
                            self._handle_esc_key()
                            
                            # ESC 2회 처리 후 스레드 종료
                            if hasattr(self, '_force_exit_executed'):
                                break
                    
                    time.sleep(0.05)  # 50ms 간격
                    
                except Exception as inner_e:
                    print(f"[ERROR] 키 감지 루프 오류: {inner_e}")
                    time.sleep(0.1)
                    
        except ImportError:
            print("[WARNING] msvcrt 모듈을 찾을 수 없습니다. Windows가 아닌 환경입니다.")
        except Exception as e:
            print(f"[ERROR] 키보드 리스너 심각한 오류: {e}")
            import traceback
            traceback.print_exc()
        
        # 스레드 종료시 모니터링 상태 비활성화
        self._is_monitoring = False
    
    def _handle_esc_key(self):
        """ESC 키 처리 - Universal Algorithm Controller 방식 (무한루프 방지)"""
        current_time = time.time()
        
        # 이미 강제 종료 처리된 경우 완전 차단
        if hasattr(self, '_force_exit_executed'):
            return
        
        # 쿨다운 기간 내 중복 클릭 무시
        if current_time - self._last_esc_time < self._esc_cooldown:
            return
        
        # 타임아웃 기간 지나면 카운트 리셋 (3초 경과시)
        if self._last_esc_time > 0 and current_time - self._last_esc_time > self._esc_timeout:
            self._esc_count = 0
        
        self._last_esc_time = current_time
        self._esc_count += 1
        
        if self._esc_count == 1:
            print(f"\n\n[ESC 1회] 자동매매 안전 중단 - {self._esc_timeout:.0f}초 내에 ESC를 한번 더 누르면 프로그램 종료")
            try:
                # 기존 큐 내용 확인하고 SAFE_STOP이 없으면 추가
                queue_contents = []
                while not self._key_queue.empty():
                    try:
                        item = self._key_queue.get_nowait()
                        queue_contents.append(item)
                    except queue.Empty:
                        break
                
                # SAFE_STOP이 없으면 추가
                if 'SAFE_STOP' not in queue_contents:
                    queue_contents.append('SAFE_STOP')
                
                # 큐에 다시 넣기
                for item in queue_contents:
                    self._key_queue.put_nowait(item)
                    
            except queue.Full:
                pass
                
        elif self._esc_count >= 2:
            # 이미 강제 종료 처리된 경우 중복 실행 방지
            if hasattr(self, '_force_exit_executed'):
                return
                
            print("\n\n[ESC 2회] 프로그램 강제 종료 중...")
            
            # 강제 종료 실행 플래그 즉시 설정 (무한 루프 방지)
            self._force_exit_executed = True
            
            # 상태 즉시 변경
            self._is_monitoring = False
            self.stop_requested = True
            self.stop_mode = StopMode.FORCE_EXIT
            
            # 큐 완전 초기화 후 FORCE_EXIT만 추가
            while not self._key_queue.empty():
                try:
                    self._key_queue.get_nowait()
                except queue.Empty:
                    break
            
            try:
                self._key_queue.put_nowait('FORCE_EXIT')
            except queue.Full:
                pass
            
            # 강제 종료 콜백 실행
            if self.force_exit_callback:
                try:
                    self.force_exit_callback()
                except Exception as e:
                    print(f"[ERROR] 강제종료 콜백 실행 오류: {e}")
                    import sys
                    sys.exit(0)
            else:
                import sys
                sys.exit(0)
    
    def check_esc_action(self) -> Optional[str]:
        """ESC 키 액션 확인 (SAFE_STOP 또는 FORCE_EXIT)"""
        try:
            return self._key_queue.get_nowait()
        except queue.Empty:
            return None
    
    def get_esc_count(self) -> int:
        """총 ESC 키 클릭 횟수"""
        return self._esc_count
    
    def reset_esc_count(self):
        """ESC 키 카운트 리셋"""
        self._esc_count = 0
            
    def is_stop_requested(self) -> bool:
        """중단 요청 여부 확인"""
        return self.stop_requested
        
    def get_stop_mode(self) -> StopMode:
        """현재 중단 모드 반환"""
        return self.stop_mode
        
    def reset(self):
        """상태 완전 리셋"""
        self.stop_requested = False
        self.stop_mode = StopMode.SAFE_RETURN
        self._esc_count = 0
        self._last_esc_time = 0
        
        # 강제 종료 실행 플래그 초기화
        if hasattr(self, '_force_exit_executed'):
            delattr(self, '_force_exit_executed')
        
        # 키 큐 비우기
        while not self._key_queue.empty():
            try:
                self._key_queue.get_nowait()
            except queue.Empty:
                break
        
        if self.listener_thread and self.listener_thread.is_alive():
            self.stop_listening()
    
    def clear_stop_signal_files(self):
        """시작 시 신호 파일 정리 (file_stop_handler 호환성)"""
        import os
        signal_files = ["SAFE_STOP", "FORCE_EXIT", "AUTO_TRADE_STOP", "AUTO_TRADE_FORCE_EXIT"]
        cleaned_files = []
        
        for name in signal_files:
            try:
                if os.path.exists(name):
                    os.remove(name)
                    cleaned_files.append(name)
            except Exception as e:
                print(f"[WARNING] Failed to remove {name}: {e}")
        
        if cleaned_files:
            print(f"[CLEANUP] Removed signal files: {', '.join(cleaned_files)}")
    
    def check_stop_signals(self) -> Optional[str]:
        """중단 신호 확인 (파일 기반 중단과의 호환성을 위한 확장)"""
        # 기존 ESC 기반 확인
        esc_action = self.check_esc_action()
        if esc_action:
            return esc_action
        
        # 파일 기반 신호 확인 (추가 호환성)
        import os
        if os.path.exists("FORCE_EXIT") or os.path.exists("AUTO_TRADE_FORCE_EXIT"):
            print("\n[FORCE EXIT] File-based force exit signal detected")
            return 'FORCE_EXIT'
        
        if os.path.exists("SAFE_STOP") or os.path.exists("AUTO_TRADE_STOP"):
            print("\n[SAFE STOP] File-based safe stop signal detected")
            return 'SAFE_STOP'
        
        return None

# 전역 핸들러 인스턴스
_global_handler = KeyboardHandler()

def get_keyboard_handler() -> KeyboardHandler:
    """전역 키보드 핸들러 반환"""
    return _global_handler

# 파일 기반 핸들러와의 호환성을 위한 별칭
def get_file_stop_handler():
    """file_stop_handler와의 호환성을 위한 별칭"""
    return get_keyboard_handler()