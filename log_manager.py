#!/usr/bin/env python3
"""
로그 관리 시스템
로그 파일 생성, 정리, 자동 삭제를 담당하는 유틸리티
"""

import os
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import glob


class SimpleLogFormatter(logging.Formatter):
    """간결한 로그 포맷터"""
    
    def format(self, record):
        # WARNING을 Error로 변경
        if record.levelname == 'WARNING':
            levelname = 'Error'
        elif record.levelname == 'ERROR':
            levelname = 'Error'
        elif record.levelname == 'CRITICAL':
            levelname = 'Critical Error'
        elif record.levelname == 'INFO':
            # INFO 레벨은 표시하지 않고 메시지만 출력
            return record.getMessage()
        else:
            levelname = record.levelname
            
        # ERROR나 WARNING인 경우에만 레벨명 포함
        if record.levelname in ['WARNING', 'ERROR', 'CRITICAL']:
            return f"{levelname}: {record.getMessage()}"
        else:
            return record.getMessage()


class LogManager:
    """로그 파일 관리 클래스"""
    
    def __init__(self, base_dir: str = None):
        """
        로그 매니저 초기화
        
        Args:
            base_dir: 프로젝트 루트 디렉토리 (기본값: 현재 스크립트 기준 상위 디렉토리)
        """
        if base_dir is None:
            # 현재 파일 기준으로 프로젝트 루트 찾기
            current_file = Path(__file__).resolve()
            self.base_dir = current_file.parent.parent
        else:
            self.base_dir = Path(base_dir)
        
        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        
        # 로그 보존 정책 (일 단위)
        self.log_retention_days = {
            'trading': 7,      # 매매 로그: 7일
            'system': 3,       # 시스템 로그: 3일
            'error': 14,       # 에러 로그: 14일
            'debug': 1         # 디버그 로그: 1일
        }
    
    def get_log_file_path(self, log_type: str, algorithm_name: str = None, account_type: str = None) -> Path:
        """
        로그 파일 경로 생성
        
        Args:
            log_type: 로그 타입 (trading, system, error, debug)
            algorithm_name: 알고리즘 이름 (매매 로그용)
            account_type: 계정 타입 (REAL, MOCK)
        
        Returns:
            로그 파일 경로
        """
        date_str = datetime.now().strftime("%Y%m%d")
        
        if log_type == 'trading' and algorithm_name and account_type:
            # 매매 로그: trading/real_trading_알고리즘명_20250804.log
            trading_dir = self.logs_dir / "trading"
            trading_dir.mkdir(exist_ok=True)
            
            safe_algorithm_name = self._safe_filename(algorithm_name)
            account_prefix = account_type.lower()
            filename = f"{account_prefix}_trading_{safe_algorithm_name}_{date_str}.log"
            return trading_dir / filename
        
        elif log_type == 'system':
            # 시스템 로그: system/system_20250804.log
            system_dir = self.logs_dir / "system"
            system_dir.mkdir(exist_ok=True)
            filename = f"system_{date_str}.log"
            return system_dir / filename
        
        elif log_type == 'error':
            # 에러 로그: error/error_20250804.log
            error_dir = self.logs_dir / "error"
            error_dir.mkdir(exist_ok=True)
            filename = f"error_{date_str}.log"
            return error_dir / filename
        
        elif log_type == 'debug':
            # 디버그 로그: debug/debug_20250804.log
            debug_dir = self.logs_dir / "debug"
            debug_dir.mkdir(exist_ok=True)
            filename = f"debug_{date_str}.log"
            return debug_dir / filename
        
        else:
            # 기본 로그: logs/general_20250804.log
            filename = f"general_{date_str}.log"
            return self.logs_dir / filename
    
    def _safe_filename(self, name: str) -> str:
        """파일명으로 사용할 수 있도록 문자열 정리"""
        import re
        # 알파벳, 숫자, 하이픈, 언더스코어만 허용
        safe_name = re.sub(r'[^a-zA-Z0-9\-_]', '_', name)
        # 연속된 언더스코어 제거
        safe_name = re.sub(r'_+', '_', safe_name)
        # 앞뒤 언더스코어 제거
        return safe_name.strip('_')
    
    def setup_logger(self, 
                    log_type: str, 
                    logger_name: str,
                    algorithm_name: str = None,
                    account_type: str = None,
                    level: int = logging.INFO) -> logging.Logger:
        """
        로거 설정
        
        Args:
            log_type: 로그 타입
            logger_name: 로거 이름
            algorithm_name: 알고리즘 이름
            account_type: 계정 타입
            level: 로그 레벨
        
        Returns:
            설정된 로거
        """
        # 기존 핸들러 제거 (중복 방지)
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        logger.setLevel(level)
        
        # 파일 핸들러 추가
        log_file_path = self.get_log_file_path(log_type, algorithm_name, account_type)
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        
        # 포맷터 설정 - 간결한 형식
        # 커스텀 포맷터 클래스 사용
        formatter = SimpleLogFormatter()
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # 콘솔 핸들러 추가 (선택적)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def cleanup_old_logs(self, dry_run: bool = False) -> List[str]:
        """
        오래된 로그 파일 정리
        
        Args:
            dry_run: 실제 삭제하지 않고 삭제 대상만 반환
        
        Returns:
            삭제된(또는 삭제 예정) 파일 목록
        """
        deleted_files = []
        current_time = datetime.now()
        
        for log_type, retention_days in self.log_retention_days.items():
            cutoff_date = current_time - timedelta(days=retention_days)
            
            # 각 로그 타입별 디렉토리에서 파일 검색
            if log_type == 'trading':
                pattern = self.logs_dir / "trading" / "*.log"
            elif log_type == 'system':
                pattern = self.logs_dir / "system" / "*.log"
            elif log_type == 'error':
                pattern = self.logs_dir / "error" / "*.log"
            elif log_type == 'debug':
                pattern = self.logs_dir / "debug" / "*.log"
            else:
                continue
            
            for log_file in glob.glob(str(pattern)):
                log_path = Path(log_file)
                
                # 파일 수정 시간 확인
                if log_path.exists():
                    file_time = datetime.fromtimestamp(log_path.stat().st_mtime)
                    file_size = log_path.stat().st_size
                    
                    # 오래된 파일이거나 빈 파일(0바이트)인 경우 삭제
                    should_delete = (file_time < cutoff_date) or (file_size == 0)
                    
                    if should_delete:
                        if not dry_run:
                            try:
                                log_path.unlink()
                                deleted_files.append(str(log_path))
                            except Exception as e:
                                print(f"로그 파일 삭제 실패: {log_path} - {e}")
                        else:
                            deleted_files.append(str(log_path))
        
        # 루트 디렉토리의 오래된 로그 파일도 정리 (기존 파일들)
        try:
            for filename in os.listdir(self.base_dir):
                if filename.endswith('.log'):
                    old_log_path = self.base_dir / filename
                    # logs 폴더 내 파일은 제외
                    if str(old_log_path).startswith(str(self.logs_dir)):
                        continue
                        
                    if old_log_path.exists():
                        file_time = datetime.fromtimestamp(old_log_path.stat().st_mtime)
                        if file_time < current_time - timedelta(days=1):  # 1일 이상 된 루트 로그는 삭제
                            if not dry_run:
                                try:
                                    old_log_path.unlink()
                                    deleted_files.append(str(old_log_path))
                                except Exception as e:
                                    print(f"기존 로그 파일 삭제 실패: {old_log_path} - {e}")
                            else:
                                deleted_files.append(str(old_log_path))
        except (OSError, PermissionError) as e:
            print(f"루트 디렉토리 로그 파일 정리 오류: {e}")
        
        return deleted_files
    
    def get_log_stats(self) -> dict:
        """로그 파일 통계 정보 반환"""
        stats = {
            'total_files': 0,
            'total_size_mb': 0.0,
            'by_type': {}
        }
        
        # 각 로그 타입별 통계
        for log_type in ['trading', 'system', 'error', 'debug']:
            type_dir = self.logs_dir / log_type
            if type_dir.exists():
                files = list(type_dir.glob("*.log"))
                total_size = sum(f.stat().st_size for f in files if f.exists())
                
                stats['by_type'][log_type] = {
                    'files': len(files),
                    'size_mb': total_size / 1024 / 1024
                }
                
                stats['total_files'] += len(files)
                stats['total_size_mb'] += total_size / 1024 / 1024
        
        # 루트 디렉토리의 기존 로그 파일도 포함
        root_logs = []
        try:
            for filename in os.listdir(self.base_dir):
                if filename.endswith('.log'):
                    log_file = self.base_dir / filename
                    # logs 폴더가 아닌 루트의 로그 파일만 포함
                    if not str(log_file).startswith(str(self.logs_dir)):
                        root_logs.append(log_file)
        except (OSError, PermissionError) as e:
            print(f"루트 디렉토리 로그 파일 스캔 오류: {e}")
        
        if root_logs:
            root_size = sum(f.stat().st_size for f in root_logs if f.exists())
            stats['by_type']['root_legacy'] = {
                'files': len(root_logs),
                'size_mb': root_size / 1024 / 1024
            }
            stats['total_files'] += len(root_logs)
            stats['total_size_mb'] += root_size / 1024 / 1024
        
        return stats


