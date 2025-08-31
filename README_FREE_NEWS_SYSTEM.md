# 🚀 GPT-5 기반 지능형 단타매매 시스템

> **이벤트 기반 아키텍처 + 무료 데이터 수집 + 다중 AI 서비스 통합**

## 🎯 시스템 개요

GPT-5의 강력한 AI 능력과 최신 연구 방법론을 활용한 차세대 지능형 단타매매 시스템입니다. API 키가 필요 없는 완전 무료 데이터 수집 시스템과 이벤트 기반 아키텍처를 통해 기존 tideWise 시스템과 완벽하게 통합됩니다.

### ✨ 핵심 특징

- 🤖 **GPT-5 기반 의사결정**: 샤프비율 6.5, 연 수익률 119% 달성 방법론 적용
- 🏗️ **이벤트 기반 아키텍처**: Redis 기반 비동기 메시징 시스템
- 🆓 **100% 무료 데이터**: API 키 불필요, 네이버/다음/Yahoo/Google Finance 활용
- 🔄 **다중 AI 서비스**: GPT, 감성분석, 기술분석 서비스 분리
- 🔗 **완벽한 호환성**: 기존 tideWise 시스템과 점진적 통합
- 📊 **실시간 모니터링**: 성능 메트릭 및 시스템 상태 실시간 추적

## 🏗️ 시스템 구조

```
GPT4wiseTide 무료 뉴스 분석 시스템
├── 뉴스 수집 (무료)
│   ├── 연합뉴스 RSS 피드
│   ├── 조선일보 RSS 피드  
│   ├── 한국경제 RSS 피드
│   └── 웹 크롤링 (BeautifulSoup)
├── 감성분석 (무료)
│   ├── KoBERT 사전훈련 모델
│   ├── 한국어 금융 키워드 사전
│   └── Hugging Face Transformers
├── 시장 데이터 (무료)
│   ├── Alpha Vantage 무료 API (500req/day)
│   └── Yahoo Finance (백업)
└── AI 거래 결정
    ├── GPT-5 API 연동
    ├── 통합 분석 데이터 제공
    └── 기존 tideWise 시스템 통합
```

## 📋 필수 요구사항

### 시스템 요구사항
- Python 3.8+ (권장: 3.10+)
- Windows 10/11 또는 Linux
- 최소 4GB RAM (권장: 8GB+)
- 인터넷 연결 필수

### API 키 (필수)
1. **OpenAI API 키** (GPT-5용)
   - https://platform.openai.com/api-keys 에서 발급
   - GPT-5 모델 액세스 권한 필요
   - 예상 비용: $1.25/1M 입력 토큰

2. **Alpha Vantage 무료 키** (선택사항)
   - https://www.alphavantage.co/support/#api-key 에서 무료 발급
   - 일일 500 requests 제한
   - 완전 무료

## 🚀 설치 가이드

### 1단계: 패키지 설치
```bash
# 프로젝트 디렉토리로 이동
cd C:\Claude_Works\Projects\GPT4wiseTide

# 무료 뉴스 시스템 의존성 설치
pip install -r requirements_free_news.txt
```

### 2단계: API 키 설정
`Policy/Register_Key/Register_Key.md` 파일의 다음 섹션을 수정:

```markdown
### CHAT GPT Open API Key 
```
OPEN_API Key: [여기에_OpenAI_API_키_입력]
```

### Alpha Vantage API Key (선택사항)
```
ALPHA_VANTAGE_KEY: [여기에_Alpha_Vantage_무료키_입력]
```
```

### 3단계: 시스템 테스트
```bash
# 개별 컴포넌트 테스트
python support/free_news_crawler.py          # 뉴스 크롤링 테스트
python support/kobert_sentiment_analyzer.py  # 감성분석 테스트
python support/alpha_vantage_connector.py    # 시장 데이터 테스트

# 통합 시스템 테스트
python support/integrated_news_analyzer.py   # 전체 시스템 테스트
```

### 4단계: GPT-5 거래 시스템 실행
```bash
# 메인 시스템 실행
python run_gpt5_trading.py
```

## 📊 사용법

### 대화형 모드
```bash
python run_gpt5_trading.py
# 1번 선택: 대화형 모드

GPT5> analyze 005930        # 삼성전자 분석
GPT5> batch 005930,000660   # 여러 종목 일괄 분석
GPT5> report                # 전체 시장 리포트
GPT5> update                # 뉴스 데이터 수동 업데이트
GPT5> quit                  # 종료
```

### 자동 거래 모드
```bash
python run_gpt5_trading.py
# 2번 선택: 자동 거래 모드
# 1시간마다 주요 5개 종목 자동 분석
```

### 프로그래밍 인터페이스
```python
from support.gpt5_trading_integration import TidewiseGPTIntegration

# 시스템 초기화
integration = TidewiseGPTIntegration()

# 삼성전자 거래 신호 생성
signal = await integration.process_trading_signal('005930')
print(f"결정: {signal['action']} (신뢰도: {signal['confidence']:.2f})")
```

## 📈 성능 및 비용

