#!/usr/bin/env python3
"""
AccountMemoryManager 테스트 스크립트
"""

import sys
from pathlib import Path

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.account_memory_manager import get_account_memory_manager, AccountSnapshot
from datetime import datetime


def test_account_memory_manager():
    """AccountMemoryManager 테스트"""
    print("=== AccountMemoryManager 테스트 시작 ===")
    
    # 싱글톤 인스턴스 가져오기
    manager = get_account_memory_manager()
    print(f"AccountMemoryManager 인스턴스: {type(manager).__name__}")
    
    # 메서드 존재 확인
    required_methods = [
        'get_pending_orders_count',
        'get_positions',
        'has_position',
        'get_position_quantity',
        'get_account',
        'get_holdings',
        'get_cash_balance',
        'get_available_cash'
    ]
    
    print("\n필수 메서드 존재 확인:")
    for method_name in required_methods:
        has_method = hasattr(manager, method_name)
        status = "OK" if has_method else "FAIL"
        print(f"  {status} {method_name}: {has_method}")
    
    # 기본 테스트 (계좌 데이터 없는 상태)
    print("\n기본 기능 테스트:")
    
    try:
        # 미체결 주문 수 테스트
        pending_count_mock = manager.get_pending_orders_count("MOCK")
        pending_count_real = manager.get_pending_orders_count("REAL")
        print(f"  미체결 주문 수 - MOCK: {pending_count_mock}, REAL: {pending_count_real}")
        
        # 보유 포지션 테스트
        positions_mock = manager.get_positions("MOCK")
        positions_real = manager.get_positions("REAL")
        print(f"  보유 포지션 수 - MOCK: {len(positions_mock)}, REAL: {len(positions_real)}")
        
        # 특정 종목 보유 여부 테스트
        has_samsung = manager.has_position("MOCK", "005930")
        print(f"  삼성전자(005930) 보유 여부 - MOCK: {has_samsung}")
        
        # 현금 잔고 테스트
        cash_mock = manager.get_cash_balance("MOCK")
        cash_real = manager.get_cash_balance("REAL")
        print(f"  현금 잔고 - MOCK: {cash_mock:,.0f}원, REAL: {cash_real:,.0f}원")
        
        print("OK 모든 기본 기능 테스트 통과")
        
    except Exception as e:
        print(f"FAIL 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    
    # 더미 계좌 데이터로 테스트
    print("\n더미 데이터 테스트:")
    try:
        # 더미 계좌 스냅샷 생성
        dummy_holdings = [
            {
                'stock_code': '005930',
                'stock_name': '삼성전자',
                'quantity': 10,
                'avg_price': 70000,
                'current_price': 75000,
                'evaluation': 750000,
                'profit_loss': 50000,
                'profit_rate': 7.14
            }
        ]
        
        dummy_snapshot = AccountSnapshot(
            timestamp=datetime.now(),
            account_type="MOCK",
            account_number="12345678-01",
            cash_balance=1000000,
            available_cash=900000,
            total_evaluation=1750000,
            profit_loss=50000,
            profit_rate=2.86,
            holdings=dummy_holdings,
            pending_orders=[]
        )
        
        # 더미 데이터 설정
        manager.mock_account = dummy_snapshot
        
        # 다시 테스트
        pending_count = manager.get_pending_orders_count("MOCK")
        positions = manager.get_positions("MOCK")
        has_samsung = manager.has_position("MOCK", "005930")
        samsung_qty = manager.get_position_quantity("MOCK", "005930")
        cash_balance = manager.get_cash_balance("MOCK")
        
        print(f"  미체결 주문 수: {pending_count}")
        print(f"  보유 포지션 수: {len(positions)}")
        print(f"  삼성전자 보유 여부: {has_samsung}")
        print(f"  삼성전자 보유 수량: {samsung_qty}주")
        print(f"  현금 잔고: {cash_balance:,.0f}원")
        
        if positions:
            print("  보유 종목:")
            for pos in positions:
                print(f"    - {pos['stock_name']}({pos['stock_code']}): {pos['quantity']}주")
        
        print("OK 더미 데이터 테스트 통과")
        
    except Exception as e:
        print(f"FAIL 더미 데이터 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== AccountMemoryManager 테스트 완료 ===")


if __name__ == "__main__":
    test_account_memory_manager()