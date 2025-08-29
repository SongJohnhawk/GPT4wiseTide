#!/usr/bin/env python3
"""
tideWise 파일 변화 감지 및 자동 Git 동기화 시스템
- 실시간 파일 모니터링
- 자동 Git 커밋 및 푸시
- 배치 처리로 성능 최적화
"""

import os
import sys
import time
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Set, Dict, List
from dataclasses import dataclass
import threading
import queue

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("⚠️  watchdog 라이브러리가 필요합니다. 설치 중...")
    subprocess.run([sys.executable, "-m", "pip", "install", "watchdog"], check=True)
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True

# UTF-8 인코딩 설정
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


@dataclass
class FileChange:
    """파일 변경 정보"""
    path: Path
    event_type: str  # 'created', 'modified', 'deleted', 'moved'
    timestamp: datetime
    is_directory: bool = False


class TideWiseFileHandler(FileSystemEventHandler):
    """tideWise 프로젝트 파일 변경 감지 핸들러"""
    
    def __init__(self, sync_queue: queue.Queue, exclude_patterns: Set[str]):
        self.sync_queue = sync_queue
        self.exclude_patterns = exclude_patterns
        self.last_events = {}  # 중복 이벤트 필터링
        self.debounce_time = 2.0  # 2초 디바운싱
        
    def should_ignore(self, path: str) -> bool:
        """파일/폴더를 무시해야 하는지 확인"""
        path_obj = Path(path)
        
        # 제외 패턴 확인
        for pattern in self.exclude_patterns:
            if pattern in str(path_obj):
                return True
        
        # 파일 확장자 확인
        ignore_extensions = {
            '.pyc', '.pyo', '.pyd', '.log', '.tmp', '.temp', 
            '.swp', '.swo', '.bak', '.orig', '.rej'
        }
        if path_obj.suffix.lower() in ignore_extensions:
            return True
            
        # 숨김 파일/폴더 확인 (시스템 파일 제외)
        if any(part.startswith('.') and part not in ['.gitignore', '.github'] 
               for part in path_obj.parts):
            return True
            
        return False
    
    def is_duplicate_event(self, path: str, event_type: str) -> bool:
        """중복 이벤트인지 확인 (디바운싱)"""
        now = time.time()
        key = f"{path}:{event_type}"
        
        if key in self.last_events:
            if now - self.last_events[key] < self.debounce_time:
                return True
        
        self.last_events[key] = now
        return False
    
    def on_created(self, event):
        self._handle_event(event, 'created')
    
    def on_modified(self, event):
        self._handle_event(event, 'modified')
    
    def on_deleted(self, event):
        self._handle_event(event, 'deleted')
    
    def on_moved(self, event):
        self._handle_event(event, 'moved')
    
    def _handle_event(self, event, event_type: str):
        """파일 이벤트 처리"""
        if self.should_ignore(event.src_path):
            return
            
        if self.is_duplicate_event(event.src_path, event_type):
            return
        
        file_change = FileChange(
            path=Path(event.src_path),
            event_type=event_type,
            timestamp=datetime.now(),
            is_directory=event.is_directory
        )
        
        try:
            self.sync_queue.put_nowait(file_change)
        except queue.Full:
            print(f"⚠️  동기화 큐가 가득참: {event.src_path}")


