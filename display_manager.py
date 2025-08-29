#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Display Manager - 사용자 친화적 메시지 출력 관리
간소화된 메시지 표시와 색상 적용을 담당
"""

import sys
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from colorama import init, Fore, Back, Style

# UTF-8 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# colorama 초기화
init(autoreset=True)

class DisplayManager:
    """사용자 친화적 메시지 출력 관리자"""
    
    def __init__(self):
        """초기화"""
        self.countdown_active = False
        self.countdown_thread = None
        
        # 색상 정의
        self.colors = {
            'process': Fore.LIGHTBLUE_EX,      # 프로세스 시작/종료 (밝은 파란색)
            'profit': Fore.LIGHTMAGENTA_EX,    # 수익 (밝은 핑크/마젠타)
            'loss': Fore.LIGHTGREEN_EX,        # 손실 (밝은 초록색)
            'info': Fore.WHITE,                 # 일반 정보
            'warning': Fore.YELLOW,             # 경고
            'error': Fore.RED,                  # 오류
            'success': Fore.GREEN,              # 성공
            'header': Fore.CYAN + Style.BRIGHT, # 헤더
        }
    
    def process_start(self, process_name: str):
        """프로세스 시작 메시지"""
        print(f"{self.colors['process']}■ {process_name} 시작{Style.RESET_ALL}")
    
    def process_end(self, process_name: str):
        """프로세스 종료 메시지"""
        print(f"{self.colors['process']}■ {process_name} 종료{Style.RESET_ALL}")
    
    def display_account_info(self, account_data: Dict[str, Any], account_number: str = None):
        """
        계좌 정보 표시 (상세)
        
        Args:
            account_data: 계좌 정보 딕셔너리
            account_number: 계좌번호
        """
        print("\n" + "="*60)
        
        # 계좌 타입 표시
        account_type = account_data.get('account_type', 'UNKNOWN')
        if account_type == 'REAL':
            print(f"{self.colors['header']}【실제투자 계좌정보】{Style.RESET_ALL}")
        else:
            print(f"{self.colors['header']}【모의투자 계좌정보】{Style.RESET_ALL}")
        
        # 계좌번호 (뒤 01 제거)
        if account_number:
            display_account = account_number[:-2] if account_number.endswith('01') else account_number
            print(f"계좌번호: {display_account}")
        
        # 예수금 및 수익률
        available_cash = float(account_data.get('ord_psbl_cash', 0))
        total_asset = float(account_data.get('tot_evlu_amt', 0))
        deposit = float(account_data.get('dnca_tot_amt', 0))
        
        # 총 수익률 계산
        profit_rate = 0.0
        if deposit > 0:
            profit_rate = ((total_asset - deposit) / deposit) * 100
        
        # 수익률에 따른 색상 적용
        profit_color = self.colors['profit'] if profit_rate >= 0 else self.colors['loss']
        
        print(f"투자가능금액: {available_cash:,.0f}원")
        print(f"계좌 총 수익률: {profit_color}{profit_rate:+.1f}%{Style.RESET_ALL}")
        
        # 보유종목 현황
        holdings = account_data.get('output1', [])
        if holdings:
            print(f"\n보유종목 현황 (총 {len(holdings)}종목)")
            print("-" * 60)
            
            for stock in holdings:
                try:
                    # 보유수량이 0보다 큰 경우만 표시
                    qty = int(float(stock.get('hldg_qty', 0)))
                    if qty > 0:
                        stock_name = stock.get('prdt_name', '').strip()
                        stock_code = stock.get('pdno', '')
                        current_price = float(stock.get('prpr', 0))
                        total_value = qty * current_price
                        stock_profit_rate = float(stock.get('evlu_pfls_rt', 0))
                        
                        # 수익률 색상
                        stock_color = self.colors['profit'] if stock_profit_rate >= 0 else self.colors['loss']
                        
                        print(f"  • {stock_name}({stock_code})/{qty:,}주/{total_value:,.0f}원/{stock_color}{stock_profit_rate:+.1f}%{Style.RESET_ALL}")
                except:
                    continue
        else:
            print("\n보유종목 없음")
        
        print("="*60)
    
    def display_trading_result(self, trade_type: str, stock_name: str, stock_code: str, 
                              quantity: int, price: float, profit_rate: float = None):
        """
        매매 결과 표시
        
        Args:
            trade_type: "매수" 또는 "매도"
            stock_name: 종목명
            stock_code: 종목코드
            quantity: 수량
            price: 거래 단가
            profit_rate: 수익률 (매도시)
        """
        total_amount = quantity * price
        
        if trade_type == "매도" and profit_rate is not None:
            profit_color = self.colors['profit'] if profit_rate >= 0 else self.colors['loss']
            print(f"  {trade_type}: {stock_name}({stock_code})/{quantity:,}주/{total_amount:,.0f}원/{profit_color}{profit_rate:+.1f}%{Style.RESET_ALL}")
        else:
            print(f"  {trade_type}: {stock_name}({stock_code})/{quantity:,}주/{total_amount:,.0f}원")
    
    def display_algorithm_info(self, algorithm_name: str):
        """알고리즘 정보 표시"""
        print(f"\n{self.colors['info']}선택 알고리즘: {algorithm_name}{Style.RESET_ALL}")
    
    def display_countdown(self, seconds: int, message: str = "다음 자동매매까지"):
        """
        카운트다운 타이머 표시
        
        Args:
            seconds: 카운트다운 초
            message: 표시할 메시지
        """
        self.stop_countdown()  # 기존 카운트다운 중지
        
        self.countdown_active = True
        self.countdown_thread = threading.Thread(
            target=self._countdown_worker,
            args=(seconds, message),
            daemon=True
        )
        self.countdown_thread.start()
    
    def _countdown_worker(self, seconds: int, message: str):
        """카운트다운 워커 스레드"""
        remaining = seconds
        
        while remaining > 0 and self.countdown_active:
            minutes = remaining // 60
            secs = remaining % 60
            
            # 카운트다운 표시 (같은 줄에 업데이트)
            sys.stdout.write(f"\r{self.colors['info']}{message}: {minutes:02d}분 {secs:02d}초{Style.RESET_ALL}")
            sys.stdout.flush()
            
            time.sleep(1)
            remaining -= 1
        
        if self.countdown_active:
            sys.stdout.write("\r" + " " * 50 + "\r")  # 카운트다운 줄 지우기
            sys.stdout.flush()
    
    def stop_countdown(self):
        """카운트다운 중지"""
        self.countdown_active = False
        if self.countdown_thread:
            self.countdown_thread.join(timeout=1)
    
    def display_balance_process_start(self):
        """전일 잔고 처리 시작"""
        self.process_start("전일 잔고 처리")
    
    def display_balance_process_end(self):
        """전일 잔고 처리 종료"""
        self.process_end("전일 잔고 처리")
    
    def display_trading_start(self, algorithm_name: str):
        """자동매매 시작 표시"""
        print(f"\n{self.colors['success']}▶ 자동매매 시작 - {algorithm_name}{Style.RESET_ALL}")
    
    def display_trading_end(self):
        """자동매매 종료 표시"""
        print(f"{self.colors['success']}▶ 자동매매 종료{Style.RESET_ALL}\n")
    
    def display_simple_message(self, message: str, msg_type: str = 'info'):
        """
        간단한 메시지 표시
        
        Args:
            message: 표시할 메시지
            msg_type: 메시지 타입 (info, warning, error, success)
        """
        color = self.colors.get(msg_type, self.colors['info'])
        print(f"{color}{message}{Style.RESET_ALL}")
    
    def clear_line(self):
        """현재 줄 지우기"""
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
    
    def display_collected_stocks(self, stock_data: Dict[str, Any], title: str = "매수 후보 종목", show_buy_candidates_only: bool = True):
        """
        수집된 종목 정보 표시 (매수 후보 종목만)
        
        Args:
            stock_data: StockDataCollector에서 수집된 데이터
            title: 표시할 제목
            show_buy_candidates_only: 매수 후보 종목만 표시할지 여부
        """
        print(f"\n{self.colors['header']}{'='*50}{Style.RESET_ALL}")
        print(f"{self.colors['header']}【{title}】{Style.RESET_ALL}")
        print(f"{self.colors['header']}{'='*50}{Style.RESET_ALL}")
        
        if not stock_data or not isinstance(stock_data, dict):
            print(f"{self.colors['warning']}수집된 종목 데이터가 없습니다.{Style.RESET_ALL}")
            return
        
        # 수집 통계 정보 표시 (간단하게)
        collection_info = stock_data.get('collection_info', {})
        if collection_info:
            success_count = collection_info.get('success_count', 0)
            print(f"{self.colors['info']}매수 후보 종목: {success_count}개{Style.RESET_ALL}")
        
        # 테마별 종목 정보 표시
        theme_stocks = stock_data.get('theme_stocks', [])
        stock_info = stock_data.get('stock_info', {})
        
        # theme_stocks가 리스트인 경우와 딕셔너리인 경우 모두 처리
        if isinstance(theme_stocks, list):
            # 리스트인 경우: enhanced_theme_stocks.json에서 테마 정보 로드하여 그룹화
            theme_groups = self._load_theme_groups_from_json(theme_stocks, stock_info)
        elif isinstance(theme_stocks, dict):
            # 딕셔너리인 경우: 기존 로직 사용
            theme_groups = self._process_theme_dict(theme_stocks, stock_info)
        else:
            theme_groups = {}
        
        if not theme_groups and not stock_info:
            print(f"{self.colors['warning']}표시할 매수 후보 종목이 없습니다.{Style.RESET_ALL}")
            return
        
        # 매수 후보 종목만 필터링
        if show_buy_candidates_only:
            theme_groups = self._filter_buy_candidates(theme_groups)
        
        # 간단한 종목 목록 표시
        print(f"{self.colors['process']}[매수 후보 종목 목록]{Style.RESET_ALL}")
        
        all_candidates = []
        for theme_name, stocks in theme_groups.items():
            for stock in stocks:
                all_candidates.append(stock)
        
        # 20개 제한 적용
        if len(all_candidates) > 20:
            all_candidates = all_candidates[:20]
            print(f"{self.colors['warning']}※ 분석 효율성을 위해 상위 20개 종목만 표시합니다.{Style.RESET_ALL}")
        
        for idx, stock in enumerate(all_candidates, 1):
            stock_name = stock['name']
            stock_code = stock['code']
            print(f"  {idx:2d}. {stock_name}({stock_code})")
        
        # 추가 종목이 있으면 표시
        total_collected = sum(len(stocks) for stocks in theme_groups.values())
        if total_collected > len(all_candidates):
            additional_count = total_collected - len(all_candidates)
            print(f"     외 {additional_count}개")
        
        # 요약 정보 표시
        print(f"\n{self.colors['success']}총 {len(all_candidates)}개 매수 후보 종목{Style.RESET_ALL}")
        print(f"{self.colors['header']}{'='*50}{Style.RESET_ALL}")
    
    def display_stock_list_simple(self, stock_list: List[str], stock_names: Dict[str, str] = None, title: str = "종목 리스트"):
        """
        간단한 종목 리스트 표시
        
        Args:
            stock_list: 종목코드 리스트
            stock_names: 종목코드 -> 종목명 매핑 (선택사항)
            title: 표시할 제목
        """
        print(f"\n{self.colors['header']}【{title}】{Style.RESET_ALL}")
        print(f"{self.colors['header']}{'-'*40}{Style.RESET_ALL}")
        
        if not stock_list:
            print(f"{self.colors['warning']}표시할 종목이 없습니다.{Style.RESET_ALL}")
            return
        
        for idx, stock_code in enumerate(stock_list, 1):
            if stock_names and stock_code in stock_names:
                stock_name = stock_names[stock_code]
                print(f"  {idx:2d}. {stock_name}({stock_code})")
            else:
                print(f"  {idx:2d}. {stock_code}")
        
        print(f"\n{self.colors['info']}총 {len(stock_list)}개 종목{Style.RESET_ALL}")
        print(f"{self.colors['header']}{'-'*40}{Style.RESET_ALL}")
    
    def display_analysis_start(self, analysis_type: str = "투자 전 분석"):
        """분석 시작 표시"""
        print(f"\n{self.colors['process']}■ {analysis_type} 시작{Style.RESET_ALL}")
    
    def display_analysis_end(self, analysis_type: str = "투자 전 분석"):
        """분석 종료 표시"""
        print(f"{self.colors['process']}■ {analysis_type} 완료{Style.RESET_ALL}\n")
    
    def _load_theme_groups_from_json(self, theme_stocks: List[str], stock_info: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """enhanced_theme_stocks.json에서 테마 정보를 로드하여 종목을 그룹화"""
        theme_groups = {}
        
        try:
            import json
            from pathlib import Path
            
            # enhanced_theme_stocks.json 파일 로드
            json_file = Path(__file__).parent.parent / "support" / "enhanced_theme_stocks.json"
            if not json_file.exists():
                json_file = Path(__file__).parent / "enhanced_theme_stocks.json"
            
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    theme_data = json.load(f)
                
                # 각 테마별로 종목을 그룹화
                for theme_name, theme_info in theme_data.items():
                    if not theme_name.startswith('_') and isinstance(theme_info, dict):
                        theme_stock_list = theme_info.get('stocks', [])
                        theme_groups[theme_name] = []
                        
                        for stock_code in theme_stock_list:
                            if stock_code in theme_stocks:  # 실제 수집된 종목 중에서만
                                if stock_code in stock_info and isinstance(stock_info[stock_code], dict):
                                    theme_groups[theme_name].append({
                                        'code': stock_code,
                                        'name': stock_info[stock_code].get('name', stock_code),
                                        'info': stock_info[stock_code]
                                    })
                                else:
                                    # stock_info가 없는 경우 기본 정보 생성
                                    theme_groups[theme_name].append({
                                        'code': stock_code,
                                        'name': stock_code,
                                        'info': {'name': stock_code}
                                    })
                        
                        # 빈 테마는 제거
                        if not theme_groups[theme_name]:
                            del theme_groups[theme_name]
            
            # 테마에 속하지 않는 종목들은 '기타'로 분류
            categorized_stocks = set()
            for stocks in theme_groups.values():
                for stock in stocks:
                    categorized_stocks.add(stock['code'])
            
            uncategorized_stocks = [code for code in theme_stocks if code not in categorized_stocks]
            if uncategorized_stocks:
                theme_groups['기타'] = []
                for stock_code in uncategorized_stocks:
                    if stock_code in stock_info and isinstance(stock_info[stock_code], dict):
                        theme_groups['기타'].append({
                            'code': stock_code,
                            'name': stock_info[stock_code].get('name', stock_code),
                            'info': stock_info[stock_code]
                        })
                    else:
                        theme_groups['기타'].append({
                            'code': stock_code,
                            'name': stock_code,
                            'info': {'name': stock_code}
                        })
            
        except Exception as e:
            # JSON 로드 실패시 모든 종목을 '수집된 종목'으로 분류
            theme_groups = {'수집된 종목': []}
            for stock_code in theme_stocks:
                if stock_code in stock_info and isinstance(stock_info[stock_code], dict):
                    theme_groups['수집된 종목'].append({
                        'code': stock_code,
                        'name': stock_info[stock_code].get('name', stock_code),
                        'info': stock_info[stock_code]
                    })
                else:
                    theme_groups['수집된 종목'].append({
                        'code': stock_code,
                        'name': stock_code,
                        'info': {'name': stock_code}
                    })
        
        return theme_groups
    
    def _process_theme_dict(self, theme_stocks: Dict[str, List[str]], stock_info: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """딕셔너리 형태의 theme_stocks 처리"""
        theme_groups = {}
        
        for theme_name, theme_stock_list in theme_stocks.items():
            theme_groups[theme_name] = []
            
            for stock_code in theme_stock_list:
                if stock_code in stock_info and isinstance(stock_info[stock_code], dict):
                    theme_groups[theme_name].append({
                        'code': stock_code,
                        'name': stock_info[stock_code].get('name', stock_code),
                        'info': stock_info[stock_code]
                    })
                else:
                    theme_groups[theme_name].append({
                        'code': stock_code,
                        'name': stock_code,
                        'info': {'name': stock_code}
                    })
        
        return theme_groups
    
    def _filter_buy_candidates(self, theme_groups: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """매수 후보 종목만 필터링 (현재는 모든 종목이 매수 후보로 간주)"""
        # TODO: 실제 매수 조건 필터링 로직 추가 가능
        # 예: 거래량, 시가총액, 기술적 지표 등을 고려한 필터링
        
        # 현재는 모든 수집된 종목을 매수 후보로 간주
        buy_candidates = {}
        
        # 우선순위 테마 정렬 (Core_Large_Cap 우선)
        priority_themes = ['Core_Large_Cap', 'AI_Semiconductor', 'Battery_EV', 'Bio_Healthcare', 'Gaming_Platform', 'Defense_Tech']
        
        # 우선순위에 따라 정렬
        for theme in priority_themes:
            if theme in theme_groups and theme_groups[theme]:
                buy_candidates[theme] = theme_groups[theme]
        
        # 나머지 테마 추가
        for theme, stocks in theme_groups.items():
            if theme not in buy_candidates and stocks:
                buy_candidates[theme] = stocks
        
        return buy_candidates


# 전역 인스턴스
_display_manager = None

def get_display_manager() -> DisplayManager:
    """DisplayManager 싱글톤 인스턴스 반환"""
    global _display_manager
    if _display_manager is None:
        _display_manager = DisplayManager()
    return _display_manager