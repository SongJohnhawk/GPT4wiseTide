# 통합 시간 제어 시스템 가이드

## 📋 개요
tideWise 자동매매 시스템의 통합 시간 제어 시스템은 모든 시간 관련 기능을 하나의 컨트롤러로 통합한 고급 시스템입니다.

## 🚀 주요 기능

### 1. 시장 시간 관리
- **장시작 대기**: 09:10까지 자동 대기
- **장마감 체크**: 15:30 시장 마감 감지
- **자동 중지**: 15:20 자동 매매 중지
- **휴장일 감지**: 주말 및 공휴일 자동 감지

### 2. 순환 간격 관리
- **기본 간격**: 180초 (3분)
- **최소/최대**: 30초 ~ 600초
- **동적 조정**: 시간대별 자동 조정
- **카운트다운**: 실시간 카운트다운 표시

### 3. 시간대별 자동 조정
- **아침장 (09:00~10:00)**: 간격 20% 축소 (빠른 실행)
- **점심시간 (12:00~13:00)**: 간격 50% 확대 (느린 실행)
- **마감전 (14:30~15:20)**: 간격 30% 축소 (빠른 실행)

### 4. 시장 단계 인식
- 장전 / 아침장 / 점심시간 / 오후장 / 마감전 / 장마감임박 / 장마감

## 📁 파일 구조
```
support/
├── integrated_time_controller.py    # 메인 컨트롤러
├── integrated_time_config.json      # 설정 파일
└── unified_cycle_manager.py        # 기존 순환 관리자 (호환)
```

## ⚙️ 설정 파일 구조

### integrated_time_config.json
```json
{
  "time_check_enabled": true,          // 시간 체크 활성화
  "daytrading_stop_time": "14:00",     // 단타매매 중지 시간
  "program_shutdown_time": "14:00",    // 프로그램 종료 시간
  "market_open_time": "09:10",         // 장시작 시간
  "auto_shutdown_enabled": true,       // 자동 종료 활성화
  "holiday_check_enabled": true,       // 휴장일 체크 활성화
  
  "cycle_settings": {
    "default_interval": 180,           // 기본 순환 간격(초)
    "min_interval": 30,                // 최소 간격
    "max_interval": 600,               // 최대 간격
    "countdown_enabled": true,         // 카운트다운 표시
    "countdown_update_interval": 10    // 카운트다운 업데이트 간격
  },
  
  "auto_adjustment": {
    "enabled": true,                   // 자동 조정 활성화
    "morning_boost": 0.8,              // 아침장 배율 (80%)
    "lunch_slowdown": 1.5,             // 점심시간 배율 (150%)
    "closing_boost": 0.7               // 마감전 배율 (70%)
  },
  
  "market_times": {
    "market_open": "09:00",
    "market_close": "15:30",
    "auto_stop": "15:20",
    "pre_market_end": "09:05",
    "lunch_start": "12:00",
    "lunch_end": "13:00"
  }
}
```

## 🔧 사용 방법

### 기본 사용법
```python
from support.integrated_time_controller import get_integrated_controller

# 컨트롤러 인스턴스 가져오기 (싱글톤)
controller = get_integrated_controller()

# 시장 상태 확인
is_tradeable, status = controller.get_market_status()
print(f"거래 가능: {is_tradeable}, 상태: {status}")

# 순환 타이머 시작
controller.start_cycle_timer()

# 순환 대기 (비동기)
await controller.wait_for_next_cycle()

# 다음 순환으로 진행
controller.advance_to_next_cycle()

# 통계 정보
stats = controller.get_cycle_stats()
```

### 고급 기능
```python
# 시장 단계 확인
phase = controller.get_market_phase()  # "아침장", "점심시간", "오후장" 등

# 점심시간 체크
if controller.is_lunch_time():
    print("점심시간입니다")

# 순환 간격 수동 변경
controller.set_cycle_interval(120)  # 2분으로 변경

# 카운트다운 표시
print(controller.get_countdown_display())
# 출력: "다음 알고리즘 실행까지: 2분 30초 [점심시간]"

# 특정 이벤트까지 남은 시간
seconds = controller.get_time_until_market_event("close")
print(f"장마감까지: {controller.format_time_until(seconds)}")
```