class AutoSyncManager:
    """자동 동기화 관리자"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.git_token = "[GITHUB_TOKEN]"
        self.git_username = "SongJohnhawk"
        self.git_repo = "https://github.com/SongJohnhawk/tideWise.git"
        self.sync_queue = queue.Queue(maxsize=1000)
        self.batch_size = 50  # 배치 크기
        self.batch_timeout = 30  # 30초 타임아웃
        self.is_running = False
        
        # 제외 패턴 설정
        self.exclude_patterns = {
            '__pycache__', '.git', 'logs', '*.log', 'cache',
            'temp', 'backup', '*.pyc', '*.tmp', 'stock_data_cache.json',
            'trading_results', 'backtest_results', '*.token', '*.signal'
        }
        
        # Git 설정
        self._setup_git()
    
    def _setup_git(self):
        """Git 초기 설정"""
        try:
            os.chdir(self.project_root)
            
            # HTTP 버퍼 크기 증가
            subprocess.run(['git', 'config', 'http.postBuffer', '524288000'], 
                          check=True, capture_output=True)
            
            # 원격 URL 설정 (토큰 포함)
            remote_url = f"https://{self.git_username}:{self.git_token}@github.com/{self.git_username}/tideWise.git"
            subprocess.run(['git', 'remote', 'set-url', 'origin', remote_url], 
                          check=True, capture_output=True)
            
            print("✅ Git 설정 완료")
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Git 설정 오류: {e}")
    
    async def start_monitoring(self):
        """파일 모니터링 시작"""
        if not WATCHDOG_AVAILABLE:
            print("❌ watchdog 라이브러리를 사용할 수 없습니다.")
            return
        
        self.is_running = True
        print(f"🔍 tideWise 폴더 모니터링 시작: {self.project_root}")
        print("📁 감지할 변경사항: 생성, 수정, 삭제, 이동")
        print("⚡ 자동 동기화 활성화됨")
        print("-" * 60)
        
        # 파일 시스템 감시자 설정
        event_handler = TideWiseFileHandler(self.sync_queue, self.exclude_patterns)
        observer = Observer()
        observer.schedule(event_handler, str(self.project_root), recursive=True)
        
        # 감시자 시작
        observer.start()
        
        # 백그라운드 동기화 작업 시작
        sync_task = asyncio.create_task(self._sync_worker())
        
        try:
            print("📡 실시간 모니터링 중... (Ctrl+C로 중단)")
            await sync_task
        except KeyboardInterrupt:
            print("\n🛑 모니터링 중단 요청됨")
        finally:
            self.is_running = False
            observer.stop()
            observer.join()
            print("✅ 파일 모니터링 종료")
    
    async def _sync_worker(self):
        """백그라운드 동기화 작업자"""
        pending_changes = []
        
        while self.is_running:
            try:
                # 변경사항 수집
                start_time = time.time()
                
                while len(pending_changes) < self.batch_size:
                    try:
                        # 타임아웃으로 배치 처리 보장
                        remaining_time = self.batch_timeout - (time.time() - start_time)
                        if remaining_time <= 0:
                            break
                        
                        change = self.sync_queue.get(timeout=min(remaining_time, 5.0))
                        pending_changes.append(change)
                        
                    except queue.Empty:
                        if pending_changes:  # 대기 중인 변경사항이 있으면 처리
                            break
                        continue
                
                # 수집된 변경사항 처리
                if pending_changes:
                    await self._process_changes(pending_changes)
                    pending_changes.clear()
                
                await asyncio.sleep(1)  # CPU 사용량 조절
                
            except Exception as e:
                print(f"❌ 동기화 작업 오류: {e}")
                await asyncio.sleep(5)
    
    async def _process_changes(self, changes: List[FileChange]):
        """변경사항 처리 및 Git 동기화"""
        if not changes:
            return
        
        print(f"\n🔄 {len(changes)}개 파일 변경 감지됨 - 동기화 시작...")
        
        # 변경사항 요약
        change_summary = {}
        for change in changes:
            event_type = change.event_type
            if event_type not in change_summary:
                change_summary[event_type] = []
            change_summary[event_type].append(change.path.name)
        
        for event_type, files in change_summary.items():
            print(f"  📝 {event_type}: {len(files)}개 파일")
        
        try:
            # Git 동기화 실행
            await self._sync_to_git(changes)
            
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"✅ [{current_time}] 동기화 완료!")
            
        except Exception as e:
            print(f"❌ 동기화 실패: {e}")
    
    async def _sync_to_git(self, changes: List[FileChange]):
        """Git에 변경사항 동기화"""
        os.chdir(self.project_root)
        
        try:
            # 1. 변경된 파일들을 Git에 추가
            subprocess.run(['git', 'add', '.'], 
                          check=True, capture_output=True, text=True)
            
            # 2. 커밋 메시지 생성
            commit_msg = self._generate_commit_message(changes)
            
            # 3. 커밋 생성
            result = subprocess.run(
                ['git', 'commit', '-m', commit_msg],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                # 4. 원격 저장소에 푸시
                subprocess.run(['git', 'push', 'origin', 'main'], 
                              check=True, capture_output=True, text=True)
                print(f"  📤 GitHub 푸시 완료")
            else:
                if "nothing to commit" not in result.stdout:
                    print(f"  ℹ️  커밋할 변경사항이 없음")
                
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
            if "nothing to commit" not in error_msg:
                raise Exception(f"Git 동기화 오류: {error_msg}")
    
    def _generate_commit_message(self, changes: List[FileChange]) -> str:
        """변경사항을 기반으로 커밋 메시지 생성"""
        change_types = {}
        for change in changes:
            event_type = change.event_type
            if event_type not in change_types:
                change_types[event_type] = 0
            change_types[event_type] += 1
        
        # 메시지 구성
        parts = []
        if 'created' in change_types:
            parts.append(f"생성 {change_types['created']}개")
        if 'modified' in change_types:
            parts.append(f"수정 {change_types['modified']}개")
        if 'deleted' in change_types:
            parts.append(f"삭제 {change_types['deleted']}개")
        if 'moved' in change_types:
            parts.append(f"이동 {change_types['moved']}개")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        commit_message = f"""자동 동기화: {', '.join(parts)} 파일

자동 파일 모니터링을 통한 실시간 동기화
시간: {timestamp}

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""
        
        return commit_message


async def main():
    """메인 실행 함수"""
    print("=" * 80)
    print("                    tideWise 자동 파일 동기화 시스템")
    print("                        실시간 GitHub 동기화 v1.0")
    print("=" * 80)
    print()
    
    project_root = Path(r"C:\Claude_Works\Projects\tideWise")
    
    if not project_root.exists():
        print(f"❌ 프로젝트 폴더를 찾을 수 없습니다: {project_root}")
        return
    
    print(f"📁 모니터링 대상: {project_root}")
    print(f"🌐 원격 저장소: https://github.com/SongJohnhawk/tideWise")
    print()
    
    # 자동 동기화 매니저 생성 및 시작
    sync_manager = AutoSyncManager(project_root)
    
    try:
        await sync_manager.start_monitoring()
    except Exception as e:
        print(f"❌ 시스템 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 자동 동기화 시스템을 종료합니다.")
    except Exception as e:
        print(f"\n💥 시스템 오류로 종료됨: {e}")