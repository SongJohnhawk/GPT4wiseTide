#!/usr/bin/env python3
"""
SystemManager - tideWise 시스템 관리 클래스
run.py에서 분리된 시스템 관리 관련 기능들을 통합 관리
"""

import asyncio
import sys
import gc
import time
import logging
from pathlib import Path
from typing import Optional


class SystemManager:
    """시스템 관리 및 정리 작업을 담당하는 클래스"""
    
    def __init__(self, project_root: Path):
        """
        SystemManager 초기화
        
        Args:
            project_root: 프로젝트 루트 디렉토리 경로
        """
        self.project_root = Path(project_root)
        self.logger = logging.getLogger(__name__)
    
    def _is_debug_mode(self) -> bool:
        """디버그 모드 확인"""
        import os
        return os.environ.get('K_AUTOTRADE_DEBUG', '').lower() in ['true', '1', 'yes']
    
    async def cleanup_pending_tasks(self):
        """비동기 작업 정리 - Task pending 메시지 방지"""
        try:
            # 현재 이벤트 루프 확인
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return  # 이벤트 루프가 없으면 정리할 것도 없음
            
            if loop.is_closed():
                return  # 루프가 이미 닫혔으면 정리 불가
            
            # 모든 pending 작업 찾기
            pending_tasks = []
            try:
                for task in asyncio.all_tasks(loop):
                    if not task.done() and not task.cancelled():
                        # 현재 실행 중인 cleanup_pending_tasks 자신은 제외
                        if task != asyncio.current_task():
                            pending_tasks.append(task)
            except RuntimeError:
                return  # 작업 목록 가져오기 실패 시 무시
            
            if pending_tasks:
                # 모든 작업 취소
                for task in pending_tasks:
                    try:
                        if not task.done() and not task.cancelled():
                            task.cancel()
                    except Exception:
                        pass  # 개별 작업 취소 실패 무시
                
                # 취소된 작업들 완료 대기
                if pending_tasks:
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*pending_tasks, return_exceptions=True),
                            timeout=0.3  # 300ms만 대기
                        )
                    except (asyncio.TimeoutError, asyncio.CancelledError, RuntimeError):
                        pass  # 모든 예외 무시
            
            if self._is_debug_mode():
                print("[SYSTEM] 비동기 작업 정리 완료")
            
        except Exception:
            # 모든 예외 완전 무시 - 정리 과정에서 오류는 중요하지 않음
            pass
    
    def clean_shutdown(self):
        """깨끗한 시스템 종료"""
        print("\n프로그램을 종료합니다...")
        
        # 가비지 컬렉션
        gc.collect()
        
        # 종료 메시지 (디버그 모드에서만)
        if self._is_debug_mode():
            print("tideWise 시스템이 안전하게 종료되었습니다.")
        
        # 프로그램 종료
        sys.exit(0)
    
    def safe_input(self, prompt: str) -> str:
        """안전한 입력 받기 (KeyboardInterrupt 처리)"""
        try:
            return input(prompt).strip()
        except KeyboardInterrupt:
            print("\n\n[INTERRUPT] 사용자에 의해 중단되었습니다.")
            raise
        except EOFError:
            if self._is_debug_mode():
                print("\n입력 스트림이 종료되었습니다.")
            return "0"  # 종료 선택으로 처리
    
    def get_display_width(self, text: str) -> int:
        """텍스트 디스플레이 너비 계산 (한글 지원)"""
        width = 0
        for char in text:
            # 한글, 중국어, 일본어 등은 너비가 2
            if '\u1100' <= char <= '\u11FF' or \
               '\u3130' <= char <= '\u318F' or \
               '\uAC00' <= char <= '\uD7A3' or \
               '\u4E00' <= char <= '\u9FFF':
                width += 2
            else:
                width += 1
        return width
    
    async def send_trading_start_message(self):
        """자동매매 시작 메시지 전송"""
        try:
            from support.telegram_notifier import get_telegram_notifier
            telegram = get_telegram_notifier()
            
            message = """
[tideWise] 자동매매 시스템 시작

시스템이 준비되었습니다.
자동매매를 시작할 수 있습니다.
            """
            
            await telegram.send_message(message.strip())
            
        except Exception as e:
            self.logger.debug(f"텔레그램 시작 메시지 전송 실패: {e}")
    
    def check_trading_records(self):
        """거래 기록 확인 및 표시"""
        try:
            report_dir = self.project_root / "report"
            
            if not report_dir.exists():
                print("\n거래 기록이 없습니다.")
                return
            
            # HTML 파일들 찾기 (최근 3개)
            html_files = list(report_dir.glob("trading_report_*.html"))
            html_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            if html_files:
                print(f"\n최근 거래 기록 ({len(html_files)}개):")
                print("-" * 50)
                
                for i, report_file in enumerate(html_files[:3], 1):
                    # 파일명에서 정보 추출
                    filename = report_file.stem
                    parts = filename.replace("trading_report_", "").split("_")
                    
                    if len(parts) >= 3:
                        account_type = parts[0]
                        algorithm = "_".join(parts[1:-1])
                        date = parts[-1]
                        
                        print(f"{i}. {date} - {account_type.upper()} - {algorithm}")
                    else:
                        print(f"{i}. {report_file.name}")
                        
                print("-" * 50)
                print("상세 내용은 report/ 폴더의 HTML 파일을 확인하세요.")
            else:
                print("\n거래 기록이 없습니다.")
                
        except Exception as e:
            print(f"거래 기록 확인 중 오류: {e}")
    
    def create_stop_signal_file(self, signal_type: str = "stop"):
        """중단 신호 파일 생성"""
        try:
            if signal_type == "stop":
                signal_file = self.project_root / "STOP_TRADING.signal"
            else:
                signal_file = self.project_root / "FORCE_EXIT.signal"
                
            signal_file.write_text(f"Created at: {time.time()}")
            print(f"\n{signal_type.upper()} 신호 파일이 생성되었습니다: {signal_file}")
            
        except Exception as e:
            print(f"신호 파일 생성 실패: {e}")
    
    def remove_signal_files(self):
        """모든 신호 파일 제거"""
        try:
            signal_files = [
                self.project_root / "STOP_TRADING.signal",
                self.project_root / "FORCE_EXIT.signal"
            ]
            
            removed_count = 0
            for signal_file in signal_files:
                if signal_file.exists():
                    signal_file.unlink()
                    removed_count += 1
            
            if removed_count > 0:
                print(f"\n{removed_count}개의 신호 파일이 제거되었습니다.")
                
        except Exception as e:
            print(f"신호 파일 제거 실패: {e}")
    
    def cleanup_temp_files(self, silent: bool = False) -> bool:
        """임시 파일들을 정리하는 함수"""
        try:
            # 백그라운드에서 조용히 정리
            
            # 직접 임시 파일 정리 (universal_temp_cleaner 사용)
            try:
                from support.universal_temp_cleaner import UniversalTempCleaner
                cleaner = UniversalTempCleaner(self.project_root)
                cleaned_count, error_count = cleaner.clean_all_temp_files(silent=True)
                
                if error_count == 0:
                    if cleaned_count > 0 and not silent:
                        print(f"[INFO] 임시 파일 정리 완료 ({cleaned_count}개 파일 정리)")
                    return True
                else:
                    if not silent:
                        print(f"[WARN] 임시 파일 정리 중 {error_count}개 오류 발생")
                    return True  # 일부 오류가 있어도 정리는 수행됨
                    
            except Exception as direct_error:
                if not silent:
                    print(f"[WARN] 직접 정리 실패, 스크립트 실행 시도: {direct_error}")
                
                # 폴백: cleanup_temp_files.py 스크립트 실행
                cleanup_script = self.project_root / "support" / "cleanup_temp_files.py"
                if cleanup_script.exists():
                    import subprocess
                    result = subprocess.run(
                        [sys.executable, str(cleanup_script)], 
                        cwd=str(cleanup_script.parent),
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        # 임시 파일 정리 완료 - 조용히 처리
                        return True
                    else:
                        if not silent:
                            print(f"[WARN] 임시 파일 정리 실패: {result.stderr}")
                        return False
                else:
                    if not silent:
                        print("[WARN] 임시 파일 정리 스크립트를 찾을 수 없습니다.")
                    return False
                
        except Exception as e:
            if not silent:
                print(f"[ERROR] 임시 파일 정리 오류: {e}")
            return False
    
    def check_system_requirements(self) -> bool:
        """시스템 요구사항 체크"""
        try:
            # Python 버전 체크
            if sys.version_info < (3, 7):
                print("ERROR: Python 3.7 이상이 필요합니다.")
                return False
            
            # 필수 디렉토리 체크
            required_dirs = [
                "Algorithm",
                "Policy", 
                "support",
                "day_trade_Algorithm"
            ]
            
            for dir_name in required_dirs:
                dir_path = self.project_root / dir_name
                if not dir_path.exists():
                    print(f"WARNING: 필수 디렉토리가 없습니다: {dir_name}")
            
            return True
            
        except Exception as e:
            print(f"시스템 요구사항 체크 실패: {e}")
            return False


def get_system_manager(project_root: Path) -> SystemManager:
    """SystemManager 인스턴스를 생성하여 반환"""
    return SystemManager(project_root)