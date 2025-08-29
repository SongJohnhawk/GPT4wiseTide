#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""매도 주문 오류 수정 확인 테스트"""

from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
from support.api_connector import KISAPIConnector

async def test_sell_order():
    """매도 주문 테스트 - invalidate_balance_cache 메서드 확인"""
    print("\n" + "="*60)
    print("매도 주문 오류 수정 확인 테스트")
    print("="*60)
    
    try:
        # 모의투자 모드로 API 커넥터 생성
        api = KISAPIConnector(is_mock=True)
        print("✅ API 커넥터 초기화 성공")
        
        # invalidate_balance_cache 메서드 존재 확인
        if hasattr(api, 'invalidate_balance_cache'):
            print("✅ invalidate_balance_cache 메서드 존재함")
            
            # 메서드 호출 테스트
            try:
                api.invalidate_balance_cache()
                print("✅ invalidate_balance_cache 메서드 호출 성공")
            except Exception as e:
                print(f"❌ invalidate_balance_cache 메서드 호출 실패: {e}")
                return False
        else:
            print("❌ invalidate_balance_cache 메서드가 없습니다")
            return False
            
        # 실제 매도 주문 테스트 (모의투자, 시장가)
        print("\n매도 주문 시뮬레이션...")
        
        # 테스트용 매도 (실제로는 실행되지 않음 - 잔고가 없을 것)
        test_symbol = "005930"  # 삼성전자
        test_quantity = 1
        
        print(f"테스트 매도: {test_symbol} {test_quantity}주")
        
        # place_sell_order 메서드가 정상 작동하는지 확인
        result = api.place_sell_order(
            symbol=test_symbol,
            quantity=test_quantity,
            price=0,  # 시장가
            order_type="01"  # 시장가 주문
        )
        
        # 결과에 관계없이 메서드 호출이 에러 없이 완료되면 성공
        if result is not None:
            print("✅ 매도 주문 메서드 호출 완료 (에러 없음)")
            if result.get('rt_cd') == '0':
                print(f"   - 주문 성공: {result.get('msg1', '')}")
            else:
                print(f"   - 예상된 실패 (잔고 부족 등): {result.get('msg1', 'N/A')}")
        else:
            print("⚠️ 매도 주문 결과가 None입니다")
            
        print("\n✅ 모든 테스트 통과 - invalidate_balance_cache 오류 수정됨")
        return True
        
    except AttributeError as e:
        print(f"❌ AttributeError 발생: {e}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        return False
    finally:
        print("\n" + "="*60)

def main():
    """메인 실행 함수"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(test_sell_order())
        if result:
            print("✅ 테스트 성공: 매도 주문 오류가 해결되었습니다!")
        else:
            print("❌ 테스트 실패: 문제가 계속 발생합니다.")
    finally:
        loop.close()

if __name__ == "__main__":
    main()