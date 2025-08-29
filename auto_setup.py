#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tideWise 자동 설치 시스템
압축 해제 후 자동으로 실행되어 필수 라이브러리를 설치합니다.
"""

import sys
import subprocess
import os
from pathlib import Path
from datetime import datetime

# UTF-8 인코딩 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 필수 라이브러리 목록
REQUIRED_LIBRARIES = [
    ('requests', '2.28.0'),
    ('aiohttp', '3.8.0'),
    ('websockets', '10.0'),
    ('pandas', '1.5.0'),
    ('numpy', '1.23.0'),
    ('beautifulsoup4', '4.11.0'),
    ('lxml', '4.9.0'),
    ('openpyxl', '3.0.0'),
    ('python-dotenv', '0.19.0'),
    ('cryptography', '38.0.0'),
    ('pytz', '2021.1'),
    ('schedule', '1.1.0'),
    ('psutil', '5.9.0'),
    ('colorama', '0.4.5'),
    ('tqdm', '4.64.0'),
    ('PyYAML', '6.0'),
    ('python-dateutil', '2.8.0'),
    ('configparser', '5.3.0'),
    ('numba', '0.56.0')
]

class AutoSetup:
    def __init__(self):
        self.current_dir = Path(__file__).parent
        self.success_libs = []
        self.failed_libs = []
        self.skipped_libs = []
        
    def check_python_version(self):
        """Python 버전 확인"""
        print("="*60)
        print("tideWise 자동 설치 시스템")
        print("="*60)
        print(f"\nPython 버전: {sys.version}")
        
        if sys.version_info < (3, 8):
            print("\n[ERROR] Python 3.8 이상이 필요합니다!")
            print("https://www.python.org/downloads/ 에서 최신 버전을 설치하세요.")
            return False
        
        print("[OK] Python 버전 확인 완료")
        return True
    
    def check_pip(self):
        """pip 업그레이드"""
        print("\n[진행] pip 업그레이드 중...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                capture_output=True,
                text=True,
                timeout=60
            )
            print("[OK] pip 업그레이드 완료")
            return True
        except Exception as e:
            print(f"[WARN] pip 업그레이드 실패: {e}")
            return True  # 계속 진행
    
    def is_library_installed(self, lib_name, min_version=None):
        """라이브러리 설치 여부 확인"""
        try:
            import importlib.metadata
            version = importlib.metadata.version(lib_name)
            
            if min_version:
                installed = tuple(map(int, version.split('.')[:2]))
                required = tuple(map(int, min_version.split('.')[:2]))
                
                if installed >= required:
                    return True, version
                else:
                    return False, version
            else:
                return True, version
                
        except ImportError:
            return False, None
    
    def install_library(self, lib_name, min_version):
        """라이브러리 설치"""
        try:
            # 이미 설치되어 있는지 확인
            is_installed, current_version = self.is_library_installed(lib_name, min_version)
            
            if is_installed:
                self.skipped_libs.append((lib_name, current_version))
                print(f"[SKIP] {lib_name} (이미 설치됨: v{current_version})")
                return True
            
            # 설치 시도
            print(f"[설치] {lib_name}>={min_version} 설치 중...")
            
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", f"{lib_name}>={min_version}"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                self.success_libs.append((lib_name, min_version))
                print(f"[OK] {lib_name} 설치 완료")
                return True
            else:
                self.failed_libs.append((lib_name, min_version, result.stderr))
                print(f"[FAIL] {lib_name} 설치 실패")
                return False
                
        except subprocess.TimeoutExpired:
            self.failed_libs.append((lib_name, min_version, "Timeout"))
            print(f"[FAIL] {lib_name} 설치 시간 초과")
            return False
        except Exception as e:
            self.failed_libs.append((lib_name, min_version, str(e)))
            print(f"[FAIL] {lib_name} 설치 오류: {e}")
            return False
    
    def install_all_libraries(self):
        """모든 라이브러리 설치"""
        print("\n" + "="*60)
        print("필수 라이브러리 설치")
        print("="*60)
        
        total = len(REQUIRED_LIBRARIES)
        
        for i, (lib_name, min_version) in enumerate(REQUIRED_LIBRARIES, 1):
            print(f"\n[{i}/{total}] {lib_name} 처리 중...")
            self.install_library(lib_name, min_version)
        
        print("\n" + "="*60)
        print("설치 결과")
        print("="*60)
        print(f"성공: {len(self.success_libs)}개")
        print(f"건너뜀: {len(self.skipped_libs)}개")
        print(f"실패: {len(self.failed_libs)}개")
    
    def create_failed_libs_report(self):
        """실패한 라이브러리 리포트 생성"""
        if not self.failed_libs:
            return
        
        report_file = self.current_dir / "설치해야_하는_라이브러리_목록.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("tideWise 필수 라이브러리 수동 설치 가이드\n")
            f.write("="*80 + "\n")
            f.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"자동 설치 실패 라이브러리: {len(self.failed_libs)}개\n")
            f.write("\n")
            f.write("="*80 + "\n")
            f.write("1. 설치 실패 라이브러리 목록\n")
            f.write("="*80 + "\n\n")
            
            for lib_name, min_version, error in self.failed_libs:
                f.write(f"라이브러리: {lib_name}\n")
                f.write(f"최소 버전: {min_version}\n")
                f.write(f"오류 내용: {error[:100]}...\n")
                f.write("-"*40 + "\n\n")
            
            f.write("="*80 + "\n")
            f.write("2. Windows Command Prompt 설치 명령어\n")
            f.write("="*80 + "\n\n")
            
            f.write("각 라이브러리를 개별적으로 설치:\n")
            f.write("-"*40 + "\n")
            for lib_name, min_version, _ in self.failed_libs:
                f.write(f"pip install {lib_name}>={min_version}\n")
            
            f.write("\n한 번에 모두 설치:\n")
            f.write("-"*40 + "\n")
            libs_str = " ".join([f"{lib}>={ver}" for lib, ver, _ in self.failed_libs])
            f.write(f"pip install {libs_str}\n")
            
            f.write("\n="*80 + "\n")
            f.write("3. Windows PowerShell 설치 명령어\n")
            f.write("="*80 + "\n\n")
            
            f.write("각 라이브러리를 개별적으로 설치:\n")
            f.write("-"*40 + "\n")
            for lib_name, min_version, _ in self.failed_libs:
                f.write(f"python -m pip install {lib_name}>={min_version}\n")
            
            f.write("\n한 번에 모두 설치:\n")
            f.write("-"*40 + "\n")
            f.write(f"python -m pip install {libs_str}\n")
            
            f.write("\n="*80 + "\n")
            f.write("4. 설치 문제 해결 방법\n")
            f.write("="*80 + "\n\n")
            
            f.write("방법 1: 관리자 권한으로 실행\n")
            f.write("-"*40 + "\n")
            f.write("1. 명령 프롬프트를 우클릭 → '관리자 권한으로 실행'\n")
            f.write("2. 위의 명령어를 실행\n\n")
            
            f.write("방법 2: 사용자 디렉토리에 설치\n")
            f.write("-"*40 + "\n")
            for lib_name, min_version, _ in self.failed_libs:
                f.write(f"pip install --user {lib_name}>={min_version}\n")
            
            f.write("\n방법 3: 캐시 삭제 후 재설치\n")
            f.write("-"*40 + "\n")
            f.write("pip cache purge\n")
            for lib_name, min_version, _ in self.failed_libs:
                f.write(f"pip install --no-cache-dir {lib_name}>={min_version}\n")
            
            f.write("\n방법 4: 프록시 설정 (회사 네트워크인 경우)\n")
            f.write("-"*40 + "\n")
            f.write("pip config set global.proxy http://proxy.company.com:8080\n")
            f.write("(프록시 주소는 네트워크 관리자에게 문의)\n")
            
            f.write("\n="*80 + "\n")
            f.write("5. 추가 도움말\n")
            f.write("="*80 + "\n\n")
            
            f.write("• Python 버전 확인: python --version\n")
            f.write("• pip 업그레이드: python -m pip install --upgrade pip\n")
            f.write("• 설치된 패키지 확인: pip list\n")
            f.write("• 특정 패키지 정보: pip show [패키지명]\n")
            
            f.write("\n문제가 지속되는 경우:\n")
            f.write("1. Python 재설치 (최신 버전)\n")
            f.write("2. 가상환경 사용 검토\n")
            f.write("3. 방화벽/백신 프로그램 예외 설정\n")
            
            f.write("\n="*80 + "\n")
            f.write("설치 완료 후 'python run.py'를 실행하여 tideWise를 시작하세요!\n")
            f.write("="*80 + "\n")
        
        print(f"\n[INFO] 설치 가이드 생성: {report_file}")
    
    def run(self):
        """자동 설치 실행"""
        print("\n🚀 tideWise 자동 설치를 시작합니다...")
        
        # Python 버전 확인
        if not self.check_python_version():
            input("\nEnter 키를 눌러 종료...")
            return False
        
        # pip 업그레이드
        self.check_pip()
        
        # 라이브러리 설치
        self.install_all_libraries()
        
        # 실패한 라이브러리 리포트 생성
        if self.failed_libs:
            self.create_failed_libs_report()
            print("\n⚠️ 일부 라이브러리 설치에 실패했습니다.")
            print("'설치해야_하는_라이브러리_목록.txt' 파일을 참고하여 수동 설치하세요.")
        else:
            print("\n✅ 모든 라이브러리가 성공적으로 설치되었습니다!")
        
        print("\n" + "="*60)
        print("tideWise 설치 완료")
        print("="*60)
        print("\n다음 단계:")
        print("1. Policy/Register_Key/Register_Key.md 파일에 API 정보 입력")
        print("2. python run.py 실행")
        
        return True

def main():
    """메인 실행 함수"""
    installer = AutoSetup()
    
    # 자동 실행 감지 (압축 해제 시)
    if os.environ.get('K_AUTOTRADE_AUTO_SETUP') == '1' or True:  # 항상 실행
        print("압축 해제 감지 - 자동 설치 시작")
        installer.run()
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n오류 발생: {e}")
        sys.exit(1)