# 전역 로그 매니저 인스턴스
_log_manager = None

def get_log_manager() -> LogManager:
    """전역 로그 매니저 인스턴스 반환"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
    return _log_manager


if __name__ == "__main__":
    # 테스트 및 정리 실행
    lm = LogManager()
    
    print("=== 로그 관리 시스템 테스트 ===")
    
    # 현재 로그 통계
    stats = lm.get_log_stats()
    print(f"\n현재 로그 파일 통계:")
    print(f"  총 파일 수: {stats['total_files']}")
    print(f"  총 용량: {stats['total_size_mb']:.2f} MB")
    
    for log_type, info in stats['by_type'].items():
        print(f"  {log_type}: {info['files']}개 파일, {info['size_mb']:.2f} MB")
    
    # 정리 대상 파일 확인 (dry run)
    cleanup_targets = lm.cleanup_old_logs(dry_run=True)
    if cleanup_targets:
        print(f"\n정리 대상 파일 ({len(cleanup_targets)}개):")
        for target in cleanup_targets:
            print(f"  - {target}")
        
        # 실제 정리 실행
        choice = input("\n위 파일들을 정리하시겠습니까? (y/N): ")
        if choice.lower() == 'y':
            deleted = lm.cleanup_old_logs(dry_run=False)
            print(f"✓ {len(deleted)}개 파일을 정리했습니다.")
    else:
        print("\n정리할 파일이 없습니다.")