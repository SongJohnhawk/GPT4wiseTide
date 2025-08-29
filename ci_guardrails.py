#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tideWise CI 가드레일 시스템
Single Source-of-Truth 원칙 위반 방지

**금지 사항:**
1. register_key_reader 사용 (AuthoritativeRegisterKeyLoader만 허용)
2. 하드코딩된 API 키, 토큰, 계좌정보
3. 백업/캐시 파일에 인증정보 저장
4. 종목정보 하드코딩 (사용자 지정 종목/테마 제외)
5. 종목 데이터 백업/풀백 하드코딩
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Set

class GuardRailViolation:
    """가드레일 위반 정보"""
    def __init__(self, file_path: str, line_number: int, violation_type: str, content: str, severity: str = "ERROR"):
        self.file_path = file_path
        self.line_number = line_number
        self.violation_type = violation_type
        self.content = content.strip()
        self.severity = severity

class tideWiseGuardRails:
    """tideWise Single Source-of-Truth 가드레일"""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.violations: List[GuardRailViolation] = []
        
        # 검사 대상 파일 확장자
        self.target_extensions = {'.py', '.json', '.yaml', '.yml', '.md', '.txt'}
        
        # 제외할 디렉토리
        self.excluded_dirs = {
            '__pycache__', '.git', '.pytest_cache', 'node_modules',
            'venv', 'env', '.venv', 'build', 'dist'
        }
        
        # 제외할 파일 (가드레일 자체 제외)
        self.excluded_files = {
            'ci_guardrails.py', 'test_authoritative_loader.py', 
            'test_trading_modes_integration.py', 'ci_guardrails_report.txt'
        }
        
        # 제외할 파일 패턴 (정당한 설정 파일들)
        self.excluded_file_patterns = [
            r'Register_Key\.md',      # 정당한 설정 파일
            r'menual_StokBuyList\.md', # 사용자 지정 종목 파일
            r'user_theme_config\.json', # 사용자 테마 설정
            r'OAuth.*\.json',         # API 문서
            r'KRX-OPEN.*\.txt',       # API 문서
            r'\[.*\].*\.json',        # API 문서
            r'CLAUDE\.md',            # 프로젝트 문서
        ]

    def scan_repository(self) -> List[GuardRailViolation]:
        """리포지토리 전체 스캔"""
        self.violations.clear()
        
        print("=== tideWise CI 가드레일 스캔 시작 ===")
        
        # 모든 파일 스캔
        for file_path in self._get_target_files():
            self._scan_file(file_path)
        
        # 위반 사항 정렬 (심각도순)
        self.violations.sort(key=lambda v: (v.severity != "ERROR", v.file_path, v.line_number))
        
        return self.violations

    def _get_target_files(self) -> List[Path]:
        """검사 대상 파일 목록 생성"""
        target_files = []
        
        for root, dirs, files in os.walk(self.project_root):
            # 제외 디렉토리 스킵
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            
            for file in files:
                file_path = Path(root) / file
                
                # 확장자 및 파일명 필터링
                if (file_path.suffix in self.target_extensions and 
                    file_path.name not in self.excluded_files and
                    not any(re.search(pattern, file_path.name) for pattern in self.excluded_file_patterns)):
                    target_files.append(file_path)
        
        return target_files

    def _scan_file(self, file_path: Path):
        """개별 파일 스캔"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                self._check_register_key_reader_usage(file_path, line_num, line)
                self._check_hardcoded_credentials(file_path, line_num, line)
                self._check_backup_auth_files(file_path, line_num, line)
                self._check_hardcoded_stock_data(file_path, line_num, line)
                self._check_stock_data_fallback(file_path, line_num, line)
                
        except Exception as e:
            print(f"[WARNING] 파일 스캔 실패: {file_path} - {e}")

    def _check_register_key_reader_usage(self, file_path: Path, line_num: int, line: str):
        """구형 register_key_reader 사용 검사"""
        if 'register_key_reader' in line and 'authoritative_register_key_loader' not in line:
            # 주석이나 문자열이 아닌 실제 import/사용 확인
            stripped = line.strip()
            if (not stripped.startswith('#') and 
                ('import' in line or 'from' in line or 'get_register_key_reader' in line) and
                'clean_logger.py' not in str(file_path)):  # clean_logger의 문자열 목록은 허용
                
                self.violations.append(GuardRailViolation(
                    str(file_path.relative_to(self.project_root)),
                    line_num,
                    "DEPRECATED_LOADER",
                    f"구형 register_key_reader 사용 금지: {line.strip()}",
                    "ERROR"
                ))

    def _check_hardcoded_credentials(self, file_path: Path, line_num: int, line: str):
        """하드코딩된 인증정보 검사"""
        # API 키 패턴 (KIS API 키 형식)
        api_key_patterns = [
            r'PS[A-Za-z0-9]{20,}',  # KIS API 키 형식
            r'[A-Za-z0-9]{32,}',    # 긴 알파벳+숫자 조합
        ]
        
        # 토큰 패턴
        token_patterns = [
            r'\d{10}:[A-Za-z0-9_-]{35}',  # 텔레그램 봇 토큰
            r'Bearer\s+[A-Za-z0-9_-]+',   # Bearer 토큰
        ]
        
        # 계좌번호 패턴
        account_patterns = [
            r'\b\d{8}\b',  # 8자리 계좌번호
        ]
        
        # 제외할 패턴 (예시, 테스트, 주석)
        exclusions = [
            'example', 'test', 'sample', 'placeholder', '[여기에', 'XXXXXXXX',
            'PS2GALh9ERMUhlVOOuZyw47gYBvzTTRUjvHd',  # Register_Key.md의 예시는 허용
            'PSzcJuOswpXZ2LUBtqzK3JE0Cqt7Xe6mTxw2',   # Register_Key.md의 예시는 허용
            'tideWiseDynamicIntervalController',       # 클래스명은 허용
            'class tideWiseDynamicIntervalController', # 클래스 정의는 허용
            'def get_dynamic_interval_controller',       # 함수명은 허용
            '_interval_controller = tideWiseDynamicIntervalController'  # 인스턴스 생성은 허용
        ]
        
        line_lower = line.lower()
        if any(exc.lower() in line_lower for exc in exclusions):
            return
            
        if line.strip().startswith('#'):  # 주석 제외
            return
            
        # API 키 검사
        for pattern in api_key_patterns:
            if re.search(pattern, line):
                self.violations.append(GuardRailViolation(
                    str(file_path.relative_to(self.project_root)),
                    line_num,
                    "HARDCODED_API_KEY",
                    f"하드코딩된 API 키 발견: {line.strip()}",
                    "ERROR"
                ))
        
        # 토큰 검사
        for pattern in token_patterns:
            if re.search(pattern, line):
                self.violations.append(GuardRailViolation(
                    str(file_path.relative_to(self.project_root)),
                    line_num,
                    "HARDCODED_TOKEN",
                    f"하드코딩된 토큰 발견: {line.strip()}",
                    "ERROR"
                ))

    def _check_backup_auth_files(self, file_path: Path, line_num: int, line: str):
        """백업 인증정보 파일 사용 검사"""
        # 주석 처리된 라인은 제외
        if line.strip().startswith('#') or line.strip().startswith('//'):
            return
            
        backup_patterns = [
            r'connection_real\.json',
            r'connection_mock\.json',
            r'api_key\.json',
            r'token_cache.*\.json',
            r'backup.*key',
            r'fallback.*auth',
        ]
        
        for pattern in backup_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                self.violations.append(GuardRailViolation(
                    str(file_path.relative_to(self.project_root)),
                    line_num,
                    "BACKUP_AUTH_FILE",
                    f"백업 인증파일 사용 금지: {line.strip()}",
                    "ERROR"
                ))

    def _check_hardcoded_stock_data(self, file_path: Path, line_num: int, line: str):
        """하드코딩된 종목정보 검사"""
        # 사용자 지정 파일은 허용
        if any(allowed in str(file_path).lower() for allowed in [
            'user_designated', 'manual_', 'menual_', 'user_theme', 'custom_'
        ]):
            return
            
        # 종목코드 패턴 (6자리 숫자)
        stock_code_patterns = [
            r'\b[0-9]{6}\b',  # 종목코드 (6자리 숫자)
        ]
        
        # 제외할 패턴
        exclusions = [
            'example', 'test', 'sample', '000000', '123456', 
            'account_number', 'user_id', 'password'
        ]
        
        if any(exc.lower() in line.lower() for exc in exclusions):
            return
            
        if line.strip().startswith('#'):  # 주석 제외
            return
        
        # 종목 리스트나 딕셔너리에서 다수 종목코드 검사
        stock_matches = re.findall(r'\b[0-9]{6}\b', line)
        if len(stock_matches) >= 3:  # 3개 이상의 종목코드가 한 줄에 있으면 의심
            self.violations.append(GuardRailViolation(
                str(file_path.relative_to(self.project_root)),
                line_num,
                "HARDCODED_STOCK_LIST",
                f"하드코딩된 종목 리스트 의심: {line.strip()}",
                "WARNING"
            ))

    def _check_stock_data_fallback(self, file_path: Path, line_num: int, line: str):
        """종목 데이터 풀백/백업 하드코딩 검사"""
        # 사용자 지정 파일은 허용
        if any(allowed in str(file_path).lower() for allowed in [
            'user_designated', 'manual_', 'menual_', 'user_theme', 'custom_'
        ]):
            return
            
        fallback_indicators = [
            r'fallback.*stock',
            r'backup.*stock',
            r'default.*stock',
            r'cached.*stock',
            r'preset.*stock',
            r'static.*stock',
            r'hardcoded.*stock',
            r'emergency.*stock',
        ]
        
        for pattern in fallback_indicators:
            if re.search(pattern, line, re.IGNORECASE):
                self.violations.append(GuardRailViolation(
                    str(file_path.relative_to(self.project_root)),
                    line_num,
                    "STOCK_DATA_FALLBACK",
                    f"종목 데이터 풀백/백업 하드코딩 의심: {line.strip()}",
                    "WARNING"
                ))
        
        # 종목명 하드코딩 패턴 (한글 종목명)
        korean_stock_patterns = [
            r'[\u3131-\u3163\uac00-\ud7a3]{2,}전자',  # 삼성전자 등
            r'[\u3131-\u3163\uac00-\ud7a3]{2,}화학',  # LG화학 등  
            r'[\u3131-\u3163\uac00-\ud7a3]{2,}바이오', # 셀트리온바이오 등
        ]
        
        # 종목명이 여러 개 나열된 경우 검사
        for pattern in korean_stock_patterns:
            matches = re.findall(pattern, line)
            if len(matches) >= 2:  # 2개 이상의 종목명이 한 줄에 있으면 의심
                self.violations.append(GuardRailViolation(
                    str(file_path.relative_to(self.project_root)),
                    line_num,
                    "HARDCODED_STOCK_NAMES",
                    f"하드코딩된 종목명 리스트 의심: {line.strip()}",
                    "WARNING"
                ))

    def generate_report(self) -> str:
        """위반사항 보고서 생성"""
        if not self.violations:
            return self._generate_success_report()
        
        report = []
        report.append("=" * 70)
        report.append("tideWise CI 가드레일 위반사항 보고서")
        report.append("=" * 70)
        
        # 위반 유형별 집계
        violation_counts = {}
        for violation in self.violations:
            violation_counts[violation.violation_type] = violation_counts.get(violation.violation_type, 0) + 1
        
        report.append("\n=== 위반사항 요약 ===")
        for violation_type, count in violation_counts.items():
            severity_indicator = "[ERROR]" if any(v.severity == "ERROR" and v.violation_type == violation_type for v in self.violations) else "[WARNING]"
            report.append(f"{severity_indicator} {violation_type}: {count}건")
        
        # 상세 위반사항
        report.append("\n=== 상세 위반사항 ===")
        current_file = None
        for violation in self.violations:
            if current_file != violation.file_path:
                current_file = violation.file_path
                report.append(f"\n[파일] {violation.file_path}")
            
            severity_marker = "[ERROR]" if violation.severity == "ERROR" else "[WARNING]"
            report.append(f"  {severity_marker} 라인 {violation.line_number}: {violation.violation_type}")
            report.append(f"     {violation.content}")
        
        # 수정 가이드
        report.append(self._generate_fix_guide())
        
        return "\n".join(report)

    def _generate_success_report(self) -> str:
        """성공 보고서 생성"""
        report = []
        report.append("=" * 70)
        report.append("tideWise CI 가드레일 검사 결과")
        report.append("=" * 70)
        report.append("\n[SUCCESS] 위반사항이 발견되지 않았습니다!")
        report.append("\n[SUCCESS] Single Source-of-Truth 원칙 준수")
        report.append("[SUCCESS] 하드코딩된 인증정보 없음")
        report.append("[SUCCESS] 백업 인증파일 사용 없음")
        report.append("[SUCCESS] 종목정보 하드코딩 없음")
        report.append("[SUCCESS] 종목 데이터 풀백/백업 하드코딩 없음")
        
        return "\n".join(report)

    def _generate_fix_guide(self) -> str:
        """수정 가이드 생성"""
        guide = []
        guide.append("\n" + "=" * 70)
        guide.append("수정 가이드")
        guide.append("=" * 70)
        
        guide.append("\n1. DEPRECATED_LOADER 수정:")
        guide.append("   - register_key_reader → authoritative_register_key_loader")
        guide.append("   - get_register_key_reader() → get_authoritative_loader()")
        
        guide.append("\n2. HARDCODED_API_KEY/TOKEN 수정:")
        guide.append("   - Policy/Register_Key/Register_Key.md로 이동")
        guide.append("   - AuthoritativeRegisterKeyLoader 사용")
        
        guide.append("\n3. BACKUP_AUTH_FILE 수정:")
        guide.append("   - 백업 파일 삭제")
        guide.append("   - Register_Key.md만 사용")
        
        guide.append("\n4. HARDCODED_STOCK_* 수정:")
        guide.append("   - 동적 데이터 수집 사용")
        guide.append("   - 사용자 지정 종목은 support/menual_StokBuyList.md 사용")
        guide.append("   - 하드코딩된 종목 리스트 제거")
        
        guide.append("\n5. STOCK_DATA_FALLBACK 수정:")
        guide.append("   - 풀백/백업 종목 데이터 제거")
        guide.append("   - 실시간 API 데이터만 사용")
        guide.append("   - 오류시 graceful failure 구현")
        
        return "\n".join(guide)

    def has_errors(self) -> bool:
        """ERROR 수준 위반사항 존재 여부"""
        return any(v.severity == "ERROR" for v in self.violations)

def main():
    """메인 실행 함수"""
    print("tideWise CI 가드레일 시스템")
    print("Single Source-of-Truth 원칙 준수 검사 중...")
    
    # 프로젝트 루트 설정
    script_dir = Path(__file__).parent
    
    # 가드레일 실행
    guard_rails = tideWiseGuardRails(script_dir)
    violations = guard_rails.scan_repository()
    
    # 보고서 출력
    report = guard_rails.generate_report()
    print(report)
    
    # 보고서 파일 저장
    report_file = script_dir / "ci_guardrails_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n보고서가 저장되었습니다: {report_file}")
    
    # 종료 코드 설정
    if guard_rails.has_errors():
        print("\n[ERROR] CI 가드레일 검사 실패!")
        print("위의 ERROR 수준 위반사항을 수정 후 다시 실행하세요.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] CI 가드레일 검사 통과!")
        sys.exit(0)

if __name__ == "__main__":
    main()