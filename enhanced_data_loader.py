#!/usr/bin/env python3
"""
[opt] [algo] [ai] Enhanced Data Loader with Investor Trading & Minute Bar Support
확장된 데이터 로더 - 투자자별 매매동향 및 분봉 데이터 지원
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime, timedelta
import json

class EnhancedDataLoader:
    """확장된 데이터 로더 - 투자자 동향 및 분봉 데이터 통합"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "backtesting" / "data"
        self.logger = logging.getLogger(__name__)
        
        # 지원하는 데이터 타입
        self.supported_timeframes = ['5min', '10min', '30min', 'daily', 'weekly']
        self.enhanced_features = ['investor_trading', 'minute_bars']
        
    def load_enhanced_stock_data(self, stock_code: str, timeframe: str = 'daily') -> Dict[str, pd.DataFrame]:
        """종목의 모든 확장 데이터 로드"""
        result = {}
        
        try:
            # 1. 기본 OHLCV 데이터
            basic_data = self.load_basic_ohlcv(stock_code, timeframe)
            if basic_data is not None:
                result['ohlcv'] = basic_data
            
            # 2. 투자자별 매매동향 데이터
            investor_data = self.load_investor_trading_data(stock_code)
            if investor_data is not None:
                result['investor_trading'] = investor_data
            
            # 3. 5분봉 데이터 (가격 액션 분석용)
            minute_data = self.load_minute_bar_data(stock_code)
            if minute_data is not None:
                result['minute_bars'] = minute_data
            
            # 4. 데이터 통합 및 정렬
            if len(result) > 1:
                result = self._synchronize_data(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"{stock_code} 확장 데이터 로드 실패: {e}")
            return {}
    
    def load_basic_ohlcv(self, stock_code: str, timeframe: str) -> Optional[pd.DataFrame]:
        """기본 OHLCV 데이터 로드"""
        try:
            file_path = self.data_dir / timeframe / f"{stock_code}_{timeframe}.csv"
            
            if not file_path.exists():
                self.logger.warning(f"OHLCV 파일 없음: {file_path}")
                return None
            
            df = pd.read_csv(file_path)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            
            # 데이터 정렬
            df.sort_index(inplace=True)
            
            return df
            
        except Exception as e:
            self.logger.error(f"{stock_code} OHLCV 데이터 로드 실패: {e}")
            return None
    
    def load_investor_trading_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """투자자별 매매동향 데이터 로드"""
        try:
            file_path = self.data_dir / "investor_trading" / f"{stock_code}_investor.csv"
            
            if not file_path.exists():
                self.logger.warning(f"투자자 데이터 파일 없음: {file_path}")
                return None
            
            df = pd.read_csv(file_path)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            
            # 추가 계산 지표
            df['Total_Net'] = df['Institution_Net'] + df['Foreign_Net'] + df['Retail_Net'] + df['Program_Net']
            df['Foreign_Dominance'] = df['Foreign_Net'] / df['Total_Volume']
            df['Institution_Strength'] = df['Institution_Net'] / (df['Institution_Buy'] + df['Institution_Sell'])
            
            return df
            
        except Exception as e:
            self.logger.error(f"{stock_code} 투자자 데이터 로드 실패: {e}")
            return None
    
    def load_minute_bar_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """5분봉 데이터 로드"""
        try:
            file_path = self.data_dir / "minute_bars" / f"{stock_code}_5min.csv"
            
            if not file_path.exists():
                self.logger.warning(f"분봉 데이터 파일 없음: {file_path}")
                return None
            
            df = pd.read_csv(file_path)
            df['DateTime'] = pd.to_datetime(df['DateTime'])
            df.set_index('DateTime', inplace=True)
            
            # 추가 기술적 지표 계산
            df = self._calculate_minute_indicators(df)
            
            return df
            
        except Exception as e:
            self.logger.error(f"{stock_code} 분봉 데이터 로드 실패: {e}")
            return None
    
    def _calculate_minute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """분봉 데이터에 추가 지표 계산"""
        try:
            # 1. 가격 액션 지표
            df['Price_Range'] = (df['High'] - df['Low']) / df['Open'] * 100
            df['Body_Size'] = abs(df['Close'] - df['Open']) / df['Open'] * 100
            df['Upper_Shadow'] = (df['High'] - np.maximum(df['Open'], df['Close'])) / df['Open'] * 100
            df['Lower_Shadow'] = (np.minimum(df['Open'], df['Close']) - df['Low']) / df['Open'] * 100
            
            # 2. VWAP 편차
            df['VWAP_Deviation'] = (df['Close'] - df['VWAP']) / df['VWAP'] * 100
            
            # 3. 볼륨 지표
            df['Volume_MA_20'] = df['Volume'].rolling(window=20).mean()
            df['Volume_Ratio'] = df['Volume'] / df['Volume_MA_20']
            
            # 4. 모멘텀 지표
            df['Price_Change'] = df['Close'].pct_change() * 100
            df['Price_MA_5'] = df['Close'].rolling(window=5).mean()
            df['Price_Above_MA'] = (df['Close'] > df['Price_MA_5']).astype(int)
            
            return df
            
        except Exception as e:
            self.logger.error(f"분봉 지표 계산 실패: {e}")
            return df
    
    def _synchronize_data(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """데이터 프레임들의 날짜 동기화"""
        try:
            # 기본 OHLCV 데이터를 기준으로 설정
            base_data = None
            for key in ['ohlcv']:
                if key in data_dict and data_dict[key] is not None and len(data_dict[key]) > 0:
                    base_data = data_dict[key]
                    break
            
            if base_data is None:
                self.logger.warning("기준 데이터가 없어 동기화 건너뜀")
                return data_dict
            
            # 기준 데이터의 날짜 범위
            base_dates = base_data.index
            
            synchronized_data = {'ohlcv': base_data}  # 기준 데이터 유지
            
            # 다른 데이터들과 동기화
            for key, df in data_dict.items():
                if key == 'ohlcv' or df is None or len(df) == 0:
                    continue
                
                if key == 'minute_bars':
                    # 분봉 데이터는 그대로 유지 (별도 처리)
                    synchronized_data[key] = df
                else:
                    # 투자자 데이터 등은 날짜 기준으로 정렬/필터링
                    if hasattr(df.index, 'intersection'):
                        common_dates = base_dates.intersection(df.index)
                        if len(common_dates) > 0:
                            synchronized_data[key] = df[df.index.isin(common_dates)].sort_index()
                        else:
                            self.logger.warning(f"{key} 데이터에 공통 날짜가 없음")
                            synchronized_data[key] = df
                    else:
                        synchronized_data[key] = df
            
            return synchronized_data
            
        except Exception as e:
            self.logger.error(f"데이터 동기화 실패: {e}")
            return data_dict
    
    def load_multiple_stocks(self, stock_codes: List[str], timeframe: str = 'daily') -> Dict[str, Dict[str, pd.DataFrame]]:
        """여러 종목의 확장 데이터 일괄 로드"""
        result = {}
        
        for stock_code in stock_codes:
            data = self.load_enhanced_stock_data(stock_code, timeframe)
            if data:
                result[stock_code] = data
        
        self.logger.info(f"{len(result)}/{len(stock_codes)} 종목 확장 데이터 로드 완료")
        return result
    
    def get_data_summary(self) -> Dict[str, Any]:
        """데이터 디렉토리 요약 정보"""
        summary = {
            'basic_timeframes': {},
            'enhanced_features': {},
            'total_stocks': 0
        }
        
        try:
            # 기본 시간프레임별 종목 수
            for timeframe in self.supported_timeframes:
                timeframe_dir = self.data_dir / timeframe
                if timeframe_dir.exists():
                    files = list(timeframe_dir.glob("*.csv"))
                    summary['basic_timeframes'][timeframe] = len(files)
            
            # 확장 기능별 종목 수
            for feature in self.enhanced_features:
                feature_dir = self.data_dir / feature
                if feature_dir.exists():
                    files = list(feature_dir.glob("*.csv"))
                    summary['enhanced_features'][feature] = len(files)
            
            # 전체 종목 수 (daily 기준)
            daily_dir = self.data_dir / "daily"
            if daily_dir.exists():
                summary['total_stocks'] = len(list(daily_dir.glob("*.csv")))
            
            return summary
            
        except Exception as e:
            self.logger.error(f"데이터 요약 정보 생성 실패: {e}")
            return summary

    def create_enhanced_features(self, ohlcv_data: pd.DataFrame, 
                               investor_data: pd.DataFrame = None,
                               minute_data: pd.DataFrame = None) -> pd.DataFrame:
        """확장된 데이터를 활용한 새로운 피처 생성"""
        
        enhanced_df = ohlcv_data.copy()
        
        try:
            # 1. 투자자 동향 기반 피처
            if investor_data is not None:
                # 날짜 기준으로 병합
                enhanced_df = enhanced_df.join(investor_data, how='left')
                
                # 투자자 동향 지표
                enhanced_df['Foreign_Flow_Signal'] = np.where(
                    enhanced_df['Foreign_Net'] > enhanced_df['Foreign_Net'].rolling(5).mean(), 1, -1
                )
                enhanced_df['Institution_Flow_Signal'] = np.where(
                    enhanced_df['Institution_Net'] > enhanced_df['Institution_Net'].rolling(5).mean(), 1, -1
                )
                enhanced_df['Retail_Sentiment'] = np.where(
                    enhanced_df['Retail_Net'] > 0, 1, -1
                )
                
                # 복합 투자자 신호
                enhanced_df['Investor_Consensus'] = (
                    enhanced_df['Foreign_Flow_Signal'] + 
                    enhanced_df['Institution_Flow_Signal'] + 
                    enhanced_df['Retail_Sentiment']
                ) / 3
            
            # 2. 분봉 데이터 기반 피처 (일별 집계)
            if minute_data is not None:
                daily_minute_features = self._aggregate_minute_features(minute_data)
                enhanced_df = enhanced_df.join(daily_minute_features, how='left')
            
            # 3. 결측치 처리
            enhanced_df = enhanced_df.fillna(method='ffill').fillna(0)
            
            return enhanced_df
            
        except Exception as e:
            self.logger.error(f"확장 피처 생성 실패: {e}")
            return enhanced_df
    
    def _aggregate_minute_features(self, minute_data: pd.DataFrame) -> pd.DataFrame:
        """분봉 데이터를 일별로 집계하여 피처 생성"""
        try:
            # 날짜별 그룹화
            daily_groups = minute_data.groupby(minute_data.index.date)
            
            daily_features = []
            
            for date, group in daily_groups:
                features = {
                    'Date': pd.to_datetime(date),
                    'Intraday_Volatility': group['Price_Change'].std(),
                    'Max_Volume_Spike': group['Volume_Ratio'].max(),
                    'VWAP_Deviation_Range': group['VWAP_Deviation'].max() - group['VWAP_Deviation'].min(),
                    'Price_Range_Avg': group['Price_Range'].mean(),
                    'Volume_Concentration': group['Volume'].std() / group['Volume'].mean() if group['Volume'].mean() > 0 else 0
                }
                daily_features.append(features)
            
            daily_df = pd.DataFrame(daily_features)
            daily_df.set_index('Date', inplace=True)
            
            return daily_df
            
        except Exception as e:
            self.logger.error(f"분봉 데이터 일별 집계 실패: {e}")
            return pd.DataFrame()
"""
사용 예시:

# 확장 데이터 로더 초기화
loader = EnhancedDataLoader()

# 단일 종목 확장 데이터 로드
test_data = loader.load_enhanced_stock_data('TEST001', 'daily')
# 결과: {'ohlcv': DataFrame, 'investor_trading': DataFrame, 'minute_bars': DataFrame}

# 확장 피처가 포함된 데이터 생성
enhanced_features = loader.create_enhanced_features(
    test_data['ohlcv'], 
    test_data.get('investor_trading'),
    test_data.get('minute_bars')
)

# 여러 종목 일괄 로드
stocks = ['TEST001', 'TEST002', 'TEST003']
multi_data = loader.load_multiple_stocks(stocks, 'daily')
"""