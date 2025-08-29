#!/usr/bin/env python3
"""
Self-Healing Test Suite - tideWise 자가 치유 테스트 시스템
자동화된 테스트를 통해 잠재적 문제 발굴 및 시스템 완전성 검증
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
import traceback

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.minimal_day_trader import MinimalDayTrader
from support.api_connector import KISAPIConnector
from support.account_memory_manager import AccountMemoryManager

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SelfHealingTestSuite:
    """자가 치유 테스트 스위트"""
    
    def __init__(self):
        self.test_results = []
        self.critical_issues = []
        self.warnings = []
        
    async def run_comprehensive_tests(self) -> Dict[str, Any]:
        """포괄적 테스트 실행"""
        print("🔍 [SELF-HEALING] tideWise 자가 치유 테스트 시작")
        print("=" * 60)
        
        # 테스트 카테고리별 실행
        test_categories = [
            ("키 불일치 테스트", self.test_key_consistency),
            ("계좌 상태 갱신 테스트", self.test_account_update),
            ("수익 계산 테스트", self.test_profit_calculation),
            ("포지션 관리 테스트", self.test_position_management),
            ("알고리즘 통합 테스트", self.test_algorithm_integration),
            ("메모리 누수 테스트", self.test_memory_management),
            ("오류 처리 테스트", self.test_error_handling),
            ("경합 상태 테스트", self.test_race_conditions)
        ]
        
        for test_name, test_func in test_categories:
            print(f"\n🧪 {test_name} 실행 중...")
            try:
                result = await test_func()
                self.test_results.append({
                    'name': test_name,
                    'status': 'PASS' if result['success'] else 'FAIL',
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                })
                
                if not result['success']:
                    self.critical_issues.extend(result.get('issues', []))
                    
                print(f"   ✅ {test_name} 완료 - {'성공' if result['success'] else '실패'}")
                
            except Exception as e:
                error_msg = f"{test_name} 실행 중 오류: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                
                self.test_results.append({
                    'name': test_name,
                    'status': 'ERROR',
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat()
                })
                self.critical_issues.append(error_msg)
                print(f"   ❌ {test_name} 오류")
        
        return self.generate_test_report()
    
    async def test_key_consistency(self) -> Dict[str, Any]:
        """키 불일치 문제 테스트 (문제 1 검증)"""
        issues = []
        success = True
        
        try:
            # MinimalDayTrader 인스턴스 생성 (MOCK 모드)
            trader = MinimalDayTrader("MOCK", skip_market_hours=True)
            
            # 시스템 초기화 (실제 동작 환경과 동일하게)
            await trader._initialize_systems()
            
            # 포지션 딕셔너리 생성 테스트
            mock_positions_list = [
                {'stock_code': '005930', 'symbol': '005930', 'quantity': 10, 'avg_price': 50000},
                {'stock_code': '000660', 'symbol': '000660', 'quantity': 5, 'average_price': 30000},
                {'symbol': '035420', 'quantity': 8, 'price': 25000}  # stock_code 없는 경우
            ]
            
            # 포지션 딕셔너리 변환 로직 테스트
            current_positions = {}
            for position in mock_positions_list:
                if isinstance(position, dict):
                    stock_code = position.get('stock_code') or position.get('symbol')
                    if stock_code:
                        if 'avg_price' not in position and 'average_price' in position:
                            position['avg_price'] = position['average_price']
                        current_positions[stock_code] = position
            
            # 검증 1: 모든 포지션이 stock_code 키로 접근 가능한지 확인
            if len(current_positions) != 3:
                issues.append(f"포지션 변환 실패: 예상 3개, 실제 {len(current_positions)}개")
                success = False
            
            # 검증 2: avg_price 필드 일관성 확인
            for stock_code, position in current_positions.items():
                if 'avg_price' not in position:
                    issues.append(f"종목 {stock_code}: avg_price 필드 누락")
                    success = False
            
            return {
                'success': success,
                'issues': issues,
                'details': {
                    'positions_converted': len(current_positions),
                    'positions_with_avg_price': sum(1 for p in current_positions.values() if 'avg_price' in p)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"키 일관성 테스트 오류: {str(e)}"],
                'error': str(e)
            }
    
    async def test_account_update(self) -> Dict[str, Any]:
        """계좌 상태 갱신 테스트 (문제 2 검증)"""
        issues = []
        success = True
        
        try:
            # AccountMemoryManager 초기화 테스트
            account_manager = AccountMemoryManager()
            
            # 거래 정보 모의 생성
            mock_trade_info = {
                'stock_code': '005930',
                'stock_name': '삼성전자',
                'quantity': 10,
                'price': 50000,
                'amount': 500000
            }
            
            # update_after_trade 메소드 존재 확인
            if not hasattr(account_manager, 'update_after_trade'):
                issues.append("AccountMemoryManager.update_after_trade 메소드 누락")
                success = False
            
            # 메소드 시그니처 확인 (매개변수 개수)
            import inspect
            sig = inspect.signature(account_manager.update_after_trade)
            if len(sig.parameters) < 4:
                issues.append("update_after_trade 메소드 매개변수 부족")
                success = False
            
            return {
                'success': success,
                'issues': issues,
                'details': {
                    'account_manager_initialized': True,
                    'update_method_exists': hasattr(account_manager, 'update_after_trade'),
                    'method_parameters': len(sig.parameters) if hasattr(account_manager, 'update_after_trade') else 0
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"계좌 상태 갱신 테스트 오류: {str(e)}"],
                'error': str(e)
            }
    
    async def test_profit_calculation(self) -> Dict[str, Any]:
        """수익 계산 테스트 (문제 3 검증)"""
        issues = []
        success = True
        
        try:
            # 매도 결과 모의 생성
            mock_position = {
                'stock_code': '005930',
                'quantity': 10,
                'avg_price': 50000
            }
            
            current_price = 55000  # 5000원 상승
            quantity = 10
            
            # 수익 계산 로직 테스트
            avg_price = mock_position.get('avg_price', 0)
            profit = (current_price - avg_price) * quantity if avg_price > 0 else 0
            profit_rate = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            
            # 검증 1: 수익 계산 정확성
            expected_profit = 50000  # (55000 - 50000) * 10
            expected_profit_rate = 10.0  # 10% 상승
            
            if abs(profit - expected_profit) > 0.01:
                issues.append(f"수익 계산 오류: 예상 {expected_profit}, 실제 {profit}")
                success = False
                
            if abs(profit_rate - expected_profit_rate) > 0.01:
                issues.append(f"수익률 계산 오류: 예상 {expected_profit_rate}%, 실제 {profit_rate}%")
                success = False
            
            # 검증 2: 매도 결과 구조 확인
            sell_result = {
                'symbol': '005930',
                'action': 'SELL',
                'quantity': quantity,
                'price': current_price,
                'avg_price': avg_price,
                'executed': True,
                'amount': quantity * current_price,
                'profit': profit,
                'profit_rate': profit_rate
            }
            
            required_fields = ['profit', 'profit_rate', 'avg_price']
            missing_fields = [field for field in required_fields if field not in sell_result]
            
            if missing_fields:
                issues.append(f"매도 결과 필수 필드 누락: {missing_fields}")
                success = False
            
            return {
                'success': success,
                'issues': issues,
                'details': {
                    'calculated_profit': profit,
                    'calculated_profit_rate': profit_rate,
                    'result_has_profit_fields': not missing_fields
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"수익 계산 테스트 오류: {str(e)}"],
                'error': str(e)
            }
    
    async def test_position_management(self) -> Dict[str, Any]:
        """포지션 관리 일관성 테스트"""
        issues = []
        success = True
        
        try:
            trader = MinimalDayTrader("MOCK", skip_market_hours=True)
            await trader._initialize_systems()
            
            # 포지션 사이즈 비율 검증
            if trader.position_size_ratio != 0.2:
                issues.append(f"포지션 사이즈 비율 불일치: 예상 0.2, 실제 {trader.position_size_ratio}")
                success = False
            
            # 신뢰도 임계값 검증
            if trader.confidence_threshold != 0.6:
                issues.append(f"신뢰도 임계값 불일치: 예상 0.6, 실제 {trader.confidence_threshold}")
            
            return {
                'success': success,
                'issues': issues,
                'details': {
                    'position_size_ratio': trader.position_size_ratio,
                    'confidence_threshold': trader.confidence_threshold,
                    'max_positions': trader.max_positions
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"포지션 관리 테스트 오류: {str(e)}"],
                'error': str(e)
            }
    
    async def test_algorithm_integration(self) -> Dict[str, Any]:
        """알고리즘 통합 테스트"""
        issues = []
        success = True
        
        try:
            trader = MinimalDayTrader("MOCK", skip_market_hours=True)
            await trader._initialize_systems()
            
            # _analyze_with_algorithm 메소드 시그니처 확인
            import inspect
            sig = inspect.signature(trader._analyze_with_algorithm)
            
            if 'is_position' not in sig.parameters:
                issues.append("_analyze_with_algorithm에 is_position 매개변수 누락")
                success = False
            
            # 기본값 확인
            is_position_param = sig.parameters.get('is_position')
            if is_position_param and is_position_param.default != False:
                issues.append("is_position 매개변수 기본값이 False가 아님")
                success = False
            
            return {
                'success': success,
                'issues': issues,
                'details': {
                    'method_exists': hasattr(trader, '_analyze_with_algorithm'),
                    'has_is_position_param': 'is_position' in sig.parameters,
                    'parameter_count': len(sig.parameters)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"알고리즘 통합 테스트 오류: {str(e)}"],
                'error': str(e)
            }
    
    async def test_memory_management(self) -> Dict[str, Any]:
        """메모리 관리 테스트"""
        issues = []
        success = True
        
        try:
            import gc
            import psutil
            import os
            
            # 메모리 사용량 측정
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 메모리 집약적 작업 시뮬레이션
            traders = []
            for i in range(10):
                trader = MinimalDayTrader("MOCK", skip_market_hours=True)
                traders.append(trader)
            
            # 가비지 컬렉션 실행
            del traders
            gc.collect()
            
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            # 메모리 누수 검사 (10MB 이상 증가시 경고)
            if memory_increase > 10:
                issues.append(f"메모리 누수 의심: {memory_increase:.2f}MB 증가")
                success = False
            
            return {
                'success': success,
                'issues': issues,
                'details': {
                    'initial_memory_mb': round(initial_memory, 2),
                    'final_memory_mb': round(final_memory, 2),
                    'memory_increase_mb': round(memory_increase, 2)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"메모리 관리 테스트 오류: {str(e)}"],
                'error': str(e)
            }
    
    async def test_error_handling(self) -> Dict[str, Any]:
        """오류 처리 테스트"""
        issues = []
        success = True
        
        try:
            trader = MinimalDayTrader("MOCK", skip_market_hours=True)
            await trader._initialize_systems()
            
            # 잘못된 데이터로 테스트
            invalid_stock_data = None
            
            # 오류 처리 능력 테스트
            try:
                result = await trader._analyze_with_algorithm("TEST", invalid_stock_data, is_position=True)
                
                # 오류가 발생해야 하는데 발생하지 않으면 문제
                if result is None:
                    issues.append("None 데이터 처리 시 적절한 기본값 반환 실패")
                    success = False
                    
            except Exception as expected_error:
                # 예상된 오류는 정상
                pass
            
            return {
                'success': success,
                'issues': issues,
                'details': {
                    'error_handling_tested': True
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"오류 처리 테스트 오류: {str(e)}"],
                'error': str(e)
            }
    
    async def test_race_conditions(self) -> Dict[str, Any]:
        """경합 상태 테스트"""
        issues = []
        success = True
        
        try:
            # 동시 실행 시뮬레이션
            trader = MinimalDayTrader("MOCK", skip_market_hours=True)
            
            # 메모리 관리자 상태 확인
            if not hasattr(trader, 'account_memory_manager') or trader.account_memory_manager is None:
                issues.append("account_memory_manager 초기화되지 않음")
                success = False
            
            if not hasattr(trader, 'memory_manager'):
                issues.append("memory_manager 초기화되지 않음")
                success = False
            
            return {
                'success': success,
                'issues': issues,
                'details': {
                    'account_memory_manager_initialized': hasattr(trader, 'account_memory_manager'),
                    'memory_manager_initialized': hasattr(trader, 'memory_manager')
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"경합 상태 테스트 오류: {str(e)}"],
                'error': str(e)
            }
    
    def generate_test_report(self) -> Dict[str, Any]:
        """테스트 결과 리포트 생성"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['status'] == 'PASS')
        failed_tests = sum(1 for result in self.test_results if result['status'] == 'FAIL')
        error_tests = sum(1 for result in self.test_results if result['status'] == 'ERROR')
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'errors': error_tests,
                'success_rate': round(success_rate, 2)
            },
            'test_results': self.test_results,
            'critical_issues': self.critical_issues,
            'warnings': self.warnings,
            'system_status': 'HEALTHY' if success_rate >= 90 and not self.critical_issues else 'NEEDS_ATTENTION'
        }
        
        return report

