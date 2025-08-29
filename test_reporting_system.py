"""
tideWise 리포팅 시스템 테스트
휴장일 제공자, 거래 리포터, 통합 모듈 테스트
"""
import sys
import asyncio
from pathlib import Path
from datetime import date, datetime
import json

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.holiday_provider import holiday_provider
from support.trade_reporter import trade_reporter, TradeRecord
from support.report_integration import reporting_integration, log_buy_order, log_sell_order


async def test_holiday_provider():
    """휴장일 제공자 테스트"""
    print("=== 휴장일 제공자 테스트 ===")
    
    # 2025년 휴장일 업데이트
    success = holiday_provider.update_holidays(2025)
    print(f"휴장일 업데이트 성공: {success}")
    
    # 특정 날짜 휴장일 확인
    test_dates = [
        date(2025, 8, 22),  # 목요일 (거래일)
        date(2025, 8, 24),  # 토요일 (주말)
        date(2025, 1, 1),   # 신정 (공휴일)
        date(2025, 12, 25), # 크리스마스 (공휴일)
    ]
    
    for test_date in test_dates:
        is_holiday = holiday_provider.is_holiday(test_date)
        print(f"{test_date}: 휴장일 {'예' if is_holiday else '아니오'}")
    
    # ISO 주 마지막 거래일 확인
    last_trading_day = holiday_provider.last_trading_day_of_iso_week(date(2025, 8, 22))
    print(f"이번 주 마지막 거래일: {last_trading_day}")
    
    # 월 마지막 거래일 확인
    last_trading_day_month = holiday_provider.last_trading_day_of_month(2025, 8)
    print(f"8월 마지막 거래일: {last_trading_day_month}")
    
    print()


async def test_trade_reporter():
    """거래 리포터 테스트"""
    print("=== 거래 리포터 테스트 ===")
    
    # 세션 시작
    trade_reporter.start_session()
    print("거래 세션 시작")
    
    # 테스트 거래 데이터 추가
    test_trades = [
        {
            'symbol': '005930',  # 삼성전자
            'action': 'BUY',
            'quantity': 10,
            'price': 70000,
            'amount': 700000,
            'commission': 105,
            'profit_loss': 0,
            'account_type': 'MOCK',
            'trading_mode': 'AUTO',
            'algorithm': 'Enhanced_DavidPaul_Trading'
        },
        {
            'symbol': '005930',  # 삼성전자
            'action': 'SELL',
            'quantity': 10,
            'price': 72000,
            'amount': 720000,
            'commission': 108 + 1656,  # 수수료 + 세금
            'profit_loss': 18136,  # 20000 - 1864
            'account_type': 'MOCK',
            'trading_mode': 'AUTO',
            'algorithm': 'Enhanced_DavidPaul_Trading'
        },
        {
            'symbol': '000660',  # SK하이닉스
            'action': 'BUY',
            'quantity': 5,
            'price': 120000,
            'amount': 600000,
            'commission': 90,
            'profit_loss': 0,
            'account_type': 'MOCK',
            'trading_mode': 'AUTO',
            'algorithm': 'Enhanced_DavidPaul_Trading'
        }
    ]
    
    for trade in test_trades:
        trade_reporter.add_trade(trade)
        print(f"거래 기록 추가: {trade['symbol']} {trade['action']} {trade['quantity']}주")
    
    # 세션 종료 및 리포트 생성
    initial_balance = 100000000  # 1억원
    final_balance = 100018136    # 수익 반영
    
    trade_reporter.end_session(initial_balance, final_balance)
    print(f"거래 세션 종료 및 리포트 생성 완료")
    print()


async def test_reporting_integration():
    """리포팅 통합 테스트"""
    print("=== 리포팅 통합 테스트 ===")
    
    # 세션 시작
    success = await reporting_integration.start_trading_session('MOCK')
    print(f"통합 세션 시작: {success}")
    
    # 매수 주문 기록
    await log_buy_order(
        symbol='035420',  # NAVER
        quantity=3,
        price=200000,
        algorithm='Enhanced_DavidPaul_Trading',
        account_type='MOCK'
    )
    print("매수 주문 기록 완료: NAVER 3주")
    
    # 매도 주문 기록
    await log_sell_order(
        symbol='035420',  # NAVER
        quantity=3,
        price=210000,
        buy_price=200000,
        algorithm='Enhanced_DavidPaul_Trading',
        account_type='MOCK'
    )
    print("매도 주문 기록 완료: NAVER 3주 (수익)")
    
    # 세션 종료
    success = await reporting_integration.end_trading_session('MOCK')
    print(f"통합 세션 종료: {success}")
    
    # 리포팅 상태 확인
    status = reporting_integration.is_report_generation_day()
    print(f"리포트 생성 시점 정보: {status}")
    print()


async def test_report_files():
    """생성된 리포트 파일 확인"""
    print("=== 생성된 리포트 파일 확인 ===")
    
    report_dir = Path("Report")
    if not report_dir.exists():
        print("Report 디렉토리가 존재하지 않습니다.")
        return
    
    # 생성된 파일 목록
    report_files = list(report_dir.glob("*.json")) + list(report_dir.glob("*.html"))
    
    if report_files:
        print("생성된 리포트 파일들:")
        for file_path in sorted(report_files):
            file_size = file_path.stat().st_size
            print(f"  {file_path.name} ({file_size:,} bytes)")
        
        # 최신 JSON 파일 내용 확인
        json_files = sorted(report_dir.glob("session_*.json"))
        if json_files:
            latest_json = json_files[-1]
            with open(latest_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"\n최신 리포트 요약 ({latest_json.name}):")
            summary = data.get('summary', {})
            print(f"  총 거래 수: {summary.get('total_trades', 0)}")
            print(f"  총 손익: {summary.get('total_profit_loss', 0):,.0f}원")
            print(f"  승률: {summary.get('win_rate', 0):.1f}%")
    else:
        print("생성된 리포트 파일이 없습니다.")
    
    print()


async def main():
    """전체 테스트 실행"""
    print("tideWise 리포팅 시스템 종합 테스트 시작\n")
    
    try:
        await test_holiday_provider()
        await test_trade_reporter()
        await test_reporting_integration()
        await test_report_files()
        
        print("모든 테스트가 성공적으로 완료되었습니다!")
        
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())