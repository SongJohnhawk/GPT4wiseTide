#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이벤트 기반 메시징 시스템
- Redis/Apache Kafka 기반 이벤트 버스
- 비동기 메시지 큐 및 이벤트 라우팅
- 다중 AI 서비스 간 통신 관리
- 백프레셔 및 재시도 로직 포함
"""

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import redis.asyncio as aioredis
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EventType(Enum):
    """이벤트 타입 열거형"""
    MARKET_DATA_UPDATE = "market_data_update"
    TRADING_SIGNAL = "trading_signal"
    ORDER_PLACED = "order_placed"
    ORDER_EXECUTED = "order_executed"
    RISK_ALERT = "risk_alert"
    SYSTEM_STATUS = "system_status"
    AI_DECISION_REQUEST = "ai_decision_request"
    AI_DECISION_RESPONSE = "ai_decision_response"
    NEWS_SENTIMENT_UPDATE = "news_sentiment_update"
    TECHNICAL_ANALYSIS_COMPLETE = "technical_analysis_complete"

class Priority(Enum):
    """메시지 우선순위"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class Event:
    """이벤트 메시지 클래스"""
    event_id: str
    event_type: EventType
    timestamp: datetime
    source_service: str
    target_service: Optional[str] = None
    priority: Priority = Priority.NORMAL
    payload: Dict[str, Any] = None
    correlation_id: Optional[str] = None
    retry_count: int = 0
    expires_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.payload is None:
            self.payload = {}
        if self.expires_at is None:
            self.expires_at = self.timestamp + timedelta(hours=1)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['priority'] = self.priority.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """딕셔너리에서 복원"""
        data['event_type'] = EventType(data['event_type'])
        data['priority'] = Priority(data['priority'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if data.get('expires_at'):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        return cls(**data)

class EventHandler(ABC):
    """이벤트 핸들러 추상 클래스"""
    
    @abstractmethod
    async def handle(self, event: Event) -> bool:
        """
        이벤트 처리
        
        Returns:
            bool: 처리 성공 여부
        """
        pass
    
    @property
    @abstractmethod
    def supported_events(self) -> List[EventType]:
        """지원하는 이벤트 타입 목록"""
        pass

class EventBusConfig:
    """이벤트 버스 설정"""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_retries: int = 3,
        retry_delay: float = 1.0,
        batch_size: int = 100,
        max_queue_size: int = 10000,
        enable_dead_letter: bool = True
    ):
        self.redis_url = redis_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.batch_size = batch_size
        self.max_queue_size = max_queue_size
        self.enable_dead_letter = enable_dead_letter

class EventBusSystem:
    """이벤트 기반 메시징 시스템"""
    
    def __init__(self, config: EventBusConfig):
        self.config = config
        self.redis_client: Optional[aioredis.Redis] = None
        self.handlers: Dict[EventType, List[EventHandler]] = {}
        self.running = False
        self.worker_tasks: List[asyncio.Task] = []
        self.metrics = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "events_retried": 0
        }
    
    async def initialize(self):
        """시스템 초기화"""
        try:
            self.redis_client = aioredis.from_url(
                self.config.redis_url,
                decode_responses=True,
                max_connections=20
            )
            await self.redis_client.ping()
            logger.info("EventBus Redis 연결 성공")
        except Exception as e:
            logger.error(f"EventBus 초기화 실패: {e}")
            raise
    
    async def shutdown(self):
        """시스템 종료"""
        self.running = False
        
        # 워커 태스크 종료
        for task in self.worker_tasks:
            task.cancel()
        
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        # Redis 연결 종료
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("EventBus 시스템 종료 완료")
    
    @asynccontextmanager
    async def lifespan(self):
        """컨텍스트 매니저"""
        await self.initialize()
        try:
            yield self
        finally:
            await self.shutdown()
    
    def register_handler(self, handler: EventHandler):
        """이벤트 핸들러 등록"""
        for event_type in handler.supported_events:
            if event_type not in self.handlers:
                self.handlers[event_type] = []
            self.handlers[event_type].append(handler)
        logger.info(f"핸들러 등록: {handler.__class__.__name__} → {handler.supported_events}")
    
    async def publish(self, event: Event) -> bool:
        """이벤트 발행"""
        try:
            if not self.redis_client:
                raise RuntimeError("EventBus가 초기화되지 않음")
            
            # 만료된 이벤트 체크
            if event.expires_at and datetime.now() > event.expires_at:
                logger.warning(f"만료된 이벤트 무시: {event.event_id}")
                return False
            
            # 메시지를 Redis 큐에 추가
            queue_name = f"events:{event.event_type.value}"
            await self.redis_client.lpush(queue_name, json.dumps(event.to_dict()))
            
            # 우선순위 큐도 업데이트
            if event.priority.value >= Priority.HIGH.value:
                priority_queue = f"priority_events:{event.priority.value}"
                await self.redis_client.lpush(priority_queue, json.dumps(event.to_dict()))
            
            self.metrics["events_published"] += 1
            logger.debug(f"이벤트 발행: {event.event_type.value} - {event.event_id}")
            return True
            
        except Exception as e:
            logger.error(f"이벤트 발행 실패: {e}")
            return False
    
    async def start_workers(self, num_workers: int = 3):
        """워커 프로세스 시작"""
        self.running = True
        
        # 우선순위 큐 워커
        priority_task = asyncio.create_task(self._priority_worker())
        self.worker_tasks.append(priority_task)
        
        # 일반 이벤트 워커들
        for i in range(num_workers):
            task = asyncio.create_task(self._event_worker(f"worker-{i}"))
            self.worker_tasks.append(task)
        
        logger.info(f"EventBus 워커 {len(self.worker_tasks)}개 시작")
    
    async def _priority_worker(self):
        """우선순위 이벤트 처리 워커"""
        while self.running:
            try:
                # 높은 우선순위부터 확인
                for priority in [Priority.CRITICAL, Priority.HIGH]:
                    queue_name = f"priority_events:{priority.value}"
                    result = await self.redis_client.brpop(queue_name, timeout=1)
                    
                    if result:
                        _, event_data = result
                        event = Event.from_dict(json.loads(event_data))
                        await self._process_event(event)
                        break
                
            except Exception as e:
                logger.error(f"우선순위 워커 오류: {e}")
                await asyncio.sleep(1)
    
    async def _event_worker(self, worker_id: str):
        """일반 이벤트 처리 워커"""
        while self.running:
            try:
                # 모든 이벤트 타입에서 라운드로빈으로 처리
                for event_type in EventType:
                    queue_name = f"events:{event_type.value}"
                    result = await self.redis_client.brpop(queue_name, timeout=1)
                    
                    if result:
                        _, event_data = result
                        event = Event.from_dict(json.loads(event_data))
                        await self._process_event(event)
                        break
                else:
                    # 처리할 이벤트가 없으면 잠시 대기
                    await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"워커 {worker_id} 오류: {e}")
                await asyncio.sleep(1)
    
    async def _process_event(self, event: Event):
        """개별 이벤트 처리"""
        try:
            # 만료 체크
            if event.expires_at and datetime.now() > event.expires_at:
                logger.warning(f"만료된 이벤트 폐기: {event.event_id}")
                return
            
            # 핸들러가 있는지 확인
            handlers = self.handlers.get(event.event_type, [])
            if not handlers:
                logger.warning(f"핸들러 없음: {event.event_type.value}")
                return
            
            # 모든 핸들러에서 병렬 처리
            tasks = [handler.handle(event) for handler in handlers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 확인
            success_count = sum(1 for result in results if result is True)
            
            if success_count > 0:
                self.metrics["events_processed"] += 1
                logger.debug(f"이벤트 처리 완료: {event.event_id} ({success_count}/{len(handlers)})")
            else:
                await self._handle_failed_event(event)
            
        except Exception as e:
            logger.error(f"이벤트 처리 중 오류: {e}")
            await self._handle_failed_event(event)
    
    async def _handle_failed_event(self, event: Event):
        """실패한 이벤트 처리"""
        if event.retry_count < self.config.max_retries:
            # 재시도
            event.retry_count += 1
            await asyncio.sleep(self.config.retry_delay * event.retry_count)
            await self.publish(event)
            self.metrics["events_retried"] += 1
            logger.info(f"이벤트 재시도: {event.event_id} ({event.retry_count}/{self.config.max_retries})")
        else:
            # 데드 레터 큐로 이동
            if self.config.enable_dead_letter:
                dead_letter_queue = "dead_letter_queue"
                await self.redis_client.lpush(dead_letter_queue, json.dumps(event.to_dict()))
            
            self.metrics["events_failed"] += 1
            logger.error(f"이벤트 최종 실패: {event.event_id}")
    
    async def create_event(
        self,
        event_type: EventType,
        source_service: str,
        payload: Dict[str, Any],
        target_service: Optional[str] = None,
        priority: Priority = Priority.NORMAL,
        correlation_id: Optional[str] = None
    ) -> Event:
        """편의 메서드: 이벤트 생성"""
        return Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.now(),
            source_service=source_service,
            target_service=target_service,
            priority=priority,
            payload=payload,
            correlation_id=correlation_id
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """시스템 메트릭 조회"""
        return {
            **self.metrics,
            "handlers_count": sum(len(handlers) for handlers in self.handlers.values()),
            "queue_sizes": self._get_queue_sizes(),
            "workers_running": len([t for t in self.worker_tasks if not t.done()])
        }
    
    def _get_queue_sizes(self) -> Dict[str, int]:
        """큐 크기 조회 (비동기 메서드에서 호출해야 함)"""
        # 실제 구현에서는 Redis 큐 크기를 조회
        return {}

# 특화된 이벤트 핸들러들
class AIDecisionHandler(EventHandler):
    """AI 결정 요청 핸들러"""
    
    def __init__(self, decision_engine):
        self.decision_engine = decision_engine
    
    @property
    def supported_events(self) -> List[EventType]:
        return [EventType.AI_DECISION_REQUEST]
    
    async def handle(self, event: Event) -> bool:
        try:
            # AI 결정 요청 처리
            market_context = event.payload.get('market_context')
            decision = await self.decision_engine.make_decision(market_context)
            
            # 결과 이벤트 발행
            response_event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.AI_DECISION_RESPONSE,
                timestamp=datetime.now(),
                source_service="ai_decision_service",
                correlation_id=event.correlation_id,
                payload={'decision': decision.to_dict()}
            )
            
            return True
        except Exception as e:
            logger.error(f"AI 결정 처리 실패: {e}")
            return False

class RiskAlertHandler(EventHandler):
    """리스크 알림 핸들러"""
    
    @property
    def supported_events(self) -> List[EventType]:
        return [EventType.RISK_ALERT]
    
    async def handle(self, event: Event) -> bool:
        try:
            risk_data = event.payload
            logger.critical(f"리스크 알림: {risk_data}")
            
            # 텔레그램 알림 등 추가 처리
            return True
        except Exception as e:
            logger.error(f"리스크 알림 처리 실패: {e}")
            return False

def create_default_event_bus() -> EventBusSystem:
    """기본 이벤트 버스 생성"""
    config = EventBusConfig()
    return EventBusSystem(config)