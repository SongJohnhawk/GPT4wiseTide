# GPT4wiseTide 프로젝트 지침서

## 🎯 핵심 원칙: Register_Key.md 중앙화 관리

### **절대 원칙 (MANDATORY RULES)**

```yaml
GPT4wiseTide API 키 관리 절대 원칙:

1. 단일 소스 원칙 (Single Source of Truth):
   ✅ 모든 API 키는 오직 "Policy/Register_Key/Register_Key.md"에서만 관리
   ❌ 어떤 코드에도 하드코딩 절대 금지  
   ❌ 환경변수(.env) 사용 금지
   ❌ 별도 JSON/YAML 설정파일 생성 금지
   ❌ Fallback 시스템으로 하드코딩 생성 금지

2. 메뉴 통합 원칙:
   ✅ "메인메뉴 → 3. Setup → 1. Register_Key (통합 연동정보 관리)" 경로만 사용
   ✅ 사용자는 이 메뉴를 통해서만 API 키 수정
   ✅ 파일 편집 후 시스템 재시작 필수 안내

3. 코드 참조 원칙:
   ✅ 모든 API/로그인 정보는 AuthoritativeRegisterKeyLoader를 통해서만 접근
   ✅ AIAPIManager 클래스를 통한 AI 엔진 설정 관리
   ❌ 다른 방법으로 API 키 읽기 절대 금지
   ✅ 실패시 명확한 오류 메시지와 Register_Key.md 파일 수정 안내

4. 확장 원칙:
   ✅ 새로운 API (Claude, Gemini 등) 추가시 Register_Key.md에 섹션 추가
   ✅ 기존 AuthoritativeRegisterKeyLoader 클래스 확장하여 새 API 지원
   ❌ 절대 별도 설정 시스템 만들지 않음
   ❌ Fallback이나 대체 시스템 구축 금지
```

---

## 🏗️ 아키텍처 구조

### **1. Register_Key.md 파일 구조**

```markdown
# K-AutoTrade 통합 연동 정보 관리

## 1. 한국투자증권 OPEN API 설정
### 실전투자 계좌 정보
### 모의투자 계좌 정보
### API 호출 URL 정보

## 3. 텔레그램 봇 설정  
### 봇 정보
### 연동 토큰

## 4. AI 엔진 API 설정
### OpenAI GPT API 설정
### Claude API 설정 (Anthropic)
### Gemini API 설정 (Google)
### AI 엔진 조합 설정
```

### **2. 코드 아키텍처**

```python
# 계층 구조
Register_Key.md (단일 소스)
    ↓
AuthoritativeRegisterKeyLoader (파싱 및 로드)
    ↓
AIAPIManager (AI 설정 전용 관리)
    ↓
Claude/Gemini/Hybrid 엔진들 (실제 사용)
```

**핵심 클래스:**
- `AuthoritativeRegisterKeyLoader`: Register_Key.md 파싱 및 모든 설정 로드
- `AIAPIManager`: AI 엔진 전용 설정 관리 (싱글톤)
- `ClaudeGeminiHybridEngine`: 하이브리드 매매 엔진

---

## 🔧 구현 가이드라인

### **새로운 API 추가시**

1. **Register_Key.md 확장**
```markdown
## 5. 새로운 API 설정
```
새_API_키: [여기에_API_키_입력]
새_API_모델: model-name
새_API_설정: value
```
```

2. **AuthoritativeRegisterKeyLoader 확장**
```python
def _parse_new_api_config(self, content: str) -> Dict[str, str]:
    """새로운 API 설정 파싱"""
    result = {}
    # 파싱 로직 구현
    return result
```

3. **AIAPIManager 확장**
```python
def get_new_api_config(self) -> Dict[str, Any]:
    """새로운 API 설정 반환"""
    config = self._ai_config_cache['new_api']
    if not config['api_key']:
        raise ValueError(
            "새 API 키가 설정되지 않았습니다.\n"
            "메뉴 3. Setup → 1. Register_Key에서 설정하세요."
        )
    return config
```

### **금지 사항**

