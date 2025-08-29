# tideWise 리포팅 시스템 통합 가이드

## 개요

tideWise 시스템에 포괄적인 리포팅 및 시장 캘린더 자동화 기능을 추가했습니다.

## 핵심 컴포넌트

### 1. HolidayProvider (`support/holiday_provider.py`)
- **목적**: 한국거래소(KRX) 휴장일 정보 관리
- **기능**: 
  - KRX OTP 플로우를 통한 휴장일 자동 수집
  - 캐시 기반 고성능 휴장일 조회
  - ISO 주/월 기준 마지막 거래일 계산

### 2. TradeReporter (`support/trade_reporter.py`)
- **목적**: 거래 기록 수집 및 리포트 생성
- **기능**:
  - 세션별 거래 기록 관리
  - JSON/HTML 형식 리포트 생성
  - 내장 차트 (일일 손익, 누적 손익)
  - 주간/월간 통합 리포트 자동 생성

### 3. ReportingIntegration (`support/report_integration.py`)
- **목적**: 기존 매매 시스템과 리포팅 연동
- **기능**:
  - 매매 함수 데코레이터 제공
  - 거래 기록 자동화
  - 세션 생명주기 관리

## 디렉토리 구조

```
Report/
├── session_2025-08-22.json    # 세션별 리포트 (JSON)
├── session_2025-08-22.html    # 세션별 리포트 (HTML)
├── weekly_2025-08-22.json     # 주간 통합 리포트
├── weekly_2025-08-22.html     # 주간 통합 리포트
├── monthly_2025-08-31.json    # 월간 통합 리포트
└── monthly_2025-08-31.html    # 월간 통합 리포트
```

## 기존 시스템 통합 방법

### 1. 자동매매 시스템 통합

**`support/production_auto_trader.py` 수정:**

```python
from .report_integration import reporting_integration, log_buy_order, log_sell_order

class ProductionAutoTrader:
    async def start_trading(self):
        # 리포팅 세션 시작
        await reporting_integration.start_trading_session(self.account_type)
        
        try:
            # 기존 매매 로직 실행
            await self._run_trading_loop()
            
        finally:
            # 리포팅 세션 종료
            await reporting_integration.end_trading_session(self.account_type)
    
    async def execute_buy_order(self, symbol, quantity, price, algorithm):
        # 기존 매수 로직
        result = await self._place_buy_order(symbol, quantity, price)
        
        if result['success']:
            # 거래 기록 추가
            await log_buy_order(symbol, quantity, price, algorithm, self.account_type)
        
        return result
    
    async def execute_sell_order(self, symbol, quantity, price, buy_price, algorithm):
        # 기존 매도 로직
        result = await self._place_sell_order(symbol, quantity, price)
        
        if result['success']:
            # 거래 기록 추가
            await log_sell_order(symbol, quantity, price, buy_price, algorithm, self.account_type)
        
        return result
```

### 2. 단타매매 시스템 통합

**`support/minimal_day_trader.py` 수정:**

```python
from .report_integration import with_reporting, log_buy_order, log_sell_order

class MinimalDayTrader:
    @with_reporting  # 데코레이터로 자동 리포팅 적용
    async def start_day_trading(self, account_type='MOCK'):
        # 기존 단타매매 로직
        await self._execute_day_trading_logic()
    
    async def process_surge_stock(self, stock_info, algorithm):
        # 매수 실행
        if self._should_buy(stock_info):
            await log_buy_order(
                symbol=stock_info['symbol'],
                quantity=stock_info['quantity'],
                price=stock_info['price'],
                algorithm=algorithm,
                account_type=self.account_type
            )
        
        # 매도 실행
        if self._should_sell(stock_info):
            await log_sell_order(
                symbol=stock_info['symbol'],
                quantity=stock_info['quantity'],
                price=stock_info['current_price'],
                buy_price=stock_info['buy_price'],
                algorithm=algorithm,
                account_type=self.account_type
            )
```

