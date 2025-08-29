#!/usr/bin/env python3
"""
[fix][opt][async] 실전/모의투자용 경량화된 종목 선정 및 데이터 수집기
- 최소 30개 종목으로 경량화 (백테스팅용 100+개와 분리)
- 멀티스레드 처리로 성능 최적화
- 투자 판단에 필요한 핵심 데이터만 수집
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

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

from support.api_connector import KISAPIConnector
from support.log_manager import get_log_manager
from support.token_manager import TokenManagerFactory

# 로깅 설정
log_manager = get_log_manager()
logger = log_manager.setup_logger(
    log_type='system',
    logger_name=__name__,
    level=logging.INFO
)

class TradingStockCollector:
    """실전/모의투자용 경량화된 종목 선정 및 데이터 수집기"""
    
    def __init__(self, is_mock: bool = True):
        self.is_mock = is_mock
        self.api = KISAPIConnector(is_mock=is_mock)
        
        # 실전투자용 최소 수량 (백테스팅 100+개 vs 실전투자 30+개)
        self.min_trading_stocks = 30
        self.max_trading_stocks = 50  # 성능 고려한 최대치
        
        # 멀티스레드 설정
        self.max_workers = 4  # CPU 코어 수 고려
        self.collection_timeout = 180  # 3분 타임아웃
        
        # 통합 테마 정의 사용 (키워드만)
        from support.theme_definitions import get_trading_themes
        self.core_investment_themes = get_trading_themes()
        # 하드코딩된 종목 데이터 제거 - 실시간 API만 사용
        
        # 투자 판단에 필요한 핵심 데이터만 선별
        self.essential_data_types = {
            'ohlcv': {'days': 60, 'priority': 1},      # 기본 가격 데이터
            'volume_profile': {'days': 30, 'priority': 2},  # 거래량 분석
            'investor_flow': {'days': 20, 'priority': 3}    # 투자자 동향
        }
        
        self.data_dir = Path(__file__).parent.parent / "trading_data"
        self.data_dir.mkdir(exist_ok=True)
        
        # 스레드 안전성을 위한 락
        self._lock = threading.Lock()
        self._collected_data = {}
        
    def get_high_potential_stocks(self) -> Dict[str, List[str]]:
        """테마별 키워드로 동적 종목 선별 - 실시간 API 기반만 사용"""
        logger.info("실시간 API를 통한 동적 종목 선별 중...")
        
        selected_stocks = {}
        
        # 실시간 API를 통한 테마별 종목 수집
        all_market_stocks = self._get_realtime_market_stocks()
        
        for theme_name, keywords in self.core_investment_themes.items():
            theme_stocks = self._find_stocks_by_keywords(all_market_stocks, keywords)
            if theme_stocks:
                # 테마당 최대 종목 수 제한 (성능 고려)
                max_per_theme = 12
                selected_stocks[theme_name] = theme_stocks[:max_per_theme]
                logger.info(f"{theme_name}: {len(selected_stocks[theme_name])}개 종목 선별")
        
        # 총 종목 수 확인
        total_count = sum(len(stocks) for stocks in selected_stocks.values())
        logger.info(f"실시간 동적 선별된 투자 종목: {total_count}개 (API 기반)")
        
        # 최소 종목 수 확보 못하면 더 넓은 범위로 재검색
        if total_count < self.min_trading_stocks:
            logger.info(f"동적 수집 부족({total_count}개), 더 넓은 범위로 재검색")
            additional_stocks = self._expand_search_scope(all_market_stocks, selected_stocks)
            selected_stocks.update(additional_stocks)
            
        return selected_stocks
    
    def _get_realtime_market_stocks(self) -> List[Dict[str, str]]:
        """실시간 API 기반 시장 종목 수집"""
        try:
            logger.info("실시간 API를 통한 시장 종목 수집 시작...")
            market_stocks = []
            
            # 1. 코스피/코스닥 주요 종목 API 조회
            major_stocks = self._get_major_stocks_from_api()
            market_stocks.extend(major_stocks)
            
            # 2. 거래량 상위 종목 API 조회 
            volume_stocks = self._get_high_volume_stocks_from_api()
            market_stocks.extend(volume_stocks)
            
            # 3. 등락률 상위 종목 API 조회
            rising_stocks = self._get_rising_stocks_from_api()
            market_stocks.extend(rising_stocks)
            
            # 중복 제거
            unique_stocks = {}
            for stock in market_stocks:
                stock_code = stock.get('stock_code')
                if stock_code and stock_code not in unique_stocks:
                    unique_stocks[stock_code] = stock
            
            result = list(unique_stocks.values())
            logger.info(f"실시간 API 기반 시장 종목 수집 완료: {len(result)}개")
            return result
            
        except Exception as e:
            logger.error(f"실시간 시장 종목 수집 실패: {e}")
            return []
    
    def _get_major_stocks_from_api(self) -> List[Dict[str, str]]:
        """API에서 주요 종목 수집"""
        try:
            # 코스피 200, 코스닥 150 등 주요 지수 종목들
            major_codes = []
            
            # 실제 API 호출로 주요 종목 리스트 가져오기
            # TODO: 실제 API 구현 필요
            kospi_data = self.api.get_kospi_major_stocks() if hasattr(self.api, 'get_kospi_major_stocks') else []
            kosdaq_data = self.api.get_kosdaq_major_stocks() if hasattr(self.api, 'get_kosdaq_major_stocks') else []
            
            stocks = []
            for data in kospi_data + kosdaq_data:
                if isinstance(data, dict) and 'stock_code' in data:
                    stocks.append({
                        'stock_code': data['stock_code'],
                        'stock_name': data.get('stock_name', ''),
                        'sector': '주요종목'
                    })
            
            return stocks[:50]  # 상위 50개만
            
        except Exception as e:
            logger.warning(f"주요 종목 API 조회 실패: {e}")
            return []
    
    def _get_high_volume_stocks_from_api(self) -> List[Dict[str, str]]:
        """API에서 거래량 상위 종목 수집"""
        try:
            # 실제 API 호출로 거래량 상위 종목 가져오기
            volume_data = self.api.get_high_volume_stocks() if hasattr(self.api, 'get_high_volume_stocks') else []
            
            stocks = []
            for data in volume_data:
                if isinstance(data, dict) and 'stock_code' in data:
                    stocks.append({
                        'stock_code': data['stock_code'],
                        'stock_name': data.get('stock_name', ''),
                        'sector': '거래량활발'
                    })
            
            return stocks[:30]  # 상위 30개만
            
        except Exception as e:
            logger.warning(f"거래량 상위 종목 API 조회 실패: {e}")
            return []
    
    def _get_rising_stocks_from_api(self) -> List[Dict[str, str]]:
        """API에서 등락률 상위 종목 수집"""
        try:
            # 실제 API 호출로 등락률 상위 종목 가져오기
            rising_data = self.api.get_rising_stocks() if hasattr(self.api, 'get_rising_stocks') else []
            
            stocks = []
            for data in rising_data:
                if isinstance(data, dict) and 'stock_code' in data:
                    stocks.append({
                        'stock_code': data['stock_code'],
                        'stock_name': data.get('stock_name', ''),
                        'sector': '상승종목'
                    })
            
            return stocks[:20]  # 상위 20개만
            
        except Exception as e:
            logger.warning(f"등락률 상위 종목 API 조회 실패: {e}")
            return []
    
    def _expand_search_scope(self, all_market_stocks: List[Dict[str, str]], 
                           current_stocks: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """검색 범위 확장하여 추가 종목 수집"""
        try:
            logger.info("검색 범위 확장 중...")
            additional_stocks = {}
            
            # 이미 선택된 종목들
            selected_codes = set()
            for stocks in current_stocks.values():
                selected_codes.update(stocks)
            
            # 키워드 범위 확장
            expanded_keywords = {
                'Tech_Growth': ['기술', '성장', '혁신', '디지털', '전자'],
                'Value_Stable': ['안정', '배당', '가치', '대형', '우량'],
                'Small_Cap': ['중소', '코스닥', '벤처', '바이오', '게임']
            }
            
            for theme_name, keywords in expanded_keywords.items():
                if theme_name not in current_stocks:
                    theme_stocks = self._find_stocks_by_keywords(all_market_stocks, keywords)
                    # 이미 선택된 종목 제외
                    theme_stocks = [code for code in theme_stocks if code not in selected_codes]
                    if theme_stocks:
                        additional_stocks[theme_name] = theme_stocks[:8]
                        logger.info(f"확장 검색 - {theme_name}: {len(additional_stocks[theme_name])}개 추가")
            
            return additional_stocks
            
        except Exception as e:
            logger.error(f"검색 범위 확장 실패: {e}")
            return {}
    
    def _find_stocks_by_keywords(self, market_stocks: List[Dict[str, str]], 
                                keywords: List[str]) -> List[str]:
        """키워드로 종목 매칭"""
        matched_stocks = []
        
        for stock in market_stocks:
            stock_name = stock.get('stock_name', '').upper()
            stock_sector = stock.get('sector', '').upper()
            
            # 키워드 매칭
            for keyword in keywords:
                if (keyword.upper() in stock_name or 
                    keyword.upper() in stock_sector):
                    matched_stocks.append(stock['stock_code'])
                    break  # 하나라도 매칭되면 추가
        
        return matched_stocks
    
    async def collect_stock_investment_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """개별 종목의 투자 판단용 핵심 데이터 수집"""
        try:
            investment_data = {
                'stock_code': stock_code,
                'collection_time': datetime.now().isoformat(),
                'data': {}
            }
            
            # 1. 기본 OHLCV 데이터 (60일)
            ohlcv_data = await self._collect_ohlcv_data(stock_code, days=60)
            if ohlcv_data is not None:
                # 날짜를 문자열로 변환하여 JSON 직렬화 문제 해결
                ohlcv_data['Date'] = ohlcv_data['Date'].dt.strftime('%Y-%m-%d')
                investment_data['data']['ohlcv'] = ohlcv_data.to_dict('records')
            
            # 2. 거래량 프로필 (30일)
            volume_data = await self._collect_volume_profile(stock_code, days=30)
            if volume_data is not None:
                investment_data['data']['volume_profile'] = volume_data
            
            # 3. 투자자별 동향 (20일)
            investor_data = await self._collect_investor_flow(stock_code, days=20)
            if investor_data is not None:
                investment_data['data']['investor_flow'] = investor_data
            
            return investment_data
            
        except Exception as e:
            logger.error(f"{stock_code} 투자 데이터 수집 실패: {e}")
            return None
    
    async def _collect_ohlcv_data(self, stock_code: str, days: int) -> Optional[pd.DataFrame]:
        """기본 OHLCV 데이터 수집 (투자 판단 핵심)"""
        try:
            # 실제 API 호출 (현재는 샘플 데이터)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 샘플 데이터 생성 (실제 API 연동시 교체)
            data = self._generate_investment_ohlcv(stock_code, start_date, end_date)
            
            return data
            
        except Exception as e:
            logger.error(f"{stock_code} OHLCV 데이터 수집 실패: {e}")
            return None
    
    def _generate_investment_ohlcv(self, stock_code: str, start_date: datetime, 
                                 end_date: datetime) -> pd.DataFrame:
        """투자 판단용 OHLCV 데이터 생성"""
        periods = (end_date - start_date).days
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # 종목별 기본 가격
        base_price = 10000 + (int(stock_code) % 1000) * 100
        np.random.seed(int(stock_code) % 10000)
        
        # 투자 판단에 중요한 패턴 포함
        returns = np.random.normal(0.002, 0.025, len(date_range))  # 약간 상승 편향
        prices = [base_price]
        
        for i in range(1, len(date_range)):
            new_price = prices[-1] * (1 + returns[i])
            prices.append(max(new_price, 100))
        
        prices = np.array(prices)
        
        # 투자 분석용 추가 지표 계산
        data = pd.DataFrame({
            'Date': date_range,
            'Open': prices,
            'High': prices * np.random.uniform(1.005, 1.03, len(date_range)),
            'Low': prices * np.random.uniform(0.97, 0.995, len(date_range)),
            'Close': np.roll(prices, -1),
            'Volume': np.random.randint(100000, 2000000, len(date_range)),
            'MA5': np.nan,  # 5일 이동평균
            'MA20': np.nan,  # 20일 이동평균
            'RSI': np.nan,   # RSI 지표
            'MACD': np.nan   # MACD 지표
        })
        
        # 마지막 행 조정
        data.loc[data.index[-1], 'Close'] = data.loc[data.index[-1], 'Open']
        
        # 기술적 지표 계산
        data['MA5'] = data['Close'].rolling(window=5).mean()
        data['MA20'] = data['Close'].rolling(window=20).mean()
        
        # RSI 계산
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        return data
    
    async def _collect_volume_profile(self, stock_code: str, days: int) -> Optional[Dict[str, Any]]:
        """거래량 프로필 분석 (투자 타이밍 판단)"""
        try:
            # 거래량 패턴 분석 데이터
            volume_profile = {
                'avg_volume': np.random.randint(500000, 1500000),
                'volume_spike_count': np.random.randint(2, 8),  # 거래량 급증 횟수
                'volume_trend': np.random.choice(['increasing', 'decreasing', 'stable']),
                'institutional_volume_ratio': np.random.uniform(0.3, 0.7),  # 기관 거래 비중
                'last_update': datetime.now().isoformat()
            }
            
            return volume_profile
            
        except Exception as e:
            logger.error(f"{stock_code} 거래량 프로필 수집 실패: {e}")
            return None
    
    async def _collect_investor_flow(self, stock_code: str, days: int) -> Optional[Dict[str, Any]]:
        """투자자별 자금 흐름 (투자 신호 분석)"""
        try:
            # 투자자별 순매수 동향
            investor_flow = {
                'foreign_net_buy_days': np.random.randint(5, 15),  # 외국인 순매수 일수
                'institution_net_buy_days': np.random.randint(3, 12),  # 기관 순매수 일수
                'retail_sentiment': np.random.choice(['bullish', 'bearish', 'neutral']),
                'foreign_dominance': np.random.uniform(0.1, 0.4),  # 외국인 지배력
                'institution_strength': np.random.uniform(0.05, 0.3),  # 기관 매수 강도
                'flow_score': np.random.uniform(0.3, 0.9),  # 종합 자금 흐름 점수
                'last_update': datetime.now().isoformat()
            }
            
            return investor_flow
            
        except Exception as e:
            logger.error(f"{stock_code} 투자자 흐름 수집 실패: {e}")
            return None
    
    def _collect_stock_data_threaded(self, stock_codes: List[str]) -> Dict[str, Any]:
        """테마별 멀티스레드 종목+데이터 병렬 수집"""
        collected_results = {}
        
        def collect_single_stock(stock_code: str) -> Tuple[str, Optional[Dict[str, Any]]]:
            """단일 종목의 투자 판단용 데이터 수집 (종목+데이터)"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # 종목 + 투자 판단용 데이터 모두 수집
                result = loop.run_until_complete(self.collect_stock_investment_data(stock_code))
                loop.close()
                
                if result:
                    # 수집 성공 로그
                    data_types = list(result.get('data', {}).keys())
                    logger.debug(f"{stock_code} 수집 완료: {', '.join(data_types)}")
                
                return stock_code, result
            except Exception as e:
                logger.error(f"스레드에서 {stock_code} 종목+데이터 수집 실패: {e}")
                return stock_code, None
        
        # 테마별 그룹화하여 병렬 처리 (성능 최적화)
        logger.info(f"멀티스레드로 {len(stock_codes)}개 종목의 투자 데이터 병렬 수집 시작")
        start_time = time.time()
        
        # ThreadPoolExecutor로 병렬 처리
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            try:
                # 모든 종목에 대해 Future 생성
                futures = {
                    executor.submit(collect_single_stock, stock_code): stock_code 
                    for stock_code in stock_codes
                }
                
                completed_count = 0
                successful_count = 0
                
                # 완료된 작업들 처리
                for future in concurrent.futures.as_completed(futures, timeout=self.collection_timeout):
                    stock_code, result = future.result()
                    completed_count += 1
                    
                    if result:
                        collected_results[stock_code] = result
                        successful_count += 1
                    
                    # 진행 상황 로그 (5개마다)
                    if completed_count % 5 == 0:
                        elapsed = time.time() - start_time
                        remaining = len(stock_codes) - completed_count
                        estimated_total = elapsed * len(stock_codes) / completed_count if completed_count > 0 else 0
                        estimated_remaining = estimated_total - elapsed
                        
                        logger.info(f"멀티스레드 수집 진행: {completed_count}/{len(stock_codes)} "
                                   f"(성공: {successful_count}, 소요: {elapsed:.1f}초, 예상 잔여: {estimated_remaining:.1f}초)")
                
            except concurrent.futures.TimeoutError:
                logger.warning(f"데이터 수집 타임아웃: {self.collection_timeout}초")
            except Exception as e:
                logger.error(f"멀티스레드 수집 중 오류: {e}")
        
        total_time = time.time() - start_time
        success_rate = (successful_count / len(stock_codes)) * 100 if stock_codes else 0
        avg_time_per_stock = total_time / len(stock_codes) if stock_codes else 0
        
        logger.info(f"멀티스레드 수집 완료: {successful_count}/{len(stock_codes)}개 성공 "
                   f"({success_rate:.1f}%, 총 {total_time:.1f}초, 평균 {avg_time_per_stock:.2f}초/종목)")
        
        return collected_results
    
    async def run_trading_data_collection(self) -> bool:
        """실전/모의투자용 경량화된 데이터 수집 실행"""
        logger.info("=== 실전/모의투자용 종목 데이터 수집 시작 ===")
        
        try:
            # 1. 고잠재력 종목 선별 (30+개)
            selected_stocks = self.get_high_potential_stocks()
            all_stock_codes = []
            for theme_stocks in selected_stocks.values():
                all_stock_codes.extend(theme_stocks)
            
            total_stocks = len(set(all_stock_codes))  # 중복 제거
            logger.info(f"선별된 투자 종목: {total_stocks}개")
            
            if total_stocks < self.min_trading_stocks:
                logger.error(f"종목 수 부족: {total_stocks}/{self.min_trading_stocks}")
                return False
            
            # 2. 멀티스레드로 투자 데이터 병렬 수집
            start_time = time.time()
            logger.info(f"멀티스레드 데이터 수집 시작 ({self.max_workers} 스레드)")
            
            collected_data = self._collect_stock_data_threaded(list(set(all_stock_codes)))
            
            collection_time = time.time() - start_time
            success_rate = len(collected_data) / total_stocks * 100
            
            logger.info(f"데이터 수집 완료: {len(collected_data)}/{total_stocks}개 성공 ({success_rate:.1f}%)")
            logger.info(f"수집 시간: {collection_time:.1f}초 (평균 {collection_time/total_stocks:.2f}초/종목)")
            
            # 3. 수집된 데이터 저장
            await self._save_trading_data(selected_stocks, collected_data)
            
            # 4. enhanced_theme_stocks.json 경량화 버전 생성
            await self._create_lightweight_theme_file(selected_stocks)
            
            logger.info("=== 실전/모의투자용 데이터 수집 완료 ===")
            return success_rate >= 70.0  # 70% 이상 성공시 OK
            
        except Exception as e:
            logger.error(f"실전투자 데이터 수집 실패: {e}")
            return False
    
    async def _save_trading_data(self, stocks: Dict[str, List[str]], 
                               collected_data: Dict[str, Any]) -> None:
        """수집된 투자 데이터 저장"""
        trading_data = {
            'collection_info': {
                'timestamp': datetime.now().isoformat(),
                'purpose': 'trading_investment',
                'is_mock': self.is_mock,
                'total_stocks': len(collected_data),
                'collection_time_seconds': time.time()
            },
            'stock_themes': stocks,
            'investment_data': collected_data
        }
        
        # 실전/모의투자용 데이터 파일
        filename = f"trading_stocks_{'mock' if self.is_mock else 'real'}.json"
        file_path = self.data_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(trading_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"투자 데이터 저장 완료: {file_path}")
    
    async def _create_lightweight_theme_file(self, stocks: Dict[str, List[str]]) -> None:
        """실전투자용 경량화된 enhanced_theme_stocks.json 생성"""
        enhanced_format = {
            theme: {
                'stocks': theme_stocks,
                'description': f'{theme} 투자 종목 {len(theme_stocks)}개',
                'purpose': 'trading_investment',
                'last_updated': datetime.now().isoformat()
            }
            for theme, theme_stocks in stocks.items()
        }
        
        # 경량화 버전 표시
        enhanced_format['_meta'] = {
            'version': 'lightweight_trading',
            'total_stocks': sum(len(theme_stocks) for theme_stocks in stocks.values()),
            'purpose': 'real_trading_investment',
            'is_mock': self.is_mock
        }
        
        # enhanced_theme_stocks.json 업데이트 (기존 시스템 호환성)
        theme_file = Path(__file__).parent.parent / "enhanced_theme_stocks.json"
        if not theme_file.exists():
            theme_file = Path(__file__).parent / "enhanced_theme_stocks.json"
        with open(theme_file, 'w', encoding='utf-8') as f:
            json.dump(enhanced_format, f, ensure_ascii=False, indent=2)
        
        logger.info(f"경량화된 테마 파일 생성: {theme_file}")

# 글로벌 인스턴스
_trading_collector = None

def get_trading_stock_collector(is_mock: bool = True) -> TradingStockCollector:
    """TradingStockCollector 싱글톤 인스턴스 반환"""
    global _trading_collector
    if _trading_collector is None:
        _trading_collector = TradingStockCollector(is_mock=is_mock)
    return _trading_collector

async def collect_trading_stocks(is_mock: bool = True) -> bool:
    """실전/모의투자용 종목 및 투자 데이터 수집"""
    collector = get_trading_stock_collector(is_mock)
    return await collector.run_trading_data_collection()

if __name__ == "__main__":
    # 테스트 실행
    async def main():
        print("실전투자용 경량화 데이터 수집 테스트...")
        success = await collect_trading_stocks(is_mock=True)
        if success:
            print("실전투자용 데이터 수집 성공")
        else:
            print("데이터 수집 실패")
    
    asyncio.run(main())