#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clean Logger - 간소화된 로그 출력 시스템
시간 스탬프와 복잡한 로그 형식을 제거한 깔끔한 출력
"""

import logging
import sys
from typing import Optional

# UTF-8 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


class CleanFormatter(logging.Formatter):
    """간소화된 로그 포맷터 - 시간스탬프 제거"""
    
    def format(self, record):
        # DEBUG, INFO 레벨은 메시지만 출력
        if record.levelname in ['DEBUG', 'INFO']:
            return record.getMessage()
        
        # WARNING, ERROR는 레벨 표시
        if record.levelname == 'WARNING':
            return f"⚠ 경고: {record.getMessage()}"
        elif record.levelname == 'ERROR':
            return f"❌ 오류: {record.getMessage()}"
        elif record.levelname == 'CRITICAL':
            return f"🔴 심각: {record.getMessage()}"
        
        return record.getMessage()


class CleanLogger:
    """간소화된 로거 관리자"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not CleanLogger._initialized:
            self.setup_logging()
            CleanLogger._initialized = True
    
    def setup_logging(self):
        """로깅 설정"""
        # 루트 로거 설정
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.WARNING)  # 기본은 WARNING 이상만
        
        # 기존 핸들러 제거
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 콘솔 핸들러 추가
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(CleanFormatter())
        root_logger.addHandler(console_handler)
        
        # 특정 모듈 로그 레벨 조정
        self.configure_module_loggers()
    
    def configure_module_loggers(self):
        """모듈별 로그 레벨 설정"""
        # 불필요한 디버그 메시지 숨기기
        suppress_modules = [
            'urllib3',
            'requests',
            'asyncio',
            'aiohttp',
            'support.api_connector',
            'support.token_manager',
            'support.trading_config_manager',
            'support.log_manager',
            'support.system_logger',
            'support.authoritative_register_key_loader',
            'support.setup_manager',
            'support.algorithm_loader',
            'support.file_stop_handler',
            'support.keyboard_handler',
            'support.market_time_manager',
            'support.dynamic_interval_controller',
        ]
        
        for module in suppress_modules:
            logger = logging.getLogger(module)
            logger.setLevel(logging.ERROR)  # ERROR 이상만 표시
        
        # 중요 모듈은 INFO 레벨 유지
        important_modules = [
            'support.display_manager',
            'support.account_info_manager',
            'support.simple_auto_trader',
            'support.minimal_auto_trader',
            'support.minimal_day_trader',
            'support.production_auto_trader',
        ]
        
        for module in important_modules:
            logger = logging.getLogger(module)
            logger.setLevel(logging.INFO)
    
    def get_logger(self, name: str) -> logging.Logger:
        """로거 반환"""
        return logging.getLogger(name)
    
    def set_level(self, level: str):
        """전체 로그 레벨 설정"""
        numeric_level = getattr(logging, level.upper(), logging.WARNING)
        logging.getLogger().setLevel(numeric_level)
    
    def silence_all(self):
        """모든 로그 출력 중지"""
        logging.getLogger().setLevel(logging.CRITICAL + 1)
    
    def enable_trading_messages(self):
        """매매 관련 메시지만 활성화"""
        self.silence_all()
        
        # 매매 관련 모듈만 INFO 레벨로
        trading_modules = [
            'support.display_manager',
            '__main__',
        ]
        
        for module in trading_modules:
            logger = logging.getLogger(module)
            logger.setLevel(logging.INFO)


# 전역 인스턴스
_clean_logger = None

def get_clean_logger() -> CleanLogger:
    """CleanLogger 싱글톤 인스턴스 반환"""
    global _clean_logger
    if _clean_logger is None:
        _clean_logger = CleanLogger()
    return _clean_logger

def setup_clean_logging():
    """간소화된 로깅 설정 - 프로그램 시작시 호출"""
    clean_logger = get_clean_logger()
    clean_logger.enable_trading_messages()
    return clean_logger