### 3. run.py 메인 실행 파일 수정

```python
import asyncio
from support.report_integration import get_reporting_status

async def run_mock_trading():
    """모의투자 자동매매 실행"""
    from support.production_auto_trader import ProductionAutoTrader
    
    trader = ProductionAutoTrader(account_type='MOCK')
    await trader.start_trading()  # 리포팅 자동 적용

async def run_day_trading():
    """단타매매 실행"""
    from support.minimal_day_trader import MinimalDayTrader
    
    trader = MinimalDayTrader()
    await trader.start_day_trading(account_type='MOCK')  # 리포팅 자동 적용

def main():
    print("tideWise 시작")
    
    # 리포팅 상태 확인
    status = get_reporting_status()
    print(f"리포트 디렉토리: {status['report_directory']}")
    
    # 기존 메뉴 로직...
```

## 사용법

### 1. 수동 리포팅

```python
from support.report_integration import reporting_integration

# 세션 시작
await reporting_integration.start_trading_session('MOCK')

# 거래 기록
trade_record = reporting_integration.create_trade_record(
    symbol='005930',
    action='BUY',
    quantity=10,
    price=70000,
    amount=700000,
    algorithm='Enhanced_DavidPaul_Trading'
)
await reporting_integration.record_trade(trade_record)

# 세션 종료
await reporting_integration.end_trading_session('MOCK')
```

### 2. 자동 리포팅 (데코레이터)

```python
from support.report_integration import with_reporting

@with_reporting
async def my_trading_function(account_type='MOCK'):
    # 거래 로직 실행
    # 세션은 자동으로 시작/종료됨
    pass
```

### 3. 개별 거래 기록

```python
from support.report_integration import log_buy_order, log_sell_order

# 매수 기록
await log_buy_order('005930', 10, 70000, 'MyAlgorithm', 'MOCK')

# 매도 기록
await log_sell_order('005930', 10, 72000, 70000, 'MyAlgorithm', 'MOCK')
```

## 리포트 자동 생성 규칙

### 세션 리포트
- **생성 시점**: 거래 세션 종료시
- **파일명**: `session_YYYY-MM-DD.json/html`

### 주간 리포트
- **생성 시점**: ISO 주 마지막 거래일 (보통 금요일)
- **휴장일 처리**: 금요일이 휴장일이면 이전 거래일에 생성
- **파일명**: `weekly_YYYY-MM-DD.json/html`

### 월간 리포트
- **생성 시점**: 월 마지막 거래일
- **휴장일 처리**: 마지막 날이 휴장일이면 이전 거래일에 생성
- **파일명**: `monthly_YYYY-MM-DD.json/html`

## HTML 리포트 특징

- **자체 완결형**: 외부 CDN 의존성 없음
- **내장 차트**: Canvas 기반 일일/누적 손익 차트
- **반응형 디자인**: 모바일/데스크톱 호환
- **한국어 지원**: 완전한 한국어 인터페이스

## 테스트 방법

```bash
# 리포팅 시스템 테스트
cd tests
python test_reporting_system.py

# 실제 매매 시스템에서 테스트
python test_complete_trading.py
```

## 설정 파일

캐시 파일이 자동 생성됩니다:
- `support/krx_holidays_cache.json`: 휴장일 캐시
- `Report/`: 모든 리포트 파일

## 성능 최적화

- **캐시 기반**: 휴장일 정보 메모리 캐시
- **월간 업데이트**: KRX 데이터는 월 1회만 갱신
- **경량 HTML**: 외부 라이브러리 없는 순수 HTML/JS
- **비동기 처리**: 모든 리포팅 작업 비동기 실행

## 에러 처리

- **KRX 연결 실패**: 기본 공휴일로 폴백
- **파일 쓰기 실패**: 로그 기록 및 계속 진행
- **잘못된 거래 데이터**: 검증 후 무시
- **리포트 생성 실패**: 로그 기록, 다음 기회에 재시도