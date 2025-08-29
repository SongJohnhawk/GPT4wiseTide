# K-AutoTrade 통합 연동 정보 관리

이 파일은 K-AutoTrade 시스템의 모든 API 키, 계좌 정보, 연동 토큰을 통합 관리하는 파일입니다.

> **⚠️ 보안 주의사항**
> - 이 파일은 민감한 정보를 포함하고 있습니다.
> - 절대 외부에 공유하거나 공개 저장소에 업로드하지 마세요.
> - 수정 후 반드시 K-AutoTrade를 재시작해야 변경사항이 적용됩니다.

---

## 1. 한국투자증권 OPEN API 설정

### 실전투자 계좌 정보
```
계좌번호: [67882340]
계좌 비밀번호: [1878]
APP KEY: [PS2GALh9ERMUhlVOOuZyw47gYBvzTTRUjvHd]
APP Secret KEY: [4PRt6hmL+XyQ0LNv5Be07CLJgUjdx/kZsD/2/ZOWw6FPap97VAN/BkIYckoUNlzRFoi7H264iNmJY4v4PsjYwv812EyOwoaXnFDhN0dh8Xyl5t9vl8gElkciMnU6acN2/dHgCYVIMRqVkY/HkL/MILaTG/sL5mEv7LC8ugiaLRm1T6QbL1E=]
```

### 모의투자 계좌 정보
```
계좌번호: [50146480]
계좌 비밀번호: [1848]
APP KEY: [PSzcJuOswpXZ2LUBtqzK3JE0Cqt7Xe6mTxw2]
APP Secret KEY: [afNS8Sd+JF2j+7VqONr3d8TS7tgnoiWNYnb9zXOeScPw2UX8FilYLGYLoA5dXQE+C+lZGdVShWb9Hb1cC2akSYCRRGux7cwot8By+PQybmOqMqpwyj6MrG8JioGtsw8ijzJN0FSL8fIwnp6Cr8me8FxcIqC4g/X+AbEZE5ozSzTsFj4nNOs=]
```

### API 호출 URL 정보
```
실전투자 REST URL: https://openapi.koreainvestment.com:9443
실전투자 Websocket URL: ws://ops.koreainvestment.com:21000
모의투자 REST URL: https://openapivts.koreainvestment.com:29443  
모의투자 Websocket URL: ws://ops.koreainvestment.com:21000
```

### OAuth 인증 방식
- REST 방식: 접근토큰(access_token) 발급 (/oauth2/tokenP)
- Websocket 방식: 실시간 접속키(approval_key) 발급 (/oauth2/Approval)


---

## 3. 텔레그램 봇 설정

### 봇 정보
```
Bot Name: KAutotrading_Bot
Bot URL: t.me/KAutotrading_Bot
```

### 연동 토큰
```
Bot Token: 7552128002:AAEZv76fDMkjr2AqWEbIFWCA9hSwRwWz_Yg
Chat ID: 5432568156
```

### 텔레그램 기능
- 자동매매 시작/종료 알림
- 매매 신호 실시간 알림
- 수익/손실 현황 알림
- 시스템 오류 알림

---

**설정 방법**:
1. 위의 템플릿에서 `[여기에...]` 부분을 실제 정보로 교체하세요.
2. 한국투자증권에서 발급받은 실제 API 키와 계좌 정보를 입력하세요.
3. KRX에서 발급받은 실제 API 키를 입력하세요.
4. 텔레그램 봇을 생성하고 실제 토큰 정보를 입력하세요.

**마지막 업데이트**: 2025-08-20
**다음 점검 예정**: 2025-09-20