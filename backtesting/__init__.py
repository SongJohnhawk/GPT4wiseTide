# tideWise 백테스트 시스템
# 프로젝트 지침: 정책 기반 다중 조건 VI 우선형 알고리즘 검증

"""
tideWise Backtest System

자동매매 알고리즘의 성과를 종합적으로 검증하는 백테스트 시스템입니다.

주요 기능:
- 동적 알고리즘 로딩 및 검증
- 다중 소스 데이터 수집
- 종합 성과 분석 및 리포트 생성
- 프로젝트 정책 기반 매매 시뮬레이션

사용법:
    python main_runner.py --algorithm ../KStockAutoTrade.py --mode full
"""

__version__ = "1.0.0"
__author__ = "tideWise Team"

# 주요 컴포넌트 임포트는 필요시에만 수행 (메모리 최적화)
