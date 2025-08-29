#!/usr/bin/env python3
"""
tideWise 임시 파일 정리 도구
- 시스템 실행 후 생성되는 불필요한 임시 파일들을 자동으로 정리
- 테스트 후 생성되는 이상한 파일명 파일들 삭제
- NUL, nul 등의 Windows 리디렉션 오류로 생성된 파일들 삭제
"""

import os
import glob
import sys
from pathlib import Path
import re
import logging

# 한국어 주석: 임시 파일 정리 시스템
class TempFileCleaner:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.cleaned_files = []
        self.errors = []
        
        # 로깅 설정 - 간결한 형식
        logging.basicConfig(level=logging.INFO, format='%(message)s')
        self.logger = logging.getLogger(__name__)
    
    def clean_temp_files(self):
        """임시 파일들을 정리하는 메인 함수"""
        self.logger.info("tideWise 임시 파일 정리 시작")
        
        # 1. 이상한 파일명 패턴 정리 (doTest && 형태)
        self._clean_weird_filenames()
        
        # 2. NUL/nul 파일들 정리  
        self._clean_null_files()
        
        # 3. 임시 캐시 파일들 정리
        self._clean_cache_files()
        
        # 4. 테스트 임시 파일들 정리
        self._clean_test_temp_files()
        
        # 결과 보고
        self._report_results()
        
        return len(self.cleaned_files), len(self.errors)
    
    def _clean_weird_filenames(self):
        """이상한 파일명 패턴 정리 (쉘 명령어가 파일명이 된 경우)"""
        weird_patterns = [
            r"doTest.*&&.*",  # doTest && ... 패턴
            r".*&&.*cp.*",    # && cp ... 패턴  
            r".*&&.*mv.*",    # && mv ... 패턴
            r"^cp\s+.*",      # cp로 시작하는 파일명
            r"^mv\s+.*",      # mv로 시작하는 파일명
        ]
        
        try:
            for file_path in self.project_root.iterdir():
                if file_path.is_file():
                    filename = file_path.name
                    
                    # 패턴 매칭 검사
                    for pattern in weird_patterns:
                        if re.match(pattern, filename):
                            self._safe_remove(file_path, "이상한 파일명")
                            break
                            
        except Exception as e:
            self.errors.append(f"이상한 파일명 정리 오류: {e}")
    
    def _clean_null_files(self):
        """NUL/nul 관련 파일들 정리"""
        null_filenames = ['nul', 'NUL', 'null', 'NULL']
        
        for filename in null_filenames:
            file_path = self.project_root / filename
            if file_path.exists():
                self._safe_remove(file_path, "NULL 디바이스 파일")
    
    def _clean_cache_files(self):
        """임시 캐시 파일들 정리 (옵션)"""
        cache_patterns = [
            "*.tmp",
            "*.temp", 
            "*~",
            "*.bak",
            ".DS_Store"
        ]
        
        for pattern in cache_patterns:
            try:
                for file_path in self.project_root.glob(pattern):
                    if file_path.is_file():
                        self._safe_remove(file_path, "캐시 파일")
            except Exception as e:
                self.errors.append(f"캐시 파일 정리 오류: {e}")
    
    def _clean_test_temp_files(self):
        """테스트 관련 임시 파일들 정리"""
        test_temp_patterns = [
            "test_*.tmp",
            "*.test.tmp",
            "temp_test_*",
            "*_test_temp*"
        ]
        
        for pattern in test_temp_patterns:
            try:
                for file_path in self.project_root.glob(pattern):
                    if file_path.is_file():
                        self._safe_remove(file_path, "테스트 임시 파일")
            except Exception as e:
                self.errors.append(f"테스트 임시 파일 정리 오류: {e}")
    
    def _safe_remove(self, file_path: Path, file_type: str):
        """안전한 파일 삭제"""
        try:
            if file_path.exists():
                file_path.unlink()
                self.cleaned_files.append(f"{file_type}: {file_path.name}")
                self.logger.info(f"삭제됨: {file_path.name} ({file_type})")
        except PermissionError:
            self.errors.append(f"권한 없음: {file_path.name}")
        except Exception as e:
            self.errors.append(f"삭제 실패 {file_path.name}: {e}")
    
    def _report_results(self):
        """정리 결과 보고"""
        print("\n" + "="*60)
        print("tideWise 임시 파일 정리 완료")
        print("="*60)
        
        if self.cleaned_files:
            print(f"[OK] 정리된 파일: {len(self.cleaned_files)}개")
            for file_info in self.cleaned_files:
                print(f"   - {file_info}")
        else:
            # 정리할 임시 파일 없음 - 메시지 숨김
        
        if self.errors:
            print(f"\n[WARN] 오류 발생: {len(self.errors)}개")  
            for error in self.errors:
                print(f"   - {error}")
        
        print("="*60)


def clean_temp_files_standalone():
    """독립 실행 함수"""
    # tideWise 프로젝트 루트 자동 감지
    current_path = Path(__file__).resolve()
    
    # support 폴더에서 실행되므로 부모 디렉토리가 프로젝트 루트
    project_root = current_path.parent.parent
    
    # tideWise 폴더인지 확인
    if not (project_root / "run.py").exists():
        print("[ERROR] tideWise 프로젝트 루트를 찾을 수 없습니다.")
        return False
    
    # 정리 실행
    cleaner = TempFileCleaner(project_root)
    cleaned_count, error_count = cleaner.clean_temp_files()
    
    return error_count == 0


if __name__ == "__main__":
    try:
        success = clean_temp_files_standalone()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단됨")
        sys.exit(1)
    except Exception as e:
        print(f"오류: {e}")
        sys.exit(1)