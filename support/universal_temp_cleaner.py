#!/usr/bin/env python3
"""
범용 임시 파일 정리 도구
- 모든 디렉토리에서 사용 가능한 임시 파일 정리 도구
- NUL/nul 파일, 이상한 쉘 명령어 파일명, 캐시 파일 등 정리
"""

import os
import sys
import glob
import re
from pathlib import Path
import argparse

class UniversalTempCleaner:
    def __init__(self, target_path: Path):
        self.target_path = Path(target_path).resolve()
        self.cleaned_files = []
        self.errors = []
    
    def clean_all_temp_files(self, silent: bool = False):
        """모든 임시 파일들을 정리하는 메인 함수"""
        if not silent:
            print(f"범용 임시 파일 정리 시작: {self.target_path}")
        
        if not self.target_path.exists():
            if not silent:
                print(f"[ERROR] 경로가 존재하지 않습니다: {self.target_path}")
            return 0, 1
        
        # 1. 이상한 파일명 패턴 정리 (doTest && 형태)
        self._clean_weird_filenames(silent)
        
        # 2. NUL/nul 파일들 정리  
        self._clean_null_files(silent)
        
        # 3. 임시 캐시 파일들 정리
        self._clean_cache_files(silent)
        
        # 4. Windows 리디렉션 오류 파일들
        self._clean_redirection_files(silent)
        
        # 결과 보고
        if not silent:
            self._report_results()
        
        return len(self.cleaned_files), len(self.errors)
    
    def _clean_weird_filenames(self, silent: bool = False):
        """이상한 파일명 패턴 정리 (쉘 명령어가 파일명이 된 경우)"""
        weird_patterns = [
            r"doTest.*&&.*",  # doTest && ... 패턴
            r".*&&.*cp.*",    # && cp ... 패턴  
            r".*&&.*mv.*",    # && mv ... 패턴
            r"^cp\s+.*",      # cp로 시작하는 파일명
            r"^mv\s+.*",      # mv로 시작하는 파일명
            r".*rmdir.*failed.*",  # rmdir 오류 메시지 파일
            r"^find.*:",      # find 명령어 오류 파일
        ]
        
        try:
            for file_path in self.target_path.iterdir():
                if file_path.is_file():
                    filename = file_path.name
                    
                    # 패턴 매칭 검사
                    for pattern in weird_patterns:
                        if re.match(pattern, filename):
                            self._safe_remove(file_path, "이상한 파일명", silent=True)
                            break
                            
        except Exception as e:
            self.errors.append(f"이상한 파일명 정리 오류: {e}")
    
    def _clean_null_files(self, silent: bool = False):
        """NUL/nul 관련 파일들 정리"""
        null_filenames = ['nul', 'NUL', 'null', 'NULL', 'CON', 'con']
        
        for filename in null_filenames:
            file_path = self.target_path / filename
            if file_path.exists() and file_path.is_file():
                self._safe_remove(file_path, "NULL 디바이스 파일", silent=True)
    
    def _clean_cache_files(self, silent: bool = False):
        """임시 캐시 파일들 정리"""
        cache_patterns = [
            "*.tmp",
            "*.temp", 
            "*~",
            "*.bak",
            ".DS_Store",
            "Thumbs.db"
        ]
        
        for pattern in cache_patterns:
            try:
                for file_path in self.target_path.glob(pattern):
                    if file_path.is_file():
                        self._safe_remove(file_path, "캐시 파일", silent=True)
            except Exception as e:
                self.errors.append(f"캐시 파일 정리 오류: {e}")
    
    def _clean_redirection_files(self, silent: bool = False):
        """Windows 리디렉션 오류로 생성된 파일들 정리"""
        # Windows 배치 파일에서 잘못된 리디렉션으로 생성된 파일들
        redirection_files = [
            "2>&1",
            ">nul", 
            ">NUL",
            "2>nul",
            "2>NUL",
            "1>nul",
            "1>NUL",
            "2>&1>nul",
            "&>nul",
            "2>/dev/null"  # Linux 스타일이 Windows에서 파일로 생성된 경우
        ]
        
        for filename in redirection_files:
            file_path = self.target_path / filename
            if file_path.exists() and file_path.is_file():
                self._safe_remove(file_path, "리디렉션 오류 파일", silent=True)
                
        # Windows 명령어가 파일명이 된 경우도 추가로 감지
        command_files = [
            "del",
            "DEL", 
            "copy",
            "COPY",
            "move",
            "MOVE",
            "type",
            "TYPE"
        ]
        
        for filename in command_files:
            file_path = self.target_path / filename
            if file_path.exists() and file_path.is_file():
                self._safe_remove(file_path, "Windows 명령어 파일", silent=True)
    
    def _safe_remove(self, file_path: Path, file_type: str, silent: bool = False):
        """안전한 파일 삭제"""
        try:
            if file_path.exists() and file_path.is_file():
                file_path.unlink()
                self.cleaned_files.append(f"{file_type}: {file_path.name}")
                if not silent and self._is_debug_mode():
                    print(f"[삭제] {file_path.name} ({file_type})")
        except PermissionError:
            self.errors.append(f"권한 없음: {file_path.name}")
        except Exception as e:
            self.errors.append(f"삭제 실패 {file_path.name}: {e}")
    
    def _is_debug_mode(self) -> bool:
        """디버그 모드 확인"""
        import os
        return os.environ.get('K_AUTOTRADE_DEBUG', '').lower() in ['true', '1', 'yes']
    
    def _report_results(self):
        """정리 결과 보고 (디버그 모드에서만)"""
        if not self._is_debug_mode():
            return
            
        print("\n" + "="*80)
        print("                         tideWise v11.0")
        print("                    한국투자증권 자동매매 시스템")
        print("="*80)
        print("  알고리즘 기반 지능형 자동매매 | 실시간 시장 분석 | 리스크 관리")
        print("="*80)
        
        if self.cleaned_files:
            print(f"[OK] 정리된 파일: {len(self.cleaned_files)}개")
            for file_info in self.cleaned_files:
                print(f"   - {file_info}")
        else:
            print("[OK] 정리할 임시 파일이 없습니다.")
        
        if self.errors:
            print(f"\n[WARN] 오류 발생: {len(self.errors)}개")  
            for error in self.errors:
                print(f"   - {error}")
        
        print("="*80)
        print(f"[INFO] 임시 파일 정리 완료 ({len(self.cleaned_files)}개 파일 정리)")


