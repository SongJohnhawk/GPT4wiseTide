"""
심플 자동매매 엔진
- 알고리즘 객체를 받아서 실행
- 테마 종목 자동 선정
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timedelta, time as datetime_time
from pathlib import Path
from typing import Dict, List, Optional, Any

sys.path.append(str(Path(__file__).parent.parent))

from support.api_connector import KISAPIConnector
# 테마 종목 관련 import
from support.enhanced_theme_stocks import load_theme_stocks
from support.system_logger import SystemLogger
from support.telegram_notifier import get_telegram_notifier
from support.trading_rules import get_trading_rules
from support.advanced_sell_rules import AdvancedSellRules
# 사용자 정의 종목 참조 제거 - 별도 관리
from support.file_stop_handler import get_file_stop_handler
from support.dynamic_interval_controller import tideWiseDynamicIntervalController as DynamicIntervalController
from support.display_manager import get_display_manager
from support.clean_logger import setup_clean_logging
from support.step_display_utils import print_step_start, print_step_end, step_delay, print_algorithm_start, print_algorithm_end
from support.previous_day_balance_handler import PreviousDayBalanceHandler, TradingStrategy

# 토큰 최적화 시스템
from token_optimizer import optimize_if_needed

logger = logging.getLogger(__name__)


class SimpleAutoTrader:
    """심플 자동매매 엔진"""
    
    def __init__(self, account_type: str = "MOCK", algorithm=None, skip_market_hours: bool = True):
        """
        Args:
            account_type: "REAL" or "MOCK"
            algorithm: 알고리즘 객체 (analyze 메소드 필수)
            skip_market_hours: 장 시간 체크 건너뛰기 (기본값 True로 변경 - 항상 실행)
        """
        # 로깅 설정 간소화
        setup_clean_logging()
        
        # 디스플레이 매니저 초기화
        self.display = get_display_manager()
        
        # 기본 설정 저장
        self.account_type = account_type
        self.algorithm = algorithm
        self.skip_market_hours = True  # 항상 True로 설정 - 무한 순환
        
        # 상태 변수 먼저 초기화
        self.is_running = False
        self.last_scan_time = None
        self.stop_requested = False
        self.api_initialized = False
        
        # 매매 규칙 초기화 (API 불필요)
        self.trading_rules = get_trading_rules()
        
        # 파일 기반 중단 핸들러 초기화 (API 불필요)
        self.keyboard_handler = get_file_stop_handler()
        self.keyboard_handler.set_stop_callback(self.request_stop)  # 안전한 중단 (Main 복귀)
        self.keyboard_handler.set_force_exit_callback(self.request_force_exit)  # 강제 종료
        
        # 항상 모든 컴포넌트 초기화 (시장 시간 체크는 run() 메소드에서 수행)
        self._initialize_components()
    
    def _initialize_components(self):
        """API 및 모든 컴포넌트 초기화 (장시간 내 또는 테스트 모드)"""
        logger.info("Initializing API and trading components...")
        
        # API 초기화 (최소한만)
        self.api = KISAPIConnector(is_mock=(self.account_type == "MOCK"))
        
        # 텔레그램 초기화
        try:
            from support.telegram_notifier import get_telegram_notifier
            self.telegram = get_telegram_notifier()
            logger.info("텔레그램 알림 시스템 초기화 완료")
        except Exception as e:
            logger.warning(f"텔레그램 초기화 실패: {e}")
            # 텔레그램 실패시 더미 객체 생성
            class DummyTelegram:
                async def send_message(self, message):
                    logger.info(f"[텔레그램 대체] {message}")
                    return True
            self.telegram = DummyTelegram()
        
        # 동적 간격 컨트롤러 초기화 (v25.0 patch: ensure controller is instantiated)
        from support.dynamic_interval_controller import tideWiseDynamicIntervalController as DynamicIntervalController
        self.interval_controller = DynamicIntervalController()
        
        # 실패한 종목 추적 (임시 제외용)
        self.failed_stocks = set()  # 가격 조회나 차트 분석이 실패한 종목들
        self.failed_stocks_reset_time = None  # 다음 실패 종목 리셋 시간
        
        # 포지션 관리
        self.positions: Dict[str, Dict] = {}
        
        # 종목 관리
        self.theme_stocks = []
        # 모니터링 종목
        self.monitoring_stocks = []
        
        self.api_initialized = True
        logger.info("Component initialization completed")
    
    def request_stop(self):
        """ESC 키에 의한 안전한 중단 요청 (Main 복귀)"""
        self.stop_requested = True
        self.is_running = False
        logger.info("사용자 요청에 의한 자동매매 안전 중단 - Main 복귀")
    
    def request_force_exit(self):
        """ESC 키에 의한 안전한 종료 (Main 복귀)"""
        self.stop_requested = True
        self.is_running = False
        logger.info("사용자 요청에 의한 안전한 자동매매 종료 - Main으로 복귀")
    
    def _safe_float(self, value, default: float = 0.0) -> float:
        """안전한 float 변환"""
        try:
            if value is None or value == '' or value == '-':
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def _safe_int(self, value, default: int = 0) -> int:
        """안전한 int 변환"""
        try:
            if value is None or value == '' or value == '-':
                return default
            return int(float(value))  # float으로 먼저 변환 후 int
        except (ValueError, TypeError):
            return default
    
    def add_failed_stock(self, symbol: str, reason: str = ""):
        """실패한 종목을 임시 제외 목록에 추가"""
        self.failed_stocks.add(symbol)
        from datetime import datetime, timedelta
        if self.failed_stocks_reset_time is None:
            self.failed_stocks_reset_time = datetime.now() + timedelta(minutes=30)  # 30분 후 리셋
        logger.info(f"종목 임시 제외: {symbol} - {reason}")
    
    def is_stock_failed(self, symbol: str) -> bool:
        """종목이 실패 목록에 있는지 확인"""
        from datetime import datetime
        
        # 30분마다 실패 목록 리셋
        if (self.failed_stocks_reset_time and 
            datetime.now() >= self.failed_stocks_reset_time):
            old_count = len(self.failed_stocks)
            self.failed_stocks.clear()
            self.failed_stocks_reset_time = None
            if old_count > 0:
                logger.info(f"실패 종목 목록 리셋: {old_count}개 종목 재활성화")
        
        return symbol in self.failed_stocks
    
    def calculate_optimal_buy_quantity(self, current_price: float, target_quantity: int, available_cash: int) -> int:
        """최적 매수 수량 계산 (예수금 7% 제한 및 가격별 규칙 적용)"""
        # 수수료 및 마진 고려 (약 0.2% 추가)
        margin_rate = 1.002
        
        # 예수금 7% 제한 적용
        max_budget_per_stock = int(available_cash * 0.07)
        max_quantity_by_budget = int(max_budget_per_stock / (current_price * margin_rate))
        
        # 가격별 규칙 적용
        if current_price <= 30000:  # 3만원 이하
            # 최소 10주 매수 규칙
            min_quantity = 10
            if max_quantity_by_budget < min_quantity:
                # 예수금이 부족하면 최소 수량도 매수 불가능한지 확인
                min_required_amount = int(current_price * min_quantity * margin_rate)
                if available_cash >= min_required_amount:
                    # 예수금 7% 제한을 무시하고 최소 10주 매수
                    final_quantity = min(target_quantity, min_quantity)
                    logger.info(f"3만원 이하 종목 최소 10주 규칙 적용: {current_price:,}원 -> {final_quantity}주")
                else:
                    return 0
            else:
                final_quantity = min(target_quantity, max_quantity_by_budget)
        elif current_price >= 200000:  # 20만원 이상
            # 최대 5주로 제한
            max_quantity_by_price = 5
            final_quantity = min(target_quantity, max_quantity_by_budget, max_quantity_by_price)
            logger.info(f"20만원 이상 종목 5주 제한 적용: {current_price:,}원 -> {final_quantity}주")
        elif available_cash < 10000000 and current_price >= 300000:  # 예수금 1천만원 미만 + 30만원 이상
            # 최대 2주로 제한
            max_quantity_by_price = 2
            final_quantity = min(target_quantity, max_quantity_by_budget, max_quantity_by_price)
            logger.info(f"예수금 1천만원 미만 & 30만원 이상 종목 2주 제한: {current_price:,}원 -> {final_quantity}주")
        else:
            # 일반적인 경우 (예수금 7% 제한만 적용)
            final_quantity = min(target_quantity, max_quantity_by_budget)
        
        logger.debug(f"매수 수량 계산: 가격={current_price:,}원, 목표={target_quantity}주, "
                    f"예수금 7%={max_budget_per_stock:,}원, 최종={final_quantity}주")
        
        return max(0, final_quantity)
        
    async def load_theme_stocks_with_notification(self) -> List[str]:
        """테마별 종목 데이터 수집 (텔레그램 알림 포함)"""
        try:
            logger.info("테마별 종목 데이터 수집 시작")
            
            # 텔레그램 알림 - 데이터 수집 시작
            if self.telegram:
                await self.telegram.send_message(
                    f"<b>종목 데이터 수집 시작</b>\n\n"
                    f"<b>수집 시간:</b> {datetime.now().strftime('%H:%M:%S')}\n"
                    f"<b>수집 방식:</b> 테마별 균등 분배\n"
                    f"<b>목표 종목:</b> 100개 이상\n\n"
                    f"5년치 기술적 분석 데이터를 수집하고 있습니다..."
                )
            
            # enhanced_theme_stocks 모듈의 최적화된 함수 사용
            from support.enhanced_theme_stocks import load_theme_stocks_list
            collected_stocks = load_theme_stocks_list()
            
            if collected_stocks and len(collected_stocks) > 0:
                logger.info(f"테마별 종목 데이터 수집 완료: {len(collected_stocks)}개")
                
                # 테마별 분포 분석
                theme_distribution = self._analyze_theme_distribution(collected_stocks)
                
                # 텔레그램 알림 - 데이터 수집 완료
                if self.telegram:
                    distribution_text = []
                    for theme, count in theme_distribution.items():
                        distribution_text.append(f"• {theme}: {count}개")
                    
                    await self.telegram.send_message(
                        f"✅ <b>종목 데이터 수집 완료</b>\n\n"
                        f"<b>수집 종목 수:</b> {len(collected_stocks)}개\n"
                        f"<b>데이터 기간:</b> 5년치\n"
                        f"<b>분석 준비:</b> 완료\n\n"
                        f"<b>테마별 분포:</b>\n" + "\n".join(distribution_text[:8]) + 
                        (f"\n• 기타 테마 {len(distribution_text)-8}개..." if len(distribution_text) > 8 else "")
                    )
                
                return collected_stocks
            else:
                raise Exception("수집된 종목이 없음")
            
        except Exception as e:
            logger.error(f"테마 종목 로드 실패: {e}")
            
            # 텔레그램 알림 - 데이터 수집 실패
            if self.telegram:
                await self.telegram.send_message(
                    f"<b>종목 데이터 수집 실패</b>\n\n"
                    f"<b>오류 내용:</b> {str(e)}\n"
                    f"<b>대체 방안:</b> 기본 종목 리스트 사용\n\n"
                    f"기본 10개 종목으로 거래를 시작합니다."
                )
            
            # 기본 종목 동적 로드 시도
            try:
                from support.enhanced_theme_stocks import get_default_stocks
                return get_default_stocks()
            except Exception:
                # 최종 fallback - 빈 리스트
                return []
    
    def _analyze_theme_distribution(self, stocks: List[str]) -> Dict[str, int]:
        """테마별 종목 분포 분석"""
        try:
            # 간단한 테마 분류 (종목 코드 기준)
            themes = {
                "대형주": 0,  # 005000번대
                "IT/반도체": 0,  # 000000번대
                "바이오": 0,  # 200000번대 이상
                "중형주": 0,  # 030000~100000번대
                "기타": 0
            }
            
            for stock in stocks:
                code = int(stock) if stock.isdigit() else 0
                if code >= 200000:
                    themes["바이오"] += 1
                elif code >= 100000:
                    themes["중형주"] += 1  
                elif code >= 30000:
                    themes["중형주"] += 1
                elif code >= 5000:
                    themes["대형주"] += 1
                elif code >= 1:
                    themes["IT/반도체"] += 1
                else:
                    themes["기타"] += 1
                    
            return themes
        except:
            return {"전체": len(stocks)}
    
    def load_theme_stocks(self) -> List[str]:
        """기존 호환성을 위한 동기 버전"""
        try:
            from support.enhanced_theme_stocks import load_theme_stocks_list
            return load_theme_stocks_list()
        except Exception as e:
            logger.error(f"테마 종목 로드 실패: {e}")
            # 기본 종목 동적 로드 시도
            try:
                from support.enhanced_theme_stocks import get_default_stocks
                return get_default_stocks()
            except Exception:
                # 최종 fallback - 빈 리스트
                return []
    
    
    async def get_stock_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """주식 데이터 조회 (타임아웃 및 비동기 처리 포함)"""
        try:
            # API 연결 상태 확인
            if not hasattr(self.api, 'get_access_token') or not self.api.get_access_token():
                logger.warning(f"API 토큰이 유효하지 않음: {symbol}")
                return None
            
            # 현재가 조회 - 타임아웃과 비동기 처리 추가
            price_data = None
            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # Rate Limit 준수를 위한 최소 대기
                    await asyncio.sleep(0.3)
                    
                    # API 호출을 별도 스레드에서 실행하여 블로킹 방지
                    future = executor.submit(self.api.get_stock_price, symbol)
                    price_data = await asyncio.wait_for(
                        asyncio.wrap_future(future), 
                        timeout=8.0  # 8초 타임아웃
                    )
                logger.debug(f"[{symbol}] 주식 가격 조회 성공")
            except asyncio.TimeoutError:
                logger.warning(f"[{symbol}] 가격 조회 API 타임아웃 (8초)")
                return None
            except Exception as api_error:
                logger.warning(f"[{symbol}] 가격 조회 API 오류: {api_error}")
                return None
                
            if not price_data:
                logger.warning(f"주식 데이터 조회 실패 - API 응답 없음: {symbol}")
                return None
            
            # API 응답 상세 로깅 (디버그용)
            logger.debug(f"API 응답 구조: {symbol} - keys: {list(price_data.keys()) if isinstance(price_data, dict) else 'not dict'}")
            
            # API 응답 오류 체크
            if isinstance(price_data, dict):
                rt_cd = price_data.get('rt_cd')
                if rt_cd and rt_cd != '0':
                    msg = price_data.get('msg1', 'Unknown error')
                    logger.warning(f"API 오류: {symbol}, 가격 조회 실패")
                    return None
            
            # 가격 데이터 안전하게 추출 (API 응답 구조 확인)
            try:
                if 'output' in price_data:
                    # 정상적인 KIS API 응답 구조
                    output_data = price_data['output']
                    current_price = self._safe_float(output_data.get('stck_prpr', 0))
                else:
                    # 직접 데이터 구조인 경우
                    current_price = self._safe_float(price_data.get('stck_prpr', 0))
                    
                if current_price <= 0:
                    logger.warning(f"유효하지 않은 가격 데이터: {symbol}, 가격: {current_price}")
                    # 실패한 종목으로 등록 (30분간 재시도 방지)
                    self.add_failed_stock(symbol, "유효하지 않은 가격")
                    return None
                    
            except (ValueError, TypeError) as e:
                logger.warning(f"가격 데이터 형식 오류: {symbol}, 오류: {e}, 데이터: {price_data}")
                return None
            
            # 일봉 데이터 조회 (간단한 가격 히스토리) - 타임아웃 추가
            prices = []
            try:
                # 일봉 데이터도 비동기 처리로 타임아웃 적용
                daily_data = None
                try:
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(self.api.get_daily_chart, symbol, 30)
                        daily_data = await asyncio.wait_for(
                            asyncio.wrap_future(future), 
                            timeout=6.0  # 6초 타임아웃
                        )
                except asyncio.TimeoutError:
                    logger.debug(f"[{symbol}] 일봉 데이터 조회 타임아웃 - 기본값 사용")
                    daily_data = None
                except Exception as e:
                    logger.debug(f"[{symbol}] 일봉 데이터 조회 오류: {e}")
                    daily_data = None
                if daily_data and isinstance(daily_data, list):
                    for day in daily_data:
                        try:
                            close_price = self._safe_float(day.get('stck_clpr', 0))
                            if close_price > 0:
                                prices.append(close_price)
                        except (ValueError, TypeError):
                            continue
                elif daily_data and isinstance(daily_data, dict) and 'output2' in daily_data:
                    # API 응답이 딕셔너리 형태인 경우
                    for day in daily_data['output2']:
                        try:
                            close_price = self._safe_float(day.get('stck_clpr', 0))
                            if close_price > 0:
                                prices.append(close_price)
                        except (ValueError, TypeError):
                            continue
            except Exception as e:
                logger.debug(f"일봉 데이터 조회 실패: {symbol}, 오류: {e}")
                # 일봉 데이터가 없어도 현재가로 기본 데이터 생성
                prices = [current_price]
            
            # 기본값이 없으면 현재가 사용
            if not prices:
                prices = [current_price]
            
            # Pine Script 알고리즘에 필요한 데이터 포함 (API 응답 구조 안전 처리)
            try:
                # API 응답 구조에 따른 데이터 추출
                if 'output' in price_data:
                    data_source = price_data['output']
                else:
                    data_source = price_data
                
                # KMomentumCut 알고리즘 호환 데이터 구조
                stock_data = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'close': current_price,  # KMomentumCut이 사용
                    'high': self._safe_float(data_source.get('stck_hgpr'), current_price),
                    'low': self._safe_float(data_source.get('stck_lwpr'), current_price),
                    'open': self._safe_float(data_source.get('stck_oprc'), current_price),
                    'volume': self._safe_int(data_source.get('acml_vol'), 0),
                    'change_rate': self._safe_float(data_source.get('prdy_ctrt'), 0),
                    'prices': prices,  # 일봉 히스토리
                    'timestamp': datetime.now(),
                    # KMomentumCut 추가 필요 데이터
                    'index': 0,  # 바 인덱스
                    'datetime': datetime.now(),  # 현재 시간
                    'prev_close': current_price * (1 - self._safe_float(data_source.get('prdy_ctrt'), 0) / 100) if self._safe_float(data_source.get('prdy_ctrt'), 0) != 0 else current_price,
                    'Market': 'KOSPI'  # 기본값
                }
            except Exception as e:
                logger.error(f"주식 데이터 구성 실패: {symbol}, 오류: {e}")
                return None
            
            return stock_data
            
        except Exception as e:
            logger.error(f"주식 데이터 조회 실패 ({symbol}): {e}")
            return None
    
    async def execute_trade(self, symbol: str, action: str, quantity: int):
        """매매 실행"""
        try:
            stock_name = self.api.get_stock_name(symbol) or symbol
            
            if action == 'BUY':
                # 현재가 조회 (매수 주문 전)
                current_price = await self.get_current_price(symbol)
                if not current_price:
                    logger.warning(f"현재가 조회 실패로 매수 중단: {symbol}")
                    return
                
                # 매수 주문
                result = self.api.buy_order(
                    stock_code=symbol,
                    quantity=quantity,
                    price=0,  # 시장가
                    order_type="MARKET"
                )
                
                if result and result.get('rt_cd') == '0':
                    logger.info(f"매수 주문 성공: {stock_name} {quantity}주")
                    print(f"[매수] {stock_name} {quantity}주 @ {current_price:,}원")
                    
                    # 동적 간격 제어기에 매매 기록
                    from support.dynamic_interval_controller import TradeResult
                    self.interval_controller.record_trade(
                        action='buy',
                        symbol=symbol,
                        stock_name=stock_name,
                        price=current_price,
                        quantity=quantity,
                        result=TradeResult.PENDING  # 매수는 일단 PENDING으로
                    )
                    
                    # 매수 후 계좌 정보 조회
                    balance_info = self.api.get_account_balance(force_refresh=True)
                    
                    # 텔레그램 알림 (잔고 정보 포함)
                    await self.telegram.send_order_result(
                        symbol, "매수", quantity, current_price, "성공",
                        balance_info=balance_info, api_connector=self.api
                    )
                    
                    # 포지션 기록 (None 값 방지)
                    stop_loss_price = None
                    take_profit_price = None
                    
                    # 알고리즘에서 손절/익절 가격 계산
                    if self.algorithm and hasattr(self.algorithm, 'get_stop_loss'):
                        try:
                            stop_loss_price = self.algorithm.get_stop_loss(current_price, 'LONG')
                        except Exception as e:
                            logger.debug(f"알고리즘 stop_loss 계산 실패: {e}")
                    
                    if self.algorithm and hasattr(self.algorithm, 'get_take_profit'):
                        try:
                            take_profit_price = self.algorithm.get_take_profit(current_price, 'LONG')
                        except Exception as e:
                            logger.debug(f"알고리즘 take_profit 계산 실패: {e}")
                    
                    # None인 경우 기본값 설정
                    if stop_loss_price is None:
                        stop_loss_price = current_price * 0.95
                    if take_profit_price is None:
                        take_profit_price = current_price * 1.05
                    
                    self.positions[symbol] = {
                        'name': stock_name,
                        'quantity': quantity,
                        'entry_price': current_price,
                        'entry_time': datetime.now(),
                        'stop_loss': stop_loss_price,
                        'take_profit': take_profit_price
                    }
                    
                    logger.info(f"포지션 등록: {symbol} - 손절: {stop_loss_price:,.0f}원, 익절: {take_profit_price:,.0f}원")
                else:
                    logger.error(f"매수 주문 실패: {result}")
                    
            elif action == 'SELL' and symbol in self.positions:
                # 현재가 조회 (매도 주문 전)
                current_price = await self.get_current_price(symbol)
                if not current_price:
                    logger.warning(f"현재가 조회 실패로 매도 중단: {symbol}")
                    return
                
                # 매도 주문
                position = self.positions[symbol]
                logger.info(f"매도 주문 시작: {symbol} {position['quantity']}주 @ {current_price:,}원")
                
                result = self.api.sell_order(
                    stock_code=symbol,
                    quantity=position['quantity'],
                    price=0,  # 시장가
                    order_type="MARKET"
                )
                
                logger.info(f"매도 주문 API 응답: {result}")
                
                if result and result.get('rt_cd') == '0':
                    logger.info(f"매도 주문 성공: {stock_name} {position['quantity']}주")
                    print(f"[매도] {stock_name} {position['quantity']}주 @ {current_price:,}원")
                    
                    # 수익률 계산
                    entry_price = position['entry_price']
                    profit_rate = ((current_price - entry_price) / entry_price) * 100
                    profit_loss = (current_price - entry_price) * position['quantity']
                    
                    # 동적 간격 제어기에 매매 기록
                    from support.dynamic_interval_controller import TradeResult
                    trade_result = TradeResult.PROFIT if profit_rate > 0 else TradeResult.LOSS
                    if abs(profit_rate) < 0.5:  # 0.5% 미만은 무승부로 간주
                        trade_result = TradeResult.BREAKEVEN
                    
                    self.interval_controller.record_trade(
                        action='sell',
                        symbol=symbol,
                        stock_name=stock_name,
                        price=current_price,
                        quantity=position['quantity'],
                        result=trade_result,
                        profit_loss=profit_loss
                    )
                    
                    # 매도 후 계좌 정보 조회
                    balance_info = self.api.get_account_balance(force_refresh=True)
                    
                    # 텔레그램 알림 (수익률 및 잔고 정보 포함)
                    await self.telegram.send_order_result(
                        symbol, "매도", position['quantity'], current_price, "성공",
                        balance_info=balance_info, profit_rate=profit_rate, api_connector=self.api,
                        avg_buy_price=entry_price
                    )
                    
                    # 포지션 제거
                    del self.positions[symbol]
                else:
                    logger.error(f"매도 주문 실패: {result}")
                    
        except Exception as e:
            logger.error(f"매매 실행 실패 ({symbol}, {action}): {e}")
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """현재가 조회"""
        try:
            data = self.api.get_stock_price(symbol)
            if data and data.get('rt_cd') == '0' and 'output' in data:
                output = data['output']
                price = float(output.get('stck_prpr', 0))
                if price > 0:
                    return price
        except Exception as e:
            logger.debug(f"현재가 조회 오류 ({symbol}): {e}")
        return None
    
    async def check_positions(self):
        """포지션 체크 (손절/익절)"""
        for symbol in list(self.positions.keys()):
            try:
                position = self.positions[symbol]
                
                # 사용자 지정종목 처리 (익절 제외, -5% 손절만 적용)
                if (position.get('user_designated', False) or 
                    self.user_stock_manager.is_user_designated_stock(symbol)):
                    await self.check_user_designated_stop_loss(symbol, position)
                    continue
                
                current_price = await self.get_current_price(symbol)
                
                if not current_price:
                    continue
                
                # 손절 체크 (None 값 안전하게 처리)
                stop_loss = position.get('stop_loss')
                take_profit = position.get('take_profit')
                
                # stop_loss가 None이면 기본값 설정 (진입가의 5% 손절)
                if stop_loss is None:
                    entry_price = position.get('entry_price', current_price)
                    stop_loss = entry_price * 0.95
                    position['stop_loss'] = stop_loss
                    logger.warning(f"{symbol}: stop_loss가 None이어서 기본값 설정: {stop_loss:,.0f}원")
                
                # take_profit이 None이면 기본값 설정 (진입가의 5% 익절)
                if take_profit is None:
                    entry_price = position.get('entry_price', current_price)
                    take_profit = entry_price * 1.05
                    position['take_profit'] = take_profit
                    logger.warning(f"{symbol}: take_profit이 None이어서 기본값 설정: {take_profit:,.0f}원")
                
                # 손절 실행 (고급 규칙 적용하지 않음)
                if current_price <= stop_loss:
                    logger.info(f"손절 실행: {symbol} at {current_price:,.0f}원 (손절가: {stop_loss:,.0f}원)")
                    await self.execute_trade(symbol, 'SELL', position['quantity'])
                    continue
                    
                # 익절 체크 - 고급 매도 규칙 적용
                elif current_price >= take_profit:
                    algorithm_sell_signal = True  # 알고리즘 매도 신호
                    
                    # 고급 매도 규칙으로 매도 지연 여부 판단
                    should_delay = await self.advanced_sell_rules.should_delay_sell(
                        symbol, algorithm_sell_signal
                    )
                    
                    if should_delay:
                        # 매도 지연 상태 조회
                        delay_status = self.advanced_sell_rules.get_sell_delay_status(symbol)
                        logger.info(f"익절 매도 지연: {symbol} at {current_price} "
                                   f"(매수세 지속, 지연 횟수: {delay_status['delay_count']}/{delay_status['max_delay']})")
                        
                        # 텔레그램 알림
                        await self.telegram.send_message(
                            f"[지연] <b>매도 지연</b>\n\n"
                            f"<b>종목:</b> {self.api.get_stock_display_name(symbol)}\n"
                            f"<b>현재가:</b> {current_price:,}원\n"
                            f"<b>매수세:</b> {delay_status['latest_buying_pressure']:.1f}\n"
                            f"<b>연속신호:</b> {delay_status['consecutive_buy_signals']}회\n"
                            f"<b>지연횟수:</b> {delay_status['delay_count']}/{delay_status['max_delay']}"
                        )
                    else:
                        logger.info(f"익절 실행: {symbol} at {current_price}")
                        await self.execute_trade(symbol, 'SELL', position['quantity'])
                    
            except Exception as e:
                logger.error(f"포지션 체크 실패 ({symbol}): {e}")
    
    async def check_user_designated_stop_loss(self, symbol: str, position: dict):
        """사용자 지정종목 -5% 손절 처리"""
        try:
            current_price = await self.get_current_price(symbol)
            if not current_price:
                return
            
            # 평균 매수가 기준으로 -5% 손절
            avg_price = position.get('avg_price') or position.get('entry_price', 0)
            if avg_price <= 0:
                logger.warning(f"사용자 지정종목 평균가 없음: {symbol}")
                return
            
            # -5% 손절 기준
            stop_loss_threshold = avg_price * 0.95
            loss_rate = (current_price - avg_price) / avg_price
            
            if current_price <= stop_loss_threshold:
                stock_name = position.get('name', symbol)
                quantity = position.get('quantity', 0)
                
                logger.warning(f"사용자 지정종목 -5% 손절 실행: {stock_name}({symbol}) "
                             f"평균가: {avg_price:,.0f}원 → 현재가: {current_price:,.0f}원 "
                             f"({loss_rate*100:.1f}% 손실)")
                
                # 텔레그램 알림 전송
                await self.send_user_designated_stop_loss_notification(
                    symbol, stock_name, quantity, avg_price, current_price, loss_rate
                )
                
                # 시장가 매도 실행
                success = await self.execute_user_designated_stop_loss(symbol, quantity)
                
                if success:
                    # 포지션에서 제거
                    if symbol in self.positions:
                        del self.positions[symbol]
                    
                    # 사용자 지정종목 관리자에도 반영
                    self.user_stock_manager.update_position_info(
                        symbol, quantity, current_price, "sell"
                    )
                    
                    logger.info(f"사용자 지정종목 -5% 손절 완료: {stock_name}({symbol})")
                else:
                    logger.error(f"사용자 지정종목 -5% 손절 실패: {stock_name}({symbol})")
                    
        except Exception as e:
            logger.error(f"사용자 지정종목 손절 처리 실패 ({symbol}): {e}")
    
    async def send_user_designated_stop_loss_notification(self, symbol: str, stock_name: str, 
                                                        quantity: int, avg_price: float, 
                                                        current_price: float, loss_rate: float):
        """사용자 지정종목 손절 알림"""
        try:
            loss_amount = (avg_price - current_price) * quantity
            
            message = (
                f"**사용자 지정종목 자동 손절 실행**\n\n"
                f"**종목**: {stock_name} ({symbol})\n"
                f"**보유수량**: {quantity:,}주\n"
                f"**평균매수가**: {avg_price:,.0f}원\n"
                f"**현재가**: {current_price:,.0f}원\n"
                f"**손실률**: {loss_rate*100:.1f}%\n"
                f"**손실금액**: -{loss_amount:,.0f}원\n"
                f"**매도유형**: 시장가 자동 손절\n"
                f"**시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"**사유**: 평균매수가 대비 -5% 이상 하락으로 자동 손절됩니다.\n\n"
                f"**참고**: 사용자 지정종목은 -5% 손절이 자동 적용됩니다."
            )
            
            if self.telegram:
                await self.telegram.send_message(message)
                logger.info(f"사용자 지정종목 손절 알림 전송: {stock_name}({symbol})")
                
        except Exception as e:
            logger.error(f"사용자 지정종목 손절 알림 실패: {symbol} - {e}")
    
    async def execute_user_designated_stop_loss(self, symbol: str, quantity: int) -> bool:
        """사용자 지정종목 시장가 손절 실행"""
        try:
            # 시장가 매도 주문
            result = self.api.sell_order(
                stock_code=symbol,
                quantity=quantity,
                price=0,  # 시장가
                order_type="MARKET"
            )
            
            if result and result.get('rt_cd') == '0':
                order_no = result.get('output', {}).get('ODNO', 'N/A')
                logger.info(f"사용자 지정종목 손절 주문 성공: {symbol} {quantity}주, 주문번호: {order_no}")
                return True
            else:
                error_msg = result.get('msg1', '알 수 없는 오류') if result else '주문 실패'
                logger.error(f"사용자 지정종목 손절 주문 실패: {symbol} - {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"사용자 지정종목 손절 실행 실패: {symbol} - {e}")
            return False
    
    async def trading_cycle(self):
        """순수 매매 사이클 - 핵심 로직만"""
        try:
            current_time = datetime.now().strftime('%H:%M:%S')
            logger.info(f"[{current_time}] 매매 사이클 시작")
            
            # 포지션 체크만 수행
            await self.check_positions()
            
            # 기본 매수 로직 (간소화)
            max_positions = 3  # 하드코딩으로 간소화
            logger.info(f"포지션 상태: {len(self.positions)}/{max_positions}")
            
            if len(self.positions) < max_positions:
                
                # 3. 모니터링 종목 업데이트 (10분마다)
                if not self.last_scan_time or (datetime.now() - self.last_scan_time).seconds > 600:
                    self.theme_stocks = self.load_theme_stocks()
                    
                    # 문자열 리스트로 변환 (딕셔너리나 객체가 포함될 수 있으므로)
                    theme_symbols = []
                    for item in self.theme_stocks:
                        if isinstance(item, str):
                            theme_symbols.append(item)
                        elif isinstance(item, dict) and 'symbol' in item:
                            theme_symbols.append(item['symbol'])
                        elif hasattr(item, 'symbol'):
                            theme_symbols.append(item.symbol)
                    
                    # 테마주만 사용 (급등주 스캔 제거)
                    self.monitoring_stocks = list(set(theme_symbols))
                    self.last_scan_time = datetime.now()
                    logger.info(f"모니터링 종목 업데이트: {len(self.monitoring_stocks)}개")
                
                # 4. 일반 알고리즘 매매
                print_algorithm_start("자동매매")
                analysis_count = 0
                total_stocks = min(30, len(self.monitoring_stocks))
                logger.info(f"일반 알고리즘 종목 분석 시작: {total_stocks}개 종목")
                logger.info(f"사용 중인 알고리즘: {self.algorithm.get_name() if self.algorithm and hasattr(self.algorithm, 'get_name') else 'Unknown'}")
                
                for symbol in self.monitoring_stocks[:30]:  # 최대 30개만 분석
                    # 이미 보유 중인 종목은 제외
                    if symbol in self.positions:
                        continue
                    
                    analysis_count += 1
                    if analysis_count % 10 == 0:  # 10개마다 로그
                        logger.info(f"종목 분석 진행중: {analysis_count}/{total_stocks}")
                    
                    # 주식 데이터 조회
                    stock_data = await self.get_stock_data(symbol)
                    if not stock_data:
                        logger.warning(f"주식 데이터 조회 실패: {symbol}")
                        continue
                    
                    # 알고리즘 분석
                    if self.algorithm and hasattr(self.algorithm, 'analyze'):
                        try:
                            logger.debug(f"알고리즘 분석 시작: {symbol}")
                            # stock_data와 symbol 타입 안전성 보장
                            safe_stock_data = stock_data if isinstance(stock_data, dict) else {}
                            safe_symbol = symbol if isinstance(symbol, str) else str(symbol) if symbol else None
                            
                            # analyze 메서드 호출 시 타입 안전성 확보
                            if hasattr(self.algorithm.analyze, '__code__') and self.algorithm.analyze.__code__.co_argcount > 2:
                                # stock_code 매개변수가 있는 경우
                                signal = self.algorithm.analyze(safe_stock_data, stock_code=safe_symbol)
                            else:
                                # stock_code 매개변수가 없는 경우
                                signal = self.algorithm.analyze(safe_stock_data)
                            
                            logger.debug(f"알고리즘 분석 결과: {symbol} = {signal}")
                            
                            # SELL 신호 처리 (보유 종목이 있을 때만)
                            if signal == 'SELL' and symbol in self.positions:
                                logger.info(f"{symbol}: 분석 결과 = {signal}")
                                logger.info(f"알고리즘 매도 신호 발생: {symbol} (가격: {stock_data.get('current_price', 0):,}원)")
                                
                                # 매매 신호 텔레그램 알림
                                current_price = stock_data.get('current_price', 0)
                                await self.telegram.send_trade_signal(symbol, signal, current_price, "알고리즘 매도 신호", self.api)
                                
                                # 고급 매도 규칙으로 매도 지연 여부 판단
                                should_delay = await self.advanced_sell_rules.should_delay_sell(
                                    symbol, True  # 알고리즘 매도 신호
                                )
                                
                                if should_delay:
                                    # 매도 지연 상태 조회
                                    delay_status = self.advanced_sell_rules.get_sell_delay_status(symbol)
                                    logger.info(f"알고리즘 매도 지연: {symbol} at {current_price} "
                                               f"(매수세 지속, 지연 횟수: {delay_status['delay_count']}/{delay_status['max_delay']})")
                                    
                                    # 텔레그램 알림
                                    await self.telegram.send_message(
                                        f"[지연] <b>알고리즘 매도 지연</b>\n\n"
                                        f"<b>종목:</b> {self.api.get_stock_display_name(symbol)}\n"
                                        f"<b>현재가:</b> {current_price:,}원\n"
                                        f"<b>매수세:</b> {delay_status['latest_buying_pressure']:.1f}\n"
                                        f"<b>연속신호:</b> {delay_status['consecutive_buy_signals']}회\n"
                                        f"<b>지연횟수:</b> {delay_status['delay_count']}/{delay_status['max_delay']}"
                                    )
                                else:
                                    logger.info(f"알고리즘 매도 실행: {symbol} at {current_price}")
                                    await self.execute_trade(symbol, 'SELL', self.positions[symbol]['quantity'])
                                    
                                continue  # 매도 처리 후 다음 종목으로
                            
                            elif signal == 'SELL' and symbol not in self.positions:
                                logger.debug(f"{symbol}: 매도 신호이지만 보유하지 않은 종목 - 무시")
                                continue
                            
                            # 매수 신호 처리
                            elif signal == 'BUY':
                                current_time = datetime.now().strftime('%H:%M:%S')
                                logger.info(f"{symbol}: 분석 결과 = {signal}")
                                logger.info(f"매수 신호 발생: {symbol} (가격: {stock_data.get('current_price', 0):,}원)")
                                print(f"[{current_time}] 매수 신호! {symbol} @ {stock_data.get('current_price', 0):,}원")
                                # 매매 신호 텔레그램 알림
                                current_price = stock_data.get('current_price', 0)
                                await self.telegram.send_trade_signal(symbol, signal, current_price, "알고리즘 매수 신호", self.api)
                                
                                # 계좌 잔고 조회
                                balance = self.api.get_account_balance()
                                if balance:
                                    cash = float(balance.get('ord_psbl_cash', 0))
                                    logger.info(f"매수 검토: {symbol}, 사용가능금액: {cash:,.0f}원")
                                    
                                    # 포지션 크기 계산
                                    if hasattr(self.algorithm, 'calculate_position_size'):
                                        logger.info(f"알고리즘 포지션 크기 계산 사용: {symbol}")
                                        quantity = self.algorithm.calculate_position_size(
                                            stock_data['current_price'], cash
                                        )
                                    else:
                                        # 매매 규칙 기반 포지션 크기 계산
                                        logger.info(f"매매 규칙 포지션 크기 계산 사용: {symbol}")
                                        quantity = self.trading_rules.calculate_position_size(
                                            cash, stock_data['current_price']
                                        )
                                        logger.info(f"매매 규칙 계산 세부사항: 잔고={cash:,.0f}원, 가격={stock_data['current_price']:,.0f}원, 포지션비율={self.trading_rules.get_position_size_ratio():.1%}")
                                    
                                    logger.info(f"계산된 매수 수량: {symbol} = {quantity}주")
                                    
                                    if quantity > 0:
                                        logger.info(f"매수 실행 시작: {symbol} {quantity}주")
                                        await self.execute_trade(symbol, 'BUY', quantity)
                                        break  # 한 번에 하나씩만 매수
                                    else:
                                        logger.warning(f"매수 실행 불가: {symbol} - 계산된 수량이 0주")
                                else:
                                    logger.error(f"매수 실행 불가: {symbol} - 계좌 잔고 조회 실패")
                                        
                        except Exception as e:
                            logger.error(f"알고리즘 분석 실패 ({symbol}): {e}")
                    
                    # Rate Limit 준수
                    await asyncio.sleep(1)
                
                print_algorithm_end("자동매매")
                await step_delay(3)
            
        except Exception as e:
            logger.error(f"매매 사이클 실패: {e}")
            print_algorithm_end("자동매매")
            await step_delay(3)
    
    async def close_all_positions(self):
        """모든 포지션 정리"""
        try:
            logger.info("모든 포지션 정리 시작")
            
            # 보유 주식 조회
            positions = self.api.get_stock_balance()
            if not positions:
                logger.info("정리할 포지션이 없습니다")
                return
            
            for position in positions:
                symbol = position['pdno']
                quantity = int(position['hldg_qty'])
                stock_name = position['prdt_name']
                
                if quantity > 0:
                    logger.info(f"포지션 정리: {stock_name}({symbol}) {quantity}주")
                    
                    # 시장가 매도 주문
                    try:
                        result = self.api.sell_order(
                            stock_code=symbol,
                            quantity=quantity,
                            price=0,  # 시장가
                            order_type="01"  # 시장가
                        )
                        
                        if result and result.get('rt_cd') == '0':
                            logger.info(f"매도 주문 완료: {stock_name}")
                            print(f"[매도 완료] {stock_name}")
                            # 내부 포지션에서도 제거
                            if symbol in self.positions:
                                del self.positions[symbol]
                        else:
                            logger.error(f"매도 주문 실패: {stock_name}")
                            
                    except Exception as e:
                        logger.error(f"매도 주문 오류 ({stock_name}): {e}")
                        
                    # Rate Limit 준수
                    await asyncio.sleep(1)
            
            logger.info("모든 포지션 정리 완료")
            
        except Exception as e:
            logger.error(f"포지션 정리 실패: {e}")
    
    async def generate_daily_report(self):
        """일일 거래 리포트 생성"""
        try:
            logger.info("일일 거래 리포트 생성 시작")
            
            # 리포트 디렉토리 생성 (프로젝트 루트 기준)
            report_dir = Path(__file__).parent.parent / "report"
            report_dir.mkdir(exist_ok=True, parents=True)
            logger.info(f"리포트 디렉토리: {report_dir}")
            
            today = datetime.now().strftime('%Y%m%d')
            account_type = "mock" if self.account_type == "MOCK" else "real"
            
            # 계좌 정보 조회
            balance_info = self.api.get_account_balance()
            positions = self.api.get_stock_balance()
            
            # 리포트 데이터 생성
            report_data = {
                "date": today,
                "account_type": account_type,
                "timestamp": datetime.now().isoformat(),
                "account_summary": {
                    "total_asset": int(balance_info.get('tot_evlu_amt', 0)) if balance_info else 0,
                    "available_cash": int(balance_info.get('ord_psbl_cash', 0)) if balance_info else 0,
                    "deposit": int(balance_info.get('dnca_tot_amt', 0)) if balance_info else 0
                },
                "positions": [],
                "trading_summary": {
                    "total_trades": len(self.positions),
                    "algorithm_used": self.algorithm.get_name() if self.algorithm else "Unknown"
                }
            }
            
            # 보유 종목 정보
            if positions:
                for pos in positions:
                    position_data = {
                        "symbol": pos['pdno'],
                        "name": pos['prdt_name'],
                        "quantity": int(pos['hldg_qty']),
                        "average_price": float(pos['pchs_avg_pric']),
                        "current_price": float(pos['prpr']),
                        "evaluation_amount": int(pos['evlu_amt']),
                        "profit_loss": int(pos['evlu_pfls_amt']),
                        "profit_rate": float(pos['evlu_pfls_rt'])
                    }
                    report_data["positions"].append(position_data)
            
            # 알고리즘 이름을 파일명에 사용할 수 있도록 정리
            algorithm_name = self.algorithm.get_name() if self.algorithm else "Unknown"
            # 파일명에 사용할 수 없는 문자 제거 및 공백을 언더스코어로 변경
            safe_algorithm_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in algorithm_name)
            safe_algorithm_name = safe_algorithm_name.replace(' ', '_').replace('__', '_').strip('_')
            
            # JSON 리포트 저장
            json_filename = f"trading_report_{account_type}_{safe_algorithm_name}_{today}.json"
            json_path = report_dir / json_filename
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            # HTML 리포트 생성
            html_content = self._generate_html_report(report_data)
            html_filename = f"trading_report_{account_type}_{safe_algorithm_name}_{today}.html"
            html_path = report_dir / html_filename
            
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"일일 리포트 생성 완료: {json_filename}, {html_filename}")
            logger.info(f"적용된 알고리즘: {algorithm_name}")
            
        except Exception as e:
            logger.error(f"리포트 생성 실패: {e}")
    
    def _generate_html_report(self, data: dict) -> str:
        """HTML 리포트 생성"""
        html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>tideWise 일일 거래 리포트 - {data['date']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; }}
        .section {{ margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .positive {{ color: #d32f2f; }}
        .negative {{ color: #1976d2; }}
        .summary {{ background-color: #e8f5e8; padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>tideWise 일일 거래 리포트</h1>
        <p>날짜: {data['date']} | 계좌: {data['account_type'].upper()} | 생성시간: {data['timestamp']}</p>
    </div>
    
    <div class="section">
        <h2>계좌 요약</h2>
        <div class="summary">
            <p><strong>총 자산:</strong> {data['account_summary']['total_asset']:,}원</p>
            <p><strong>주문가능금액:</strong> {data['account_summary']['available_cash']:,}원</p>
            <p><strong>예수금:</strong> {data['account_summary']['deposit']:,}원</p>
        </div>
    </div>
    
    <div class="section">
        <h2>보유 종목</h2>
        <table>
            <thead>
                <tr>
                    <th>종목명</th>
                    <th>종목코드</th>
                    <th>보유수량</th>
                    <th>평균단가</th>
                    <th>현재가</th>
                    <th>평가금액</th>
                    <th>평가손익</th>
                    <th>수익률</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for pos in data['positions']:
            profit_class = 'positive' if pos['profit_loss'] >= 0 else 'negative'
            html += f"""
                <tr>
                    <td>{pos['name']}</td>
                    <td>{pos['symbol']}</td>
                    <td>{pos['quantity']:,}주</td>
                    <td>{pos['average_price']:,}원</td>
                    <td>{pos['current_price']:,}원</td>
                    <td>{pos['evaluation_amount']:,}원</td>
                    <td class="{profit_class}">{pos['profit_loss']:+,}원</td>
                    <td class="{profit_class}">{pos['profit_rate']:+.2f}%</td>
                </tr>
