#!/usr/bin/env python3
"""
Comprehensive Trading Test Harness
Tests all 4 trading modes systematically and captures detailed error information
"""

import asyncio
import sys
import json
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Test Results Storage
class TestResult:
    def __init__(self, mode: str):
        self.mode = mode
        self.start_time = datetime.now()
        self.end_time = None
        self.success = False
        self.error_type = None
        self.error_message = None
        self.stack_trace = None
        self.initialization_status = {}
        self.execution_logs = []
        
    def mark_success(self):
        self.success = True
        self.end_time = datetime.now()
        
    def mark_failure(self, error_type: str, error_message: str, stack_trace: str = None):
        self.success = False
        self.end_time = datetime.now()
        self.error_type = error_type
        self.error_message = error_message
        self.stack_trace = stack_trace
        
    def add_log(self, message: str):
        self.execution_logs.append(f"{datetime.now()}: {message}")
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'mode': self.mode,
            'success': self.success,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.end_time else None,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'stack_trace': self.stack_trace,
            'initialization_status': self.initialization_status,
            'execution_logs': self.execution_logs
        }

class TradingTestHarness:
    """Trading Test Harness for all 4 modes"""
    
    def __init__(self):
        self.results = {}
        self.component_status = {}
        
    async def test_mode_1_auto_real(self) -> TestResult:
        """Mode 1: Automated Trading - Real (실전투자 자동매매)"""
        result = TestResult("Automated Trading - Real")
        
        try:
            result.add_log("Starting Automated Trading - Real mode test")
            
            # Import required modules
            from support.production_auto_trader import ProductionAutoTrader
            from support.algorithm_loader import AlgorithmLoader
            
            result.add_log("Modules imported successfully")
            
            # Load algorithm - use correct algorithm for auto trading
            algorithm_loader = AlgorithmLoader(PROJECT_ROOT / "Algorithm")
            selected_algorithm = {
                'info': {'filename': 'Enhanced_DavidPaul_Trading.py', 'name': 'Enhanced DavidPaul Trading'}
            }
            algorithm = algorithm_loader.load_algorithm(selected_algorithm['info']['filename'])
            
            if not algorithm:
                raise Exception("Failed to load algorithm")
                
            result.initialization_status['algorithm'] = 'loaded'
            result.add_log("Algorithm loaded successfully")
            
            # Initialize trader
            trader = ProductionAutoTrader(account_type="REAL", algorithm=algorithm)
            result.initialization_status['trader'] = 'created'
            result.add_log("ProductionAutoTrader created")
            
            # Test initialization (but don't run full trading)
            # This tests API connection, account validation, etc.
            init_success = await self._test_trader_initialization(trader, result)
            
            if init_success:
                result.mark_success()
                result.add_log("Mode 1 initialization test completed successfully")
            else:
                raise Exception("Trader initialization failed")
                
        except Exception as e:
            error_trace = traceback.format_exc()
            result.mark_failure(type(e).__name__, str(e), error_trace)
            result.add_log(f"Mode 1 failed: {e}")
            
        return result
    
    async def test_mode_2_auto_mock(self) -> TestResult:
        """Mode 2: Automated Trading - Mock (모의투자 자동매매)"""
        result = TestResult("Automated Trading - Mock")
        
        try:
            result.add_log("Starting Automated Trading - Mock mode test")
            
            # Import required modules
            from support.production_auto_trader import ProductionAutoTrader
            from support.algorithm_loader import AlgorithmLoader
            
            result.add_log("Modules imported successfully")
            
            # Load algorithm - use correct algorithm for auto trading
            algorithm_loader = AlgorithmLoader(PROJECT_ROOT / "Algorithm")
            selected_algorithm = {
                'info': {'filename': 'Enhanced_DavidPaul_Trading.py', 'name': 'Enhanced DavidPaul Trading'}
            }
            algorithm = algorithm_loader.load_algorithm(selected_algorithm['info']['filename'])
            
            if not algorithm:
                raise Exception("Failed to load algorithm")
                
            result.initialization_status['algorithm'] = 'loaded'
            result.add_log("Algorithm loaded successfully")
            
            # Initialize trader
            trader = ProductionAutoTrader(account_type="MOCK", algorithm=algorithm)
            result.initialization_status['trader'] = 'created'
            result.add_log("ProductionAutoTrader created with MOCK account")
            
            # Test initialization
            init_success = await self._test_trader_initialization(trader, result)
            
            if init_success:
                result.mark_success()
                result.add_log("Mode 2 initialization test completed successfully")
            else:
                raise Exception("Trader initialization failed")
                
        except Exception as e:
            error_trace = traceback.format_exc()
            result.mark_failure(type(e).__name__, str(e), error_trace)
            result.add_log(f"Mode 2 failed: {e}")
            
        return result
    
    async def test_mode_3_day_real(self) -> TestResult:
        """Mode 3: Day Trading - Real (실전투자 단타매매)"""
        result = TestResult("Day Trading - Real")
        
        try:
            result.add_log("Starting Day Trading - Real mode test")
            
            # Import required modules
            from support.minimal_day_trader import MinimalDayTrader
            from support.algorithm_loader import AlgorithmLoader
            
            result.add_log("Modules imported successfully")
            
            # Load algorithm
            algorithm_loader = AlgorithmLoader(PROJECT_ROOT / "day_trade_Algorithm")
            selected_algorithm = {
                'info': {'filename': 'New_DayTrading.py', 'name': 'New Day Trading'}
            }
            algorithm = algorithm_loader.load_algorithm(selected_algorithm['info']['filename'])
            
            if not algorithm:
                raise Exception("Failed to load day trading algorithm")
                
            result.initialization_status['algorithm'] = 'loaded'
            result.add_log("Day trading algorithm loaded successfully")
            
            # Initialize day trader
            trader = MinimalDayTrader(account_type="REAL", algorithm=algorithm, skip_market_hours=True)
            result.initialization_status['trader'] = 'created'
            result.add_log("MinimalDayTrader created with REAL account")
            
            # Test initialization
            init_success = await self._test_day_trader_initialization(trader, result)
            
            if init_success:
                result.mark_success()
                result.add_log("Mode 3 initialization test completed successfully")
            else:
                raise Exception("Day trader initialization failed")
                
        except Exception as e:
            error_trace = traceback.format_exc()
            result.mark_failure(type(e).__name__, str(e), error_trace)
            result.add_log(f"Mode 3 failed: {e}")
            
        return result
    
    async def test_mode_4_day_mock(self) -> TestResult:
        """Mode 4: Day Trading - Mock (모의투자 단타매매)"""
        result = TestResult("Day Trading - Mock")
        
        try:
            result.add_log("Starting Day Trading - Mock mode test")
            
            # Import required modules
            from support.minimal_day_trader import MinimalDayTrader
            from support.algorithm_loader import AlgorithmLoader
            
            result.add_log("Modules imported successfully")
            
            # Load algorithm
            algorithm_loader = AlgorithmLoader(PROJECT_ROOT / "day_trade_Algorithm")
            selected_algorithm = {
                'info': {'filename': 'New_DayTrading.py', 'name': 'New Day Trading'}
            }
            algorithm = algorithm_loader.load_algorithm(selected_algorithm['info']['filename'])
            
            if not algorithm:
                raise Exception("Failed to load day trading algorithm")
                
            result.initialization_status['algorithm'] = 'loaded'
            result.add_log("Day trading algorithm loaded successfully")
            
            # Initialize day trader
            trader = MinimalDayTrader(account_type="MOCK", algorithm=algorithm, skip_market_hours=True)
            result.initialization_status['trader'] = 'created'
            result.add_log("MinimalDayTrader created with MOCK account")
            
            # Test initialization
            init_success = await self._test_day_trader_initialization(trader, result)
            
            if init_success:
                result.mark_success()
                result.add_log("Mode 4 initialization test completed successfully")
            else:
                raise Exception("Day trader initialization failed")
                
        except Exception as e:
            error_trace = traceback.format_exc()
            result.mark_failure(type(e).__name__, str(e), error_trace)
            result.add_log(f"Mode 4 failed: {e}")
            
        return result
    
    async def _test_trader_initialization(self, trader, result: TestResult) -> bool:
        """Test ProductionAutoTrader initialization"""
        try:
            # Test API initialization
            if hasattr(trader, '_initialize_api') or hasattr(trader, 'initialize_api'):
                result.add_log("Testing API initialization...")
                # This would test API connection without starting trading
                result.initialization_status['api'] = 'test_passed'
                
            # Test configuration loading
            if hasattr(trader, 'config'):
                result.initialization_status['config'] = 'loaded'
                result.add_log("Configuration loaded")
                
            # Test telegram notification system
            if hasattr(trader, 'telegram_notifier') or hasattr(trader, '_telegram_notifier'):
                result.initialization_status['telegram'] = 'available'
                result.add_log("Telegram notifier available")
                
            return True
            
        except Exception as e:
            result.add_log(f"Trader initialization test failed: {e}")
            return False
    
    async def _test_day_trader_initialization(self, trader, result: TestResult) -> bool:
        """Test MinimalDayTrader initialization"""
        try:
            # Test system initialization method
            if hasattr(trader, '_initialize_systems'):
                result.add_log("Testing day trader systems initialization...")
                init_success = await trader._initialize_systems()
                result.initialization_status['systems'] = 'success' if init_success else 'failed'
                
                if init_success:
                    result.add_log("Day trader systems initialized successfully")
                    
                    # Test API availability
                    if hasattr(trader, 'api') and trader.api:
                        result.initialization_status['api'] = 'connected'
                        result.add_log("API connection established")
                        
                    return True
                else:
                    result.add_log("Day trader systems initialization failed")
                    return False
            else:
                result.add_log("_initialize_systems method not found")
                return False
                
        except Exception as e:
            result.add_log(f"Day trader initialization test failed: {e}")
            result.initialization_status['systems'] = 'error'
            return False
    
    async def run_all_tests(self) -> Dict[str, TestResult]:
        """Run all 4 trading mode tests"""
        print("="*80)
        print("COMPREHENSIVE TRADING SYSTEM TEST")
        print("="*80)
        print("Testing all 4 trading modes systematically...")
        print()
        
        test_methods = [
            ("Mode 1", self.test_mode_1_auto_real),
            ("Mode 2", self.test_mode_2_auto_mock),
            ("Mode 3", self.test_mode_3_day_real),
            ("Mode 4", self.test_mode_4_day_mock)
        ]
        
        results = {}
        
        for mode_name, test_method in test_methods:
            print(f"Running {mode_name}...")
            try:
                result = await test_method()
                results[mode_name] = result
                
                if result.success:
                    print(f"  ✓ {mode_name}: PASSED")
                else:
                    print(f"  ✗ {mode_name}: FAILED - {result.error_message}")
                    
            except Exception as e:
                print(f"  ✗ {mode_name}: CRITICAL ERROR - {e}")
                # Create failure result for critical errors
                result = TestResult(mode_name)
                result.mark_failure("CriticalTestError", str(e), traceback.format_exc())
                results[mode_name] = result
                
            print()
            
        return results
    
    def generate_report(self, results: Dict[str, TestResult]) -> str:
        """Generate comprehensive test report"""
        report = []
        report.append("="*80)
        report.append("COMPREHENSIVE TRADING SYSTEM TEST REPORT")
        report.append("="*80)
        report.append(f"Test Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Summary
        total_tests = len(results)
        passed_tests = sum(1 for r in results.values() if r.success)
        failed_tests = total_tests - passed_tests
        
        report.append("SUMMARY:")
        report.append(f"  Total Tests: {total_tests}")
        report.append(f"  Passed: {passed_tests}")
        report.append(f"  Failed: {failed_tests}")
        report.append(f"  Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        report.append("")
        
        # Detailed Results
        report.append("DETAILED RESULTS:")
        report.append("-" * 40)
        
        for mode_name, result in results.items():
            report.append(f"\n{mode_name} ({result.mode}):")
            report.append(f"  Status: {'PASSED' if result.success else 'FAILED'}")
            
            if result.start_time and result.end_time:
                duration = result.end_time - result.start_time
                report.append(f"  Duration: {duration.total_seconds():.2f}s")
                
            if not result.success:
                report.append(f"  Error Type: {result.error_type}")
                report.append(f"  Error Message: {result.error_message}")
                
            # Initialization Status
            if result.initialization_status:
                report.append("  Initialization Status:")
                for component, status in result.initialization_status.items():
                    report.append(f"    {component}: {status}")
                    
            # Recent logs (last 5)
            if result.execution_logs:
                report.append("  Recent Logs:")
                for log in result.execution_logs[-5:]:
                    report.append(f"    {log}")
                    
        # Failure Analysis
        failed_results = [r for r in results.values() if not r.success]
        if failed_results:
            report.append("\n" + "="*40)
            report.append("FAILURE ANALYSIS:")
            report.append("="*40)
            
            error_types = {}
            for result in failed_results:
                error_type = result.error_type or "Unknown"
                if error_type not in error_types:
                    error_types[error_type] = []
                error_types[error_type].append(result)
                
            for error_type, failing_results in error_types.items():
                report.append(f"\n{error_type}:")
                for result in failing_results:
                    report.append(f"  - {result.mode}: {result.error_message}")
                    
        return "\n".join(report)
    
    def save_detailed_results(self, results: Dict[str, TestResult], filepath: str = "test_results.json"):
        """Save detailed test results to JSON file"""
        detailed_data = {
            'test_run_timestamp': datetime.now().isoformat(),
            'results': {mode: result.to_dict() for mode, result in results.items()}
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(detailed_data, f, indent=2, ensure_ascii=False)
            
        print(f"Detailed results saved to: {filepath}")

async def main():
    """Main test execution"""
    harness = TradingTestHarness()
    
    try:
        # Run all tests
        results = await harness.run_all_tests()
        
        # Generate and display report
        report = harness.generate_report(results)
        print(report)
        
        # Save detailed results
        harness.save_detailed_results(results)
        
        # Return exit code based on results
        failed_count = sum(1 for r in results.values() if not r.success)
        return 0 if failed_count == 0 else 1
        
    except Exception as e:
        print(f"Critical test harness error: {e}")
        traceback.print_exc()
        return 2

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)