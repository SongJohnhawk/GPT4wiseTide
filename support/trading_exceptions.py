"""
자동매매 시스템 커스텀 예외 정의 모듈
GPT5 코드 리뷰 권장사항에 따른 세분화된 예외 처리
"""

from typing import Optional, Dict, Any


class TradingException(Exception):
    """자동매매 시스템 기본 예외 클래스"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {super().__str__()}"
        return super().__str__()


class APIConnectionError(TradingException):
    """API 연결 오류"""
    
    def __init__(self, message: str = "API 연결에 실패했습니다", **kwargs):
        super().__init__(message, error_code="API_CONNECTION_ERROR", **kwargs)


class APIRateLimitError(TradingException):
    """API 호출 한도 초과 오류"""
    
    def __init__(self, message: str = "API 호출 한도를 초과했습니다", **kwargs):
        super().__init__(message, error_code="API_RATE_LIMIT_ERROR", **kwargs)


class APIResponseError(TradingException):
    """API 응답 오류"""
    
    def __init__(self, message: str = "API 응답이 올바르지 않습니다", response_code: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="API_RESPONSE_ERROR", **kwargs)
        if response_code:
            self.details["response_code"] = response_code


class AccountQueryError(TradingException):
    """계좌 조회 오류"""
    
    def __init__(self, message: str = "계좌 조회에 실패했습니다", **kwargs):
        super().__init__(message, error_code="ACCOUNT_QUERY_ERROR", **kwargs)


class TokenError(TradingException):
    """토큰 관련 오류"""
    
    def __init__(self, message: str = "토큰 처리에 실패했습니다", **kwargs):
        super().__init__(message, error_code="TOKEN_ERROR", **kwargs)


class AccountError(TradingException):
    """계좌 관련 일반 오류"""
    
    def __init__(self, message: str = "계좌 처리에 실패했습니다", **kwargs):
        super().__init__(message, error_code="ACCOUNT_ERROR", **kwargs)


class InsufficientFundsError(TradingException):
    """자금 부족 오류"""
    
    def __init__(self, message: str = "매수 가능 금액이 부족합니다", required_amount: Optional[float] = None, available_amount: Optional[float] = None, **kwargs):
        super().__init__(message, error_code="INSUFFICIENT_FUNDS_ERROR", **kwargs)
        if required_amount is not None:
            self.details["required_amount"] = required_amount
        if available_amount is not None:
            self.details["available_amount"] = available_amount


class OrderExecutionError(TradingException):
    """주문 실행 오류"""
    
    def __init__(self, message: str = "주문 실행에 실패했습니다", order_type: Optional[str] = None, stock_code: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="ORDER_EXECUTION_ERROR", **kwargs)
        if order_type:
            self.details["order_type"] = order_type
        if stock_code:
            self.details["stock_code"] = stock_code


class OrderValidationError(TradingException):
    """주문 유효성 검증 오류"""
    
    def __init__(self, message: str = "주문 정보가 유효하지 않습니다", **kwargs):
        super().__init__(message, error_code="ORDER_VALIDATION_ERROR", **kwargs)


class PositionQueryError(TradingException):
    """포지션 조회 오류"""
    
    def __init__(self, message: str = "포지션 조회에 실패했습니다", **kwargs):
        super().__init__(message, error_code="POSITION_QUERY_ERROR", **kwargs)


class StockDataError(TradingException):
    """종목 데이터 오류"""
    
    def __init__(self, message: str = "종목 데이터 조회에 실패했습니다", stock_code: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="STOCK_DATA_ERROR", **kwargs)
        if stock_code:
            self.details["stock_code"] = stock_code


class AlgorithmError(TradingException):
    """알고리즘 실행 오류"""
    
    def __init__(self, message: str = "알고리즘 실행에 실패했습니다", algorithm_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="ALGORITHM_ERROR", **kwargs)
        if algorithm_name:
            self.details["algorithm_name"] = algorithm_name


class AlgorithmLoadError(TradingException):
    """알고리즘 로드 오류"""
    
    def __init__(self, message: str = "알고리즘 로드에 실패했습니다", algorithm_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="ALGORITHM_LOAD_ERROR", **kwargs)
        if algorithm_name:
            self.details["algorithm_name"] = algorithm_name


class TelegramNotificationError(TradingException):
    """텔레그램 알림 오류"""
    
    def __init__(self, message: str = "텔레그램 알림 발송에 실패했습니다", **kwargs):
        super().__init__(message, error_code="TELEGRAM_NOTIFICATION_ERROR", **kwargs)


class MarketTimeError(TradingException):
    """장 시간 관련 오류"""
    
    def __init__(self, message: str = "장 시간 확인에 실패했습니다", **kwargs):
        super().__init__(message, error_code="MARKET_TIME_ERROR", **kwargs)


class MarketClosedError(TradingException):
    """장 마감 오류"""
    
    def __init__(self, message: str = "현재 장이 마감되었습니다", **kwargs):
        super().__init__(message, error_code="MARKET_CLOSED_ERROR", **kwargs)


class ConfigurationError(TradingException):
    """설정 오류"""
    
    def __init__(self, message: str = "설정에 오류가 있습니다", config_key: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="CONFIGURATION_ERROR", **kwargs)
        if config_key:
            self.details["config_key"] = config_key


class ResourceCleanupError(TradingException):
    """리소스 정리 오류"""
    
    def __init__(self, message: str = "리소스 정리에 실패했습니다", resource_type: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="RESOURCE_CLEANUP_ERROR", **kwargs)
        if resource_type:
            self.details["resource_type"] = resource_type


class ValidationError(TradingException):
    """데이터 유효성 검증 오류"""
    
    def __init__(self, message: str = "데이터 유효성 검증에 실패했습니다", field_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="VALIDATION_ERROR", **kwargs)
        if field_name:
            self.details["field_name"] = field_name


class TimeoutError(TradingException):
    """타임아웃 오류"""
    
    def __init__(self, message: str = "작업이 시간 초과되었습니다", timeout_seconds: Optional[int] = None, **kwargs):
        super().__init__(message, error_code="TIMEOUT_ERROR", **kwargs)
        if timeout_seconds is not None:
            self.details["timeout_seconds"] = timeout_seconds


class CancellationError(TradingException):
    """작업 취소 오류"""
    
    def __init__(self, message: str = "작업이 취소되었습니다", **kwargs):
        super().__init__(message, error_code="CANCELLATION_ERROR", **kwargs)


# 예외 카테고리별 매핑
EXCEPTION_MAPPING = {
    "api": [APIConnectionError, APIRateLimitError, APIResponseError],
    "account": [AccountQueryError, InsufficientFundsError],
    "order": [OrderExecutionError, OrderValidationError],
    "position": [PositionQueryError],
    "stock_data": [StockDataError],
    "algorithm": [AlgorithmError, AlgorithmLoadError],
    "telegram": [TelegramNotificationError],
    "market": [MarketTimeError, MarketClosedError],
    "config": [ConfigurationError],
    "resource": [ResourceCleanupError],
    "validation": [ValidationError],
    "system": [TimeoutError, CancellationError]
}


def get_exception_category(exception: TradingException) -> Optional[str]:
    """예외의 카테고리 반환"""
    exception_type = type(exception)
    for category, exception_types in EXCEPTION_MAPPING.items():
        if exception_type in exception_types:
            return category
    return None


def format_exception_details(exception: TradingException) -> str:
    """예외 상세 정보를 포맷팅된 문자열로 반환"""
    details = []
    if exception.error_code:
        details.append(f"Error Code: {exception.error_code}")
    if exception.details:
        for key, value in exception.details.items():
            details.append(f"{key}: {value}")
    
    if details:
        return f"{str(exception)}\nDetails: {', '.join(details)}"
    return str(exception)