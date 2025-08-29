# tideWise 매매 원칙 및 규칙 설정

이 파일은 tideWise 시스템 자체에서 적용하는 매매 원칙과 규칙을 정의합니다.
알고리즘 특화 규칙은 제외하고, 시스템 전반에 적용되는 기본 원칙만 포함됩니다.

---

## 🎯 사용자 지정종목 관리 규칙

### 수익률 알림 설정
```
PROFIT_NOTIFICATION_THRESHOLD = "0.30"  # 30% 이상 수익시 텔레그램 알림
```

### 사용자 지정종목 목록 (17개)
```
USER_DESIGNATED_STOCKS = {
    "005930": {"name": "삼성전자", "target_quantity": "20"},
    "009540": {"name": "한화오션", "target_quantity": "20"},
    "267260": {"name": "HD현대일렉트릭", "target_quantity": "5"},
    "267250": {"name": "HD현대중공업", "target_quantity": "5"},
    "373220": {"name": "LG에너지솔루션", "target_quantity": "10"},
    "375500": {"name": "DL이엔씨", "target_quantity": "50"},
    "034020": {"name": "두산에너빌리티", "target_quantity": "50"},
    "003490": {"name": "대한항공", "target_quantity": "20"},
    "000150": {"name": "두산", "target_quantity": "50"},
    "123330": {"name": "제닉", "target_quantity": "20"},
    "117730": {"name": "로보티즈", "target_quantity": "20"},
    "030800": {"name": "원익홀딩스", "target_quantity": "50"},
    "212560": {"name": "클로봇", "target_quantity": "20"},
    "454910": {"name": "두산로보틱스", "target_quantity": "20"},
    "000720": {"name": "현대건설", "target_quantity": "20"},
    "196170": {"name": "알테오젠", "target_quantity": "10"},
    "064350": {"name": "현대로템", "target_quantity": "20"},
    "047810": {"name": "한국항공우주", "target_quantity": "10"}
}
```

---

## 💰 매수 수량 및 예산 관리 규칙

### 예산 비율 제한 (모든 종목 공통 적용)
```
POSITION_SIZE_BUDGET_RATIO = "0.07"  # 예수금의 7%를 넘지 않도록 제한 (모든 종목 대상)
MARGIN_RATE = "1.002"  # 수수료 및 마진 고려 (0.2% 추가)
APPLY_TO_ALL_STOCKS = "true"  # 사용자 지정종목, 급등주, 일반 종목 모두 7% 원칙 적용
```

### 가격별 매수 수량 제한
```
# 3만원 이하 종목
LOW_PRICE_THRESHOLD = "30000"  # 3만원 이하 기준
LOW_PRICE_MIN_QUANTITY = "10"  # 최소 10주 매수 (예산 제한 무시 가능)

# 20만원 이상 종목
HIGH_PRICE_THRESHOLD = "200000"  # 20만원 이상 기준
HIGH_PRICE_MAX_QUANTITY = "5"  # 최대 5주 제한

# 30만원 이상 종목 (소액 계좌)
ULTRA_HIGH_PRICE_THRESHOLD = "300000"  # 30만원 이상 기준
SMALL_ACCOUNT_LIMIT = "10000000"  # 예수금 1천만원 미만 기준
ULTRA_HIGH_PRICE_MAX_QUANTITY = "2"  # 최대 2주 제한
```

### 가격대별 기본 수량 기준
```
PRICE_THRESHOLDS = {
    "high_price_limit": "200000",  # 20만원 이상 -> 기본 10주
    "low_price_limit": "100000",   # 10만원 이하 -> 기본 50주
    "default_quantity": "20"       # 기타 -> 기본 20주
}
```

---

## 📊 매매 세션 및 시간 관리