❌ **절대 하지 말 것:**
```python
# 하드코딩 금지
api_key = "sk-abc123..."

# 환경변수 사용 금지  
api_key = os.getenv("API_KEY")

# 별도 설정파일 금지
with open("config.json") as f:
    config = json.load(f)

# Fallback 시스템 금지
try:
    api_key = load_from_register_key()
except:
    api_key = "fallback_key"  # 절대 금지!
```

✅ **올바른 방법:**
```python
# Register_Key.md를 통한 올바른 접근
from support.ai_api_manager import get_ai_api_manager

ai_manager = get_ai_api_manager()
claude_config = ai_manager.get_claude_config()  # 자동으로 Register_Key.md에서 로드
```

---

## 🚀 Claude+Gemini 하이브리드 시스템

### **활성화 방법**

1. **Register_Key.md 설정**
```markdown
### Claude API 설정 (Anthropic)
```
Claude API Key: [실제_Claude_API_키]
Claude Model: claude-3.5-sonnet
```

### Gemini API 설정 (Google)
```
Gemini API Key: [실제_Gemini_API_키] 
Gemini Model: gemini-1.5-pro
```

### AI 엔진 조합 설정
```
하이브리드 모드 활성화: [true]
Claude 분석 가중치: [0.6]
Gemini 분석 가중치: [0.4]
```
```

2. **시스템에서 자동 감지 및 활용**
```python
# 하이브리드 엔진 자동 활성화
from support.claude_gemini_hybrid_engine import ClaudeGeminiHybridEngine

engine = ClaudeGeminiHybridEngine()  # 자동으로 Register_Key.md에서 설정 로드
decision = await engine.make_decision(market_context)
```

### **작동 원리**

1. **Claude 역할**: 정성적 펀더멘털 분석 (뉴스, 공시, 감정 분석)
2. **Gemini 역할**: 정량적 기술적 분석 (차트, 지표, 실시간 데이터)  
3. **융합 로직**: 가중 평균으로 최종 매매 결정
4. **실패 처리**: 하나라도 실패시 안전하게 HOLD 결정

---

## 📋 운영 가이드라인

### **사용자 안내**

**API 키 설정 방법:**
1. 메인메뉴에서 "3. Setup" 선택
2. "1. Register_Key (통합 연동정보 관리)" 선택  
3. Register_Key.md 파일이 열림
4. `[여기에...]` 부분을 실제 API 키로 교체
5. 파일 저장 후 시스템 재시작

**오류 발생시:**
- 모든 오류 메시지는 Register_Key.md 수정을 안내
- API 키 관련 문제는 반드시 해당 파일 확인 지시

### **개발자 가이드라인**

**코드 리뷰 체크리스트:**
- [ ] API 키 하드코딩 없음
- [ ] 환경변수 사용 없음  
- [ ] AuthoritativeRegisterKeyLoader 또는 AIAPIManager 사용
- [ ] Fallback 시스템 구현 없음
- [ ] 명확한 오류 메시지 (Register_Key.md 수정 안내)

**새 기능 개발시:**
- Register_Key.md 확장 먼저 설계
- AuthoritativeRegisterKeyLoader에 파싱 로직 추가
- AIAPIManager에 접근 메서드 추가
- 단위 테스트에서 Register_Key.md 시나리오 포함

---

## ⚠️ 보안 고려사항

### **파일 보안**
- Register_Key.md는 .gitignore에 포함
- 민감 정보 노출 방지
- 파일 권한 설정 (읽기/쓰기 제한)

### **API 키 보안**
- API 키 회전 주기적 실시
- 키 노출 모니터링
- 최소 권한 원칙 적용

### **오류 처리 보안**
- API 키 정보 로그 노출 금지
- 오류 메시지에서 민감 정보 마스킹
- 디버그 모드에서도 키 정보 숨김

---

## 🎯 결론

이 가이드라인은 **GPT4wiseTide 프로젝트의 핵심 원칙**입니다. 모든 개발자와 사용자는 반드시 이 원칙을 준수해야 하며, 특히 **Register_Key.md 중앙화 관리 원칙**은 절대 위반해서는 안 됩니다.

**Claude+Gemini 하이브리드 시스템**을 통해 더욱 정확하고 안정적인 매매 결정을 제공하면서도, 보안성과 유지보수성을 최대한 확보할 수 있습니다.