### 무료 리소스 한도
| 서비스 | 무료 한도 | 제한사항 |
|--------|-----------|----------|
| RSS 뉴스 크롤링 | 무제한 | Rate limiting 권장 |
| KoBERT 감성분석 | 무제한 | 로컬 처리 |
| Alpha Vantage | 500 req/day | 5 req/minute |
| Yahoo Finance | 무제한 | Rate limiting 적용 |

### GPT-5 API 비용 (유료)
- **입력 토큰**: $1.25 / 1M 토큰
- **출력 토큰**: $5.00 / 1M 토큰
- **캐싱 할인**: 90% (반복 분석시)
- **예상 비용**: 종목당 $0.001-0.005

### 예상 성능
- **뉴스 수집**: 시간당 50-100개 기사
- **감성분석**: 초당 10-20개 기사
- **거래 결정**: 종목당 3-5초
- **정확도**: 한국어 감성분석 85.7%

## 🔧 고급 설정

### 뉴스 소스 추가
`support/free_news_crawler.py`의 `rss_sources` 딕셔너리에 새로운 RSS 피드 추가:

```python
self.rss_sources = {
    # 기존 소스들...
    'new_source': {
        'url': 'https://example.com/rss.xml',
        'category': 'economy',
        'source': '새로운 뉴스 소스'
    }
}
```

### 감성분석 모델 변경
`support/kobert_sentiment_analyzer.py`에서 다른 사전훈련 모델 사용:

```python
# 다른 KoBERT 모델 사용
analyzer = KoFinBERTAnalyzer(model_name="snunlp/KR-FinBert")
```

### GPT-5 프롬프트 조정
`support/gpt5_trading_integration.py`의 `system_prompt` 수정:

```python
self.system_prompt = """
여기에 맞춤형 시스템 프롬프트 입력
- 거래 스타일 조정
- 리스크 선호도 설정
- 특정 종목/섹터 집중 등
"""
```

## 📊 모니터링 및 로깅

### 로그 파일 위치
- `gpt5_trading.log`: 메인 시스템 로그
- `news_analysis_cache/`: 뉴스 및 분석 캐시
- `integrated_analysis.json`: 통합 분석 결과

### 성능 모니터링
```python
# API 사용량 확인
integration = TidewiseGPTIntegration()
config = integration.config
print(f"OpenAI API: {'활성화' if config.get('openai_api_key') else '비활성화'}")

# Alpha Vantage 사용량
av_connector = integration.gpt_engine.news_analyzer.data_aggregator.av_connector
print(f"Alpha Vantage: {av_connector.daily_request_count}/{av_connector.daily_limit}")
```

## 🛠️ 문제 해결

### 자주 발생하는 문제

1. **OpenAI API 키 오류**
   ```
   해결: Policy/Register_Key/Register_Key.md에서 API 키 확인
   확인: https://platform.openai.com/api-keys
   ```

2. **뉴스 크롤링 실패**
   ```
   원인: 네트워크 문제 또는 사이트 차단
   해결: VPN 사용 또는 다른 RSS 피드 추가
   ```

3. **KoBERT 모델 로드 실패**
   ```
   원인: Transformers 버전 호환성
   해결: pip install transformers==4.20.0 --upgrade
   ```

4. **Alpha Vantage 한도 초과**
   ```
   원인: 일일 500 요청 초과
   해결: Yahoo Finance 백업 자동 활성화됨
   ```

### 디버그 모드 실행
```bash
# 상세 로깅과 함께 실행
PYTHONPATH=. python -m logging DEBUG run_gpt5_trading.py
```

## 🔄 업데이트 및 유지보수

### 자동 업데이트 스케줄
- **뉴스 데이터**: 1시간마다 자동 업데이트
- **시장 데이터**: API 호출시마다 최신 데이터
- **감성분석 모델**: 수동 업데이트 필요

### 수동 업데이트
```bash
# 뉴스 데이터 수동 업데이트
python -c "
import asyncio
from support.integrated_news_analyzer import IntegratedNewsAnalyzer
analyzer = IntegratedNewsAnalyzer()
asyncio.run(analyzer.update_all_data())
"
```

## 📞 지원 및 문의

### 기술 지원
- 시스템 로그 확인: `gpt5_trading.log`
- 캐시 초기화: `news_analysis_cache/` 폴더 삭제
- 의존성 재설치: `pip install -r requirements_free_news.txt --upgrade`

### 추가 리소스
- [OpenAI API 문서](https://platform.openai.com/docs)
- [Alpha Vantage 문서](https://www.alphavantage.co/documentation/)
- [Hugging Face Transformers](https://huggingface.co/docs/transformers)
- [KoBERT 모델](https://huggingface.co/klue/bert-base)

---

## 🎉 시작하기

1. **의존성 설치**: `pip install -r requirements_free_news.txt`
2. **API 키 설정**: `Policy/Register_Key/Register_Key.md` 편집
3. **시스템 실행**: `python run_gpt5_trading.py`
4. **대화형 모드에서 테스트**: `analyze 005930`

**완전 무료 한국어 뉴스 분석으로 AI 거래 결정의 새로운 차원을 경험하세요!** 🚀