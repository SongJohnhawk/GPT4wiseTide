#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
거래 시스템의 실제 메서드 탐지
"""

import sys
import inspect
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def find_trading_methods():
    """거래 시스템의 실제 메서드들 찾기"""
    print("=== Trading System Method Discovery ===")
    
    try:
        from support.minimal_day_trader import MinimalDayTrader
        
        # 클래스의 모든 메서드 탐지
        all_methods = []
        all_attributes = dir(MinimalDayTrader)
        
        for attr_name in all_attributes:
            attr = getattr(MinimalDayTrader, attr_name, None)
            if callable(attr) and not attr_name.startswith('__'):
                all_methods.append(attr_name)
        
        print(f"[INFO] Total methods found: {len(all_methods)}")
        
        # 거래 관련 메서드 필터링
        trading_keywords = ['balance', 'position', 'account', 'stock', 'price', 'order', 'buy', 'sell', 'trade']
        trading_methods = []
        
        for method_name in all_methods:
            for keyword in trading_keywords:
                if keyword.lower() in method_name.lower():
                    trading_methods.append(method_name)
                    break
        
        print(f"\n[TRADING METHODS] Found {len(trading_methods)} trading-related methods:")
        for method in sorted(trading_methods):
            print(f"  - {method}")
        
        # 유용한 public 메서드들 (async가 아닌 것들)
        public_methods = [m for m in all_methods if not m.startswith('_') and 'async' not in m]
        print(f"\n[PUBLIC METHODS] Found {len(public_methods)} public methods:")
        for method in sorted(public_methods)[:15]:  # 처음 15개만 출력
            print(f"  - {method}")
        
        # 실제 인스턴스에서 메서드 확인
        print(f"\n[INSTANCE METHODS] Checking actual instance...")
        try:
            trader = MinimalDayTrader(account_type="MOCK")
            print("[OK] MinimalDayTrader instance created")
            
            # 실제 사용 가능한 메서드들 확인
            instance_methods = [m for m in dir(trader) if callable(getattr(trader, m)) and not m.startswith('__')]
            
            # 거래 관련 메서드들만 필터링
            instance_trading_methods = []
            for method_name in instance_methods:
                for keyword in trading_keywords:
                    if keyword.lower() in method_name.lower():
                        instance_trading_methods.append(method_name)
                        break
            
            print(f"Instance trading methods: {len(instance_trading_methods)}")
            for method in sorted(instance_trading_methods):
                print(f"  - {method}")
            
            # 특정 메서드 존재 여부 확인
            important_methods = [
                'get_current_balance', 'get_positions', 'get_account_info',
                'balance', 'positions', 'account_info',
                'current_balance', 'account_balance', 'portfolio'
            ]
            
            print(f"\n[SPECIFIC METHOD CHECK]")
            for method in important_methods:
                has_method = hasattr(trader, method)
                print(f"  {method}: {'YES' if has_method else 'NO'}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Could not create MinimalDayTrader instance: {e}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Could not import MinimalDayTrader: {e}")
        return False

def find_api_connector_methods():
    """API 커넥터 메서드들 찾기"""
    print(f"\n=== API Connector Method Discovery ===")
    
    try:
        from support.api_connector import KISAPIConnector
        
        # API 커넥터 인스턴스 생성
        connector = KISAPIConnector()
        print("[OK] KISAPIConnector instance created")
        
        # 메서드 탐지
        all_methods = [m for m in dir(connector) if callable(getattr(connector, m)) and not m.startswith('__')]
        
        # 거래 관련 메서드 필터링
        trading_keywords = ['balance', 'position', 'account', 'stock', 'price', 'order', 'buy', 'sell', 'trade', 'token']
        trading_methods = []
        
        for method_name in all_methods:
            for keyword in trading_keywords:
                if keyword.lower() in method_name.lower():
                    trading_methods.append(method_name)
                    break
        
        print(f"API Connector trading methods: {len(trading_methods)}")
        for method in sorted(trading_methods):
            print(f"  - {method}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Could not check API connector: {e}")
        return False

def main():
    """메인 실행"""
    print("Trading System Method Discovery")
    print("=" * 50)
    
    success_count = 0
    
    if find_trading_methods():
        success_count += 1
    
    if find_api_connector_methods():
        success_count += 1
    
    print(f"\n" + "=" * 50)
    print(f"Discovery completed: {success_count}/2 systems analyzed")
    
    return success_count >= 1

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Discovery failed: {e}")
        sys.exit(2)