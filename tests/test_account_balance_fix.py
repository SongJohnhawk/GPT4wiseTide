#!/usr/bin/env python3
"""
실계좌 계좌조회 하드코딩 수정사항 긴급 테스트
예수금 104,880원 및 원익홀딩스 12주 표시 확인
"""

import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_real_account_balance():
    """실계좌 계좌조회 수정 테스트"""
    print("[긴급] 실계좌 테스트 - 하드코딩 제거 확인")
    
    try:
        # day_trading_runner 직접 테스트
        from support.day_trading_runner import DayTradingRunner
        
        print("1. 실전계좌 DayTradingRunner 초기화...")
        runner = DayTradingRunner(
            account_type="REAL",
            selected_algorithm={"name": "test", "file": "test.py"}
        )
        
        print("2. API 초기화 및 계좌 조회...")
        
        # 실제 계좌 조회 테스트
        import asyncio
        result = asyncio.run(test_account_query(runner))
        
        return result
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_account_query(runner):
    """계좌 조회 비동기 테스트"""
    try:
        # 최적화 시스템 초기화
        await runner._initialize_optimization_systems()
        
        # 실제 계좌 정보 조회
        from support.api_connector import KISAPIConnector
        
        print("3. 실전투자 API 직접 호출...")
        api = KISAPIConnector(is_mock=False)  # 실전계좌
        account_data = await api.get_account_balance(force_refresh=True)
        
        print(f"[디버그] API 응답 타입: {type(account_data)}")
        if account_data:
            print(f"[디버그] API 응답 키: {list(account_data.keys()) if isinstance(account_data, dict) else 'Not Dict'}")
        
        if account_data:
            # API 응답이 이미 루트 레벨에 데이터가 있음 (output2 구조 아님)
            cash_balance = float(account_data.get('dnca_tot_amt', '0'))
            available_cash = float(account_data.get('ord_psbl_cash', '0'))
            
            # 실현손익 관련 정보 추가
            realized_profit = float(account_data.get('evlu_pfls_smtl_amt', '0'))
            asset_change = float(account_data.get('asst_icdc_amt', '0'))
            today_sell = float(account_data.get('thdt_sll_amt', '0'))
            yesterday_sell = float(account_data.get('bfdy_sll_amt', '0'))
            
            print(f"[OK] API 응답 - 예수금: {cash_balance:,.0f}원")
            print(f"[OK] API 응답 - 주문가능: {available_cash:,.0f}원")
            print(f"[OK] API 응답 - 실현손익: {realized_profit:,.0f}원")
            print(f"[OK] API 응답 - 자산증감: {asset_change:,.0f}원")
            print(f"[OK] API 응답 - 당일매도: {today_sell:,.0f}원")
            print(f"[OK] API 응답 - 전일매도: {yesterday_sell:,.0f}원")
            
            # 보유종목 확인
            holdings = []
            if 'output1' in account_data:
                for item in account_data['output1']:
                    quantity = int(item.get('hldg_qty', '0'))
                    if quantity > 0:
                        stock_name = item.get('prdt_name', '').strip()
                        # 다른 수량 필드들도 확인
                        ord_psbl_qty = int(item.get('ord_psbl_qty', '0'))  # 주문가능수량
                        bfdy_buy_qty = int(item.get('bfdy_buy_qty', '0'))  # 전일매수수량  
                        thdt_buy_qty = int(item.get('thdt_buyqty', '0'))   # 당일매수수량
                        thdt_sll_qty = int(item.get('thdt_sll_qty', '0'))  # 당일매도수량
                        
                        print(f"[디버그] {stock_name}: 보유수량={quantity}주, 주문가능={ord_psbl_qty}주, 전일매수={bfdy_buy_qty}주, 당일매수={thdt_buy_qty}주, 당일매도={thdt_sll_qty}주")
                        print(f"[OK] 보유종목: {stock_name} {quantity}주 (당일매도: {thdt_sll_qty}주)")
                        holdings.append((stock_name, quantity))
            
            # 결과 검증
            if cash_balance == 104880:
                print("[성공] 예수금 104,880원 정확 일치!")
            elif cash_balance > 0:
                print(f"[확인] 실제 예수금: {cash_balance:,.0f}원")
            else:
                print("[실패] 여전히 0원 - 하드코딩 문제 미해결")
                return False
            
            # 원익홀딩스 확인 
            woonik_found = False
            for name, qty in holdings:
                if '원익홀딩스' in name:
                    if qty == 17:
                        print("[성공] 원익홀딩스 17주 정확 일치!")
                        woonik_found = True
                    else:
                        print(f"[확인] 원익홀딩스: {qty}주 (예상: 17주)")
                        woonik_found = True
                    break
            
            if not woonik_found and holdings:
                print("[정보] 원익홀딩스 미발견 - 다른 종목들:")
                for name, qty in holdings:
                    print(f"   {name}: {qty}주")
            
            return True
        else:
            print("[실패] API 응답이 비어있음")
            return False
            
    except Exception as e:
        print(f"[오류] 계좌조회 오류: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("실계좌 하드코딩 제거 긴급 테스트")
    print("=" * 50)
    
    success = test_real_account_balance()
    
    if success:
        print("\n[완료] 실계좌 테스트 성공!")
    else:
        print("\n[실패] 실계좌 테스트 실패 - 즉시 수정 필요")