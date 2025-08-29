#!/usr/bin/env python3
"""
범용 알고리즘 인터페이스
모든 형식의 알고리즘 파일을 통합 처리하는 인터페이스
"""

import os
import sys
import json
import logging
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class UniversalAlgorithmInterface:
    """범용 알고리즘 인터페이스 - 모든 형식의 알고리즘 파일을 처리"""
    
    def __init__(self, algorithm_file_path: str):
        self.algorithm_file_path = Path(algorithm_file_path)
        self.algorithm_type = self._detect_algorithm_type()
        self.algorithm_instance = None
        self.algorithm_metadata = {}
        self._load_algorithm()
    
    def _detect_algorithm_type(self) -> str:
        """알고리즘 파일 타입 감지"""
        if not self.algorithm_file_path.exists():
            raise FileNotFoundError(f"알고리즘 파일을 찾을 수 없습니다: {self.algorithm_file_path}")
        
        suffix = self.algorithm_file_path.suffix.lower()
        type_mapping = {
            '.py': 'python',
            '.pine': 'pinescript', 
            '.js': 'javascript',
            '.txt': 'text',
            '.json': 'json'
        }
        
        return type_mapping.get(suffix, 'unknown')
    
    def _load_algorithm(self):
        """알고리즘 로드"""
        try:
            if self.algorithm_type == 'python':
                self._load_python_algorithm()
            elif self.algorithm_type == 'pinescript':
                self._load_pinescript_algorithm()
            elif self.algorithm_type == 'javascript':
                self._load_javascript_algorithm()
            elif self.algorithm_type == 'text':
                self._load_text_algorithm()
            elif self.algorithm_type == 'json':
                self._load_json_algorithm()
            else:
                raise ValueError(f"지원하지 않는 알고리즘 타입: {self.algorithm_type}")
                
        except Exception as e:
            logger.error(f"알고리즘 로드 실패: {e}")
            raise e
    
    def _load_python_algorithm(self):
        """Python 알고리즘 로드"""
        try:
            # 먼저 구문 오류 검사
            with open(self.algorithm_file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            try:
                compile(source_code, self.algorithm_file_path, 'exec')
            except SyntaxError as syntax_err:
                raise SyntaxError(f"구문 오류: {syntax_err.msg} (라인 {syntax_err.lineno})")
            
            spec = importlib.util.spec_from_file_location("user_algorithm", self.algorithm_file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 알고리즘 클래스 찾기
            algorithm_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    hasattr(attr, 'analyze') and 
                    attr_name != 'BaseAlgorithm'):
                    algorithm_class = attr
                    break
            
            if algorithm_class:
                self.algorithm_instance = algorithm_class()
                self.algorithm_metadata = {
                    'name': getattr(self.algorithm_instance, 'name', self.algorithm_file_path.stem),
                    'version': getattr(self.algorithm_instance, 'version', '1.0'),
                    'description': getattr(self.algorithm_instance, 'description', 'Python 기반 알고리즘'),
                    'type': 'python'
                }
                # Python 알고리즘 로드 성공 - 로그 간소화
            else:
                raise ValueError("Python 파일에서 유효한 알고리즘 클래스를 찾을 수 없습니다")
                
        except Exception as e:
            logger.error(f"Python 알고리즘 로드 실패: {e}")
            print(f"알고리즘 파일 오류: {e}")
            raise e
    
    def _load_pinescript_algorithm(self):
        """Pine Script 알고리즘 로드"""
        try:
            with open(self.algorithm_file_path, 'r', encoding='utf-8') as f:
                pine_content = f.read()
            
            # Pine Script 메타데이터 추출
            name = self._extract_pinescript_name(pine_content)
            description = self._extract_pinescript_description(pine_content)
            
            self.algorithm_instance = PineScriptWrapper(pine_content, name, description)
            self.algorithm_metadata = {
                'name': name,
                'version': '1.0',
                'description': description,
                'type': 'pinescript'
            }
            
        except Exception as e:
            logger.error(f"Pine Script 알고리즘 로드 실패: {e}")
            raise e
    
    def _load_javascript_algorithm(self):
        """JavaScript 알고리즘 로드"""
        try:
            with open(self.algorithm_file_path, 'r', encoding='utf-8') as f:
                js_content = f.read()
            
            name = self.algorithm_file_path.stem
            description = "JavaScript 기반 알고리즘"
            
            self.algorithm_instance = JavaScriptWrapper(js_content, name, description)
            self.algorithm_metadata = {
                'name': name,
                'version': '1.0', 
                'description': description,
                'type': 'javascript'
            }
            
        except Exception as e:
            logger.error(f"JavaScript 알고리즘 로드 실패: {e}")
            self._create_fallback_algorithm()
    
    def _load_text_algorithm(self):
        """텍스트 알고리즘 로드"""
        try:
            with open(self.algorithm_file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            name = self.algorithm_file_path.stem
            description = self._extract_text_description(text_content)
            
            self.algorithm_instance = TextWrapper(text_content, name, description)
            self.algorithm_metadata = {
                'name': name,
                'version': '1.0',
                'description': description,
                'type': 'text'
            }
            
        except Exception as e:
            logger.error(f"텍스트 알고리즘 로드 실패: {e}")
            self._create_fallback_algorithm()
    
    def _load_json_algorithm(self):
        """JSON 알고리즘 로드"""
        try:
            with open(self.algorithm_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            name = json_data.get('name', self.algorithm_file_path.stem)
            description = json_data.get('description', 'JSON 기반 알고리즘')
            
            self.algorithm_instance = JsonWrapper(json_data, name, description)
            self.algorithm_metadata = {
                'name': name,
                'version': json_data.get('version', '1.0'),
                'description': description,
                'type': 'json'
            }
            
        except Exception as e:
            logger.error(f"JSON 알고리즘 로드 실패: {e}")
            self._create_fallback_algorithm()
    
    def _create_fallback_algorithm(self):
        """기본 대체 알고리즘 생성"""
        logger.warning("기본 대체 알고리즘을 사용합니다")
        self.algorithm_instance = FallbackAlgorithm()
        self.algorithm_metadata = {
            'name': 'Fallback Algorithm',
            'version': '1.0',
            'description': '기본 HOLD 전략',
            'type': 'fallback'
        }
    
    def _extract_pinescript_name(self, content: str) -> str:
        """Pine Script에서 이름 추출"""
        lines = content.split('\n')
        for line in lines:
            if 'indicator(' in line or 'strategy(' in line:
                if '"' in line:
                    start = line.find('"') + 1
                    end = line.find('"', start)
                    if end > start:
                        return line[start:end]
        return self.algorithm_file_path.stem
    
    def _extract_pinescript_description(self, content: str) -> str:
        """Pine Script에서 설명 추출"""
        lines = content.split('\n')
        for line in lines:
            if line.strip().startswith('//') and ('설명' in line or '전략' in line):
                return line.strip()[2:].strip()
        return "Pine Script 기반 알고리즘"
    
    def _extract_text_description(self, content: str) -> str:
        """텍스트에서 설명 추출"""
        lines = content.split('\n')
        for line in lines[:5]:  # 처음 5줄에서 설명 찾기
            if line.strip() and not line.startswith('#'):
                return line.strip()
        return "텍스트 기반 알고리즘"
    
    # 공용 인터페이스 메소드들
    def get_name(self) -> str:
        return self.algorithm_metadata.get('name', 'Unknown Algorithm')
    
    def get_version(self) -> str:
        return self.algorithm_metadata.get('version', '1.0')
    
    def get_description(self) -> str:
        return self.algorithm_metadata.get('description', 'Algorithm')
    
    def analyze(self, stock_data: Dict[str, Any]) -> str:
        """매매 신호 분석"""
        if self.algorithm_instance and hasattr(self.algorithm_instance, 'analyze'):
            return self.algorithm_instance.analyze(stock_data)
        return 'HOLD'
    
    def calculate_position_size(self, price: float, cash: float) -> int:
        """포지션 크기 계산"""
        if self.algorithm_instance and hasattr(self.algorithm_instance, 'calculate_position_size'):
            return self.algorithm_instance.calculate_position_size(price, cash)
        return max(1, int(cash * 0.05 / price))  # 기본값: 5%
    
    async def execute_trading(self, api):
        """자동매매 실행 - pure_trader.py 호환성을 위한 래퍼 메서드"""
        try:
            logger.info(f"{self.get_name()} 알고리즘 실행 시작")
            
            # 계좌 정보 조회
            balance = api.get_account_balance()
            if not balance:
                logger.error("계좌 정보 조회 실패")
                return "FAIL: 계좌 정보 조회 실패"
            
            cash = float(balance.get('dnca_tot_amt', '0'))
            if cash <= 0:
                logger.warning("예수금 부족")
                return "HOLD: 예수금 부족"
            
            # 보유종목 조회
            positions = api.get_account_positions()
            
            # 알고리즘 실행을 위한 기본 데이터 준비
            stock_data = {
                'current_price': 0,
                'change_rate': 0,
                'volume_ratio': 1.0,
                'cash': cash,
                'positions': positions
            }
            
            # 알고리즘 분석 실행
            signal = self.analyze(stock_data)
            
            logger.info(f"{self.get_name()} 알고리즘 분석 결과: {signal}")
            return signal
            
        except Exception as e:
            logger.error(f"알고리즘 실행 오류: {e}")
            return f"ERROR: {str(e)}"

class FallbackAlgorithm:
    """기본 대체 알고리즘"""
    
    def __init__(self):
        self.name = "Fallback Algorithm"
        self.version = "1.0"
        self.description = "기본 HOLD 전략"
    
    def analyze(self, stock_data: Dict[str, Any]) -> str:
        return 'HOLD'
    
    def calculate_position_size(self, price: float, cash: float) -> int:
        return max(1, int(cash * 0.05 / price))

class PineScriptWrapper:
    """Pine Script 래퍼"""
    
    def __init__(self, pine_content: str, name: str, description: str):
        self.pine_content = pine_content
        self.name = name
        self.description = description
        self.version = "1.0"
        self.price_history = []
        self.settings = self._extract_pine_settings()
    
    def _extract_pine_settings(self) -> Dict[str, Any]:
        """Pine Script에서 설정 추출"""
        settings = {
            'period': 14,
            'multiplier': 2.0,
            'threshold': 0.02
        }
        
        # Pine Script 내용에서 input 값들 추출
        lines = self.pine_content.split('\n')
        for line in lines:
            if 'input' in line:
                if 'period' in line.lower():
                    try:
                        import re
                        match = re.search(r'(\d+)', line)
                        if match:
                            settings['period'] = int(match.group(1))
                    except:
                        pass
                elif 'multiplier' in line.lower():
                    try:
                        import re
                        match = re.search(r'(\d+\.?\d*)', line)
                        if match:
                            settings['multiplier'] = float(match.group(1))
                    except:
                        pass
        
        return settings
    
    def analyze(self, stock_data: Dict[str, Any]) -> str:
        """간단한 Pine Script 로직 구현"""
        try:
            current_price = stock_data.get('current_price', 0)
            if current_price <= 0:
                return 'HOLD'
            
            self.price_history.append(current_price)
            if len(self.price_history) > 100:
                self.price_history = self.price_history[-100:]
            
            if len(self.price_history) < self.settings['period']:
                return 'HOLD'
            
            # 간단한 이동평균 기반 신호
            recent_prices = self.price_history[-self.settings['period']:]
            avg_price = sum(recent_prices) / len(recent_prices)
            
            change_rate = (current_price - avg_price) / avg_price
            
            if change_rate > self.settings['threshold']:
                return 'BUY'
            elif change_rate < -self.settings['threshold']:
                return 'SELL'
            else:
                return 'HOLD'
                
        except Exception as e:
            logger.error(f"Pine Script 분석 오류: {e}")
            return 'HOLD'
    
    def calculate_position_size(self, price: float, cash: float) -> int:
        return max(1, int(cash * 0.10 / price))

class JavaScriptWrapper:
    """JavaScript 래퍼"""
    
    def __init__(self, js_content: str, name: str, description: str):
        self.js_content = js_content
        self.name = name
        self.description = description
        self.version = "1.0"
    
    def analyze(self, stock_data: Dict[str, Any]) -> str:
        """JavaScript 로직을 Python으로 변환 (간단한 구현)"""
        # 실제로는 JavaScript 엔진이 필요하지만, 여기서는 간단한 로직으로 대체
        current_price = stock_data.get('current_price', 0)
        change_rate = stock_data.get('change_rate', 0)
        
        if change_rate > 0.03:
            return 'BUY'
        elif change_rate < -0.02:
            return 'SELL'
        else:
            return 'HOLD'
    
    def calculate_position_size(self, price: float, cash: float) -> int:
        return max(1, int(cash * 0.08 / price))

class TextWrapper:
    """텍스트 래퍼"""
    
    def __init__(self, text_content: str, name: str, description: str):
        self.text_content = text_content
        self.name = name
        self.description = description
        self.version = "1.0"
        self.rules = self._parse_text_rules()
    
    def _parse_text_rules(self) -> Dict[str, float]:
        """텍스트에서 매매 규칙 추출"""
        rules = {
            'buy_threshold': 0.03,
            'sell_threshold': -0.02,
            'volume_multiplier': 1.5
        }
        
        lines = self.text_content.split('\n')
        for line in lines:
            line_lower = line.lower()
            if 'buy' in line_lower or '매수' in line:
                # 숫자 패턴 찾기
                import re
                numbers = re.findall(r'(\d+\.?\d*)%?', line)
                if numbers:
                    rules['buy_threshold'] = float(numbers[0]) / 100
            elif 'sell' in line_lower or '매도' in line:
                numbers = re.findall(r'(\d+\.?\d*)%?', line)
                if numbers:
                    rules['sell_threshold'] = -abs(float(numbers[0]) / 100)
        
        return rules
    
    def analyze(self, stock_data: Dict[str, Any]) -> str:
        """텍스트 규칙 기반 분석"""
        change_rate = stock_data.get('change_rate', 0)
        volume_ratio = stock_data.get('volume_ratio', 1.0)
        
        # 거래량 조건 확인
        if volume_ratio < self.rules['volume_multiplier']:
            return 'HOLD'
        
        if change_rate >= self.rules['buy_threshold']:
            return 'BUY'
        elif change_rate <= self.rules['sell_threshold']:
            return 'SELL'
        else:
            return 'HOLD'
    
    def calculate_position_size(self, price: float, cash: float) -> int:
        return max(1, int(cash * 0.15 / price))

class JsonWrapper:
    """JSON 래퍼"""
    
    def __init__(self, json_data: Dict[str, Any], name: str, description: str):
        self.json_data = json_data
        self.name = name
        self.description = description
        self.version = json_data.get('version', '1.0')
        self.parameters = json_data.get('parameters', {})
    
    def analyze(self, stock_data: Dict[str, Any]) -> str:
        """JSON 설정 기반 분석"""
        current_price = stock_data.get('current_price', 0)
        change_rate = stock_data.get('change_rate', 0)
        
        buy_threshold = self.parameters.get('buy_threshold', 0.02)
        sell_threshold = self.parameters.get('sell_threshold', -0.02)
        
        if change_rate >= buy_threshold:
            return 'BUY'
        elif change_rate <= sell_threshold:
            return 'SELL'
        else:
            return 'HOLD'
    
    def calculate_position_size(self, price: float, cash: float) -> int:
        max_position = self.parameters.get('max_position_size', 0.10)
        return max(1, int(cash * max_position / price))