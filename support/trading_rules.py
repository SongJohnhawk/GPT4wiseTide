"""
자동매매 원칙 및 규칙 관리
알고리즘과 독립적인 매매 규칙들을 정의
"""

import json
import logging
from datetime import datetime, time
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class TradingRules:
    """자동매매 원칙 및 규칙 관리 클래스"""
    
    def __init__(self, rules_file: str = "trading_rules.json"):
        # support 폴더 내의 trading_rules.json 파일을 찾도록 수정
        if not Path(rules_file).is_absolute():
            support_dir = Path(__file__).parent
            self.rules_file = support_dir / rules_file
        else:
            self.rules_file = Path(rules_file)
        self.rules = self._load_rules()
        
    def _load_rules(self) -> Dict[str, Any]:
        """매매 규칙 로드"""
        try:
            if self.rules_file.exists():
                with open(self.rules_file, 'r', encoding='utf-8') as f:
                    rules = json.load(f)
                logger.info(f"매매 규칙 로드 완료: {self.rules_file}")
                return rules
            else:
                # 기본 규칙 생성
                default_rules = self._get_default_rules()
                self._save_rules(default_rules)
                logger.info("기본 매매 규칙 생성 완료")
                return default_rules
        except Exception as e:
            logger.error(f"매매 규칙 로드 실패: {e}")
            return self._get_default_rules()
    
    def _get_default_rules(self) -> Dict[str, Any]:
        """기본 매매 규칙 정의"""
        return {
            "position_management": {
                "max_positions": 5,           # 최대 보유 포지션 수
                "position_size_ratio": 0.1,   # 계좌 대비 포지션 크기 (10%)
                "max_position_value": 0.2,    # 단일 포지션 최대 비중 (20%)
                "min_position_value": 0.01    # 단일 포지션 최소 비중 (1%)
            },
            
            "risk_management": {
                "daily_loss_limit": 0.05,     # 일일 최대 손실한도 (5%)
                "total_risk_limit": 0.15,     # 전체 리스크 한도 (15%)
                "max_consecutive_losses": 3,  # 연속 손실 허용 횟수
                "drawdown_limit": 0.10        # 최대 낙폭 한도 (10%)
            },
            
            "trading_session": {
                "market_open": "09:00",       # 장 시작 시간
                "market_close": "15:30",      # 장 마감 시간
                "pre_market_buffer": 30,      # 장 시작 전 준비시간 (분)
                "post_market_buffer": 30,     # 장 마감 후 정리시간 (분)
                "lunch_break_start": "12:00", # 점심시간 시작
                "lunch_break_end": "13:00",   # 점심시간 종료
                "morning_interval": 180,      # 오전 매매 간격 (180초 = 3분)
                "afternoon_interval": 180     # 오후 매매 간격 (180초 = 3분)
            },
            
            "emergency_sell": {
                "enable_crash_detection": True,  # 급락 감지 활성화
                "crash_threshold": -3.0,         # 급락 기준 (-3%)
                "vi_detection": True,            # 변동성 완화장치(VI) 감지
                "volume_spike_ratio": 3.0,       # 거래량 급증 비율
                "immediate_sell_on_crash": True, # 급락시 즉시 매도
                "immediate_sell_on_vi": True     # VI 발동시 즉시 매도
            },
            
            "order_management": {
                "order_timeout": 300,         # 주문 타임아웃 (초)
                "max_retries": 3,            # 주문 재시도 횟수
                "partial_fill_threshold": 0.8, # 부분체결 허용 비율
                "price_deviation_limit": 0.02  # 호가 이탈 허용범위 (2%)
            },
            
            "monitoring": {
                "position_check_interval": 60,  # 포지션 체크 간격 (초)
                "market_scan_interval": 300,    # 시장 스캔 간격 (초)
                "health_check_interval": 600,   # 시스템 헬스체크 간격 (초)
                "data_refresh_interval": 900    # 데이터 갱신 간격 (초)
            },
            
            "filters": {
                "min_volume": 100000,         # 최소 거래량
                "min_market_cap": 1000,       # 최소 시가총액 (억원)
                "max_volatility": 0.15,       # 최대 변동성 (15%)
                "excluded_sectors": [],       # 제외 업종
                "blacklist_stocks": []        # 거래금지 종목
            },
            
            "volume_price_analysis": {
                "enable": True,               # 거래량-주가 분석 활성화
                "signal_priority": 1,         # 최우선 순위 (1순위)
                
                # 규칙 1: 주가 하락 + 거래량 증가 → 무조건 매도
                "decline_with_volume_sell": True,    # 하락+거래량증가 매도 활성화
                "decline_threshold": -1.0,           # 하락 판단 기준 (-1%)
                "decline_period_days": 3,            # 하락 분석 기간 (3일)
                "decline_volume_ratio": 1.2,         # 거래량 증가 기준 (20% 이상)
                
                # 규칙 2: 주가 횡보(1주일+) + 거래량 증가 → 무조건 매수  
                "sideways_with_volume_buy": True,    # 횡보+거래량증가 매수 활성화
                "sideways_period_days": 5,           # 횡보 판단 기간 (5일) - 완화
                "sideways_threshold": 2.0,           # 횡보 판단 기준 (가격 변동 2% 이내)
                "sideways_volume_ratio": 1.15,       # 횡보시 거래량 증가 기준 (15% 이상) - 완화
                "sideways_stability": 0.7            # 횡보 안정성 기준 (70% 이상)
            }
        }
    
    def _save_rules(self, rules: Dict[str, Any]):
        """매매 규칙 저장"""
        try:
            with open(self.rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            logger.info(f"매매 규칙 저장 완료: {self.rules_file}")
        except Exception as e:
            logger.error(f"매매 규칙 저장 실패: {e}")
    
    # Position Management Rules
    def get_max_positions(self) -> int:
        """최대 포지션 수 반환"""
        return self.rules["position_management"]["max_positions"]
    
    def get_position_size_ratio(self) -> float:
        """포지션 크기 비율 반환"""
        return self.rules["position_management"]["position_size_ratio"]
    
    def get_max_position_value(self) -> float:
        """단일 포지션 최대 비중 반환"""
        return self.rules["position_management"]["max_position_value"]
    
    def calculate_position_size(self, account_balance: float, stock_price: float) -> int:
        """포지션 크기 계산 (규칙 기반)"""
        try:
            # 기본 포지션 크기
            position_value = account_balance * self.get_position_size_ratio()
            
            # 최대/최소 제한 적용
            max_value = account_balance * self.get_max_position_value()
            min_value = account_balance * self.rules["position_management"]["min_position_value"]
            
            position_value = min(max(position_value, min_value), max_value)
            
            # 주식 수 계산
            quantity = int(position_value / stock_price)
            
            logger.debug(f"포지션 크기 계산: {quantity}주 (가격: {stock_price:,}원, 비중: {position_value/account_balance:.2%})")
            return quantity
            
        except Exception as e:
            logger.error(f"포지션 크기 계산 실패: {e}")
            return 0

    def calculate_max_quantity_by_budget_ratio(self, account_balance: float, stock_price: float, budget_ratio: float = 0.07) -> int:
        """예수금 대비 비율로 최대 매수 수량 계산 (7% 원칙)"""
        try:
            # 예수금의 7%로 최대 매수 가능 금액 계산
            max_budget = account_balance * budget_ratio
            
            # 수수료 및 마진 고려 (0.2% 추가)
            margin_rate = 1.002
            adjusted_budget = max_budget / margin_rate
            
            # 최대 매수 가능 수량 계산
            max_quantity = int(adjusted_budget / stock_price)
            
            logger.debug(f"7% 원칙 매수 수량: {max_quantity}주 (가격: {stock_price:,}원, 예산: {max_budget:,}원)")
            return max_quantity
            
        except Exception as e:
            logger.error(f"7% 원칙 수량 계산 실패: {e}")
            return 0
    
    def apply_seven_percent_rule(self, account_balance: float, stock_price: float, target_quantity: int = None) -> int:
        """7% 원칙을 적용한 최종 매수 수량 결정"""
        try:
            # 7% 원칙으로 최대 수량 계산
            max_quantity_by_budget = self.calculate_max_quantity_by_budget_ratio(account_balance, stock_price)
            
            if target_quantity is None:
                # 목표 수량이 없으면 7% 원칙 수량 반환
                final_quantity = max_quantity_by_budget
            else:
                # 목표 수량과 7% 원칙 중 작은 값 선택
                final_quantity = min(target_quantity, max_quantity_by_budget)
            
            logger.info(f"7% 원칙 적용 결과: {final_quantity}주 (목표: {target_quantity}, 예산한도: {max_quantity_by_budget})")
            return final_quantity
            
        except Exception as e:
            logger.error(f"7% 원칙 적용 실패: {e}")
            return 0
    
    # Risk Management Rules
    def check_daily_loss_limit(self, current_loss: float, account_balance: float) -> bool:
        """일일 손실한도 체크"""
        loss_ratio = abs(current_loss) / account_balance
        limit = self.rules["risk_management"]["daily_loss_limit"]
        
        if loss_ratio >= limit:
            logger.warning(f"일일 손실한도 도달: {loss_ratio:.2%} >= {limit:.2%}")
            return False
        return True
    
    def check_total_risk(self, total_risk: float, account_balance: float) -> bool:
        """전체 리스크 한도 체크"""
        risk_ratio = total_risk / account_balance
        limit = self.rules["risk_management"]["total_risk_limit"]
        
        if risk_ratio >= limit:
            logger.warning(f"전체 리스크 한도 도달: {risk_ratio:.2%} >= {limit:.2%}")
            return False
        return True
    
    # Trading Session Rules
    def is_trading_time(self, now: Optional[datetime] = None) -> bool:
        """거래 가능 시간 체크"""
        if now is None:
            now = datetime.now()
        
        current_time = now.time()
        
        # 장 시간 확인 (09:00 ~ 15:00)
        market_open = time.fromisoformat(self.rules["trading_session"]["market_open"])
        market_close = time.fromisoformat(self.rules["trading_session"]["market_close"])
        
        return market_open <= current_time <= market_close
    
    def get_trading_interval(self, now: Optional[datetime] = None) -> int:
        """현재 시간대별 매매 간격 반환 (초) - 모든 시간대 5분 통일"""
        if now is None:
            now = datetime.now()
        
        # 모든 시간대에서 3분(180초) 간격 사용
        return self.rules["trading_session"]["morning_interval"]  # 180초 (3분)
    
    def should_close_all_positions(self, now: Optional[datetime] = None) -> bool:
        """모든 포지션 정리 시간인지 확인 (15:30 장 마감)"""
        if now is None:
            now = datetime.now()
        
        current_time = now.time()
        market_close = time.fromisoformat(self.rules["trading_session"]["market_close"])
        
        return current_time >= market_close
    
    def is_premarket_liquidation_time(self, now: Optional[datetime] = None) -> bool:
        """장 개시 직후 전날 보유 잔고 매도 시간인지 확인 (09:05-09:06)"""
        if now is None:
            now = datetime.now()
        
        if not self.rules["trading_session"].get("enable_premarket_liquidation", False):
            return False
        
        current_time = now.time()
        liquidation_start = time.fromisoformat(self.rules["trading_session"]["premarket_liquidation_start"])
        liquidation_end = time.fromisoformat(self.rules["trading_session"]["premarket_liquidation_end"])
        
        return liquidation_start <= current_time <= liquidation_end
    
    def is_regular_trading_time(self, now: Optional[datetime] = None) -> bool:
        """일반 자동매매 시간인지 확인 (09:06 이후)"""
        if now is None:
            now = datetime.now()
        
        current_time = now.time()
        liquidation_end = time.fromisoformat(self.rules["trading_session"]["premarket_liquidation_end"])
        market_close = time.fromisoformat(self.rules["trading_session"]["market_close"])
        
        return liquidation_end < current_time < market_close
    
    def is_pre_market_time(self, now: Optional[datetime] = None) -> bool:
        """장 시작 전 준비시간 체크"""
        if now is None:
            now = datetime.now()
        
        current_time = now.time()
        market_open = time.fromisoformat(self.rules["trading_session"]["market_open"])
        
        # 30분 전부터 준비시간
        buffer_minutes = self.rules["trading_session"]["pre_market_buffer"]
        pre_market_start = time(
            hour=market_open.hour,
            minute=max(0, market_open.minute - buffer_minutes)
        )
        
        return pre_market_start <= current_time < market_open
    
    def is_post_market_time(self, now: Optional[datetime] = None) -> bool:
        """장 종료 후 시간 체크"""
        if now is None:
            now = datetime.now()
        
        current_time = now.time()
        market_close = time.fromisoformat(self.rules["trading_session"]["market_close"])
        
        return current_time > market_close
    
    def is_market_closed_time(self, now: Optional[datetime] = None) -> bool:
        """장시작 전 또는 장 종료 후 시간 체크"""
        if now is None:
            now = datetime.now()
        
        return not self.is_trading_time(now)
    
    def get_market_status_message(self, now: Optional[datetime] = None) -> str:
        """현재 시장 상태에 따른 메시지 반환"""
        if now is None:
            now = datetime.now()
        
        current_time = now.time()
        market_open = time.fromisoformat(self.rules["trading_session"]["market_open"])
        market_close = time.fromisoformat(self.rules["trading_session"]["market_close"])
        
        if current_time < market_open:
            return f"Market Closed - Before Market Hours (Market opens at {market_open.strftime('%H:%M')})"
        elif current_time > market_close:
            return f"Market Closed - After Market Hours (Market closed at {market_close.strftime('%H:%M')})"
        else:
            return "Market Open - Trading Hours"
    
    # Stock Filtering Rules
    def is_stock_allowed(self, symbol: str, volume: int = 0, market_cap: float = 0) -> bool:
        """종목 거래 허용 여부 확인"""
        # 블랙리스트 확인
        if symbol in self.rules["filters"]["blacklist_stocks"]:
            logger.info(f"블랙리스트 종목: {symbol}")
            return False
        
        # 최소 거래량 확인
        if volume > 0 and volume < self.rules["filters"]["min_volume"]:
            logger.debug(f"거래량 부족: {symbol} ({volume:,})")
            return False
        
        # 최소 시가총액 확인
        if market_cap > 0 and market_cap < self.rules["filters"]["min_market_cap"]:
            logger.debug(f"시가총액 부족: {symbol} ({market_cap:,}억원)")
            return False
        
        return True
    
    # Rule Updates
    def update_rule(self, category: str, key: str, value: Any):
        """개별 규칙 업데이트"""
        try:
            if category in self.rules and key in self.rules[category]:
                old_value = self.rules[category][key]
                self.rules[category][key] = value
                self._save_rules(self.rules)
                logger.info(f"규칙 업데이트: {category}.{key} = {value} (이전: {old_value})")
            else:
                logger.error(f"존재하지 않는 규칙: {category}.{key}")
        except Exception as e:
            logger.error(f"규칙 업데이트 실패: {e}")
    
    def get_rule(self, category: str, key: str = None) -> Any:
        """규칙 조회"""
        try:
            if key is None:
                return self.rules.get(category, {})
            else:
                return self.rules.get(category, {}).get(key)
        except Exception as e:
            logger.error(f"규칙 조회 실패: {e}")
            return None
    
    def reset_to_default(self):
        """기본 규칙으로 리셋"""
        self.rules = self._get_default_rules()
        self._save_rules(self.rules)
        logger.info("매매 규칙을 기본값으로 리셋")
    
    # Emergency Sell Rules (급락/VI 감지)
    def check_crash_condition(self, price_change_rate: float, volume_ratio: float = 1.0) -> bool:
        """급락 조건 확인"""
        if not self.rules.get("emergency_sell", {}).get("enable_crash_detection", True):
            return False
        
        crash_threshold = self.rules.get("emergency_sell", {}).get("crash_threshold", -3.0)
        volume_spike_ratio = self.rules.get("emergency_sell", {}).get("volume_spike_ratio", 3.0)
        
        # 급락 조건: 가격 하락률이 임계값 이하이거나, 거래량 급증과 함께 하락
        is_crash = price_change_rate <= crash_threshold
        is_volume_spike = volume_ratio >= volume_spike_ratio and price_change_rate < 0
        
        if is_crash:
            logger.warning(f"급락 감지: 가격 변동률 {price_change_rate:.2f}% <= {crash_threshold}%")
            return True
        
        if is_volume_spike:
            logger.warning(f"거래량 급증과 함께 하락 감지: 거래량 비율 {volume_ratio:.1f}배, 가격 변동 {price_change_rate:.2f}%")
            return True
        
        return False
    
    def check_vi_condition(self, vi_flag: bool) -> bool:
        """변동성 완화장치(VI) 발동 확인"""
        if not self.rules.get("emergency_sell", {}).get("vi_detection", True):
            return False
        
        if vi_flag:
            logger.warning("변동성 완화장치(VI) 발동 감지")
            return True
        
        return False
    
    def should_emergency_sell(self, price_change_rate: float, volume_ratio: float = 1.0, vi_flag: bool = False) -> bool:
        """긴급 매도 필요 여부 확인"""
        # 급락 확인
        if self.check_crash_condition(price_change_rate, volume_ratio):
            if self.rules.get("emergency_sell", {}).get("immediate_sell_on_crash", True):
                logger.critical(f"급락 감지 - 즉시 매도 실행 (가격 변동: {price_change_rate:.2f}%)")
                return True
        
        # VI 발동 확인
        if self.check_vi_condition(vi_flag):
            if self.rules.get("emergency_sell", {}).get("immediate_sell_on_vi", True):
                logger.critical("VI 발동 - 즉시 매도 실행")
                return True
        
        return False
    
    def check_profit_target(self, purchase_price: float, current_price: float) -> bool:
        """7% 익절 조건 확인"""
        if not self.rules.get("risk_management", {}).get("enable_profit_taking", True):
            return False
        
        profit_target = self.rules.get("risk_management", {}).get("profit_target", 0.07)
        profit_rate = (current_price - purchase_price) / purchase_price
        
        if profit_rate >= profit_target:
            logger.info(f"익절 조건 충족: 수익률 {profit_rate:.2%} >= 목표 {profit_target:.2%}")
            return True
        
        return False
    
    def get_profit_target(self) -> float:
        """익절 목표 수익률 반환"""
        return self.rules.get("risk_management", {}).get("profit_target", 0.07)
    
    def is_profit_taking_enabled(self) -> bool:
        """익절 기능 활성화 여부 확인"""
        return self.rules.get("risk_management", {}).get("enable_profit_taking", True)
    
    def get_summary(self) -> Dict[str, str]:
        """규칙 요약 정보 반환"""
        return {
            "최대 포지션": f"{self.get_max_positions()}개",
            "포지션 크기": f"{self.get_position_size_ratio():.1%}",
            "일일 손실한도": f"{self.rules['risk_management']['daily_loss_limit']:.1%}",
            "거래 시간": f"{self.rules['trading_session']['market_open']} ~ {self.rules['trading_session']['market_close']}",
            "최소 거래량": f"{self.rules['filters']['min_volume']:,}주",
            "매매 간격": f"{self.rules['trading_session']['morning_interval']}초 (3분)",
            "급락 기준": f"{self.rules.get('emergency_sell', {}).get('crash_threshold', -3.0)}%",
            "VI 감지": "활성화" if self.rules.get("emergency_sell", {}).get("vi_detection", True) else "비활성화",
            "익절 목표": f"{self.get_profit_target():.1%}",
            "익절 기능": "활성화" if self.is_profit_taking_enabled() else "비활성화"
        }


# 글로벌 인스턴스
_trading_rules = None

def get_trading_rules() -> TradingRules:
    """Trading Rules 싱글톤 인스턴스 반환"""
    global _trading_rules
    if _trading_rules is None:
        _trading_rules = TradingRules()
    return _trading_rules