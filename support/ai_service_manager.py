#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
다중 AI 서비스 관리자
- GPT-5, 감성분석, 기술분석 서비스 분리
- 서비스 인스턴스 관리 및 라이프사이클
- 로드 밸런싱 및 헬스체크
- 서비스 간 통신 조율
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import psutil
from contextlib import asynccontextmanager

from .event_bus_system import EventBusSystem, EventType, Event, Priority
from .gpt5_decision_engine import GPT5DecisionEngine
from .integrated_news_analyzer import IntegratedNewsAnalyzer
try:
    from .kobert_sentiment_analyzer import KoFinBERTAnalyzer as KoBERTSentimentAnalyzer
except ImportError:
    # Fallback for testing
    KoBERTSentimentAnalyzer = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    """서비스 상태"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    ERROR = "error"

class ServiceType(Enum):
    """서비스 타입"""
    GPT_DECISION = "gpt_decision"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    TECHNICAL_ANALYSIS = "technical_analysis"
    NEWS_ANALYSIS = "news_analysis"
    MARKET_DATA = "market_data"

@dataclass
class ServiceMetrics:
    """서비스 메트릭"""
    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    avg_response_time: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    last_health_check: Optional[datetime] = None
    uptime_seconds: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if self.requests_total == 0:
            return 0.0
        return self.requests_success / self.requests_total
    
    @property
    def error_rate(self) -> float:
        return 1.0 - self.success_rate

class AIService(ABC):
    """AI 서비스 추상 클래스"""
    
    def __init__(self, service_id: str, service_type: ServiceType):
        self.service_id = service_id
        self.service_type = service_type
        self.status = ServiceStatus.INITIALIZING
        self.metrics = ServiceMetrics()
        self.start_time = time.time()
        self.event_bus: Optional[EventBusSystem] = None
        self.config: Dict[str, Any] = {}
    
    @abstractmethod
    async def initialize(self) -> bool:
        """서비스 초기화"""
        pass
    
    @abstractmethod
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """요청 처리"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """헬스체크"""
        pass
    
    async def shutdown(self):
        """서비스 종료"""
        self.status = ServiceStatus.STOPPED
        logger.info(f"서비스 종료: {self.service_id}")
    
    def set_event_bus(self, event_bus: EventBusSystem):
        """이벤트 버스 설정"""
        self.event_bus = event_bus
    
    def update_metrics(self, success: bool, response_time: float):
        """메트릭 업데이트"""
        self.metrics.requests_total += 1
        if success:
            self.metrics.requests_success += 1
        else:
            self.metrics.requests_failed += 1
        
        # 응답시간 이동평균
        total_requests = self.metrics.requests_total
        self.metrics.avg_response_time = (
            (self.metrics.avg_response_time * (total_requests - 1) + response_time) 
            / total_requests
        )
        
        # 시스템 리소스 업데이트
        process = psutil.Process()
        self.metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        self.metrics.cpu_usage_percent = process.cpu_percent()
        self.metrics.uptime_seconds = time.time() - self.start_time

class GPTDecisionService(AIService):
    """GPT 기반 매매 결정 서비스"""
    
    def __init__(self, service_id: str = "gpt_decision_service"):
        super().__init__(service_id, ServiceType.GPT_DECISION)
        self.decision_engine: Optional[GPT5DecisionEngine] = None
    
    async def initialize(self) -> bool:
        try:
            # GPT-5 결정 엔진 초기화
            self.decision_engine = GPT5DecisionEngine()
            self.status = ServiceStatus.RUNNING
            logger.info(f"GPT 결정 서비스 초기화 완료: {self.service_id}")
            return True
        except Exception as e:
            self.status = ServiceStatus.ERROR
            logger.error(f"GPT 결정 서비스 초기화 실패: {e}")
            return False
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        try:
            market_context = request.get('market_context')
            trading_rules = request.get('trading_rules')
            
            decision = await self.decision_engine.make_decision(market_context, trading_rules)
            
            response_time = time.time() - start_time
            self.update_metrics(True, response_time)
            
            return {
                'success': True,
                'decision': decision.to_dict(),
                'response_time': response_time
            }
        except Exception as e:
            response_time = time.time() - start_time
            self.update_metrics(False, response_time)
            logger.error(f"GPT 결정 처리 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'response_time': response_time
            }
    
    async def health_check(self) -> bool:
        try:
            # 간단한 테스트 요청
            test_context = {
                'symbol': 'TEST',
                'current_price': 100000,
                'technical_indicators': {'rsi': 50}
            }
            
            result = await self.process_request({'market_context': test_context})
            is_healthy = result['success']
            
            self.metrics.last_health_check = datetime.now()
            if not is_healthy:
                self.status = ServiceStatus.DEGRADED
            
            return is_healthy
        except Exception as e:
            logger.error(f"GPT 서비스 헬스체크 실패: {e}")
            self.status = ServiceStatus.ERROR
            return False

class SentimentAnalysisService(AIService):
    """감성분석 서비스"""
    
    def __init__(self, service_id: str = "sentiment_analysis_service"):
        super().__init__(service_id, ServiceType.SENTIMENT_ANALYSIS)
        self.news_analyzer: Optional[IntegratedNewsAnalyzer] = None
        self.kobert_analyzer: Optional[KoBERTSentimentAnalyzer] = None
    
    async def initialize(self) -> bool:
        try:
            # 뉴스 분석기 초기화
            self.news_analyzer = IntegratedNewsAnalyzer()
            self.kobert_analyzer = KoBERTSentimentAnalyzer()
            
            self.status = ServiceStatus.RUNNING
            logger.info(f"감성분석 서비스 초기화 완료: {self.service_id}")
            return True
        except Exception as e:
            self.status = ServiceStatus.ERROR
            logger.error(f"감성분석 서비스 초기화 실패: {e}")
            return False
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        try:
            text_data = request.get('text_data', [])
            symbol = request.get('symbol')
            
            # 병렬 감성분석
            tasks = []
            if self.news_analyzer:
                tasks.append(self.news_analyzer.analyze_sentiment(text_data))
            if self.kobert_analyzer and symbol:
                tasks.append(self.kobert_analyzer.analyze_stock_sentiment(symbol, text_data))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 통합
            sentiment_scores = {}
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"감성분석 오류 {i}: {result}")
                    continue
                sentiment_scores.update(result)
            
            response_time = time.time() - start_time
            self.update_metrics(True, response_time)
            
            return {
                'success': True,
                'sentiment_scores': sentiment_scores,
                'response_time': response_time
            }
        except Exception as e:
            response_time = time.time() - start_time
            self.update_metrics(False, response_time)
            logger.error(f"감성분석 처리 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'response_time': response_time
            }
    
    async def health_check(self) -> bool:
        try:
            # 테스트 데이터로 헬스체크
            test_request = {
                'text_data': ['좋은 뉴스입니다', '나쁜 소식입니다'],
                'symbol': '005930'
            }
            
            result = await self.process_request(test_request)
            is_healthy = result['success']
            
            self.metrics.last_health_check = datetime.now()
            if not is_healthy:
                self.status = ServiceStatus.DEGRADED
            
            return is_healthy
        except Exception as e:
            logger.error(f"감성분석 서비스 헬스체크 실패: {e}")
            self.status = ServiceStatus.ERROR
            return False

class TechnicalAnalysisService(AIService):
    """기술적 분석 서비스"""
    
    def __init__(self, service_id: str = "technical_analysis_service"):
        super().__init__(service_id, ServiceType.TECHNICAL_ANALYSIS)
    
    async def initialize(self) -> bool:
        try:
            # 기술적 분석 도구 초기화
            self.status = ServiceStatus.RUNNING
            logger.info(f"기술적 분석 서비스 초기화 완료: {self.service_id}")
            return True
        except Exception as e:
            self.status = ServiceStatus.ERROR
            logger.error(f"기술적 분석 서비스 초기화 실패: {e}")
            return False
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        try:
            price_data = request.get('price_data')
            indicators = request.get('indicators', ['rsi', 'macd', 'bollinger_bands'])
            
            # 기술적 지표 계산 (예시)
            technical_indicators = {}
            for indicator in indicators:
                if indicator == 'rsi':
                    # RSI 계산 로직
                    technical_indicators['rsi'] = 50.0  # 예시
                elif indicator == 'macd':
                    # MACD 계산 로직
                    technical_indicators['macd'] = {'macd': 0.1, 'signal': 0.05}
                elif indicator == 'bollinger_bands':
                    # 볼린저 밴드 계산 로직
                    technical_indicators['bollinger_bands'] = {
                        'upper': 105000, 'middle': 100000, 'lower': 95000
                    }
            
            response_time = time.time() - start_time
            self.update_metrics(True, response_time)
            
            return {
                'success': True,
                'technical_indicators': technical_indicators,
                'response_time': response_time
            }
        except Exception as e:
            response_time = time.time() - start_time
            self.update_metrics(False, response_time)
            logger.error(f"기술적 분석 처리 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'response_time': response_time
            }
    
    async def health_check(self) -> bool:
        try:
            # 테스트 데이터로 헬스체크
            test_request = {
                'price_data': [100, 101, 99, 102, 98],
                'indicators': ['rsi']
            }
            
            result = await self.process_request(test_request)
            is_healthy = result['success']
            
            self.metrics.last_health_check = datetime.now()
            if not is_healthy:
                self.status = ServiceStatus.DEGRADED
            
            return is_healthy
        except Exception as e:
            logger.error(f"기술적 분석 서비스 헬스체크 실패: {e}")
            self.status = ServiceStatus.ERROR
            return False

class AIServiceManager:
    """AI 서비스 관리자"""
    
    def __init__(self, event_bus: EventBusSystem):
        self.event_bus = event_bus
        self.services: Dict[str, AIService] = {}
        self.running = False
        self.health_check_interval = 60  # 60초
        self.health_check_task: Optional[asyncio.Task] = None
        self.load_balancer = LoadBalancer()
    
    async def initialize(self):
        """서비스 매니저 초기화"""
        # 기본 서비스들 생성 및 등록
        services = [
            GPTDecisionService(),
            SentimentAnalysisService(),
            TechnicalAnalysisService()
        ]
        
        # 서비스 초기화 및 등록
        init_tasks = []
        for service in services:
            service.set_event_bus(self.event_bus)
            self.services[service.service_id] = service
            init_tasks.append(service.initialize())
        
        # 병렬 초기화
        results = await asyncio.gather(*init_tasks, return_exceptions=True)
        
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"서비스 초기화 실패 {services[i].service_id}: {result}")
            elif result:
                success_count += 1
        
        logger.info(f"AI 서비스 매니저 초기화 완료: {success_count}/{len(services)} 서비스")
        
        # 헬스체크 태스크 시작
        self.running = True
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        
        return success_count > 0
    
    async def shutdown(self):
        """서비스 매니저 종료"""
        self.running = False
        
        if self.health_check_task:
            self.health_check_task.cancel()
        
        # 모든 서비스 종료
        shutdown_tasks = [service.shutdown() for service in self.services.values()]
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        logger.info("AI 서비스 매니저 종료 완료")
    
    @asynccontextmanager
    async def lifespan(self):
        """컨텍스트 매니저"""
        await self.initialize()
        try:
            yield self
        finally:
            await self.shutdown()
    
    async def get_service(self, service_type: ServiceType) -> Optional[AIService]:
        """서비스 인스턴스 조회"""
        available_services = [
            service for service in self.services.values()
            if service.service_type == service_type and service.status == ServiceStatus.RUNNING
        ]
        
        if not available_services:
            return None
        
        # 로드 밸런싱
        return self.load_balancer.select_service(available_services)
    
    async def process_ai_request(
        self, 
        service_type: ServiceType, 
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """AI 요청 처리"""
        service = await self.get_service(service_type)
        if not service:
            return {
                'success': False,
                'error': f'사용 가능한 {service_type.value} 서비스 없음'
            }
        
        return await service.process_request(request)
    
    async def _health_check_loop(self):
        """헬스체크 루프"""
        while self.running:
            try:
                # 모든 서비스 헬스체크 (병렬 처리)
                health_tasks = [
                    service.health_check() 
                    for service in self.services.values()
                ]
                
                results = await asyncio.gather(*health_tasks, return_exceptions=True)
                
                # 결과 분석
                unhealthy_services = []
                for i, (service_id, result) in enumerate(zip(self.services.keys(), results)):
                    if isinstance(result, Exception) or not result:
                        unhealthy_services.append(service_id)
                
                if unhealthy_services:
                    logger.warning(f"비정상 서비스: {unhealthy_services}")
                    
                    # 위험 알림 이벤트 발행
                    alert_event = await self.event_bus.create_event(
                        event_type=EventType.SYSTEM_STATUS,
                        source_service="ai_service_manager",
                        payload={
                            'status': 'degraded',
                            'unhealthy_services': unhealthy_services
                        },
                        priority=Priority.HIGH
                    )
                    await self.event_bus.publish(alert_event)
                
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"헬스체크 루프 오류: {e}")
                await asyncio.sleep(10)
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """시스템 전체 메트릭"""
        service_metrics = {}
        total_requests = 0
        total_success = 0
        avg_response_times = []
        
        for service_id, service in self.services.items():
            metrics = service.metrics
            service_metrics[service_id] = {
                'status': service.status.value,
                'requests_total': metrics.requests_total,
                'success_rate': metrics.success_rate,
                'avg_response_time': metrics.avg_response_time,
                'memory_usage_mb': metrics.memory_usage_mb,
                'cpu_usage_percent': metrics.cpu_usage_percent,
                'uptime_seconds': metrics.uptime_seconds
            }
            
            total_requests += metrics.requests_total
            total_success += metrics.requests_success
            if metrics.avg_response_time > 0:
                avg_response_times.append(metrics.avg_response_time)
        
        return {
            'services': service_metrics,
            'summary': {
                'total_services': len(self.services),
                'running_services': sum(1 for s in self.services.values() 
                                      if s.status == ServiceStatus.RUNNING),
                'total_requests': total_requests,
                'overall_success_rate': total_success / total_requests if total_requests > 0 else 0,
                'avg_response_time': sum(avg_response_times) / len(avg_response_times) 
                                   if avg_response_times else 0
            }
        }

class LoadBalancer:
    """간단한 로드 밸런서"""
    
    def __init__(self):
        self.round_robin_counters = {}
    
    def select_service(self, services: List[AIService]) -> AIService:
        """라운드 로빈 방식으로 서비스 선택"""
        if not services:
            raise ValueError("사용 가능한 서비스 없음")
        
        service_type = services[0].service_type
        
        # 라운드 로빈 카운터 초기화
        if service_type not in self.round_robin_counters:
            self.round_robin_counters[service_type] = 0
        
        # 다음 서비스 선택
        index = self.round_robin_counters[service_type] % len(services)
        self.round_robin_counters[service_type] += 1
        
        return services[index]

async def create_ai_service_manager(event_bus: EventBusSystem) -> AIServiceManager:
    """AI 서비스 매니저 생성 및 초기화"""
    manager = AIServiceManager(event_bus)
    await manager.initialize()
    return manager