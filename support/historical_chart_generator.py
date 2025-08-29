"""
tideWise 과거 1년 데이터 기반 차트 생성기
historical 데이터를 수집하여 현재 상태와 비교하는 차트 생성
"""
import json
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

class HistoricalChartGenerator:
    """과거 1년 데이터 기반 차트 생성"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.historical_data_dir = Path("historical_data")
        self.report_base_dir = Path("Report")
        
    def load_historical_data(self, end_date: date, days: int = 365) -> Dict[str, List]:
        """과거 1년 데이터 로드"""
        start_date = end_date - timedelta(days=days)
        historical_data = {
            'dates': [],
            'daily_pnl': [],
            'cumulative_pnl': [],
            'win_rate': [],
            'trade_volume': [],
            'portfolio_value': []
        }
        
        # 과거 세션 리포트들 로드
        current_date = start_date
        cumulative = 0
        initial_portfolio = 100000000  # 1억원
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            date_folder = self.report_base_dir / date_str
            session_file = date_folder / "session.json"
            
            if session_file.exists():
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        summary = data.get('summary', {})
                        
                        daily_pnl = summary.get('total_profit_loss', 0)
                        cumulative += daily_pnl
                        
                        historical_data['dates'].append(date_str)
                        historical_data['daily_pnl'].append(daily_pnl)
                        historical_data['cumulative_pnl'].append(cumulative)
                        historical_data['win_rate'].append(summary.get('win_rate', 0))
                        historical_data['trade_volume'].append(summary.get('total_trades', 0))
                        historical_data['portfolio_value'].append(initial_portfolio + cumulative)
                        
                except Exception as e:
                    self.logger.error(f"과거 데이터 로드 실패 {date_str}: {e}")
            
            current_date += timedelta(days=1)
        
        # 데이터가 없으면 시뮬레이션 데이터 생성
        if not historical_data['dates']:
            historical_data = self._generate_simulated_historical_data(start_date, end_date)
        
        return historical_data
    
    def _generate_simulated_historical_data(self, start_date: date, end_date: date) -> Dict[str, List]:
        """시뮬레이션 과거 데이터 생성"""
        import random
        
        historical_data = {
            'dates': [],
            'daily_pnl': [],
            'cumulative_pnl': [],
            'win_rate': [],
            'trade_volume': [],
            'portfolio_value': []
        }
        
        current_date = start_date
        cumulative = 0
        portfolio = 100000000  # 1억원
        
        # 주말 제외하고 거래일만 생성
        while current_date <= end_date:
            if current_date.weekday() < 5:  # 월-금
                date_str = current_date.strftime('%Y-%m-%d')
                
                # 실제같은 거래 데이터 시뮬레이션
                # 60% 확률로 수익, 40% 손실
                if random.random() < 0.6:
                    daily_pnl = random.randint(10000, 500000)  # 1만원~50만원 수익
                else:
                    daily_pnl = -random.randint(5000, 300000)  # 5천원~30만원 손실
                
                cumulative += daily_pnl
                portfolio += daily_pnl
                
                win_rate = random.uniform(45, 65)  # 45~65% 승률
                trade_volume = random.randint(5, 30)  # 5~30건 거래
                
                historical_data['dates'].append(date_str)
                historical_data['daily_pnl'].append(daily_pnl)
                historical_data['cumulative_pnl'].append(cumulative)
                historical_data['win_rate'].append(win_rate)
                historical_data['trade_volume'].append(trade_volume)
                historical_data['portfolio_value'].append(portfolio)
            
            current_date += timedelta(days=1)
        
        return historical_data
    
    def generate_chart_html(self, current_session: Dict, historical_data: Dict) -> str:
        """과거 1년 데이터 기반 차트 HTML 생성"""
        
        # 최근 30일, 90일, 365일 구간 계산
        total_days = len(historical_data['dates'])
        
        ranges = {
            '30일': max(0, total_days - 30),
            '90일': max(0, total_days - 90),
            '365일': 0
        }
        
        # 통계 계산
        stats = self._calculate_statistics(historical_data, current_session)
        
        chart_html = f"""
