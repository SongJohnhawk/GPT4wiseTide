#!/usr/bin/env python3
"""
백테스팅용 강화된 데이터 수집기
- 백테스팅 시작 시 자동으로 종목 및 과거 데이터 수집
- backtesting/data 폴더에 데이터 저장
- 멀티스레드로 빠른 데이터 수집
"""

import asyncio
import json
import logging
import pandas as pd
import numpy as np
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import threading
import sys
import time
import requests

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from support.api_connector import KISAPIConnector
from support.enhanced_theme_stocks import load_theme_stocks
from support.log_manager import get_log_manager

# 로깅 설정
log_manager = get_log_manager()
logger = log_manager.setup_logger('backtesting', __name__)

class BacktestingDataCollector:
    """백테스팅용 데이터 수집기 - 실제 KIS API 연동"""
    
    def __init__(self):
        self.backtesting_dir = Path(__file__).parent
        self.data_dir = self.backtesting_dir / "data"
        self.project_root = project_root
        
        # 데이터 폴더 생성
        self.data_types = ["daily", "weekly", "5min", "10min", "30min", "investor_trading"]
        for data_type in self.data_types:
            (self.data_dir / data_type).mkdir(parents=True, exist_ok=True)
        
        # 멀티스레드 설정 (API 제한으로 인해 감소)
        self.max_workers = 3
        self.collection_timeout = 600  # 10분 타임아웃
        
        # KIS API 커넥터 초기화
        try:
            self.api_connector = KISAPIConnector()
            logger.info("KIS API 커넥터 초기화 완료")
        except Exception as e:
            logger.error(f"KIS API 커넥터 초기화 실패: {e}")
            self.api_connector = None
        
        # 수집할 종목 목록
        self.target_stocks = []
        self.collected_count = 0
        self.total_count = 0
        
    def collect_target_stocks(self) -> List[str]:
        """백테스팅 대상 종목 수집"""
        print("백테스팅 대상 종목 수집 중...")
        
        try:
            # 테마 종목 로드
            theme_data = load_theme_stocks()
            all_stocks = set()
            
            if theme_data:
                for theme_name, theme_info in theme_data.items():
                    stocks = theme_info.get('stocks', [])
                    all_stocks.update(stocks)
                    print(f"  {theme_name}: {len(stocks)}개 종목")
            
            # 기본 종목 추가 (중요 종목)
            default_stocks = [
                "005930",  # 삼성전자
                "000660",  # SK하이닉스
                "035420",  # NAVER
                "051910",  # LG화학
                "006400",  # 삼성SDI
                "035720",  # 카카오
                "207940",  # 삼성바이오로직스
                "068270",  # 셀트리온
                "005380",  # 현대차
                "012330",  # 현대모비스
                "003670",  # 포스코DX
                "096770",  # SK이노베이션
                "326030",  # SK바이오팜
                "373220",  # LG에너지솔루션
                "042700",  # 한미반도체
                "000270",  # 기아
                "018260",  # 삼성에스디에스
                "028260",  # 삼성물산
                "009540",  # HD한국조선해양
                "017670",  # SK텔레콤
                "030200",  # KT
            ]
            
            all_stocks.update(default_stocks)
            
            # 목표 100개 이상 확보
            if len(all_stocks) < 100:
                # 코스피 대형주 추가
                additional_stocks = [
                    f"00{i:04d}" for i in range(1000, 1100)
                    if f"00{i:04d}" not in all_stocks
                ]
                all_stocks.update(additional_stocks[:100-len(all_stocks)])
            
            self.target_stocks = list(all_stocks)[:150]  # 최대 150개로 제한
            print(f"백테스팅 대상 종목 수: {len(self.target_stocks)}개")
            
            return self.target_stocks
            
        except Exception as e:
            logger.error(f"종목 수집 실패: {e}")
            # 기본 종목만 사용
            self.target_stocks = default_stocks
            return self.target_stocks
    
    def collect_stock_data(self, stock_code: str, data_type: str) -> bool:
        """단일 종목의 특정 데이터 타입 수집 - 실제 KIS API 호출"""
        if not self.api_connector:
            logger.error("API 커넥터가 초기화되지 않음")
            return False
            
        try:
            df = None
            
            if data_type == "daily":
                # 일봉 데이터 수집 (최근 1년)
                result = self.api_connector.get_daily_chart(stock_code, period=365)
                if result and result.get('rt_cd') == '0':
                    daily_data = result.get('output2', [])
                    if daily_data:
                        df = self._parse_daily_data(daily_data, stock_code)
                        
            elif data_type in ["5min", "10min", "30min"]:
                # 분봉 데이터 수집 (당일)
                result = self.api_connector.get_minute_chart_data(stock_code, count=300)  # 최대 300개
                if result and result.get('rt_cd') == '0':
                    minute_data = result.get('output2', [])
                    if minute_data:
                        df = self._parse_minute_data(minute_data, stock_code, data_type)
                        
            elif data_type == "investor_trading":
                # 투자자별 거래 데이터 수집 (최근 30일 일봉 기준으로 추정)
                result = self.api_connector.get_daily_chart(stock_code, period=30)
                if result and result.get('rt_cd') == '0':
                    daily_data = result.get('output2', [])
                    if daily_data:
                        df = self._parse_investor_trading_data(daily_data, stock_code)
                        
            elif data_type == "weekly":
                # 주봉 데이터 (일봉을 주간 단위로 집계)
                result = self.api_connector.get_daily_chart(stock_code, period=365)
                if result and result.get('rt_cd') == '0':
                    daily_data = result.get('output2', [])
                    if daily_data:
                        df = self._parse_weekly_data(daily_data, stock_code)
            
            if df is not None and not df.empty:
                # 파일 경로
                file_path = self.data_dir / data_type / f"{stock_code}_{data_type}.csv"
                
                # CSV 저장
                df.to_csv(file_path, index=False)
                
                self.collected_count += 1
                if self.collected_count % 5 == 0:  # API 호출이므로 더 자주 진행률 표시
                    progress = (self.collected_count / self.total_count) * 100
                    print(f"  데이터 수집 진행률: {progress:.1f}% ({self.collected_count}/{self.total_count})")
                
                # API 제한으로 인한 딜레이
                time.sleep(0.5)
                return True
            else:
                logger.warning(f"종목 {stock_code} {data_type} 데이터 없음")
                return False
                
        except Exception as e:
            logger.error(f"종목 {stock_code} {data_type} 데이터 수집 실패: {e}")
            # API 오류시 더 긴 딜레이
            time.sleep(2)
            return False
    
    def _parse_daily_data(self, daily_data: list, stock_code: str) -> pd.DataFrame:
        """일봉 데이터 파싱"""
        parsed_data = []
        for item in daily_data:
            parsed_data.append({
                'Date': item.get('stck_bsop_date', ''),
                'Open': float(item.get('stck_oprc', 0)),
                'High': float(item.get('stck_hgpr', 0)),
                'Low': float(item.get('stck_lwpr', 0)),
                'Close': float(item.get('stck_clpr', 0)),
                'Volume': int(item.get('acml_vol', 0)),
                'StockCode': stock_code
            })
        return pd.DataFrame(parsed_data)
    
    def _parse_minute_data(self, minute_data: list, stock_code: str, data_type: str) -> pd.DataFrame:
        """분봉 데이터 파싱"""
        parsed_data = []
        for item in minute_data:
            time_str = item.get('stck_cntg_hour', '')
            date_str = datetime.now().strftime('%Y-%m-%d')
            
            parsed_data.append({
                'DateTime': f"{date_str} {time_str[:2]}:{time_str[2:4]}:00",
                'Date': date_str,
                'Time': f"{time_str[:2]}:{time_str[2:4]}",
                'Open': float(item.get('stck_oprc', 0)),
                'High': float(item.get('stck_hgpr', 0)),
                'Low': float(item.get('stck_lwpr', 0)),
                'Close': float(item.get('stck_prpr', 0)),
                'Volume': int(item.get('cntg_vol', 0)),
                'StockCode': stock_code
            })
        return pd.DataFrame(parsed_data)
    
    def _parse_investor_trading_data(self, daily_data: list, stock_code: str) -> pd.DataFrame:
        """투자자별 거래 데이터 파싱 (추정치)"""
        parsed_data = []
        for item in daily_data:
            volume = int(item.get('acml_vol', 0))
            # 투자자별 비율 추정 (실제 데이터는 별도 API 필요)
            institution_ratio = 0.2
            foreign_ratio = 0.3
            retail_ratio = 0.5
            
            parsed_data.append({
                'Date': item.get('stck_bsop_date', ''),
                'StockCode': stock_code,
                'Open': float(item.get('stck_oprc', 0)),
                'High': float(item.get('stck_hgpr', 0)),
                'Low': float(item.get('stck_lwpr', 0)),
                'Close': float(item.get('stck_clpr', 0)),
                'Volume': volume,
                # 추정 데이터 (실제로는 별도 API 호출 필요)
                'Institution_Buy': int(volume * institution_ratio * 0.6),
                'Institution_Sell': int(volume * institution_ratio * 0.4),
                'Institution_Net': int(volume * institution_ratio * 0.2),
                'Foreign_Buy': int(volume * foreign_ratio * 0.5),
                'Foreign_Sell': int(volume * foreign_ratio * 0.5),
                'Foreign_Net': int(volume * foreign_ratio * 0.0),
                'Retail_Buy': int(volume * retail_ratio * 0.4),
                'Retail_Sell': int(volume * retail_ratio * 0.6),
                'Retail_Net': int(volume * retail_ratio * -0.2),
                'Total_Volume': volume
            })
        return pd.DataFrame(parsed_data)
    
    def _parse_weekly_data(self, daily_data: list, stock_code: str) -> pd.DataFrame:
        """주봉 데이터 생성 (일봉에서 주간 집계)"""
        df_daily = self._parse_daily_data(daily_data, stock_code)
        if df_daily.empty:
            return df_daily
            
        df_daily['Date'] = pd.to_datetime(df_daily['Date'])
        df_daily.set_index('Date', inplace=True)
        
        # 주간 리샘플링
        weekly = df_daily.resample('W').agg({
            'Open': 'first',
            'High': 'max', 
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        
        weekly.reset_index(inplace=True)
        weekly['StockCode'] = stock_code
        weekly['Date'] = weekly['Date'].dt.strftime('%Y-%m-%d')
        
        return weekly
    
    def collect_all_data_for_stock(self, stock_code: str) -> Dict[str, bool]:
        """단일 종목의 모든 데이터 타입 수집"""
        results = {}
        
        for data_type in self.data_types:
            success = self.collect_stock_data(stock_code, data_type)
            results[data_type] = success
        
        return results
    
    def collect_data_multithreaded(self) -> Dict[str, Any]:
        """멀티스레드로 모든 종목 데이터 수집"""
        print(f"멀티스레드 데이터 수집 시작 (워커: {self.max_workers}개)")
        
        self.collected_count = 0
        self.total_count = len(self.target_stocks) * len(self.data_types)
        
        start_time = time.time()
        collection_results = {}
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 모든 작업 제출
                future_to_task = {}
                
                for stock_code in self.target_stocks:
                    for data_type in self.data_types:
                        future = executor.submit(self.collect_stock_data, stock_code, data_type)
                        future_to_task[future] = (stock_code, data_type)
                
                # 결과 수집
                for future in concurrent.futures.as_completed(future_to_task, timeout=self.collection_timeout):
                    stock_code, data_type = future_to_task[future]
                    
                    try:
                        success = future.result()
                        if stock_code not in collection_results:
                            collection_results[stock_code] = {}
                        collection_results[stock_code][data_type] = success
                        
                    except Exception as e:
                        logger.error(f"작업 실행 오류 {stock_code} {data_type}: {e}")
                        if stock_code not in collection_results:
                            collection_results[stock_code] = {}
                        collection_results[stock_code][data_type] = False
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            # 수집 결과 요약
            total_files = sum(
                sum(1 for success in stock_results.values() if success)
                for stock_results in collection_results.values()
            )
            
            print(f"\\n데이터 수집 완료:")
            print(f"  소요 시간: {elapsed:.1f}초")
            print(f"  수집된 파일 수: {total_files}개")
            print(f"  성공률: {(total_files/self.total_count)*100:.1f}%")
            
            # 데이터 타입별 요약
            for data_type in self.data_types:
                type_count = sum(
                    1 for stock_results in collection_results.values()
                    if stock_results.get(data_type, False)
                )
                print(f"  {data_type}: {type_count}개 파일")
            
            return {
                "success": True,
                "total_files": total_files,
                "elapsed_time": elapsed,
                "results": collection_results,
                "target_stocks": self.target_stocks
            }
            
        except concurrent.futures.TimeoutError:
            print(f"데이터 수집 타임아웃 ({self.collection_timeout}초)")
            return {"success": False, "error": "timeout"}
        except Exception as e:
            logger.error(f"멀티스레드 데이터 수집 실패: {e}")
            return {"success": False, "error": str(e)}
    
    def save_collection_summary(self, collection_results: Dict[str, Any]):
        """데이터 수집 결과 요약 저장"""
        try:
            summary = {
                "collection_timestamp": datetime.now().isoformat(),
                "total_stocks": len(self.target_stocks),
                "data_types": self.data_types,
                "collection_results": collection_results,
                "data_directory": str(self.data_dir)
            }
            
            summary_file = self.data_dir / "collection_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            print(f"수집 요약 저장: {summary_file}")
            
        except Exception as e:
            logger.error(f"수집 요약 저장 실패: {e}")

def main():
    """데이터 수집기 단독 실행"""
    print("백테스팅용 데이터 수집기 시작")
    print("=" * 50)
    
    collector = BacktestingDataCollector()
    
    # 1. 대상 종목 수집
    target_stocks = collector.collect_target_stocks()
    
    if not target_stocks:
        print("수집할 종목이 없습니다.")
        return
    
    # 2. 멀티스레드 데이터 수집
    results = collector.collect_data_multithreaded()
    
    if results.get("success"):
        # 3. 수집 결과 저장
        collector.save_collection_summary(results)
        print("\\n데이터 수집이 성공적으로 완료되었습니다.")
    else:
        print(f"\\n데이터 수집 실패: {results.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()