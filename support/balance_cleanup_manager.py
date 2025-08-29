#!/usr/bin/env python3
"""
Balance Cleanup Manager - 잔고 정리 전용 모듈
자동매매 및 단타매매 시작 전에 독립적으로 실행되는 잔고 정리 시스템
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BalanceCleanupManager:
    """잔고 정리 전용 관리 클래스"""
    
    def __init__(self, api_connector, account_type: str = "REAL"):
        """
        BalanceCleanupManager 초기화
        
        Args:
            api_connector: API 연결 객체
            account_type: 계좌 유형 ("REAL" 또는 "MOCK")
        """
        self.api = api_connector
        self.account_type = account_type
        self.account_display = "실계좌" if account_type == "REAL" else "모의계좌"
        
        logger.info(f"BalanceCleanupManager 초기화: {self.account_display}")
    
    async def execute_balance_cleanup(self) -> Dict[str, Any]:
        """
        잔고 정리 실행 (독립적)
        
        Returns:
            Dict: 잔고 정리 결과
        """
        try:
            logger.info(f"[{self.account_display}] 잔고 정리 시작")
            print(f"\n[{self.account_display}] 잔고 정리를 시작합니다...")
            
            # 현재 포지션 조회
            positions = await self.api.get_positions()
            if not positions:
                result = {
                    "success": True,
                    "sold_stocks": 0,
                    "kept_stocks": 0,
                    "profit": "0원",
                    "message": "보유 종목이 없습니다.",
                    "analysis_results": []
                }
                print(f"[{self.account_display}] 보유 종목이 없습니다.")
                return result
            
            sold_count = 0
            kept_count = 0
            total_profit = 0.0
            analysis_results = []
            
            print(f"[{self.account_display}] {len(positions)}개 보유종목 분석 중...")
            
            for position in positions:
                try:
                    stock_code = position.get('stock_code')
                    stock_name = position.get('stock_name', '').strip()
                    
                    # 포지션 매매 결정 분석
                    decision = await self._analyze_position_decision(position)
                    analysis_results.append(f"{stock_name}({stock_code}): {decision['action']} - {decision['reason']}")
                    
                    if decision['action'] == 'SELL':
                        # 매도 주문 실행
                        sell_result = await self._execute_sell_order(position)
                        if sell_result['success']:
                            sold_count += 1
                            total_profit += sell_result.get('profit', 0)
                            logger.info(f"매도 실행: {stock_name}({stock_code}) - {decision['reason']}")
                            print(f"  ✓ 매도: {stock_name}({stock_code}) - {decision['reason']}")
                        else:
                            kept_count += 1  # 매도 실패시 보유 유지
                            logger.warning(f"매도 실패: {stock_name}({stock_code}) - {sell_result.get('error', 'Unknown')}")
                            print(f"  ! 매도실패: {stock_name}({stock_code}) - {sell_result.get('error', 'Unknown')}")
                    else:
                        kept_count += 1
                        logger.info(f"보유 유지: {stock_name}({stock_code}) - {decision['reason']}")
                        print(f"  ○ 보유유지: {stock_name}({stock_code}) - {decision['reason']}")
                        
                except Exception as e:
                    logger.warning(f"포지션 처리 중 오류 ({position.get('stock_code', 'unknown')}): {e}")
                    kept_count += 1
                    analysis_results.append(f"오류: {position.get('stock_name', 'Unknown')} - {str(e)}")
                    print(f"  ! 오류: {position.get('stock_name', 'Unknown')} - {str(e)}")
            
            # 결과 요약
            result = {
                "success": True,
                "sold_stocks": sold_count,
                "kept_stocks": kept_count,
                "profit": f"{total_profit:+,.0f}원",
                "message": f"매도 {sold_count}개, 보유 {kept_count}개, 손익 {total_profit:+,.0f}원",
                "analysis_results": analysis_results
            }
            
            print(f"\n[{self.account_display}] 잔고 정리 완료:")
            print(f"  - 매도된 종목: {sold_count}개")
            print(f"  - 보유 유지 종목: {kept_count}개")
            print(f"  - 실현 손익: {total_profit:+,.0f}원")
            
            logger.info(f"[{self.account_display}] 잔고 정리 완료: 매도 {sold_count}개, 보유 {kept_count}개")
            
            return result
            
        except Exception as e:
            error_msg = f"잔고 정리 실행 실패: {e}"
            logger.error(f"[{self.account_display}] {error_msg}")
            print(f"\n[{self.account_display}] {error_msg}")
            
            return {
                "success": False,
                "sold_stocks": 0,
                "kept_stocks": 0,
                "profit": "실행 실패",
                "message": error_msg,
                "analysis_results": [f"시스템 오류: {str(e)}"],
                "error": str(e)
            }
    
    async def _analyze_position_decision(self, position: Dict[str, Any]) -> Dict[str, str]:
        """포지션 매매 결정 분석 (David Paul 분석 포함)"""
        try:
            stock_code = position.get('stock_code')
            stock_name = position.get('stock_name', '').strip()
            current_price = position.get('current_price', 0)
            avg_price = position.get('avg_price', 0)
            
            # 1. 기본 손절/익절 체크
            profit_rate = self._calculate_profit_rate(position)
            
            # 2. 2단계 매도 시스템 분석
            sell_analysis = await self._analyze_two_stage_sell_decision(position)
            
            # 3. 매매 결정
            if sell_analysis['stage1_sell']:
                return {"action": "SELL", "reason": f"1단계매도: {sell_analysis['stage1_reason']}"}
            elif sell_analysis['stage2_sell']:
                return {"action": "SELL", "reason": f"2단계매도: {sell_analysis['stage2_reason']}"}
            elif profit_rate <= -0.05:  # 5% 손절
                return {"action": "SELL", "reason": f"손절매: {profit_rate*100:.1f}%"}
            elif profit_rate >= 0.07:  # 7% 익절
                return {"action": "SELL", "reason": f"익절매: {profit_rate*100:.1f}%"}
            else:
                return {"action": "HOLD", "reason": f"현재수익률 {profit_rate*100:.1f}%"}
            
        except Exception as e:
            logger.warning(f"포지션 분석 중 오류 ({stock_code}): {e}")
            return {"action": "HOLD", "reason": f"분석오류: {str(e)}"}
    
    async def _analyze_two_stage_sell_decision(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """2단계 매도 시스템 분석 (간소화 버전)"""
        try:
            # David Paul 분석 통합
            dp_analysis = await self._analyze_david_paul_for_position(position.get('stock_code'))
            
            current_price = float(position.get('current_price', 0))
            avg_price = float(position.get('avg_price', 0))
            profit_rate = (current_price - avg_price) / avg_price if avg_price > 0 else 0
            
            # 1단계 매도 조건 (즉시 매도)
            stage1_sell = False
            stage1_reason = ""
            
            # David Paul 위험 신호 우선 확인
            if dp_analysis['non_validation']:
                stage1_sell = True
                stage1_reason = "DP Non-Validation: 가짜 신호 감지"
            elif dp_analysis['bearish_divergence']:
                stage1_sell = True
                stage1_reason = "DP 약세 다이버전스: 위험 신호"
            elif dp_analysis['rise_on_falling_volume']:
                stage1_sell = True
                stage1_reason = "DP 위험신호: 상승 중 거래량 감소"
            
            # 2단계 매도 조건 (익절)
            stage2_sell = False
            stage2_reason = ""
            
            if profit_rate >= 0.07:  # 7% 익절
                stage2_sell = True
                stage2_reason = f"잔고정리 익절: {profit_rate*100:.1f}%"
            
            return {
                'stage1_sell': stage1_sell,
                'stage1_reason': stage1_reason,
                'stage2_sell': stage2_sell,
                'stage2_reason': stage2_reason,
                'profit_rate': profit_rate,
                'dp_analysis': dp_analysis
            }
            
        except Exception as e:
            logger.warning(f"2단계 매도 분석 오류: {e}")
            return {
                'stage1_sell': False,
                'stage1_reason': f"분석 오류: {str(e)}",
                'stage2_sell': False,
                'stage2_reason': "",
                'profit_rate': 0,
                'dp_analysis': {}
            }
    
    async def _analyze_david_paul_for_position(self, stock_code: str) -> Dict[str, Any]:
        """간소화된 David Paul 분석"""
        try:
            from support.david_paul_volume_analysis import get_david_paul_analyzer
            import pandas as pd
            
            # 주가 데이터 조회
            price_data = await self.api.get_stock_price_async(stock_code)
            if not price_data or price_data.get('rt_cd') != '0':
                return self._get_safe_dp_analysis()
            
            output = price_data.get('output', {})
            current_price = float(output.get('stck_prpr', 0))
            volume = float(output.get('acml_vol', 0))
            
            if current_price <= 0 or volume <= 0:
                return self._get_safe_dp_analysis()
            
            # 간단한 추정 데이터로 DP 분석
            data_rows = []
            for i in range(20):
                variation = 0.98 + (i * 0.002)
                data_rows.append({
                    'close': current_price * variation,
                    'high': current_price * variation * 1.01,
                    'low': current_price * variation * 0.99,
                    'volume': volume * (0.8 + (i * 0.02))
                })
            
            df = pd.DataFrame(data_rows)
            dp_analyzer = get_david_paul_analyzer()
            dp_result = dp_analyzer.analyze_validation(df)
            
            return {
                'validation': dp_result.get('validation', False),
                'non_validation': dp_result.get('non_validation', False),
                'rise_on_falling_volume': dp_result.get('rise_on_falling_volume', False),
                'bearish_divergence': dp_result.get('divergence', {}).get('bearish_divergence', False),
                'volume_spike': dp_result.get('volume_spike', False)
            }
            
        except Exception as e:
            logger.warning(f"David Paul 분석 오류 {stock_code}: {e}")
            return self._get_safe_dp_analysis()
    
    def _get_safe_dp_analysis(self) -> Dict[str, Any]:
        """David Paul 분석 안전 기본값"""
        return {
            'validation': False,
            'non_validation': False,
            'rise_on_falling_volume': False,
            'bearish_divergence': False,
            'volume_spike': False
        }
    
    async def _execute_sell_order(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """매도 주문 실행"""
        try:
            stock_code = position.get('stock_code')
            stock_name = position.get('stock_name', '').strip()
            quantity = int(position.get('quantity', 0))
            current_price = float(position.get('current_price', 0))
            
            if quantity <= 0:
                return {"success": False, "error": "보유 수량이 0입니다"}
            
            # 시장가 매도 주문
            sell_result = await self.api.place_sell_order(
                stock_code=stock_code,
                quantity=quantity,
                price=0,  # 시장가
                order_type="market"
            )
            
            if sell_result and sell_result.get('success', False):
                # 손익 계산
                avg_price = float(position.get('avg_price', 0))
                profit = (current_price - avg_price) * quantity
                
                return {
                    "success": True,
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "quantity": quantity,
                    "price": current_price,
                    "profit": profit
                }
            else:
                error_msg = sell_result.get('error', '매도 주문 실패') if sell_result else '매도 주문 응답 없음'
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            logger.error(f"매도 주문 실행 중 오류: {e}")
            return {"success": False, "error": str(e)}
    
    def _calculate_profit_rate(self, position: Dict[str, Any]) -> float:
        """수익률 계산"""
        try:
            current_price = float(position.get('current_price', 0))
            avg_price = float(position.get('avg_price', 0))
            
            if avg_price > 0:
                return (current_price - avg_price) / avg_price
            else:
                return 0.0
                
        except Exception:
            return 0.0


# 전역 인스턴스 관리
_balance_cleanup_manager = None

def get_balance_cleanup_manager(api_connector, account_type: str = "REAL") -> BalanceCleanupManager:
    """BalanceCleanupManager 인스턴스 반환"""
    global _balance_cleanup_manager
    if _balance_cleanup_manager is None or _balance_cleanup_manager.account_type != account_type:
        _balance_cleanup_manager = BalanceCleanupManager(api_connector, account_type)
    return _balance_cleanup_manager


async def execute_standalone_balance_cleanup(account_type: str = "REAL") -> Dict[str, Any]:
    """
    독립적인 잔고 정리 실행 함수
    
    Args:
        account_type: 계좌 유형 ("REAL" 또는 "MOCK")
        
    Returns:
        Dict: 잔고 정리 결과
    """
    try:
        from support.api_connector import KISAPIConnector
        
        # API 연결
        api = KISAPIConnector(is_mock=(account_type == "MOCK"))
        
        # 잔고 정리 매니저 생성 및 실행
        cleanup_manager = get_balance_cleanup_manager(api, account_type)
        result = await cleanup_manager.execute_balance_cleanup()
        
        return result
        
    except Exception as e:
        error_msg = f"독립적 잔고 정리 실행 실패: {e}"
        logger.error(error_msg)
        
        return {
            "success": False,
            "sold_stocks": 0,
            "kept_stocks": 0,
            "profit": "실행 실패",
            "message": error_msg,
            "analysis_results": [],
            "error": str(e)
        }