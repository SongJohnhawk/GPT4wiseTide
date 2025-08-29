#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Console Output Manager
- Rich 라이브러리 기반 아름다운 콘솔 출력
- 2025년 UI/UX 디자인 원칙 적용
- 계층적 정보 구조, 시각적 그룹핑, 명확한 상태 표시
- Windows CP949 인코딩 호환성 지원
"""

import sys
import os
from datetime import datetime

# Windows 콘솔 UTF-8 인코딩 설정 (CP949 호환성)
if sys.platform.startswith('win'):
    try:
        # 콘솔 코드페이지를 UTF-8로 설정
        import subprocess
        subprocess.run(['chcp', '65001'], capture_output=True, shell=True)
        # stdout과 stderr를 UTF-8로 재구성 시도
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        # 설정 실패 시 무시하고 계속 진행 (fallback 사용)
        pass
from typing import Optional, Dict, Any, List
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.live import Live
    from rich.layout import Layout
    from rich.text import Text
    from rich.rule import Rule
    from rich.columns import Columns
    from rich.status import Status
    from rich.prompt import Prompt, Confirm
    from rich.tree import Tree
    from rich.align import Align
    from rich.padding import Padding
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

# 콘솔 설정
if RICH_AVAILABLE:
    console = Console(
        width=120,  # 적절한 너비 설정
        force_terminal=True,
        legacy_windows=False,
        color_system="truecolor"
    )
else:
    console = None


class EnhancedConsoleOutput:
    """향상된 콘솔 출력 관리자"""
    
    def __init__(self):
        self.console = console
        self.available = RICH_AVAILABLE
        
        # 색상 테마 정의 (2025년 트렌드 적용)
        self.colors = {
            'primary': '#0066CC',      # 메인 브랜드 색상
            'success': '#00B050',      # 성공 상태
            'warning': '#FF9900',      # 경고 상태
            'error': '#CC0000',        # 오류 상태
            'info': '#6B73FF',         # 정보성 메시지
            'secondary': '#6C757D',    # 보조 텍스트
            'accent': '#E066FF',       # 강조 색상
            'neutral': '#F8F9FA'       # 중립적 배경
        }
        
        # 아이콘 정의 (유니코드 기반, CP949 호환 fallback 포함)
        self.icons = {
            'success': '✅',
            'error': '❌', 
            'warning': '⚠️',
            'info': 'ℹ️',
            'loading': '⏳',
            'money': '💰',
            'chart': '📊',
            'rocket': '🚀',
            'gear': '⚙️',
            'clock': '🕐',
            'check': '✓',
            'cross': '✗',
            'arrow_right': '→',
            'arrow_up': '↑',
            'arrow_down': '↓',
            'dot': '•'
        }
        
        # CP949 호환 fallback 아이콘 (UTF-8 지원이 안 될 경우)
        self.fallback_icons = {
            'success': '[OK]',
            'error': '[ERROR]', 
            'warning': '[WARN]',
            'info': '[INFO]',
            'loading': '[...]',
            'money': '[MONEY]',
            'chart': '[CHART]',
            'rocket': '[START]',
            'gear': '[SETUP]',
            'clock': '[TIME]',
            'check': '[V]',
            'cross': '[X]',
            'arrow_right': '->',
            'arrow_up': '^',
            'arrow_down': 'v',
            'dot': '*'
        }
    
    def _get_safe_icon(self, icon_name: str) -> str:
        """안전한 아이콘 반환 (인코딩 오류 시 fallback 사용)"""
        try:
            # UTF-8 아이콘 사용 시도
            icon = self.icons.get(icon_name, self.icons['info'])
            # 테스트 출력으로 인코딩 가능 여부 확인
            icon.encode(sys.stdout.encoding or 'utf-8')
            return icon
        except (UnicodeEncodeError, AttributeError):
            # 인코딩 실패 시 fallback 아이콘 사용
            return self.fallback_icons.get(icon_name, '[INFO]')
    
    def print_system_header(self, title: str = "tideWise v11.0", subtitle: str = "한국투자증권 자동매매 시스템"):
        """시스템 헤더 출력"""
        if not self.available:
            print(f"\n{title}\n{subtitle}\n" + "="*60)
            return
            
        header_text = Text(title, style="bold white")
        subtitle_text = Text(subtitle, style=self.colors['secondary'])
        
        safe_rocket_icon = self._get_safe_icon('rocket')
        panel = Panel(
            Align.center(f"{header_text}\n{subtitle_text}"),
            style=f"bold {self.colors['primary']}",
            padding=(1, 2),
            title=f"{safe_rocket_icon} 실시간 자동매매",
            title_align="center"
        )
        
        self.console.print()
        self.console.print(panel)
        self.console.print()
    
    def print_menu(self, title: str, options: List[str], current_selection: Optional[str] = None):
        """깔끔한 메뉴 출력"""
        if not self.available:
            print(f"\n[ {title} ]")
            for i, option in enumerate(options, 1):
                marker = ">" if current_selection == str(i) else " "
                print(f"{marker} {i}. {option}")
            print("-" * 40)
            return
            
        menu_table = Table(show_header=False, show_lines=False, padding=(0, 1))
        menu_table.add_column("번호", style="bold cyan", width=4)
        menu_table.add_column("메뉴", style="white")
        
        for i, option in enumerate(options, 1):
            number_style = "bold green" if current_selection == str(i) else "cyan"
            option_style = "bold white" if current_selection == str(i) else "white"
            marker = f"{self.icons['arrow_right']} " if current_selection == str(i) else "  "
            
            menu_table.add_row(
                f"{marker}{i}",
                option,
                style=number_style
            )
        
        panel = Panel(
            menu_table,
            title=f"📋 {title}",
            border_style=self.colors['primary'],
            padding=(0, 1)
        )
        
        self.console.print(panel)
    
    def print_account_info(self, account_data: Dict[str, Any]):
        """계좌 정보 깔끔하게 출력"""
        if not self.available:
            account_type = account_data.get('account_type', '알 수 없음')
            balance = account_data.get('balance', 0)
            available = account_data.get('available_cash', 0)
            profit_rate = account_data.get('profit_rate', 0)
            holdings_count = len(account_data.get('holdings', []))
            
            print(f"\n[{account_type} 계좌 정보]")
            print(f"- 총 예수금: {balance:,.0f}원")
            print(f"- 주문가능: {available:,.0f}원") 
            print(f"- 수익률: {profit_rate:+.2f}%")
            print(f"- 보유종목: {holdings_count}개")
            return
            
        account_type = account_data.get('account_type', '알 수 없음')
        account_number = account_data.get('account_number', 'N/A')
        balance = account_data.get('balance', 0)
        available = account_data.get('available_cash', 0)
        profit_rate = account_data.get('profit_rate', 0)
        holdings = account_data.get('holdings', [])
        
        # 메인 계좌 정보 테이블
        info_table = Table(show_header=False, padding=(0, 2))
        info_table.add_column("항목", style="cyan", width=12)
        info_table.add_column("금액", style="bold white", justify="right")
        info_table.add_column("상태", style="green", justify="center")
        
        # 수익률 색상 결정
        profit_color = "green" if profit_rate >= 0 else "red"
        profit_icon = self.icons['arrow_up'] if profit_rate >= 0 else self.icons['arrow_down']
        
        info_table.add_row("총 예수금", f"{balance:,.0f}원", "")
        info_table.add_row("주문가능", f"{available:,.0f}원", f"{self.icons['check']}")
        info_table.add_row("수익률", f"{profit_rate:+.2f}%", f"[{profit_color}]{profit_icon}[/{profit_color}]")
        info_table.add_row("보유종목", f"{len(holdings)}개", f"{self.icons['chart']}")
        
        # 계좌 정보 패널
        account_panel = Panel(
            info_table,
            title=f"{self.icons['money']} {account_type} ({account_number})",
            border_style=self.colors['success'],
            padding=(1, 1)
        )
        
        self.console.print(account_panel)
        
        # 보유종목이 있으면 표시
        if holdings:
            self.print_holdings_table(holdings)
    
    def print_holdings_table(self, holdings: List[Dict]):
        """보유종목 테이블 출력"""
        if not self.available:
            print("\n[보유종목 현황]")
            for holding in holdings[:5]:  # 최대 5개만 표시
                name = holding.get('stock_name', '')
                code = holding.get('stock_code', '')
                quantity = holding.get('quantity', 0)
                current_price = holding.get('current_price', 0)
                profit_loss = holding.get('profit_loss', 0)
                profit_rate = holding.get('profit_rate', 0)
                
                print(f"  {name}({code}): {quantity:,}주 | {current_price:,.0f}원 | {profit_loss:+,.0f}원({profit_rate:+.2f}%)")
            return
            
        holdings_table = Table(title="보유종목 현황")
        holdings_table.add_column("종목명", style="cyan", width=15)
        holdings_table.add_column("수량", justify="right", style="white")
        holdings_table.add_column("현재가", justify="right", style="yellow")
        holdings_table.add_column("평가손익", justify="right")
        holdings_table.add_column("수익률", justify="center")
        
        for holding in holdings[:5]:  # 최대 5개만 표시
            name = holding.get('stock_name', '')
            code = holding.get('stock_code', '')
            quantity = holding.get('quantity', 0)
            current_price = holding.get('current_price', 0)
            profit_loss = holding.get('profit_loss', 0)
            profit_rate = holding.get('profit_rate', 0)
            
            # 수익률에 따른 색상
            if profit_rate > 0:
                profit_color = "green"
                rate_icon = self.icons['arrow_up']
            elif profit_rate < 0:
                profit_color = "red"
                rate_icon = self.icons['arrow_down']
            else:
                profit_color = "white"
                rate_icon = ""
            
            display_name = name[:12] + "..." if len(name) > 12 else name
            
            holdings_table.add_row(
                f"{display_name}\n[dim]({code})[/dim]",
                f"{quantity:,}주",
                f"{current_price:,.0f}원",
                f"[{profit_color}]{profit_loss:+,.0f}원[/{profit_color}]",
                f"[{profit_color}]{rate_icon}{profit_rate:+.2f}%[/{profit_color}]"
            )
        
        if len(holdings) > 5:
            holdings_table.add_row(
                f"[dim]... 외 {len(holdings)-5}개 종목[/dim]",
                "", "", "", ""
            )
        
        self.console.print(holdings_table)
    
    def print_trading_status(self, status: str, message: str = "", details: Dict = None):
        """매매 상태 출력"""
        if not self.available:
            print(f"\n[{status}] {message}")
            if details:
                for key, value in details.items():
                    print(f"  - {key}: {value}")
            return
            
        # 상태에 따른 색상과 아이콘 결정
        if status.upper() in ['SUCCESS', '성공', '완료']:
            color = self.colors['success']
            icon = self._get_safe_icon('success')
        elif status.upper() in ['ERROR', '오류', '실패']:
            color = self.colors['error']
            icon = self._get_safe_icon('error')
        elif status.upper() in ['WARNING', '경고']:
            color = self.colors['warning']
            icon = self._get_safe_icon('warning')
        elif status.upper() in ['INFO', '정보', '진행']:
            color = self.colors['info']
            icon = self._get_safe_icon('info')
        elif status.upper() in ['LOADING', '로딩', '처리중']:
            color = self.colors['info']
            icon = self._get_safe_icon('loading')
        else:
            color = self.colors['secondary']
            icon = self._get_safe_icon('dot')
        
        # 메인 상태 메시지
        status_text = Text()
        status_text.append(f"{icon} ", style=color)
        status_text.append(f"{status.upper()}", style=f"bold {color}")
        if message:
            status_text.append(f" - {message}", style="white")
        
        # 세부 정보가 있으면 테이블로 표시
        content = status_text
        if details:
            details_table = Table(show_header=False, padding=(0, 1))
            details_table.add_column("항목", style="cyan")
            details_table.add_column("내용", style="white")
            
            for key, value in details.items():
                details_table.add_row(f"{self.icons['dot']} {key}", str(value))
            
            from rich.console import Group
            content = Group(status_text, "", details_table)
        
        panel = Panel(
            content,
            border_style=color,
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def print_progress_bar(self, description: str, total: int = 100):
        """진행률 표시바 반환 (context manager)"""
        if not self.available:
            print(f"\n{description}...")
            return None
            
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            transient=False,
            console=self.console
        )
    
    def print_section_header(self, title: str, subtitle: str = ""):
        """섹션 헤더 출력"""
        if not self.available:
            print(f"\n{'='*20} {title} {'='*20}")
            if subtitle:
                print(subtitle)
            return
            
        if subtitle:
            header = f"{title}\n[dim]{subtitle}[/dim]"
        else:
            header = title
            
        self.console.print()
        self.console.rule(f"[bold {self.colors['primary']}]{header}[/]", style=self.colors['primary'])
        self.console.print()
    
    def print_error_details(self, error: Exception, context: str = ""):
        """오류 세부정보 출력"""
        if not self.available:
            print(f"\n[오류] {context}")
            print(f"상세: {str(error)}")
            return
            
        error_panel = Panel(
            f"[bold red]{self.icons['error']} 오류 발생[/bold red]\n\n"
            f"[yellow]컨텍스트:[/yellow] {context}\n"
            f"[yellow]상세 내용:[/yellow] {str(error)}",
            border_style="red",
            title="시스템 오류",
            padding=(1, 2)
        )
        
        self.console.print(error_panel)
    
    def clear_screen(self):
        """화면 지우기"""
        if self.available:
            self.console.clear()
        else:
            import os
            os.system('cls' if os.name == 'nt' else 'clear')
    
    def get_user_input(self, prompt: str, choices: List[str] = None) -> str:
        """사용자 입력 받기"""
        if not self.available:
            if choices:
                print(f"\n선택 가능한 옵션: {', '.join(choices)}")
            return input(f"{prompt}: ").strip()
            
        if choices:
            return Prompt.ask(
                f"[cyan]{prompt}[/cyan]",
                choices=choices,
                console=self.console
            )
        else:
            return Prompt.ask(
                f"[cyan]{prompt}[/cyan]",
                console=self.console
            )
    
    def get_user_confirmation(self, message: str, default: bool = False) -> bool:
        """사용자 확인 받기"""
        if not self.available:
            response = input(f"{message} (y/n): ").strip().lower()
            return response in ['y', 'yes', '예', 'ㅇ']
            
        return Confirm.ask(
            f"[yellow]{message}[/yellow]",
            default=default,
            console=self.console
        )


# 전역 인스턴스
_enhanced_console = None

def get_enhanced_console():
    """향상된 콘솔 인스턴스 반환"""
    global _enhanced_console
    if _enhanced_console is None:
        _enhanced_console = EnhancedConsoleOutput()
    return _enhanced_console


# 편의 함수들
def print_header(title: str = "tideWise v11.0", subtitle: str = "한국투자증권 자동매매 시스템"):
    """시스템 헤더 출력"""
    console_output = get_enhanced_console()
    console_output.print_system_header(title, subtitle)

def print_menu(title: str, options: List[str], current_selection: Optional[str] = None):
    """메뉴 출력"""
    console_output = get_enhanced_console()
    console_output.print_menu(title, options, current_selection)

def print_account(account_data: Dict[str, Any]):
    """계좌 정보 출력"""
    console_output = get_enhanced_console()
    console_output.print_account_info(account_data)

def print_status(status: str, message: str = "", details: Dict = None):
    """상태 출력"""
    console_output = get_enhanced_console()
    console_output.print_trading_status(status, message, details)

def print_section(title: str, subtitle: str = ""):
    """섹션 헤더 출력"""
    console_output = get_enhanced_console()
    console_output.print_section_header(title, subtitle)

def print_error(error: Exception, context: str = ""):
    """오류 출력"""
    console_output = get_enhanced_console()
    console_output.print_error_details(error, context)

def clear_screen():
    """화면 지우기"""
    console_output = get_enhanced_console()
    console_output.clear_screen()

def get_input(prompt: str, choices: List[str] = None) -> str:
    """사용자 입력"""
    console_output = get_enhanced_console()
    return console_output.get_user_input(prompt, choices)

def get_confirmation(message: str, default: bool = False) -> bool:
    """사용자 확인"""
    console_output = get_enhanced_console()
    return console_output.get_user_confirmation(message, default)