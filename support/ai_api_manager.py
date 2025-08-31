#!/usr/bin/env python3
"""
AI API 관리자 - Register_Key.md 전용
GPT4wiseTide 프로젝트의 모든 AI API 키는 오직 Register_Key.md에서만 관리

**핵심 원칙:**
- Register_Key.md 파일만이 유일한 신뢰 소스
- 하드코딩된 API 키 절대 금지
- 환경변수나 별도 설정파일 사용 금지
- AuthoritativeRegisterKeyLoader를 통해서만 접근
"""

import re
import logging
from typing import Dict, Optional, Any
from pathlib import Path

from .authoritative_register_key_loader import AuthoritativeRegisterKeyLoader

logger = logging.getLogger(__name__)

class AIAPIManager:
    """AI API 키 및 설정 관리자 - Register_Key.md 전용"""
    
    def __init__(self, project_root: Path = None):
        """
        초기화
        
        Args:
            project_root: 프로젝트 루트 경로 (None이면 자동 탐지)
        """
        self.key_loader = AuthoritativeRegisterKeyLoader(project_root)
        self._ai_config_cache: Optional[Dict[str, Any]] = None
        
        logger.info("AI API Manager 초기화 - Register_Key.md 전용")
    
    def _load_ai_config(self) -> Dict[str, Any]:
        """Register_Key.md에서 AI 설정 로드"""
        try:
            # 전체 설정 로드
            all_config = self.key_loader.load_all_configuration()
            
            # AI 엔진 설정 추출
            ai_config = {}
            
            # OpenAI GPT 설정
            ai_config['openai'] = {
                'api_key': all_config.get('gpt_api_key', ''),
                'model': all_config.get('gpt_model', 'gpt-4o'),
                'max_tokens': int(all_config.get('gpt_max_tokens', '4000')),
                'temperature': float(all_config.get('gpt_temperature', '0.1'))
            }
            
            # Claude 설정
            ai_config['claude'] = {
                'api_key': all_config.get('claude_api_key', ''),
                'model': all_config.get('claude_model', 'claude-3.5-sonnet'),
                'max_tokens': int(all_config.get('claude_max_tokens', '4000')),
                'temperature': float(all_config.get('claude_temperature', '0.1'))
            }
            
            # Gemini 설정
            ai_config['gemini'] = {
                'api_key': all_config.get('gemini_api_key', ''),
                'model': all_config.get('gemini_model', 'gemini-1.5-pro'),
                'max_tokens': int(all_config.get('gemini_max_tokens', '4000')),
                'temperature': float(all_config.get('gemini_temperature', '0.1'))
            }
            
            # 하이브리드 설정
            ai_config['hybrid'] = {
                'enabled': all_config.get('hybrid_mode_enabled', 'false').lower() == 'true',
                'claude_weight': float(all_config.get('claude_weight', '0.6')),
                'gemini_weight': float(all_config.get('gemini_weight', '0.4')),
                'timeout_seconds': int(all_config.get('api_timeout', '10')),
                'max_retries': int(all_config.get('max_retries', '3'))
            }
            
            self._ai_config_cache = ai_config
            return ai_config
            
        except Exception as e:
            logger.error(f"AI 설정 로드 실패: {e}")
            raise RuntimeError(f"Register_Key.md에서 AI 설정을 읽을 수 없습니다: {e}")
    
    def get_openai_config(self) -> Dict[str, Any]:
        """OpenAI API 설정 반환"""
        if not self._ai_config_cache:
            self._load_ai_config()
        
        config = self._ai_config_cache['openai']
        if not config['api_key']:
            raise ValueError(
                "OpenAI API 키가 설정되지 않았습니다.\n"
                "메뉴 3. Setup → 1. Register_Key에서 GPT API Key를 설정하세요."
            )
        return config
    
    def get_claude_config(self) -> Dict[str, Any]:
        """Claude API 설정 반환"""
        if not self._ai_config_cache:
            self._load_ai_config()
        
        config = self._ai_config_cache['claude']
        if not config['api_key']:
            raise ValueError(
                "Claude API 키가 설정되지 않았습니다.\n"
                "메뉴 3. Setup → 1. Register_Key에서 Claude API Key를 설정하세요."
            )
        return config
    
    def get_gemini_config(self) -> Dict[str, Any]:
        """Gemini API 설정 반환"""
        if not self._ai_config_cache:
            self._load_ai_config()
        
        config = self._ai_config_cache['gemini']
        if not config['api_key']:
            raise ValueError(
                "Gemini API 키가 설정되지 않았습니다.\n"
                "메뉴 3. Setup → 1. Register_Key에서 Gemini API Key를 설정하세요."
            )
        return config
    
    def get_hybrid_config(self) -> Dict[str, Any]:
        """하이브리드 모드 설정 반환"""
        if not self._ai_config_cache:
            self._load_ai_config()
        
        return self._ai_config_cache['hybrid']
    
    def is_hybrid_mode_enabled(self) -> bool:
        """하이브리드 모드 활성화 여부 확인"""
        hybrid_config = self.get_hybrid_config()
        return hybrid_config.get('enabled', False)
    
    def validate_hybrid_requirements(self) -> bool:
        """하이브리드 모드 필요 조건 검증"""
        try:
            claude_config = self.get_claude_config()
            gemini_config = self.get_gemini_config()
            
            # 두 API 키 모두 존재하는지 확인
            return bool(claude_config['api_key'] and gemini_config['api_key'])
            
        except ValueError:
            return False
    
    def get_available_engines(self) -> Dict[str, bool]:
        """사용 가능한 AI 엔진 목록 반환"""
        availability = {
            'openai': False,
            'claude': False, 
            'gemini': False,
            'hybrid': False
        }
        
        try:
            self.get_openai_config()
            availability['openai'] = True
        except ValueError:
            pass
        
        try:
            self.get_claude_config()
            availability['claude'] = True
        except ValueError:
            pass
        
        try:
            self.get_gemini_config()
            availability['gemini'] = True
        except ValueError:
            pass
        
        # 하이브리드 모드는 Claude + Gemini 둘 다 필요
        availability['hybrid'] = (
            availability['claude'] and 
            availability['gemini'] and 
            self.is_hybrid_mode_enabled()
        )
        
        return availability
    
    def refresh_cache(self):
        """설정 캐시 새로고침"""
        self._ai_config_cache = None
        logger.info("AI 설정 캐시 새로고침 완료")


# 전역 인스턴스 (싱글톤 패턴)
_ai_api_manager_instance: Optional[AIAPIManager] = None

def get_ai_api_manager(project_root: Path = None) -> AIAPIManager:
    """AI API Manager 싱글톤 인스턴스 반환"""
    global _ai_api_manager_instance
    
    if _ai_api_manager_instance is None:
        _ai_api_manager_instance = AIAPIManager(project_root)
    
    return _ai_api_manager_instance

def reset_ai_api_manager():
    """AI API Manager 인스턴스 리셋 (테스트용)"""
    global _ai_api_manager_instance
    _ai_api_manager_instance = None