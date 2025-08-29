#!/usr/bin/env python3
"""
백그라운드 급등종목 수집 시스템
장 개장 30분 전부터 급등종목 수집 및 기존 보유종목 매도 분석
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys
import json

# 프로젝트 루트 경로 추가
sys.path.append(str(Path(__file__).parent.parent))

from support.unified_cycle_manager import get_step_delay_manager
from support.api_connector import KISAPIConnector
from support.telegram_notifier import TelegramNotifier

# 로깅 설정
from support.log_manager import get_log_manager

# 깔끔한 콘솔 로거 사용
from support.clean_console_logger import (
    get_clean_logger, Phase, log as clean_log
)

# 로그 매니저를 통한 로거 설정
log_manager = get_log_manager()
logger = log_manager.setup_logger('system', __name__)


class PremarketDataCollector:
    """장 개장 전 급등종목 수집 및 보유종목 분석 시스템"""
    
    def __init__(self, account_type: str = "REAL"):
        """
        초기화
        
        Args:
            account_type: 계좌 유형 ("REAL" 또는 "MOCK")
        """
        self.account_type = account_type
        self.is_running = False
        self.collection_start_time = "08:30:00"  # 8:30 시작
        self.market_open_time = "09:00:00"       # 9:00 장 개장
        self.collection_interval_minutes = 5     # 5분 간격
        
        # 데이터 저장소 (메모리 캐시)
        self.surge_stocks_cache: Dict[str, Any] = {}
        self.holding_analysis_cache: Dict[str, Any] = {}
        self.market_overview_cache: Dict[str, Any] = {}
        
        # 급등종목 기준
        self.surge_criteria = {
            "volume_ratio_threshold": 2.2,  # 거래량 배수 (≥2.2×V20)
            "price_change_threshold": 3.0,  # 최소 상승률 (3% 이상)
            "min_price": 1000,              # 최소 주가 (1,000원 이상)
            "max_price": 500000,            # 최대 주가 (500,000원 이하)
            "min_market_cap": 100,          # 최소 시가총액 (100억원)
        }
        
        # API 및 알림 시스템
        self.api_connector: Optional[KISAPIConnector] = None
        self.telegram_notifier: Optional[TelegramNotifier] = None
        self.step_delay_manager = get_step_delay_manager(2)
        
        # 수집 통계
        self.collection_stats = {
            "total_collections": 0,
            "surge_stocks_found": 0,
            "holding_analysis_count": 0,
            "api_calls_made": 0,
            "last_collection_time": None,
            "errors_encountered": 0
        }
    
    async def initialize(self) -> bool:
        """시스템 초기화"""
        try:
            # API 커넥터 초기화
            is_mock = (self.account_type == "MOCK")
            self.api_connector = KISAPIConnector(is_mock=is_mock)
            if not await self.api_connector.initialize():
                clean_log("API 커넥터 초기화 실패", "ERROR")
                return False
            
            # 텔레그램 알리미 초기화
            try:
                self.telegram_notifier = TelegramNotifier()
                await self.telegram_notifier.initialize()
            except Exception as e:
                # 텔레그램 초기화 실패 (로그 제거 - 선택사항)
                self.telegram_notifier = None
            
            clean_log("백그라운드 수집 시스템 초기화 완료", "SUCCESS")
            return True
            
        except Exception as e:
            clean_log(f"시스템 초기화 오류: {str(e)[:50]}...", "ERROR")
            return False
    
    def should_start_collection(self) -> bool:
        """수집을 시작해야 하는 시간인지 확인"""
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        
        # 주말은 수집하지 않음
        if now.weekday() >= 5:  # 토요일(5), 일요일(6)
            return False
        
        # 8:30 ~ 9:00 시간대만 수집
        return self.collection_start_time <= current_time < self.market_open_time
    
    def is_market_hours(self) -> bool:
        """현재 장시간인지 확인"""
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        
        # 주말은 장시간 아님
        if now.weekday() >= 5:
            return False
        
        # 9:00 ~ 15:30 장시간
        return "09:00:00" <= current_time <= "15:30:00"
    
    async def run_premarket_collection(self) -> bool:
        """백그라운드 급등종목 수집 메인 루프"""
        if not await self.initialize():
            return False
        
        clean_log("백그라운드 급등종목 수집 시작", "SUCCESS")
        
        # 텔레그램 알림
        if self.telegram_notifier:
            await self.telegram_notifier.send_message(
                "📊 백그라운드 급등종목 수집 시작\n"
                f"⏰ 수집 시간: {self.collection_start_time} ~ {self.market_open_time}\n"
                f"🔄 수집 간격: {self.collection_interval_minutes}분"
            )
        
        self.is_running = True
        
        try:
            while self.is_running:
                current_time = datetime.now()
                
                # 수집 시간대 확인
                if self.should_start_collection():
                    await self._perform_collection_cycle()
                    
                    # 다음 수집까지 대기 (5분 간격)
                    next_collection_time = current_time + timedelta(minutes=self.collection_interval_minutes)
                    wait_seconds = (next_collection_time - datetime.now()).total_seconds()
                    
                    if wait_seconds > 0:
                        # 다음 수집까지 대기 (로그 제거 - 반복 메시지)
                        await asyncio.sleep(wait_seconds)
                
                # 장시간이 되면 수집 종료
                elif self.is_market_hours():
                    clean_log("장시간 시작 - 백그라운드 수집 종료", "INFO")
                    break
                
                else:
                    # 수집 시간이 아니면 1분 후 재확인
                    await asyncio.sleep(60)
            
            return True
            
        except Exception as e:
            clean_log(f"백그라운드 수집 오류: {str(e)[:50]}...", "ERROR")
            return False
        finally:
            self.is_running = False
            await self._send_collection_summary()
    
    async def _perform_collection_cycle(self) -> None:
        """한 번의 수집 사이클 수행"""
        try:
            cycle_start_time = datetime.now()
            # 수집 사이클 시작 (로그 제거 - 반복 메시지)
            
            # 1단계: 급등종목 스캔
            await self._scan_surge_stocks()
            await self.step_delay_manager.delay_between_steps("급등종목 스캔")
            
            # 2단계: 보유종목 분석
            await self._analyze_holding_stocks()
            await self.step_delay_manager.delay_between_steps("보유종목 분석")
            
            # 3단계: 시장 개황 업데이트
            await self._update_market_overview()
            await self.step_delay_manager.delay_between_steps("시장 개황 업데이트")
            
            # 4단계: 알림 발송
            await self._send_collection_alerts()
            
            # 통계 업데이트
            self.collection_stats["total_collections"] += 1
            self.collection_stats["last_collection_time"] = cycle_start_time.strftime('%H:%M:%S')
            
            cycle_end_time = datetime.now()
            cycle_duration = (cycle_end_time - cycle_start_time).total_seconds()
            # 수집 사이클 완료 (로그 제거 - 반복 메시지)
            
        except Exception as e:
            logger.error(f"수집 사이클 오류: {e}")
            self.collection_stats["errors_encountered"] += 1
    
    async def _scan_surge_stocks(self) -> None:
        """급등종목 스캔"""
        try:
            if not self.api_connector:
                logger.warning("API 커넥터가 초기화되지 않음")
                return
            
            # 코스닥 및 코스피 급등종목 조회
            markets = ["KOSPI", "KOSDAQ"]
            all_surge_stocks = []
            
            for market in markets:
                try:
                    # API 호출로 급등종목 조회 (실제 구현 시 API 커넥터 메서드 사용)
                    surge_stocks = await self._get_surge_stocks_from_api(market)
                    
                    if surge_stocks:
                        all_surge_stocks.extend(surge_stocks)
                        logger.info(f"{market} 급등종목 {len(surge_stocks)}개 발견")
                    
                    self.collection_stats["api_calls_made"] += 1
                    
                except Exception as e:
                    logger.error(f"{market} 급등종목 조회 오류: {e}")
            
            # 급등종목 필터링 및 저장
            if all_surge_stocks:
                filtered_stocks = self._filter_surge_stocks(all_surge_stocks)
                await self._update_surge_stocks_cache(filtered_stocks)
                
                self.collection_stats["surge_stocks_found"] += len(filtered_stocks)
                logger.info(f"필터링된 급등종목: {len(filtered_stocks)}개")
            
        except Exception as e:
            logger.error(f"급등종목 스캔 오류: {e}")
    
    async def _get_surge_stocks_from_api(self, market: str) -> List[Dict[str, Any]]:
        """API를 통한 급등종목 조회 (실제 API 연동 필요)"""
        try:
            # 실제 구현 시 API 커넥터의 급등종목 조회 메서드 호출
            # 현재는 모의 데이터 반환
            mock_surge_stocks = [
                {
                    "stock_code": "000001",
                    "stock_name": "급등종목A",
                    "current_price": 15000,
                    "change_rate": 5.2,
                    "volume": 1500000,
                    "volume_ratio": 2.8,
                    "market_cap": 500000000000,
                    "market": market
                }
            ]
            
            return mock_surge_stocks
            
        except Exception as e:
            logger.error(f"{market} 급등종목 API 조회 오류: {e}")
            return []
    
    def _filter_surge_stocks(self, stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """급등종목 필터링"""
        filtered_stocks = []
        
        for stock in stocks:
            try:
                # 기준 조건 확인
                if (stock.get("volume_ratio", 0) >= self.surge_criteria["volume_ratio_threshold"] and
                    stock.get("change_rate", 0) >= self.surge_criteria["price_change_threshold"] and
                    self.surge_criteria["min_price"] <= stock.get("current_price", 0) <= self.surge_criteria["max_price"] and
                    stock.get("market_cap", 0) >= self.surge_criteria["min_market_cap"] * 100000000):  # 억원 단위
                    
                    filtered_stocks.append(stock)
                    
            except Exception as e:
                logger.error(f"종목 필터링 오류 ({stock.get('stock_code', 'Unknown')}): {e}")
        
        return filtered_stocks
    
    async def _update_surge_stocks_cache(self, surge_stocks: List[Dict[str, Any]]) -> None:
        """급등종목 캐시 업데이트"""
        try:
            current_time = datetime.now().strftime('%H:%M:%S')
            
            self.surge_stocks_cache = {
                "timestamp": current_time,
                "stocks": surge_stocks,
                "count": len(surge_stocks),
                "criteria": self.surge_criteria.copy()
            }
            
            logger.info(f"급등종목 캐시 업데이트: {len(surge_stocks)}개")
            
        except Exception as e:
            logger.error(f"급등종목 캐시 업데이트 오류: {e}")
    
    async def _analyze_holding_stocks(self) -> None:
        """보유종목 분석"""
        try:
            if not self.api_connector:
                return
            
            # 보유종목 조회 (API 커넥터 사용)
            holdings = await self._get_holdings_from_api()
            
            if not holdings:
                logger.info("보유종목이 없습니다")
                return
            
            analyzed_holdings = []
            
            for holding in holdings:
                try:
                    # 각 보유종목에 대한 매도 신호 분석
                    analysis = await self._analyze_single_holding(holding)
                    if analysis:
                        analyzed_holdings.append(analysis)
                        
                except Exception as e:
                    logger.error(f"보유종목 분석 오류 ({holding.get('stock_code', 'Unknown')}): {e}")
            
            # 보유종목 분석 결과 캐시 업데이트
            await self._update_holdings_analysis_cache(analyzed_holdings)
            
            self.collection_stats["holding_analysis_count"] += len(analyzed_holdings)
            logger.info(f"보유종목 분석 완료: {len(analyzed_holdings)}개")
            
        except Exception as e:
            logger.error(f"보유종목 분석 오류: {e}")
    
    async def _get_holdings_from_api(self) -> List[Dict[str, Any]]:
        """API를 통한 보유종목 조회"""
        try:
            # 실제 구현 시 API 커넥터의 보유종목 조회 메서드 호출
            # 현재는 모의 데이터 반환
            mock_holdings = [
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 100,
                    "avg_price": 70000,
                    "current_price": 72000,
                    "profit_loss_rate": 2.86
                }
            ]
            
            return mock_holdings
            
        except Exception as e:
            logger.error(f"보유종목 API 조회 오류: {e}")
            return []
    
    async def _analyze_single_holding(self, holding: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """단일 보유종목 분석"""
        try:
            stock_code = holding.get("stock_code")
            current_price = holding.get("current_price", 0)
            avg_price = holding.get("avg_price", 0)
            profit_loss_rate = holding.get("profit_loss_rate", 0)
            
            # 매도 신호 분석 (간단한 기준)
            sell_signal = "HOLD"
            sell_reason = "관망"
            urgency = "LOW"
            
            # 수익률 기반 매도 신호
            if profit_loss_rate >= 10.0:  # 10% 이상 수익
                sell_signal = "STRONG_SELL"
                sell_reason = "고수익 실현"
                urgency = "HIGH"
            elif profit_loss_rate >= 5.0:  # 5% 이상 수익
                sell_signal = "SELL"
                sell_reason = "수익 실현 검토"
                urgency = "MEDIUM"
            elif profit_loss_rate <= -5.0:  # 5% 이상 손실
                sell_signal = "SELL"
                sell_reason = "손절 검토"
                urgency = "MEDIUM"
            elif profit_loss_rate <= -10.0:  # 10% 이상 손실
                sell_signal = "STRONG_SELL"
                sell_reason = "손절 필요"
                urgency = "HIGH"
            
            return {
                "stock_code": stock_code,
                "stock_name": holding.get("stock_name"),
                "analysis_time": datetime.now().strftime('%H:%M:%S'),
                "current_price": current_price,
                "avg_price": avg_price,
                "profit_loss_rate": profit_loss_rate,
                "sell_signal": sell_signal,
                "sell_reason": sell_reason,
                "urgency": urgency,
                "quantity": holding.get("quantity", 0)
            }
            
        except Exception as e:
            logger.error(f"보유종목 개별 분석 오류: {e}")
            return None
    
    async def _update_holdings_analysis_cache(self, analyzed_holdings: List[Dict[str, Any]]) -> None:
        """보유종목 분석 캐시 업데이트"""
        try:
            current_time = datetime.now().strftime('%H:%M:%S')
            
            self.holding_analysis_cache = {
                "timestamp": current_time,
                "holdings": analyzed_holdings,
                "count": len(analyzed_holdings),
                "high_urgency_count": len([h for h in analyzed_holdings if h.get("urgency") == "HIGH"])
            }
            
            logger.info(f"보유종목 분석 캐시 업데이트: {len(analyzed_holdings)}개")
            
        except Exception as e:
            logger.error(f"보유종목 분석 캐시 업데이트 오류: {e}")
    
    async def _update_market_overview(self) -> None:
        """시장 개황 업데이트"""
        try:
            current_time = datetime.now().strftime('%H:%M:%S')
            
            # 시장 지수 정보 수집 (실제 구현 시 API 사용)
            market_data = {
                "timestamp": current_time,
                "kospi": {
                    "current": 2500.0,
                    "change": 15.2,
                    "change_rate": 0.61
                },
                "kosdaq": {
                    "current": 850.0,
                    "change": -8.5,
                    "change_rate": -0.99
                },
                "volume_status": "증가",
                "market_sentiment": "보통"
            }
            
            self.market_overview_cache = market_data
            logger.info("시장 개황 업데이트 완료")
            
        except Exception as e:
            logger.error(f"시장 개황 업데이트 오류: {e}")
    
    async def _send_collection_alerts(self) -> None:
        """수집 결과 알림 발송"""
        try:
            if not self.telegram_notifier:
                return
            
            current_time = datetime.now().strftime('%H:%M:%S')
            
            # 급등종목 알림
            if self.surge_stocks_cache.get("stocks"):
                surge_count = len(self.surge_stocks_cache["stocks"])
                if surge_count > 0:
                    message = f"🔥 급등종목 발견 [{current_time}]\n"
                    message += f"📈 발견 종목: {surge_count}개\n\n"
                    
                    # 상위 3개 종목만 표시
                    for i, stock in enumerate(self.surge_stocks_cache["stocks"][:3]):
                        message += (f"{i+1}. {stock.get('stock_name', 'N/A')} "
                                  f"({stock.get('stock_code', 'N/A')})\n"
                                  f"   💰 {stock.get('current_price', 0):,}원 "
                                  f"(+{stock.get('change_rate', 0):.1f}%)\n"
                                  f"   📊 거래량: {stock.get('volume_ratio', 0):.1f}배\n")
                    
                    await self.telegram_notifier.send_message(message)
            
            # 보유종목 중요 알림
            if self.holding_analysis_cache.get("holdings"):
                high_urgency_holdings = [
                    h for h in self.holding_analysis_cache["holdings"] 
                    if h.get("urgency") == "HIGH"
                ]
                
                if high_urgency_holdings:
                    message = f"⚠️ 보유종목 긴급 알림 [{current_time}]\n\n"
                    for holding in high_urgency_holdings:
                        message += (f"📍 {holding.get('stock_name', 'N/A')}\n"
                                  f"   신호: {holding.get('sell_signal', 'N/A')}\n"
                                  f"   사유: {holding.get('sell_reason', 'N/A')}\n"
                                  f"   수익률: {holding.get('profit_loss_rate', 0):.1f}%\n\n")
                    
                    await self.telegram_notifier.send_message(message)
            
        except Exception as e:
            logger.error(f"알림 발송 오류: {e}")
    
    async def _send_collection_summary(self) -> None:
        """수집 완료 요약 알림"""
        try:
            if not self.telegram_notifier:
                return
            
            message = "📊 백그라운드 수집 완료 요약\n\n"
            message += f"🔄 총 수집 횟수: {self.collection_stats['total_collections']}회\n"
            message += f"🔥 급등종목 발견: {self.collection_stats['surge_stocks_found']}개\n"
            message += f"💼 보유종목 분석: {self.collection_stats['holding_analysis_count']}개\n"
            message += f"📞 API 호출: {self.collection_stats['api_calls_made']}회\n"
            message += f"❌ 오류 발생: {self.collection_stats['errors_encountered']}회\n"
            message += f"⏰ 마지막 수집: {self.collection_stats['last_collection_time']}\n\n"
            message += "💡 장 개장 준비 완료!"
            
            await self.telegram_notifier.send_message(message)
            
        except Exception as e:
            logger.error(f"수집 요약 알림 오류: {e}")
    
    def get_surge_stocks(self) -> Dict[str, Any]:
        """급등종목 캐시 반환"""
        return self.surge_stocks_cache.copy()
    
    def get_holdings_analysis(self) -> Dict[str, Any]:
        """보유종목 분석 캐시 반환"""
        return self.holding_analysis_cache.copy()
    
    def get_market_overview(self) -> Dict[str, Any]:
        """시장 개황 캐시 반환"""
        return self.market_overview_cache.copy()
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """수집 통계 반환"""
        return self.collection_stats.copy()
    
    def stop_collection(self) -> None:
        """수집 중지"""
        self.is_running = False
        logger.info("백그라운드 수집 중지 요청")


# 전역 인스턴스 (싱글톤 패턴)
_premarket_collector: Optional[PremarketDataCollector] = None


def get_premarket_collector(account_type: str = "REAL") -> PremarketDataCollector:
    """백그라운드 수집기 인스턴스 반환 (싱글톤)"""
    global _premarket_collector
    if _premarket_collector is None:
        _premarket_collector = PremarketDataCollector(account_type)
    return _premarket_collector


async def start_premarket_collection(account_type: str = "REAL") -> bool:
    """백그라운드 급등종목 수집 시작"""
    collector = get_premarket_collector(account_type)
    return await collector.run_premarket_collection()


def get_cached_surge_stocks() -> Dict[str, Any]:
    """캐시된 급등종목 반환"""
    global _premarket_collector
    if _premarket_collector:
        return _premarket_collector.get_surge_stocks()
    return {}


def get_cached_holdings_analysis() -> Dict[str, Any]:
    """캐시된 보유종목 분석 반환"""
    global _premarket_collector
    if _premarket_collector:
        return _premarket_collector.get_holdings_analysis()
    return {}


if __name__ == "__main__":
    # 테스트 실행
    async def test_premarket_collector():
        print("=== 백그라운드 급등종목 수집 테스트 ===")
        
        collector = PremarketDataCollector("MOCK")
        
        # 초기화 테스트
        if await collector.initialize():
            print("✅ 초기화 성공")
            
            # 한 번의 수집 사이클 테스트
            await collector._perform_collection_cycle()
            
            # 결과 확인
            surge_stocks = collector.get_surge_stocks()
            holdings_analysis = collector.get_holdings_analysis()
            stats = collector.get_collection_stats()
            
            print(f"급등종목: {surge_stocks}")
            print(f"보유종목 분석: {holdings_analysis}")
            print(f"수집 통계: {stats}")
            
        else:
            print("❌ 초기화 실패")
    
    # 테스트 실행
    asyncio.run(test_premarket_collector())