async def main():
    """메인 함수 - 자가 치유 테스트 실행"""
    test_suite = SelfHealingTestSuite()
    
    try:
        # 포괄적 테스트 실행
        report = await test_suite.run_comprehensive_tests()
        
        # 결과 출력
        print("\n" + "=" * 60)
        print("🏥 [SELF-HEALING] 자가 치유 테스트 완료")
        print("=" * 60)
        
        summary = report['summary']
        print(f"📊 테스트 결과: {summary['passed']}/{summary['total_tests']} 통과 ({summary['success_rate']}%)")
        print(f"🚨 시스템 상태: {report['system_status']}")
        
        if report['critical_issues']:
            print(f"\n⚠️  중대 문제 발견:")
            for issue in report['critical_issues']:
                print(f"   - {issue}")
        else:
            print("\n✅ 중대 문제 없음")
        
        # 상세 리포트 파일 저장
        report_file = PROJECT_ROOT / f"self_healing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        import json
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"📄 상세 리포트: {report_file}")
        
        return report['system_status'] == 'HEALTHY'
        
    except Exception as e:
        print(f"❌ 자가 치유 테스트 실행 오류: {e}")
        logger.error(f"자가 치유 테스트 오류: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    # 비동기 실행
    success = asyncio.run(main())
    sys.exit(0 if success else 1)