"""
        
        if not data['positions']:
            html += "<tr><td colspan='8'>보유 종목이 없습니다.</td></tr>"
        
        html += f"""
            </tbody>
        </table>
    </div>
    
    <div class="section">
        <h2>거래 요약</h2>
        <p><strong>사용 알고리즘:</strong> {data['trading_summary']['algorithm_used']}</p>
        <p><strong>총 거래 건수:</strong> {data['trading_summary']['total_trades']}건</p>
    </div>
    
    <div class="section">
        <p><small>이 리포트는 tideWise 시스템에 의해 자동 생성되었습니다.</small></p>
    </div>
</body>
</html>
"""
        return html
    
    async def analyze_market_sentiment(self, symbol: str) -> Dict[str, Any]:
        """매수세 및 시장 심리 분석 - 전전날 vs 전날 종가 및 거래량 비교"""
        try:
            # 타임아웃 설정 및 비동기 처리 개선 (API 호출 블로킹 방지)
            logger.debug(f"[{symbol}] 매수세 분석 시작...")
            
            # API 호출을 비동기화하고 타임아웃 적용 (최대 10초)
            daily_data = None
            try:
                # API 호출을 별도 스레드에서 실행하여 블로킹 방지
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self.api.get_daily_chart, symbol, 5)
                    daily_data = await asyncio.wait_for(
                        asyncio.wrap_future(future), 
                        timeout=10.0  # 10초 타임아웃
                    )
                logger.debug(f"[{symbol}] 일봉 데이터 조회 성공")
            except asyncio.TimeoutError:
                logger.warning(f"[{symbol}] API 타임아웃 (10초) - 기본값 사용")
                daily_data = None
            except Exception as api_error:
                logger.warning(f"[{symbol}] API 호출 오류: {api_error} - 기본값 사용")
                daily_data = None
            
            sentiment = {
                'trend': 'NEUTRAL',
                'buy_pressure': 0,
                'volume_trend': 'STABLE',
                'recommendation': 'HOLD',
                'day_before_yesterday': 0,  # 전전날 종가
                'yesterday': 0,            # 전날 종가  
                'yesterday_volume': 0,     # 전날 거래량
                'day_before_yesterday_volume': 0  # 전전날 거래량
            }
            
            # 일봉 데이터 분석 (전전날, 전날 종가 및 거래량 비교)
            if daily_data and isinstance(daily_data, dict) and 'output2' in daily_data:
                candles = daily_data['output2']  # 일봉 데이터
                
                if len(candles) >= 3:  # 최소 3일 데이터 필요 (오늘, 전날, 전전날)
                    # 인덱스 0: 최신(오늘/현재), 1: 전날, 2: 전전날
                    today_close = self._safe_float(candles[0].get('stck_clpr', 0))
                    yesterday_close = self._safe_float(candles[1].get('stck_clpr', 0))  # 전날 종가
                    day_before_yesterday_close = self._safe_float(candles[2].get('stck_clpr', 0))  # 전전날 종가
                    
                    # 거래량 정보 (전체 매수물량 기준)
                    yesterday_volume = self._safe_int(candles[1].get('acml_vol', 0))  # 전날 거래량
                    day_before_yesterday_volume = self._safe_int(candles[2].get('acml_vol', 0))  # 전전날 거래량
                    
                    # 센티멘트 정보에 기록
                    sentiment['yesterday'] = yesterday_close
                    sentiment['day_before_yesterday'] = day_before_yesterday_close  
                    sentiment['yesterday_volume'] = yesterday_volume
                    sentiment['day_before_yesterday_volume'] = day_before_yesterday_volume
                    
                    logger.debug(f"[{symbol}] 전전날: {day_before_yesterday_close:,}원, 전날: {yesterday_close:,}원")
                    logger.debug(f"[{symbol}] 전전날 거래량: {day_before_yesterday_volume:,}, 전날 거래량: {yesterday_volume:,}")
                    
                    # 주가 상승세 분석: 전날 종가 > 전전날 종가
                    if yesterday_close > day_before_yesterday_close:
                        price_increase_rate = ((yesterday_close - day_before_yesterday_close) / day_before_yesterday_close) * 100
                        if price_increase_rate >= 1.0:  # 1% 이상 상승
                            sentiment['trend'] = 'RISING'
                        else:
                            sentiment['trend'] = 'SLIGHTLY_RISING'
                    elif yesterday_close < day_before_yesterday_close:
                        price_decrease_rate = ((day_before_yesterday_close - yesterday_close) / day_before_yesterday_close) * 100
                        if price_decrease_rate >= 1.0:  # 1% 이상 하락
                            sentiment['trend'] = 'FALLING' 
                        else:
                            sentiment['trend'] = 'SLIGHTLY_FALLING'
                    else:
                        sentiment['trend'] = 'NEUTRAL'
                    
                    # 매수물량(거래량) 증가 분석: 전날 거래량 > 전전날 거래량
                    if yesterday_volume > 0 and day_before_yesterday_volume > 0:
                        volume_increase_rate = ((yesterday_volume - day_before_yesterday_volume) / day_before_yesterday_volume) * 100
                        if volume_increase_rate >= 20.0:  # 20% 이상 증가
                            sentiment['volume_trend'] = 'INCREASING'
                        elif volume_increase_rate <= -20.0:  # 20% 이상 감소
                            sentiment['volume_trend'] = 'DECREASING'
                        else:
                            sentiment['volume_trend'] = 'STABLE'
                        
                        logger.debug(f"[{symbol}] 거래량 변화율: {volume_increase_rate:+.1f}%")
                    else:
                        sentiment['volume_trend'] = 'STABLE'
            
            # 매수 압력 계산 (전전날 vs 전날 기준) - 정교한 분석
            base_pressure = 40
            
            # 주가 트렌드에 따른 점수 (전날 종가 기준)
            if sentiment['trend'] == 'RISING':
                base_pressure += 30  # 1% 이상 상승
            elif sentiment['trend'] == 'SLIGHTLY_RISING':
                base_pressure += 15  # 소폭 상승
            elif sentiment['trend'] == 'FALLING':
                base_pressure -= 25  # 1% 이상 하락
            elif sentiment['trend'] == 'SLIGHTLY_FALLING':
                base_pressure -= 10  # 소폭 하락
            
            # 거래량 트렌드에 따른 점수 (전날 거래량 기준)
            if sentiment['volume_trend'] == 'INCREASING':
                base_pressure += 25  # 20% 이상 증가
            elif sentiment['volume_trend'] == 'DECREASING':
                base_pressure -= 15  # 20% 이상 감소
            
            # 최종 매수 압력 점수 설정 (10-90점 범위)
            sentiment['buy_pressure'] = max(10, min(90, base_pressure))
            
            # 권장 사항 결정 (전전날 vs 전날 기준)
            if sentiment['buy_pressure'] >= 80:
                sentiment['recommendation'] = 'STRONG_HOLD'  # 매우 강한 홀딩
            elif sentiment['buy_pressure'] >= 65:
                sentiment['recommendation'] = 'HOLD'        # 홀딩
            elif sentiment['buy_pressure'] <= 25:
                sentiment['recommendation'] = 'SELL'        # 매도
            else:
                sentiment['recommendation'] = 'NEUTRAL'     # 중립
            
            return sentiment
            
        except Exception as e:
            logger.error(f"시장 심리 분석 실패 ({symbol}): {e}")
            return {
                'trend': 'NEUTRAL',
                'buy_pressure': 40,
                'volume_trend': 'STABLE',
                'recommendation': 'HOLD'
            }
    
    async def premarket_position_liquidation(self):
        """장 개시 직후 전날 보유 잔고 처리 (매수세 분석 포함)"""
        try:
            logger.info("="*50)
            logger.info("전날 보유 잔고 매수세 분석 시작")
            logger.info("="*50)
            
            # 보유 주식 조회
            positions = self.api.get_stock_balance()
            if not positions:
                logger.info("전날 보유 잔고가 없습니다 - 처리 건너뛰기")
                return
            
            # 실제 보유 수량이 있는 종목만 필터링
            actual_positions = [pos for pos in positions if int(pos.get('hldg_qty', 0)) > 0]
            if not actual_positions:
                logger.info("실제 보유 수량이 있는 종목이 없습니다")
                return
            
            liquidation_decisions = []
            
            # 각 종목별 매수세 분석 (순차 처리 - 메모리 효율성 개선)
            for idx, position in enumerate(actual_positions, 1):
                symbol = position['pdno']
                quantity = int(position['hldg_qty'])
                stock_name = position['prdt_name']
                current_price = float(position['prpr'])
                avg_price = float(position['pchs_avg_pric'])
                profit_rate = float(position['evlu_pfls_rt'])
                
                if quantity > 0:
                    logger.info(f"\n[{idx}/{len(actual_positions)}] 종목 분석: {stock_name}({symbol})")
                    logger.info(f"  - 보유수량: {quantity}주")
                    logger.info(f"  - 현재가: {current_price:,.0f}원 (평균단가: {avg_price:,.0f}원)")
                    logger.info(f"  - 수익률: {profit_rate:+.2f}%")
                    
                    # 1. 사용자 지정종목 빠른 체크 (API 호출 없이)
                    is_user_designated = self.user_stock_manager.is_user_designated_stock(symbol)
                    if is_user_designated:
                        # 사용자 지정종목은 API 호출 없이 즉시 홀딩 처리
                        decision = {
                            'symbol': symbol,
                            'name': stock_name,
                            'quantity': quantity,
                            'current_price': current_price,
                            'avg_price': avg_price,
                            'profit_rate': profit_rate,
                            'should_hold': True,
                            'reason': f"사용자 지정종목 (자동매도 금지, 수익률: {profit_rate:+.2f}%)",
                            'sentiment': {'buy_pressure': 80, 'trend': 'USER_DESIGNATED'},  # 최소 데이터
                            'algorithm_signal': 'HOLD'
                        }
                        liquidation_decisions.append(decision)
                        logger.info(f"  - [사용자 지정종목] 빠른 홀딩 처리: {stock_name}({symbol})")
                        print(f"[사용자 지정종목 홀딩] {stock_name} - 수익률 {profit_rate:+.2f}% (자동매도 금지)")
                        continue  # API 호출 없이 다음 종목으로
                    
                    # 2. 전전날 vs 전날 매수세 및 시장 심리 분석 (API 호출)
                    sentiment = await self.analyze_market_sentiment(symbol)
                    logger.info(f"  - 매수압력: {sentiment['buy_pressure']}%")
                    logger.info(f"  - 전날 가격트렌드: {sentiment['trend']}")
                    logger.info(f"  - 전날 거래량트렌드: {sentiment['volume_trend']}")
                    
                    # 전전날 vs 전날 상세 정보 (간소화)
                    yesterday_price = sentiment.get('yesterday', 0)
                    day_before_yesterday_price = sentiment.get('day_before_yesterday', 0)
                    if yesterday_price > 0 and day_before_yesterday_price > 0:
                        price_change = ((yesterday_price - day_before_yesterday_price) / day_before_yesterday_price * 100)
                        logger.info(f"  - 전날 가격변동: {price_change:+.1f}% ({day_before_yesterday_price:,}→{yesterday_price:,})")
                        
                        # 거래량 정보는 디버그 모드에서만 출력 (성능 개선)
                        if logger.isEnabledFor(logging.DEBUG):
                            yesterday_volume = sentiment.get('yesterday_volume', 0)
                            day_before_yesterday_volume = sentiment.get('day_before_yesterday_volume', 0)
                            if yesterday_volume > 0 and day_before_yesterday_volume > 0:
                                volume_change = ((yesterday_volume - day_before_yesterday_volume) / day_before_yesterday_volume * 100)
                                logger.debug(f"  - 전날 거래량변동: {volume_change:+.1f}%")
                    
                    # 3. 알고리즘 신호 분석 (get_stock_data 호출)
                    algorithm_signal = 'HOLD'  # 기본값
                    if self.algorithm:
                        stock_data = await self.get_stock_data(symbol)
                        if stock_data:
                            try:
                                # 타입 안전성 확보 및 간소화
                                if hasattr(self.algorithm, 'analyze'):
                                    algorithm_signal = self.algorithm.analyze(stock_data)
                            except Exception as e:
                                logger.warning(f"알고리즘 분석 오류 ({symbol}): {e}")
                                algorithm_signal = 'HOLD'
                        else:
                            logger.debug(f"stock_data 조회 실패: {symbol}")
                    logger.info(f"  - 알고리즘 신호: {algorithm_signal}")
                    
                    # 4. 종합 판단 (간소화된 로직)
                    should_hold = False
                    reason = ""
                    buy_pressure = sentiment.get('buy_pressure', 40)
                    trend = sentiment.get('trend', 'NEUTRAL')
                    
                    # 간소화된 가격 변동률 계산
                    price_change = 0
                    if yesterday_price > 0 and day_before_yesterday_price > 0:
                        price_change = ((yesterday_price - day_before_yesterday_price) / day_before_yesterday_price * 100)
                    
                    # 홀딩 조건 검사 (우선순위 순)
                    if (trend in ['RISING', 'SLIGHTLY_RISING'] and 
                        sentiment.get('volume_trend') == 'INCREASING' and 
                        buy_pressure >= 75):
                        should_hold = True
                        reason = f"전날 상승+거래량증가 ({price_change:+.1f}%, 매수압력: {buy_pressure}%)"
                        print(f"[전날 상승+거래량 증가] {stock_name} - {price_change:+.1f}%, 매수압력 {buy_pressure}%")
                    
                    elif (trend in ['RISING', 'SLIGHTLY_RISING'] and buy_pressure >= 65):
                        should_hold = True
                        reason = f"전날 상승세 지속 ({price_change:+.1f}%, 매수압력: {buy_pressure}%)"
                        print(f"[전날 상승세 홀딩] {stock_name} - {price_change:+.1f}%, 매수압력 {buy_pressure}%")
                    
                    elif algorithm_signal == 'BUY' and trend not in ['FALLING', 'SLIGHTLY_FALLING']:
                        should_hold = True
                        reason = f"알고리즘 매수 신호 (트렌드: {trend})"
                    
                    elif profit_rate >= 3.0 and trend in ['RISING', 'SLIGHTLY_RISING']:
                        should_hold = True
                        reason = f"수익 실현 대기 (수익률: {profit_rate:+.2f}%, 상승세)"
                    
                    # 매도 조건 검사
                    elif trend in ['FALLING', 'SLIGHTLY_FALLING'] or buy_pressure < 30:
                        should_hold = False
                        reason = f"전날 하락세 ({price_change:+.1f}%, 매수압력: {buy_pressure}%)"
                    
                    elif profit_rate <= -2.0:
                        should_hold = False
                        reason = f"손실 제한 (수익률: {profit_rate:+.2f}%)"
                    
                    else:
                        should_hold = False
                        reason = f"매도 우위 (매수압력: {buy_pressure}%, 트렌드: {trend})"
                    
                    logger.info(f"  - 결정: {'홀딩' if should_hold else '매도'} - {reason}")
                    
                    liquidation_decisions.append({
                        'symbol': symbol,
                        'name': stock_name,
                        'quantity': quantity,
                        'current_price': current_price,
                        'avg_price': avg_price,
                        'profit_rate': profit_rate,
                        'should_hold': should_hold,
                        'reason': reason,
                        'sentiment': sentiment,
                        'algorithm_signal': algorithm_signal
                    })
                    
                    # Rate Limit 준수 - 최적화된 대기시간 (2초 → 0.5초)
                    await asyncio.sleep(0.5)
            
            # 매도 결정 종목들 실행
            logger.info("\n" + "="*50)
            logger.info("매매 결정 실행")
            logger.info("="*50)
            
            held_count = 0
            sold_count = 0
            
            for decision in liquidation_decisions:
                if decision['should_hold']:
                    held_count += 1
                    logger.info(f"[홀딩] {decision['name']}({decision['symbol']}) - {decision['reason']}")
                    
                    # 내부 포지션에 추가 (자동매매 알고리즘이 관리)
                    self.positions[decision['symbol']] = {
                        'name': decision['name'],
                        'quantity': decision['quantity'],
                        'entry_price': decision['avg_price'],  # 평균단가 사용
                        'current_price': decision['current_price'],
                        'entry_time': datetime.now(),
                        'stop_loss': decision['current_price'] * 0.95,
                        'take_profit': decision['current_price'] * 1.08,
                        'profit_rate': decision['profit_rate']
                    }
                else:
                    sold_count += 1
                    logger.info(f"[매도] {decision['name']}({decision['symbol']}) - {decision['reason']}")
                    
                    try:
                        # 시장가 매도 주문
                        result = self.api.place_sell_order(
                            symbol=decision['symbol'],
                            quantity=decision['quantity'],
                            price=0,  # 시장가
                            order_type="01"  # 시장가
                        )
                        
                        if result and result.get('rt_cd') == '0':
                            logger.info(f"매도 주문 성공: {decision['name']} {decision['quantity']}주")
                            print(f"[전날 보유종목 매도] {decision['name']} {decision['quantity']}주")
                            
                            # 텔레그램 알림
                            msg = f"전날 잔고 매도\n"
                            msg += f"종목: {decision['name']}({decision['symbol']})\n"
                            msg += f"수량: {decision['quantity']}주\n"
                            msg += f"현재가: {decision['current_price']:,.0f}원\n"
                            msg += f"수익률: {decision['profit_rate']:+.2f}%\n"
                            msg += f"사유: {decision['reason']}"
                            await self.telegram.send_message(msg)
                        else:
                            logger.error(f"전날 보유 종목 매도 실패: {decision['name']}")
                            
                    except Exception as e:
                        logger.error(f"매도 주문 오류 ({decision['name']}): {e}")
                
                # Rate Limit 준수
                await asyncio.sleep(1)
            
            logger.info("\n" + "="*50)
            logger.info(f"전날 보유 잔고 처리 결과")
            logger.info(f"- 홀딩: {held_count}개 종목")
            logger.info(f"- 매도: {sold_count}개 종목")
            logger.info("="*50)
            
        except Exception as e:
            logger.error(f"전날 보유 잔고 처리 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    
    async def initialize_trading_data(self):
        """자동매매 시작 전 데이터 초기화"""
        try:
            logger.info("="*60)
            logger.info("자동매매 초기화 시작")
            logger.info(f"투자 타입: {'모의투자' if self.account_type == 'MOCK' else '실전투자'}")
            logger.info("="*60)
            
            # 1. 테마별 종목 정보 갱신 (빠른 초기화를 위해 간소화)
            logger.info("[1/6] 테마별 종목 정보 갱신 중... (빠른 시작)")
            # 기본 종목 동적 로드
            try:
                from support.enhanced_theme_stocks import get_default_stocks
                self.theme_stocks = get_default_stocks()[:5]  # 빠른 시작을 위해 5개만
            except Exception:
                # JSON에서 직접 최소 종목 로드 시도
                try:
                    import json
                    from pathlib import Path
                    json_file = Path(__file__).parent / "enhanced_theme_stocks.json"
                    if json_file.exists():
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if 'Core_Large_Cap' in data and 'stocks' in data['Core_Large_Cap']:
                            self.theme_stocks = data['Core_Large_Cap']['stocks'][:3]
                        else:
                            self.theme_stocks = []  # 빈 리스트
                    else:
                        self.theme_stocks = []  # 빈 리스트
                except Exception:
                    self.theme_stocks = []  # 빈 리스트
            logger.info(f"테마 종목 {len(self.theme_stocks)}개 로드 완료 (빠른 시작 모드)")
            
            # 2. 계좌 정보 조회
            logger.info("[2/5] 계좌 정보 조회 중...")
            balance_info = self.api.get_account_balance()
            if balance_info:
                available_cash = float(balance_info.get('ord_psbl_cash', 0))
                total_asset = float(balance_info.get('tot_evlu_amt', 0))
                logger.info(f"예수금: {available_cash:,.0f}원")
                logger.info(f"총평가금액: {total_asset:,.0f}원")
            else:
                logger.warning("계좌 정보 조회 실패")
            
            # 3. 보유 종목 확인 및 사용자 지정종목 동기화
            logger.info("[3/5] 보유 종목 확인 및 사용자 지정종목 동기화 중...")
            positions = self.api.get_stock_balance()
            actual_positions = []
            if positions:
                actual_positions = [pos for pos in positions if int(pos.get('hldg_qty', 0)) > 0]
                if actual_positions:
                    logger.info(f"보유 종목 {len(actual_positions)}개:")
                    for pos in actual_positions:
                        logger.info(f"  - {pos['prdt_name']}({pos['pdno']}): {pos['hldg_qty']}주")
                else:
                    logger.info("보유 종목 없음")
            
            # 텔레그램으로 계좌 연결 정보 전송 (보유 종목 포함) - 비동기로 처리하여 블로킹 방지
            if self.telegram:
                try:
                    account_type_text = "모의투자" if self.account_type == "MOCK" else "실전투자"
                    # 계좌번호는 API 커넥터의 config에서 가져오기
                    account_number = self.api.config.get('CANO', 'Unknown') if self.api and self.api.config else 'Unknown'
                    
                    # 타임아웃을 설정하여 3초 내에 완료되지 않으면 건너뛰기
                    await asyncio.wait_for(
                        self.telegram.send_connection_info(
                            account_type=account_type_text,
                            account_number=account_number,
                            balance_info=balance_info,
                            positions=actual_positions
                        ),
                        timeout=3.0  # 3초 타임아웃
                    )
                    logger.info("텔레그램 연결 정보 전송 완료")
                except asyncio.TimeoutError:
                    logger.warning("텔레그램 연결 정보 전송 타임아웃 - 계속 진행")
                except Exception as e:
                    logger.warning(f"텔레그램 연결 정보 전송 실패: {e} - 계속 진행")
                
                # 사용자 지정종목과 계좌 보유종목 동기화
                try:
                    self.user_stock_manager.sync_with_account_positions(positions)
                    logger.info("[성공] 사용자 지정종목 동기화 완료")
                except Exception as e:
                    logger.error(f"사용자 지정종목 동기화 실패: {e}")
            else:
                logger.info("보유 종목 없음")
                # 계좌에 종목이 없는 경우 빈 리스트로 동기화
                try:
                    self.user_stock_manager.sync_with_account_positions([])
                    logger.info("[성공] 사용자 지정종목 동기화 완료 (계좌 비어있음)")
                except Exception as e:
                    logger.error(f"사용자 지정종목 동기화 실패: {e}")
            
            # 4. 사용자 지정종목 현황 확인
            logger.info("[4/5] 사용자 지정종목 현황 확인 중...")
            try:
                position_summary = self.user_stock_manager.get_position_summary()
                logger.info(f"사용자 지정종목 현황:")
                logger.info(f"  - 전체 종목: {position_summary['total_stocks']}개")
                logger.info(f"  - 보유 종목: {position_summary['holding_stocks']}개")
                logger.info(f"  - 목표 달성: {position_summary['completed_stocks']}개 ({position_summary['completion_rate']:.1f}%)")
                logger.info(f"  - 총 투자금액: {position_summary['total_investment']:,.0f}원")
            except Exception as e:
                logger.error(f"사용자 지정종목 현황 확인 실패: {e}")
            
            # 5. 사용자 지정종목 준비 완료 (실제 매수는 시장 시간 체크 후 실행)
            logger.info("[5/5] 사용자 지정종목 준비 완료")
            logger.info("사용자 지정종목 우선 매수는 시장 시간 체크 후 실행됩니다")
            # 실제 매수 로직은 시장 시간 체크 후로 이동됨 - 아래 코드 주석 처리됨
            
            logger.info("="*60)
            logger.info("데이터 수집 및 초기화 완료")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"자동매매 초기화 중 오류: {e}")
    
    async def execute_premarket_liquidation(self):
        """통합된 전날 잔고 처리 로직 실행"""
        print_step_start("전날잔고처리")
        
        try:
            # 통합 전날잔고 처리기 생성 (SIMPLE 전략 사용)
            balance_handler = PreviousDayBalanceHandler(
                self.api, 
                self.account_type, 
                TradingStrategy.SIMPLE
            )
            
            # 전낡잔고 정리 실행
            cleanup_result = await balance_handler.execute_previous_day_balance_cleanup()
            
            # 결과 처리
            if cleanup_result.get('success'):
                sold_count = cleanup_result.get('sold_count', 0)
                kept_count = cleanup_result.get('kept_count', 0)
                
                # 간단한 메시지 표시
                if sold_count > 0 or kept_count > 0:
                    self.display.display_simple_message(
                        f"전날 잔고 처리 완료: 매도 {sold_count}개, 보유 {kept_count}개", 
                        'info'
                    )
                else:
                    self.display.display_simple_message("보유 종목이 없습니다.", 'info')
                
                # 매도된 종목이 있으면 텔레그램 알림
                if sold_count > 0 and hasattr(self, 'telegram') and self.telegram:
                    summary_message = f"<b>전날 잔고 처리 완료</b>\n\n"
                    summary_message += f"<b>매도된 종목:</b> {sold_count}개\n"
                    summary_message += f"<b>보유 유지:</b> {kept_count}개\n"
                    summary_message += f"<b>전략:</b> {cleanup_result.get('strategy', 'SIMPLE')}"
                    
                    await self.telegram.send_message(summary_message)
                
                logger.info(f"전날 잔고 처리 완료: {cleanup_result.get('message')}")
            else:
                logger.warning(f"전날 잔고 처리 실패: {cleanup_result.get('message')}")
            
            print_step_end("전날잔고처리")
            await step_delay(3)
            
        except Exception as e:
            logger.error(f"통합 전날 잔고 처리 중 오류: {e}")
            print_step_end("전날잔고처리")
            await step_delay(3)
    
            
    async def run(self):
        """자동매매 실행 - 순수 매매 사이클만 실행"""
        print_step_start("자동매매 시스템")
        logger.info("자동매매 시작")
        self.is_running = True
        self.stop_requested = False
        
        # 1) 시작 시 신호 파일 정리 (잔여 신호 파일로 인한 즉시 종료 방지)
        self.keyboard_handler.clear_stop_signal_files()
        
        # 2) ESC 감지 비활성 옵션 반영 (환경/설정 기반)
        from support.trading_config_manager import TradingConfigManager
        try:
            cfg = TradingConfigManager()
            use_esc = cfg.get("enable_esc_stop", False)
            if not use_esc:
                self.keyboard_handler.disable_esc_listening = True
                logger.info("[CONFIG] ESC detection disabled - using file-based signals only")
        except Exception as e:
            logger.warning(f"[CONFIG] Failed to load ESC config, using default: {e}")
        
        # 파일 기반 중단 시스템 시작
        self.keyboard_handler.start_listening()
        # 방어용: interval_controller 재초기화 보장 (NoneType 방지)
        if not hasattr(self, 'interval_controller') or self.interval_controller is None:
            from support.dynamic_interval_controller import tideWiseDynamicIntervalController as DynamicIntervalController
            self.interval_controller = DynamicIntervalController()
        print("* Auto trading can be stopped by creating signal files. (See instructions above)")
        
        # 계좌 조회 중 메시지만 표시
        from support.account_display_utils import show_account_inquiry_message, display_account_info
        show_account_inquiry_message()
        
        # 텔레그램 알림 (간소화)
        await self.telegram.send_message("계좌 정보 조회 시작")
        
        balance_info = await self.api.get_account_balance(force_refresh=True)
        if balance_info:
            # 계좌번호 가져오기
            account_no = self.api.account_number or balance_info.get('acct_no', '')
            
            # 표준화된 계좌 정보 표시
            account_data = {
                'account_number': account_no,
                'total_cash': balance_info.get('total_evaluation', 0),
                'buyable_cash': balance_info.get('available_cash', 0),
                'profit_rate': balance_info.get('profit_rate', 0.0),
                'holdings': balance_info.get('holdings', [])
            }
            
            display_account_info(account_data, "MOCK")
            await step_delay(3)
        else:
            print("[ERROR] 계좌 정보 조회 실패")
            await step_delay(3)
            await step_delay(3)
        
        # [2/5] 보유 종목 조회
        logger.info("[2/5] 보유 종목 조회 중...")
        print("[2/5] 보유 종목 조회 중...")
        
        await self.telegram.send_message(
            f"<b>[2/5] 보유 종목 조회 시작</b>\n\n"
            f"현재 보유하고 있는 종목을 확인 중입니다."
        )
        
        positions = await self.api.get_stock_balance()
        if positions and len(positions) > 0:
            actual_positions = [pos for pos in positions if int(pos.get('hldg_qty', 0)) > 0]
            if actual_positions:
                logger.info(f"[완료] 보유 종목: {len(actual_positions)}개")
                print(f"[완료] 보유 종목: {len(actual_positions)}개")
                
                position_details = []
                for pos in actual_positions:
                    name = pos.get('prdt_name', '')
                    symbol = pos.get('pdno', '')
                    qty = int(pos.get('hldg_qty', 0))
                    avg_price = float(pos.get('pchs_avg_pric', 0))
                    current_price = float(pos.get('prpr', 0))
                    profit_rate = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
                    
                    position_detail = f"• {name}({symbol}): {qty}주, 평균가: {avg_price:,.0f}원, 수익률: {profit_rate:+.2f}%"
                    position_details.append(position_detail)
                    print(f"  - {position_detail}")
                
                await self.telegram.send_message(
                    f"<b>[완료] 보유 종목: {len(actual_positions)}개</b>\n\n"
                    + "\n".join(position_details)
                )
            else:
                logger.info("[완료] 보유 종목 없음")
                print("[완료] 보유 종목 없음")
                await self.telegram.send_message(
                    f"<b>[완료] 보유 종목 조회</b>\n\n"
                    f"현재 보유하고 있는 종목이 없습니다."
                )
        else:
            logger.info("[완료] 보유 종목 없음")
            print("[완료] 보유 종목 없음")
            await self.telegram.send_message(
                f"<b>[완료] 보유 종목 조회</b>\n\n"
                f"현재 보유하고 있는 종목이 없습니다."
            )
        
        # [3/5] 사용자 지정종목 조회
        logger.info("[3/5] 사용자 지정종목 조회 중...")
        print("[3/5] 사용자 지정종목 조회 중...")
        
        await self.telegram.send_message(
            f"<b>[3/5] 사용자 지정종목 조회 시작</b>\n\n"
            f"투자할 종목 리스트를 확인 중입니다."
        )
        
        user_stocks = self.load_user_designated_stocks()
        if user_stocks:
            logger.info(f"[완료] 사용자 지정종목: {len(user_stocks)}개")
            print(f"[완료] 사용자 지정종목: {len(user_stocks)}개")
            
            display_stocks = user_stocks[:5]
            stock_details = []
            for stock in display_stocks:
                if isinstance(stock, dict):
                    name = stock.get('name', '이름없음')
                    symbol = stock.get('symbol', '코드없음')
                elif isinstance(stock, str):
                    symbol = stock
                    name = self.api.get_stock_display_name(symbol)
                else:
                    continue
                    
                stock_detail = f"• {name}({symbol})"
                stock_details.append(stock_detail)
                print(f"  - {stock_detail}")
            
            if len(user_stocks) > 5:
                more_count = len(user_stocks) - 5
                stock_details.append(f"외 {more_count}개")
                print(f"  외 {more_count}개")
            
            await self.telegram.send_message(
                f"<b>[완료] 사용자 지정종목: {len(user_stocks)}개</b>\n\n"
                + "\n".join(stock_details)
            )
        else:
            logger.info("[완료] 사용자 지정종목 없음")
            print("[완료] 사용자 지정종목 없음")
            await self.telegram.send_message(
                f"<b>[완료] 사용자 지정종목 조회</b>\n\n"
                f"설정된 사용자 지정종목이 없습니다."
            )
        
        # [4/5] 모니터링 종목 수집
        logger.info("[4/5] 모니터링 종목 수집 중...")
        print("[4/5] 모니터링 종목 수집 중...")
        
        await self.telegram.send_message(
            f"<b>[4/5] 모니터링 종목 수집 시작</b>\n\n"
            f"매매 대상 종목들을 수집하고 있습니다."
        )
        
        self.theme_stocks = self.load_theme_stocks()
        
        all_monitoring = list(set(self.theme_stocks))
        
        if all_monitoring:
            logger.info(f"[완료] 수집된 종목: {len(all_monitoring)}개")
            print(f"[완료] 수집된 종목: {len(all_monitoring)}개")
            
            display_monitoring = all_monitoring[:10]
            monitoring_details = []
            for symbol in display_monitoring:
                name = self.api.get_stock_display_name(symbol)
                monitoring_detail = f"• {name}({symbol})"
                monitoring_details.append(monitoring_detail)
                print(f"  - {monitoring_detail}")
            
            if len(all_monitoring) > 10:
                more_count = len(all_monitoring) - 10
                monitoring_details.append(f"외 {more_count}개")
                print(f"  외 {more_count}개")
            
            await self.telegram.send_message(
                f"<b>[완료] 모니터링 종목 수집: {len(all_monitoring)}개</b>\n\n"
                + "\n".join(monitoring_details)
            )
        else:
            logger.info("[완료] 수집된 종목 없음")
            print("[완료] 수집된 종목 없음")
            await self.telegram.send_message(
                f"<b>[완료] 모니터링 종목 수집</b>\n\n"
                f"매매 대상 종목이 수집되지 않았습니다."
            )
        
        # [5/5] 자동매매 시작
        logger.info("="*60)
        logger.info("[5/5] 자동매매 사이클 시작!")
        logger.info("="*60)
        print("\n[5/5] 자동매매 사이클 시작!")
        print("="*60)
        
        await self.telegram.send_message(
            f"<b>[5/5] 자동매매 시작!</b>\n\n"
            f"<b>시작 시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"<b>매매 간격:</b> 5초\n"
            f"<b>모드:</b> {'모의투자' if self.account_type == 'MOCK' else '실전투자'}"
        )
        
        try:
            # 자동매매 메인 사이클 시작
            cycle_count = 0
            logger.info(f"자동매매 루프 시작 - is_running: {self.is_running}, stop_requested: {self.stop_requested}")
            print(f"자동매매 루프 시작 - is_running: {self.is_running}, stop_requested: {self.stop_requested}")
            
            while self.is_running and not self.stop_requested:  # 제한 없이 계속 실행
                now = datetime.now()
                current_time = now.strftime('%H:%M:%S')
                logger.info(f"[{current_time}] 매매 사이클 {cycle_count + 1} 시작")
                
                # 파일 기반 중단 신호 확인 (Claude CLI 환경 호환)
                stop_action = self.keyboard_handler.check_stop_signals()
                if stop_action == 'SAFE_STOP':
                    termination_reason = "FILE_SIGNAL_SAFE_STOP"
                    if cfg.is_termination_reason_logging_enabled():
                        logger.info(f"[TERMINATION] 사유: {termination_reason}")
                        logger.info(f"[{current_time}] [STOP-DEBUG] File-based safe stop detected in main trading cycle")
                    
                    logger.info(f"[{current_time}] File-based safe stop request - Auto trading will stop and return to Main")
                    await self.telegram.send_message(
                        f"자동매매 중단 알림\n\n"
                        f"중단 시각: {current_time}\n"
                        f"중단 사유: 파일 기반 안전 중단\n"
                        f"종료 방식: Main 메뉴로 복귀"
                    )
                    self.stop_requested = True
                    self.is_running = False
                    # 파일 핸들러 즉시 정리하여 중복 처리 방지
                    self.keyboard_handler.stop_listening()
                    break
                elif stop_action == 'FORCE_EXIT':
                    termination_reason = "FILE_SIGNAL_FORCE_EXIT"
                    if cfg.is_termination_reason_logging_enabled():
                        logger.info(f"[TERMINATION] 사유: {termination_reason}")
                        logger.info(f"[{current_time}] [STOP-DEBUG] File-based force exit detected in main trading cycle")
                    
                    logger.info(f"[{current_time}] File-based force exit request - Safe return to Main")
                    await self.telegram.send_message(
                        f"자동매매 강제 종료 알림\n\n"
                        f"종료 시각: {current_time}\n"
                        f"종료 사유: 파일 기반 강제 종료\n"
                        f"종료 방식: Main 메뉴로 안전 복귀"
                    )
                    self.stop_requested = True
                    self.is_running = False
                    # 파일 핸들러 즉시 정리
                    self.keyboard_handler.stop_listening()
                    # 안전한 종료 (Main으로 복귀)
                    break
                
                # 기존 중단 요청 체크 (호환성 유지)
                if self.stop_requested:
                    termination_reason = "USER_STOP_REQUEST"
                    if cfg.is_termination_reason_logging_enabled():
                        logger.info(f"[TERMINATION] 사유: {termination_reason}")
                    
                    logger.info(f"[{current_time}] 사용자 중단 요청 감지 - 자동매매 종료")
                    await self.telegram.send_message(
                        f"자동매매 사용자 중단 알림\n\n"
                        f"중단 시각: {current_time}\n"
                        f"중단 사유: 사용자 중단 요청\n"
                        f"종료 방식: 안전한 종료"
                    )
                    break
                
                # 장 마감 시간 체크 (MarketCloseController 사용)
                from support.market_close_controller import get_market_close_controller
                
                market_controller = get_market_close_controller()
                
                # 장마감 체크가 활성화된 경우에만 실행
                if market_controller.is_market_close_check_enabled():
                    current_time = datetime.now().time()
                    
                    # 가드 모드 진입 체크
                    if market_controller.should_enter_guard_mode(current_time) and not getattr(self, "_guard_announced", False):
                        self._guard_announced = True
                        self.allow_new_entry = False
                        
                        remaining_time = market_controller.get_time_until_close(current_time)
                        logger.info(f"마감 {market_controller.guard_minutes}분 전 — 신규 진입 금지")
                        
                        try:
                            await self.telegram.send_message(
                                f"장 마감 임박 알림\n\n"
                                f"현재 시각: {datetime.now().strftime('%H:%M:%S')}\n"
                                f"설정 마감: {market_controller.market_close_time.strftime('%H:%M')}\n"
                                f"남은 시간: {remaining_time['formatted']}\n"
                                f"신규 진입 금지 - 포지션 관리 모드"
                            )
                        except Exception:
                            pass
                    
                    # 매매 종료 체크
                    if market_controller.should_stop_trading(current_time):
                        logger.info(f"장 마감({market_controller.market_close_time.strftime('%H:%M')}) 도달 — 자동매매 종료")
                        
                        # 매매 리포트 생성
                        trading_stats = {
                            "total_trades": getattr(self, 'total_trades', 0),
                            "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "account_type": getattr(self, 'account_type', 'SIMPLE')
                        }
                        
                        report_path = await market_controller.generate_trading_report(
                            getattr(self, 'account_type', 'SIMPLE'), 
                            'SimpleAutoTrader',
                            trading_stats
                        )
                        
                        try:
                            await self.telegram.send_message(
                                f"장 마감으로 인한 자동매매 종료\n\n"
                                f"종료 시각: {datetime.now().strftime('%H:%M:%S')}\n"
                                f"설정 마감: {market_controller.market_close_time.strftime('%H:%M')}\n"
                                f"매매 리포트: {report_path if report_path else '생성 실패'}\n"
                                f"안전하게 종료되었습니다."
                            )
                        except Exception:
                            pass
                        
                        # 포지션 정리 후 종료
                        self.stop_requested = True
                        self.is_running = False
                    self.keyboard_handler.stop_listening()
                    break
                
                # 기존 조건 체크 로직 완전 제거 - 바로 자동매매 실행
                # 급등주 스크리닝과 잔고 처리는 1단계에서 이미 완료됨
                
                logger.info(f"[{current_time}] 매매 사이클 {cycle_count + 1}회차 시작")
                
                # premarket_liquidation_done 변수 초기화
                premarket_liquidation_done = False
                
                # 매매 사이클 시작 텔레그램 알림
                await self.telegram.send_message(
                    f"<b>매매 사이클 {cycle_count + 1} 시작</b>\n\n"
                    f"<b>시간:</b> {current_time}\n"
                    f"<b>모드:</b> {'모의투자' if self.account_type == 'MOCK' else '실전투자'}\n"
                    f"<b>간격:</b> 5초"
                )
                
                logger.info(f"[{current_time}] 자동매매 사이클 시작!")
                print(f"\n={'='*60}")
                print(f"[{current_time}] === 매매 사이클 {cycle_count + 1} 시작 ===")
                print(f"{'='*60}")
                
                # 매매 사이클 실행
                try:
                    if self.skip_market_hours:
                        logger.info(f"[{current_time}] 시간체크 스킵 모드 - 매매 사이클 시작")
                        print(f"[{current_time}] 시간체크 스킵 모드 - 매매 사이클 시작")
                    else:
                        logger.info(f"[{current_time}] 일반 매매 시간 - 매매 사이클 시작")
                        print(f"[{current_time}] 일반 매매 시간 - 매매 사이클 시작")
                    
                    await self.trading_cycle()
                    
                    logger.info(f"[{current_time}] 매매 사이클 완료")
                    print(f"[{current_time}] 매매 사이클 완료")
                    
                    # 사이클 완료 텔레그램 알림
                    await self.telegram.send_message(
                        f"<b>매매 사이클 {cycle_count + 1} 완료</b>\n\n"
                        f"<b>완료 시간:</b> {datetime.now().strftime('%H:%M:%S')}\n"
                        f"다음 사이클까지 5초 대기"
                    )
                    
                    # 테스트용 짧은 간격 사용
                    sleep_interval = 5  # 5초로 단축 (테스트용)
                    logger.info(f"[{current_time}] {sleep_interval}초 후 다음 매매 사이클")
                    print(f"[{current_time}] {sleep_interval}초 후 다음 매매 사이클")
                    
                    # 파일 신호 체크하면서 대기
                    for i in range(sleep_interval):
                        if self.stop_requested or not self.is_running:
                            break
                        
                        # 매초마다 파일 신호 체크
                        stop_action = self.keyboard_handler.check_stop_signals()
                        if stop_action in ['SAFE_STOP', 'FORCE_EXIT']:
                            logger.info(f"[{current_time}] [STOP-DEBUG] Stop signal '{stop_action}' detected during trading wait")
                            logger.info(f"[{current_time}] 파일 신호로 중단 요청")
                            self.stop_requested = True
                            self.is_running = False
                            break
                        
                        await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"trading_cycle 실행 중 오류: {e}")
                    print(f"[ERROR] trading_cycle 실행 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    # 오류가 발생해도 계속 실행
                    await asyncio.sleep(30)  # 30초 대기 후 재시도
                
                # 사이클 카운트 증가 (루프 끝에서)
                cycle_count += 1
                
        except KeyboardInterrupt:
            logger.info("사용자가 자동매매를 중지했습니다")
            print("사용자가 자동매매를 중지했습니다")
        except Exception as e:
            import traceback
            logger.error(f"자동매매 실행 중 오류: {e}")
            logger.error(f"오류 상세: {traceback.format_exc()}")
            print(f"[ERROR] 자동매매 실행 중 오류 발생: {e}")
            print(f"오류 상세:\n{traceback.format_exc()}")
        finally:
            logger.info(f"자동매매 종료 - cycle_count: {cycle_count if 'cycle_count' in locals() else 'N/A'}")
            print(f"자동매매 종료 - 실행된 사이클: {cycle_count if 'cycle_count' in locals() else 0}회")
            self.is_running = False
            # 조용한 종료 - 불필요한 메시지 제거
            try:
                if hasattr(self, 'keyboard_handler') and self.keyboard_handler._is_monitoring:
                    self.keyboard_handler.stop_listening()
                    self.keyboard_handler.reset()
            except:
                pass
            try:
                if hasattr(self, 'telegram'):
                    await self.telegram.close()
            except:
                pass
    
    async def execute_sequential_buying(self, stocks_to_buy: List, available_cash: float):
        """순차 매수 실행 (1주씩 순서대로)"""
        try:
            logger.info(f"순차 매수 시작: {len(stocks_to_buy)}개 종목, 예수금: {available_cash:,.0f}원")
            
            remaining_cash = available_cash
            successful_buys = 0
            failed_buys = 0
            
            for user_stock in stocks_to_buy:
                try:
                    # 실패한 종목 체크
                    if self.is_stock_failed(user_stock.symbol):
                        logger.debug(f"순차 매수 - 임시 제외된 종목 건너뛰기: {user_stock.name}({user_stock.symbol})")
                        failed_buys += 1
                        continue
                    
                    # 현재가 조회
                    price_data = self.api.get_stock_price(user_stock.symbol)
                    if not price_data or price_data.get('rt_cd') != '0':
                        logger.warning(f"순차 매수 - 가격 조회 실패: {user_stock.name}({user_stock.symbol})")
                        self.add_failed_stock(user_stock.symbol, "순차매수 - 가격 조회 실패")
                        failed_buys += 1
                        continue
                    
                    current_price = float(price_data.get('output', {}).get('stck_prpr', 0))
                    if current_price <= 0:
                        logger.warning(f"순차 매수 - 유효하지 않은 가격: {user_stock.name}({user_stock.symbol})")
                        self.add_failed_stock(user_stock.symbol, "순차매수 - 유효하지 않은 가격")
                        # 계속해서 같은 종목을 시도하지 않도록 건너뛰기
                        continue
                        failed_buys += 1
                        continue
                    
                    # 1주 매수 비용 계산
                    required_amount = int(current_price * 1.002)  # 1주 + 수수료
                    
                    # 예수금 확인
                    if remaining_cash < required_amount:
                        logger.warning(f"순차 매수 중단: {user_stock.name}({user_stock.symbol}) "
                                     f"필요: {required_amount:,.0f}원 > 잔여: {remaining_cash:,.0f}원")
                        failed_buys += 1
                        break  # 더 이상 매수 불가능
                    
                    # 1주 매수 실행
                    logger.info(f"순차 매수 시도: {user_stock.name}({user_stock.symbol}) "
                               f"1주 @ {current_price:,}원 (비용: {required_amount:,}원)")
                    
                    success = await self.buy_user_designated_stock_single(user_stock, current_price, 1)
                    
                    if success:
                        successful_buys += 1
                        remaining_cash -= required_amount
                        logger.info(f"순차 매수 성공: {user_stock.name}({user_stock.symbol}) "
                                   f"1주, 잔여: {remaining_cash:,.0f}원")
                    else:
                        failed_buys += 1
                        logger.warning(f"순차 매수 실패: {user_stock.name}({user_stock.symbol})")
                    
                    # Rate limit 준수
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"순차 매수 처리 중 오류: {user_stock.symbol} - {e}")
                    failed_buys += 1
                    continue
            
            logger.info(f"순차 매수 완료: 성공 {successful_buys}개, 실패 {failed_buys}개, "
                       f"사용: {available_cash - remaining_cash:,.0f}원, 잔여: {remaining_cash:,.0f}원")
                       
        except Exception as e:
            logger.error(f"순차 매수 실행 실패: {e}")
    
    async def buy_user_designated_stock_single(self, user_stock, current_price: float, quantity: int = 1):
        """사용자 지정종목 단일 수량 매수 (순차 매수용)"""
        try:
            # 추매 여부 확인
            is_additional_buy = user_stock.current_quantity > 0
            buy_reason = "추매" if is_additional_buy else "신규매수"
            
            # 매수 주문
            result = self.api.buy_order(
                stock_code=user_stock.symbol,
                quantity=quantity,
                price=0,  # 시장가
                order_type="MARKET"
            )
            
            if result and result.get('rt_cd') == '0':
                logger.info(f"순차 매수 성공: {user_stock.name}({user_stock.symbol}) {quantity}주 ({buy_reason})")
                print(f"[순차 매수] {user_stock.name} {quantity}주 @ {current_price:,}원")
                
                # 포지션 정보 업데이트
                self.user_stock_manager.update_position_info(
                    user_stock.symbol, quantity, current_price, "buy"
                )
                
                # 내부 포지션 업데이트
                if user_stock.symbol in self.positions:
                    old_position = self.positions[user_stock.symbol]
                    total_quantity = old_position['quantity'] + quantity
                    total_cost = (old_position['avg_price'] * old_position['quantity']) + (current_price * quantity)
                    new_avg_price = total_cost / total_quantity
                    
                    self.positions[user_stock.symbol].update({
                        'quantity': total_quantity,
                        'avg_price': new_avg_price,
                        'user_designated': True
                    })
                else:
                    self.positions[user_stock.symbol] = {
                        'name': user_stock.name,
                        'quantity': quantity,
                        'entry_price': current_price,
                        'avg_price': current_price,
                        'entry_time': datetime.now(),
                        'user_designated': True,
                        'algorithm': 'user_designated'
                    }
                
                return True
            else:
                error_msg = result.get('msg1', '알 수 없는 오류') if result else '주문 실패'
                logger.error(f"순차 매수 실패: {user_stock.name}({user_stock.symbol}) - {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"순차 매수 처리 실패: {user_stock.symbol} - {e}")
            return False
    
    async def buy_user_designated_stock(self, user_stock):
        """사용자 지정종목 매수 실행 (신규매수/추매 통합)"""
        try:
            # 실패한 종목 체크
            if self.is_stock_failed(user_stock.symbol):
                logger.debug(f"임시 제외된 종목 건너뛰기: {user_stock.name}({user_stock.symbol})")
                return False
            
            # 이미 보유 중인 종목인지 확인 (positions를 통한 다중 방어)
            if user_stock.symbol in self.positions:
                logger.debug(f"이미 보유 중인 종목 건너뛰기: {user_stock.name}({user_stock.symbol})")
                return False
            
            # 현재가 조회
            price_data = self.api.get_stock_price(user_stock.symbol)
            if not price_data or price_data.get('rt_cd') != '0':
                logger.warning(f"가격 조회 실패: {user_stock.name}({user_stock.symbol})")
                self.add_failed_stock(user_stock.symbol, "가격 조회 실패")  # 실패 목록에 추가
                return False
            
            current_price = float(price_data.get('output', {}).get('stck_prpr', 0))
            if current_price <= 0:
                logger.warning(f"유효하지 않은 가격: {user_stock.name}({user_stock.symbol})")
                self.add_failed_stock(user_stock.symbol, "유효하지 않은 가격")  # 실패 목록에 추가
                return False  # 오류 발생 시 즉시 종료
                return False
            
            # 잔고 확인
            balance_info = self.api.get_account_balance()
            if not balance_info:
                logger.warning("계좌 잔고 조회 실패")
                return False
            
            available_cash = int(balance_info.get('ord_psbl_cash', 0))
            
            # 추매 여부 확인
            is_additional_buy = user_stock.current_quantity > 0
            buy_reason = "추매" if is_additional_buy else "신규매수"
            
            # 7% 원칙 적용 (추매 구분) - 순차 매수 모드에서는 1주만
            is_sequential_mode = self.user_stock_manager.is_sequential_buying_mode(available_cash)
            buy_quantity = self.user_stock_manager.apply_seven_percent_rule(
                user_stock.symbol, available_cash, current_price, is_additional_buy, force_single_share=is_sequential_mode
            )
            
            if buy_quantity <= 0:
                logger.info(f"{buy_reason} 불가: {user_stock.name}({user_stock.symbol}) "
                           f"가격: {current_price:,}원, 예수금: {available_cash:,}원")
                return False
            
            # 수수료 및 마진 고려
            margin_rate = 1.002
            required_amount = int(current_price * buy_quantity * margin_rate)
            
            # 최종 잔고 확인
            if available_cash < required_amount:
                logger.info(f"최종 잔고 부족: {user_stock.name}({user_stock.symbol}) "
                           f"필요: {required_amount:,}원, 보유: {available_cash:,}원")
                return False
            
            # 추매 정보 로깅
            if is_additional_buy:
                drop_rate = (user_stock.avg_price - current_price) / user_stock.avg_price * 100
                logger.info(f"추매 조건: {user_stock.name}({user_stock.symbol}) "
                           f"평균가 {user_stock.avg_price:,.0f}원 → 현재가 {current_price:,.0f}원 "
                           f"({drop_rate:.1f}% 하락)")
            
            # 매수 주문
            logger.info(f"사용자 지정종목 {buy_reason} 시도: {user_stock.name}({user_stock.symbol}) "
                       f"{buy_quantity}주 @ {current_price:,}원 (총 {required_amount:,}원)")
            
            result = self.api.buy_order(
                stock_code=user_stock.symbol,
                quantity=buy_quantity,
                price=0,  # 시장가
                order_type="MARKET"
            )
            
            if result and result.get('rt_cd') == '0':
                logger.info(f"사용자 지정종목 {buy_reason} 성공: {user_stock.name}({user_stock.symbol}) {buy_quantity}주")
                
                # 포지션 정보 업데이트 (사용자 지정종목 관리자)
                self.user_stock_manager.update_position_info(
                    user_stock.symbol, buy_quantity, current_price, "buy"
                )
                
                # 추매 알림 전송
                if is_additional_buy:
                    try:
                        buy_info = self.user_stock_manager.get_additional_buy_info(user_stock.symbol)
                        if buy_info:
                            await self.user_stock_manager.send_additional_buy_notification(
                                user_stock.symbol, buy_info, buy_quantity
                            )
                    except Exception as e:
                        logger.error(f"추매 알림 전송 실패: {e}")
                
                # 내부 포지션에도 추가 (자동매도 방지)
                if user_stock.symbol in self.positions:
                    # 이미 있는 포지션에 추가
                    old_position = self.positions[user_stock.symbol]
                    total_quantity = old_position['quantity'] + buy_quantity
                    total_cost = (old_position['avg_price'] * old_position['quantity']) + (current_price * buy_quantity)
                    new_avg_price = total_cost / total_quantity
                    
                    self.positions[user_stock.symbol].update({
                        'quantity': total_quantity,
                        'avg_price': new_avg_price,
                        'user_designated': True
                    })
                    logger.info(f"포지션 업데이트: {user_stock.name}({user_stock.symbol}) "
                               f"총 {total_quantity}주, 평균가: {new_avg_price:,.0f}원")
                else:
                    # 새 포지션 생성
                    self.positions[user_stock.symbol] = {
                        'name': user_stock.name,
                        'quantity': buy_quantity,
                        'entry_price': current_price,
                        'avg_price': current_price,  # 평균가 필드 추가
                        'entry_time': datetime.now(),
                        # 사용자 지정종목은 -5% 손절만 적용, 익절 없음 (사용자 판단)
                        'user_designated': True  # 사용자 지정종목 표시
                    }
                
                # 텔레그램 알림
                if self.telegram:
                    try:
                        await self.telegram.send_order_result(
                            user_stock.symbol, "매수 (사용자지정)", buy_quantity,
                            current_price, "성공", balance_info=balance_info, api_connector=self.api
                        )
                    except Exception as e:
                        logger.warning(f"텔레그램 알림 실패: {e}")
                
                return True
            else:
                # 장 종료 메시지 체크
                error_msg = result.get('msg1', '') if result else ''
                if '장종료' in error_msg or '장마감' in error_msg:
                    logger.info("장이 종료되었습니다.")
                else:
                    logger.error(f"사용자 지정종목 매수 실패: {user_stock.name}({user_stock.symbol}) - {result}")
                return False
                
        except Exception as e:
            logger.error(f"사용자 지정종목 매수 중 오류: {user_stock.symbol} - {e}")
            return False
    
    def stop(self):
        """자동매매 중지"""
        self.is_running = False
    
    async def _collect_market_data_for_interval(self) -> Dict[str, Any]:
        """동적 간격 계산을 위한 시장 데이터 수집"""
        try:
            # 현재 보유 종목들의 시장 데이터 수집
            market_data = {
                'price_change_rate': 0.0,
                'volume_ratio': 1.0,
                'vi_triggered': False
            }
            
            if len(self.positions) > 0:
                total_change_rate = 0.0
                valid_positions = 0
                
                for symbol, position in self.positions.items():
                    try:
                        # 현재가 조회
                        price_data = self.api.get_stock_price(symbol)
                        if price_data and price_data.get('rt_cd') == '0':
                            output = price_data.get('output', {})
                            current_price = float(output.get('stck_prpr', 0))
                            change_rate = float(output.get('prdy_ctrt', 0))  # 전일대비율
                            
                            total_change_rate += abs(change_rate)
                            valid_positions += 1
                            
                            # VI 발동 여부 확인 (임시 조건)
                            if abs(change_rate) >= 30.0:  # 30% 이상 변동시 VI로 간주
                                market_data['vi_triggered'] = True
                                
                    except Exception as e:
                        logger.debug(f"시장 데이터 수집 오류 ({symbol}): {e}")
                        continue
                
                # 평균 변동률 계산
                if valid_positions > 0:
                    market_data['price_change_rate'] = total_change_rate / valid_positions
            
            return market_data
            
        except Exception as e:
            logger.error(f"시장 데이터 수집 실패: {e}")
            return {'price_change_rate': 0.0, 'volume_ratio': 1.0, 'vi_triggered': False}
    
    async def _smart_sleep_with_signal_check(self, total_seconds: float):
        """파일 신호 체크를 포함한 스마트 대기 (최소 4초 간격 보장)"""
        # 최소 간격 보장
        if total_seconds < 4.0:
            logger.debug(f"최소 간격 보장: {total_seconds:.1f}초 → 4.0초")
            total_seconds = 4.0
        
        sleep_chunk = 1.0  # 1초씩 체크하여 파일 신호 인식률 향상
        total_slept = 0.0
        
        while total_slept < total_seconds and self.is_running and not self.stop_requested:
            # 파일 기반 중단 신호 체크 (매초 체크로 인식률 향상)
            stop_action = self.keyboard_handler.check_stop_signals()
            if stop_action == 'SAFE_STOP':
                logger.info("[STOP-DEBUG] Safe stop signal detected during dynamic interval wait")
                logger.info("동적 간격 대기 중 안전 중단 요청 - 즉시 중단")
                self.stop_requested = True
                self.is_running = False
                self.keyboard_handler.stop_listening()
                return
            elif stop_action == 'FORCE_EXIT':
                logger.info("[STOP-DEBUG] Force exit signal detected during dynamic interval wait")
                logger.info("동적 간격 대기 중 강제 종료 요청 - 안전한 종료")
                self.stop_requested = True
                self.is_running = False
                self.keyboard_handler.stop_listening()
                return  # 함수에서 안전하게 복귀
            
            # 남은 시간과 청크 시간 중 작은 값만큼 대기
            current_sleep = min(sleep_chunk, total_seconds - total_slept)
            await asyncio.sleep(current_sleep)
            total_slept += current_sleep
    
    async def _update_market_condition_analysis(self, market_data: Dict[str, Any]):
        """시장 상황 자동 감지 및 업데이트"""
        try:
            from support.dynamic_interval_controller import MarketCondition
            
            price_change_rate = market_data.get('price_change_rate', 0.0)
            volume_ratio = market_data.get('volume_ratio', 1.0)
            vi_triggered = market_data.get('vi_triggered', False)
            
            current_condition = self.interval_controller.current_market_condition
            new_condition = None
            reason = ""
            
            # 위기 상황 감지 (VI 발동)
            if vi_triggered:
                new_condition = MarketCondition.CRISIS
                reason = "VI(변동성완화장치) 발동"
            
            # 고변동성 감지 (3% 이상 급등락)
            elif price_change_rate >= 3.0:
                new_condition = MarketCondition.VOLATILE
                reason = f"고변동성 감지 ({price_change_rate:.1f}% 변동)"
            
            # 거래량 급증 감지
            elif volume_ratio >= 3.0:
                new_condition = MarketCondition.VOLATILE
                reason = f"거래량 급증 ({volume_ratio:.1f}배)"
            
            # 안정적 상황
            elif price_change_rate < 1.0 and volume_ratio < 1.5:
                new_condition = MarketCondition.STABLE
                reason = "시장 안정화"
            
            # 시장 상황 변경이 필요한 경우
            if new_condition and new_condition != current_condition:
                self.interval_controller.update_market_condition(new_condition, reason)
                
                # 중요한 변화는 로깅
                if new_condition in [MarketCondition.CRISIS, MarketCondition.VOLATILE]:
                    logger.warning(f"시장 상황 변화 감지: {current_condition.value} → {new_condition.value} ({reason})")
                
        except Exception as e:
            logger.error(f"시장 상황 분석 오류: {e}")
    
    async def _notify_special_market_conditions(self, interval_status: Dict[str, Any], market_data: Dict[str, Any]):
        """특별한 시장 상황 알림"""
        try:
            market_condition = interval_status.get('market_condition', 'stable')
            consecutive_losses = interval_status.get('consecutive_losses', 0)
            current_interval = interval_status.get('current_interval', 0)
            
            # 위기 상황 알림
            if market_condition == 'crisis':
                if self.telegram:
                    await self.telegram.send_message(
                        f"<b>위기 상황 감지</b>\n\n"
                        f"• 시장 상황: 위기 모드\n"
                        f"• 매매 간격: {current_interval:.0f}초로 확대\n"
                        f"• VI 발동 또는 급변동 감지\n"
                        f"• 신중한 매매 모드 진입"
                    )
            
            # 연속 손실 알림 (3회 이상)
            elif consecutive_losses >= 3:
                if self.telegram:
                    await self.telegram.send_message(
                        f"<b>연속 손실 알림</b>\n\n"
                        f"• 연속 손실: {consecutive_losses}회\n"
                        f"• 매매 간격: {current_interval:.0f}초로 확대\n"
                        f"• 쿨다운 모드 진입\n"
                        f"• 시장 상황 재분석 필요"
                    )
            
            # 고변동성 알림
            elif market_condition == 'volatile':
                price_change = market_data.get('price_change_rate', 0)
                if price_change >= 5.0:  # 5% 이상 변동시에만 알림
                    if self.telegram:
                        await self.telegram.send_message(
                            f"<b>고변동성 감지</b>\n\n"
                            f"• 평균 변동률: {price_change:.1f}%\n"
                            f"• 매매 간격: {current_interval:.0f}초로 조정\n"
                            f"• 신중한 매매 모드"
                        )
            
        except Exception as e:
            logger.error(f"특별 상황 알림 실패: {e}")