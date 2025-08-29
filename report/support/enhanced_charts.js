// CanvasJS 기반 tideWise 차트 시스템

// 매매 물량 더미 데이터 생성 함수
function generateTradingVolumeData(priceData) {
    return priceData.map((candle, i) => {
        const baseVolume = candle.volume || 1000;
        return {
            time: candle.time,
            individual: Math.floor(baseVolume * (0.4 + Math.random() * 0.3)), // 개인: 40-70%
            foreign: Math.floor(baseVolume * (0.1 + Math.random() * 0.2)), // 외국인: 10-30%
            institution: Math.floor(baseVolume * (0.1 + Math.random() * 0.15)) // 기관: 10-25%
        };
    });
}

// CanvasJS 캔들스틱 + 매매 물량 차트 생성
function createCandlestickChart(containerId, priceData) {
    if (!priceData || priceData.length === 0) return;
    
    // 매매 물량 데이터 생성
    const volumeData = generateTradingVolumeData(priceData);
    
    // 캔들스틱 데이터 변환
    const candlestickData = priceData.map((candle, i) => ({
        x: new Date(2025, 7, 23, 15, i), // 2025-08-23 15:00부터 분 단위
        y: [candle.open, candle.high, candle.low, candle.close]
    }));
    
    // 개인 매매 물량 데이터
    const individualData = volumeData.map((vol, i) => ({
        x: new Date(2025, 7, 23, 15, i),
        y: vol.individual
    }));
    
    // 외국인 매매 물량 데이터
    const foreignData = volumeData.map((vol, i) => ({
        x: new Date(2025, 7, 23, 15, i),
        y: vol.foreign
    }));
    
    // 기관 매매 물량 데이터
    const institutionData = volumeData.map((vol, i) => ({
        x: new Date(2025, 7, 23, 15, i),
        y: vol.institution
    }));
    
    var chart = new CanvasJS.Chart(containerId, {
        animationEnabled: true,
        theme: "light2",
        exportEnabled: true,
        title: {
            text: "삼성전자 실시간 5분봉 차트",
            fontSize: 18,
            fontFamily: "Helvetica"
        },
        subtitles: [{
            text: "캔들스틱 + 투자자별 매매 물량",
            fontSize: 12
        }],
        axisX: {
            valueFormatString: "HH:mm",
            labelFontSize: 11,
            gridColor: "#f0f2f5",
            lineColor: "#e5e7eb"
        },
        axisY: {
            prefix: "₩",
            title: "주가",
            titleFontSize: 12,
            labelFontSize: 11,
            gridColor: "#f0f2f5",
            lineColor: "#e5e7eb",
            valueFormatString: "#,##0",
            interval: 100, // 100원 단위로 구간 설정 (더 세밀하게)
            minimum: Math.min(...priceData.map(d => Math.min(d.open, d.high, d.low, d.close))) - 25,
            maximum: Math.max(...priceData.map(d => Math.max(d.open, d.high, d.low, d.close))) + 25
        },
        axisY2: {
            title: "매매 물량 (주)",
            titleFontSize: 12,
            labelFontSize: 11,
            gridColor: "#f0f2f5",
            lineColor: "#e5e7eb",
            valueFormatString: "#,##0",
            interval: 20000, // 2만주 단위로 구간 설정
            minimum: 0,
            maximum: Math.max(...priceData.map(d => d.volume || 0)) * 0.7 / 3 * 1.1 // 매매량 추정치의 110%
        },
        toolTip: {
            shared: true,
            contentFormatter: function (e) {
                var content = "<strong>" + CanvasJS.formatDate(e.entries[0].dataPoint.x, "HH:mm") + "</strong><br/>";
                
                for (var i = 0; i < e.entries.length; i++) {
                    if (e.entries[i].dataSeries.type === "candlestick") {
                        var ohlc = e.entries[i].dataPoint.y;
                        content += "<span style='color: " + e.entries[i].dataSeries.color + "'>" + e.entries[i].dataSeries.name + "</span><br/>";
                        content += "시가: ₩" + ohlc[0].toLocaleString() + "<br/>";
                        content += "고가: ₩" + ohlc[1].toLocaleString() + "<br/>";
                        content += "저가: ₩" + ohlc[2].toLocaleString() + "<br/>";
                        content += "종가: ₩" + ohlc[3].toLocaleString() + "<br/>";
                    } else {
                        content += "<span style='color: " + e.entries[i].dataSeries.color + "'>" + e.entries[i].dataSeries.name + "</span>: " + e.entries[i].dataPoint.y.toLocaleString() + "주<br/>";
                    }
                }
                return content;
            }
        },
        legend: {
            reversed: true,
            cursor: "pointer",
            itemclick: toggleDataSeries,
            fontSize: 11,
            fontFamily: "Helvetica"
        },
        data: [{
            type: "candlestick",
            showInLegend: true,
            name: "삼성전자",
            yValueFormatString: "₩#,##0",
            xValueFormatString: "HH:mm",
            risingColor: "#FF69B4", // 핑크 색상 (상승)
            fallingColor: "#87CEEB", // 라이트 블루 색상 (하락)
            lineThickness: 1, // 캔들스틱 라인 굵기를 절반으로
            dataPoints: candlestickData
        }, {
            type: "line",
            showInLegend: true,
            name: "개인 매매량",
            axisYType: "secondary",
            yValueFormatString: "#,##0주",
            xValueFormatString: "HH:mm",
            color: "#00FF00", // 초록색
            lineThickness: 2,
            markerSize: 4,
            dataPoints: individualData
        }, {
            type: "line",
            showInLegend: true,
            name: "외국인 매매량",
            axisYType: "secondary",
            yValueFormatString: "#,##0주",
            xValueFormatString: "HH:mm",
            color: "#800080", // 퍼플색
            lineThickness: 2,
            markerSize: 4,
            dataPoints: foreignData
        }, {
            type: "line",
            showInLegend: true,
            name: "기관 매매량",
            axisYType: "secondary",
            yValueFormatString: "#,##0주",
            xValueFormatString: "HH:mm",
            color: "#000000", // 검정색
            lineThickness: 2,
            markerSize: 4,
            dataPoints: institutionData
        }]
    });
    
    chart.render();
    return chart;
}

