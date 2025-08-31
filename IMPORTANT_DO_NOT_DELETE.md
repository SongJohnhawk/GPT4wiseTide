# ⚠️ 중요한 파일 보호 안내

## 절대 삭제하거나 수정하면 안 되는 파일들:

### 🔑 API 키 설정 파일 (최우선 보호)
- `Policy/Register_Key/Register_Key.md` 
  - **GPT API Key 포함**
  - **KIS API Key 포함** 
  - **텔레그램 봇 토큰 포함**
  - **절대 삭제/수정 금지**

### 📊 데이터베이스 및 캐시 파일
- `stock_data_cache.json` - 주식 데이터 캐시
- `support/selected_algorithm.json` - 선택된 알고리즘
- `support/trading_config.json` - 거래 설정

### 📝 로그 및 리포트
- `logs/` 디렉토리 전체 - 거래 로그 보관
- `report/` 디렉토리 전체 - 매매 리포트 보관

## 🛡️ 보호 조치
- Register_Key.md는 .gitignore에 포함되어 Git에서 추적하지 않음
- 시스템 정리 시 이 파일들은 자동으로 보호됨
- Claude는 이 파일들을 임의로 수정하지 않음

**경고**: 이 파일들을 잃어버리면 시스템이 작동하지 않을 수 있습니다!