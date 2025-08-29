"""
tideWise 거래 리포트 생성기
세션별/주간/월간 리포트 자동 생성
"""
import json
import os
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import pytz
import logging
from dataclasses import dataclass, asdict
from .holiday_provider import holiday_provider

@dataclass
class TradeRecord:
    """개별 거래 기록"""
    timestamp: str
    symbol: str
    action: str  # BUY/SELL
    quantity: int
    price: float
    amount: float
    commission: float
    profit_loss: float
    account_type: str  # MOCK/REAL
    trading_mode: str  # AUTO/DAY
    algorithm: str

@dataclass
class SessionSummary:
    """세션 요약 정보"""
    session_start: str
    session_end: str
    total_trades: int
    total_profit_loss: float
    total_commission: float
    win_trades: int
    lose_trades: int
    win_rate: float
    largest_win: float
    largest_loss: float
    account_balance_start: float
    account_balance_end: float

class TradeReporter:
    """거래 리포트 생성 및 관리"""
    
    def __init__(self):
        self.seoul_tz = pytz.timezone('Asia/Seoul')
        self.report_base_dir = Path("Report")
        self.report_base_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.current_session_trades: List[TradeRecord] = []
        self.session_start_time = None
        self.report_dir = None  # 날짜별 폴더
        
    def start_session(self):
        """거래 세션 시작"""
        self.session_start_time = datetime.now(self.seoul_tz)
        self.current_session_trades.clear()
        self.logger.info(f"거래 세션 시작: {self.session_start_time}")
    
    def add_trade(self, trade_data: Dict[str, Any]):
        """거래 기록 추가"""
        try:
            trade = TradeRecord(
                timestamp=datetime.now(self.seoul_tz).isoformat(),
                symbol=trade_data.get('symbol', ''),
                action=trade_data.get('action', ''),
                quantity=trade_data.get('quantity', 0),
                price=trade_data.get('price', 0.0),
                amount=trade_data.get('amount', 0.0),
                commission=trade_data.get('commission', 0.0),
                profit_loss=trade_data.get('profit_loss', 0.0),
                account_type=trade_data.get('account_type', 'MOCK'),
                trading_mode=trade_data.get('trading_mode', 'AUTO'),
                algorithm=trade_data.get('algorithm', 'Unknown')
            )
            
            self.current_session_trades.append(trade)
            self.logger.info(f"거래 기록 추가: {trade.symbol} {trade.action} {trade.quantity}주")
            
        except Exception as e:
            self.logger.error(f"거래 기록 추가 실패: {e}")
    
    def end_session(self, account_balance_start: float, account_balance_end: float):
        """거래 세션 종료 및 리포트 생성"""
        if not self.session_start_time:
            self.logger.warning("세션이 시작되지 않았습니다")
            return
        
        session_end_time = datetime.now(self.seoul_tz)
        
        # 세션 요약 계산
        summary = self._calculate_session_summary(
            self.session_start_time, 
            session_end_time,
            account_balance_start,
            account_balance_end
        )
        
        # 세션 리포트 생성
        today_str = session_end_time.date().strftime('%Y-%m-%d')
        self._generate_session_report(summary, today_str)
        
        # 주간/월간 리포트 체크
        self._check_periodic_reports(session_end_time.date())
        
        # 세션 초기화
        self.current_session_trades.clear()
        self.session_start_time = None
        
        self.logger.info(f"거래 세션 종료: {session_end_time}")
    
    def _calculate_session_summary(self, start_time: datetime, end_time: datetime,
                                  balance_start: float, balance_end: float) -> SessionSummary:
        """세션 요약 정보 계산"""
        total_profit_loss = sum(trade.profit_loss for trade in self.current_session_trades)
        total_commission = sum(trade.commission for trade in self.current_session_trades)
        
        win_trades = len([t for t in self.current_session_trades if t.profit_loss > 0])
        lose_trades = len([t for t in self.current_session_trades if t.profit_loss < 0])
        total_trades = len(self.current_session_trades)
        
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
        
        profit_losses = [t.profit_loss for t in self.current_session_trades]
        largest_win = max(profit_losses) if profit_losses else 0
        largest_loss = min(profit_losses) if profit_losses else 0
        
        return SessionSummary(
            session_start=start_time.isoformat(),
            session_end=end_time.isoformat(),
            total_trades=total_trades,
            total_profit_loss=total_profit_loss,
            total_commission=total_commission,
            win_trades=win_trades,
            lose_trades=lose_trades,
            win_rate=win_rate,
            largest_win=largest_win,
            largest_loss=largest_loss,
            account_balance_start=balance_start,
            account_balance_end=balance_end
        )
    
    def _generate_session_report(self, summary: SessionSummary, date_str: str):
        """세션 리포트 생성 (JSON + HTML)"""
        # 날짜별 폴더 생성
        self.report_dir = self.report_base_dir / date_str
        self.report_dir.mkdir(exist_ok=True)
        
        # JSON 리포트
        json_file = self.report_dir / f"session.json"
        json_data = {
            'summary': asdict(summary),
            'trades': [asdict(trade) for trade in self.current_session_trades],
            'generated_at': datetime.now(self.seoul_tz).isoformat()
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        # HTML 리포트
        html_file = self.report_dir / f"session.html"
        html_content = self._generate_session_html(summary, date_str)
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.logger.info(f"세션 리포트 생성 완료: {json_file}, {html_file}")
    
    def _generate_session_html(self, summary: SessionSummary, date_str: str) -> str:
        """세션 HTML 리포트 생성"""
        # 과거 1년 데이터 기반 차트 생성
        from .historical_chart_generator import chart_generator
        from datetime import datetime
        
        # 차트 데이터 준비
        chart_data = self._prepare_chart_data()
        
        # 과거 1년 데이터 로드
        current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        historical_data = chart_generator.load_historical_data(current_date)
        
        # 현재 세션 정보
        current_session = {
            'total_profit_loss': summary.total_profit_loss,
            'win_rate': summary.win_rate,
            'total_trades': summary.total_trades
        }
        
        # 과거 데이터 기반 차트 HTML 생성
        advanced_charts = chart_generator.generate_chart_html(current_session, historical_data)
        
        html_template = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>tideWise 세션 리포트 - {date_str}</title>
    <link rel="stylesheet" href="../support/Report4Css_new.css">
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>tideWise 거래 세션 리포트</h1>
            <h2>{date_str}</h2>
        </div>
        
        <div class="summary-grid">
            <div class="summary-card">
                <h3>총 거래 수</h3>
                <div style="font-size: 24px; font-weight: bold;">{summary.total_trades}</div>
            </div>
            <div class="summary-card">
                <h3>총 손익</h3>
                <div style="font-size: 24px; font-weight: bold;" class="{'positive' if summary.total_profit_loss >= 0 else 'negative'}">
                    {summary.total_profit_loss:,.0f}원
                </div>
            </div>
            <div class="summary-card">
                <h3>승률</h3>
                <div style="font-size: 24px; font-weight: bold;">{summary.win_rate:.1f}%</div>
            </div>
            <div class="summary-card">
                <h3>최대 수익</h3>
                <div style="font-size: 24px; font-weight: bold;" class="positive">{summary.largest_win:,.0f}원</div>
            </div>
            <div class="summary-card">
                <h3>최대 손실</h3>
                <div style="font-size: 24px; font-weight: bold;" class="negative">{summary.largest_loss:,.0f}원</div>
            </div>
            <div class="summary-card">
                <h3>수수료</h3>
                <div style="font-size: 24px; font-weight: bold;">{summary.total_commission:,.0f}원</div>
            </div>
        </div>
        
        <div class="chart-container">
            <h3>일일 손익 차트</h3>
            <canvas id="sessionPnlChart" width="800" height="300"></canvas>
        </div>
        
        <div class="chart-container">
            <h3>누적 손익 차트</h3>
            <canvas id="sessionCumulativeChart" width="800" height="300"></canvas>
        </div>
        
        {advanced_charts}
        
        <h3>거래 내역</h3>
        <table class="trades-table">
            <thead>
                <tr>
                    <th>시간</th>
                    <th>종목</th>
                    <th>매매</th>
                    <th>수량</th>
                    <th>가격</th>
                    <th>손익</th>
                    <th>알고리즘</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f"<tr><td>{trade.timestamp[11:19]}</td><td>{trade.symbol}</td><td>{trade.action}</td><td>{trade.quantity:,}</td><td>{trade.price:,.0f}</td><td class=\"{'positive' if trade.profit_loss >= 0 else 'negative'}\">{trade.profit_loss:,.0f}</td><td>{trade.algorithm}</td></tr>" for trade in self.current_session_trades])}
            </tbody>
        </table>
    </div>
    
    <script>
        {self._generate_chart_javascript(chart_data)}
    </script>
