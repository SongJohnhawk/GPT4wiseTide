# 단타매매 실행 순차적 프로세스 상세 분석
## 📅 기록일시: 2025-08-31

---

## 📋 단타매매 프로세스 단계별 실행 흐름

### 🚀 **1단계: 시스템 초기화 (INIT Phase)**
**코드 위치**: `support/minimal_day_trader.py:86-105`
**함수**: `async def run(self)`

```python
async def run(self):
    self.is_running = True
    self.stop_requested = False
    
    # 1.1 시스템 초기화 실행
    if not await self._initialize_systems():
        return False
```

#### **세부 프로세스 (1.1):**
- **API 연결 초기화**: KIS OpenAPI 토큰 발급 및 연결 확인
- **세션 계좌 관리자 초기화**: 실시간 계좌 정보 관리 객체 생성
- **메모리 관리자 초기화**: 거래 후 계좌 상태 갱신 관리
- **텔레그램 알림 초기화**: 실시간 알림 시스템 설정
- **계좌 정보 조회**: 초기 계좌 잔고 및 보유 종목 확인
- **종목 데이터 로드**: 급등종목 데이터 수집 준비

---

### 🔄 **2단계: 연결 및 사전 초기화 (CONNECTION Phase)**
**코드 위치**: `support/minimal_day_trader.py:123-131`
**함수**: `_pre_day_trading_initialization()`

```python
if not await self._pre_day_trading_initialization():
    return False
```

#### **세부 프로세스 (2.1-2.6):**
- **2.1 계좌 조회**: 서버 연결 확인 (최대 3회 재시도)
- **2.2 토큰 검증**: API 액세스 토큰 유효성 확인
- **2.3 실시간 계좌 정보 업데이트**: 예수금, 주문가능금액, 보유종목 조회
- **2.4 전날잔고처리**: 이전일 보유종목 매도/보유 결정 (`_execute_balance_cleanup()`)
- **2.5 급등종목 수집**: 한투 API로 실시간 급등종목 수집 (최대 10개)
- **2.6 텔레그램 시작 알림**: 계좌 정보 및 급등종목 정보 전송

---

### 🔁 **3단계: 단타매매 순환 실행 (TRADING Phase)**
**코드 위치**: `support/minimal_day_trader.py:144-201`
**함수**: `_execute_day_trading_cycle(cycle_count)`

```python
while self.is_running and not self.stop_requested:
    cycle_count += 1
    cycle_result = await self._execute_day_trading_cycle(cycle_count)
```

#### **각 사이클별 세부 프로세스:**

##### **3.1 급등종목 재수집** (매 사이클마다)
**코드**: `support/minimal_day_trader.py:513-527`
```python
if self.algorithm and hasattr(self.algorithm, 'collect_surge_stocks'):
    surge_collection_success = await self.algorithm.collect_surge_stocks(self)
```

##### **3.2 계좌 정보 업데이트**
**코드**: `support/minimal_day_trader.py:529-540`
```python
await self.memory_manager.update_account_info()
account_info = self.memory_manager.get_account_info()
```

##### **3.3 현재 포지션 확인**
**코드**: `support/minimal_day_trader.py:541-562`
```python
current_positions_list = self.memory_manager.get_positions()
position_count = len(current_positions_list)
```

##### **3.4 매도 신호 처리** (보유 종목 대상)
**코드**: `support/minimal_day_trader.py:564-565`
**함수**: `_process_sell_signals(current_positions)`

**매도 처리 세부 단계:**
- **3.4.1** 보유 종목별 현재 데이터 조회: `_get_stock_current_data(stock_code)`
- **3.4.2** **🤖 AI 알고리즘 분석**: `_analyze_with_algorithm(stock_code, stock_data, is_position=True)`
  - Claude + Gemini 하이브리드 AI 엔진 사용
  - 펀더멘털 + 기술적 분석 결합
  - 신뢰도 기반 매도 결정
