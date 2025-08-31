# 🆓 완전 무료 주식 데이터 수집 시스템

## 🎯 개요
**100% 무료** 주식 데이터 및 뉴스 수집 시스템 - API 키 불필요!

### ✨ 핵심 특징
- 🚫 **API 키 불필요**: 모든 데이터 소스가 무료
- 🇰🇷 **한국 주식**: 네이버, 다음 금융 크롤링
- 🌍 **글로벌 주식**: Yahoo Finance (yfinance), Google Finance 크롤링
- 📰 **실시간 뉴스**: RSS 피드 기반 무료 뉴스 수집
- 🤖 **스마트 크롤링**: 2024 최신 안티스크래핑 우회 기술 적용
- 📊 **통합 분석**: 여러 소스 데이터 자동 집계

## 🏗️ 시스템 구조

```
완전 무료 데이터 시스템
├── 한국 주식 (크롤링)
│   ├── 네이버 금융 (BeautifulSoup)
│   ├── 다음 금융 (BeautifulSoup)
│   └── 실시간 가격, 거래량, 시가/고가/저가
├── 글로벌 주식 (라이브러리 + 크롤링)
│   ├── Yahoo Finance (yfinance 라이브러리)
│   ├── Google Finance (웹 크롤링)
│   └── 미국, 유럽, 아시아 시장 지원
├── 뉴스 수집 (RSS)
│   ├── 연합뉴스, 조선일보, 한국경제
│   └── 금융 관련 뉴스 필터링
└── 스마트 기능
    ├── User-Agent 로테이션
    ├── 랜덤 딜레이
    ├── 캐싱 시스템
    └── 에러 복구
```

## 📋 설치 방법

### 1. 필수 패키지 설치
```bash
pip install -r requirements_free_system.txt
```

### 2. 선택적 고급 기능 (필요시)
```bash
# 동적 웹페이지 크롤링
pip install playwright
playwright install chromium

# 고급 안티탐지 기능
pip install undetected-chromedriver
```

## 🚀 사용법

### 빠른 시작
```python
from support.integrated_free_data_system import IntegratedFreeDataSystem

# 시스템 초기화
system = IntegratedFreeDataSystem()

# 시장 리포트 생성
report = await system.generate_market_report()
print(report)
```

### 개별 주식 데이터 수집

#### 한국 주식
```python
from support.free_stock_data_collector import FreeStockDataCollector

collector = FreeStockDataCollector()

# 네이버에서 삼성전자 데이터
naver_data = await collector.get_naver_stock_data('005930')
print(f"삼성전자: {naver_data.current_price:,}원")

# 다음에서 SK하이닉스 데이터
daum_data = await collector.get_daum_stock_data('000660')
print(f"SK하이닉스: {daum_data.current_price:,}원")
```

#### 미국 주식
```python
# Yahoo Finance 사용 (yfinance 라이브러리)
yahoo_data = collector.get_yahoo_finance_data('AAPL')
print(f"Apple: ${yahoo_data.current_price:.2f}")

# Google Finance 크롤링
google_data = await collector.get_google_finance_data('GOOGL:NASDAQ')
print(f"Google: ${google_data.current_price:.2f}")
```

### 통합 데이터 수집
```python
from support.integrated_free_data_system import IntegratedFreeDataSystem

system = IntegratedFreeDataSystem()

# 한국 주식 전체
korean_stocks = await system.collect_korean_stock_data()

# 미국 주식 전체
us_stocks = await system.collect_us_stock_data()

# 뉴스 수집
news = await system.collect_news_data()

# 종합 리포트
report = await system.generate_market_report()
```

### 실시간 모니터링
```python
# 30분마다 자동 업데이트
await system.run_monitoring(interval_minutes=30)
```

## 📊 데이터 소스 및 제한사항

### 한국 주식
| 소스 | 제한사항 | 권장 딜레이 |
|------|----------|------------|
| 네이버 금융 | 과도한 요청시 일시 차단 | 1-2초 |
| 다음 금융 | IP 기반 rate limiting | 1-2초 |

### 글로벌 주식
| 소스 | 제한사항 | 권장 딜레이 |
|------|----------|------------|
| Yahoo Finance | 무제한 (yfinance) | 0.5초 |
| Google Finance | 봇 탐지 시스템 | 2-3초 |

### 뉴스 RSS
| 소스 | 제한사항 | 업데이트 주기 |
|------|----------|--------------|
| 연합뉴스 | 없음 | 실시간 |
| 조선일보 | 없음 | 실시간 |
| 한국경제 | 없음 | 실시간 |

## 🛡️ 안티스크래핑 우회 기술

### 적용된 2024 최신 기술
1. **User-Agent 로테이션**: 최신 브라우저 시뮬레이션
2. **랜덤 딜레이**: 인간 행동 패턴 모방
3. **헤더 최적화**: 실제 브라우저 헤더 구조
4. **세션 관리**: 쿠키 및 세션 유지
5. **에러 복구**: 자동 재시도 및 대체 소스

### 고급 옵션 (필요시)
- Playwright: JavaScript 렌더링 지원
- Undetected ChromeDriver: 고급 봇 탐지 우회
- 프록시 로테이션: IP 차단 방지

## 🔧 트러블슈팅

### 네이버/다음 크롤링 실패
```python
# User-Agent 업데이트
collector.user_agents.append('새로운 User-Agent 문자열')

# 딜레이 증가
await asyncio.sleep(3)  # 3초 대기
```

### Yahoo Finance 오류
```bash
# yfinance 업데이트
pip install --upgrade yfinance
```

### 인코딩 오류
```python
# UTF-8 인코딩 강제
response.encoding = 'utf-8'
```

## 📈 성능 최적화

### 캐싱 활용
```python
# 5분 캐시 활성화
data = await manager.get_stock_data(
    symbol='AAPL',
    use_cache=True,
    cache_ttl=300  # 5분
)
```

### 병렬 처리
```python
# 여러 종목 동시 수집
tasks = [
    collector.get_naver_stock_data('005930'),
    collector.get_naver_stock_data('000660'),
    collector.get_naver_stock_data('035420')
]
results = await asyncio.gather(*tasks)
```

## 🧪 테스트

### 전체 시스템 테스트
```bash
python test_free_system.py
```

### 개별 컴포넌트 테스트
```python
# 주식 수집기 테스트
await test_stock_collector()

# 통합 시스템 테스트
await test_integrated_system()

# 데이터 소스 테스트
await test_data_sources()
```

## 📝 주의사항

1. **과도한 요청 금지**: 서버 부하 방지를 위해 적절한 딜레이 사용
2. **robots.txt 준수**: 웹사이트의 크롤링 정책 확인
3. **개인 용도**: 상업적 사용시 법적 검토 필요
4. **데이터 정확성**: 크롤링 데이터는 지연될 수 있음

## 🔄 업데이트 내역

### v2.0.0 (2024.12)
- ✅ API 키 의존성 완전 제거
- ✅ 네이버/다음 주식 크롤링 추가
- ✅ yfinance 라이브러리 통합
- ✅ 2024 최신 안티스크래핑 기술 적용
- ✅ 통합 무료 시스템 구축

### v1.0.0 (2024.11)
- 초기 버전 (API 키 필요)

## 📞 지원

문제 발생시 Issue를 생성하거나 다음 파일들을 확인하세요:
- `support/free_stock_data_collector.py` - 주식 데이터 수집
- `support/integrated_free_data_system.py` - 통합 시스템
- `test_free_system.py` - 테스트 및 예제

## 📄 라이선스

MIT License - 자유롭게 사용 가능 (단, 웹사이트 이용약관 준수 필요)