// CanvasJS 거래량 차트 생성 (막대 + 핑크 라인)
function createVolumeChart(containerId, priceData) {
    if (!priceData || priceData.length === 0) return;
    
    // 거래량 데이터 변환 (막대그래프용)
    const volumeData = priceData.map((candle, i) => ({
        x: new Date(2025, 7, 23, 15, i),
        y: candle.volume || 0,
        color: candle.close >= candle.open ? "#FF69B4" : "#87CEEB" // 상승: 핑크, 하락: 라이트블루
    }));
    
    // 거래량 라인 데이터 (핑크 라인용)
    const volumeLineData = priceData.map((candle, i) => ({
        x: new Date(2025, 7, 23, 15, i),
        y: candle.volume || 0
    }));
    
    var chart = new CanvasJS.Chart(containerId, {
        animationEnabled: true,
        theme: "light2",
        exportEnabled: true,
        title: {
            text: "거래량 차트",
            fontSize: 18,
            fontFamily: "Helvetica"
        },
        axisX: {
            valueFormatString: "HH:mm",
            labelFontSize: 11,
            gridColor: "#f0f2f5",
            lineColor: "#e5e7eb"
        },
        axisY: {
            title: "거래량 (주)",
            titleFontSize: 12,
            labelFontSize: 11,
            gridColor: "#f0f2f5",
            lineColor: "#e5e7eb",
            valueFormatString: "#,##0",
            minimum: 0,
            maximum: Math.max(...priceData.map(d => d.volume || 0)) * 1.02, // 최대값의 102%로 설정 (더욱 좁게)
            interval: 100000 // 100,000주 (10만주) 단위로 고정
        },
        toolTip: {
            shared: true,
            contentFormatter: function (e) {
                var content = "<strong>" + CanvasJS.formatDate(e.entries[0].dataPoint.x, "HH:mm") + "</strong><br/>";
                content += "거래량: " + e.entries[0].dataPoint.y.toLocaleString() + "주";
                return content;
            }
        },
        legend: {
            fontSize: 11,
            fontFamily: "Helvetica"
        },
        data: [{
            type: "column",
            showInLegend: true,
            name: "거래량 (막대)",
            yValueFormatString: "#,##0주",
            xValueFormatString: "HH:mm",
            dataPoints: volumeData
        }, {
            type: "line",
            showInLegend: true,
            name: "거래량 추세선",
            yValueFormatString: "#,##0주",
            xValueFormatString: "HH:mm",
            color: "#FF0000", // 빨간색 라인
            lineThickness: 2,
            markerType: "circle",
            markerSize: 4,
            markerColor: "#FF0000",
            markerBorderColor: "#CC0000",
            markerBorderThickness: 1,
            dataPoints: volumeLineData
        }]
    });
    
    chart.render();
    return chart;
}

// 레전드 토글 함수
function toggleDataSeries(e) {
    if (typeof (e.dataSeries.visible) === "undefined" || e.dataSeries.visible) {
        e.dataSeries.visible = false;
    } else {
        e.dataSeries.visible = true;
    }
    e.chart.render();
}

// 차트 초기화 함수 (CanvasJS 버전)
function initializeEnhancedCharts(data) {
    if (!data || data.length === 0) {
        console.error('차트 데이터가 없습니다.');
        return;
    }
    
    // CanvasJS 차트 생성
    const candlestickChart = createCandlestickChart('sessionPnlChart', data);
    const volumeChart = createVolumeChart('sessionCumulativeChart', data);
    
    console.log('CanvasJS charts initialized with', data.length, 'data points');
    return { candlestickChart, volumeChart };
}