### 장 시간 설정
```
MARKET_OPEN_TIME = "09:05"      # 장 시작 시간
MARKET_CLOSE_TIME = "15:30"     # 장 마감 시간
MORNING_SESSION_END = "12:00"   # 오전 세션 종료
AFTERNOON_SESSION_START = "13:00"  # 오후 세션 시작
AFTERNOON_SESSION_END = "15:20"    # 오후 세션 종료
AUTO_STOP_TIME = "15:20"        # 자동매매 종료 시간
```

### 매매 간격 설정
```
MORNING_TRADING_INTERVAL = "180"    # 오전 매매 간격 (3분)
AFTERNOON_TRADING_INTERVAL = "180"  # 오후 매매 간격 (3분)
```

### 전날 보유 잔고 처리
```
PREMARKET_LIQUIDATION_START = "09:05"  # 전날 잔고 처리 시작
PREMARKET_LIQUIDATION_END = "09:06"    # 전날 잔고 처리 종료
ENABLE_PREMARKET_LIQUIDATION = "true"  # 전날 잔고 처리 활성화
```

---

## 🚨 리스크 관리 및 긴급 매도

### 포지션 관리
```
MAX_POSITIONS = "5"           # 최대 보유 포지션 수
POSITION_SIZE_RATIO = "0.15"  # 포지션 크기 비율
MAX_POSITION_VALUE = "0.25"   # 최대 포지션 가치 비율
MIN_POSITION_VALUE = "0.05"   # 최소 포지션 가치 비율
```

### 손실 제한 및 익절 기준
```
DAILY_LOSS_LIMIT = "0.05"          # 일일 손실 한도 (5%)
TOTAL_RISK_LIMIT = "0.15"          # 총 리스크 한도 (15%)
MAX_CONSECUTIVE_LOSSES = "3"       # 최대 연속 손실 횟수
DRAWDOWN_LIMIT = "0.1"             # 최대 낙폭 한도 (10%)
PROFIT_TARGET = "0.07"             # 익절 목표 수익률 (7%)
ENABLE_PROFIT_TAKING = "true"      # 익절 기능 활성화
```

### 긴급 매도 규칙
```
ENABLE_CRASH_DETECTION = "true"     # 급락 감지 활성화
CRASH_THRESHOLD = "-3.0"            # 급락 임계값 (-3%)
VI_DETECTION = "true"               # VI(변동성완화장치) 감지
VOLUME_SPIKE_RATIO = "3.0"          # 거래량 급증 비율
IMMEDIATE_SELL_ON_CRASH = "true"    # 급락시 즉시 매도
IMMEDIATE_SELL_ON_VI = "true"       # VI 발동시 즉시 매도
```

### 거래량-주가 분석 기반 매매 원칙 (신규 추가)
```
# 핵심 매매 신호 규칙
VOLUME_PRICE_ANALYSIS = "true"      # 거래량-주가 분석 활성화

# 규칙 1: 주가 하락 + 거래량 증가 → 무조건 매도
DECLINE_WITH_VOLUME_SELL = "true"   # 하락+거래량증가 매도 활성화
DECLINE_THRESHOLD = "-1.0"          # 하락 판단 기준 (-1%)
VOLUME_INCREASE_RATIO = "1.2"       # 거래량 증가 기준 (20% 이상)
DECLINE_PERIOD_DAYS = "3"           # 하락 분석 기간 (3일)

# 규칙 2: 주가 횡보(1주일 이상) + 거래량 증가 → 무조건 매수
SIDEWAYS_WITH_VOLUME_BUY = "true"   # 횡보+거래량증가 매수 활성화
SIDEWAYS_PERIOD_DAYS = "7"          # 횡보 판단 기간 (7일)
SIDEWAYS_THRESHOLD = "2.0"          # 횡보 판단 기준 (가격 변동 2% 이내)
SIDEWAYS_VOLUME_RATIO = "1.2"       # 횡보시 거래량 증가 기준 (20% 이상)
SIDEWAYS_STABILITY = "0.7"          # 횡보 안정성 기준 (70% 이상)

# 매매 신호 우선순위
VOLUME_SIGNAL_PRIORITY = "1"        # 거래량 신호가 최우선 (1순위)
TECHNICAL_SIGNAL_PRIORITY = "2"     # 기술적 지표는 2순위
FUNDAMENTAL_SIGNAL_PRIORITY = "3"   # 펀더멘털 지표는 3순위
```

