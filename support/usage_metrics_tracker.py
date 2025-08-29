"""
tideWise 사용자 메트릭 추적 시스템
사용 패턴, 성능 지표, 시스템 활용도를 추적하고 분석
"""
import json
import os
import time
import asyncio
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import pytz
import logging
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import psutil
import threading

@dataclass
class SystemMetrics:
    """시스템 리소스 사용량 메트릭"""
    timestamp: str
    cpu_percent: float
    memory_used_mb: float
    memory_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float

@dataclass
class TradingMetrics:
    """거래 관련 메트릭"""
    timestamp: str
    session_duration_minutes: float
    total_trades_executed: int
    api_calls_count: int
    algorithm_switches: int
    manual_interventions: int
    stop_loss_triggers: int
    profit_target_hits: int
    current_algorithm: str
    account_type: str  # MOCK/REAL
    trading_mode: str  # AUTO/DAY

@dataclass
class UserInteractionMetrics:
    """사용자 상호작용 메트릭"""
    timestamp: str
    menu_selections: Dict[str, int] = field(default_factory=dict)
    feature_usage_count: Dict[str, int] = field(default_factory=dict)
    error_encounters: int = 0
    session_start_time: str = ""
    session_end_time: str = ""
    keyboard_interrupts: int = 0

@dataclass
class PerformanceMetrics:
    """성능 관련 메트릭"""
    timestamp: str
    api_response_times_ms: List[float] = field(default_factory=list)
    database_query_times_ms: List[float] = field(default_factory=list)
    algorithm_execution_times_ms: List[float] = field(default_factory=list)
    memory_peaks_mb: List[float] = field(default_factory=list)
    cache_hit_rate: float = 0.0
    error_rate: float = 0.0

@dataclass
class DailyUsageSummary:
    """일일 사용량 요약"""
    date: str
    total_session_time_minutes: float
    sessions_count: int
    total_trades: int
    total_api_calls: int
    unique_features_used: int
    system_errors: int
    avg_cpu_usage: float
    avg_memory_usage: float
    peak_memory_usage: float

