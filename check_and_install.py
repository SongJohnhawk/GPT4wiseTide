#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tideWise 배포용 라이브러리 설치 및 검증 스크립트
필수 라이브러리들을 체크하고 누락된 라이브러리를 자동 설치
"""

import sys
import subprocess
import importlib
import os
from pathlib import Path

# UTF-8 인코딩 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# pkg_resources 대체 함수
def get_installed_version(package_name):
    """설치된 패키지 버전 확인"""
    try:
        import importlib.metadata
        return importlib.metadata.version(package_name)
    except ImportError:
        try:
            import pkg_resources
            return pkg_resources.get_distribution(package_name).version
        except:
            return None
    except:
        return None

def compare_versions(installed, required):
    """버전 비교"""
    try:
        def version_tuple(v):
            return tuple(map(int, v.split('.')))
        return version_tuple(installed) >= version_tuple(required)
    except:
        return True  # 비교 실패 시 통과로 처리

# tideWise 실행에 필요한 핵심 라이브러리 목록
REQUIRED_LIBRARIES = {
    # 필수 외부 라이브러리
    'requests': '2.25.0',
    'aiohttp': '3.8.0',
    'websockets': '10.0',
    'pandas': '1.3.0',
    'numpy': '1.21.0',
    'PyQt5': '5.15.0',
    'beautifulsoup4': '4.9.0',
    'lxml': '4.6.0',
    'openpyxl': '3.0.0',
    'python-dotenv': '0.19.0',
    'cryptography': '3.4.0',
    'pytz': '2021.1',
    'schedule': '1.1.0',
    
    # 내장 모듈들 (체크용)
    'asyncio': None,
    'json': None,
    'datetime': None,
    'threading': None,
    'logging': None,
    'configparser': None,
    'sqlite3': None,
    'hashlib': None,
    'base64': None,
    'hmac': None,
    'urllib': None,
    'time': None,
    'os': None,
    'sys': None,
    'pathlib': None,
    'dataclasses': None,
    'typing': None,
    'enum': None,
    'collections': None,
    'functools': None,
    'itertools': None,
    're': None,
    'math': None,
    'random': None,
    'pickle': None,
    'copy': None,
    'warnings': None,
    'traceback': None,
    'concurrent': None,
    'queue': None,
    'multiprocessing': None,
}

def check_python_version():
    """Python 버전 확인"""
    print("=" * 60)
    print("tideWise 설치 환경 검사")
    print("=" * 60)
    
    version = sys.version_info
    print(f"Python 버전: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("[ERROR] Python 3.8 이상이 필요합니다!")
        print("Python 3.8 이상을 설치해주세요.")
        print("다운로드: https://www.python.org/downloads/")
        return False
    else:
        print("[OK] Python 버전 확인 완료")
        return True

def is_built_in_module(module_name):
    """내장 모듈인지 확인"""
    try:
        if module_name in sys.builtin_module_names:
            return True
        
        # 표준 라이브러리 모듈 확인
        spec = importlib.util.find_spec(module_name)
        if spec and spec.origin:
            stdlib_path = os.path.dirname(os.__file__)
            return spec.origin.startswith(stdlib_path)
        return False
    except:
        return False

def check_library(lib_name, min_version=None):
    """라이브러리 설치 및 버전 확인"""
    try:
        # 내장 모듈 확인
        if min_version is None and is_built_in_module(lib_name):
            print(f"[OK] {lib_name}: 내장 모듈")
            return True
            
        # 설치된 라이브러리 확인
        installed_version = get_installed_version(lib_name)
        
        if installed_version:
            if min_version:
                if compare_versions(installed_version, min_version):
                    print(f"[OK] {lib_name}: {installed_version} (최소 요구: {min_version})")
                    return True
                else:
                    print(f"[WARN] {lib_name}: {installed_version} (업그레이드 필요: {min_version})")
                    return False
            else:
                print(f"[OK] {lib_name}: {installed_version}")
                return True
        else:
            # 모듈 import로 재확인
            try:
                importlib.import_module(lib_name)
                print(f"[OK] {lib_name}: 설치됨 (버전 확인 불가)")
                return True
            except ImportError:
                print(f"[ERROR] {lib_name}: 설치되지 않음")
                return False
                
    except Exception as e:
        print(f"[ERROR] {lib_name}: 확인 중 오류 - {e}")
        return False

def install_library(lib_name, version=None):
    """라이브러리 설치"""
    try:
        if version:
            package = f"{lib_name}>={version}"
        else:
            package = lib_name
            
        print(f"[INSTALL] {lib_name} 설치 중...")
        
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", package, "--upgrade"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"[OK] {lib_name} 설치 완료")
            return True
        else:
            print(f"[ERROR] {lib_name} 설치 실패: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[ERROR] {lib_name} 설치 시간 초과")
        return False
    except Exception as e:
        print(f"[ERROR] {lib_name} 설치 중 오류: {e}")
        return False

def generate_install_commands(failed_libraries):
    """설치 실패한 라이브러리에 대한 수동 설치 명령어 생성"""
    if not failed_libraries:
        return
        
    print("\n" + "=" * 60)
    print("수동 설치가 필요한 라이브러리")
    print("=" * 60)
    
    # Windows 명령 프롬프트용
    print("\n📋 Windows 명령 프롬프트에서 실행할 명령어:")
    print("-" * 40)
    for lib_name, version in failed_libraries:
        if version:
            print(f"pip install {lib_name}>={version}")
        else:
            print(f"pip install {lib_name}")
    
    # 한 번에 설치하는 명령어
    libs_to_install = []
    for lib_name, version in failed_libraries:
        if version:
            libs_to_install.append(f"{lib_name}>={version}")
        else:
            libs_to_install.append(lib_name)
    
    if libs_to_install:
        print(f"\n🚀 한 번에 설치하는 명령어:")
        print("-" * 40)
        print(f"pip install {' '.join(libs_to_install)}")

def create_requirements_file():
    """requirements.txt 파일 생성"""
    requirements_content = []
    
    for lib_name, version in REQUIRED_LIBRARIES.items():
        if version:  # 버전이 지정된 외부 라이브러리만 추가
            requirements_content.append(f"{lib_name}>={version}")
    
    requirements_path = Path("requirements.txt")
    
    try:
        with open(requirements_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(requirements_content))
        print(f"[OK] requirements.txt 파일 생성: {requirements_path.absolute()}")
    except Exception as e:
        print(f"[ERROR] requirements.txt 생성 실패: {e}")

def check_k_autotrade_structure():
    """tideWise 필수 구조 확인"""
    print(f"\n[INFO] tideWise 구조 확인 중...")
    print("-" * 40)
    
    required_files = [
        "run.py",
        "stock_data_collector.py",
        "enhanced_theme_stocks.json",
        "trading_config.json"
    ]
    
    required_folders = [
        "Algorithm",
        "day_trade_Algorithm", 
        "support",
        "Policy",
        "backtesting",
        "backtest_results"
    ]
    
    missing_items = []
    
    # 파일 확인
    for file_name in required_files:
        if Path(file_name).exists():
            print(f"[OK] {file_name}")
        else:
            print(f"[ERROR] {file_name}")
            missing_items.append(file_name)
    
    # 폴더 확인
    for folder_name in required_folders:
        if Path(folder_name).exists():
            print(f"[OK] {folder_name}/")
        else:
            print(f"[ERROR] {folder_name}/")
            missing_items.append(f"{folder_name}/")
    
    if missing_items:
        print(f"\n[WARN] 누락된 파일/폴더: {len(missing_items)}개")
        for item in missing_items:
            print(f"   - {item}")
        return False
    else:
        print(f"\n[OK] tideWise 구조 확인 완료")
        return True

def main():
    """메인 실행 함수"""
    print("tideWise 환경 설정을 시작합니다...")
    
    # Python 버전 확인
    if not check_python_version():
        input("\nPress Enter to exit...")
        return False
    
    # tideWise 구조 확인
    if not check_k_autotrade_structure():
        print(f"\n[ERROR] tideWise 구조가 올바르지 않습니다.")
        print(f"올바른 tideWise 배포 패키지인지 확인해주세요.")
        input("\nPress Enter to exit...")
        return False
    
    print(f"\n[INFO] 필수 라이브러리 확인 중... (총 {len(REQUIRED_LIBRARIES)}개)")
    print("-" * 60)
    
    # 라이브러리 확인
    missing_libraries = []
    failed_installations = []
    
    for lib_name, min_version in REQUIRED_LIBRARIES.items():
        if not check_library(lib_name, min_version):
            missing_libraries.append((lib_name, min_version))
    
    # 누락된 라이브러리 설치 시도
    if missing_libraries:
        print(f"\n[SETUP] 누락된 라이브러리 자동 설치 중... (총 {len(missing_libraries)}개)")
        print("-" * 60)
        
        for lib_name, version in missing_libraries:
            if version:  # 외부 라이브러리만 설치 시도
                if not install_library(lib_name, version):
                    failed_installations.append((lib_name, version))
            else:
                # 내장 모듈이지만 확인되지 않은 경우
                print(f"[WARN] {lib_name}: 내장 모듈이지만 확인되지 않음")
    
    # 최종 결과
    print("\n" + "=" * 60)
    print("설치 결과 요약")
    print("=" * 60)
    
    total_libs = len(REQUIRED_LIBRARIES)
    failed_count = len(failed_installations)
    success_count = total_libs - failed_count
    
    print(f"[OK] 성공: {success_count}/{total_libs}")
    print(f"[ERROR] 실패: {failed_count}/{total_libs}")
    
    if failed_installations:
        print(f"\n[WARN] 설치 실패한 라이브러리: {failed_count}개")
        for lib_name, version in failed_installations:
            print(f"   - {lib_name} ({version})")
        
        # 수동 설치 명령어 생성
        generate_install_commands(failed_installations)
        
        # requirements.txt 생성
        print(f"\n[FILE] requirements.txt 파일을 생성합니다...")
        create_requirements_file()
        
        print(f"\n[TIP] Tip: 위 명령어를 실행한 후 다시 이 스크립트를 실행하세요.")
        input("\nPress Enter to exit...")
        return False
    else:
        print("\n[SUCCESS] 모든 필수 라이브러리가 설치되어 있습니다!")
        print("tideWise를 사용할 준비가 완료되었습니다.")
        
        # tideWise 실행 방법 안내
        print(f"\n[RUN] tideWise 실행 방법:")
        print(f"   python run.py")
        
        # API 설정 안내
        print(f"\n[WARN] 최초 실행 전 필수 설정:")
        print(f"   1. Policy/Register_Key/Register_Key.md 파일을 열어")
        print(f"   2. 한국투자증권 API KEY와 계좌 정보를 입력하세요")
        print(f"   3. 설정 완료 후 tideWise를 실행하세요")
        
        input("\nPress Enter to exit...")
        return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print(f"\n[OK] 설치 완료! tideWise를 사용할 수 있습니다.")
        else:
            print(f"\n[ERROR] 일부 라이브러리 설치가 필요합니다. 위의 명령어를 참고하세요.")
        
    except KeyboardInterrupt:
        print(f"\n\n[STOP] 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n[ERROR] 오류 발생: {e}")
        input("\nPress Enter to exit...")