- **3.4.3** 매도 조건 확인:
  - AI 신호가 'SELL'
  - 손절 조건 (-3% 이하)
  - 익절 조건 (+2% 이상)
- **3.4.4** 매도 주문 실행: `_execute_sell_order()` 및 결과 기록

##### **3.5 매수 신호 처리** (신규 종목 대상)
**코드**: `support/minimal_day_trader.py:567-575`
**함수**: `_process_buy_signals(account_info, current_positions)`

**매수 처리 세부 단계:**
- **3.5.1** 매수 가능 현금 확인 (최소 10,000원)
- **3.5.2** 단타 매수 후보 종목 선별: `_select_day_trade_candidates()` - 급등종목 기반
- **3.5.3** 종목별 분석 (최대 10개):
  - 현재가, 전일대비, 거래량 조회: `_get_stock_current_data(symbol)`
  - **🤖 AI 알고리즘 분석**: `_analyze_with_algorithm(symbol, stock_data, is_position=True)`
    - Claude: 뉴스/감정 분석 (60% 가중치)
    - Gemini: 기술적 지표 분석 (40% 가중치)
    - 하이브리드 융합 결정
  - 매수 조건 확인: 신호='BUY' & 신뢰도 > 임계값
- **3.5.4** 매수 주문 실행: `_execute_buy_order()` 및 결과 기록

##### **3.6 사이클 결과 정리 및 전송**
**코드**: `support/minimal_day_trader.py:577-588`
```python
cycle_result = {
    'cycle_number': cycle_number,
    'timestamp': start_time.strftime('%H:%M:%S'),
    'account_balance': account_info.get('cash_balance', 0),
    'position_count': position_count,
    'sell_results': sell_results,
    'buy_results': buy_results,
    'session_stats': self.memory_manager.get_session_stats()
}
```

##### **3.7 사이클 간격 대기**
**코드**: `support/minimal_day_trader.py:187-201`
```python
dynamic_interval = self._get_cycle_interval()
await self._safe_sleep(dynamic_interval, f"사이클 {cycle_count + 1}")
```

**동적 사이클 간격:**
- 기본 3분 (180초) 간격
- 시간대별 동적 조정 가능
- 오류 발생 시 30초 대기 후 재시도

---

### 🏁 **4단계: 종료 처리 (FINALIZATION)**
**코드 위치**: `support/minimal_day_trader.py:203-221`
**함수**: `_finalize_day_trading()`

```python
await self._finalize_day_trading()

# finally 블록에서:
self.is_running = False
if self.account_manager:
    self.account_manager.end_session()
```

#### **종료 처리 세부 단계:**
- **4.1** 최종 계좌 상태 조회 및 기록
- **4.2** 세션 종료 처리
- **4.3** 텔레그램 종료 알림 전송
- **4.4** 리소스 정리 및 로그 기록

---

## ⏱️ **실제 실행 시간 및 주기**

### 시간 분석
- **초기화**: 약 10-15초
- **각 사이클**: 약 3-5분 (AI 분석 시간 + 3분 대기)
- **일일 총 사이클**: 약 100-130회 (09:05-15:20 기준)
- **매도 분석**: 보유 종목당 약 2-3초 (AI 병렬 처리)
- **매수 분석**: 급등종목 10개당 약 20-30초 (AI 순차 분석)

### 거래 시간 관리
- **시장 오픈**: 09:05 KST
- **자동 중단**: 15:20 KST  
- **시장 마감**: 15:30 KST
- **전체 운영시간**: 약 6시간 15분

---

## 🧠 **AI 분석 프로세스 상세**

### AI 엔진 호출 구조
**함수**: `_analyze_with_algorithm(stock_code, stock_data, is_position=True)`

