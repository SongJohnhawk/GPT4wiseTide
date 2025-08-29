#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Error Handler for tideWise Auto Trading System
고급 에러 핸들러 - 로그 관리 및 에러 처리 통합 시스템
"""

import logging
import traceback
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import json
import sys
import os
from functools import wraps

class EnhancedErrorHandler:
    """통합 에러 핸들러 및 로거"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.logs_dir = project_root / "logs"
        self.error_log_path = self.logs_dir / "error"
        self.system_log_path = self.logs_dir / "system"
        
        # 로그 디렉토리 생성
        self.logs_dir.mkdir(exist_ok=True)
        self.error_log_path.mkdir(exist_ok=True)
        self.system_log_path.mkdir(exist_ok=True)
        
        # 로거 설정
        self.setup_loggers()
        
        # 에러 카운터
        self.error_count = 0
        self.warning_count = 0
        
    def setup_loggers(self):
        """로거 설정 - 파일 및 콘솔 출력"""
        
        # 메인 로거
        self.logger = logging.getLogger('tideWise')
        self.logger.setLevel(logging.DEBUG)
        
        # 포매터 설정
        detailed_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # 파일 핸들러 - 일반 로그
        today = datetime.datetime.now().strftime('%Y%m%d')
        general_log_file = self.logs_dir / f"general_{today}.log"
        
        file_handler = logging.FileHandler(general_log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(detailed_formatter)
        
        # 파일 핸들러 - 에러 로그
        error_log_file = self.error_log_path / f"error_{today}.log"
        
        error_file_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(detailed_formatter)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        
        # 핸들러 추가
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(error_file_handler)
            self.logger.addHandler(console_handler)
    
    def log_error(self, error: Exception, context: str = "", additional_data: Dict[str, Any] = None):
        """에러 로깅 - 상세 정보 포함"""
        self.error_count += 1
        
        error_info = {
            'timestamp': datetime.datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'traceback': traceback.format_exc(),
            'additional_data': additional_data or {}
        }
        
        # 로그 메시지 생성
        log_message = f"ERROR #{self.error_count} in {context}: {error}"
        
        # 파일에 상세 정보 저장
        self.logger.error(log_message)
        self.logger.debug(f"Full error info: {json.dumps(error_info, indent=2, ensure_ascii=False)}")
        
        return error_info
    
    def log_warning(self, message: str, context: str = "", additional_data: Dict[str, Any] = None):
        """경고 로깅"""
        self.warning_count += 1
        
        warning_info = {
            'timestamp': datetime.datetime.now().isoformat(),
            'message': message,
            'context': context,
            'additional_data': additional_data or {}
        }
        
        log_message = f"WARNING #{self.warning_count} in {context}: {message}"
        self.logger.warning(log_message)
        
        return warning_info
    
    def log_info(self, message: str, context: str = "", additional_data: Dict[str, Any] = None):
        """정보 로깅"""
        info_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'message': message,
            'context': context,
            'additional_data': additional_data or {}
        }
        
        log_message = f"INFO in {context}: {message}" if context else f"INFO: {message}"
        self.logger.info(log_message)
        
        return info_data
    
    def error_handler_decorator(self, context: str = "", reraise: bool = False):
        """데코레이터 - 함수 에러 자동 처리"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self.log_error(
                        e, 
                        context or f"{func.__module__}.{func.__name__}",
                        {'args': str(args)[:200], 'kwargs': str(kwargs)[:200]}
                    )
                    
                    if reraise:
                        raise
                    return None
            return wrapper
        return decorator
    
    def get_error_summary(self) -> Dict[str, Any]:
        """에러 요약 정보 반환"""
        return {
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'timestamp': datetime.datetime.now().isoformat(),
            'logs_directory': str(self.logs_dir)
        }
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """오래된 로그 파일 정리"""
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
        
        cleaned_count = 0
        for log_file in self.logs_dir.rglob("*.log"):
            try:
                file_date = datetime.datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_date < cutoff_date:
                    log_file.unlink()
                    cleaned_count += 1
            except Exception as e:
                self.log_warning(f"로그 파일 정리 실패: {log_file}", "cleanup", {'error': str(e)})
        
        if cleaned_count > 0:
            self.log_info(f"{cleaned_count}개의 오래된 로그 파일 정리 완료", "cleanup")


# 전역 인스턴스
_error_handler_instance = None

def get_error_handler(project_root: Path = None) -> EnhancedErrorHandler:
    """에러 핸들러 인스턴스 반환 (싱글톤)"""
    global _error_handler_instance
    
    if _error_handler_instance is None:
        if project_root is None:
            project_root = Path(__file__).parent.parent
        _error_handler_instance = EnhancedErrorHandler(project_root)
    
    return _error_handler_instance


# 편의 함수들
def log_error(error: Exception, context: str = "", additional_data: Dict[str, Any] = None):
    """편의 함수 - 에러 로깅"""
    return get_error_handler().log_error(error, context, additional_data)

def log_warning(message: str, context: str = "", additional_data: Dict[str, Any] = None):
    """편의 함수 - 경고 로깅"""
    return get_error_handler().log_warning(message, context, additional_data)

def log_info(message: str, context: str = "", additional_data: Dict[str, Any] = None):
    """편의 함수 - 정보 로깅"""
    return get_error_handler().log_info(message, context, additional_data)

def handle_errors(context: str = "", reraise: bool = False):
    """편의 함수 - 에러 핸들러 데코레이터"""
    return get_error_handler().error_handler_decorator(context, reraise)


# 사용 예시
if __name__ == "__main__":
    # 테스트 실행
    handler = get_error_handler()
    
    # 정보 로그 테스트
    log_info("Enhanced Error Handler 테스트 시작", "test")
    
    # 경고 로그 테스트
    log_warning("이것은 테스트 경고입니다", "test")
    
    # 에러 로그 테스트
    try:
        raise ValueError("테스트 에러")
    except Exception as e:
        log_error(e, "test", {"test_data": "example"})
    
    # 데코레이터 테스트
    @handle_errors("decorator_test")
    def test_function():
        raise RuntimeError("데코레이터 테스트 에러")
    
    result = test_function()
    
    # 요약 정보 출력
    summary = handler.get_error_summary()
    print(f"\n에러 요약: {json.dumps(summary, indent=2, ensure_ascii=False)}")