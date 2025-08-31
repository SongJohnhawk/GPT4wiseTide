#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT-5 System Health Check
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def check_modules():
    """Check module imports"""
    print("=== Module Import Check ===")
    
    modules = [
        ("Data System", "support.integrated_free_data_system", "IntegratedFreeDataSystem"),
        ("GPT-5 Engine", "support.gpt5_decision_engine", "GPT5DecisionEngine"),
        ("Event Bus", "support.event_bus_system", "EventBusSystem"),
        ("AI Manager", "support.ai_service_manager", "AIServiceManager"),
        ("Integration", "support.tidewise_integration_adapter", "TideWiseIntegrationAdapter"),
    ]
    
    success = 0
    total = len(modules)
    
    for name, module_path, class_name in modules:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"[OK] {name}")
            success += 1
        except Exception as e:
            print(f"[FAIL] {name}: {str(e)[:50]}...")
    
    print(f"Result: {success}/{total} modules OK")
    return success, total

def check_files():
    """Check file structure"""
    print("\n=== File Structure Check ===")
    
    files = [
        "run_gpt5_trading.py",
        "support/integrated_free_data_system.py",
        "support/gpt5_decision_engine.py",
        "support/event_bus_system.py",
        "requirements_free_news.txt"
    ]
    
    success = 0
    total = len(files)
    
    for file_path in files:
        full_path = PROJECT_ROOT / file_path
        if full_path.exists():
            print(f"[OK] {file_path}")
            success += 1
        else:
            print(f"[MISSING] {file_path}")
    
    print(f"Result: {success}/{total} files OK")
    return success, total

def main():
    """Main health check"""
    print("GPT-5 Trading System Health Check")
    print("=" * 40)
    
    mod_ok, mod_total = check_modules()
    file_ok, file_total = check_files()
    
    total_ok = mod_ok + file_ok
    total_tests = mod_total + file_total
    
    rate = (total_ok / total_tests) * 100
    
    print(f"\n=== Summary ===")
    print(f"Modules: {mod_ok}/{mod_total}")
    print(f"Files: {file_ok}/{file_total}")
    print(f"Overall: {total_ok}/{total_tests} ({rate:.1f}%)")
    
    if rate >= 80:
        print("Status: HEALTHY")
    elif rate >= 60:
        print("Status: WARNING")
    else:
        print("Status: CRITICAL")
    
    return rate >= 80

if __name__ == "__main__":
    try:
        healthy = main()
        sys.exit(0 if healthy else 1)
    except Exception as e:
        print(f"Health check failed: {e}")
        sys.exit(1)