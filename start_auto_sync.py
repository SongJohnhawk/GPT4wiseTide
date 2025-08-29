#!/usr/bin/env python3
"""
tideWise 자동 동기화 서비스 시작/관리 스크립트
- 백그라운드 실행 및 관리
- 서비스 상태 확인
- 로그 모니터링
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent
MONITOR_SCRIPT = PROJECT_ROOT / "support" / "file_sync_monitor.py"
PID_FILE = PROJECT_ROOT / "auto_sync.pid"
LOG_FILE = PROJECT_ROOT / "logs" / "auto_sync.log"

# UTF-8 인코딩 설정
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


def create_logs_dir():
    """로그 디렉토리 생성"""
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir


def is_running() -> bool:
    """자동 동기화 서비스가 실행 중인지 확인"""
    if not PID_FILE.exists():
        return False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # 윈도우에서 프로세스 확인
        if sys.platform.startswith('win'):
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV'],
                capture_output=True, text=True
            )
            return str(pid) in result.stdout
        else:
            # Unix 계열에서 프로세스 확인
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False
    except (ValueError, FileNotFoundError):
        return False


def start_service():
    """자동 동기화 서비스 시작"""
    if is_running():
        print("⚠️  자동 동기화 서비스가 이미 실행 중입니다.")
        return
    
    create_logs_dir()
    
    print("🚀 tideWise 자동 동기화 서비스 시작 중...")
    print(f"📁 모니터링 폴더: {PROJECT_ROOT}")
    print(f"📝 로그 파일: {LOG_FILE}")
    
    try:
        # 백그라운드에서 모니터링 스크립트 실행
        if sys.platform.startswith('win'):
            # Windows: 새 프로세스로 실행
            process = subprocess.Popen(
                [sys.executable, str(MONITOR_SCRIPT)],
                stdout=open(LOG_FILE, 'w', encoding='utf-8'),
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Unix: 백그라운드 실행
            process = subprocess.Popen(
                [sys.executable, str(MONITOR_SCRIPT)],
                stdout=open(LOG_FILE, 'w', encoding='utf-8'),
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
        
        # PID 저장
        with open(PID_FILE, 'w') as f:
            f.write(str(process.pid))
        
        print(f"✅ 서비스 시작됨 (PID: {process.pid})")
        print("📡 실시간 파일 모니터링 활성화")
        print("🔄 파일 변경 시 자동으로 GitHub에 동기화됩니다")
        print()
        print("명령어:")
        print("  python start_auto_sync.py stop     - 서비스 중단")
        print("  python start_auto_sync.py status   - 서비스 상태 확인")
        print("  python start_auto_sync.py logs     - 실시간 로그 보기")
        
    except Exception as e:
        print(f"❌ 서비스 시작 실패: {e}")


def stop_service():
    """자동 동기화 서비스 중단"""
    if not is_running():
        print("ℹ️  자동 동기화 서비스가 실행되고 있지 않습니다.")
        return
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        print(f"🛑 자동 동기화 서비스 중단 중... (PID: {pid})")
        
        if sys.platform.startswith('win'):
            # Windows: taskkill 사용
            subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], 
                          capture_output=True)
        else:
            # Unix: SIGTERM 전송
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        
        # PID 파일 삭제
        if PID_FILE.exists():
            PID_FILE.unlink()
        
        print("✅ 서비스가 중단되었습니다")
        
    except Exception as e:
        print(f"❌ 서비스 중단 실패: {e}")
        # 강제로 PID 파일 삭제
        if PID_FILE.exists():
            PID_FILE.unlink()


def show_status():
    """서비스 상태 표시"""
    print("📊 tideWise 자동 동기화 서비스 상태")
    print("-" * 50)
    
    if is_running():
        with open(PID_FILE, 'r') as f:
            pid = f.read().strip()
        
        print(f"🟢 상태: 실행 중 (PID: {pid})")
        
        if LOG_FILE.exists():
            file_size = LOG_FILE.stat().st_size / 1024  # KB
            modified_time = datetime.fromtimestamp(LOG_FILE.stat().st_mtime)
            print(f"📝 로그 파일: {LOG_FILE}")
            print(f"📏 로그 크기: {file_size:.1f} KB")
            print(f"🕐 마지막 수정: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("📝 로그 파일: 없음")
    else:
        print("🔴 상태: 중단됨")
        if PID_FILE.exists():
            print("⚠️  PID 파일이 남아있음 (정리 필요)")
    
    print(f"📁 모니터링 폴더: {PROJECT_ROOT}")
    print(f"🌐 GitHub 저장소: https://github.com/SongJohnhawk/tideWise")


def show_logs():
    """실시간 로그 표시"""
    if not LOG_FILE.exists():
        print("📝 로그 파일이 없습니다.")
        return
    
    print(f"📝 실시간 로그 보기: {LOG_FILE}")
    print("   (Ctrl+C로 중단)")
    print("-" * 60)
    
    try:
        # 마지막 20줄 먼저 표시
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.rstrip())
        
        # 실시간 tail 구현
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            # 파일 끝으로 이동
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    print(line.rstrip())
                else:
                    time.sleep(0.5)
                    
    except KeyboardInterrupt:
        print("\n📝 로그 모니터링 종료")
    except Exception as e:
        print(f"❌ 로그 읽기 오류: {e}")


def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        command = "start"
    else:
        command = sys.argv[1].lower()
    
    print("=" * 60)
    print("         tideWise 자동 동기화 서비스 관리자")
    print("=" * 60)
    print()
    
    if command == "start":
        start_service()
    elif command == "stop":
        stop_service()
    elif command == "status":
        show_status()
    elif command == "restart":
        print("🔄 서비스 재시작 중...")
        stop_service()
        time.sleep(2)
        start_service()
    elif command == "logs" or command == "log":
        show_logs()
    else:
        print("📖 사용법:")
        print("  python start_auto_sync.py [명령]")
        print()
        print("명령:")
        print("  start    - 자동 동기화 서비스 시작 (기본값)")
        print("  stop     - 자동 동기화 서비스 중단")
        print("  restart  - 자동 동기화 서비스 재시작")
        print("  status   - 서비스 상태 확인")
        print("  logs     - 실시간 로그 보기")


if __name__ == "__main__":
    main()