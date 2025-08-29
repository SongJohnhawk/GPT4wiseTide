#!/usr/bin/env python3
"""
알고리즘 로더 - Python 및 Pine Script 알고리즘을 로드하고 관리
지원 형식: .py, .pine
"""

import os
import sys
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any

# 깔끔한 콘솔 로거 사용
from support.clean_console_logger import (
    get_clean_logger, Phase, log as clean_log
)

class AlgorithmLoader:
    """Python 및 Pine Script 알고리즘 파일을 로드하는 클래스"""
    
    def __init__(self, algorithm_dir: str = "Algorithm"):
        self.algorithm_dir = Path(algorithm_dir)
        self.supported_extensions = ['.py', '.pine']
        self.algorithms = {}
        self.scan_algorithms()
    
    def scan_algorithms(self):
        """Algorithm 폴더의 모든 알고리즘 파일 스캔"""
        self.algorithms = {}
        
        if not self.algorithm_dir.exists():
            clean_log(f"알고리즘 폴더가 존재하지 않습니다: {self.algorithm_dir}", "WARNING")
            return
        
        for file_path in self.algorithm_dir.glob("*"):
            if file_path.is_file() and file_path.suffix in self.supported_extensions:
                algorithm_info = self._analyze_algorithm_file(file_path)
                if algorithm_info:
                    self.algorithms[file_path.name] = algorithm_info
        
        if self._is_debug_mode():
            print(f"총 {len(self.algorithms)}개의 알고리즘 파일을 발견했습니다")
    
    def _analyze_algorithm_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """알고리즘 파일 분석"""
        try:
            file_extension = file_path.suffix.lower()
            
            algorithm_info = {
                'file_path': file_path,
                'file_name': file_path.name,
                'file_type': file_extension,
                'name': file_path.stem,
                'description': '',
                'version': '1.0',
                'size': file_path.stat().st_size,
                'modified': file_path.stat().st_mtime
            }
            
            # 파일 내용에서 메타데이터 추출
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                algorithm_info['description'] = self._extract_description(content, file_extension)
                algorithm_info['version'] = self._extract_version(content, file_extension)
            
            return algorithm_info
            
        except Exception as e:
            clean_log(f"알고리즘 파일 분석 실패 {file_path}: {e}", "ERROR")
            return None
    
    def _extract_description(self, content: str, file_type: str) -> str:
        """파일 내용에서 설명 추출"""
        if file_type == '.py':
            # Python docstring 찾기
            if '"""' in content:
                start = content.find('"""') + 3
                end = content.find('"""', start)
                if end > start:
                    return content[start:end].strip().split('\n')[0]
        
        elif file_type == '.pine':
            # Pine Script indicator 이름 찾기
            if 'indicator(' in content:
                start = content.find('indicator(') + 10
                end = content.find(')', start)
                if end > start:
                    indicator_line = content[start:end]
                    if '"' in indicator_line:
                        return indicator_line.split('"')[1]
        
        return f"{file_type[1:].upper()} 알고리즘"
    
    def _extract_version(self, content: str, file_type: str) -> str:
        """파일 내용에서 버전 추출"""
        # 간단한 버전 추출 로직
        if 'version' in content.lower():
            lines = content.split('\n')
            for line in lines:
                if 'version' in line.lower() and ('=' in line or ':' in line):
                    # 간단한 버전 패턴 매칭
                    import re
                    version_match = re.search(r'[\d]+\.[\d]+(?:\.[\d]+)?', line)
                    if version_match:
                        return version_match.group(0)
        
        return "1.0"
    
    def _is_debug_mode(self) -> bool:
        """디버그 모드 확인"""
        import os
        return os.environ.get('K_AUTOTRADE_DEBUG', '').lower() in ['true', '1', 'yes']
    
    def get_algorithm_list(self) -> List[Dict[str, Any]]:
        """알고리즘 목록 반환"""
        return list(self.algorithms.values())
    
    def show_algorithm_menu(self) -> Optional[str]:
        """알고리즘 선택 메뉴 표시"""
        if not self.algorithms:
            print("사용 가능한 알고리즘이 없습니다.")
            return None
        
        print("\n[ 사용 가능한 알고리즘 목록 ]")
        print("-" * 70)
        
        algorithm_list = list(self.algorithms.items())
        for i, (filename, info) in enumerate(algorithm_list, 1):
            file_type = info['file_type'].upper()
            size_kb = info['size'] / 1024
            print(f"{i:2d}. {info['name']:<25} ({file_type:<5}) - {info['description']}")
            print(f"    파일: {filename} ({size_kb:.1f}KB)")
        
        print("-" * 70)
        print("0. 기본 알고리즘 사용")
        
        try:
            choice = input("\n알고리즘 선택 (번호 입력): ").strip()
            
            if choice == '0':
                return 'default'
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(algorithm_list):
                selected_filename = algorithm_list[choice_num - 1][0]
                selected_info = self.algorithms[selected_filename]
                print(f"\n선택된 알고리즘: {selected_info['name']} ({selected_info['file_type']})")
                return selected_filename
            else:
                print("잘못된 선택입니다.")
                return None
                
        except (ValueError, KeyboardInterrupt):
            print("선택이 취소되었습니다.")
            return None
    
    def load_algorithm(self, filename: Optional[str] = None):
        """선택된 알고리즘 로드 - 대체 로직 없음"""
        if filename is None:
            clean_log("알고리즘이 설정되지 않았습니다", "ERROR")
            return None
        
        if filename not in self.algorithms:
            clean_log(f"알고리즘 파일을 찾을 수 없습니다: {filename}", "ERROR")
            return None
        
        algorithm_info = self.algorithms[filename]
        file_path = algorithm_info['file_path']
        
        try:
            from support.universal_algorithm_interface import UniversalAlgorithmInterface
            return UniversalAlgorithmInterface(str(file_path))
                
        except Exception as e:
            clean_log(f"알고리즘 로드 실패 {filename}: {e}", "ERROR")
            return None

# 전역 인스턴스
_algorithm_loader = None

def get_algorithm_loader() -> AlgorithmLoader:
    """알고리즘 로더 싱글톤 인스턴스 반환"""
    global _algorithm_loader
    if _algorithm_loader is None:
        _algorithm_loader = AlgorithmLoader()
    return _algorithm_loader