#!/usr/bin/env python3
"""
[fix][opt] 통합 테마 정의 모듈
- 백테스팅용 vs 실전투자용 테마 통합 관리
- 사용자 설정 파일 자동 로딩 및 덮어쓰기
- 중복 제거 및 일관성 유지
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from enum import Enum

logger = logging.getLogger(__name__)

class ThemeType(Enum):
    """테마 사용 목적"""
    BACKTESTING = "backtesting"      # 백테스팅용 (종합적, 100+개)
    TRADING = "trading"              # 실전투자용 (선별적, 30+개)

class ThemeDefinitions:
    """테마별 종목 및 키워드 통합 정의"""
    
    # 사용자 설정 파일 경로
    USER_CONFIG_FILE = Path(__file__).parent / "user_theme_config.json"
    _user_config = None  # 캐시된 사용자 설정
    
    # =================================================================
    # 전체 테마 카테고리 (백테스팅용 - 종합적)
    # =================================================================
    COMPREHENSIVE_THEMES = {
        'AI_Technology': {
            'keywords': ['인공지능', 'AI', '머신러닝', '딥러닝', '자연어처리', '로보틱스', '자동화'],
            'description': 'AI 및 인공지능 기술 관련 종목',
            'priority': 1
        },
        'Semiconductor': {
            'keywords': ['반도체', '메모리', '시스템반도체', '팹리스', '반도체장비', 'DRAM', 'NAND'],
            'description': '반도체 및 메모리 관련 종목',
            'priority': 1
        },
        'Battery_EV': {
            'keywords': ['배터리', '전기차', 'EV', '이차전지', '리튬', '양극재', '음극재', '전지'],
            'description': '배터리 및 전기차 관련 종목',
            'priority': 1
        },
        'Bio_Healthcare': {
            'keywords': ['바이오', '제약', '의료기기', '진단', '백신', '항체', '의료', '헬스케어'],
            'description': '바이오 및 헬스케어 관련 종목',
            'priority': 1
        },
        'Gaming_Metaverse': {
            'keywords': ['게임', '메타버스', 'VR', 'AR', '가상현실', '증강현실', '플랫폼'],
            'description': '게임 및 메타버스 관련 종목',
            'priority': 2
        },
        'Renewable_Energy': {
            'keywords': ['태양광', '풍력', '수소', '연료전지', '신재생에너지', '그린에너지'],
            'description': '신재생에너지 관련 종목',
            'priority': 2
        },
        'Defense_Aerospace': {
            'keywords': ['방산', '국방', '항공우주', '위성', '드론', '미사일', '레이더'],
            'description': '방산 및 항공우주 관련 종목',
            'priority': 2
        },
        'Financial_Fintech': {
            'keywords': ['핀테크', '블록체인', '암호화폐', '디지털화폐', '결제', '금융'],
            'description': '핀테크 및 디지털금융 관련 종목',
            'priority': 3
        },
        'Food_Agriculture': {
            'keywords': ['식품', '농업', '축산', '수산', '대체육', '농기계', '바이오식품'],
            'description': '식품 및 농업 관련 종목',
            'priority': 3
        },
        'Construction_Infrastructure': {
            'keywords': ['건설', '인프라', '스마트시티', '건축자재', '도시개발'],
            'description': '건설 및 인프라 관련 종목',
            'priority': 3
        }
    }
    
    # =================================================================
    # 핵심 투자 테마 (실전투자용 - 선별적)
    # =================================================================
    CORE_INVESTMENT_THEMES = {
        'AI_Semiconductor': {
            'keywords': ['인공지능', 'AI', '반도체', '메모리', '시스템반도체', 'DRAM'],
            'description': 'AI 및 반도체 융합 고성장 종목',
            'priority': 1,
            'expected_return': 'high'
        },
        'Battery_EV': {
            'keywords': ['배터리', '전기차', 'EV', '이차전지', '양극재', '전지'],
            'description': '배터리 및 전기차 생태계 종목',
            'priority': 1,
            'expected_return': 'high'
        },
        'Bio_Healthcare': {
            'keywords': ['바이오', '제약', '의료기기', '진단', '백신'],
            'description': '바이오 및 헬스케어 혁신 종목',
            'priority': 2,
            'expected_return': 'medium-high'
        },
        'Gaming_Platform': {
            'keywords': ['게임', '플랫폼', '콘텐츠', '메타버스'],
            'description': '게임 및 디지털 플랫폼 종목',
            'priority': 2,
            'expected_return': 'medium-high'
        },
        'Defense_Tech': {
            'keywords': ['방산', '국방', '항공우주', '드론'],
            'description': '방산 및 첨단 기술 종목',
            'priority': 3,
            'expected_return': 'medium'
        }
    }
    
    # =================================================================
    # 동적 종목 로딩 - enhanced_theme_stocks.json 기반
    # =================================================================
    
    @classmethod
    def _load_enhanced_theme_stocks(cls) -> Dict[str, Any]:
        """enhanced_theme_stocks.json에서 동적 로드"""
        try:
            json_file = Path(__file__).parent / "enhanced_theme_stocks.json"
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"Enhanced theme stocks 로드 성공: {len([k for k in data.keys() if not k.startswith('_')])}개 테마")
                return data
            else:
                logger.warning("enhanced_theme_stocks.json 파일이 없습니다")
                return {}
        except Exception as e:
            logger.error(f"Enhanced theme stocks 로드 실패: {e}")
            return {}
    
    @classmethod
    def get_core_large_cap_stocks(cls) -> List[str]:
        """하드코딩된 종목 제거 - 실시간 API 사용 필요"""
        logger.warning("하드코딩된 대형주 데이터 제거됨 - 실시간 API 사용 권장")
        return []
    
    @classmethod
    def get_theme_representative_stocks(cls) -> Dict[str, List[str]]:
        """하드코딩된 종목 제거 - 실시간 API 사용 필요"""
        logger.warning("하드코딩된 테마 종목 데이터 제거됨 - 실시간 API 사용 권장")
        return {}
    
    @classmethod
    def _load_user_config(cls) -> Dict[str, Any]:
        """사용자 설정 파일 로드 (캐시 사용)"""
        if cls._user_config is not None:
            return cls._user_config
            
        try:
            if cls.USER_CONFIG_FILE.exists():
                with open(cls.USER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cls._user_config = json.load(f)
                    logger.info(f"사용자 테마 설정 로드 완료: {cls.USER_CONFIG_FILE}")
            else:
                logger.info("사용자 설정 파일이 없어서 기본 테마 사용")
                cls._user_config = {}
        except Exception as e:
            logger.error(f"사용자 설정 로드 실패: {e}, 기본 테마 사용")
            cls._user_config = {}
            
        return cls._user_config
    
    @classmethod
    def _merge_user_themes(cls, default_themes: Dict[str, Dict[str, Any]], 
                          theme_type: ThemeType) -> Dict[str, Dict[str, Any]]:
        """사용자 설정으로 기본 테마 덮어쓰기"""
        user_config = cls._load_user_config()
        
        if not user_config.get('user_preferences', {}).get('enable_custom_themes', False):
            return default_themes
            
        # 사용자 테마 설정 가져오기
        theme_key = f"{theme_type.value}_themes"
        user_themes = user_config.get(theme_key, {})
        
        if not user_themes:
            return default_themes
            
        # 활성화된 테마만 필터링하고 사용자 설정으로 덮어쓰기
        merged_themes = {}
        for theme_name, user_theme_config in user_themes.items():
            if user_theme_config.get('enabled', True):
                # 기본 테마 구조로 변환
                merged_themes[theme_name] = {
                    'keywords': user_theme_config.get('keywords', []),
                    'description': user_theme_config.get('description', ''),
                    'priority': user_theme_config.get('priority', 3),
                    'expected_return': user_theme_config.get('expected_return', 'medium')
                }
        
        if merged_themes:
            logger.info(f"사용자 정의 테마 적용: {len(merged_themes)}개 테마 ({theme_type.value})")
            return merged_themes
        else:
            logger.info(f"활성화된 사용자 테마가 없어서 기본 테마 사용 ({theme_type.value})")
            return default_themes
    
    @classmethod
    def get_themes_by_type(cls, theme_type: ThemeType) -> Dict[str, Dict[str, Any]]:
        """용도별 테마 정의 반환 (사용자 설정 자동 적용)"""
        if theme_type == ThemeType.BACKTESTING:
            default_themes = cls.COMPREHENSIVE_THEMES
        elif theme_type == ThemeType.TRADING:
            default_themes = cls.CORE_INVESTMENT_THEMES
        else:
            raise ValueError(f"Unknown theme type: {theme_type}")
            
        # 사용자 설정으로 덮어쓰기
        return cls._merge_user_themes(default_themes, theme_type)
    
    @classmethod
    def get_theme_keywords(cls, theme_type: ThemeType) -> Dict[str, List[str]]:
        """테마별 키워드 목록 반환"""
        themes = cls.get_themes_by_type(theme_type)
        return {theme_name: theme_info['keywords'] 
                for theme_name, theme_info in themes.items()}
    
    @classmethod
    def get_trading_stock_portfolio(cls) -> Dict[str, List[str]]:
        """실전투자용 종목 포트폴리오 반환 (사용자 설정 적용)"""
        user_config = cls._load_user_config()
        
        # 사용자 정의 대형주 포트폴리오 확인
        user_large_cap = user_config.get('core_large_cap_stocks', {})
        if user_large_cap.get('enabled', True) and user_large_cap.get('stocks'):
            large_cap_stocks = user_large_cap['stocks']
            logger.info("사용자 정의 대형주 포트폴리오 사용")
        else:
            large_cap_stocks = cls.get_core_large_cap_stocks()
            
        portfolio = {
            'Core_Large_Cap': large_cap_stocks,
            **cls.get_theme_representative_stocks()
        }
        return portfolio
    
    @classmethod
    def get_theme_info(cls, theme_type: ThemeType) -> Dict[str, str]:
        """테마별 상세 정보 반환"""
        themes = cls.get_themes_by_type(theme_type)
        return {theme_name: theme_info['description'] 
                for theme_name, theme_info in themes.items()}
    
    @classmethod
    def get_high_priority_themes(cls, theme_type: ThemeType, max_priority: int = 2) -> Dict[str, Dict[str, Any]]:
        """우선순위가 높은 테마만 반환"""
        themes = cls.get_themes_by_type(theme_type)
        return {theme_name: theme_info 
                for theme_name, theme_info in themes.items() 
                if theme_info['priority'] <= max_priority}

# 편의 함수들
def get_backtesting_themes() -> Dict[str, List[str]]:
    """백테스팅용 종합 테마 반환"""
    return ThemeDefinitions.get_theme_keywords(ThemeType.BACKTESTING)

def get_trading_themes() -> Dict[str, List[str]]:
    """실전투자용 핵심 테마 반환"""
    return ThemeDefinitions.get_theme_keywords(ThemeType.TRADING)

def get_trading_stocks() -> Dict[str, List[str]]:
    """하드코딩된 종목 데이터 제거 - 실시간 API 사용 필요"""
    logger.warning("하드코딩된 종목 포트폴리오 제거됨 - 실시간 API 사용 권장")
    return {}

# 테스트용
if __name__ == "__main__":
    print("=== 테마 정의 테스트 ===")
    
    print("1. 백테스팅용 테마:")
    backtesting_themes = get_backtesting_themes()
    for theme, keywords in backtesting_themes.items():
        print(f"  {theme}: {len(keywords)}개 키워드")
    
    print("2. 실전투자용 테마:")
    trading_themes = get_trading_themes()
    for theme, keywords in trading_themes.items():
        print(f"  {theme}: {len(keywords)}개 키워드")
    
    print("3. 실전투자용 종목 포트폴리오:")
    trading_stocks = get_trading_stocks()
    total_stocks = 0
    for theme, stocks in trading_stocks.items():
        print(f"  {theme}: {len(stocks)}개")
        total_stocks += len(stocks)
    
    print(f"총 {total_stocks}개 종목")