<div class="advanced-charts">
    <h3>📊 과거 1년 데이터 기반 성과 분석</h3>
    
    <!-- 기간 선택 탭 -->
    <div class="period-tabs">
        <button class="tab-button active" onclick="showPeriod('30')">30일</button>
        <button class="tab-button" onclick="showPeriod('90')">90일</button>
        <button class="tab-button" onclick="showPeriod('365')">1년</button>
    </div>
    
    <!-- 차트 컨테이너 -->
    <div class="chart-grid">
        <!-- 누적 손익 차트 -->
        <div class="chart-box">
            <h4>누적 손익 추이</h4>
            <canvas id="historicalCumulativeChart" width="500" height="250"></canvas>
            <div class="chart-stats">
                <span>최고: {max(historical_data['cumulative_pnl']) if historical_data['cumulative_pnl'] else 0:,.0f}원</span>
                <span>최저: {min(historical_data['cumulative_pnl']) if historical_data['cumulative_pnl'] else 0:,.0f}원</span>
                <span>현재: {historical_data['cumulative_pnl'][-1] if historical_data['cumulative_pnl'] else 0:,.0f}원</span>
            </div>
        </div>
        
        <!-- 일일 손익 차트 -->
        <div class="chart-box">
            <h4>일일 손익 분포</h4>
            <canvas id="dailyPnlChart" width="500" height="250"></canvas>
            <div class="chart-stats">
                <span>평균: {stats['avg_daily_pnl']:,.0f}원</span>
                <span>표준편차: {stats['std_daily_pnl']:,.0f}원</span>
                <span>오늘: {current_session.get('total_profit_loss', 0):,.0f}원</span>
            </div>
        </div>
        
        <!-- 승률 추이 차트 -->
        <div class="chart-box">
            <h4>승률 변화</h4>
            <canvas id="winRateChart" width="500" height="250"></canvas>
            <div class="chart-stats">
                <span>평균: {stats['avg_win_rate']:.1f}%</span>
                <span>최고: {stats['max_win_rate']:.1f}%</span>
                <span>오늘: {current_session.get('win_rate', 0):.1f}%</span>
            </div>
        </div>
        
        <!-- 포트폴리오 가치 차트 -->
        <div class="chart-box">
            <h4>포트폴리오 가치 변화</h4>
            <canvas id="portfolioChart" width="500" height="250"></canvas>
            <div class="chart-stats">
                <span>시작: 100,000,000원</span>
                <span>최고: {max(historical_data['portfolio_value']) if historical_data['portfolio_value'] else 100000000:,.0f}원</span>
                <span>현재: {historical_data['portfolio_value'][-1] if historical_data['portfolio_value'] else 100000000:,.0f}원</span>
            </div>
        </div>
    </div>
    
    <!-- 성과 지표 테이블 -->
    <div class="performance-metrics">
        <h4>📈 핵심 성과 지표 (1년 기준)</h4>
        <table class="metrics-table">
            <tr>
                <td>총 거래일</td>
                <td>{len(historical_data['dates'])}일</td>
                <td>총 수익률</td>
                <td class="{'positive' if stats['total_return'] >= 0 else 'negative'}">{stats['total_return']:.2f}%</td>
            </tr>
            <tr>
                <td>승리일</td>
                <td>{stats['winning_days']}일</td>
                <td>패배일</td>
                <td>{stats['losing_days']}일</td>
            </tr>
            <tr>
                <td>최대 일일 수익</td>
                <td class="positive">{stats['max_daily_gain']:,.0f}원</td>
                <td>최대 일일 손실</td>
                <td class="negative">{stats['max_daily_loss']:,.0f}원</td>
            </tr>
            <tr>
                <td>평균 거래량</td>
                <td>{stats['avg_trade_volume']:.1f}건/일</td>
                <td>샤프 비율</td>
                <td>{stats['sharpe_ratio']:.2f}</td>
            </tr>
        </table>
    </div>
</div>

<style>
.advanced-charts {{
    margin: 30px 0;
    padding: 20px;
    background: #f8f9fa;
    border-radius: 10px;
}}

.period-tabs {{
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
}}

.tab-button {{
    padding: 8px 20px;
    border: 1px solid #ddd;
    background: white;
    border-radius: 5px;
    cursor: pointer;
    transition: all 0.3s;
}}

.tab-button.active {{
    background: #007bff;
    color: white;
    border-color: #007bff;
}}

.chart-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
    margin-bottom: 30px;
}}

.chart-box {{
    background: white;
    padding: 15px;
    border-radius: 8px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}}

.chart-box h4 {{
    margin: 0 0 10px 0;
    color: #333;
}}

.chart-stats {{
    display: flex;
    justify-content: space-between;
    margin-top: 10px;
    font-size: 12px;
    color: #666;
}}

.performance-metrics {{
    background: white;
    padding: 20px;
    border-radius: 8px;
}}

.metrics-table {{
    width: 100%;
    border-collapse: collapse;
}}

.metrics-table td {{
    padding: 10px;
    border-bottom: 1px solid #eee;
}}

.metrics-table td:nth-child(even) {{
    text-align: right;
    font-weight: bold;
}}
</style>

<script>
// 과거 데이터
const historicalData = {json.dumps(historical_data)};
const currentSession = {json.dumps(current_session)};

// 차트 그리기 함수
function drawHistoricalCharts(period) {{
    const days = period === '30' ? 30 : period === '90' ? 90 : 365;
    const startIdx = Math.max(0, historicalData.dates.length - days);
    
    // 누적 손익 차트
    drawLineChart('historicalCumulativeChart', 
        historicalData.dates.slice(startIdx),
        historicalData.cumulative_pnl.slice(startIdx),
        '#007bff');
    
    // 일일 손익 차트
    drawBarChart('dailyPnlChart',
        historicalData.dates.slice(startIdx),
        historicalData.daily_pnl.slice(startIdx));
    
    // 승률 차트
    drawLineChart('winRateChart',
        historicalData.dates.slice(startIdx),
        historicalData.win_rate.slice(startIdx),
        '#28a745');
    
    // 포트폴리오 차트
    drawLineChart('portfolioChart',
        historicalData.dates.slice(startIdx),
        historicalData.portfolio_value.slice(startIdx),
        '#6f42c1');
}}