#### 1. 시장 컨텍스트 생성
```python
context = MarketContext(
    symbol=stock_code,
    current_price=stock_data['current_price'],
    volume=stock_data['volume'],
    price_change_pct=stock_data['change_rate'],
    technical_indicators=stock_data.get('indicators', {}),
    news_sentiment=stock_data.get('news', {}),
    market_conditions=stock_data.get('market', {}),
    timestamp=datetime.now()
)
```

#### 2. 하이브리드 AI 분석 실행
```python
# Claude + Gemini 병렬 분석
claude_task = self._analyze_with_claude(context)
gemini_task = self._analyze_with_gemini(context)

claude_result, gemini_result = await asyncio.gather(
    claude_task, gemini_task,
    return_exceptions=False
)
```

#### 3. 결과 융합 및 결정
```python
decision = self._fuse_decisions(claude_result, gemini_result, context)
# 가중치 적용: Claude(0.6) + Gemini(0.4)
# 안전 규칙: 불일치 시 HOLD 선택
```

#### 4. 최종 매매 결정
```python
DecisionResult(
    symbol=stock_code,
    decision="BUY|SELL|HOLD",
    confidence=weighted_confidence,  # 0.0 ~ 1.0
    reasoning="🤖 Claude + 🔍 Gemini 분석 결과"
)
```

---

## 🔄 **순환 구조 및 예외 처리**

### 순환 제어
- **무한 루프**: `while self.is_running and not self.stop_requested`
- **중단 조건**: 
  - 파일 기반 중단 신호 (`STOP_DAYTRADING.signal`)
  - 시장 마감 시간 초과 (15:20)
  - 서버 연속 오류 (3회 이상)
- **오류 복구**: 개별 사이클 오류 시 30초 대기 후 다음 사이클 계속

### AI 분석 안전장치
- **타임아웃**: AI API 호출 10초 제한
- **재시도**: 최대 3회 재시도
- **안전모드**: 분석 실패 시 즉시 HOLD 결정
- **로깅**: 모든 AI 호출 및 결과 상세 기록

---

## 📊 **매매 규칙 및 리스크 관리**

### 포지션 관리
- **최대 포지션**: 5개 종목 동시 보유
- **포지션 크기**: 종목당 가용자금의 7% 이하
- **진입 조건**: AI 신뢰도 > 임계값 & BUY 신호

### 손익 관리
- **자동 손절**: -3% 손실 시 무조건 매도
- **자동 익절**: +2% 수익 시 무조건 매도
- **일일 손실 한도**: 총 자금의 5%

### AI 신뢰도 기반 의사결정
```python
# 매수 결정 로직
if (signal_result.get('signal') == 'BUY' and 
    signal_result.get('confidence', 0) > self.confidence_threshold):
    # 매수 주문 실행
    
# 매도 결정 로직
if (signal_result.get('signal') == 'SELL' or 
    self._check_stop_loss_condition() or
    self._check_take_profit_condition()):
    # 매도 주문 실행
```

---

## 🎯 **핵심 특징 및 혁신사항**

### 🚀 **AI 기반 의사결정**
- **이중 검증**: Claude(펀더멘털) + Gemini(기술적) 분석
- **실시간 학습**: 매 사이클마다 급등종목 재분석
- **상황 인식**: 보유종목 vs 신규종목 구분 분석

### 🔄 **적응형 시스템**
- **동적 사이클**: 시장 상황에 따른 간격 조정
- **유연한 가중치**: AI 모델별 기여도 실시간 조정
- **리스크 적응**: 시장 변동성에 따른 포지션 조정

### 🛡️ **안전 우선**
- **보수적 접근**: 불확실 시 항상 HOLD 선택
- **다중 안전장치**: API, 시간, 금액, 포지션 제한
- **투명한 기록**: 모든 결정 과정 상세 로깅

---

**분석 완료 일시**: 2025-08-31 21:35
**시스템 버전**: MinimalDayTrader v11.0
**AI 엔진**: Claude + Gemini 하이브리드
**상태**: ✅ 완료