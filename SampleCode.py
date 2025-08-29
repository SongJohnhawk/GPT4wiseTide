import pandas as pd
from pykrx import stock
import time
from datetime import datetime, time as dt_time

def get_target_stocks():
    """
    관심 대상 종목을 선정하는 함수
    - 코스피, 코스닥 전 종목 대상
    - 전일 대비 거래량 급증 및 상승 추세 종목 필터링
    """
    print("관심 대상 종목을 탐색합니다...")
    tickers = stock.get_market_ticker_list()
    target_stocks = []

    for ticker in tickers:
        try:
            # 21일치 데이터 조회 (20일 이평선 계산 위함)
            df = stock.get_market_ohlcv_by_date(
                fromdate="20250701", # 실제 사용 시에는 최근 날짜로 변경 필요
                todate="20250822",   # 실제 사용 시에는 오늘 날짜로 변경 필요
                ticker=ticker
            )

            if len(df) < 20:
                continue

            # 이동평균선 계산
            df['ma5'] = df['종가'].rolling(window=5).mean()
            df['ma20'] = df['종가'].rolling(window=20).mean()

            # 최신 데이터 (오늘)
            today = df.iloc[-1]
            # 어제 데이터
            yesterday = df.iloc[-2]

            # 1. 거래량 조건: 오늘 거래량이 어제 거래량의 50%를 초과했는가?
            if today['거래량'] > yesterday['거래량'] * 0.5:
                # 2. 상승 추세 조건: 오늘 종가가 5일선과 20일선 위에 있는가?
                if today['종가'] > today['ma5'] and today['종가'] > today['ma20']:
                    print(f"관심 종목 발견: {stock.get_market_ticker_name(ticker)} ({ticker})")
                    target_stocks.append({
                        'ticker': ticker,
                        'name': stock.get_market_ticker_name(ticker),
                        'entry_price': today['고가'] # 돌파 기준 가격
                    })
            time.sleep(0.1) # 서버 부하 방지
        except Exception as e:
            print(f"{ticker} 처리 중 오류 발생: {e}")
            continue
            
    return target_stocks


def run_trading_bot():
    """
    자동매매 봇을 실행하는 메인 함수
    """
    # 가상 계좌 정보
    balance = 1_000_000 # 초기 자본금 100만원
    portfolio = {} # 보유 종목
    
    # 한국 주식시장 정규 시간 (오전 9시 ~ 오후 3시 20분)
    market_open = dt_time(9, 0)
    market_close = dt_time(15, 20)

    # --- 장 시작 전, 관심 종목 선정 ---
    target_stocks = get_target_stocks()
    print("\n오늘의 관심 종목 리스트:")
    for stock_info in target_stocks:
        print(f"- {stock_info['name']} (매수 목표가: {stock_info['entry_price']})")
    
    print("\n--- 장 시작! 자동매매를 시작합니다. (가상매매) ---")

    while True:
        now = datetime.now().time()
        
        # 장 운영 시간 체크
        if not (market_open <= now <= market_close):
            print("장 마감 시간입니다. 프로그램을 종료합니다.")
            break

        # --- 실시간 감시 및 매매 로직 ---
        for stock_info in target_stocks:
            ticker = stock_info['ticker']
            
            try:
                # 현재가 조회
                current_price = stock.get_market_ohlcv_by_date(
                    fromdate="20250822", 
                    todate="20250822", 
                    ticker=ticker
                )['종가'].iloc[-1]

                # 1. 매수 조건 체크 (미보유 종목 대상)
                if ticker not in portfolio:
                    if current_price >= stock_info['entry_price']:
                        # 가상 매수
                        buy_qty = balance // current_price
                        if buy_qty > 0:
                            balance -= buy_qty * current_price
                            portfolio[ticker] = {
                                'name': stock_info['name'],
                                'buy_price': current_price,
                                'qty': buy_qty,
                                'target_price': current_price * 1.03, # +3% 익절 목표가
                                'stop_loss': current_price * 0.98   # -2% 손절가
                            }
                            print(f"🚀 [매수] {portfolio[ticker]['name']} / {buy_qty}주 / {current_price}원")
                
                # 2. 매도 조건 체크 (보유 종목 대상)
                else:
                    # 익절 조건
                    if current_price >= portfolio[ticker]['target_price']:
                        # 가상 매도
                        balance += portfolio[ticker]['qty'] * current_price
                        print(f"💰 [익절] {portfolio[ticker]['name']} / {portfolio[ticker]['qty']}주 / {current_price}원")
                        del portfolio[ticker]
                    # 손절 조건
                    elif current_price <= portfolio[ticker]['stop_loss']:
                        # 가상 매도
                        balance += portfolio[ticker]['qty'] * current_price
                        print(f"🛡️ [손절] {portfolio[ticker]['name']} / {portfolio[ticker]['qty']}주 / {current_price}원")
                        del portfolio[ticker]

                time.sleep(0.5) # 실시간 조회 부하 방지
            except Exception as e:
                print(f"{ticker} 실시간 처리 중 오류: {e}")
                continue

        time.sleep(5) # 5초마다 전체 종목 반복 감시

# --- 프로그램 시작 ---
if __name__ == "__main__":
    run_trading_bot()