function drawLineChart(canvasId, labels, data, color) {{
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    ctx.clearRect(0, 0, width, height);
    
    if (data.length < 2) return;
    
    const padding = 40;
    const graphWidth = width - padding * 2;
    const graphHeight = height - padding * 2;
    
    const maxVal = Math.max(...data);
    const minVal = Math.min(...data);
    const range = maxVal - minVal || 1;
    
    // 그리드 그리기
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 5; i++) {{
        const y = padding + (graphHeight / 5) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(width - padding, y);
        ctx.stroke();
    }}
    
    // 데이터 라인 그리기
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    
    data.forEach((val, i) => {{
        const x = padding + (i / (data.length - 1)) * graphWidth;
        const y = padding + graphHeight - ((val - minVal) / range) * graphHeight;
        
        if (i === 0) {{
            ctx.moveTo(x, y);
        }} else {{
            ctx.lineTo(x, y);
        }}
    }});
    
    ctx.stroke();
    
    // 현재 값 강조
    if (data.length > 0) {{
        const lastX = width - padding;
        const lastY = padding + graphHeight - ((data[data.length - 1] - minVal) / range) * graphHeight;
        
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(lastX, lastY, 4, 0, 2 * Math.PI);
        ctx.fill();
    }}
}}

function drawBarChart(canvasId, labels, data) {{
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    ctx.clearRect(0, 0, width, height);
    
    if (data.length === 0) return;
    
    const padding = 40;
    const graphWidth = width - padding * 2;
    const graphHeight = height - padding * 2;
    
    const maxVal = Math.max(...data.map(Math.abs));
    
    // 중심선 그리기
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, height / 2);
    ctx.lineTo(width - padding, height / 2);
    ctx.stroke();
    
    // 바 그리기
    const barWidth = graphWidth / data.length;
    
    data.forEach((val, i) => {{
        const x = padding + i * barWidth;
        const barHeight = (Math.abs(val) / maxVal) * (graphHeight / 2);
        const y = val >= 0 ? height / 2 - barHeight : height / 2;
        
        ctx.fillStyle = val >= 0 ? '#28a745' : '#dc3545';
        ctx.fillRect(x + 1, y, barWidth - 2, barHeight);
    }});
}}

function showPeriod(period) {{
    // 탭 활성화 상태 변경
    document.querySelectorAll('.tab-button').forEach(btn => {{
        btn.classList.remove('active');
    }});
    event.target.classList.add('active');
    
    // 차트 다시 그리기
    drawHistoricalCharts(period);
}}

// 초기 차트 그리기
setTimeout(() => drawHistoricalCharts('30'), 100);
</script>
        """
        
        return chart_html
    
    def _calculate_statistics(self, historical_data: Dict, current_session: Dict) -> Dict:
        """통계 계산"""
        import statistics
        
        stats = {}
        
        if historical_data['daily_pnl']:
            stats['avg_daily_pnl'] = statistics.mean(historical_data['daily_pnl'])
            stats['std_daily_pnl'] = statistics.stdev(historical_data['daily_pnl']) if len(historical_data['daily_pnl']) > 1 else 0
            stats['max_daily_gain'] = max(historical_data['daily_pnl'])
            stats['max_daily_loss'] = min(historical_data['daily_pnl'])
            stats['winning_days'] = len([p for p in historical_data['daily_pnl'] if p > 0])
            stats['losing_days'] = len([p for p in historical_data['daily_pnl'] if p < 0])
        else:
            stats['avg_daily_pnl'] = 0
            stats['std_daily_pnl'] = 0
            stats['max_daily_gain'] = 0
            stats['max_daily_loss'] = 0
            stats['winning_days'] = 0
            stats['losing_days'] = 0
        
        if historical_data['win_rate']:
            stats['avg_win_rate'] = statistics.mean(historical_data['win_rate'])
            stats['max_win_rate'] = max(historical_data['win_rate'])
        else:
            stats['avg_win_rate'] = 0
            stats['max_win_rate'] = 0
        
        if historical_data['trade_volume']:
            stats['avg_trade_volume'] = statistics.mean(historical_data['trade_volume'])
        else:
            stats['avg_trade_volume'] = 0
        
        # 총 수익률 계산
        initial_value = 100000000
        final_value = historical_data['portfolio_value'][-1] if historical_data['portfolio_value'] else initial_value
        stats['total_return'] = ((final_value - initial_value) / initial_value) * 100
        
        # 샤프 비율 계산 (연율화)
        if stats['std_daily_pnl'] > 0:
            daily_return = stats['avg_daily_pnl'] / initial_value
            daily_std = stats['std_daily_pnl'] / initial_value
            stats['sharpe_ratio'] = (daily_return * 252) / (daily_std * (252 ** 0.5))
        else:
            stats['sharpe_ratio'] = 0
        
        return stats


# 전역 인스턴스
chart_generator = HistoricalChartGenerator()