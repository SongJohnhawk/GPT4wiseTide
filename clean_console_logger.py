#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clean Console Logger
- 단계별 메시지 그룹핑
- 시간 표시 간소화 ([HH:MM] 형식)
- 중복 메시지 필터링
- 색상 코딩으로 가독성 향상
"""

import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any, List, Set
from enum import Enum
import threading

# Windows 콘솔 UTF-8 설정
if sys.platform.startswith('win'):
    try:
        import subprocess
        subprocess.run(['chcp', '65001'], capture_output=True, shell=True)
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    from rich.console import Console
    from rich.text import Text
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.rule import Rule
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None


class Phase(Enum):
    """시스템 단계 정의"""
    INIT = "초기화"
    CONNECTION = "연결"
    ACCOUNT = "계좌"
    TRADING = "매매"
    ANALYSIS = "분석"
    CLEANUP = "종료"
    ERROR = "오류"
    SUCCESS = "완료"


class CleanConsoleLogger:
    """깔끔한 콘솔 로거"""
    
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self.current_phase = None
        self.phase_messages = {}  # 단계별 메시지 저장
        self.seen_messages = set()  # 중복 방지용
        self.suppress_duplicates = True
        self.verbose = False  # 상세 모드
        self.lock = threading.Lock()
        
        # 색상 테마
        self.colors = {
            'time': '#808080',        # 회색 (시간)
            'phase': '#0066CC',       # 파란색 (단계)
            'success': '#00B050',     # 초록색 (성공)
            'warning': '#FF9900',     # 주황색 (경고)
            'error': '#CC0000',       # 빨간색 (오류)
            'info': '#6B73FF',        # 보라색 (정보)
            'debug': '#606060',       # 진한 회색 (디버그)
        }
        
        # 필터링할 메시지 패턴
        self.filter_patterns = [
            "INFO - ",
            "WARNING - ",
            "ERROR - ",
            "DEBUG - ",
            "토큰 관리자 초기화",
            "토큰 파일 없음",
            "새 토큰 발급",
            "Register_Key.md",
            "AuthoritativeRegisterKeyLoader",
            "텔레그램 봇 토큰 로드",
            "텔레그램 채팅 ID 로드",
            "Fast Token Manager",
            "백그라운드 급등종목 수집 비동기",
            "단계 시작:",
            "단계 종료:",
        ]
        
        # 단계별 중요 메시지만 표시
        self.phase_highlights = {
            Phase.INIT: ["알고리즘 로드", "시스템 초기화", "매매 시작"],
            Phase.CONNECTION: ["서버 연결", "API 초기화", "연결 성공"],
            Phase.ACCOUNT: ["계좌 조회", "예수금", "보유종목", "수익률"],
            Phase.TRADING: ["매수", "매도", "주문", "체결", "포지션"],
            Phase.ANALYSIS: ["분석 시작", "종목 선정", "신호 발생"],
            Phase.CLEANUP: ["종료", "정리", "완료"],
        }
    
    def _get_time_str(self) -> str:
        """현재 시간을 [HH:MM] 형식으로 반환"""
        return datetime.now().strftime("[%H:%M]")
    
    def _format_time(self, time_str: str) -> Text:
        """시간 문자열에 색상 적용"""
        if RICH_AVAILABLE:
            return Text(time_str, style=self.colors['time'])
        return time_str
    
    def _should_filter(self, message: str) -> bool:
        """메시지 필터링 여부 확인"""
        if self.verbose:  # 상세 모드에서는 모든 메시지 표시
            return False
            
        # 중복 메시지 필터링
        if self.suppress_duplicates:
            msg_key = message.strip().lower()
            if msg_key in self.seen_messages:
                return True
            self.seen_messages.add(msg_key)
        
        # 불필요한 패턴 필터링
        for pattern in self.filter_patterns:
            if pattern in message:
                return True
        
        return False
    
    def start_phase(self, phase: Phase, description: str = ""):
        """새로운 단계 시작"""
        with self.lock:
            self.current_phase = phase
            self.phase_messages[phase] = []
            
            time_str = self._get_time_str()
            
            if RICH_AVAILABLE and self.console:
                # Rich 라이브러리 사용
                rule_text = Text()
                rule_text.append(self._format_time(time_str))
                rule_text.append(" ")
                rule_text.append(f"【{phase.value}】", style=f"bold {self.colors['phase']}")
                if description:
                    rule_text.append(f" {description}", style="dim")
                
                self.console.print()
                self.console.rule(rule_text, style=self.colors['phase'])
                self.console.print()
            else:
                # Fallback 출력
                print(f"\n{time_str} ━━━━━━【{phase.value}】{description}━━━━━━")
    
    def end_phase(self, phase: Phase, success: bool = True):
        """단계 종료"""
        with self.lock:
            time_str = self._get_time_str()
            status = "✅ 완료" if success else "❌ 실패"
            color = self.colors['success'] if success else self.colors['error']
            
            if RICH_AVAILABLE and self.console:
                end_text = Text()
                end_text.append(self._format_time(time_str))
                end_text.append(f" {status}", style=color)
                self.console.print(end_text)
                self.console.print()
            else:
                print(f"{time_str} {status}\n")
            
            self.current_phase = None
    
    def log(self, message: str, level: str = "INFO", phase: Optional[Phase] = None):
        """메시지 로깅"""
        with self.lock:
            # 필터링 확인
            if self._should_filter(message):
                return
            
            time_str = self._get_time_str()
            phase = phase or self.current_phase
            
            # 레벨별 색상 및 아이콘
            level_config = {
                "SUCCESS": (self.colors['success'], "✅"),
                "ERROR": (self.colors['error'], "❌"),
                "WARNING": (self.colors['warning'], "⚠️"),
                "INFO": (self.colors['info'], "ℹ️"),
                "DEBUG": (self.colors['debug'], "🔍"),
            }
            
            color, icon = level_config.get(level.upper(), (self.colors['info'], "•"))
            
            if RICH_AVAILABLE and self.console:
                log_text = Text()
                log_text.append(self._format_time(time_str))
                log_text.append(" ")
                if level.upper() in ["ERROR", "WARNING", "SUCCESS"]:
                    log_text.append(f"{icon} ", style=color)
                log_text.append(message, style=color if level.upper() in ["ERROR", "WARNING"] else "")
                
                self.console.print(log_text)
            else:
                prefix = f"{icon} " if level.upper() in ["ERROR", "WARNING", "SUCCESS"] else ""
                print(f"{time_str} {prefix}{message}")
    
    def log_account(self, account_data: Dict):
        """계좌 정보 출력 (간단 버전)"""
        with self.lock:
            time_str = self._get_time_str()
            
            if RICH_AVAILABLE and self.console:
                # 간단한 계좌 정보 테이블
                table = Table(show_header=False, box=box.SIMPLE, pad_edge=False)
                table.add_column("항목", style="cyan", width=15)
                table.add_column("값", style="white", justify="right")
                
                # 주요 정보만 표시 (계좌번호 포함)
                account_number = account_data.get('account_number', 'Unknown')
                table.add_row("계좌번호", f"{account_number}")
                table.add_row("예수금", f"{account_data.get('available_cash', 0):,.0f}원")
                table.add_row("보유종목", f"{account_data.get('positions_count', 0)}개")
                table.add_row("수익률", f"{account_data.get('profit_rate', 0):.2f}%")
                
                panel = Panel(
                    table,
                    title=f"{self._format_time(time_str)} 계좌 현황",
                    style=self.colors['info'],
                    expand=False
                )
                self.console.print(panel)
            else:
                account_number = account_data.get('account_number', 'Unknown')
                print(f"{time_str} [계좌] 계좌번호: {account_number} | "
                      f"예수금: {account_data.get('available_cash', 0):,.0f}원 | "
                      f"보유: {account_data.get('positions_count', 0)}개 | "
                      f"수익률: {account_data.get('profit_rate', 0):.2f}%")
    
    def log_trade(self, action: str, symbol: str, quantity: int, price: float, success: bool = True):
        """거래 정보 출력"""
        with self.lock:
            time_str = self._get_time_str()
            status_icon = "✅" if success else "❌"
            action_text = "매수" if action.upper() == "BUY" else "매도"
            
            message = f"{status_icon} {action_text} {'체결' if success else '실패'}: {symbol} {quantity}주 @ {price:,.0f}원"
            
            if RICH_AVAILABLE and self.console:
                trade_text = Text()
                trade_text.append(self._format_time(time_str))
                trade_text.append(" ")
                trade_text.append(message, style=self.colors['success'] if success else self.colors['error'])
                self.console.print(trade_text)
            else:
                print(f"{time_str} {message}")
    
    def progress_bar(self, description: str, total: int = 100):
        """진행 상황 표시"""
        if RICH_AVAILABLE:
            return Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            )
        return None
    
    def clear_duplicates(self):
        """중복 메시지 캐시 초기화"""
        with self.lock:
            self.seen_messages.clear()
    
    def set_verbose(self, verbose: bool):
        """상세 모드 설정"""
        self.verbose = verbose


# 싱글톤 인스턴스
_logger_instance = None

def get_clean_logger() -> CleanConsoleLogger:
    """싱글톤 로거 인스턴스 반환"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = CleanConsoleLogger()
    return _logger_instance


# 간편 함수들
def start_phase(phase: Phase, description: str = ""):
    """단계 시작"""
    get_clean_logger().start_phase(phase, description)

def end_phase(phase: Phase, success: bool = True):
    """단계 종료"""
    get_clean_logger().end_phase(phase, success)

def log(message: str, level: str = "INFO", phase: Optional[Phase] = None):
    """메시지 로깅"""
    get_clean_logger().log(message, level, phase)

def log_account(account_data: Dict):
    """계좌 정보 로깅"""
    get_clean_logger().log_account(account_data)

def log_trade(action: str, symbol: str, quantity: int, price: float, success: bool = True):
    """거래 로깅"""
    get_clean_logger().log_trade(action, symbol, quantity, price, success)

def set_verbose(verbose: bool):
    """상세 모드 설정"""
    get_clean_logger().set_verbose(verbose)