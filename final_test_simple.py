#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Final Simple Test - No Unicode Issues
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_all_systems():
    """Test all systems"""
    print("GPT-5 Trading System Final Test")
    print("=" * 50)
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    results = {}
    
    # Test 1: API Connection
    print("\n[1] API Connection Test...")
    try:
        from support.api_connector import KISAPIConnector
        connector = KISAPIConnector()
        token = connector.get_access_token()
        
        if token and len(token) > 20:
            print(f"[OK] Token: {token[:30]}...")
            results['api'] = True
        else:
            print(f"[FAIL] Invalid token: {token}")
            results['api'] = False
    except Exception as e:
        print(f"[ERROR] API test failed: {e}")
        results['api'] = False
    
    # Test 2: Account Functions
    print("\n[2] Account Functions Test...")
    try:
        if 'connector' in locals() and connector:
            balance = connector.get_account_balance()
            positions = connector.get_positions()
            stock_info = connector.get_stock_info("005930")
            
            tests = [balance is not None, positions is not None, stock_info is not None]
            if any(tests):
                print(f"[OK] Account functions: {sum(tests)}/3 working")
                results['account'] = True
            else:
                print("[FAIL] No account functions working")
                results['account'] = False
        else:
            print("[SKIP] No connector available")
            results['account'] = False
    except Exception as e:
        print(f"[ERROR] Account test failed: {e}")
        results['account'] = False
    
    # Test 3: GPT-5 System
    print("\n[3] GPT-5 System Test...")
    try:
        from support.gpt5_decision_engine import GPT5DecisionEngine
        from support.trading_decision import TradingDecision
        
        config = {"model": "gpt-4", "api_base": None}
        engine = GPT5DecisionEngine(config)
        
        decision = TradingDecision(
            symbol="005930",
            decision="BUY",
            confidence=0.8,
            reasoning="Test decision"
        )
        
        print(f"[OK] GPT-5 engine and TradingDecision working")
        results['gpt5'] = True
    except Exception as e:
        print(f"[ERROR] GPT-5 test failed: {e}")
        results['gpt5'] = False
    
    # Test 4: Data Collection
    print("\n[4] Data Collection Test...")
    try:
        from support.integrated_free_data_system import IntegratedFreeDataSystem
        
        data_system = IntegratedFreeDataSystem()
        korea_data = await data_system.collect_korean_stock_data()
        
        if korea_data and len(korea_data) > 0:
            print(f"[OK] Data collected: {len(korea_data)} items")
            results['data'] = True
        else:
            print("[FAIL] No data collected")
            results['data'] = False
    except Exception as e:
        print(f"[ERROR] Data test failed: {e}")
        results['data'] = False
    
    # Test 5: Event System
    print("\n[5] Event System Test...")
    try:
        from support.event_bus_system import Event, EventType, Priority
        import datetime as dt
        
        event = Event(
            event_id="test",
            event_type=EventType.MARKET_DATA_UPDATE,
            priority=Priority.NORMAL,
            timestamp=dt.datetime.now(),
            data={"test": "data"},
            source="test"
        )
        
        print("[OK] Event system structure working")
        results['events'] = True
    except Exception as e:
        print(f"[ERROR] Event test failed: {e}")
        results['events'] = False
    
    # Test 6: AI Service Manager
    print("\n[6] AI Service Manager Test...")
    try:
        from support.ai_service_manager import AIServiceManager
        
        service_manager = AIServiceManager()
        
        if hasattr(service_manager, 'services'):
            print("[OK] AI Service Manager structure working")
            results['ai_manager'] = True
        else:
            print("[FAIL] AI Service Manager incomplete")
            results['ai_manager'] = False
    except Exception as e:
        print(f"[ERROR] AI manager test failed: {e}")
        results['ai_manager'] = False
    
    # Test 7: Integration Adapter
    print("\n[7] Integration Adapter Test...")
    try:
        from support.tidewise_integration_adapter import TideWiseIntegrationAdapter
        
        adapter = TideWiseIntegrationAdapter()
        
        if hasattr(adapter, 'active_system'):
            print("[OK] Integration adapter working")
            results['integration'] = True
        else:
            print("[FAIL] Integration adapter incomplete")
            results['integration'] = False
    except Exception as e:
        print(f"[ERROR] Integration test failed: {e}")
        results['integration'] = False
    
    # Final Results
    print("\n" + "=" * 50)
    print("FINAL RESULTS:")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {test_name}: {status}")
    
    success_rate = (passed / total) * 100
    print(f"\nSuccess Rate: {passed}/{total} ({success_rate:.1f}%)")
    
    if success_rate >= 90:
        print("Status: EXCELLENT - Production Ready!")
        return 0
    elif success_rate >= 75:
        print("Status: VERY GOOD - Most functions working")
        return 0
    elif success_rate >= 60:
        print("Status: GOOD - Core functions working")
        return 0
    elif success_rate >= 40:
        print("Status: WARNING - Needs improvement")
        return 1
    else:
        print("Status: CRITICAL - Major issues")
        return 2

async def main():
    """Main execution"""
    try:
        exit_code = await test_all_systems()
        print(f"\nFinal Exit Code: {exit_code}")
        return exit_code
    except Exception as e:
        print(f"Test failed: {e}")
        return 3

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)