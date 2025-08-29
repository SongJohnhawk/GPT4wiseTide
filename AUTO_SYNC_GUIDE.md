# tideWise 자동 동기화 시스템 사용 가이드

## 개요
tideWise 프로젝트의 모든 파일 변경사항을 실시간으로 감지하고 자동으로 GitHub에 동기화하는 시스템입니다.

## 주요 기능
- 📁 **실시간 파일 모니터링**: 파일 생성, 수정, 삭제, 이동 감지
- 🔄 **자동 Git 동기화**: 변경사항을 자동으로 커밋하고 GitHub에 푸시
- 🚀 **백그라운드 실행**: 시스템 백그라운드에서 지속적으로 실행
- 📦 **배치 처리**: 여러 변경사항을 묶어서 효율적으로 처리
- 🎯 **스마트 필터링**: 불필요한 파일 (캐시, 로그, 임시파일) 자동 제외

## 시스템 구성 파일

### 1. `support/file_sync_monitor.py`
실시간 파일 감시 및 자동 동기화를 수행하는 핵심 모듈입니다.

**주요 기능:**
- `TideWiseFileHandler`: 파일 시스템 이벤트 감지
- `AutoSyncManager`: Git 동기화 및 배치 처리
- 중복 이벤트 필터링 (2초 디바운싱)
- 스마트 제외 패턴 적용

### 2. `start_auto_sync.py`
자동 동기화 서비스를 쉽게 관리할 수 있는 런처 스크립트입니다.

## 사용법

### 기본 명령어

#### 1. 자동 동기화 서비스 시작
```bash
python start_auto_sync.py start
# 또는 간단히
python start_auto_sync.py
```

#### 2. 서비스 상태 확인
```bash
python start_auto_sync.py status
```

#### 3. 서비스 중단
```bash
python start_auto_sync.py stop
```

#### 4. 서비스 재시작
```bash
python start_auto_sync.py restart
```

#### 5. 실시간 로그 보기
```bash
python start_auto_sync.py logs
```

### 실행 예시

1. **서비스 시작**
   ```
   ============================================================
            tideWise 자동 동기화 서비스 관리자
   ============================================================

   🚀 tideWise 자동 동기화 서비스 시작 중...
   📁 모니터링 폴더: C:\Claude_Works\Projects\tideWise
   📝 로그 파일: C:\Claude_Works\Projects\tideWise\logs\auto_sync.log
   ✅ 서비스 시작됨 (PID: 12345)
   📡 실시간 파일 모니터링 활성화
   🔄 파일 변경 시 자동으로 GitHub에 동기화됩니다
   ```

2. **실시간 동기화 작동**
   ```
   🔄 3개 파일 변경 감지됨 - 동기화 시작...
     📝 modified: 2개 파일
     📝 created: 1개 파일
   📤 GitHub 푸시 완료
   ✅ [16:45:23] 동기화 완료!
   ```

## 설정 및 제외 규칙

### 자동 제외되는 파일/폴더
- `__pycache__/` - Python 캐시 파일
- `.git/` - Git 내부 파일
- `logs/`, `*.log` - 로그 파일
- `cache/`, `temp/`, `backup/` - 임시 폴더
- `*.pyc`, `*.tmp`, `*.token` - 임시 및 민감 파일
- `stock_data_cache.json` - 데이터 캐시
- `trading_results/`, `backtest_results/` - 결과 폴더
- 숨김 파일 (`.`로 시작, `.gitignore` 제외)

### 배치 처리 설정
- **배치 크기**: 최대 50개 파일
- **타임아웃**: 30초 (변경사항이 적어도 30초 후 처리)
- **디바운싱**: 2초 (같은 파일의 중복 이벤트 제거)

### GitHub 설정
자동으로 다음 GitHub 정보를 사용합니다:
- **사용자명**: SongJohnhawk  
- **저장소**: https://github.com/SongJohnhawk/tideWise
- **토큰**: CLAUDE.md에서 자동 로드