</body>
</html>
        """
        
        return html_template
    
    def _prepare_chart_data(self) -> Dict[str, Any]:
        """차트 데이터 준비"""
        if not self.current_session_trades:
            return {'labels': [], 'pnl_data': [], 'cumulative_data': []}
        
        # 시간별 손익 집계
        hourly_pnl = {}
        cumulative_pnl = 0
        
        for trade in self.current_session_trades:
            hour = trade.timestamp[11:13]  # HH 추출
            if hour not in hourly_pnl:
                hourly_pnl[hour] = 0
            hourly_pnl[hour] += trade.profit_loss
        
        labels = sorted(hourly_pnl.keys())
        pnl_data = [hourly_pnl[hour] for hour in labels]
        
        # 누적 손익 계산
        cumulative_data = []
        cumulative = 0
        for pnl in pnl_data:
            cumulative += pnl
            cumulative_data.append(cumulative)
        
        return {
            'labels': labels,
            'pnl_data': pnl_data,
            'cumulative_data': cumulative_data
        }
    
    def _generate_chart_javascript(self, chart_data: Dict[str, Any]) -> str:
        """차트 JavaScript 코드 생성"""
        return f"""
        // 일일 손익 차트
        const pnlCanvas = document.getElementById('sessionPnlChart');
        const pnlCtx = pnlCanvas.getContext('2d');
        
        const labels = {chart_data['labels']};
        const pnlData = {chart_data['pnl_data']};
        const cumulativeData = {chart_data['cumulative_data']};
        
        // 세션 바 차트 그리기 (함수명 변경)
        function drawSessionBarChart(ctx, data, width, height) {{
            const barWidth = width / Math.max(data.length, 1);
            const maxVal = data.length > 0 ? Math.max(...data.map(Math.abs)) : 1;
            
            ctx.clearRect(0, 0, width, height);
            
            if (data.length === 0) {{
                // 데이터가 없을 때 메시지 표시
                ctx.fillStyle = '#666';
                ctx.font = '16px Arial';
                ctx.textAlign = 'center';
                ctx.fillText('데이터가 없습니다', width/2, height/2);
                return;
            }}
            
            // 축 그리기
            ctx.strokeStyle = '#000';
            ctx.beginPath();
            ctx.moveTo(0, height/2);
            ctx.lineTo(width, height/2);
            ctx.stroke();
            
            // 바 그리기
            data.forEach((val, i) => {{
                const barHeight = (Math.abs(val) / maxVal) * (height/2 - 20);
                const x = i * barWidth;
                const y = val >= 0 ? height/2 - barHeight : height/2;
                
                ctx.fillStyle = val >= 0 ? '#28a745' : '#dc3545';
                ctx.fillRect(x + 2, y, barWidth - 4, barHeight);
                
                // 레이블 (시간대별)
                ctx.fillStyle = '#000';
                ctx.font = '12px Arial';
                ctx.textAlign = 'center';
                if (labels.length > i) {{
                    ctx.fillText(labels[i] + '시', x + barWidth/2, height - 5);
                }}
            }});
        }}
        
        // 세션 라인 차트 그리기 (함수명 변경 및 단일 데이터 처리)
        function drawSessionLineChart(ctx, data, width, height) {{
            ctx.clearRect(0, 0, width, height);
            
            if (data.length === 0) {{
                // 데이터가 없을 때 메시지 표시
                ctx.fillStyle = '#666';
                ctx.font = '16px Arial';
                ctx.textAlign = 'center';
                ctx.fillText('데이터가 없습니다', width/2, height/2);
                return;
            }}
            
            if (data.length === 1) {{
                // 단일 데이터 포인트 처리
                const maxVal = Math.abs(data[0]);
                const minVal = -maxVal;
                const range = maxVal * 2 || 1;
                
                // 중심선 그리기
                ctx.strokeStyle = '#ddd';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(50, height/2);
                ctx.lineTo(width - 50, height/2);
                ctx.stroke();
                
                // 단일 포인트 그리기
                const x = width / 2;
                const y = height / 2 - (data[0] / range) * (height - 80);
                
                ctx.fillStyle = '#007bff';
                ctx.beginPath();
                ctx.arc(x, y, 6, 0, 2 * Math.PI);
                ctx.fill();
                
                // 값 표시
                ctx.fillStyle = '#333';
                ctx.font = '14px Arial';
                ctx.textAlign = 'center';
                ctx.fillText(data[0].toLocaleString() + '원', x, y - 15);
                return;
            }}
            
            // 다중 데이터 처리
            const pointWidth = (width - 100) / (data.length - 1);
            const maxVal = Math.max(...data);
            const minVal = Math.min(...data);
            const range = maxVal - minVal || 1;
            
            ctx.strokeStyle = '#007bff';
            ctx.lineWidth = 2;
            ctx.beginPath();
            
            data.forEach((val, i) => {{
                const x = 50 + i * pointWidth;
                const y = 50 + (height - 100) - ((val - minVal) / range) * (height - 100);
                
                if (i === 0) {{
                    ctx.moveTo(x, y);
                }} else {{
                    ctx.lineTo(x, y);
                }}
            }});
            
            ctx.stroke();
            
            // 포인트 그리기
            ctx.fillStyle = '#007bff';
            data.forEach((val, i) => {{
                const x = 50 + i * pointWidth;
                const y = 50 + (height - 100) - ((val - minVal) / range) * (height - 100);
                ctx.beginPath();
                ctx.arc(x, y, 3, 0, 2 * Math.PI);
                ctx.fill();
            }});
        }}
        
        drawSessionBarChart(pnlCtx, pnlData, 800, 300);
        
        const cumulativeCanvas = document.getElementById('sessionCumulativeChart');
        const cumulativeCtx = cumulativeCanvas.getContext('2d');
        drawSessionLineChart(cumulativeCtx, cumulativeData, 800, 300);
        """
    
    def _check_periodic_reports(self, current_date: date):
        """주간/월간 리포트 생성 시점 확인"""
        # 주간 리포트 확인
        last_trading_day_of_week = holiday_provider.last_trading_day_of_iso_week(current_date)
        if current_date == last_trading_day_of_week:
            self._generate_weekly_report(current_date)
        
        # 월간 리포트 확인
        last_trading_day_of_month = holiday_provider.last_trading_day_of_month(
            current_date.year, current_date.month
        )
        if current_date == last_trading_day_of_month:
            self._generate_monthly_report(current_date)
    
    def _generate_weekly_report(self, report_date: date):
        """주간 통합 리포트 생성"""
        try:
            # 해당 주의 세션 리포트들 수집
            week_start = report_date - timedelta(days=report_date.weekday())
            week_sessions = []
            
            for i in range(7):
                check_date = week_start + timedelta(days=i)
                date_folder = self.report_base_dir / check_date.strftime('%Y-%m-%d')
                session_file = date_folder / "session.json"
                
                if session_file.exists():
                    with open(session_file, 'r', encoding='utf-8') as f:
                        week_sessions.append(json.load(f))
            
            if not week_sessions:
                return
            
            # 주간 요약 계산
            weekly_summary = self._calculate_period_summary(week_sessions, 'weekly')
            
            # 리포트 생성
            date_str = report_date.strftime('%Y-%m-%d')
            self._generate_period_report(weekly_summary, week_sessions, date_str, 'weekly')
            
            self.logger.info(f"주간 리포트 생성 완료: {date_str}")
            
        except Exception as e:
            self.logger.error(f"주간 리포트 생성 실패: {e}")
    
    def _generate_monthly_report(self, report_date: date):
        """월간 통합 리포트 생성"""
        try:
            # 해당 월의 세션 리포트들 수집
            month_sessions = []
            month_start = date(report_date.year, report_date.month, 1)
            
            current = month_start
            while current.month == report_date.month:
                date_folder = self.report_base_dir / current.strftime('%Y-%m-%d')
                session_file = date_folder / "session.json"
                
                if session_file.exists():
                    with open(session_file, 'r', encoding='utf-8') as f:
                        month_sessions.append(json.load(f))
                
                current += timedelta(days=1)
            
            if not month_sessions:
                return
            
            # 월간 요약 계산
            monthly_summary = self._calculate_period_summary(month_sessions, 'monthly')
            
            # 리포트 생성
            date_str = report_date.strftime('%Y-%m-%d')
            self._generate_period_report(monthly_summary, month_sessions, date_str, 'monthly')
            
            self.logger.info(f"월간 리포트 생성 완료: {date_str}")
            
        except Exception as e:
            self.logger.error(f"월간 리포트 생성 실패: {e}")
    
    def _calculate_period_summary(self, sessions: List[Dict], period_type: str) -> Dict[str, Any]:
        """기간별 요약 계산"""
        total_trades = sum(len(session['trades']) for session in sessions)
        total_profit_loss = sum(session['summary']['total_profit_loss'] for session in sessions)
        total_commission = sum(session['summary']['total_commission'] for session in sessions)
        
        win_sessions = len([s for s in sessions if s['summary']['total_profit_loss'] > 0])
        lose_sessions = len([s for s in sessions if s['summary']['total_profit_loss'] < 0])
        
        win_rate = (win_sessions / len(sessions) * 100) if sessions else 0
        
        return {
            'period_type': period_type,
            'total_sessions': len(sessions),
            'total_trades': total_trades,
            'total_profit_loss': total_profit_loss,
            'total_commission': total_commission,
            'win_sessions': win_sessions,
            'lose_sessions': lose_sessions,
            'session_win_rate': win_rate
        }
    
    def _generate_period_report(self, summary: Dict[str, Any], sessions: List[Dict], 
                               date_str: str, period_type: str):
        """기간별 리포트 생성 (JSON + HTML)"""
        # 날짜별 폴더 사용
        report_folder = self.report_base_dir / date_str
        report_folder.mkdir(exist_ok=True)
        
        # JSON 리포트
        json_file = report_folder / f"{period_type}.json"
        json_data = {
            'summary': summary,
            'sessions': sessions,
            'generated_at': datetime.now(self.seoul_tz).isoformat()
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        # HTML 리포트
        html_file = report_folder / f"{period_type}.html"
        html_content = self._generate_period_html(summary, sessions, date_str, period_type)
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _generate_period_html(self, summary: Dict[str, Any], sessions: List[Dict], 
                             date_str: str, period_type: str) -> str:
        """기간별 HTML 리포트 생성"""
        period_name = "주간" if period_type == "weekly" else "월간"
        
        html_template = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>tideWise {period_name} 리포트 - {date_str}</title>
    <link rel="stylesheet" href="../support/Report4Css_new.css">
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>tideWise {period_name} 통합 리포트</h1>
            <h2>{date_str}</h2>
        </div>
        
        <div class="summary-grid">
            <div class="summary-card">
                <h3>총 세션 수</h3>
                <div style="font-size: 24px; font-weight: bold;">{summary['total_sessions']}</div>
            </div>
            <div class="summary-card">
                <h3>총 거래 수</h3>
                <div style="font-size: 24px; font-weight: bold;">{summary['total_trades']}</div>
            </div>
            <div class="summary-card">
                <h3>총 손익</h3>
                <div style="font-size: 24px; font-weight: bold;" class="{'positive' if summary['total_profit_loss'] >= 0 else 'negative'}">
                    {summary['total_profit_loss']:,.0f}원
                </div>
            </div>
            <div class="summary-card">
                <h3>세션 승률</h3>
                <div style="font-size: 24px; font-weight: bold;">{summary['session_win_rate']:.1f}%</div>
            </div>
            <div class="summary-card">
                <h3>수익 세션</h3>
                <div style="font-size: 24px; font-weight: bold;" class="positive">{summary['win_sessions']}</div>
            </div>
            <div class="summary-card">
                <h3>손실 세션</h3>
                <div style="font-size: 24px; font-weight: bold;" class="negative">{summary['lose_sessions']}</div>
            </div>
        </div>
        
        <h3>세션별 요약</h3>
        <table class="sessions-table">
            <thead>
                <tr>
                    <th>날짜</th>
                    <th>거래 수</th>
                    <th>손익</th>
                    <th>승률</th>
                    <th>수수료</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f"<tr><td>{session['summary']['session_start'][:10]}</td><td>{session['summary']['total_trades']}</td><td class=\"{'positive' if session['summary']['total_profit_loss'] >= 0 else 'negative'}\">{session['summary']['total_profit_loss']:,.0f}원</td><td>{session['summary']['win_rate']:.1f}%</td><td>{session['summary']['total_commission']:,.0f}원</td></tr>" for session in sessions])}
            </tbody>
        </table>
    </div>
</body>
</html>
        """
        
        return html_template


# 전역 인스턴스
trade_reporter = TradeReporter()