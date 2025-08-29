#!/usr/bin/env python3
"""
단계 표시 유틸리티 모듈
전날잔고처리 및 자동매매 단계의 시작/종료를 명확하게 표시
"""

import asyncio
import logging
import sys
import os
import locale
from typing import Optional

# 한글 출력 문제 해결을 위한 인코딩 설정
def _fix_korean_encoding():
    """한글 출력 문제 완전 해결"""
    try:
        # Python 환경변수 설정
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PYTHONUTF8'] = '1'
        os.environ['PYTHONLEGACYWINDOWSSTDIO'] = '0'
        
        # sys.stdout/stderr 강제 재구성
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        
        # 로케일 설정
        try:
            locale.setlocale(locale.LC_ALL, 'ko_KR.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_ALL, 'Korean_Korea.UTF-8')
            except:
                pass
    except Exception:
        pass

# 모듈 로드 시 한글 인코딩 자동 설정
_fix_korean_encoding()

logger = logging.getLogger(__name__)

# ANSI 색상 코드
class Colors:
    BRIGHT_PINK = '\033[95m'    # 밝은 핑크색 (일반 단계용)
    RED = '\033[91m'            # 빨간색 (알고리즘 단계용)
    BLUE = '\033[94m'           # 파란색 (시스템 초기화용)
    GREEN = '\033[92m'          # 녹색 (성공 메시지용)
    YELLOW = '\033[93m'         # 노란색 (경고 메시지용)
    RESET = '\033[0m'           # 색상 리셋
    BOLD = '\033[1m'            # 굵게


class StepDisplayManager:
    """단계 표시 관리자"""
    
    @staticmethod
    def print_step_start(step_name: str, step_number: Optional[int] = None, is_algorithm: bool = False):
        """단계 시작 표시"""
        if step_number:
            message = f"[{step_number}단계시작] {step_name}"
        else:
            message = f"[{step_name}단계시작]"
        
        # 알고리즘 단계는 빨간색, 일반 단계는 핑크색
        color = Colors.RED if is_algorithm else Colors.BRIGHT_PINK
        colored_message = f"{color}{Colors.BOLD}{message}{Colors.RESET}"
        print(colored_message)
        logger.info(f"단계 시작: {step_name}")
    
    @staticmethod
    def print_step_end(step_name: str, step_number: Optional[int] = None, is_algorithm: bool = False):
        """단계 종료 표시"""
        if step_number:
            message = f"[{step_number}단계종료] {step_name}"
        else:
            message = f"[{step_name}단계종료]"
        
        # 알고리즘 단계는 빨간색, 일반 단계는 핑크색
        color = Colors.RED if is_algorithm else Colors.BRIGHT_PINK
        colored_message = f"{color}{Colors.BOLD}{message}{Colors.RESET}"
        print(colored_message)
        logger.info(f"단계 종료: {step_name}")
    
    @staticmethod
    async def step_delay(seconds: int = 3):
        """단계 간 지연 처리 (화면 표시 없음)"""
        await asyncio.sleep(seconds)
    
    @staticmethod
    def format_step_message(message: str, is_start: bool = True, step_number: Optional[int] = None):
        """단계 메시지 포맷팅 (출력 없이 문자열만 반환)"""
        action = "시작" if is_start else "종료"
        
        if step_number:
            formatted = f"[{step_number}단계{action}] {message}"
        else:
            formatted = f"[{message}단계{action}]"
        
        return f"{Colors.BRIGHT_PINK}{Colors.BOLD}{formatted}{Colors.RESET}"


def get_step_display_manager() -> StepDisplayManager:
    """StepDisplayManager 인스턴스 반환"""
    return StepDisplayManager()


# 편의 함수들
def print_step_start(step_name: str, step_number: Optional[int] = None, is_algorithm: bool = False):
    """단계 시작 표시 편의 함수"""
    StepDisplayManager.print_step_start(step_name, step_number, is_algorithm)


def print_step_end(step_name: str, step_number: Optional[int] = None, is_algorithm: bool = False):
    """단계 종료 표시 편의 함수"""
    StepDisplayManager.print_step_end(step_name, step_number, is_algorithm)


def print_algorithm_start(algorithm_name: str):
    """알고리즘 시작 표시 (빨간색)"""
    StepDisplayManager.print_step_start(f"{algorithm_name} 알고리즘", is_algorithm=True)


def print_algorithm_end(algorithm_name: str):
    """알고리즘 종료 표시 (빨간색)"""
    StepDisplayManager.print_step_end(f"{algorithm_name} 알고리즘", is_algorithm=True)


async def step_delay(seconds: int = 3):
    """단계 간 지연 처리 편의 함수"""
    await StepDisplayManager.step_delay(seconds)


# ========== 시스템 초기화 박스 표시 기능 ==========

def print_system_loading_start():
    """tideWise 시스템 로딩 시작 박스 표시"""
    box_width = 60
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*box_width}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'[tideWise System Loading]':^{box_width}}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'='*box_width}{Colors.RESET}")
    print(f"{Colors.BLUE}┌{'─'*(box_width-2)}{Colors.RESET}")


