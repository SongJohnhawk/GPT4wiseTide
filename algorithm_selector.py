#!/usr/bin/env python3
"""
AlgorithmSelector - tideWise 알고리즘 선택 관리 클래스
run.py에서 분리된 알고리즘 선택 관련 기능들을 통합 관리
"""

import json
import importlib.util
from pathlib import Path
from typing import Optional, Dict, Any


class AlgorithmSelector:
    """알고리즘 선택 및 관리를 담당하는 클래스"""
    
    def __init__(self, project_root: Path):
        """
        AlgorithmSelector 초기화
        
        Args:
            project_root: 프로젝트 루트 디렉토리 경로
        """
        self.project_root = Path(project_root)
        self.algorithm_state_file = Path(__file__).parent / "selected_algorithm.json"
        self.day_trade_dir = self.project_root / "day_trade_Algorithm"
        
        # 전역 알고리즘 선택 상태
        self.selected_algorithm = {
            'filename': None,
            'algorithm_instance': None,
            'info': {
                'name': '선택된 알고리즘 없음',
                'description': '메뉴 3번에서 알고리즘을 선택하세요',
                'version': '1.0'
            }
        }
    
    def save_algorithm_state(self):
        """선택된 알고리즘 상태를 파일에 저장"""
        try:
            state_data = {
                'filename': self.selected_algorithm['filename'],
                'info': self.selected_algorithm['info'].copy()
            }
            with open(self.algorithm_state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"알고리즘 상태 저장 실패: {e}")
    
    def load_algorithm_state(self):
        """저장된 알고리즘 상태를 파일에서 로드 (통합 폴더 지원)"""
        try:
            if self.algorithm_state_file.exists():
                with open(self.algorithm_state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    
                filename = state_data.get('filename')
                if filename:
                    # 파일이 실제로 존재하는지 확인
                    if self._verify_algorithm_file_exists(filename):
                        # 알고리즘 인스턴스 로드 시도
                        algorithm_instance = self._load_algorithm_instance_from_file(filename)
                        if algorithm_instance:
                            self.selected_algorithm['filename'] = filename
                            self.selected_algorithm['algorithm_instance'] = algorithm_instance
                            # 파일명에서 확장자 제거한 이름 사용
                            algorithm_file_name = Path(filename).stem
                            self.selected_algorithm['info'] = {
                                'name': algorithm_file_name,
                                'filename': filename,
                                'description': algorithm_instance.get_description() if hasattr(algorithm_instance, 'get_description') else state_data.get('info', {}).get('description', ''),
                                'version': algorithm_instance.get_version() if hasattr(algorithm_instance, 'get_version') else state_data.get('info', {}).get('version', '1.0')
                            }
                            if self._is_debug_mode():
                                print(f"저장된 알고리즘 로드 성공: {filename}")
                            return  # 성공적으로 로드됨
                        else:
                            if self._is_debug_mode():
                                print(f"알고리즘 인스턴스 로드 실패: {filename}")
                    else:
                        if self._is_debug_mode():
                            print(f"저장된 알고리즘 파일을 찾을 수 없음: {filename}")
        except Exception as e:
            if self._is_debug_mode():
                print(f"알고리즘 상태 로드 실패: {e}")
        
        # 로드 실패 시 기본 상태 유지
    
    def _load_algorithm_instance_from_file(self, filename: str):
        """파일명으로부터 알고리즘 인스턴스를 로드"""
        try:
            # Algorithm 폴더에서 시도
            algorithm_path = self.project_root / "Algorithm" / filename
            if algorithm_path.exists():
                return self._load_python_algorithm_from_path(algorithm_path)
            
            # day_trade_Algorithm 폴더에서 시도
            day_trade_path = self.project_root / "day_trade_Algorithm" / filename
            if day_trade_path.exists():
                if filename.endswith('.py'):
                    return self._load_python_algorithm_from_path(day_trade_path)
                elif filename.endswith('.pine'):
                    return self._create_pine_script_wrapper(day_trade_path)
            
            return None
        except Exception as e:
            if self._is_debug_mode():
                print(f"알고리즘 인스턴스 로드 중 오류: {e}")
            return None
    
    def _load_python_algorithm_from_path(self, file_path: Path):
        """Python 알고리즘 파일에서 인스턴스 로드"""
        try:
            import sys
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))
            
            # 모듈 로드
            spec = importlib.util.spec_from_file_location("temp_algorithm", file_path)
            if spec is None or spec.loader is None:
                return None
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            # BaseAlgorithm을 상속받은 클래스 찾기
            from support.algorithm_interface import BaseAlgorithm
            
            for name in dir(module):
                obj = getattr(module, name)
                if (isinstance(obj, type) and 
                    issubclass(obj, BaseAlgorithm) and 
                    obj != BaseAlgorithm):
                    return obj()  # 인스턴스 생성
            
            return None
        except Exception as e:
            if self._is_debug_mode():
                print(f"Python 알고리즘 로드 오류: {e}")
            return None
    
    def select_algorithm(self):
        """자동매매 알고리즘 선택 및 변경"""
        print("\n[ 알고리즘 선택 ]")
        print("-" * 50)
        
        # 현재 선택된 알고리즘 표시
        # 파일명이 있으면 파일명을 우선 표시, 없으면 이름 표시
        algorithm_display = self.selected_algorithm['info'].get('filename', self.selected_algorithm['info']['name'])
        print(f"현재 알고리즘: {algorithm_display}")
        print("-" * 50)
        
        try:
            from support.algorithm_loader import get_algorithm_loader
            loader = get_algorithm_loader()
            
            # 알고리즘 메뉴 표시 및 선택
            selected_filename = loader.show_algorithm_menu()
            
            if selected_filename:
                # 선택된 알고리즘 로드
                algorithm = loader.load_algorithm(selected_filename)
                if algorithm:
                    # 전역 변수에 저장
                    self.selected_algorithm['filename'] = selected_filename
                    self.selected_algorithm['algorithm_instance'] = algorithm
                    # 파일명에서 확장자 제거한 이름 사용
                    algorithm_file_name = Path(selected_filename).stem
                    self.selected_algorithm['info'] = {
                        'name': algorithm_file_name,
                        'filename': selected_filename,
                        'description': algorithm.get_description(),
                        'version': algorithm.get_version()
                    }
                    
                    print(f"\nOK 알고리즘 선택 완료!")
                    print(f"이름: {algorithm_file_name}")
                    print(f"버전: {algorithm.get_version()}")
                    print(f"설명: {algorithm.get_description()}")
                    print(f"파일: {selected_filename}")
                    
                    # 알고리즘 상태 저장
                    self.save_algorithm_state()
                    
                    print("\n이제 모의투자(메뉴 1-2) 또는 실전투자(메뉴 1-1)를 시작할 수 있습니다.")
                    print("선택된 알고리즘은 다른 알고리즘을 선택할 때까지 계속 사용됩니다.")
                else:
                    print("ERR 알고리즘 로드에 실패했습니다.")
            else:
                print("알고리즘 선택이 취소되었습니다.")
                
        except Exception as e:
            print(f"ERR 알고리즘 선택 중 오류가 발생했습니다: {e}")
    
    def select_day_trade_algorithm(self):
        """단타매매 알고리즘 선택 및 변경"""
        print("\n[ 단타매매 알고리즘 선택 ]")
        print("-" * 50)
        
        # 현재 선택된 알고리즘 표시
        # 파일명이 있으면 파일명을 우선 표시, 없으면 이름 표시
        algorithm_display = self.selected_algorithm['info'].get('filename', self.selected_algorithm['info']['name'])
        print(f"현재 알고리즘: {algorithm_display}")
        print("-" * 50)
        
        try:
            # day_trade_Algorithm 폴더에서 알고리즘 스캔
            if not self.day_trade_dir.exists():
                print("단타매매 알고리즘 폴더가 존재하지 않습니다.")
                return
            
            # Python 및 Pine Script 파일 찾기
            algorithms = []
            
            # Python 파일 스캔
            for file_path in self.day_trade_dir.glob("*.py"):
                if file_path.name != "__init__.py":
                    algorithms.append({
                        'filename': file_path.name,
                        'filepath': file_path,
                        'name': file_path.stem,
                        'type': 'Python'
                    })
            
            # Pine Script 파일 스캔
            for file_path in self.day_trade_dir.glob("*.pine"):
                algorithms.append({
                    'filename': file_path.name,
                    'filepath': file_path,
                    'name': file_path.stem,
                    'type': 'Pine Script'
                })
            
            if not algorithms:
                print("단타매매 알고리즘을 찾을 수 없습니다.")
                print("day_trade_Algorithm 폴더에 Python 또는 Pine Script 알고리즘 파일을 추가하세요.")
                return
            
            # 알고리즘 목록 표시
            print("사용 가능한 단타매매 알고리즘:")
            for i, algo in enumerate(algorithms, 1):
                print(f"{i}. {algo['name']} ({algo['type']})")
            
            print("0. 취소")
            print("-" * 50)
            
            # 사용자 선택
            try:
                choice = input("선택하세요: ").strip()
                
                if choice == '0' or choice == '':
                    print("단타매매 알고리즘 선택이 취소되었습니다.")
                    return
                
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(algorithms):
                    selected_algo = algorithms[choice_idx]
                    
                    # 알고리즘 로드 (타입에 따라 다르게 처리)
                    algorithm = self._load_day_trade_algorithm(selected_algo['filepath'], selected_algo['type'])
                    if algorithm:
                        # 전역 변수에 저장
                        self.selected_algorithm['filename'] = selected_algo['filename']
                        self.selected_algorithm['algorithm_instance'] = algorithm
                        # 파일명에서 확장자 제거한 이름 사용
                        algorithm_file_name = Path(selected_algo['filename']).stem
                        self.selected_algorithm['info'] = {
                            'name': algorithm_file_name,
                            'filename': selected_algo['filename'],
                            'description': algorithm.get_description(),
                            'version': algorithm.get_version()
                        }
                        
                        print(f"\nOK 단타매매 알고리즘 선택 완료!")
                        print(f"이름: {algorithm_file_name}")
                        print(f"버전: {algorithm.get_version()}")
                        print(f"설명: {algorithm.get_description()}")
                        print(f"파일: {selected_algo['filename']}")
                        
                        # 알고리즘 상태 저장
                        self.save_algorithm_state()
                        
                        print("\n이제 단타매매(메뉴 2)를 시작할 수 있습니다.")
                        print("선택된 알고리즘은 다른 알고리즘을 선택할 때까지 계속 사용됩니다.")
                    else:
                        print("ERR 알고리즘 로드에 실패했습니다.")
                else:
                    print("잘못된 선택입니다.")
                    
            except ValueError:
                print("올바른 숫자를 입력하세요.")
            except Exception as e:
                print(f"선택 처리 중 오류: {e}")
            
        except Exception as e:
            print(f"ERR 단타매매 알고리즘 선택 중 오류가 발생했습니다: {e}")
    
    def _load_day_trade_algorithm(self, file_path, algorithm_type='Python'):
        """단타매매 알고리즘 파일 로드 (Python/Pine Script 지원)"""
        try:
            # 시스템 경로에 프로젝트 루트 추가
            import sys
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))
            
            # Pine Script 파일 처리
            if algorithm_type == 'Pine Script':
                return self._handle_pine_script_algorithm(file_path)
            
            # Python 파일 처리
            # 모듈 로드
            spec = importlib.util.spec_from_file_location("day_trade_algorithm", file_path)
            if spec is None or spec.loader is None:
                print(f"모듈 스펙 생성 실패: {file_path}")
                return None
                
            module = importlib.util.module_from_spec(spec)
            
            # 모듈에 sys.path 설정
            sys.modules[spec.name] = module
            
            # 모듈 실행
            spec.loader.exec_module(module)
            
            # BaseAlgorithm을 상속받은 클래스 찾기
            from support.algorithm_interface import BaseAlgorithm
            
            algorithm_classes = []
            for name in dir(module):
                obj = getattr(module, name)
                if (isinstance(obj, type) and 
                    issubclass(obj, BaseAlgorithm) and 
                    obj != BaseAlgorithm):
                    algorithm_classes.append((name, obj))
            
            if algorithm_classes:
                # 첫 번째 알고리즘 클래스 사용
                class_name, algorithm_class = algorithm_classes[0]
                print(f"알고리즘 클래스 발견: {class_name}")
                
                # 클래스 인스턴스 생성
                algorithm_instance = algorithm_class()
                return algorithm_instance
            else:
                print("BaseAlgorithm을 상속받은 클래스를 찾을 수 없습니다.")
                print(f"모듈 내용: {dir(module)}")
                return None
            
        except ImportError as e:
            print(f"임포트 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
        except Exception as e:
            print(f"알고리즘 로드 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _handle_pine_script_algorithm(self, file_path):
        """Pine Script 파일 처리 - Python 포팅 버전 우선 로드"""
        try:
            # Pine Script 파일명에서 확장자 제거
            pine_file = Path(file_path)
            python_file = pine_file.parent / f"{pine_file.stem}.py"
            
            # 동일한 이름의 Python 파일이 있는지 확인
            if python_file.exists():
                print(f"Pine Script '{pine_file.name}'의 Python 포팅 버전 발견: {python_file.name}")
                print("실제 실행 가능한 Python 버전을 로드합니다...")
                
                # Python 버전 로드
                return self._load_python_algorithm(python_file)
            else:
                print(f"주의: Pine Script '{pine_file.name}'는 TradingView 전용입니다.")
                print("tideWise에서는 매매 신호가 생성되지 않습니다.")
                print(f"실행 가능한 버전을 원하시면 {pine_file.stem}.py 파일을 개발하세요.")
                
                # 기존 Pine Script 래퍼 반환 (경고와 함께)
                return self._create_pine_script_wrapper(file_path)
                
        except Exception as e:
            print(f"Pine Script 처리 오류: {e}")
            return self._create_pine_script_wrapper(file_path)
    
    def _load_python_algorithm(self, file_path):
        """Python 알고리즘 파일 로드 (Pine Script 포팅 버전 포함)"""
        try:
            import sys
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))
            
            # 모듈 로드
            spec = importlib.util.spec_from_file_location("python_algorithm", file_path)
            if spec is None or spec.loader is None:
                print(f"모듈 스펙 생성 실패: {file_path}")
                return None
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            # BaseAlgorithm을 상속받은 클래스 찾기
            from support.algorithm_interface import BaseAlgorithm
            
            algorithm_classes = []
            for name in dir(module):
                obj = getattr(module, name)
                if (isinstance(obj, type) and 
                    issubclass(obj, BaseAlgorithm) and 
                    obj != BaseAlgorithm):
                    algorithm_classes.append((name, obj))
            
            if algorithm_classes:
                # 첫 번째 알고리즘 클래스 사용
                class_name, algorithm_class = algorithm_classes[0]
                print(f"Python 알고리즘 클래스 발견: {class_name}")
                
                # 클래스 인스턴스 생성
                algorithm_instance = algorithm_class()
                return algorithm_instance
            else:
                print("BaseAlgorithm을 상속받은 클래스를 찾을 수 없습니다.")
                return None
                
        except Exception as e:
            print(f"Python 알고리즘 로드 오류: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _create_pine_script_wrapper(self, file_path):
        """Pine Script 파일을 위한 래퍼 클래스 생성"""
        try:
            from support.algorithm_interface import BaseAlgorithm
            
            class PineScriptWrapper(BaseAlgorithm):
                """Pine Script 파일을 위한 래퍼 클래스"""
                
                def __init__(self, pine_script_path):
                    super().__init__()
                    self.pine_script_path = Path(pine_script_path)
                    self.name = self.pine_script_path.stem
                    self.description = self._extract_pine_description()
                    self.version = self._extract_pine_version()
                
                def _extract_pine_description(self):
                    """Pine Script 파일에서 설명 추출"""
                    try:
                        with open(self.pine_script_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        # strategy() 또는 indicator() 에서 title 추출
                        import re
                        if 'strategy(' in content:
                            match = re.search(r'strategy\s*\(\s*["\']([^"\']+)["\']', content)
                            if match:
                                return match.group(1)
                        elif 'indicator(' in content:
                            match = re.search(r'indicator\s*\(\s*["\']([^"\']+)["\']', content)
                            if match:
                                return match.group(1)
                        
                        return f"Pine Script 알고리즘 - {self.name}"
                    except:
                        return f"Pine Script 알고리즘 - {self.name}"
                
                def _extract_pine_version(self):
                    """Pine Script 파일에서 버전 추출"""
                    try:
                        with open(self.pine_script_path, 'r', encoding='utf-8') as f:
                            first_line = f.readline()
                            
                        # //@version=5 형태에서 버전 추출
                        import re
                        match = re.search(r'//@version=(\d+)', first_line)
                        if match:
                            return f"Pine Script v{match.group(1)}"
                        
                        return "Pine Script v5"
                    except:
                        return "Pine Script v5"
                
                def get_name(self):
                    return self.name
                
                def get_description(self):
                    return self.description
                
                def get_version(self):
                    return self.version
                
                def should_buy(self, stock_data, market_data=None):
                    """Pine Script는 TradingView에서 실행되므로 여기서는 항상 False 반환"""
                    return False
                
                def should_sell(self, stock_data, current_position, market_data=None):
                    """Pine Script는 TradingView에서 실행되므로 여기서는 항상 False 반환"""
                    return False
                
                def analyze(self, stock_data):
                    # Pine Script는 TradingView에서 실행되므로 항상 HOLD 반환
                    return 'HOLD'
                
                def calculate_position_size(self, account_info, stock_price):
                    """기본 포지션 크기 계산"""
                    return 1000000  # 기본 100만원
                
                def get_file_path(self):
                    """Pine Script 파일 경로 반환"""
                    return str(self.pine_script_path)
            
            # Pine Script 래퍼 인스턴스 생성
            wrapper = PineScriptWrapper(file_path)
            print(f"Pine Script 래퍼 생성: {wrapper.get_name()}")
            return wrapper
            
        except Exception as e:
            print(f"Pine Script 래퍼 생성 실패: {e}")
            return None
    
    def get_selected_algorithm(self) -> Dict[str, Any]:
        """현재 선택된 알고리즘 정보 반환"""
        return self.selected_algorithm.copy()
    
    def get_selected_algorithm_instance(self):
        """현재 선택된 알고리즘 인스턴스 반환"""
        return self.selected_algorithm.get('algorithm_instance')
    
    def has_selected_algorithm(self) -> bool:
        """알고리즘이 선택되었는지 확인"""
        return (self.selected_algorithm.get('algorithm_instance') is not None and
                self.selected_algorithm.get('filename') is not None)
    
    def ensure_algorithm_available(self) -> bool:
        """엄격한 알고리즘 검증 - 실제 파일 기반 알고리즘만 허용 (통합 폴더 지원)"""
        try:
            # 이미 유효한 알고리즘이 로드되어 있는지 확인
            if self.has_selected_algorithm():
                # 선택된 알고리즘 파일이 실제로 존재하는지 검증
                filename = self.selected_algorithm.get('filename')
                if filename and self._verify_algorithm_file_exists(filename):
                    return True
                else:
                    print(f"\n[경고] 선택된 알고리즘 파일을 찾을 수 없습니다: {filename}")
                    # 알고리즘 상태 초기화
                    self.selected_algorithm = {
                        'filename': None,
                        'algorithm_instance': None,
                        'info': {
                            'name': '선택된 알고리즘 없음',
                            'description': '메뉴 3번에서 알고리즘을 선택하세요',
                            'version': '1.0'
                        }
                    }
            
            # 사용 가능한 알고리즘 폴더들 확인
            algorithm_dir = self.project_root / "Algorithm"
            day_trade_dir = self.project_root / "day_trade_Algorithm"
            
            # 모든 사용 가능한 알고리즘 파일 수집
            available_algorithms = []
            
            # Algorithm 폴더 확인
            if algorithm_dir.exists():
                for file in algorithm_dir.glob("*.py"):
                    available_algorithms.append({
                        'file': file.name,
                        'path': file,
                        'type': '자동매매 알고리즘'
                    })
            
            # day_trade_Algorithm 폴더 확인  
            if day_trade_dir.exists():
                for file in day_trade_dir.glob("*.py"):
                    available_algorithms.append({
                        'file': file.name,
                        'path': file,
                        'type': '단타매매 알고리즘'
                    })
                for file in day_trade_dir.glob("*.pine"):
                    available_algorithms.append({
                        'file': file.name,
                        'path': file,
                        'type': '단타매매 알고리즘 (Pine Script)'
                    })
            
            if not available_algorithms:
                print("\n[오류] 사용 가능한 알고리즘 파일이 없습니다.")
                print("다음 폴더에 알고리즘 파일을 추가하세요:")
                print("  - Algorithm/ (자동매매용 .py 파일)")
                print("  - day_trade_Algorithm/ (단타매매용 .py, .pine 파일)")
                return False
            
            print("\n[오류] 선택된 알고리즘이 없습니다.")
            print(f"사용 가능한 알고리즘:")
            for algo in available_algorithms:
                print(f"  - {algo['file']} ({algo['type']})")
            
            print("\n매매를 시작하려면:")
            print("1. 메뉴 3번에서 자동매매 알고리즘을 선택하거나")
            print("2. 메뉴 4번에서 단타매매 알고리즘을 선택하세요")
            print("3. 알고리즘 선택 후 해당 매매를 시작할 수 있습니다")
            print("\n매매는 알고리즘이 선택되어야만 실행됩니다.")
            return False
            
        except Exception as e:
            print(f"\n[오류] 알고리즘 검증 실패: {e}")
            return False
    
    def _verify_algorithm_file_exists(self, filename: str) -> bool:
        """선택된 알고리즘 파일이 실제로 존재하는지 확인"""
        try:
            # Algorithm 폴더에서 확인
            algorithm_path = self.project_root / "Algorithm" / filename
            if algorithm_path.exists():
                return True
            
            # day_trade_Algorithm 폴더에서 확인
            day_trade_path = self.project_root / "day_trade_Algorithm" / filename
            if day_trade_path.exists():
                return True
            
            return False
        except Exception:
            return False
    
    
    def _is_debug_mode(self) -> bool:
        """디버그 모드 여부 확인"""
        import os
        return os.environ.get('K_AUTOTRADE_DEBUG', '').lower() in ('true', '1', 'yes', 'on')


def get_algorithm_selector(project_root: Path) -> AlgorithmSelector:
    """AlgorithmSelector 인스턴스를 생성하여 반환"""
    return AlgorithmSelector(project_root)