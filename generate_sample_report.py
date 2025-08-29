"""
tideWise 가상 매매 데이터 샘플 리포트 생성
실제 매매 시뮬레이션 데이터로 JSON/HTML 리포트 생성
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random
import json

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.trade_reporter import trade_reporter
from support.holiday_provider import holiday_provider


def generate_virtual_trades():
    """가상 매매 데이터 생성 (실제 같은 시나리오)"""
    
    # 한국 주요 종목들
    stocks = [
        {'code': '005930', 'name': '삼성전자', 'base_price': 70000},
        {'code': '000660', 'name': 'SK하이닉스', 'base_price': 120000},
        {'code': '035420', 'name': 'NAVER', 'base_price': 200000},
        {'code': '051910', 'name': 'LG화학', 'base_price': 450000},
        {'code': '005380', 'name': '현대차', 'base_price': 180000},
        {'code': '035720', 'name': '카카오', 'base_price': 45000},
        {'code': '207940', 'name': '삼성바이오로직스', 'base_price': 800000},
        {'code': '006400', 'name': '삼성SDI', 'base_price': 400000},
        {'code': '068270', 'name': '셀트리온', 'base_price': 150000},
        {'code': '003670', 'name': '포스코퓨처엠', 'base_price': 280000}
    ]
    
    trades = []
    buy_history = {}  # 매수 이력 저장
    
    # 09:00 ~ 15:20 거래 시뮬레이션
    start_time = datetime(2025, 8, 23, 9, 0, 0)
    current_time = start_time
    
    while current_time.hour < 15 or (current_time.hour == 15 and current_time.minute < 20):
        # 30% 확률로 거래 발생
        if random.random() < 0.3:
            stock = random.choice(stocks)
            
            # 매수/매도 결정
            if stock['code'] not in buy_history or random.random() < 0.4:
                # 매수
                quantity = random.randint(1, 10)
                price_variation = random.uniform(0.98, 1.02)
                buy_price = int(stock['base_price'] * price_variation)
                
                trade = {
                    'timestamp': current_time.isoformat(),
                    'symbol': stock['code'],
                    'name': stock['name'],
                    'action': 'BUY',
                    'quantity': quantity,
                    'price': buy_price,
                    'amount': buy_price * quantity,
                    'commission': int(buy_price * quantity * 0.00015),
                    'profit_loss': 0,
                    'account_type': 'MOCK',
                    'trading_mode': random.choice(['AUTO', 'DAY']),
                    'algorithm': random.choice(['Enhanced_DavidPaul_Trading', 'SurgeDetector_v2', 'MomentumBreaker'])
                }
                
                if stock['code'] not in buy_history:
                    buy_history[stock['code']] = []
                buy_history[stock['code']].append({
                    'quantity': quantity,
                    'price': buy_price
                })
                
                trades.append(trade)
                
            else:
                # 매도
                if buy_history[stock['code']]:
                    buy_info = buy_history[stock['code']].pop(0)
                    quantity = buy_info['quantity']
                    buy_price = buy_info['price']
                    
                    # 60% 확률로 수익, 40% 확률로 손실
                    if random.random() < 0.6:
                        price_variation = random.uniform(1.01, 1.07)  # 1~7% 수익
                    else:
                        price_variation = random.uniform(0.95, 0.99)  # 1~5% 손실
                    
                    sell_price = int(buy_price * price_variation)
                    amount = sell_price * quantity
                    commission = int(amount * 0.00015 + amount * 0.0023)  # 수수료 + 세금
                    profit_loss = amount - (buy_price * quantity) - commission
                    
                    trade = {
                        'timestamp': current_time.isoformat(),
                        'symbol': stock['code'],
                        'name': stock['name'],
                        'action': 'SELL',
                        'quantity': quantity,
                        'price': sell_price,
                        'amount': amount,
                        'commission': commission,
                        'profit_loss': profit_loss,
                        'account_type': 'MOCK',
                        'trading_mode': random.choice(['AUTO', 'DAY']),
                        'algorithm': random.choice(['Enhanced_DavidPaul_Trading', 'SurgeDetector_v2', 'MomentumBreaker'])
                    }
                    
                    trades.append(trade)
        
        # 시간 진행 (5~15분 간격)
        current_time += timedelta(minutes=random.randint(5, 15))
    
    return trades


def main():
    print("tideWise 가상 매매 리포트 생성 시작")
    
    # Report 디렉토리 생성
    report_dir = Path("Report")
    report_dir.mkdir(exist_ok=True)
    
    # 세션 시작
    trade_reporter.start_session()
    print("거래 세션 시작")
    
    # 가상 매매 데이터 생성
    virtual_trades = generate_virtual_trades()
    print(f"가상 거래 데이터 {len(virtual_trades)}건 생성")
    
    # 거래 기록 추가
    total_profit_loss = 0
    win_count = 0
    lose_count = 0
    
    for trade in virtual_trades:
        trade_reporter.add_trade(trade)
        
        if trade['action'] == 'SELL':
            if trade['profit_loss'] > 0:
                win_count += 1
            else:
                lose_count += 1
            total_profit_loss += trade['profit_loss']
    
    # 세션 종료 및 리포트 생성
    initial_balance = 100000000  # 1억원
    final_balance = initial_balance + total_profit_loss
    
    trade_reporter.end_session(initial_balance, final_balance)
    
    # 결과 출력
    print("\n=== 가상 매매 결과 요약 ===")
    print(f"총 거래 수: {len(virtual_trades)}건")
    print(f"매수 거래: {len([t for t in virtual_trades if t['action'] == 'BUY'])}건")
    print(f"매도 거래: {len([t for t in virtual_trades if t['action'] == 'SELL'])}건")
    print(f"수익 거래: {win_count}건")
    print(f"손실 거래: {lose_count}건")
    
    if win_count + lose_count > 0:
        win_rate = (win_count / (win_count + lose_count)) * 100
        print(f"승률: {win_rate:.1f}%")
    
    print(f"총 손익: {total_profit_loss:,.0f}원")
    print(f"초기 잔고: {initial_balance:,.0f}원")
    print(f"최종 잔고: {final_balance:,.0f}원")
    print(f"수익률: {(total_profit_loss / initial_balance * 100):.2f}%")
    
    # 생성된 파일 확인
    today_str = datetime.now().strftime('%Y-%m-%d')
    json_file = report_dir / f"session_{today_str}.json"
    html_file = report_dir / f"session_{today_str}.html"
    
    print(f"\n=== 생성된 리포트 파일 ===")
    if json_file.exists():
        print(f"JSON: {json_file.absolute()} ({json_file.stat().st_size:,} bytes)")
    if html_file.exists():
        print(f"HTML: {html_file.absolute()} ({html_file.stat().st_size:,} bytes)")
    
    # JSON 파일 내용 미리보기
    if json_file.exists():
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n=== JSON 리포트 미리보기 ===")
        summary = data['summary']
        print(f"세션 시작: {summary['session_start'][11:19]}")
        print(f"세션 종료: {summary['session_end'][11:19]}")
        print(f"총 거래: {summary['total_trades']}건")
        print(f"총 손익: {summary['total_profit_loss']:,.0f}원")
        print(f"승률: {summary['win_rate']:.1f}%")
        
        # 거래 내역 샘플 (처음 3개)
        print(f"\n거래 내역 샘플 (처음 3개):")
        for i, trade in enumerate(data['trades'][:3], 1):
            print(f"{i}. {trade['timestamp'][11:19]} {trade['symbol']} {trade['action']} {trade['quantity']}주 @ {trade['price']:,}원")
    
    print("\n가상 매매 리포트 생성 완료!")


if __name__ == "__main__":
    main()