def main():
    parser = argparse.ArgumentParser(description='범용 임시 파일 정리 도구')
    parser.add_argument('path', nargs='?', default='.', 
                       help='정리할 디렉토리 경로 (기본값: 현재 디렉토리)')
    parser.add_argument('--recursive', '-r', action='store_true',
                       help='하위 디렉토리까지 재귀적으로 정리')
    
    args = parser.parse_args()
    
    target_path = Path(args.path).resolve()
    
    if not target_path.exists():
        print(f"[ERROR] 경로가 존재하지 않습니다: {target_path}")
        return False
    
    if not target_path.is_dir():
        print(f"[ERROR] 디렉토리가 아닙니다: {target_path}")
        return False
    
    if args.recursive:
        # 재귀적으로 모든 하위 디렉토리 정리
        total_cleaned = 0
        total_errors = 0
        
        for root, dirs, files in os.walk(target_path):
            root_path = Path(root)
            cleaner = UniversalTempCleaner(root_path)
            cleaned_count, error_count = cleaner.clean_all_temp_files()
            total_cleaned += cleaned_count
            total_errors += error_count
        
        print(f"\n전체 정리 결과: {total_cleaned}개 파일 정리, {total_errors}개 오류")
        return total_errors == 0
    else:
        # 단일 디렉토리만 정리
        cleaner = UniversalTempCleaner(target_path)
        cleaned_count, error_count = cleaner.clean_all_temp_files()
        return error_count == 0


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단됨")
        sys.exit(1)
    except Exception as e:
        print(f"오류: {e}")
        sys.exit(1)