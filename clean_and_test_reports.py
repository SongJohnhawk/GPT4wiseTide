"""
리포트 디렉토리 정리 및 새 구조로 테스트
날짜별 폴더 구조로 재구성
"""
import os
import shutil
from pathlib import Path
from datetime import datetime
import json

def clean_old_reports():
    """기존 JSON 파일들 정리"""
    report_dir = Path("Report")
    
    if not report_dir.exists():
        print("Report 디렉토리가 없습니다.")
        return
    
    # 기존 JSON/HTML 파일들 찾기
    old_files = list(report_dir.glob("session_*.json")) + \
                list(report_dir.glob("session_*.html")) + \
                list(report_dir.glob("weekly_*.json")) + \
                list(report_dir.glob("weekly_*.html")) + \
                list(report_dir.glob("monthly_*.json")) + \
                list(report_dir.glob("monthly_*.html"))
    
    if old_files:
        print(f"기존 리포트 파일 {len(old_files)}개 발견")
        
        # 백업 폴더 생성
        backup_dir = report_dir / "_backup_old_structure"
        backup_dir.mkdir(exist_ok=True)
        
        # 파일 이동
        for file_path in old_files:
            target = backup_dir / file_path.name
            shutil.move(str(file_path), str(target))
            print(f"  이동: {file_path.name} -> _backup_old_structure/")
        
        print(f"총 {len(old_files)}개 파일을 백업 폴더로 이동했습니다.")
    else:
        print("정리할 기존 파일이 없습니다.")
    
    # 날짜별 폴더 있으면 유지
    date_folders = [d for d in report_dir.iterdir() if d.is_dir() and not d.name.startswith('_')]
    if date_folders:
        print(f"날짜별 폴더 {len(date_folders)}개 유지")


def test_new_structure():
    """새 구조로 샘플 리포트 생성"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    from support.trade_reporter import trade_reporter
    
    print("\n새 구조로 샘플 리포트 생성 테스트")
    
    # 세션 시작
    trade_reporter.start_session()
    
    # 테스트 거래 추가
    test_trades = [
        {
            'symbol': '005930',
            'action': 'BUY',
            'quantity': 10,
            'price': 71000,
            'amount': 710000,
            'commission': 106,
            'profit_loss': 0,
            'account_type': 'MOCK',
            'trading_mode': 'AUTO',
            'algorithm': 'Test_Algorithm'
        },
        {
            'symbol': '005930',
            'action': 'SELL',
            'quantity': 10,
            'price': 72500,
            'amount': 725000,
            'commission': 1777,
            'profit_loss': 13117,
            'account_type': 'MOCK',
            'trading_mode': 'AUTO',
            'algorithm': 'Test_Algorithm'
        }
    ]
    
    for trade in test_trades:
        trade_reporter.add_trade(trade)
    
    # 세션 종료
    trade_reporter.end_session(100000000, 100013117)
    
    # 생성된 파일 확인
    today_str = datetime.now().strftime('%Y-%m-%d')
    report_folder = Path("Report") / today_str
    
    if report_folder.exists():
        print(f"\n날짜별 폴더 생성 확인: Report/{today_str}/")
        
        files = list(report_folder.glob("*"))
        for file_path in files:
            size = file_path.stat().st_size
            print(f"  - {file_path.name} ({size:,} bytes)")
        
        # HTML 파일 내용 확인
        html_file = report_folder / "session.html"
        if html_file.exists():
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 차트 ID 확인
            chart_ids = [
                'sessionPnlChart',
                'sessionCumulativeChart', 
                'historicalCumulativeChart',
                'dailyPnlChart',
                'winRateChart',
                'portfolioChart'
            ]
            
            print("\n차트 ID 검증:")
            for chart_id in chart_ids:
                if chart_id in content:
                    print(f"  [OK] {chart_id} 존재")
                else:
                    print(f"  [X] {chart_id} 없음")
        
        print(f"\n[완료] 새 구조 테스트 완료!")
        print(f"브라우저에서 확인: Report/{today_str}/session.html")
    else:
        print("리포트 폴더 생성 실패")


def main():
    print("=" * 60)
    print("리포트 구조 재구성")
    print("=" * 60)
    
    # 1. 기존 파일 정리
    clean_old_reports()
    
    # 2. 새 구조 테스트
    test_new_structure()
    
    print("\n" + "=" * 60)
    print("완료! 날짜별 폴더 구조로 재구성되었습니다.")
    print("=" * 60)


if __name__ == "__main__":
    main()