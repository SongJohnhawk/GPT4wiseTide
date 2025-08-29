#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process Cleanup Manager - tideWise 프로세스 정리 관리자
자동매매/단타매매 종료 시 백그라운드 프로세스 및 관련 프로세스 완전 정리
"""

import os
import sys
import psutil
import signal
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional

# 로깅 설정
from support.log_manager import get_log_manager

# 깔끔한 콘솔 로거 사용
from support.clean_console_logger import (
    get_clean_logger, Phase, log as clean_log
)

# 로그 매니저를 통한 로거 설정
log_manager = get_log_manager()
logger = log_manager.setup_logger('system', __name__)


class ProcessCleanupManager:
    """tideWise 프로세스 정리 관리자"""
    
    def __init__(self):
        """초기화"""
        self.project_root = Path(__file__).parent.parent
        self.current_pid = os.getpid()
        self._cleanup_in_progress = False  # 중복 cleanup 방지
        self._cleanup_completed = False
        
        # tideWise 관련 프로세스 식별 키워드
        self.process_keywords = [
            'run.py',
            'minimal_day_trader',
            'minimal_auto_trader',
            'production_auto_trader',
            'simple_auto_trader',
            'day_trading_runner',
            'stock_data_collector',
            'surge_stock_buyer',
            'account_memory_manager',
            'premarket_data_collector',
            'telegram_notifier',
            'api_connector',
            'token_manager',
            'tideWise',
            'kauto',
            'auto_trading',
            'day_trading'
        ]
        
        # 중지 신호 파일들
        self.stop_signal_files = [
            self.project_root / "STOP_DAYTRADING.signal",
            self.project_root / "STOP_AUTOTRADING.signal",
            self.project_root / "STOP_ALL.signal"
        ]
        
        # 임시 파일 패턴
        self.temp_file_patterns = [
            "*.signal",
            "*.lock",
            "*.tmp",
            "*.pid",
            ".token_cache/*",
            "__pycache__/*"
        ]
        
        # ProcessCleanupManager 초기화 완료 (로그 제거)
    
    def find_kauto_processes(self, timeout_seconds: int = 5) -> List[psutil.Process]:
        """tideWise 관련 프로세스 찾기 (KeyboardInterrupt 안전)"""
        kauto_processes = []
        start_time = time.time()
        
        try:
            # psutil.process_iter() 호출을 KeyboardInterrupt로부터 보호
            process_list = []
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                    # 타임아웃 체크
                    if time.time() - start_time > timeout_seconds:
                        clean_log(f"프로세스 검색 타임아웃 ({timeout_seconds}초)", "WARNING")
                        break
                    
                    process_list.append(proc)
                    
            except KeyboardInterrupt:
                clean_log("프로세스 검색 중 KeyboardInterrupt 발생 - 안전하게 중단", "INFO")
                return kauto_processes
            except Exception as e:
                clean_log(f"프로세스 목록 수집 오류: {e}", "ERROR")
                return kauto_processes
            
            # 수집된 프로세스 목록 분석
            for proc in process_list:
                try:
                    # 타임아웃 체크
                    if time.time() - start_time > timeout_seconds:
                        clean_log("프로세스 분석 타임아웃", "WARNING")
                        break
                    
                    # 현재 프로세스는 제외
                    if proc.pid == self.current_pid:
                        continue
                    
                    # Python 프로세스만 체크
                    if proc.info and 'python' not in proc.info.get('name', '').lower():
                        continue
                    
                    # 명령행 인자 확인
                    cmdline = proc.info.get('cmdline', [])
                    if not cmdline:
                        continue
                    
                    cmdline_str = ' '.join(cmdline).lower()
                    
                    # tideWise 관련 키워드 체크
                    for keyword in self.process_keywords:
                        if keyword.lower() in cmdline_str:
                            kauto_processes.append(proc)
                            # tideWise 프로세스 발견 (로그 제거 - 과도한 정보)
                            break
                    
                    # 프로젝트 경로 체크
                    if str(self.project_root).lower() in cmdline_str:
                        kauto_processes.append(proc)
                        # 프로젝트 경로 프로세스 발견 (로그 제거 - 과도한 정보)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                except KeyboardInterrupt:
                    clean_log("프로세스 분석 중 KeyboardInterrupt 발생 - 안전하게 중단", "INFO")
                    break
                except Exception as e:
                    # 프로세스 분석 오류 (로그 제거 - 과도한 디버그 메시지)
                    continue
                    
        except KeyboardInterrupt:
            clean_log("프로세스 검색 전체가 KeyboardInterrupt로 중단됨", "INFO")
        except Exception as e:
            clean_log(f"프로세스 검색 오류: {e}", "ERROR")
            
        return kauto_processes
    
    def terminate_process_safely(self, proc: psutil.Process) -> bool:
        """프로세스를 안전하게 종료"""
        try:
            pid = proc.pid
            name = proc.name()
            
            # 1단계: SIGTERM으로 정상 종료 시도
            # 프로세스 종료 시도 (로그 제거 - 과도한 정보)
            proc.terminate()
            
            # 최대 5초 대기
            try:
                proc.wait(timeout=5)
                # 프로세스 정상 종료 (로그 제거)
                return True
            except psutil.TimeoutExpired:
                pass
            
            # 2단계: 아직 살아있으면 SIGKILL로 강제 종료
            if proc.is_running():
                clean_log(f"프로세스 강제 종료 시도: PID={pid}", "WARNING")
                proc.kill()
                
                try:
                    proc.wait(timeout=3)
                    clean_log(f"프로세스 강제 종료됨: PID={pid}", "INFO")
                    return True
                except psutil.TimeoutExpired:
                    clean_log(f"프로세스 종료 실패: PID={pid}", "ERROR")
                    return False
                    
        except psutil.NoSuchProcess:
            # 프로세스가 이미 종료 (로그 제거)
            return True
        except psutil.AccessDenied:
            clean_log(f"프로세스 종료 권한 없음: PID={proc.pid}", "ERROR")
            return False
        except Exception as e:
            clean_log(f"프로세스 종료 오류: PID={proc.pid}, {e}", "ERROR")
            return False
    
    def create_stop_signals(self):
        """중지 신호 파일 생성"""
        for signal_file in self.stop_signal_files:
            try:
                signal_file.write_text("STOP")
                clean_log(f"중지 신호 파일 생성: {signal_file.name}", "INFO")
            except Exception as e:
                clean_log(f"신호 파일 생성 실패: {signal_file.name}, {e}", "ERROR")
    
    def cleanup_temp_files(self):
        """임시 파일 정리"""
        cleaned_count = 0
        
        for pattern in self.temp_file_patterns:
            try:
                # 프로젝트 루트에서 패턴 매칭
                if '*' in pattern:
                    if '/' in pattern:
                        # 디렉토리 포함 패턴
                        dir_part, file_part = pattern.rsplit('/', 1)
                        base_dir = self.project_root / dir_part.replace('*', '')
                        if base_dir.exists():
                            for file in base_dir.glob(file_part):
                                if file.is_file():
                                    file.unlink()
                                    cleaned_count += 1
                    else:
                        # 파일만 패턴
                        for file in self.project_root.glob(pattern):
                            if file.is_file():
                                file.unlink()
                                cleaned_count += 1
                else:
                    # 특정 파일
                    file_path = self.project_root / pattern
                    if file_path.exists() and file_path.is_file():
                        file_path.unlink()
                        cleaned_count += 1
                        
            except Exception as e:
                clean_log(f"임시 파일 정리 오류: {pattern}, {e}", "ERROR")
                
        if cleaned_count > 0:
            clean_log(f"임시 파일 {cleaned_count}개 정리 완료", "SUCCESS")
    
    def cleanup_all_processes(self, include_self: bool = False) -> Dict[str, any]:
        """모든 tideWise 관련 프로세스 정리 (KeyboardInterrupt 안전)"""
        result = {
            'found_processes': 0,
            'terminated_processes': 0,
            'failed_processes': 0,
            'details': [],
            'interrupted': False
        }
        
        try:
            print("\n" + "="*60)
            print("tideWise 프로세스 정리 시작")
            print("="*60)
            
            # 1. 중지 신호 파일 생성
            print("\n[1단계] 중지 신호 파일 생성...")
            self.create_stop_signals()
            
            # 2. tideWise 프로세스 찾기
            print("\n[2단계] tideWise 관련 프로세스 검색...")
            kauto_processes = self.find_kauto_processes()
            result['found_processes'] = len(kauto_processes)
            
            if not kauto_processes:
                print("  - 실행 중인 tideWise 프로세스가 없습니다.")
            else:
                print(f"  - {len(kauto_processes)}개의 관련 프로세스 발견")
                
                # 3. 프로세스 종료
                print("\n[3단계] 프로세스 종료 중...")
                for proc in kauto_processes:
                    try:
                        proc_info = {
                            'pid': proc.pid,
                            'name': proc.name(),
                            'status': 'unknown'
                        }
                        
                        # 자기 자신은 마지막에 처리
                        if proc.pid == self.current_pid and not include_self:
                            proc_info['status'] = 'skipped_self'
                            result['details'].append(proc_info)
                            continue
                        
                        print(f"  - PID {proc.pid} ({proc.name()}) 종료 중...")
                        
                        if self.terminate_process_safely(proc):
                            proc_info['status'] = 'terminated'
                            result['terminated_processes'] += 1
                            print(f"    [OK] 프로세스 종료됨")
                        else:
                            proc_info['status'] = 'failed'
                            result['failed_processes'] += 1
                            print(f"    [ERROR] 프로세스 종료 실패")
                        
                        result['details'].append(proc_info)
                        
                    except KeyboardInterrupt:
                        clean_log("프로세스 종료 중 KeyboardInterrupt 발생 - 안전하게 중단", "INFO")
                        result['interrupted'] = True
                        break
                    except Exception as e:
                        clean_log(f"프로세스 처리 오류: {e}", "ERROR")
                        result['failed_processes'] += 1
            
            # KeyboardInterrupt가 발생하지 않은 경우에만 추가 정리 수행
            if not result['interrupted']:
                # 4. 임시 파일 정리
                print("\n[4단계] 임시 파일 정리...")
                self.cleanup_temp_files()
                
                # 5. 메모리 정리
                print("\n[5단계] 메모리 정리...")
                try:
                    import gc
                    gc.collect()
                    print("  - 가비지 컬렉션 완료")
                except Exception as e:
                    clean_log(f"메모리 정리 오류: {e}", "ERROR")
        
        except KeyboardInterrupt:
            clean_log("프로세스 정리 전체가 KeyboardInterrupt로 중단됨", "INFO")
            result['interrupted'] = True
        except Exception as e:
            clean_log(f"프로세스 정리 오류: {e}", "ERROR")
        
        # 결과 출력 (간소화)
        try:
            if result['interrupted']:
                print("\n[WARNING] 정리 작업이 중단되었습니다")
            else:
                print("\n" + "="*60)
                print("프로세스 정리 완료")
                print(f"  - 발견된 프로세스: {result['found_processes']}개")
                print(f"  - 종료된 프로세스: {result['terminated_processes']}개")
                if result['failed_processes'] > 0:
                    print(f"  - 종료 실패: {result['failed_processes']}개")
                print("="*60)
        except:
            # 출력 중 오류가 발생해도 조용히 넘어감
            pass
        
        return result
    
    def cleanup_on_exit(self):
        """프로그램 종료 시 자동 정리 (atexit 핸들러용, KeyboardInterrupt 안전)"""
        # 중복 실행 방지
        if self._cleanup_in_progress or self._cleanup_completed:
            return
            
        self._cleanup_in_progress = True
        
        try:
            # KeyboardInterrupt나 다른 신호로 인한 종료 시에는 조용히 처리
            import signal
            import sys
            
            # atexit 콜백에서는 로깅 시스템이 불안정하므로 조용히 정리만 수행
            # logger.info 제거 - 종료 시점에서 로깅 오류 방지
            
            # KeyboardInterrupt가 발생할 수 있는 상황을 고려하여 간단한 정리만 수행
            self._quick_cleanup()
            
            self._cleanup_completed = True
            
        except KeyboardInterrupt:
            # atexit 중 KeyboardInterrupt는 조용히 무시
            pass
        except Exception as e:
            # 로깅도 실패할 수 있으므로 조용히 넘어감
            try:
                logger.error(f"종료 시 정리 오류: {e}")
            except:
                pass
        finally:
            self._cleanup_in_progress = False
    
    def _quick_cleanup(self):
        """빠른 정리 작업 (KeyboardInterrupt 중에도 안전)"""
        try:
            # 1. 중지 신호 파일만 생성 (빠르고 안전)
            for signal_file in self.stop_signal_files:
                try:
                    signal_file.write_text("STOP")
                except:
                    pass
            
            # 2. 현재 실행 중인 프로세스 목록을 빠르게 찾아서 종료 시도
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.pid == self.current_pid:
                            continue
                        
                        cmdline = proc.info.get('cmdline', [])
                        if not cmdline:
                            continue
                        
                        cmdline_str = ' '.join(cmdline).lower()
                        
                        # 핵심 키워드만 체크 (빠른 처리)
                        if any(keyword in cmdline_str for keyword in ['run.py', 'auto_trader', 'day_trader']):
                            proc.terminate()
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied, KeyboardInterrupt):
                        break
                    except:
                        continue
                        
            except (KeyboardInterrupt, Exception):
                # 프로세스 검색 중 오류 발생 시 조용히 넘어감
                pass
                
        except:
            # 모든 오류를 조용히 처리
            pass


# 싱글톤 인스턴스
_cleanup_manager = None


def get_cleanup_manager() -> ProcessCleanupManager:
    """ProcessCleanupManager 싱글톤 인스턴스 반환"""
    global _cleanup_manager
    if _cleanup_manager is None:
        _cleanup_manager = ProcessCleanupManager()
    return _cleanup_manager


def cleanup_all_processes():
    """모든 tideWise 프로세스 정리 (외부 호출용)"""
    manager = get_cleanup_manager()
    return manager.cleanup_all_processes()


def register_cleanup_on_exit():
    """프로그램 종료 시 자동 정리 등록"""
    import atexit
    manager = get_cleanup_manager()
    atexit.register(manager.cleanup_on_exit)
    logger.info("프로그램 종료 시 자동 정리 핸들러 등록됨")


if __name__ == "__main__":
    # 직접 실행 시 정리 수행
    print("tideWise 프로세스 정리 유틸리티")
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 정리 실행
    manager = ProcessCleanupManager()
    result = manager.cleanup_all_processes(include_self=True)
    
    # 결과 반환
    sys.exit(0 if result['failed_processes'] == 0 else 1)