### production_auto_trader.py 통합 예제
```python
async def main_trading_loop():
    controller = get_integrated_controller()
    controller.start_cycle_timer()
    
    while True:
        # 시장 상태 체크
        is_tradeable, status = controller.get_market_status()
        if not is_tradeable:
            print(f"거래 불가: {status}")
            break
        
        # 자동 중지 체크
        if controller.should_auto_stop():
            print("자동 중지 시간 도달")
            break
        
        # 알고리즘 실행
        execute_trading_algorithm()
        
        # 다음 순환까지 대기
        success = await controller.wait_for_next_cycle()
        if not success:
            break
        
        # 다음 순환 준비
        controller.advance_to_next_cycle()
```

## 📊 시간대별 동작

### 시간대별 순환 간격
| 시간대 | 기본 간격 | 조정 배율 | 실제 간격 |
|--------|----------|-----------|-----------|
| 09:00~10:00 (아침장) | 180초 | 0.8 | 144초 |
| 10:00~12:00 (오전) | 180초 | 1.0 | 180초 |
| 12:00~13:00 (점심) | 180초 | 1.5 | 270초 |
| 13:00~14:30 (오후) | 180초 | 1.0 | 180초 |
| 14:30~15:20 (마감전) | 180초 | 0.7 | 126초 |

### 자동 동작
- **09:10 이전**: 장시작 대기
- **09:10**: 자동매매 시작
- **12:00~13:00**: 순환 간격 자동 확대
- **14:00**: 단타매매 자동 중지
- **14:00**: 프로그램 자동 종료 (설정시)
- **15:20**: 모든 매매 자동 중지
- **15:30**: 장마감

## 🧪 테스트

### 단위 테스트 실행
```bash
python test_time_controller.py
```

### 테스트 항목
1. 시간 체크 활성화 상태
2. 휴장일/주말 체크
3. 장시작 대기 로직
4. 단타매매 중지 시간
5. 프로그램 자동 종료
6. 상태 메시지
7. 거래 시간 검증
8. 순환 관리 기능
9. 시장 단계 확인
10. 시간대별 자동 조정
11. 순환 대기 사이클

## ⚠️ 주의사항

1. **시간 설정**: 시스템 시간이 정확해야 합니다
2. **최소 간격**: 순환 간격은 30초 이상이어야 합니다
3. **싱글톤 패턴**: `get_integrated_controller()` 사용 권장
4. **비동기 처리**: `wait_for_next_cycle()`은 async 함수입니다

## 🔄 마이그레이션 가이드

### 기존 시스템에서 마이그레이션
```python
# 기존 코드
from support.unified_cycle_manager import UnifiedCycleManager
from support.market_time_manager import MarketTimeManager

cycle_manager = UnifiedCycleManager()
time_manager = MarketTimeManager()

# 새 코드
from support.integrated_time_controller import get_integrated_controller

controller = get_integrated_controller()
# 모든 기능이 통합됨
```

## 📈 성능 최적화

- **메모리 효율**: 싱글톤 패턴으로 인스턴스 하나만 유지
- **CPU 효율**: 1초 간격 체크로 CPU 사용 최소화
- **동적 조정**: 시장 상황에 따른 자동 간격 조정
- **카운트다운 최적화**: 10초마다 업데이트로 출력 최소화

## 🚦 상태 코드

- **SUCCESS**: 정상 동작
- **WARNING**: 경고 (계속 동작)
- **ERROR**: 오류 (중단 필요)
- **INFO**: 정보 표시

## 📞 지원

문제 발생시 다음을 확인하세요:
1. `integrated_time_config.json` 설정 확인
2. 시스템 시간 정확성 확인
3. 로그 파일 확인
4. `test_time_controller.py` 실행하여 진단