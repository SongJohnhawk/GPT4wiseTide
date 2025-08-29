"""
자동매매 시스템 상수 정의 모듈
GPT5 코드 리뷰 권장사항에 따른 하드코딩 값 외부화
"""

from datetime import time
from enum import Enum
from typing import Dict, Any


class TradingSteps(Enum):
    """자동매매 단계 상수"""
    ACCOUNT_QUERY = "1/19"
    BALANCE_CLEANUP_START = "2/19"
    BALANCE_CLEANUP_PROCESS = "3/19"
    STOCK_COLLECTION_START = "4/19"
    STOCK_COLLECTION_PROCESS = "5/19"
    AUTO_TRADING_START = "6/19"
    AUTO_TRADING_ANALYSIS = "7/19"
    AUTO_TRADING_DECISION = "8/19"
    AUTO_TRADING_EXECUTE = "9/19"
    AUTO_TRADING_END = "10/19"
    AUTO_TRADING_RESULT = "11/19"
    USER_STOCK_START = "12/19"
    USER_STOCK_DECISION = "13/19"
    USER_STOCK_RESULT = "14/19"
    CYCLE_END = "15/19"
    COUNTDOWN = "16/19"
    SECOND_CYCLE_START = "17/19"
    SECOND_CYCLE_PROCESS = "18/19"
    TEST_COMPLETE = "19/19"


class TradingConfig:
    """자동매매 설정 상수"""
    
    # 시간 설정
    MARKET_CLOSE_TIME = time(14, 55)  # 오후 2시 55분
    TRADING_CYCLE_SECONDS = 5  # 자동매매 사이클 간격
    COUNTDOWN_SECONDS = 5  # 카운트다운 시간
    STEP_DELAY_SECONDS = 2  # 각 단계별 지연 시간
    
    # 매매 설정
    MAX_POSITION_PERCENT = 20  # 최대 포지션 비중 (%)
    STOP_LOSS_PERCENT = -3  # 손절 기준 (%)
    TAKE_PROFIT_PERCENT = 5  # 익절 기준 (%)
    
    # 알고리즘 설정
    DEFAULT_ALGORITHM = "default"
    
    # 메시지 포맷
    MESSAGE_SEPARATOR = "-" * 50
    STEP_FORMAT = "[{step}] {title}"
    
    # 파일 경로
    CONFIG_FILE = "trading_config.json"
    LOG_FILE = "trading.log"


class ExceptionMessages:
    """예외 메시지 상수"""
    
    API_CONNECTION_FAILED = "API 연결에 실패했습니다"
    ALGORITHM_LOAD_FAILED = "알고리즘 로드에 실패했습니다"
    TELEGRAM_INIT_FAILED = "텔레그램 초기화에 실패했습니다"
    ACCOUNT_QUERY_FAILED = "계좌 조회에 실패했습니다"
    ORDER_EXECUTION_FAILED = "주문 실행에 실패했습니다"
    POSITION_QUERY_FAILED = "포지션 조회에 실패했습니다"
    STOCK_DATA_FAILED = "종목 데이터 조회에 실패했습니다"
    MARKET_TIME_CHECK_FAILED = "장 시간 확인에 실패했습니다"


class ReturnCodes:
    """반환 코드 상수"""
    
    SUCCESS = 0
    FAILURE = 1
    PARTIAL_SUCCESS = 2
    TIMEOUT = 3
    CANCELLED = 4


