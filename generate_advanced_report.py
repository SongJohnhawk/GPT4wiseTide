"""
tideWise 과거 1년 데이터 기반 고급 리포트 생성
실제 매매 시뮬레이션 + 과거 데이터 차트
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, date
import random
import json

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.trade_reporter import trade_reporter
from support.historical_chart_generator import chart_generator


def generate_one_year_historical_data():
    """1년치 과거 데이터 생성"""
    print("1년치 과거 데이터 생성 중...")
    
    report_dir = Path("Report")
    report_dir.mkdir(exist_ok=True)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=365)
    current_date = start_date
    
    # 한국 주요 종목들
    stocks = [
        {'code': '005930', 'name': '삼성전자', 'base_price': 70000},
        {'code': '000660', 'name': 'SK하이닉스', 'base_price': 120000},
        {'code': '035420', 'name': 'NAVER', 'base_price': 200000},
        {'code': '051910', 'name': 'LG화학', 'base_price': 450000},
        {'code': '005380', 'name': '현대차', 'base_price': 180000}
    ]
    
    generated_count = 0
    
    while current_date < end_date:
        # 주말 제외
        if current_date.weekday() < 5:
            # 세션 시작
            trade_reporter.session_start_time = datetime.combine(current_date, datetime.min.time()).replace(hour=9, minute=0)
            trade_reporter.current_session_trades.clear()
            
            # 하루 거래 생성 (10~30건)
            num_trades = random.randint(10, 30)
            total_profit_loss = 0
            
            for _ in range(num_trades):
                stock = random.choice(stocks)
                action = random.choice(['BUY', 'SELL'])
                quantity = random.randint(1, 10)
                
                # 가격 변동
                price_variation = random.uniform(0.95, 1.05)
                price = int(stock['base_price'] * price_variation)
                
                if action == 'SELL':
                    # 매도시 손익 계산
                    buy_price = int(stock['base_price'] * random.uniform(0.98, 1.02))
                    profit_loss = (price - buy_price) * quantity
                    total_profit_loss += profit_loss
                else:
                    profit_loss = 0
                
                trade_data = {
                    'symbol': stock['code'],
                    'action': action,
                    'quantity': quantity,
                    'price': price,
                    'amount': price * quantity,
                    'commission': int(price * quantity * 0.00015),
                    'profit_loss': profit_loss,
                    'account_type': 'MOCK',
                    'trading_mode': 'AUTO',
                    'algorithm': 'Historical_Simulation'
                }
                
                trade_reporter.add_trade(trade_data)
            
            # 세션 종료
            initial_balance = 100000000
            final_balance = initial_balance + total_profit_loss
            
            # 세션 종료 시간 설정
            trade_reporter.session_end_time = datetime.combine(current_date, datetime.min.time()).replace(hour=15, minute=30)
            
            # 리포트 생성
            summary = trade_reporter._calculate_session_summary(
                trade_reporter.session_start_time,
                trade_reporter.session_end_time,
                initial_balance,
                final_balance
            )
            
            date_str = current_date.strftime('%Y-%m-%d')
            
            # JSON만 생성 (HTML은 최종 리포트에서만)
            json_file = report_dir / f"session_{date_str}.json"
            json_data = {
                'summary': {
                    'session_start': summary.session_start,
                    'session_end': summary.session_end,
                    'total_trades': summary.total_trades,
                    'total_profit_loss': summary.total_profit_loss,
                    'total_commission': summary.total_commission,
                    'win_trades': summary.win_trades,
                    'lose_trades': summary.lose_trades,
                    'win_rate': summary.win_rate,
                    'largest_win': summary.largest_win,
                    'largest_loss': summary.largest_loss,
                    'account_balance_start': summary.account_balance_start,
                    'account_balance_end': summary.account_balance_end
                },
                'trades': [
                    {
                        'timestamp': trade.timestamp,
                        'symbol': trade.symbol,
                        'action': trade.action,
                        'quantity': trade.quantity,
                        'price': trade.price,
                        'amount': trade.amount,
                        'commission': trade.commission,
                        'profit_loss': trade.profit_loss,
                        'account_type': trade.account_type,
                        'trading_mode': trade.trading_mode,
                        'algorithm': trade.algorithm
                    } for trade in trade_reporter.current_session_trades
                ],
                'generated_at': datetime.now().isoformat()
            }
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            generated_count += 1
            
            # 진행 상황 표시
            if generated_count % 20 == 0:
                print(f"  {generated_count}개 거래일 데이터 생성 완료...")
        
        current_date += timedelta(days=1)
    
    print(f"총 {generated_count}개 거래일 데이터 생성 완료")
    return generated_count


def generate_today_report_with_history():
    """오늘 거래 + 과거 1년 데이터 차트 포함 리포트 생성"""
    print("\n오늘 거래 리포트 생성 (과거 1년 데이터 차트 포함)")
    
    # 세션 시작
    trade_reporter.start_session()
    
    # 오늘 거래 데이터 생성
    stocks = [
        {'code': '005930', 'name': '삼성전자', 'base_price': 71000},
        {'code': '035420', 'name': 'NAVER', 'base_price': 205000},
        {'code': '068270', 'name': '셀트리온', 'base_price': 155000}
    ]
    
    total_profit_loss = 0
    
    for i in range(15):  # 15건 거래
        stock = random.choice(stocks)
        
        if i % 3 == 0:  # 매수
            trade_data = {
                'symbol': stock['code'],
                'action': 'BUY',
                'quantity': random.randint(2, 8),
                'price': int(stock['base_price'] * random.uniform(0.99, 1.01)),
                'amount': 0,
                'commission': 0,
                'profit_loss': 0,
                'account_type': 'MOCK',
                'trading_mode': 'AUTO',
                'algorithm': 'Enhanced_DavidPaul_Trading'
            }
            trade_data['amount'] = trade_data['price'] * trade_data['quantity']
            trade_data['commission'] = int(trade_data['amount'] * 0.00015)
            
        else:  # 매도
            quantity = random.randint(2, 8)
            buy_price = int(stock['base_price'] * random.uniform(0.98, 1.02))
            sell_price = int(buy_price * random.uniform(0.97, 1.05))
            amount = sell_price * quantity
            commission = int(amount * (0.00015 + 0.0023))
            profit_loss = amount - (buy_price * quantity) - commission
            total_profit_loss += profit_loss
            
            trade_data = {
                'symbol': stock['code'],
                'action': 'SELL',
                'quantity': quantity,
                'price': sell_price,
                'amount': amount,
                'commission': commission,
                'profit_loss': profit_loss,
                'account_type': 'MOCK',
                'trading_mode': 'AUTO',
                'algorithm': 'Enhanced_DavidPaul_Trading'
            }
        
        trade_reporter.add_trade(trade_data)
    
    # 세션 종료 (과거 1년 데이터 차트 포함)
    initial_balance = 100000000
    final_balance = initial_balance + total_profit_loss
    
    trade_reporter.end_session(initial_balance, final_balance)
    
    print(f"총 손익: {total_profit_loss:,.0f}원")
    print(f"수익률: {(total_profit_loss / initial_balance * 100):.2f}%")
    
    # 생성된 파일 확인
    today_str = datetime.now().strftime('%Y-%m-%d')
    report_dir = Path("Report")
    json_file = report_dir / f"session_{today_str}.json"
    html_file = report_dir / f"session_{today_str}.html"
    
    print(f"\n생성된 리포트 파일:")
    if json_file.exists():
        print(f"  JSON: {json_file.absolute()} ({json_file.stat().st_size:,} bytes)")
    if html_file.exists():
        print(f"  HTML: {html_file.absolute()} ({html_file.stat().st_size:,} bytes)")
        print(f"\n  ✅ HTML 파일에 과거 1년 데이터 기반 차트가 포함되었습니다!")
        print(f"  ✅ 30일, 90일, 365일 기간별 차트 전환 가능")
        print(f"  ✅ 누적 손익, 일일 손익, 승률, 포트폴리오 가치 차트 포함")


def main():
    print("=" * 60)
    print("tideWise 과거 1년 데이터 기반 고급 리포트 생성")
    print("=" * 60)
    
    # 1. 과거 1년 데이터 생성
    generated_days = generate_one_year_historical_data()
    
    # 2. 오늘 리포트 생성 (과거 데이터 차트 포함)
    generate_today_report_with_history()
    
    print("\n" + "=" * 60)
    print("완료! Report 폴더에서 HTML 파일을 브라우저로 열어보세요.")
    print("=" * 60)


if __name__ == "__main__":
    main()