class UsageMetricsTracker:
    """사용자 메트릭 추적 및 관리 시스템"""
    
    def __init__(self, project_root: Path = None):
        self.seoul_tz = pytz.timezone('Asia/Seoul')
        self.logger = logging.getLogger(__name__)
        
        # 프로젝트 루트 설정
        if project_root is None:
            project_root = Path(__file__).parent.parent
        self.project_root = project_root
        
        # 메트릭 저장 디렉토리 설정
        self.metrics_dir = project_root / "metrics"
        self.metrics_dir.mkdir(exist_ok=True)
        
        # 현재 세션 데이터
        self.session_start_time = None
        self.current_session_id = None
        self.is_tracking = False
        
        # 메트릭 수집 인터벌 (초)
        self.collection_interval = 60  # 1분마다
        
        # 실시간 메트릭 저장소
        self.current_metrics = {
            'system': [],
            'trading': [],
            'user_interaction': defaultdict(lambda: UserInteractionMetrics(
                timestamp=self._get_current_time(),
                menu_selections={},
                feature_usage_count={},
                error_encounters=0
            )),
            'performance': []
        }
        
        # 백그라운드 수집 스레드
        self._collection_thread = None
        self._stop_collection = False
        
        # 초기 시스템 정보 수집
        self._collect_initial_system_info()
    
    def _get_current_time(self) -> str:
        """현재 시간을 서울 시간대로 반환"""
        return datetime.now(self.seoul_tz).isoformat()
    
    def _collect_initial_system_info(self):
        """초기 시스템 정보 수집"""
        try:
            # 시스템 사양 정보
            system_info = {
                'timestamp': self._get_current_time(),
                'cpu_count': psutil.cpu_count(),
                'cpu_freq_mhz': psutil.cpu_freq().current if psutil.cpu_freq() else 0,
                'total_memory_gb': round(psutil.virtual_memory().total / (1024**3), 2),
                'python_version': f"{psutil.__version__}",
                'platform': os.name
            }
            
            # 초기 시스템 정보 저장
            info_file = self.metrics_dir / "system_info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(system_info, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"초기 시스템 정보 수집 실패: {e}")
    
    def start_session(self, account_type: str = 'MOCK', trading_mode: str = 'AUTO') -> str:
        """메트릭 추적 세션 시작"""
        try:
            self.session_start_time = datetime.now(self.seoul_tz)
            self.current_session_id = f"session_{self.session_start_time.strftime('%Y%m%d_%H%M%S')}"
            
            # 세션 정보 기록
            session_info = {
                'session_id': self.current_session_id,
                'start_time': self.session_start_time.isoformat(),
                'account_type': account_type,
                'trading_mode': trading_mode,
                'system_info': self._get_system_snapshot()
            }
            
            # 세션 파일 생성
            session_file = self.metrics_dir / f"{self.current_session_id}.json"
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_info, f, ensure_ascii=False, indent=2)
            
            self.is_tracking = True
            self._start_background_collection()
            
            self.logger.info(f"메트릭 추적 세션 시작: {self.current_session_id}")
            return self.current_session_id
            
        except Exception as e:
            self.logger.error(f"메트릭 세션 시작 실패: {e}")
            return ""
    
    def stop_session(self):
        """메트릭 추적 세션 종료"""
        try:
            if not self.is_tracking:
                return
                
            self.is_tracking = False
            self._stop_background_collection()
            
            # 세션 종료 정보 업데이트
            session_end_time = datetime.now(self.seoul_tz)
            session_duration = (session_end_time - self.session_start_time).total_seconds() / 60
            
            session_file = self.metrics_dir / f"{self.current_session_id}.json"
            if session_file.exists():
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                session_data.update({
                    'end_time': session_end_time.isoformat(),
                    'duration_minutes': round(session_duration, 2),
                    'final_metrics': self._get_session_summary()
                })
                
                with open(session_file, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, ensure_ascii=False, indent=2)
            
            self._save_daily_summary()
            self.logger.info(f"메트릭 세션 종료: {self.current_session_id}, 지속시간: {session_duration:.1f}분")
            
        except Exception as e:
            self.logger.error(f"메트릭 세션 종료 실패: {e}")
    
    def _start_background_collection(self):
        """백그라운드 메트릭 수집 시작"""
        self._stop_collection = False
        self._collection_thread = threading.Thread(target=self._background_collection_worker, daemon=True)
        self._collection_thread.start()
    
    def _stop_background_collection(self):
        """백그라운드 메트릭 수집 중지"""
        self._stop_collection = True
        if self._collection_thread and self._collection_thread.is_alive():
            self._collection_thread.join(timeout=5)
    
    def _background_collection_worker(self):
        """백그라운드에서 주기적으로 시스템 메트릭 수집"""
        while not self._stop_collection and self.is_tracking:
            try:
                self._collect_system_metrics()
                time.sleep(self.collection_interval)
            except Exception as e:
                self.logger.error(f"백그라운드 메트릭 수집 오류: {e}")
                time.sleep(self.collection_interval)
    
    def _collect_system_metrics(self):
        """시스템 리소스 메트릭 수집"""
        try:
            # CPU 및 메모리 사용률
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # 디스크 I/O
            disk_io = psutil.disk_io_counters()
            disk_read_mb = disk_io.read_bytes / (1024 * 1024) if disk_io else 0
            disk_write_mb = disk_io.write_bytes / (1024 * 1024) if disk_io else 0
            
            # 네트워크 I/O
            network_io = psutil.net_io_counters()
            network_sent_mb = network_io.bytes_sent / (1024 * 1024) if network_io else 0
            network_recv_mb = network_io.bytes_recv / (1024 * 1024) if network_io else 0
            
            system_metric = SystemMetrics(
                timestamp=self._get_current_time(),
                cpu_percent=cpu_percent,
                memory_used_mb=round(memory.used / (1024 * 1024), 2),
                memory_percent=memory.percent,
                disk_io_read_mb=round(disk_read_mb, 2),
                disk_io_write_mb=round(disk_write_mb, 2),
                network_sent_mb=round(network_sent_mb, 2),
                network_recv_mb=round(network_recv_mb, 2)
            )
            
            self.current_metrics['system'].append(asdict(system_metric))
            
        except Exception as e:
            self.logger.error(f"시스템 메트릭 수집 실패: {e}")
    
    def record_trading_activity(self, activity_type: str, details: Dict[str, Any]):
        """거래 활동 메트릭 기록"""
        try:
            if not self.is_tracking:
                return
                
            current_time = self._get_current_time()
            
            # 거래 메트릭 생성
            trading_metric = TradingMetrics(
                timestamp=current_time,
                session_duration_minutes=self._get_session_duration(),
                total_trades_executed=details.get('total_trades', 0),
                api_calls_count=details.get('api_calls', 0),
                algorithm_switches=details.get('algorithm_switches', 0),
                manual_interventions=details.get('manual_interventions', 0),
                stop_loss_triggers=details.get('stop_loss_triggers', 0),
                profit_target_hits=details.get('profit_target_hits', 0),
                current_algorithm=details.get('current_algorithm', 'unknown'),
                account_type=details.get('account_type', 'MOCK'),
                trading_mode=details.get('trading_mode', 'AUTO')
            )
            
            self.current_metrics['trading'].append(asdict(trading_metric))
            
        except Exception as e:
            self.logger.error(f"거래 활동 메트릭 기록 실패: {e}")
    
    def record_user_interaction(self, interaction_type: str, details: Dict[str, Any]):
        """사용자 상호작용 메트릭 기록"""
        try:
            if not self.is_tracking:
                return
                
            current_time = self._get_current_time()
            today = date.today().isoformat()
            
            # 오늘 날짜의 상호작용 메트릭 가져오기
            if today not in self.current_metrics['user_interaction']:
                self.current_metrics['user_interaction'][today] = UserInteractionMetrics(
                    timestamp=current_time,
                    session_start_time=self.session_start_time.isoformat() if self.session_start_time else current_time
                )
            
            interaction_metric = self.current_metrics['user_interaction'][today]
            
            # 상호작용 유형에 따라 카운터 업데이트
            if interaction_type == 'menu_selection':
                menu_item = details.get('menu_item', 'unknown')
                interaction_metric.menu_selections[menu_item] = interaction_metric.menu_selections.get(menu_item, 0) + 1
            
            elif interaction_type == 'feature_usage':
                feature_name = details.get('feature_name', 'unknown')
                interaction_metric.feature_usage_count[feature_name] = interaction_metric.feature_usage_count.get(feature_name, 0) + 1
            
            elif interaction_type == 'error':
                interaction_metric.error_encounters += 1
            
            elif interaction_type == 'keyboard_interrupt':
                interaction_metric.keyboard_interrupts += 1
            
            interaction_metric.timestamp = current_time
            
        except Exception as e:
            self.logger.error(f"사용자 상호작용 메트릭 기록 실패: {e}")
    
    def record_performance_metric(self, metric_type: str, value: Union[float, List[float]], details: Dict[str, Any] = None):
        """성능 메트릭 기록"""
        try:
            if not self.is_tracking:
                return
                
            current_time = self._get_current_time()
            
            # 최신 성능 메트릭 가져오기 또는 새로 생성
            if not self.current_metrics['performance'] or \
               (datetime.now(self.seoul_tz) - datetime.fromisoformat(self.current_metrics['performance'][-1]['timestamp'].replace('Z', '+00:00'))).seconds > 300:  # 5분 간격
                
                performance_metric = PerformanceMetrics(timestamp=current_time)
                self.current_metrics['performance'].append(asdict(performance_metric))
            
            # 가장 최근 성능 메트릭 업데이트
            latest_metric = self.current_metrics['performance'][-1]
            
            if metric_type == 'api_response_time':
                latest_metric['api_response_times_ms'].append(value)
            elif metric_type == 'database_query_time':
                latest_metric['database_query_times_ms'].append(value)
            elif metric_type == 'algorithm_execution_time':
                latest_metric['algorithm_execution_times_ms'].append(value)
            elif metric_type == 'memory_peak':
                latest_metric['memory_peaks_mb'].append(value)
            elif metric_type == 'cache_hit_rate':
                latest_metric['cache_hit_rate'] = value
            elif metric_type == 'error_rate':
                latest_metric['error_rate'] = value
                
            latest_metric['timestamp'] = current_time
            
        except Exception as e:
            self.logger.error(f"성능 메트릭 기록 실패: {e}")
    
    def _get_session_duration(self) -> float:
        """현재 세션 지속 시간(분) 반환"""
        if not self.session_start_time:
            return 0.0
        return (datetime.now(self.seoul_tz) - self.session_start_time).total_seconds() / 60
    
    def _get_system_snapshot(self) -> Dict[str, Any]:
        """현재 시스템 상태 스냅샷"""
        try:
            return {
                'cpu_count': psutil.cpu_count(),
                'total_memory_gb': round(psutil.virtual_memory().total / (1024**3), 2),
                'available_memory_gb': round(psutil.virtual_memory().available / (1024**3), 2),
                'disk_usage_percent': psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent
            }
        except Exception as e:
            self.logger.error(f"시스템 스냅샷 생성 실패: {e}")
            return {}
    
    def _get_session_summary(self) -> Dict[str, Any]:
        """현재 세션 요약 정보"""
        try:
            summary = {
                'total_system_metrics': len(self.current_metrics['system']),
                'total_trading_metrics': len(self.current_metrics['trading']),
                'total_performance_metrics': len(self.current_metrics['performance']),
                'user_interactions_today': len(self.current_metrics['user_interaction']),
                'session_duration_minutes': self._get_session_duration()
            }
            
            # 시스템 리소스 평균값 계산
            if self.current_metrics['system']:
                system_metrics = self.current_metrics['system']
                summary.update({
                    'avg_cpu_percent': round(sum(m['cpu_percent'] for m in system_metrics) / len(system_metrics), 2),
                    'avg_memory_percent': round(sum(m['memory_percent'] for m in system_metrics) / len(system_metrics), 2),
                    'peak_memory_mb': max(m['memory_used_mb'] for m in system_metrics)
                })
            
            return summary
            
        except Exception as e:
            self.logger.error(f"세션 요약 생성 실패: {e}")
            return {}
    
    def _save_daily_summary(self):
        """일일 요약 저장"""
        try:
            today = date.today().isoformat()
            summary_file = self.metrics_dir / f"daily_summary_{today}.json"
            
            # 기존 일일 요약이 있으면 로드
            daily_summary = {}
            if summary_file.exists():
                with open(summary_file, 'r', encoding='utf-8') as f:
                    daily_summary = json.load(f)
            
            # 현재 세션 데이터로 업데이트
            session_summary = self._get_session_summary()
            daily_summary.update({
                'date': today,
                'last_updated': self._get_current_time(),
                'total_sessions': daily_summary.get('total_sessions', 0) + 1,
                'total_session_time_minutes': daily_summary.get('total_session_time_minutes', 0) + session_summary.get('session_duration_minutes', 0),
                'system_metrics_collected': daily_summary.get('system_metrics_collected', 0) + session_summary.get('total_system_metrics', 0),
                'trading_activities': daily_summary.get('trading_activities', 0) + session_summary.get('total_trading_metrics', 0),
                'performance_measurements': daily_summary.get('performance_measurements', 0) + session_summary.get('total_performance_metrics', 0)
            })
            
            # 시스템 리소스 통계 업데이트
            if 'avg_cpu_percent' in session_summary:
                daily_summary.update({
                    'avg_cpu_usage': session_summary['avg_cpu_percent'],
                    'avg_memory_usage': session_summary['avg_memory_percent'],
                    'peak_memory_usage': max(daily_summary.get('peak_memory_usage', 0), session_summary.get('peak_memory_mb', 0))
                })
            
            # 일일 요약 저장
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(daily_summary, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"일일 요약 저장 실패: {e}")
    
    def get_metrics_data(self, start_date: str = None, end_date: str = None, metric_types: List[str] = None) -> Dict[str, Any]:
        """메트릭 데이터 조회"""
        try:
            if metric_types is None:
                metric_types = ['system', 'trading', 'user_interaction', 'performance']
            
            result = {}
            
            # 현재 세션 데이터
            if self.is_tracking:
                result['current_session'] = {
                    'session_id': self.current_session_id,
                    'start_time': self.session_start_time.isoformat() if self.session_start_time else None,
                    'duration_minutes': self._get_session_duration(),
                    'metrics': {k: v for k, v in self.current_metrics.items() if k in metric_types}
                }
            
            # 과거 세션 데이터 로드 (날짜 범위 적용)
            historical_data = self._load_historical_metrics(start_date, end_date, metric_types)
            if historical_data:
                result['historical_data'] = historical_data
            
            return result
            
        except Exception as e:
            self.logger.error(f"메트릭 데이터 조회 실패: {e}")
            return {}
    
    def _load_historical_metrics(self, start_date: str, end_date: str, metric_types: List[str]) -> Dict[str, Any]:
        """과거 메트릭 데이터 로드"""
        try:
            historical_data = {}
            
            # 메트릭 디렉토리에서 세션 파일 찾기
            for session_file in self.metrics_dir.glob("session_*.json"):
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)
                    
                    # 날짜 필터링 (구현 예정)
                    session_date = session_data.get('start_time', '')[:10]  # YYYY-MM-DD 형식
                    
                    if self._is_date_in_range(session_date, start_date, end_date):
                        historical_data[session_data['session_id']] = session_data
                        
                except Exception as e:
                    self.logger.warning(f"세션 파일 로드 실패 {session_file}: {e}")
            
            return historical_data
            
        except Exception as e:
            self.logger.error(f"과거 메트릭 데이터 로드 실패: {e}")
            return {}
    
    def _is_date_in_range(self, target_date: str, start_date: str, end_date: str) -> bool:
        """날짜가 범위 내에 있는지 확인"""
        try:
            if not target_date:
                return True
                
            target = datetime.fromisoformat(target_date).date()
            
            if start_date:
                start = datetime.fromisoformat(start_date).date()
                if target < start:
                    return False
            
            if end_date:
                end = datetime.fromisoformat(end_date).date()
                if target > end:
                    return False
            
            return True
            
        except Exception:
            return True  # 날짜 파싱 실패 시 포함

# 전역 메트릭 추적기 인스턴스
usage_tracker = UsageMetricsTracker()