def print_system_loading_message(message: str):
    """시스템 로딩 박스 안에 메시지 표시"""
    print(f"{Colors.BLUE}│ {Colors.GREEN}{message}{Colors.RESET}")


def print_system_loading_end(success: bool = True):
    """tideWise 시스템 로딩 종료 박스 표시"""
    box_width = 60
    
    if success:
        status_msg = "[OK] System Ready"
        color = Colors.GREEN
    else:
        status_msg = "[ERROR] System Error"
        color = Colors.RED
    
    print(f"{Colors.BLUE}├{'─'*(box_width-2)}{Colors.RESET}")
    print(f"{Colors.BLUE}│ {color}{Colors.BOLD}{status_msg}{Colors.RESET}")
    print(f"{Colors.BLUE}└{'─'*(box_width-2)}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'='*box_width}{Colors.RESET}\n")


class SystemLoadingContext:
    """시스템 로딩 컨텍스트 매니저"""
    
    def __init__(self, capture_logs: bool = False):
        self.success = True
        self.capture_logs = capture_logs
        self.original_handler = None
        
    def __enter__(self):
        print_system_loading_start()
        
        if self.capture_logs:
            # 로깅 핸들러 설치하여 INFO 레벨 메시지 캡처
            self._setup_log_capture()
            
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.success = False
            
        if self.capture_logs:
            self._teardown_log_capture()
            
        print_system_loading_end(self.success)
        
    def _setup_log_capture(self):
        """로그 캡처 설정"""
        import logging
        
        class LoadingLogHandler(logging.Handler):
            def __init__(self, context):
                super().__init__(logging.INFO)
                self.context = context
                
            def emit(self, record):
                if record.levelno >= logging.INFO:
                    # 시스템 초기화 관련 메시지만 필터링
                    msg = record.getMessage()
                    if any(keyword in msg for keyword in [
                        "초기화", "활성화", "시작", "완료", "Ready", "로드",
                        "ProcessCleanupManager", "토큰", "알고리즘", "연결"
                    ]):
                        self.context._log_from_handler(msg)
        
        self.log_handler = LoadingLogHandler(self)
        logging.getLogger().addHandler(self.log_handler)
        
    def _teardown_log_capture(self):
        """로그 캡처 해제"""
        import logging
        if hasattr(self, 'log_handler'):
            logging.getLogger().removeHandler(self.log_handler)
            
    def _log_from_handler(self, message: str):
        """로그 핸들러에서 호출되는 메시지 처리"""
        # 너무 긴 메시지는 축약
        if len(message) > 50:
            message = message[:47] + "..."
        self.log(message)
        
    def log(self, message: str):
        """로딩 메시지 출력"""
        print_system_loading_message(message)
        
    def error(self, message: str):
        """에러 메시지 출력"""
        print_system_loading_message(f"[ERROR] {message}")
        self.success = False
        
    def success_msg(self, message: str):
        """성공 메시지 출력"""
        print_system_loading_message(f"[OK] {message}")


def system_loading_box(func):
    """시스템 로딩 박스 데코레이터"""
    def wrapper(*args, **kwargs):
        with SystemLoadingContext() as context:
            try:
                result = func(*args, **kwargs)
                if hasattr(result, '__await__'):
                    # 비동기 함수인 경우
                    async def async_wrapper():
                        return await result
                    return async_wrapper()
                return result
            except Exception as e:
                context.error(f"오류: {e}")
                raise
    return wrapper