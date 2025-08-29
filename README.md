<<<<<<< HEAD
# 🚀 tideWise 자동매매 시스템

**한국투자증권 OpenAPI 기반 지능형 자동매매 시스템**

## 📋 개요

tideWise는 한국투자증권 OpenAPI를 활용한 고도화된 자동매매 시스템입니다. 알고리즘 기반의 지능형 매매 결정과 실시간 리스크 관리를 통해 안정적이고 효율적인 자동매매를 제공합니다.

### 🎯 핵심 기능

- ✅ **실전/모의투자** 자동매매 지원
- ✅ **동적 알고리즘 로딩** (사용자 정의 알고리즘 지원)
- ✅ **급등주 자동 감지** 및 매매
- ✅ **실시간 리스크 관리** (손절/익절 자동화)
- ✅ **텔레그램 알림** 실시간 매매 상황 전송
- ✅ **포지션 관리** 및 자동 종료

## 📁 디렉토리 구조

```
tideWise/
├── run.py                      # 메인 실행 파일
├── run_debug.py                # 디버그 실행 파일
├── support/                    # 핵심 지원 모듈
│   ├── simple_auto_trader.py   # 자동매매 엔진
│   ├── surge_stock_buyer.py    # 급등주 매수 시스템
│   ├── surge_stock_providers.py # 급등주 데이터 수집
│   ├── system_logger.py        # 시스템 로깅
│   ├── telegram_notifier.py    # 텔레그램 알림
│   ├── trading_rules.py        # 매매 규칙 관리
│   ├── api_connector.py        # KIS API 연동
│   ├── algorithm_loader.py     # 알고리즘 동적 로딩
│   ├── universal_algorithm_interface.py # 알고리즘 인터페이스
│   ├── advanced_sell_rules.py  # 고급 매도 규칙
│   └── enhanced_theme_stocks.py # 테마 종목 관리
├── Algorithm/                  # 매매 알고리즘 (사용자 정의)
├── Policy/                     # 프로젝트 정책 문서
│   ├── Register_Key/          # API 키 및 인증정보 설정
│   ├── Trading_Rule.md        # 매매 규칙 설정
│   └── CLAUDE.md              # 프로젝트 지침
├── Package-Backup/             # 버전별 백업 파일
├── report/                     # 매매 기록 및 리포트
└── systemlog/                  # 시스템 로그 파일
```

## ⚡ 빠른 시작

### 1. 환경 설정

```bash
# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows

# 필요한 패키지 설치
pip install requests aiohttp telegram
```

### 2. 한국투자증권 API 키 설정

Policy/Register_Key 폴더의 `Register_Key.md` 파일을 편집하여 API 키를 설정하세요:

```json
{
  "실전투자 계좌": "your_real_account",
  "실전투자계좌 password": "your_password",
  "APP KEY": "your_app_key",
  "APP SECRET KEY": "your_app_secret",
  "모의투자 계좌": "your_mock_account",
  "모의투자계좌 password": "your_mock_password",
  "모의투자 APP KEY": "your_mock_app_key",
  "모의투자 APP SECRET KEY": "your_mock_app_secret"
}
```

### 3. 자동매매 실행

```bash
# 일반 실행 (모의투자)
python run.py

# 디버그 모드 실행
python run_debug.py
```

## 🔧 사용법 상세

### 디버그 모드 메뉴

`run_debug.py` 실행 시 다음 옵션을 선택할 수 있습니다:

| 옵션 | 설명 |
|------|------|
| 1 | 실전투자 디버그 모드 (주의!) |
| 2 | 모의투자 디버그 모드 |
| 3 | API 연결 테스트 |
| 4 | 알고리즘 로딩 테스트 |
| 5 | 데이터 수집 테스트 |
| 6 | 전체 시스템 진단 |

### 알고리즘 관리

#### Algorithm 폴더
- 사용자 정의 알고리즘 파일을 저장하는 폴더
- 지원 형식: `.py`, `.pine`, `.js`, `.txt`, `.json`
- 시스템이 자동으로 감지하여 동적 로딩

#### 알고리즘 인터페이스
모든 알고리즘은 다음 메소드를 구현해야 합니다:
- `analyze(data)`: 주식 데이터 분석 후 매매 신호 반환
- `get_name()`: 알고리즘 이름 반환
- `get_version()`: 알고리즘 버전 반환
- `get_description()`: 알고리즘 설명 반환

## 📊 매매 기록 및 리포트

### 매매 기록 저장
- `report/` 폴더에 일별 매매 기록 저장
- CSV 형식으로 상세 거래 내역 관리
- 텔레그램을 통한 실시간 알림

### 시스템 로그
- `systemlog/` 폴더에 시스템 로그 저장
- 디버그 모드에서 상세 로그 기록
- 오류 및 예외 상황 추적

## ⚙️ 설정 커스터마이징

### 매매 규칙 설정

`Policy/Trading_Rule.md` 파일에서 매매 규칙을 설정할 수 있습니다:

#### 주요 매매 규칙

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `POSITION_SIZE_BUDGET_RATIO` | 0.07 | 예수금의 7% 단위로 매수 |
| `PROFIT_TARGET` | 0.07 | 7% 익절 목표 |
| `STOP_LOSS` | 0.03 | 3% 손절 기준 |
| `DAILY_LOSS_LIMIT` | 0.05 | 일일 5% 손실 한도 |
| `MAX_POSITIONS` | 5 | 최대 5개 종목 동시 보유 |

### 텔레그램 알림 설정

텔레그램 봇을 통한 실시간 매매 알림:
- 매수/매도 체결 알림
- 손익 상황 알림
- 시스템 오류 알림
- 일일 매매 결과 요약

### 급등주 감지 설정

- 상한가 근접 종목 자동 감지
- 거래량 급증 종목 모니터링
- 테마주 연동 매매
- VI(변동성완충장치) 발동 종목 대응

## 🔍 알고리즘 동적 로딩

### 알고리즘 추가 워크플로우

1. **Algorithm 폴더에 알고리즘 파일 추가**
   - Python 파일(.py) 또는 Pine Script 파일(.pine) 지원
   - 필수 메소드 구현: `analyze()`, `get_name()`, `get_version()`, `get_description()`

2. **시스템 재시작 없이 자동 감지**
   - 동적 로딩 시스템이 새 알고리즘 자동 인식
   - 런타임 중에도 알고리즘 변경 가능

3. **디버그 모드로 테스트**
   ```bash
   python run_debug.py
   # 옵션 4: 알고리즘 로딩 테스트 선택
   ```

4. **실제 매매에 적용**
   - 검증 완료 후 실제 매매 시스템에서 사용

## 📋 성과 지표

### 핵심 지표

- **일일 수익률** (Daily Return)
- **누적 수익률** (Cumulative Return)
- **승률** (Win Rate)
- **평균 수익** (Average Profit)
- **최대 손실** (Maximum Loss)
- **포지션 유지 시간** (Holding Period)

### 리스크 관리 지표

- **손절 실행률** (Stop Loss Execution Rate)
- **익절 실행률** (Take Profit Execution Rate)
- **포지션 관리** (Position Management)
- **자금 관리** (Money Management)

## ⚠️ 주의사항

### 투자 위험 경고

- **실전투자 주의**: 실제 자금 손실 가능성
- **모의투자 우선**: 충분한 테스트 후 실전 적용
- **시장 리스크**: 급변하는 시장 상황에 유의
- **알고리즘 한계**: 완전한 수익을 보장하지 않음

### 시스템 안정성

- **인터넷 연결**: 안정적인 네트워크 환경 필수
- **전력 공급**: 정전에 대비한 UPS 권장
- **시스템 모니터링**: 정기적인 로그 확인

### 권장사항

1. **소액으로 시작**: 초기에는 작은 금액으로 테스트
2. **정기적인 점검**: 매매 결과 정기 검토
3. **리스크 관리**: 손실 한도 엄격 준수
4. **지속적인 학습**: 시장 변화에 대응한 알고리즘 개선

## 🛠️ 문제 해결

### 자주 발생하는 오류

#### 1. API 연결 오류
```
해결방법: 
- Register_Key.md 파일의 키 값 확인
- 한국투자증권 API 서비스 상태 확인
- 네트워크 연결 상태 점검
```

#### 2. 알고리즘 로딩 실패
```
해결방법:
- Algorithm 폴더 내 알고리즘 파일 존재 확인
- 알고리즘 파일 문법 오류 검사
- 필수 메소드 구현 여부 확인
```

#### 3. 텔레그램 알림 실패
```
해결방법:
- 텔레그램 봇 토큰 확인
- 채팅방 ID 확인
- 인터넷 연결 상태 점검
```

### 로그 확인

모든 실행 로그는 `systemlog/` 폴더에 저장됩니다:

```bash
# 최신 로그 확인
tail -f systemlog/debug_YYYYMMDD_HHMMSS.log

# 오류만 필터링
grep ERROR systemlog/debug_YYYYMMDD_HHMMSS.log
```

## 🔄 지속적 개선

### 성과 모니터링

1. **일일 매매 기록** 정기 검토
2. **수익률 추이** 분석
3. **리스크 지표** 모니터링

### 알고리즘 최적화

1. **매매 규칙 조정**
2. **새로운 지표 추가**
3. **리스크 관리 강화**

## 📞 지원

문제가 발생하거나 개선 제안이 있으시면:

1. **로그 파일 확인** (`systemlog/` 폴더)
2. **설정 파일 점검** (`Policy/` 폴더)
3. **디버그 모드 실행** (상세한 진단 정보 확인)

---

## 📄 라이선스

이 프로젝트는 tideWise 자동매매 시스템입니다.

**⚠️ 투자에는 항상 위험이 따르며, 모든 투자 결정에 대한 책임은 투자자 본인에게 있습니다.**

**🚀 안전하고 체계적인 자동매매를 시작하세요!**
=======
# GPT4wiseTide
>>>>>>> 729688714eff0f3b2e273786484d053cddff8a2d