class TradingMessages:
    """자동매매 메시지 템플릿"""
    
    STEP_TEMPLATES = {
        TradingSteps.ACCOUNT_QUERY: {
            "title": "계좌 조회",
            "start": "계좌 정보를 조회하고 있습니다.\n현재 보유 자산과 매수 가능 금액을 확인합니다.",
            "complete": "총 자산: {total_asset}\n매수 가능 금액: {available_cash}\n보유 종목 수: {stock_count}개"
        },
        TradingSteps.BALANCE_CLEANUP_START: {
            "title": "잔고 정리 시작",
            "start": "전날 보유 종목에 대한 정리 작업을 시작합니다.\n손절/익절 조건을 확인하여 매도 여부를 판단합니다."
        },
        TradingSteps.BALANCE_CLEANUP_PROCESS: {
            "title": "잔고 정리 진행중",
            "process": "보유 종목별 수익률을 분석하고 있습니다.\n- 수익률 +5% 이상: 익절 검토\n- 수익률 -3% 이하: 손절 검토\n- 그 외: 보유 유지",
            "complete": "매도 종목: {sold_stocks}개\n보유 유지: {kept_stocks}개\n정리 손익: {profit}"
        },
        TradingSteps.STOCK_COLLECTION_START: {
            "title": "종목 및 종목별 정보 수집 시작",
            "start": "매매 대상 종목들을 수집하고 있습니다.\n- 테마주 분석\n- 기술적 지표 계산\n- 시장 상황 파악"
        },
        TradingSteps.STOCK_COLLECTION_PROCESS: {
            "title": "종목 정보 분석중",
            "process": "수집된 종목들의 기술적 지표를 계산하고 있습니다.\nRSI, MACD, 볼린저 밴드 등을 분석합니다.",
            "complete": "테마주 수집: {theme_stocks}개\n분석 완료: {analyzed_stocks}개\n매수 후보: {buy_candidates}개"
        },
        TradingSteps.AUTO_TRADING_START: {
            "title": "자동매매 시작",
            "start": "알고리즘: {algorithm_name}\n수집된 종목을 대상으로 매매를 시작합니다."
        },
        TradingSteps.AUTO_TRADING_ANALYSIS: {
            "title": "종목 분석 진행중",
            "process": "알고리즘이 각 종목을 분석하고 있습니다.\n- 진입 시점 분석\n- 리스크 평가\n- 포지션 크기 계산"
        },
        TradingSteps.AUTO_TRADING_DECISION: {
            "title": "매매 여부 판단",
            "process": "알고리즘 분석 결과를 바탕으로 매수/매도를 결정합니다.\n위험 관리 규칙을 적용하여 최종 결정합니다."
        },
        TradingSteps.AUTO_TRADING_EXECUTE: {
            "title": "매수/매도 실행",
            "complete": "매수 주문: {buy_orders}건\n매도 주문: {sell_orders}건\n체결률: {success_rate}"
        },
        TradingSteps.AUTO_TRADING_END: {
            "title": "자동매매 종료",
            "complete": "이번 라운드 자동매매가 완료되었습니다.\n포지션 관리 및 리스크 체크를 완료했습니다."
        },
        TradingSteps.AUTO_TRADING_RESULT: {
            "title": "자동매매 결과",
            "complete": "총 거래: {total_trades}건\n실현 손익: {profit}\n성공 거래: {success_trades}건"
        },
        TradingSteps.USER_STOCK_START: {
            "title": "사용자 지정종목 매매 시작",
            "start": "사용자가 직접 지정한 종목에 대한 매매를 시작합니다.\n우선순위 높은 종목부터 검토합니다."
        },
        TradingSteps.USER_STOCK_DECISION: {
            "title": "사용자 지정종목 분석중",
            "process": "지정된 종목의 현재 상황을 분석하고 있습니다.\n- 기술적 분석\n- 시장 상황 고려\n- 포트폴리오 밸런스 체크"
        },
        TradingSteps.USER_STOCK_RESULT: {
            "title": "사용자 지정종목 매매 결과",
            "complete": "분석 종목: {analyzed_stocks}개\n실행 거래: {executed_trades}건\n대기 주문: {pending_orders}건"
        },
        TradingSteps.CYCLE_END: {
            "title": "자동매매 사이클 종료",
            "complete": "매매 사이클이 완료되었습니다.\n다음 사이클 준비를 시작합니다."
        },
        TradingSteps.COUNTDOWN: {
            "title": "인터벌 카운트다운 시작",
            "start": "다음 사이클까지 {seconds}초 대기합니다."
        }
    }


# 기본 설정값들
DEFAULT_CONFIG = {
    "market_close_time": "14:55",
    "trading_cycle_seconds": 5,
    "countdown_seconds": 5,
    "step_delay_seconds": 2,
    "max_position_percent": 20,
    "stop_loss_percent": -3,
    "take_profit_percent": 5,
    "default_algorithm": "SafeSimpleAlgorithm",
    # 마감 임박 제어 설정
    "enable_esc_stop": False,
    "close_guard_minutes": 5,
    "close_guard_enabled": True,
    "new_entry_block_before_close": True,
    "countdown_warning_enabled": True,
    "termination_reason_logging": True
}