---

## 📱 텔레그램 알림 연동 정책

### 필수 알림 규칙 (모든 기능에 적용)
```
TELEGRAM_NOTIFICATION_ENABLED = "true"  # 텔레그램 알림 활성화
TELEGRAM_ACCOUNT_ALERT = "true"         # 계좌 변동 알림
TELEGRAM_BALANCE_ALERT = "true"         # 잔고 변경 알림
TELEGRAM_TRADING_ALERT = "true"         # 매매 알림
TELEGRAM_SYSTEM_ALERT = "true"          # 시스템 상태 알림
```

### 계좌 관련 필수 알림
```
# 계좌 조회/연결 시 알림
- 실전투자/모의투자 계좌 연결 시작
- 계좌 잔고 조회 완료 (예수금, 총평가액, 평가손익, 보유종목 수)
- 계좌 연결 실패/오류 발생

# 잔고 변동 시 알림
- 보유종목 매수/매도 완료
- 계좌 초기화 (전량매도) 완료
- 보유종목 선택매도 완료
```

### 구현 원칙
```
1. 모든 계좌/잔고 변동 기능은 텔레그램 알림을 기본 포함
2. 알림 실패시에도 주 기능은 정상 동작 유지
3. 비동기 전송으로 성능 영향 최소화
4. 알림 내용은 명확하고 구체적으로 작성
```

---

## 📋 주문 관리

### 주문 실행 설정
```
ORDER_TIMEOUT = "300"               # 주문 타임아웃 (5분)
MAX_ORDER_RETRIES = "3"             # 최대 재시도 횟수
PARTIAL_FILL_THRESHOLD = "0.8"      # 부분 체결 임계값 (80%)
PRICE_DEVIATION_LIMIT = "0.02"      # 가격 편차 한도 (2%)
```

---

## 🔍 모니터링 및 필터링

### 모니터링 주기
```
POSITION_CHECK_INTERVAL = "60"      # 포지션 체크 간격 (1분)
MARKET_SCAN_INTERVAL = "300"        # 시장 스캔 간격 (5분)
HEALTH_CHECK_INTERVAL = "600"       # 시스템 상태 체크 (10분)
DATA_REFRESH_INTERVAL = "900"       # 데이터 갱신 간격 (15분)
```

### 종목 필터링
```
MIN_VOLUME = "100000"               # 최소 거래량
MIN_MARKET_CAP = "1000"             # 최소 시가총액 (억원)
MAX_VOLATILITY = "0.15"             # 최대 변동성 (15%)
EXCLUDED_SECTORS = "[]"             # 제외 섹터 목록
BLACKLIST_STOCKS = "[]"             # 거래 금지 종목 목록
```

### 급등주 매매 특별 규칙
```
# 급등주 가격 범위 (완화됨)
SURGE_MIN_PRICE = "9000"            # 최소 가격 (9천원 이하 매수 금지)
SURGE_MAX_PRICE = "80000"           # 최대 가격 (50,000원 → 80,000원으로 확대)

# 급등주 매매 조건 (대폭 완화)
SURGE_MAX_BUY_COUNT = "8"           # 최대 매수 종목 수 (6개 → 8개 증가)
SURGE_HIGH_PRICE_THRESHOLD = "300000"  # 고가 기준 (20만원 → 30만원 확대)
SURGE_RSI_THRESHOLD = "80"          # RSI 과매수 기준 (80 이상만 제외)

# 급등주 익절 기준
SURGE_PROFIT_TARGET = "0.07"        # 7% 익절 기준
```

---

## 🕰️ 자동 프로그램 실행 설정

