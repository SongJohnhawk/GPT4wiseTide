"""
tideWise Support 모듈
핵심 지원 기능들을 포함하는 패키지
"""

# 모듈들을 지연 로딩으로 변경하여 의존성 문제 해결
__all__ = [
    'SimpleAutoTrader',
    'SystemLogger',
    'TelegramNotifier',
    'get_telegram_notifier',
    'TradingRules',
    'get_trading_rules',
    'AdvancedSellRules',
    'load_theme_stocks',
    'get_default_theme_stocks',
    'AlgorithmLoader',
    'get_algorithm_loader'
]

def __getattr__(name):
    """지연 로딩을 통해 모듈 import"""
    if name == 'SimpleAutoTrader':
        from .simple_auto_trader import SimpleAutoTrader
        return SimpleAutoTrader
    elif name == 'SystemLogger':
        from .system_logger import SystemLogger
        return SystemLogger
    elif name == 'TelegramNotifier':
        from .telegram_notifier import TelegramNotifier
        return TelegramNotifier
    elif name == 'get_telegram_notifier':
        from .telegram_notifier import get_telegram_notifier
        return get_telegram_notifier
    elif name == 'TradingRules':
        from .trading_rules import TradingRules
        return TradingRules
    elif name == 'get_trading_rules':
        from .trading_rules import get_trading_rules
        return get_trading_rules
    elif name == 'AdvancedSellRules':
        from .advanced_sell_rules import AdvancedSellRules
        return AdvancedSellRules
    elif name == 'load_theme_stocks':
        from .enhanced_theme_stocks import load_theme_stocks
        return load_theme_stocks
    elif name == 'get_default_theme_stocks':
        from .enhanced_theme_stocks import get_default_theme_stocks
        return get_default_theme_stocks
    elif name == 'AlgorithmLoader':
        from .algorithm_loader import AlgorithmLoader
        return AlgorithmLoader
    elif name == 'get_algorithm_loader':
        from .algorithm_loader import get_algorithm_loader
        return get_algorithm_loader
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")