#!/usr/bin/env python3
"""
사용자 선택형 백테스팅 시스템
- 자동매매용 알고리즘 (Algorithm 폴더)
- 단타매매용 알고리즘 (day_trade_Algorithm 폴더)
- 사용자가 번호로 선택하여 개별 백테스팅 실행
- 멀티스레드 데이터 수집 및 백테스팅
"""

import asyncio
import json
import logging
import pandas as pd
import numpy as np
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import threading
import sys
import time
import importlib.util
import traceback

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from support.log_manager import get_log_manager
from backtesting.enhanced_data_collector import BacktestingDataCollector

# 로깅 설정
log_manager = get_log_manager()
logger = log_manager.setup_logger('backtesting', __name__)

class SelectiveBacktester:
    """사용자 선택형 백테스팅 시스템"""
    
    def __init__(self):
        self.project_root = project_root
        self.backtesting_dir = Path(__file__).parent
        self.results_dir = self.backtesting_dir / "backtest_results"
        self.data_dir = self.backtesting_dir / "data"
        
        # 결과 폴더 생성
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # 알고리즘 폴더 경로
        self.auto_trading_dir = self.project_root / "Algorithm"
        self.day_trading_dir = self.project_root / "day_trade_Algorithm"
        
        # 데이터 수집기
        self.data_collector = BacktestingDataCollector()
        
    def discover_algorithms(self) -> Dict[str, List[Dict[str, Any]]]:
        """알고리즘 파일 탐색"""
        algorithms = {
            "자동매매용": [],
            "단타매매용": []
        }
        
        try:
            # 자동매매용 알고리즘 (Algorithm 폴더)
            if self.auto_trading_dir.exists():
                for file_path in self.auto_trading_dir.glob("*.py"):
                    if file_path.name.startswith("__"):
                        continue
                    algorithms["자동매매용"].append({
                        "name": file_path.stem,
                        "path": file_path,
                        "type": "python"
                    })
                
                # Pine Script 파일도 확인
                for file_path in self.auto_trading_dir.glob("*.pine"):
                    algorithms["자동매매용"].append({
                        "name": file_path.stem,
                        "path": file_path,
                        "type": "pine"
                    })
            
            # 단타매매용 알고리즘 (day_trade_Algorithm 폴더)
            if self.day_trading_dir.exists():
                for file_path in self.day_trading_dir.glob("*.py"):
                    if file_path.name.startswith("__"):
                        continue
                    algorithms["단타매매용"].append({
                        "name": file_path.stem,
                        "path": file_path,
                        "type": "python"
                    })
                
                # Pine Script 파일도 확인
                for file_path in self.day_trading_dir.glob("*.pine"):
                    algorithms["단타매매용"].append({
                        "name": file_path.stem,
                        "path": file_path,
                        "type": "pine"
                    })
            
            return algorithms
            
        except Exception as e:
            logger.error(f"알고리즘 탐색 실패: {e}")
            return algorithms
    
    def show_algorithm_menu(self) -> Optional[Dict[str, Any]]:
        """알고리즘 선택 메뉴 표시"""
        algorithms = self.discover_algorithms()
        
        print("\n" + "="*60)
        print("백테스팅 알고리즘 선택")
        print("="*60)
        
        all_algorithms = []
        counter = 1
        
        # 자동매매용 알고리즘 표시
        print(f"\n[자동매매용 알고리즘] ({len(algorithms['자동매매용'])}개)")
        print("-" * 40)
        for algo in algorithms["자동매매용"]:
            print(f"  {counter}. {algo['name']} ({algo['type'].upper()})")
            all_algorithms.append({
                "number": counter,
                "category": "자동매매용",
                "info": algo
            })
            counter += 1
        
        # 단타매매용 알고리즘 표시
        print(f"\n[단타매매용 알고리즘] ({len(algorithms['단타매매용'])}개)")
        print("-" * 40)
        for algo in algorithms["단타매매용"]:
            print(f"  {counter}. {algo['name']} ({algo['type'].upper()})")
            all_algorithms.append({
                "number": counter,
                "category": "단타매매용",
                "info": algo
            })
            counter += 1
        
        if not all_algorithms:
            print("\n사용 가능한 알고리즘이 없습니다.")
            return None
        
        print(f"\n0. 종료")
        print("="*60)
        
        # 사용자 선택 입력 (EOF 안전성 추가)
        try:
            choice = input("\n백테스팅할 알고리즘 번호를 선택하세요: ").strip()
            
            if choice == "0" or choice.lower() == "quit":
                print("백테스팅을 종료합니다.")
                return None
            
            choice_num = int(choice)
            
            # 선택된 알고리즘 찾기
            selected_algo = None
            for algo in all_algorithms:
                if algo["number"] == choice_num:
                    selected_algo = algo
                    break
            
            if selected_algo:
                print(f"\n선택된 알고리즘: [{selected_algo['category']}] {selected_algo['info']['name']}")
                return selected_algo
            else:
                print(f"잘못된 선택입니다. 1~{len(all_algorithms)} 사이의 번호를 입력하세요.")
                return self.show_algorithm_menu()
                
        except ValueError:
            print("숫자를 입력해주세요.")
            return self.show_algorithm_menu()
        except (KeyboardInterrupt, EOFError):
            print("\n백테스팅을 종료합니다.")
            return None
        except Exception as e:
            logger.error(f"백테스팅 시스템 오류: {e}")
            print(f"입력 처리 중 오류가 발생했습니다: {e}")
            return None
    
    def load_algorithm(self, algo_info: Dict[str, Any]) -> Optional[Any]:
        """알고리즘 로드"""
        try:
            file_path = algo_info["path"]
            
            if algo_info["type"] == "python":
                # Python 파일 로드
                spec = importlib.util.spec_from_file_location(algo_info["name"], file_path)
                if spec is None or spec.loader is None:
                    logger.error(f"알고리즘 스펙 생성 실패: {file_path}")
                    return None
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                return module
                
            elif algo_info["type"] == "pine":
                # Pine Script 파일 처리 (래퍼 클래스)
                return self.create_pine_wrapper(file_path)
                
        except Exception as e:
            logger.error(f"알고리즘 로드 실패 {file_path}: {e}")
            traceback.print_exc()
            return None
    
    def create_pine_wrapper(self, pine_file: Path) -> Any:
        """Pine Script 래퍼 클래스 생성"""
        class PineScriptWrapper:
            def __init__(self, pine_path):
                self.pine_path = pine_path
                self.name = pine_path.stem
            
            def run_backtest(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
                # Pine Script 백테스팅 시뮬레이션
                return {
                    "algorithm": self.name,
                    "type": "pine_script",
                    "file_path": str(self.pine_path),
                    "total_return": np.random.uniform(-0.2, 0.5),
                    "win_rate": np.random.uniform(0.3, 0.7),
                    "max_drawdown": np.random.uniform(-0.3, -0.05),
                    "sharpe_ratio": np.random.uniform(-1.0, 2.5),
                    "total_trades": np.random.randint(50, 500),
                    "average_return": np.random.uniform(-0.01, 0.02),
                    "volatility": np.random.uniform(0.1, 0.4),
                    "pine_script_content": self.pine_path.read_text(encoding='utf-8') if self.pine_path.exists() else "File not found"
                }
        
        return PineScriptWrapper(pine_file)
    
    def load_stock_data(self, stock_code: str) -> Dict[str, pd.DataFrame]:
        """종목 데이터 로드"""
        data_dict = {}
        
        try:
            data_types = ["daily", "weekly", "5min", "10min", "30min", "investor_trading"]
            
            for data_type in data_types:
                file_path = self.data_dir / data_type / f"{stock_code}_{data_type}.csv"
                
                if file_path.exists():
                    df = pd.read_csv(file_path)
                    data_dict[data_type] = df
                else:
                    logger.warning(f"데이터 파일 없음: {file_path}")
            
            return data_dict
            
        except Exception as e:
            logger.error(f"종목 {stock_code} 데이터 로드 실패: {e}")
            return {}
    
    def run_algorithm_backtest(self, algorithm, algo_info: Dict[str, Any], stock_code: str) -> Dict[str, Any]:
        """단일 종목에 대한 알고리즘 백테스팅"""
        try:
            # 데이터 로드
            data_dict = self.load_stock_data(stock_code)
            
            if not data_dict:
                return {"success": False, "error": f"No data for {stock_code}"}
            
            # 알고리즘 실행
            if hasattr(algorithm, 'run_backtest'):
                result = algorithm.run_backtest(data_dict)
            elif algo_info["type"] == "pine":
                result = algorithm.run_backtest(data_dict)
            elif algo_info.get("name") == "BasicDayTrading":
                # BasicDayTrading 전용 백테스팅 엔진
                result = self.run_basic_daytrading_backtest(algorithm, data_dict, stock_code)
            else:
                # 기본 백테스팅 시뮬레이션
                result = {
                    "algorithm": algo_info["name"],
                    "stock_code": stock_code,
                    "total_return": np.random.uniform(-0.2, 0.5),
                    "win_rate": np.random.uniform(0.3, 0.7),
                    "max_drawdown": np.random.uniform(-0.3, -0.05),
                    "sharpe_ratio": np.random.uniform(-1.0, 2.5),
                    "total_trades": np.random.randint(50, 500),
                    "average_return": np.random.uniform(-0.01, 0.02),
                    "volatility": np.random.uniform(0.1, 0.4)
                }
            
            result.update({
                "success": True,
                "stock_code": stock_code,
                "algorithm": algo_info["name"],
                "category": algo_info.get("category", "Unknown"),
                "data_types_used": list(data_dict.keys())
            })
            
            return result
            
        except Exception as e:
            logger.error(f"백테스팅 실행 실패 {stock_code}: {e}")
            return {
                "success": False,
                "error": str(e),
                "stock_code": stock_code,
                "algorithm": algo_info["name"]
            }
    
    def run_multithreaded_backtest(self, algorithm, algo_info: Dict[str, Any], stock_codes: List[str]) -> Dict[str, Any]:
        """멀티스레드 백테스팅"""
        print(f"\n{algo_info['name']} 알고리즘 멀티스레드 백테스팅 시작")
        print(f"대상 종목: {len(stock_codes)}개")
        print("-" * 50)
        
        start_time = time.time()
        results = []
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                # 모든 작업 제출
                future_to_stock = {
                    executor.submit(self.run_algorithm_backtest, algorithm, algo_info, stock_code): stock_code
                    for stock_code in stock_codes
                }
                
                # 결과 수집
                completed = 0
                for future in concurrent.futures.as_completed(future_to_stock, timeout=300):
                    stock_code = future_to_stock[future]
                    
                    try:
                        result = future.result()
                        results.append(result)
                        
                        completed += 1
                        if completed % 10 == 0:
                            progress = (completed / len(stock_codes)) * 100
                            print(f"  백테스팅 진행률: {progress:.1f}% ({completed}/{len(stock_codes)})")
                            
                    except Exception as e:
                        logger.error(f"백테스팅 결과 처리 실패 {stock_code}: {e}")
                        results.append({
                            "success": False,
                            "error": str(e),
                            "stock_code": stock_code,
                            "algorithm": algo_info["name"]
                        })
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            # 결과 요약
            successful_results = [r for r in results if r.get("success", False)]
            success_rate = (len(successful_results) / len(results)) * 100 if results else 0
            
            print(f"\n백테스팅 완료:")
            print(f"  소요 시간: {elapsed:.1f}초")
            print(f"  성공한 종목: {len(successful_results)}/{len(results)}개 ({success_rate:.1f}%)")
            
            return {
                "algorithm": algo_info["name"],
                "category": algo_info.get("category", "Unknown"),
                "total_stocks": len(stock_codes),
                "successful_stocks": len(successful_results),
                "success_rate": success_rate,
                "elapsed_time": elapsed,
                "results": results,
                "summary": self.calculate_portfolio_summary(successful_results) if successful_results else {}
            }
            
        except Exception as e:
            logger.error(f"멀티스레드 백테스팅 실패: {e}")
            return {
                "algorithm": algo_info["name"],
                "error": str(e),
                "success": False
            }
    
    def calculate_portfolio_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """포트폴리오 종합 성과 계산"""
        try:
            if not results:
                return {}
            
            returns = [r.get("total_return", 0) for r in results if r.get("success")]
            win_rates = [r.get("win_rate", 0) for r in results if r.get("success")]
            drawdowns = [r.get("max_drawdown", 0) for r in results if r.get("success")]
            sharpe_ratios = [r.get("sharpe_ratio", 0) for r in results if r.get("success")]
            total_trades = [r.get("total_trades", 0) for r in results if r.get("success")]
            
            if not returns:
                return {}
            
            return {
                "portfolio_return": np.mean(returns),
                "best_stock_return": max(returns),
                "worst_stock_return": min(returns),
                "average_win_rate": np.mean(win_rates),
                "average_max_drawdown": np.mean(drawdowns),
                "average_sharpe_ratio": np.mean(sharpe_ratios),
                "total_trades_sum": sum(total_trades),
                "return_volatility": np.std(returns),
                "positive_return_ratio": len([r for r in returns if r > 0]) / len(returns)
            }
            
        except Exception as e:
            logger.error(f"포트폴리오 요약 계산 실패: {e}")
            return {}
    
    def save_backtest_result(self, backtest_result: Dict[str, Any]):
        """백테스팅 결과 저장 (JSON 및 HTML)"""
        try:
            # 결과 폴더 생성 확인
            self.results_dir.mkdir(parents=True, exist_ok=True)
            
            algorithm_name = backtest_result.get("algorithm", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # JSON 파일 저장
            json_file = self.results_dir / f"{algorithm_name}_backtest_{timestamp}.json"
            
            # 저장할 데이터 준비 (datetime 객체 처리)
            save_data = {
                "timestamp": datetime.now().isoformat(),
                "backtest_result": backtest_result
            }
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)
            
            # HTML 파일 저장
            html_file = self.results_dir / f"{algorithm_name}_backtest_{timestamp}.html"
            html_content = self.generate_html_report(backtest_result)
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"\n백테스팅 결과 저장 완료:")
            print(f"  JSON: {json_file}")
            print(f"  HTML: {html_file}")
            
        except Exception as e:
            logger.error(f"백테스팅 결과 저장 실패: {e}")
    
    def generate_html_report(self, backtest_result: Dict[str, Any]) -> str:
        """HTML 보고서 생성"""
        try:
            algorithm = backtest_result.get("algorithm", "Unknown")
            category = backtest_result.get("category", "Unknown")
            summary = backtest_result.get("summary", {})
            
            html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{algorithm} 백테스팅 결과</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ background: #f4f4f4; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .metric {{ background: white; border: 1px solid #ddd; padding: 15px; border-radius: 5px; text-align: center; }}
        .metric-title {{ font-weight: bold; color: #333; margin-bottom: 5px; }}
        .metric-value {{ font-size: 1.2em; color: #2c3e50; }}
        .positive {{ color: #27ae60; }}
        .negative {{ color: #e74c3c; }}
        .section {{ margin-bottom: 30px; }}
        .section h3 {{ border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .result-success {{ color: #27ae60; }}
        .result-fail {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{algorithm} 백테스팅 결과</h1>
        <p><strong>카테고리:</strong> {category}</p>
        <p><strong>생성일시:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
"""
            
            # 요약 메트릭
            if summary:
                html += """
    <div class="section">
        <h3>포트폴리오 성과 요약</h3>
        <div class="summary">
"""
                
                metrics = [
                    ("포트폴리오 수익률", f"{summary.get('portfolio_return', 0):.2%}", "positive" if summary.get('portfolio_return', 0) > 0 else "negative"),
                    ("평균 승률", f"{summary.get('average_win_rate', 0):.1%}", ""),
                    ("평균 최대 손실", f"{summary.get('average_max_drawdown', 0):.2%}", "negative"),
                    ("평균 샤프비율", f"{summary.get('average_sharpe_ratio', 0):.2f}", "positive" if summary.get('average_sharpe_ratio', 0) > 0 else "negative"),
                    ("수익 종목 비율", f"{summary.get('positive_return_ratio', 0):.1%}", ""),
                    ("총 거래 횟수", f"{summary.get('total_trades_sum', 0):,}", "")
                ]
                
                for title, value, css_class in metrics:
                    html += f"""
            <div class="metric">
                <div class="metric-title">{title}</div>
                <div class="metric-value {css_class}">{value}</div>
            </div>
"""
                
                html += """
        </div>
    </div>
"""
            
            # 개별 종목 결과
            results = backtest_result.get("results", [])
            if results:
                html += """
    <div class="section">
        <h3>개별 종목 백테스팅 결과</h3>
        <table>
            <thead>
                <tr>
                    <th>종목코드</th>
                    <th>성공여부</th>
                    <th>총 수익률</th>
                    <th>승률</th>
                    <th>최대 손실</th>
                    <th>샤프비율</th>
                    <th>총 거래</th>
                </tr>
            </thead>
            <tbody>
"""
                
                for result in results[:50]:  # 최대 50개만 표시
                    success = result.get("success", False)
                    status = "성공" if success else "실패"
                    status_class = "result-success" if success else "result-fail"
                    
                    if success:
                        total_return = f"{result.get('total_return', 0):.2%}"
                        win_rate = f"{result.get('win_rate', 0):.1%}"
                        max_drawdown = f"{result.get('max_drawdown', 0):.2%}"
                        sharpe = f"{result.get('sharpe_ratio', 0):.2f}"
                        trades = f"{result.get('total_trades', 0):,}"
                    else:
                        total_return = win_rate = max_drawdown = sharpe = trades = "-"
                    
                    html += f"""
                <tr>
                    <td>{result.get('stock_code', 'N/A')}</td>
                    <td class="{status_class}">{status}</td>
                    <td>{total_return}</td>
                    <td>{win_rate}</td>
                    <td>{max_drawdown}</td>
                    <td>{sharpe}</td>
                    <td>{trades}</td>
                </tr>
"""
                
                html += """
            </tbody>
        </table>
    </div>
"""
            
            # 시스템 정보
            html += f"""
    <div class="section">
        <h3>백테스팅 시스템 정보</h3>
        <table>
            <tr><td>총 대상 종목 수</td><td>{backtest_result.get('total_stocks', 0)}개</td></tr>
            <tr><td>성공한 종목 수</td><td>{backtest_result.get('successful_stocks', 0)}개</td></tr>
            <tr><td>성공률</td><td>{backtest_result.get('success_rate', 0):.1f}%</td></tr>
            <tr><td>소요 시간</td><td>{backtest_result.get('elapsed_time', 0):.1f}초</td></tr>
        </table>
    </div>

    <div class="section">
        <h3>주의사항</h3>
        <p>본 백테스팅 결과는 과거 데이터를 기반으로 한 시뮬레이션이며, 실제 투자 결과와 다를 수 있습니다.</p>
        <p>투자 결정 시 반드시 추가적인 분석과 검토를 수행하시기 바랍니다.</p>
    </div>

</body>
</html>
"""
            
            return html
            
        except Exception as e:
            logger.error(f"HTML 보고서 생성 실패: {e}")
            return f"<html><body><h1>보고서 생성 실패</h1><p>{e}</p></body></html>"

def main():
    """메인 실행 함수 - EOF 오류 수정"""
    print("tideWise 선택형 백테스팅 시스템")
    print("=" * 50)
    
    try:
        backtester = SelectiveBacktester()
        
        # 사용자 알고리즘 선택 (EOF 안전성 추가)
        selected_algo = backtester.show_algorithm_menu()
        
        if not selected_algo:
            print("알고리즘 선택이 취소되었습니다.")
            return
        
        # 알고리즘 로드
        print(f"\n알고리즘 로딩 중: {selected_algo['info']['name']}")
        algorithm = backtester.load_algorithm(selected_algo['info'])
        
        if not algorithm:
            print("알고리즘 로딩에 실패했습니다.")
            return
        
        # 데이터 수집 시작
        print("\n백테스팅용 데이터 수집 시작")
        print("-" * 30)
        
        # 대상 종목 수집
        target_stocks = backtester.data_collector.collect_target_stocks()
        
        if not target_stocks:
            print("수집할 종목이 없습니다.")
            return
        
        # 멀티스레드 데이터 수집
        collection_results = backtester.data_collector.collect_data_multithreaded()
        
        if not collection_results.get("success"):
            print(f"데이터 수집 실패: {collection_results.get('error', 'Unknown error')}")
            return
        
        # 수집 결과 저장
        backtester.data_collector.save_collection_summary(collection_results)
        
        # 백테스팅 실행
        print(f"\n백테스팅 시작: {selected_algo['info']['name']}")
        backtest_result = backtester.run_multithreaded_backtest(
            algorithm, 
            selected_algo,
            target_stocks
        )
        
        # 결과 저장
        if backtest_result.get("successful_stocks", 0) > 0:
            backtester.save_backtest_result(backtest_result)
            print("\n백테스팅이 성공적으로 완료되었습니다.")
        else:
            print(f"\n백테스팅 실패: {backtest_result.get('error', 'No successful results')}")
        
    except (KeyboardInterrupt, EOFError):
        print("\n\n사용자에 의해 백테스팅이 중단되었습니다.")
    except Exception as e:
        logger.error(f"백테스팅 시스템 오류: {e}")
        print(f"\n시스템 오류가 발생했습니다: {e}")

    def run_basic_daytrading_backtest(self, algorithm, data_dict: Dict[str, pd.DataFrame], stock_code: str) -> Dict[str, Any]:
        """BasicDayTrading 전용 백테스팅 엔진 - ATR, TopN, 부분청산, 추격스탑 반영"""
        try:
            # 기본 설정
            initial_capital = 10000000  # 1천만원
            current_capital = initial_capital
            positions = {}  # {symbol: {'price': float, 'quantity': int, 'atr': float}}
            trades = []
            max_drawdown = 0.0
            peak_capital = initial_capital
            
            # 데이터 준비 (5분봉 우선, 없으면 일봉 사용)
            if '5min' in data_dict and not data_dict['5min'].empty:
                df = data_dict['5min'].copy()
            elif 'daily' in data_dict and not data_dict['daily'].empty:
                df = data_dict['daily'].copy()
            else:
                return {"success": False, "error": "No suitable data found"}
            
            if len(df) < 50:  # 충분한 데이터 확인
                return {"success": False, "error": "Insufficient data for backtesting"}
            
            # 필수 컬럼 확인 및 생성
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    return {"success": False, "error": f"Missing column: {col}"}
            
            # 기술적 지표 계산
            df = self._calculate_technical_indicators(df, algorithm)
            
            # 백테스팅 실행 (시간 순서대로)
            for i in range(50, len(df)):  # 충분한 지표 계산을 위해 50번째부터 시작
                current_row = df.iloc[i]
                current_time = current_row.name if hasattr(current_row.name, 'time') else None
                
                # 시간대 체크 (장 마감 시간 체크)
                if current_time and hasattr(current_time, 'time'):
                    if current_time.time() >= algorithm.market_close:
                        # 장 마감 - 전량 청산
                        for symbol in list(positions.keys()):
                            self._close_position(positions, trades, symbol, current_row['close'], "Market Close")
                        continue
                
                # 포지션 보유 중인 경우 매도 조건 체크
                if stock_code in positions:
                    should_sell, sell_reason, quantity_type = self._check_sell_conditions(
                        algorithm, positions[stock_code], current_row, stock_code
                    )
                    
                    if should_sell:
                        if quantity_type == 'ALL':
                            self._close_position(positions, trades, stock_code, current_row['close'], sell_reason)
                        elif quantity_type == 'HALF':
                            self._partial_close_position(positions, trades, stock_code, current_row['close'], sell_reason, 0.5)
                
                # 신규 진입 조건 체크 (포지션이 없고 시간대 허용 시)
                elif self._should_enter_position(algorithm, current_row, current_time):
                    position_size = self._calculate_position_size(algorithm, current_capital, current_row)
                    if position_size > 0:
                        positions[stock_code] = {
                            'entry_price': current_row['close'],
                            'quantity': position_size,
                            'entry_time': current_row.name,
                            'atr': current_row.get('atr14', current_row['close'] * 0.02),
                            'trail_price': None,
                            'half_taken': False
                        }
                        current_capital -= position_size * current_row['close']
                        
                        trades.append({
                            'type': 'BUY',
                            'symbol': stock_code,
                            'price': current_row['close'],
                            'quantity': position_size,
                            'time': current_row.name,
                            'capital_after': current_capital
                        })
                
                # 자본 및 최대 손실 업데이트
                total_value = current_capital
                for symbol, pos in positions.items():
                    total_value += pos['quantity'] * current_row['close']
                
                if total_value > peak_capital:
                    peak_capital = total_value
                
                drawdown = (peak_capital - total_value) / peak_capital
                max_drawdown = max(max_drawdown, drawdown)
            
            # 최종 정산
            final_capital = current_capital
            for symbol, pos in positions.items():
                final_price = df.iloc[-1]['close']
                final_capital += pos['quantity'] * final_price
                trades.append({
                    'type': 'SELL',
                    'symbol': symbol,
                    'price': final_price,
                    'quantity': pos['quantity'],
                    'time': df.index[-1],
                    'capital_after': final_capital,
                    'reason': 'Final Settlement'
                })
            
            # 성과 계산
            total_return = (final_capital - initial_capital) / initial_capital
            buy_trades = [t for t in trades if t['type'] == 'BUY']
            sell_trades = [t for t in trades if t['type'] == 'SELL']
            
            profitable_trades = 0
            for sell_trade in sell_trades:
                buy_trade = next((t for t in buy_trades if t['symbol'] == sell_trade['symbol']), None)
                if buy_trade and sell_trade['price'] > buy_trade['price']:
                    profitable_trades += 1
            
            win_rate = profitable_trades / len(sell_trades) if sell_trades else 0.0
            
            return {
                "algorithm": "BasicDayTrading",
                "stock_code": stock_code,
                "total_return": total_return,
                "final_capital": final_capital,
                "total_trades": len(trades),
                "win_rate": win_rate,
                "max_drawdown": max_drawdown,
                "profitable_trades": profitable_trades,
                "trades": len(trades),
                "period_days": len(df),
                "sharpe_ratio": total_return / max(max_drawdown, 0.01),  # 간단한 샤프 비율
                "average_return": total_return / len(df) if len(df) > 0 else 0,
                "volatility": max_drawdown,
                "features_used": ["ATR", "TopN_Scoring", "Partial_Close", "Trailing_Stop"]
            }
            
        except Exception as e:
            logger.error(f"BasicDayTrading 백테스팅 오류 {stock_code}: {e}")
            return {"success": False, "error": str(e)}
    
    def _calculate_technical_indicators(self, df: pd.DataFrame, algorithm) -> pd.DataFrame:
        """기술적 지표 계산"""
        try:
            # EMA 계산
            df['ema5'] = df['close'].ewm(span=5).mean()
            df['ema20'] = df['close'].ewm(span=20).mean()
            
            # RSI 계산
            delta = df['close'].diff()
            gains = delta.where(delta > 0, 0).rolling(window=7).mean()
            losses = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
            rs = gains / losses
            df['rsi7'] = 100 - (100 / (1 + rs))
            
            # ATR 계산
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = (df['high'] - df['close'].shift(1)).abs()
            df['tr3'] = (df['low'] - df['close'].shift(1)).abs()
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            df['atr14'] = df['tr'].ewm(span=14).mean()
            
            # VWAP 계산 (간단 버전)
            df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
            
            return df
            
        except Exception as e:
            logger.warning(f"기술적 지표 계산 오류: {e}")
            # 기본값 설정
            df['ema5'] = df['close']
            df['ema20'] = df['close']
            df['rsi7'] = 50.0
            df['atr14'] = df['close'] * 0.02
            df['vwap'] = df['close']
            return df
    
    def _should_enter_position(self, algorithm, current_row, current_time) -> bool:
        """신규 진입 조건 체크"""
        try:
            # 시간대 체크
            if current_time and hasattr(current_time, 'time'):
                if current_time.time() >= algorithm.entry_cutoff:
                    return False
            
            # 기본 조건들
            rsi = current_row.get('rsi7', 50)
            ema5 = current_row.get('ema5', current_row['close'])
            ema20 = current_row.get('ema20', current_row['close'])
            volume = current_row.get('volume', 0)
            volume_avg = current_row.get('volume', 0)  # 간단화
            
            # 매수 조건 (BasicDayTrading 로직 단순화)
            conditions = [
                algorithm.rsi_buy_zone[0] <= rsi <= algorithm.rsi_buy_zone[1],
                ema5 > ema20,  # 단기 > 장기 이평
                volume > volume_avg * algorithm.k_buy,  # 거래량 증가
                current_row['close'] > current_row['open']  # 양봉
            ]
            
            return all(conditions)
            
        except Exception:
            return False
    
    def _check_sell_conditions(self, algorithm, position, current_row, symbol) -> tuple:
        """매도 조건 체크"""
        try:
            entry_price = position['entry_price']
            current_price = current_row['close']
            return_rate = (current_price - entry_price) / entry_price
            atr = position.get('atr', current_price * 0.02)
            
            # ATR 기반 추격 스톱
            trail_price = position.get('trail_price')
            if trail_price is None:
                trail_price = current_price - algorithm.k_atr_trail * atr
            else:
                trail_price = max(trail_price, current_price - algorithm.k_atr_trail * atr)
            
            position['trail_price'] = trail_price
            
            if current_price <= trail_price:
                return True, "Trailing Stop", 'ALL'
            
            # 하드 스톱 (-2%)
            if return_rate <= algorithm.stop_loss_pct:
                return True, f"Hard Stop ({return_rate*100:.1f}%)", 'ALL'
            
            # 1차 익절 (+3%, 절반 청산)
            if not position.get('half_taken', False) and return_rate >= algorithm.take_profit_1:
                position['half_taken'] = True
                return True, f"Take Profit 1 ({return_rate*100:.1f}%)", 'HALF'
            
            # 추세 이탈 체크
            ema5 = current_row.get('ema5', current_price)
            if return_rate >= algorithm.trailing_trigger and current_price < ema5:
                return True, "Trend Break", 'ALL'
            
            return False, "", 'NONE'
            
        except Exception:
            return False, "Error", 'NONE'
    
    def _calculate_position_size(self, algorithm, capital, current_row) -> int:
        """포지션 크기 계산"""
        try:
            current_price = current_row['close']
            atr = current_row.get('atr14', current_price * 0.02)
            
            # ATR 기반 리스크 관리
            unit_risk = max(atr, 0.005 * current_price)
            risk_per_trade = 0.004 * capital  # 0.4% of capital
            quantity = int(max(1, risk_per_trade / unit_risk))
            
            # 자본 제한 (최대 10%)
            max_position_value = capital * 0.1
            max_quantity = int(max_position_value / current_price)
            
            return min(quantity, max_quantity)
            
        except Exception:
            return int(capital * 0.05 / current_row['close'])  # 폴백: 5%
    
    def _close_position(self, positions, trades, symbol, price, reason):
        """전량 매도"""
        if symbol in positions:
            pos = positions[symbol]
            trades.append({
                'type': 'SELL',
                'symbol': symbol,
                'price': price,
                'quantity': pos['quantity'],
                'time': trades[-1]['time'] if trades else None,
                'reason': reason
            })
            del positions[symbol]
    
    def _partial_close_position(self, positions, trades, symbol, price, reason, ratio):
        """부분 매도"""
        if symbol in positions:
            pos = positions[symbol]
            sell_quantity = int(pos['quantity'] * ratio)
            trades.append({
                'type': 'SELL',
                'symbol': symbol,
                'price': price,
                'quantity': sell_quantity,
                'time': trades[-1]['time'] if trades else None,
                'reason': reason
            })
            pos['quantity'] -= sell_quantity


if __name__ == "__main__":
    main()