## 로그 및 모니터링

### 로그 파일 위치
```
C:\Claude_Works\Projects\tideWise\logs\auto_sync.log
```

### 로그 내용
- 파일 변경 감지 이벤트
- Git 커밋 및 푸시 결과
- 에러 및 예외 상황
- 시스템 상태 정보

### 실시간 로그 모니터링
```bash
python start_auto_sync.py logs
```
- 최근 20줄 표시 후 실시간 업데이트
- `Ctrl+C`로 종료

## 트러블슈팅

### 1. 서비스가 시작되지 않는 경우
```bash
# 상태 확인
python start_auto_sync.py status

# 강제 중단 후 재시작
python start_auto_sync.py stop
python start_auto_sync.py start
```

### 2. Git 인증 오류
- CLAUDE.md 파일의 GitHub 토큰 확인
- 토큰 권한 설정 확인 (repo, workflow 권한 필요)

### 3. 파일이 동기화되지 않는 경우
- 제외 규칙에 해당하는지 확인
- 로그 파일에서 에러 메시지 확인
- 수동으로 git add, commit, push 테스트

### 4. 성능 문제 (너무 많은 이벤트)
- 배치 크기 조정: `batch_size` 값 수정
- 타임아웃 증가: `batch_timeout` 값 수정
- 제외 패턴 추가

## 고급 사용법

### 1. 직접 모니터링 스크립트 실행
```bash
python support/file_sync_monitor.py
```
- 포그라운드에서 실행 (디버깅용)
- `Ctrl+C`로 중단

### 2. 설정 커스터마이징
`support/file_sync_monitor.py` 파일에서 다음 값을 수정:
- `batch_size`: 배치 크기 (기본값: 50)
- `batch_timeout`: 배치 타임아웃 초 (기본값: 30)
- `debounce_time`: 디바운싱 시간 초 (기본값: 2.0)
- `exclude_patterns`: 제외 패턴 추가/제거

### 3. 멀티 프로젝트 설정
다른 프로젝트에도 적용하려면:
1. 스크립트 복사
2. `project_root` 경로 수정
3. GitHub 저장소 정보 수정

## 시스템 요구사항

### Python 패키지
```bash
pip install watchdog
```

### 운영체제
- Windows 10/11
- Python 3.8 이상
- Git 설치 및 설정 완료

### 네트워크
- 안정적인 인터넷 연결
- GitHub 접근 가능

## 보안 고려사항

1. **토큰 관리**: GitHub 토큰을 안전하게 보관
2. **권한 설정**: 필요한 최소 권한만 부여
3. **로그 보안**: 민감한 정보가 로그에 기록되지 않도록 주의
4. **접근 제어**: 스크립트 파일의 접근 권한 관리

## FAQ

### Q: 시스템 재부팅 후 자동으로 시작되나요?
A: 현재는 수동으로 시작해야 합니다. Windows 작업 스케줄러나 서비스로 등록하면 자동 시작 가능합니다.

### Q: 대용량 파일도 동기화되나요?
A: Git의 제한에 따라 100MB 이상 파일은 제외됩니다. 필요시 Git LFS 사용을 권장합니다.

### Q: 네트워크가 끊어지면 어떻게 되나요?
A: 로컬에 커밋은 저장되고, 네트워크 복구 시 자동으로 푸시를 재시도합니다.

### Q: 특정 파일/폴더를 제외하고 싶다면?
A: `file_sync_monitor.py`의 `exclude_patterns`에 패턴을 추가하세요.

## 지원 및 문의

문제가 발생하거나 개선 사항이 있으면 다음을 확인해주세요:

1. **로그 파일 확인**: `logs/auto_sync.log`
2. **상태 점검**: `python start_auto_sync.py status`
3. **서비스 재시작**: `python start_auto_sync.py restart`

---

📝 이 시스템은 tideWise 주식 자동매매 시스템의 개발 생산성 향상을 위해 Claude Code에 의해 개발되었습니다.