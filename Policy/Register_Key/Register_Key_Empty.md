# tideWise 통합 연동 정보 관리

이 파일은 tideWise 시스템의 모든 API 키, 계좌 정보, 연동 토큰을 통합 관리하는 파일입니다.

> **[주의] 보안 주의사항**
> - 이 파일은 민감한 정보를 포함하고 있습니다.
> - 절대 외부에 공유하거나 공개 저장소에 업로드하지 마세요.
> - 수정 후 반드시 tideWise를 재시작해야 변경사항이 적용됩니다.

---

## 한국투자증권 연동 정보

### 실전투자 계좌 정보
```
APP KEY: [test_real_app_key]
APP Secret KEY: [test_real_app_secret]
계좌번호: [12345678-01]
계좌 비밀번호: [1234]
```

### 모의투자 계좌 정보
```
APP KEY: [test_mock_app_key]
APP Secret KEY: [test_mock_app_secret]
계좌번호: [50000000-01]
계좌 비밀번호: [0000]
```

### API 호출 URL 정보
```
실전투자 REST URL: https://openapi.koreainvestment.com:9443
실전투자 Websocket URL: ws://ops.koreainvestment.com:21000
모의투자 REST URL: https://openapivts.koreainvestment.com:29443
모의투자 Websocket URL: ws://ops.koreainvestment.com:31000
```

---

## KRX API 인증키

### KRX API 인증키
```
KRX API Key: [test_krx_api_key]
```

---

## 연동 토큰

### 텔레그램 봇 설정
```
Bot Token: [test_telegram_bot_token]
Chat ID: [test_telegram_chat_id]
```

---

**마지막 업데이트**: 2024-12-19