### 자동 시작 설정
```
AUTO_START_TIME = "09:10"       # 자동매매 시작 시간
AUTO_START_MOCK = "OFF"         # 모의투자 자동 시작 (ON/OFF)
AUTO_START_REAL = "OFF"         # 실전투자 자동 시작 (ON/OFF)
```

### 자동 종료 설정
```
AUTO_SHUTDOWN = "true"          # 15:20 자동 프로그램 종료
SAVE_DAILY_REPORT = "true"      # 종료 시 일일 리포트 자동 저장
```

### 자동 실행 동작
- 자동 시작이 ON으로 설정된 경우:
  - 프로그램 실행 시 주식 시장 시간 모니터링
  - 09:10에 자동으로 해당 매매 시작
  - 15:20에 자동으로 리포트 생성 후 프로그램 종료
- 자동 시작이 OFF인 경우:
  - 사용자가 직접 메뉴에서 매매 시작
  - 15:20에 자동으로 리포트 생성 후 프로그램 종료

---

## 📝 업데이트 이력

### v18.0 (2025-08-07)
- **거래량-주가 분석 기반 매매 원칙 신규 추가**:
  - **핵심 원칙 1**: 주가 하락 + 거래량 증가 → 무조건 매도 (매도 압력 감지)
  - **핵심 원칙 2**: 주가 횡보(1주일+) + 거래량 증가 → 무조건 매수 (지지선 돌파 준비)
- **매매 신호 우선순위 체계 도입**: 거래량 신호 > 기술적 지표 > 펀더멘털 지표
- **분석 매개변수 설정**: 하락 기준 -1%, 횡보 기준 2%, 거래량 증가 기준 20%
- **시스템 전반 적용**: 모든 매매 알고리즘에서 우선 적용되는 핵심 규칙으로 설정

### v17.1 (2025-08-02)
- **7% 익절 기준 추가**: 급등주 및 일반 매매 모두 7% 수익시 자동 익절
- **급등주 매매 조건 대폭 완화**: 
  - 매수 가격 범위: 9,000원~80,000원 (기존: ~50,000원)
  - 최대 매수 종목: 8개 (기존: 6개)
  - 고가 기준: 30만원 (기존: 20만원)
  - RSI 조건 완화: 80 이상만 제외 (기존: 점수 조건)
- **익절 기능 시스템화**: trading_rules.json에 profit_target, enable_profit_taking 추가

### v16.6 (2025-08-01)
- 자동 프로그램 실행 설정 추가
- 15:20 자동 종료 기능 구현
- 일일 리포트 자동 생성 기능 개선
- 09:10 자동 시작 스케줄러 추가

### v16.2 (2025-08-01)
- 사용자 지정종목에서 POSCO홀딩스(005490) 삭제
- HD현대일렉트릭, HD현대중공업은 유지 (5주씩)
- 지정종목 총 개수: 19개 → 17개

### v16.1 (2025-08-01)
- 사용자 지정종목에서 솔브레인/에이피알(357780) 삭제
- 지정종목 총 개수: 20개 → 19개

### v16.0 (2025-08-01)
- 예수금 7% 제한 규칙 추가
- 3만원 이하 종목 최소 10주 매수 규칙
- 20만원 이상 종목 5주 제한 규칙
- 30만원 이상 종목 2주 제한 규칙 (소액 계좌)
- HD현대일렉트릭, HD현대중공업 수량 5주로 조정

---

## ⚙️ 설정 변경 방법

1. 이 파일에서 원하는 설정값을 수정합니다.
2. "설정값 변경 적용" 요청을 하면 자동으로 프로그램에 반영됩니다.
3. 변경 내용은 자동으로 업데이트 이력에 기록됩니다.

**주의사항**: 
- 모든 설정값은 문자열 형태로 작성해야 합니다.
- 불린 값은 "true" 또는 "false"로 작성합니다.
- 배열 값은 JSON 형태로 작성합니다.