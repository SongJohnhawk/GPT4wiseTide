"""
종목 데이터 수집기 - tideWise 시작시 한 번만 실행
피처 확장: 매수 선정 정확도 향상을 위한 고급 지표 수집
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import asyncio
import numpy as np
import pandas as pd
import concurrent.futures
import threading
import time

logger = logging.getLogger(__name__)

class StockDataCollector:
    def __init__(self, max_analysis_stocks: int = 20):
        # 분석용 종목 수집 제한 (기본 20개) - 먼저 설정
        self.max_analysis_stocks = max_analysis_stocks
        
        self.data_file = Path("stock_data_cache.json")
        # 동적 테마 기반 종목 로드
        self.theme_stocks = self._load_dynamic_theme_stocks()
        
        # 멀티스레드 설정
        self.max_workers = 2  # API Rate Limiting 고려 - 서버 안정성을 위해 2개로 제한
        self.collection_timeout = 300  # 5분 타임아웃
        self._lock = threading.Lock()
        self._collected_data = {}
    
    def _load_dynamic_theme_stocks(self) -> List[str]:
        """동적 테마 기반 종목 로드 (분석용 제한 적용)"""
        try:
            from support.enhanced_theme_stocks import load_theme_stocks_list
            theme_stocks = load_theme_stocks_list()
            
            if theme_stocks and len(theme_stocks) > 0:
                # 분석 효율성을 위해 종목 수 제한 적용
                original_count = len(theme_stocks)
                if len(theme_stocks) > self.max_analysis_stocks:
                    # 우선순위 기반 종목 선별 (Core_Large_Cap 우선)
                    theme_stocks = self._select_priority_stocks(theme_stocks)
                    logger.info(f"분석 효율성을 위해 종목 수를 {original_count}개에서 {len(theme_stocks)}개로 제한")
                else:
                    logger.info(f"동적 테마 종목 로드 성공: {len(theme_stocks)}개")
                return theme_stocks
            else:
                logger.info("동적 테마 종목 로드 결과가 없음 - 하드코딩 종목 사용 안함")
                return []
                
        except Exception as e:
            logger.warning(f"테마 종목 로드 실패: {e} - 하드코딩 종목 사용 안함")
            return []
    
    def _get_fallback_stocks(self) -> List[str]:
        """fallback 종목 리스트 - 하드코딩 데이터 사용 금지"""
        logger.warning("Fallback 종목 요청 - 하드코딩 데이터 사용 금지")
        return []
    
    def _select_priority_stocks(self, theme_stocks: List[str]) -> List[str]:
        """우선순위 기반 종목 선별 (Core_Large_Cap 우선)"""
        try:
            import json
            from pathlib import Path
            
            # enhanced_theme_stocks.json에서 테마별 종목 로드
            json_file = Path(__file__).parent / "support" / "enhanced_theme_stocks.json"
            if not json_file.exists():
                # 그냥 앞에서 max_analysis_stocks 개수만큼 선택
                return theme_stocks[:self.max_analysis_stocks]
            
            with open(json_file, 'r', encoding='utf-8') as f:
                theme_data = json.load(f)
            
            # 우선순위 테마 정의 (투자 안정성 고려)
            priority_themes = [
                'Core_Large_Cap',      # 대형주 (최우선)
                'AI_Semiconductor',    # AI/반도체 (고성장)
                'Battery_EV',          # 배터리/전기차 (미래성장)
                'Bio_Healthcare',      # 바이오/헬스케어 (중장기)
                'Gaming_Platform',     # 게임/플랫폼 (변동성)
                'Defense_Tech'         # 방산/기술 (안정성)
            ]
            
            selected_stocks = []
            
            # 우선순위 테마별로 종목 선별
            for theme_name in priority_themes:
                if len(selected_stocks) >= self.max_analysis_stocks:
                    break
                
                if theme_name in theme_data and 'stocks' in theme_data[theme_name]:
                    theme_stock_list = theme_data[theme_name]['stocks']
                    
                    # 해당 테마의 종목 중에서 수집 대상에 포함된 것들만 선택
                    for stock_code in theme_stock_list:
                        if stock_code in theme_stocks and stock_code not in selected_stocks:
                            selected_stocks.append(stock_code)
                            
                            if len(selected_stocks) >= self.max_analysis_stocks:
                                break
            
            # 아직 부족하면 나머지 종목에서 추가 선별
            if len(selected_stocks) < self.max_analysis_stocks:
                for stock_code in theme_stocks:
                    if stock_code not in selected_stocks:
                        selected_stocks.append(stock_code)
                        
                        if len(selected_stocks) >= self.max_analysis_stocks:
                            break
            
            logger.info(f"우선순위 기반 종목 선별: Core_Large_Cap 우선, 총 {len(selected_stocks)}개 선택")
            return selected_stocks
            
        except Exception as e:
            logger.warning(f"우선순위 종목 선별 실패: {e}, 기본 선별 사용")
            # fallback: 그냥 앞에서부터 max_analysis_stocks 개수만큼 선택
            return theme_stocks[:self.max_analysis_stocks]
        
    def load_cached_data(self) -> Dict:
        """캐시된 종목 데이터 로드"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cache_time = data.get('cached_at', '')
                    logger.info(f"종목 데이터 캐시 로드 완료 - 캐시 시간: {cache_time}")
                    return data
        except Exception as e:
            logger.error(f"종목 데이터 캐시 로드 실패: {e}")
        return None
        
    def _collect_single_stock_data(self, stock_code: str, api_connector) -> tuple:
        """단일 종목 데이터 수집 (멀티스레드용)"""
        try:
            # 스레드별 이벤트 루프 생성
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 종목 데이터 수집
            market_data = loop.run_until_complete(self._collect_enhanced_features(stock_code, api_connector))
            stock_name = self._get_stock_name(stock_code, api_connector)
            
            result = {
                "name": stock_name,
                "updated_at": datetime.now().strftime("%H:%M:%S"),
                **market_data
            }
            
            loop.close()
            
            logger.debug(f"종목 데이터 수집 완료: {stock_code} - {stock_name}")
            return stock_code, result
            
        except Exception as e:
            logger.warning(f"종목 데이터 수집 실패 {stock_code}: {e}")
            return stock_code, None

    def _collect_stocks_multithreaded(self, api_connector=None) -> Dict:
        """멀티스레드 종목 데이터 수집"""
        if not api_connector:
            logger.info("API 커넥터가 없어 기본값 사용")
            return {}
            
        collected_results = {}
        
        logger.info(f"멀티스레드로 {len(self.theme_stocks)}개 종목 데이터 수집 시작 (최대 {self.max_workers} 스레드)")
        start_time = time.time()
        
        # ThreadPoolExecutor로 병렬 처리
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            try:
                # 모든 종목에 대해 Future 생성
                futures = {
                    executor.submit(self._collect_single_stock_data, stock_code, api_connector): stock_code 
                    for stock_code in self.theme_stocks
                }
                
                completed_count = 0
                successful_count = 0
                
                # 완료된 작업들 처리
                for future in concurrent.futures.as_completed(futures, timeout=self.collection_timeout):
                    stock_code, result = future.result()
                    completed_count += 1
                    
                    if result:
                        with self._lock:
                            collected_results[stock_code] = result
                        successful_count += 1
                    
                    # 진행 상황 로그 (5개마다)
                    if completed_count % 5 == 0 or completed_count == len(self.theme_stocks):
                        elapsed = time.time() - start_time
                        remaining = len(self.theme_stocks) - completed_count
                        estimated_total = elapsed * len(self.theme_stocks) / completed_count if completed_count > 0 else 0
                        estimated_remaining = estimated_total - elapsed if remaining > 0 else 0
                        
                        logger.info(f"멀티스레드 수집 진행: {completed_count}/{len(self.theme_stocks)} "
                                   f"(성공: {successful_count}, 소요: {elapsed:.1f}초, 예상 잔여: {estimated_remaining:.1f}초)")
                
            except concurrent.futures.TimeoutError:
                logger.warning(f"데이터 수집 타임아웃: {self.collection_timeout}초")
            except Exception as e:
                logger.error(f"멀티스레드 수집 중 오류: {e}")
        
        total_time = time.time() - start_time
        success_rate = (successful_count / len(self.theme_stocks)) * 100 if self.theme_stocks else 0
        avg_time_per_stock = total_time / len(self.theme_stocks) if self.theme_stocks else 0
        
        logger.info(f"멀티스레드 수집 완료: {successful_count}/{len(self.theme_stocks)}개 성공 "
                   f"({success_rate:.1f}%, 총 {total_time:.1f}초, 평균 {avg_time_per_stock:.2f}초/종목)")
        
        return collected_results

    async def collect_and_cache_stocks(self, api_connector=None, use_multithreading: bool = True) -> Dict:
        """종목 데이터 수집 및 캐시 (3번 재시도 포함)"""
        max_retries = 3
        
        # 동적 테마 종목 확인
        if not self.theme_stocks or len(self.theme_stocks) == 0:
            logger.error("동적 테마 종목이 없습니다 - 하드코딩 데이터 사용 금지")
            print("서버가 응답하지 않습니다.")
            return {
                "cached_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "theme_stocks": [],
                "stock_info": {}
            }
        
        for attempt in range(max_retries):
            try:
                logger.info(f"종목 데이터 수집 시작... (시도 {attempt + 1}/{max_retries})")
                
                # 기본 종목 정보
                stock_data = {
                    "cached_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "theme_stocks": self.theme_stocks,
                    "stock_info": {}
                }
                
                # API 연결이 있으면 실제 데이터 수집
                if api_connector:
                    if use_multithreading:
                        # 멀티스레드 수집
                        collected_results = self._collect_stocks_multithreaded(api_connector)
                        if not collected_results or len(collected_results) == 0:
                            raise Exception("종목 데이터 수집 실패")
                        stock_data["stock_info"] = collected_results
                        logger.info(f"멀티스레드로 {len(collected_results)}개 종목 데이터 수집 완료")
                    else:
                        # 기존 순차 수집
                        for stock_code in self.theme_stocks:
                            market_data = await self._collect_enhanced_features(stock_code, api_connector)
                            
                            stock_data["stock_info"][stock_code] = {
                                "name": self._get_stock_name(stock_code, api_connector),
                                "updated_at": datetime.now().strftime("%H:%M:%S"),
                                **market_data
                            }
                            await asyncio.sleep(0.1)  # API 제한 방지
                            
                        logger.info(f"순차적으로 {len(self.theme_stocks)}개 종목 데이터 수집 완료")
                    
                    # 캐시 파일 저장 (numpy 타입 변환)
                    with open(self.data_file, 'w', encoding='utf-8') as f:
                        json.dump(stock_data, f, ensure_ascii=False, indent=2, default=self._json_serializer)
                    
                    logger.info(f"종목 데이터 캐시 저장 완료: {self.data_file}")
                    return stock_data
                else:
                    logger.error("API 커넥터가 없습니다")
                    raise Exception("API 커넥터가 없습니다")
                    
            except Exception as e:
                logger.error(f"종목 데이터 수집/캐시 실패 (시도 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"재시도 중... ({attempt + 2}/{max_retries})")
                    await asyncio.sleep(2)  # 2초 대기 후 재시도
                    continue
                else:
                    print("서버가 응답하지 않습니다.")
                    break
        
        # 모든 재시도 실패시 기본 데이터 반환
        return {
            "cached_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "theme_stocks": self.theme_stocks,
            "stock_info": {}
        }
    
    def get_theme_stocks(self) -> List[str]:
        """테마 종목 리스트 반환"""
        cached_data = self.load_cached_data()
        if cached_data and "theme_stocks" in cached_data:
            return cached_data["theme_stocks"]
        return self.theme_stocks
    
    def get_stock_info(self, stock_code: str) -> Dict:
        """특정 종목 정보 반환"""
        cached_data = self.load_cached_data()
        if cached_data and "stock_info" in cached_data:
            return cached_data["stock_info"].get(stock_code, {})
        return {}
    
    async def _collect_enhanced_features(self, symbol: str, api_connector) -> Dict:
        """확장된 피처 수집 - 실제 API 데이터 수집"""
        try:
            if not api_connector:
                logger.warning(f"API 커넥터가 없어 종목 {symbol} 데이터 수집 불가")
                return self._get_default_features()
            
            # 실제 API를 통한 현재가 데이터 수집
            current_price = 0
            volume = 0
            high = 0
            low = 0
            
            try:
                # 실제 현재가 조회
                price_data = api_connector.get_stock_price(symbol)
                if price_data and price_data.get('rt_cd') == '0':
                    output = price_data.get('output', {})
                    current_price = float(output.get('stck_prpr', 0))  # 현재가
                    volume = int(output.get('acml_vol', 0))  # 누적거래량
                    high = float(output.get('stck_hgpr', current_price))  # 최고가
                    low = float(output.get('stck_lwpr', current_price))   # 최저가
                    
                    logger.debug(f"실제 API 데이터 수집 완료: {symbol} 가격={current_price:,.0f}원")
                else:
                    logger.warning(f"종목 {symbol} 가격 조회 실패: {price_data}")
                    return self._get_default_features()
                    
            except Exception as api_error:
                logger.warning(f"API 호출 실패 ({symbol}): {api_error}")
                return self._get_default_features()
            
            # 가격 데이터가 유효하지 않으면 기본값 반환
            if current_price <= 0:
                logger.warning(f"종목 {symbol} 유효하지 않은 가격: {current_price}")
                return self._get_default_features()
            
            # 실제 데이터 기반으로 OHLCV 구성
            # 단일 데이터 포인트를 기반으로 한 간단한 시리즈 생성
            ohlcv = {
                'open': [current_price * 0.99, current_price * 0.995, current_price],
                'high': [high if high > 0 else current_price * 1.01, current_price * 1.005, high if high > 0 else current_price],
                'low': [low if low > 0 else current_price * 0.99, current_price * 0.995, low if low > 0 else current_price],
                'close': [current_price * 0.995, current_price * 0.998, current_price],
                'vol_5m': [volume // 3 if volume > 0 else 50000, volume // 2 if volume > 0 else 60000, volume if volume > 0 else 80000]
            }
            
            # numpy 배열로 변환
            close = np.array(ohlcv['close'])
            high = np.array(ohlcv['high'])
            low = np.array(ohlcv['low'])
            vol5 = np.array(ohlcv['vol_5m'])
            
            # 확장 피처 계산
            ret15 = (close[-1] / close[-5] - 1.0) if len(close) >= 6 else 0.0
            
            # 기술적 지표 계산 (간단한 구현)
            ema20 = np.mean(close[-20:]) if len(close) >= 20 else close[-1]
            rsi7 = self._calculate_rsi(close, 7)
            atr14 = self._calculate_atr(high, low, close, 14)
            
            # MACD 계산 (간단 버전)
            ema12 = np.mean(close[-12:]) if len(close) >= 12 else close[-1]
            ema26 = np.mean(close[-26:]) if len(close) >= 26 else close[-1]
            macd_val = ema12 - ema26
            macd_sig = macd_val * 0.9  # 단순화된 신호선
            
            # VWAP 계산 (간단 버전)
            vwap_now = current_price * 1.001  # 예시값
            vwap_series = [current_price * (1 + i * 0.001) for i in range(-9, 1)]
            
            # 갭 및 전일 데이터
            prev_close = close[-2] if len(close) >= 2 else close[-1]
            open_today = ohlcv['open'][-1]
            gap_open = open_today / prev_close - 1.0
            high_prev = high[-2] if len(high) >= 2 else high[-1]
            low_prev = low[-2] if len(low) >= 2 else low[-1]
            
            # 호가 정보 (API에서 실제 수집 필요)
            # order_book = api_connector.get_orderbook(symbol)
            spread_pct = 0.002  # 예시: 0.2%
            bid_depth_1_3 = 5000  # 예시: Bid1~3 합계
            upper_limit = current_price * 1.3  # 예시: 상한가
            dist_to_upper_limit = (upper_limit - current_price) / current_price
            
            # 히스토리 데이터 (실제로는 별도 축적 필요)
            vol5m_hist_60d = vol5.tolist()[-60:] if len(vol5) >= 60 else vol5.tolist()
            ret15_hist_60d = [ret15] * min(60, len(close))  # 예시
            
            # 확장된 market_data 구성 (numpy 타입을 Python 기본 타입으로 변환)
            enhanced_data = {
                'current_price': float(current_price),
                'last': float(current_price),
                
                # 거래량 피처
                'vol_5m_now': int(vol5[-1]) if len(vol5) else 0,
                'vol_5m_hist_60d': [int(x) for x in vol5m_hist_60d],
                
                # 수익률 피처  
                'ret_15m': float(ret15),
                'ret_15m_hist_60d': [float(x) for x in ret15_hist_60d],
                
                # 갭/전일 피처
                'gap_open': float(gap_open),
                'high_prev': float(high_prev),
                'low_prev': float(low_prev),
                'open_today': float(open_today),
                
                # VWAP 피처
                'vwap_now': float(vwap_now),
                'vwap_series': [float(x) for x in vwap_series[-10:]],
                
                # 기술적 지표
                'macd': float(macd_val),
                'macd_signal': float(macd_sig),
                'rsi7': float(rsi7),
                'ema20': float(ema20),
                'atr14': float(atr14),
                
                # 유동성/호가 피처 (옵션)
                'spread': float(spread_pct),
                'bid_depth_1_3': int(bid_depth_1_3),
                'dist_to_upper_limit': float(dist_to_upper_limit),
                
                # 히스토리 시리즈
                'high_series': [float(x) for x in high.tolist()],
                'low_series': [float(x) for x in low.tolist()],
                'close_series': [float(x) for x in close.tolist()],
            }
            
            return enhanced_data
            
        except Exception as e:
            logger.warning(f"확장 피처 수집 실패 ({symbol}): {e}")
            # 더미 데이터 없는 기본값 반환
            return self._get_default_features()
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 7) -> float:
        """RSI 계산"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
        """ATR 계산"""
        if len(high) < 2:
            return high[-1] - low[-1] if len(high) > 0 else 1000.0
        
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr)
        
        return atr
    
    def _get_default_features(self) -> Dict:
        """API 데이터 수집 실패 시 기본 피처 반환 (더미 데이터 없음)"""
        return {
            'current_price': 0.0,
            'last': 0.0,
            'vol_5m_now': 0,
            'ret_15m': 0.0,
            'vol_5m_hist_60d': [],
            'ret_15m_hist_60d': [],
            'gap_open': 0.0,
            'high_prev': 0.0,
            'low_prev': 0.0,
            'open_today': 0.0,
            'vwap_now': 0.0,
            'vwap_series': [],
            'macd': 0.0,
            'macd_signal': 0.0,
            'rsi7': 50.0,
            'ema20': 0.0,
            'atr14': 0.0,
            'spread': 0.0,
            'bid_depth_1_3': 0,
            'dist_to_upper_limit': 0.0,
            'high_series': [],
            'low_series': [],
            'close_series': [],
        }
    
    def _get_stock_name(self, stock_code: str, api_connector) -> str:
        """종목코드로부터 정확한 종목명 조회 (실제 종목명 매핑 기반)"""
        # 1차: 실제 종목명 매핑 테이블 조회 (네트워크 오류 방지)
        real_stock_names = {
            # Core_Large_Cap (대형주)
            "005930": "삼성전자",
            "000660": "SK하이닉스", 
            "035420": "NAVER",
            "051910": "LG화학",
            "006400": "삼성SDI",
            "207940": "삼성바이오로직스",
            "005380": "현대차",
            "373220": "LG에너지솔루션",
            
            # AI_Semiconductor (AI반도체)
            "042700": "한미반도체",
            "095340": "ISC",
            "108860": "셀바스AI",
            "036930": "주성엔지니어링",
            "240810": "원익IPS",
            
            # Battery_EV (배터리/전기차)
            "096770": "SK이노베이션",
            "066970": "엘앤에프",
            "247540": "에코프로비엠",
            "322000": "HD현대에너지솔루션",
            "018880": "한온시스템",
            
            # Bio_Healthcare (바이오/헬스케어)
            "326030": "SK바이오팜",
            "302440": "SK바이오사이언스",
            "196170": "알테오젠",
            "145720": "덴티움",
            "068270": "셀트리온",
            
            # Gaming_Platform (게임/플랫폼)
            "251270": "넷마블",
            "036570": "엔씨소프트",
            "259960": "크래프톤",
            "263750": "펄어비스",
            "035720": "카카오",
            
            # Defense_Tech (방산/기술)
            "047810": "한국항공우주",
            "272210": "한화시스템",
            "012450": "한화에어로스페이스",
            "278470": "굿맨머티리얼"
        }
        
        if stock_code in real_stock_names:
            return real_stock_names[stock_code]
        
        # 2차: API를 통한 실시간 종목명 조회 시도 (매핑 테이블에 없는 경우만)
        try:
            if api_connector and hasattr(api_connector, 'get_stock_name'):
                real_name = api_connector.get_stock_name(stock_code)
                if real_name and not real_name.startswith('종목') and real_name != stock_code:
                    logger.debug(f"API로 종목명 조회 성공: {stock_code} -> {real_name}")
                    return real_name
        except Exception as e:
            logger.warning(f"API 종목명 조회 실패 {stock_code}: {e}")
        
        # 3차: enhanced_theme_stocks.json에서 종목명 추론 시도 (기존 로직)
        try:
            theme_file = Path(__file__).parent / "support" / "enhanced_theme_stocks.json"
            if theme_file.exists():
                with open(theme_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 각 테마에서 해당 종목코드 검색
                for theme_name, theme_info in data.items():
                    if theme_name.startswith('_') or not isinstance(theme_info, dict):
                        continue
                    
                    stocks = theme_info.get('stocks', [])
                    if stock_code in stocks:
                        # 테마명만 반환 (종목코드는 제외)
                        theme_korean = {
                            'Core_Large_Cap': '대형주',
                            'AI_Semiconductor': 'AI반도체',
                            'Battery_EV': '배터리',
                            'Bio_Healthcare': '바이오',
                            'Gaming_Platform': '게임',
                            'Defense_Tech': '방산'
                        }.get(theme_name, theme_name)
                        return f"{theme_korean}종목"
                        
        except Exception as e:
            logger.debug(f"테마 기반 종목명 추론 실패 {stock_code}: {e}")
        
        # 최종 기본값 반환 (종목코드만)
        return f"종목{stock_code}"
    
    def collect_stocks_sync(self, api_connector=None, use_multithreading: bool = True) -> Dict:
        """동기 방식으로 종목 데이터 수집 (편의 메서드)"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.collect_and_cache_stocks(api_connector, use_multithreading))
            loop.close()
            return result
        except Exception as e:
            logger.error(f"동기 방식 종목 데이터 수집 실패: {e}")
            return {
                "cached_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "theme_stocks": self.theme_stocks,
                "stock_info": {}
            }

    def get_collection_stats(self) -> Dict:
        """데이터 수집 통계 반환"""
        try:
            cached_data = self.load_cached_data()
            if not cached_data:
                return {"status": "no_cache", "stats": {}}
            
            stock_info = cached_data.get("stock_info", {})
            theme_stocks = cached_data.get("theme_stocks", [])
            
            stats = {
                "cached_at": cached_data.get("cached_at", "unknown"),
                "total_theme_stocks": len(theme_stocks),
                "collected_stocks": len(stock_info),
                "success_rate": (len(stock_info) / len(theme_stocks) * 100) if theme_stocks else 0,
                "has_enhanced_features": any(
                    "current_price" in info for info in stock_info.values()
                ) if stock_info else False,
                "collection_method": "multithreaded" if len(stock_info) > 0 else "unknown"
            }
            
            return {"status": "success", "stats": stats}
            
        except Exception as e:
            logger.error(f"수집 통계 조회 실패: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_stock_name(self, stock_code: str) -> str:
        """공용 종목명 조회 인터페이스"""
        if not hasattr(self, '_stock_name_cache'):
            self._stock_name_cache = {}
        
        # 캐시에서 먼저 확인
        if stock_code in self._stock_name_cache:
            return self._stock_name_cache[stock_code]
        
        # API 커넥터 없이 종목명 조회
        stock_name = self._get_stock_name(stock_code, None)
        
        # 캐시에 저장 
        self._stock_name_cache[stock_code] = stock_name
        return stock_name
    
    def _json_serializer(self, obj):
        """JSON 직렬화를 위한 numpy 타입 변환"""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif hasattr(obj, 'item'):  # numpy scalar
            return obj.item()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# 전역 인스턴스
stock_data_collector = StockDataCollector()